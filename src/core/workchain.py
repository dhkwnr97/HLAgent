#!/usr/bin/env python3
"""
workchain.py
===============
A reusable work chain component for agent workflows that includes:
1. File monitoring before parameter handler handoff
2. Parameter handler handoff via supervisor
3. Python script execution
4. File monitoring after execution
5. Output file filtering and return

This work chain is designed to be used by any agent that needs to:
- Modify YAML configuration files via parameter handler
- Execute Python scripts
- Monitor and return specific output files
"""

import os
from dotenv import load_dotenv
import glob
import subprocess
import asyncio
from typing import List, Dict, Any, Optional, Set
from pathlib import Path
from datetime import datetime

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


load_dotenv()

class WorkChain:
    """
    Reusable work chain component for agent workflows.
    
    This class provides a standardized workflow pattern that includes:
    1. Pre-execution file monitoring
    2. Parameter handler handoff for YAML modification
    3. Python script execution
    4. Post-execution file monitoring
    5. Output file filtering and return
    """
    
    def __init__(self, 
                 output_directory: str = os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"), "data/output"),
                 supervisor_handoff_callback: Optional[callable] = None):
        """
        Initialize the work chain.
        
        Args:
            output_directory: Directory to monitor for output files
            supervisor_handoff_callback: Callback function for supervisor handoff
        """
        self.output_directory = Path(output_directory)
        self.supervisor_handoff_callback = supervisor_handoff_callback
        self.pre_execution_files: Set[str] = set()
        self.post_execution_files: Set[str] = set()
        self.pre_execution_snapshots: Dict[str, float] = {}
        self.post_execution_snapshots: Dict[str, float] = {}
        
    def _get_all_files_recursive(self, directory: Path) -> Set[str]:
        """
        Get all files in directory and subdirectories recursively.
        
        Args:
            directory: Directory to scan
            
        Returns:
            Set of file paths
        """
        files = set()
        try:
            if directory.exists():
                for file_path in directory.rglob("*"):
                    if file_path.is_file():
                        files.add(str(file_path))
        except Exception as e:
            logger.error(f"Error scanning directory {directory}: {e}")
        
        return files
    
    def _snapshot_files_with_mtime(self, directory: Path) -> Dict[str, float]:
        """
        Create a snapshot of all files with their modification times.
        
        Args:
            directory: Directory to scan
            
        Returns:
            Dict mapping file paths to modification times
        """
        snapshot = {}
        try:
            if directory.exists():
                for file_path in directory.rglob("*"):
                    if file_path.is_file():
                        snapshot[str(file_path)] = os.path.getmtime(file_path)
        except Exception as e:
            logger.error(f"Error creating snapshot for directory {directory}: {e}")
        
        return snapshot
    
    def _monitor_files_before_execution(self) -> Set[str]:
        """
        Monitor files before parameter handler handoff.
        
        Returns:
            Set of file paths found before execution
        """
        logger.info(f"Monitoring files before execution in: {self.output_directory}")
        self.pre_execution_files = self._get_all_files_recursive(self.output_directory)
        self.pre_execution_snapshots = self._snapshot_files_with_mtime(self.output_directory)
        logger.info(f"Found {len(self.pre_execution_files)} files before execution")
        return self.pre_execution_files
    
    def _monitor_files_after_execution(self) -> Set[str]:
        """
        Monitor files after Python script execution.
        
        Returns:
            Set of file paths found after execution
        """
        logger.info(f"Monitoring files after execution in: {self.output_directory}")
        self.post_execution_files = self._get_all_files_recursive(self.output_directory)
        self.post_execution_snapshots = self._snapshot_files_with_mtime(self.output_directory)
        logger.info(f"Found {len(self.post_execution_files)} files after execution")
        return self.post_execution_files
    
    def _filter_new_output_files(self, 
                                file_extensions: List[str] = None,
                                file_prefixes: List[str] = None) -> List[str]:
        """
        Filter new or modified files based on extensions and prefixes using modification time.
        
        Args:
            file_extensions: List of file extensions to include (e.g., [".hped", ".txt", ".pdf"])
            file_prefixes: List of file prefixes to include (e.g., ["HLA_SNP", "HLA_AA"])
            
        Returns:
            List of filtered new or modified file paths
        """
        if file_extensions is None:
            file_extensions = [".hped", ".txt", ".pdf"]
        if file_prefixes is None:
            file_prefixes = ["HLA_SNP", "HLA_AA"]
        
        # Find new files (traditional way)
        new_files = self.post_execution_files - self.pre_execution_files
        
        # Find modified files (using modification time comparison)
        modified_files = set()
        for file_path in self.post_execution_files:
            if file_path in self.pre_execution_snapshots:
                # File existed before, check if it was modified
                pre_mtime = self.pre_execution_snapshots[file_path]
                post_mtime = self.post_execution_snapshots.get(file_path, 0)
                
                # If modification time changed, it was modified
                if post_mtime > pre_mtime:
                    modified_files.add(file_path)
        
        # Combine new and modified files
        updated_files = new_files | modified_files
        
        logger.info(f"Found {len(new_files)} new files after execution")
        logger.info(f"Found {len(modified_files)} modified files after execution")
        logger.info(f"Total updated files: {len(updated_files)}")
        
        # Filter by extensions and prefixes
        filtered_files = []
        for file_path in updated_files:
            file_name = os.path.basename(file_path)
            
            # Check file extensions
            has_valid_extension = any(file_path.endswith(ext) for ext in file_extensions)
            
            # Check file prefixes
            has_valid_prefix = any(file_name.startswith(prefix) for prefix in file_prefixes)
            
            if has_valid_extension or has_valid_prefix:
                filtered_files.append(file_path)
        
        logger.info(f"Filtered to {len(filtered_files)} files matching criteria")
        return sorted(filtered_files)
    
    async def _handoff_to_parameter_handler(self, yaml_path: str) -> bool:
        """
        Handoff to parameter handler agent via supervisor.
        
        Args:
            yaml_path: Path to YAML file to be modified
            
        Returns:
            True if handoff successful, False otherwise
        """
        try:
            if self.supervisor_handoff_callback:
                logger.info(f"Handing off to parameter handler for YAML: {yaml_path}")
                result = await self.supervisor_handoff_callback(
                    agent_name="parameterhandler",
                    task_description=f"Modify YAML configuration file: {yaml_path}",
                    yaml_path=yaml_path
                )
                logger.info("Parameter handler handoff completed")
                return result
            else:
                logger.warning("No supervisor handoff callback provided")
                return False
        except Exception as e:
            logger.error(f"Error in parameter handler handoff: {e}")
            return False
    
    def _execute_python_script(self, python_script_path: str) -> bool:
        """
        Execute the specified Python script.
        
        Args:
            python_script_path: Path to Python script to execute
            
        Returns:
            True if execution successful, False otherwise
        """
        try:
            logger.info(f"Executing Python script: {python_script_path}")
            
            # Change to project root directory for script execution
            project_root = Path(__file__).parents[2]
            
            # Execute the Python script
            result = subprocess.run(
                ["python", python_script_path],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            
            if result.returncode == 0:
                logger.info("Python script executed successfully")
                if result.stdout:
                    logger.info(f"Script output: {result.stdout}")
                return True
            else:
                logger.error(f"Python script failed with return code {result.returncode}")
                if result.stderr:
                    logger.error(f"Script error: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Python script execution timed out")
            return False
        except Exception as e:
            logger.error(f"Error executing Python script: {e}")
            return False
    
    async def execute_workchain(self,
                               yaml_path: str,
                               python_script_path: str,
                               output_file_extensions: List[str] = None,
                               output_file_prefixes: List[str] = None) -> List[str]:
        """
        Execute the complete work chain.
        
        Args:
            yaml_path: Path to YAML configuration file
            python_script_path: Path to Python script to execute
            output_file_extensions: List of file extensions to filter (default: [".hped", ".txt", ".pdf"])
            output_file_prefixes: List of file prefixes to filter (default: ["HLA_SNP", "HLA_AA"])
            
        Returns:
            List of output file paths that match the filtering criteria
        """
        logger.info("Starting work chain execution")
        
        try:
            # Step 1: Monitor files before execution
            self._monitor_files_before_execution()
            
            # Step 2: Handoff to parameter handler for YAML modification
            success = await self._handoff_to_parameter_handler(yaml_path)
            if not success:
                logger.error("Parameter handler handoff failed")
                return []
            
            # Step 3: Execute Python script
            success = self._execute_python_script(python_script_path)
            if not success:
                logger.error("Python script execution failed")
                return []
            
            # Step 4: Monitor files after execution
            self._monitor_files_after_execution()
            
            # Step 5: Filter and return new output files
            filtered_files = self._filter_new_output_files(
                file_extensions=output_file_extensions,
                file_prefixes=output_file_prefixes
            )
            
            logger.info(f"Work chain completed successfully. Found {len(filtered_files)} output files")
            return filtered_files
            
        except Exception as e:
            logger.error(f"Work chain execution failed: {e}")
            return []
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """
        Get summary of work chain execution.
        
        Returns:
            Dictionary containing execution summary
        """
        # Calculate modified files
        modified_files = set()
        for file_path in self.post_execution_files:
            if file_path in self.pre_execution_snapshots:
                pre_mtime = self.pre_execution_snapshots[file_path]
                post_mtime = self.post_execution_snapshots.get(file_path, 0)
                if post_mtime > pre_mtime:
                    modified_files.add(file_path)
        
        new_files = self.post_execution_files - self.pre_execution_files
        
        return {
            "pre_execution_files": len(self.pre_execution_files),
            "post_execution_files": len(self.post_execution_files),
            "new_files_created": len(new_files),
            "modified_files": len(modified_files),
            "total_updated_files": len(new_files | modified_files),
            "output_directory": str(self.output_directory),
            "timestamp": datetime.now().isoformat()
        }


# Convenience function for creating work chain instances
def create_workchain(output_directory: str = None, 
                    supervisor_handoff_callback: callable = None) -> WorkChain:
    """
    Create a work chain instance.
    
    Args:
        output_directory: Directory to monitor for output files
        supervisor_handoff_callback: Callback function for supervisor handoff
        
    Returns:
        WorkChain instance
    """
    if output_directory is None:
        output_directory = "/home/hanjg/App/Agents/HLAgent-main/data/output"
    
    return WorkChain(
        output_directory=output_directory,
        supervisor_handoff_callback=supervisor_handoff_callback
    )


# Example usage for genotype phasing agent
async def example_genotype_phasing_workchain(supervisor_handoff_callback):
    """
    Example usage of work chain for genotype phasing.
    
    Args:
        supervisor_handoff_callback: Callback function for supervisor handoff
        
    Returns:
        List of output file paths
    """
    workchain = create_workchain(supervisor_handoff_callback=supervisor_handoff_callback)
    
    # Execute work chain with genotype phasing specific parameters
    output_files = await workchain.execute_workchain(
        yaml_path=os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"), "src/tools/HATK/Runners/phasing_run_config_orig.yaml"),
        python_script_path=os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"), "src/tools/HATK/Runners/run_phasing.py"),
        output_file_extensions=[".bgl.phased", ".aa", ".markers"],
        output_file_prefixes=[]
    )
    
    return output_files


if __name__ == "__main__":
    # Simple test without supervisor handoff
    async def test_workchain():
        workchain = create_workchain()
        summary = workchain.get_execution_summary()
        print("Work chain test completed")
        print(f"Summary: {summary}")
    
    asyncio.run(test_workchain())