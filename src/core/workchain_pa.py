#!/usr/bin/env python3
"""
workchain_pa.py
===============
A simple, reusable work chain component for PydanticAI agent workflows that includes:
1. File monitoring before parameter handler handoff
2. Parameter handler handoff via supervisor agent
3. Python script execution
4. File monitoring after execution
5. Output file filtering and return

This work chain is designed to be used by any PydanticAI sub agent with simple import:
from src.core.workchain_pa import execute_workchain_pa
result = await execute_workchain_pa(orig_yaml_file, python_script_path, output_file_prefixes=[], output_file_suffixes=[])
"""

import os
from dotenv import load_dotenv
import subprocess
import asyncio
from typing import List, Dict, Any, Set
from pathlib import Path
from datetime import datetime

from src.utils.logger import setup_logger

logger = setup_logger(__name__)
load_dotenv()


def _get_all_files_recursive(directory: Path) -> Set[str]:
    """Get all files in directory and subdirectories recursively."""
    files = set()
    try:
        if directory.exists():
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    files.add(str(file_path))
    except Exception as e:
        logger.error(f"Error scanning directory {directory}: {e}")
    return files


def _snapshot_files_with_mtime(directory: Path) -> Dict[str, float]:
    """Create a snapshot of all files with their modification times."""
    snapshot = {}
    try:
        if directory.exists():
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    snapshot[str(file_path)] = os.path.getmtime(file_path)
    except Exception as e:
        logger.error(f"Error creating snapshot for directory {directory}: {e}")
    return snapshot


def _monitor_files_before_execution(output_directory: str) -> Dict[str, Any]:
    """Monitor files before parameter handler handoff."""
    output_dir = Path(output_directory)
    logger.info(f"Step 1: Taking initial file snapshot in: {output_dir}")
    
    files = _get_all_files_recursive(output_dir)
    snapshots = _snapshot_files_with_mtime(output_dir)
    
    logger.info(f"Found {len(files)} files before execution")
    return {
        "files": files,
        "snapshots": snapshots,
        "timestamp": datetime.now().isoformat()
    }


def _monitor_files_after_execution(output_directory: str) -> Dict[str, Any]:
    """Monitor files after Python script execution."""
    output_dir = Path(output_directory)
    logger.info(f"Step 4: Taking final file snapshot in: {output_dir}")
    
    files = _get_all_files_recursive(output_dir)
    snapshots = _snapshot_files_with_mtime(output_dir)
    
    logger.info(f"Found {len(files)} files after execution")
    return {
        "files": files,
        "snapshots": snapshots,
        "timestamp": datetime.now().isoformat()
    }


async def _handoff_to_parameter_handler_via_supervisor(original_yaml_path: str) -> bool:
    """Step 2: Handover to parameter handler agent for YAML modification via supervisor agent."""
    try:
        logger.info(f"Step 2: Handover to parameter handler agent for YAML modification: {original_yaml_path}")
        
        # Import at runtime to avoid circular imports
        from src.agents_pa.supervisor.Handover.ho_parameterhandler import ParameterHandlerHandover
        from src.agents_pa.supervisor.dependencies import SupervisorDependencies
        
        # Create supervisor dependencies for handover
        supervisor_deps = SupervisorDependencies.create_default(
            session_id=f"workchain_{hash(original_yaml_path)}",
        )
        
        # Execute handover to parameter handler via supervisor
        result = await ParameterHandlerHandover.handover_to_parameterhandler(
            original_yaml_path=original_yaml_path,
            deps=supervisor_deps
        )
        
        logger.info("Parameter handler handover completed via supervisor")
        # Check if handover was successful based on result message
        success = "completed successfully" in result or "Parameter modification completed" in result
        return success
        
    except Exception as e:
        logger.error(f"Error in parameter handler handover via supervisor: {e}")
        return False


async def _handoff_to_parameter_handler_via_streamlit_ui(original_yaml_path: str) -> bool:
    """Step 2: Alternative - Use Streamlit UI for parameter handler interaction."""
    try:
        logger.info(f"Step 2: Parameter handler via Streamlit UI: {original_yaml_path}")
        
        # Print instructions for using Streamlit UI instead of console
        print(f"""
🔧 **Parameter Handler - Streamlit UI Mode**

**YAML File**: {original_yaml_path}

**📱 Please use the Streamlit Web UI for parameter modification:**

1. **Open your browser** and navigate to the Streamlit app
2. **Go to page: p.2_ParameterChat** (use sidebar navigation)  
3. **Enter YAML path**: {original_yaml_path}
4. **Click "Start Parameter Session"**
5. **Chat with Parameter Handler** to modify parameters:
   - "Change line 19 to 18"
   - "Set line 47 to ['A', 'B', 'C']"
6. **Type "Done!"** when finished
7. **Confirm with "Yes"** to complete

**⏳ Waiting for parameter modification to complete...**
**The workflow will continue automatically once parameters are finalized.**

Press Enter when you have completed the parameter modification in the web UI...
""")
        
        # Wait for user confirmation that they've completed the web UI interaction
        input()
        
        logger.info("Parameter handler handover completed via Streamlit UI")
        return True
        
    except Exception as e:
        logger.error(f"Error in parameter handler Streamlit UI handoff: {e}")
        return False


def _execute_python_script(python_script_path: str) -> bool:
    """Step 3: Execute Python script after parameter handler finish."""
    try:
        logger.info(f"Step 3: Execute Python script: {python_script_path}")
        
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
                # Display script output to console
                print(f"Script output: {result.stdout}")
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


def _filter_new_output_files(
    pre_execution_data: Dict[str, Any], 
    post_execution_data: Dict[str, Any],
    output_file_suffixes: List[str] = None,
    output_file_prefixes: List[str] = None
) -> List[str]:
    """Step 5-6: Identify new files and filter by prefixes and extensions."""
    if output_file_suffixes is None:
        output_file_suffixes = [".bed", ".bim", ".fam"]
    if output_file_prefixes is None:
        output_file_prefixes = []
    
    pre_files = pre_execution_data["files"]
    post_files = post_execution_data["files"]
    pre_snapshots = pre_execution_data["snapshots"]
    post_snapshots = post_execution_data["snapshots"]
    
    # Step 5: Identify new files
    new_files = post_files - pre_files
    
    # Find modified files using modification time comparison
    modified_files = set()
    for file_path in post_files:
        if file_path in pre_snapshots:
            pre_mtime = pre_snapshots[file_path]
            post_mtime = post_snapshots.get(file_path, 0)
            if post_mtime > pre_mtime:
                modified_files.add(file_path)
    
    # Combine new and modified files
    updated_files = new_files | modified_files
    
    logger.info(f"Step 5: Found {len(new_files)} new files after execution")
    logger.info(f"Found {len(modified_files)} modified files after execution")
    logger.info(f"Total updated files: {len(updated_files)}")
    
    # Step 6: Filter files by prefixes and extensions
    logger.info(f"Step 6: Filter files by suffixes {output_file_suffixes} and prefixes {output_file_prefixes}")
    filtered_files = []
    for file_path in updated_files:
        file_name = os.path.basename(file_path)
        
        # Check file extensions (suffixes)
        has_valid_extension = any(file_path.endswith(ext) for ext in output_file_suffixes)
        
        # Check file prefixes
        has_valid_prefix = any(file_name.startswith(prefix) for prefix in output_file_prefixes)
        
        if has_valid_extension or has_valid_prefix:
            filtered_files.append(file_path)
    
    logger.info(f"Filtered to {len(filtered_files)} files matching criteria")
    return sorted(filtered_files)


async def execute_workchain_pa(
    orig_yaml_file: str,
    python_script_path: str,
    output_file_prefixes: List[str] = None,
    output_file_suffixes: List[str] = None,
    use_streamlit_ui: bool = False
) -> List[str]:
    """
    Execute the complete PydanticAI work chain workflow.
    
    Args:
        orig_yaml_file: Path to original YAML configuration file (must end with _orig.yaml)
        python_script_path: Path to Python script to execute
        output_file_prefixes: List of file prefixes to filter (default: ["HLA_SNP", "HLA_AA"])
        output_file_suffixes: List of file extensions to filter (default: [".hped", ".txt", ".pdf"])
        use_streamlit_ui: If True, use Streamlit UI for parameter handler; if False, use supervisor handoff (default: False)
        
    Returns:
        List of output file paths that match the filtering criteria
    """
    logger.info("Starting PydanticAI work chain execution")
    mode = "Streamlit UI" if use_streamlit_ui else "Supervisor handoff"
    logger.info(f"Parameter handler mode: {mode}")
    
    output_directory = os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"), "data/output")
    
    try:
        # Step 1: Take initial file snapshot
        pre_execution_data = _monitor_files_before_execution(output_directory)
        
        # Step 2: Handover to parameter handler - choose method based on flag
        if use_streamlit_ui:
            success = await _handoff_to_parameter_handler_via_streamlit_ui(orig_yaml_file)
        else:
            success = await _handoff_to_parameter_handler_via_supervisor(orig_yaml_file)
        
        if not success:
            logger.error("Parameter handler handoff failed")
            return []
        
        # Step 3: After parameter handler finish, Execute Python script
        success = _execute_python_script(python_script_path)
        if not success:
            logger.error("Python script execution failed")
            return []
        
        # Step 4: Take final file snapshot
        post_execution_data = _monitor_files_after_execution(output_directory)
        
        # Step 5-6: Identify new files and filter by prefixes and extensions
        filtered_files = _filter_new_output_files(
            pre_execution_data, 
            post_execution_data,
            output_file_suffixes=output_file_suffixes,
            output_file_prefixes=output_file_prefixes
        )
        
        logger.info(f"Work chain completed successfully. Found {len(filtered_files)} output files")
        
        # Display generated file paths to console
        if filtered_files:
            print(f"\n\n===== Generated Files ({len(filtered_files)} files) =====\n\n")
            for i, file_path in enumerate(filtered_files, 1):
                print(f"{i}. {file_path}")
            print("=" * 50)
        else:
            print("\n\n===== No files generated matching the criteria =====\n\n")
        
        return filtered_files
        
    except Exception as e:
        logger.error(f"Work chain execution failed: {e}")
        return []


# Convenience function for Streamlit UI mode
async def execute_workchain_pa_with_streamlit_ui(
    orig_yaml_file: str,
    python_script_path: str,
    output_file_prefixes: List[str] = None,
    output_file_suffixes: List[str] = None
) -> List[str]:
    """
    Execute workchain with Streamlit UI for parameter handler.
    
    This is a convenience function that calls execute_workchain_pa with use_streamlit_ui=True.
    """
    return await execute_workchain_pa(
        orig_yaml_file=orig_yaml_file,
        python_script_path=python_script_path,
        output_file_prefixes=output_file_prefixes,
        output_file_suffixes=output_file_suffixes,
        use_streamlit_ui=True
    )
