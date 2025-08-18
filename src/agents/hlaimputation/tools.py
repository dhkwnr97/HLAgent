"""
Tools and utilities for HLA Imputation Agent.

This module provides tools for:
- Scanning available HLA imputation tools
- Managing workchain integration
- Handling tool selection and configuration
"""

import os
from pathlib import Path
from typing import List, Dict, Optional, Callable
from dotenv import load_dotenv

from .agent_types import (
    HLAToolInfo, InputFormat
)
from src.core.workchain import create_workchain
from src.utils.logger import setup_logger

logger = setup_logger(__name__)
load_dotenv()


class HLAToolScanner:
    """
    Scanner for available HLA imputation tools.
    
    This class scans the HLA imputation tools directory and identifies
    available tools, their capabilities, and configuration requirements.
    """
    
    def __init__(self, tools_directory: str = None):
        if tools_directory is None:
            tools_directory = os.path.join(
                os.getenv("HLAGENT_MAIN_DIRECTORY", "/home/hanjg/App/Agents/HLAgent-main"),
                "src/tools/HLAimputation"
            )
        self.tools_directory = Path(tools_directory)
        
        # Tool information database
        self.tool_database = {
            "cookhla": HLAToolInfo(
                name="cookhla",
                display_name="CookHLA",
                description="Population-scale HLA imputation using reference panels. Highly accurate for common populations with good reference data.",
                input_format=InputFormat.PLINK_BINARY,
                input_description="PLINK binary files (.bed, .bim, .fam) + Reference panel data",
                output_extensions=[".hped", ".alleles"],
                output_prefixes=[],
                yaml_path=os.path.join(self.tools_directory, "cookhla/cookhla_run_config_orig.yaml"),
                python_script_path=os.path.join(self.tools_directory, "cookhla/cookhla_run.py"),
                advantages=[
                    "High accuracy for population-scale data",
                    "Excellent for common populations",
                    "Uses population-specific reference panels",
                    "Fast processing for large datasets"
                ]
            ),
            "hlahd": HLAToolInfo(
                name="hlahd",
                display_name="HLA-HD",
                description="High-resolution HLA typing from NGS data. Excellent for novel allele discovery and detailed typing.",
                input_format=InputFormat.FASTQ_PAIRED,
                input_description="Paired-end FASTQ files (R1.fastq, R2.fastq)",
                output_extensions=["_final.result.txt"],
                output_prefixes=[],
                yaml_path=os.path.join(self.tools_directory, "hlahd/hlahd_run_config_orig.yaml"),
                python_script_path=os.path.join(self.tools_directory, "hlahd/hlahd_run.py"),
                advantages=[
                    "High-resolution typing to 4-field level",
                    "Can discover novel alleles",
                    "Direct from sequencing data",
                    "Comprehensive allele database"
                ]
            ),
            "optitype": HLAToolInfo(
                name="optitype",
                display_name="OptiType",
                description="Precision HLA typing from RNA-seq and DNA-seq data. Optimized for accurate Class I typing.",
                input_format=InputFormat.FASTQ_PAIRED,
                input_description="Paired-end FASTQ files (R1.fastq, R2.fastq)",
                output_extensions=["_result.tsv"],
                output_prefixes=[],
                yaml_path=os.path.join(self.tools_directory, "optitype/optitype_run_config_orig.yaml"),
                python_script_path=os.path.join(self.tools_directory, "optitype/optitype_run.py"),
                advantages=[
                    "Optimized for HLA Class I (A, B, C)",
                    "Works with both DNA and RNA data",
                    "High precision and recall",
                    "Robust against sequencing errors"
                ]
            )
        }
    
    def scan_available_tools(self) -> List[HLAToolInfo]:
        """
        Scan the tools directory and return available tools.
        
        Returns:
            List of HLAToolInfo objects for available tools
        """
        available_tools = []
        
        try:
            if not self.tools_directory.exists():
                logger.error(f"Tools directory not found: {self.tools_directory}")
                return available_tools
            
            # Scan directory for tool folders
            for item in self.tools_directory.iterdir():
                if item.is_dir():
                    tool_name = item.name.lower()
                    
                    # Skip system folders and tools marked as not supported
                    if (tool_name in ["__pycache__", ".git", ".pytest_cache", ".vscode"] or 
                        "_notsupported" in tool_name.lower()):
                        logger.debug(f"Skipping system/unsupported folder: {tool_name}")
                        continue
                    
                    # Check if this tool is in our database
                    if tool_name in self.tool_database:
                        tool_info = self.tool_database[tool_name]
                        
                        # Verify required files exist
                        if self._verify_tool_files(tool_info):
                            tool_info.is_supported = True
                            available_tools.append(tool_info)
                            logger.info(f"Found supported tool: {tool_name}")
                        else:
                            tool_info.is_supported = False
                            logger.warning(f"Tool {tool_name} missing required files")
                    else:
                        logger.info(f"Unknown tool found: {tool_name}")
            
            logger.info(f"Scan complete. Found {len(available_tools)} supported tools")
            return available_tools
            
        except Exception as e:
            logger.error(f"Error scanning tools directory: {e}")
            return available_tools
    
    def _verify_tool_files(self, tool_info: HLAToolInfo) -> bool:
        """
        Verify that required files exist for a tool.
        
        Args:
            tool_info: Tool information to verify
            
        Returns:
            True if all required files exist
        """
        try:
            # Check YAML config file
            if not Path(tool_info.yaml_path).exists():
                logger.warning(f"Missing YAML config: {tool_info.yaml_path}")
                return False
            
            # Check Python script
            if not Path(tool_info.python_script_path).exists():
                logger.warning(f"Missing Python script: {tool_info.python_script_path}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error verifying tool files for {tool_info.name}: {e}")
            return False
    
    def get_tool_by_name(self, name: str) -> Optional[HLAToolInfo]:
        """
        Get tool information by name.
        
        Args:
            name: Tool name to look up
            
        Returns:
            HLAToolInfo object or None if not found
        """
        name = name.lower().strip()
        return self.tool_database.get(name)
    
    def get_supported_tool_names(self) -> List[str]:
        """
        Get list of supported tool names.
        
        Returns:
            List of supported tool names
        """
        available_tools = self.scan_available_tools()
        return [tool.name for tool in available_tools if tool.is_supported]


class HLAWorkchainManager:
    """
    Manager for HLA imputation workchain integration.
    
    This class handles the workchain execution for different HLA tools,
    providing a unified interface for parameter handling and tool execution.
    """
    
    def __init__(self, supervisor_handoff_callback: Optional[Callable] = None):
        self.supervisor_handoff_callback = supervisor_handoff_callback
        self.workchain = create_workchain(
            supervisor_handoff_callback=supervisor_handoff_callback
        )
    
    async def execute_tool_workchain(self, tool_info: HLAToolInfo) -> List[str]:
        """
        Execute workchain for the specified tool.
        
        Args:
            tool_info: Information about the tool to execute
            
        Returns:
            List of output file paths generated
        """
        try:
            logger.info(f"Executing workchain for tool: {tool_info.name}")
            
            # Execute workchain with tool-specific parameters
            output_files = await self.workchain.execute_workchain(
                yaml_path=tool_info.yaml_path,
                python_script_path=tool_info.python_script_path,
                output_file_extensions=tool_info.output_extensions,
                output_file_prefixes=tool_info.output_prefixes
            )
            
            logger.info(f"Workchain completed. Generated {len(output_files)} output files")
            return output_files
            
        except Exception as e:
            logger.error(f"Workchain execution failed for {tool_info.name}: {e}")
            return []
    
    def get_workchain_summary(self) -> Dict[str, any]:
        """
        Get summary of last workchain execution.
        
        Returns:
            Dictionary containing execution summary
        """
        try:
            return self.workchain.get_execution_summary()
        except Exception as e:
            logger.error(f"Error getting workchain summary: {e}")
            return {"error": str(e)}


class HLAToolSelector:
    """
    Helper class for tool selection and validation.
    """
    
    @staticmethod
    def parse_user_selection(user_input: str, available_tools: List[HLAToolInfo]) -> Optional[HLAToolInfo]:
        """
        Parse user tool selection input.
        
        Args:
            user_input: User's input (tool name or number)
            available_tools: List of available tools
            
        Returns:
            Selected HLAToolInfo or None if invalid
        """
        user_input = user_input.strip()
        
        if not user_input:
            # Default to cookhla
            for tool in available_tools:
                if tool.name == "cookhla":
                    return tool
            return available_tools[0] if available_tools else None
        
        # Try parsing as number
        try:
            tool_number = int(user_input)
            if 1 <= tool_number <= len(available_tools):
                return available_tools[tool_number - 1]
        except ValueError:
            pass
        
        # Try parsing as tool name
        user_input_lower = user_input.lower()
        for tool in available_tools:
            if tool.name.lower() == user_input_lower:
                return tool
        
        return None
    
    @staticmethod
    def validate_tool_selection(tool_info: HLAToolInfo) -> bool:
        """
        Validate that a tool selection is supported.
        
        Args:
            tool_info: Tool information to validate
            
        Returns:
            True if tool is supported
        """
        return tool_info is not None and tool_info.is_supported