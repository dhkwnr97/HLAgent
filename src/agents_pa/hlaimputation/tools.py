"""
Tool functions for HLA Imputation Agent.
Contains tools for HLA tool scanning, workchain execution, and file handling.
"""

import os
import re
from typing import List, Dict, Tuple
from pydantic_ai import RunContext

from .dependencies import HLAImputationDependencies, HLAImputationSession
from .models import HLAImputationResult, HLAToolInfo, ToolSelectionResult
from .prompts import TOOL_FILE_REQUIREMENTS, TOOL_OUTPUT_DESCRIPTIONS
from src.core.workchain_pa import execute_workchain_pa
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def scan_hla_tools(tools_directory: str) -> List[HLAToolInfo]:
    """
    Scan HLA tools directory and return available tools information.
    
    Args:
        tools_directory: Path to HLA tools directory
        
    Returns:
        List of HLAToolInfo objects with tool details
    """
    try:
        if not os.path.exists(tools_directory):
            logger.error(f"HLA tools directory not found: {tools_directory}")
            return []
        
        tools = []
        directory_names = os.listdir(tools_directory)
        
        for dir_name in directory_names:
            # Skip files and docker_runner.py
            if not os.path.isdir(os.path.join(tools_directory, dir_name)):
                continue
                
            # Check if tool is supported (not ending with _Notsupported)
            supported = not re.search(r"_Notsupported$", dir_name)
            
            if supported:
                # Get file requirements for this tool
                required_files = TOOL_FILE_REQUIREMENTS.get(dir_name, "Unknown file requirements")
                
                tool_info = HLAToolInfo(
                    name=dir_name,
                    supported=supported,
                    required_files=[required_files],
                    description=f"HLA imputation using {dir_name.upper()} algorithm"
                )
                tools.append(tool_info)
                logger.info(f"Found supported HLA tool: {dir_name}")
            else:
                logger.info(f"Found unsupported HLA tool: {dir_name}")
        
        return sorted(tools, key=lambda x: x.name)
        
    except Exception as e:
        logger.error(f"Error scanning HLA tools: {str(e)}")
        return []


def validate_tool_selection(user_input: str, available_tools: List[str]) -> ToolSelectionResult:
    """
    Validate user's tool selection input.
    
    Args:
        user_input: User's tool selection (number or name)
        available_tools: List of available tool names
        
    Returns:
        ToolSelectionResult with validation details
    """
    try:
        user_input = user_input.strip().lower()
        
        # Check if input is a digit (tool number)
        if user_input.isdigit():
            tool_index = int(user_input) - 1  # Convert to 0-based index
            if 0 <= tool_index < len(available_tools):
                return ToolSelectionResult(
                    valid=True,
                    tool_name=available_tools[tool_index]
                )
            else:
                return ToolSelectionResult(
                    valid=False,
                    tool_name="",
                    error_message=f"Invalid tool number. Please choose between 1 and {len(available_tools)}"
                )
        
        # Check if input is a tool name
        for tool in available_tools:
            if tool.lower() == user_input:
                return ToolSelectionResult(
                    valid=True,
                    tool_name=tool
                )
        
        # Invalid selection
        tool_list = ", ".join([f"{i+1}({tool})" for i, tool in enumerate(available_tools)])
        return ToolSelectionResult(
            valid=False,
            tool_name="",
            error_message=f"Invalid tool selection. Available options: {tool_list}"
        )
        
    except Exception as e:
        logger.error(f"Error validating tool selection: {str(e)}")
        return ToolSelectionResult(
            valid=False,
            tool_name="",
            error_message=f"Error processing tool selection: {str(e)}"
        )


async def execute_hla_imputation_workflow(
    ctx: RunContext[HLAImputationDependencies],
    tool_name: str
) -> HLAImputationResult:
    """
    Execute HLA imputation workflow using workchain_pa.
    
    Args:
        ctx: Runtime context with dependencies
        tool_name: Name of the HLA tool to use
        
    Returns:
        HLAImputationResult with execution details
    """
    try:
        logger.info(f"Starting HLA imputation workflow for tool: {tool_name}")
        
        # Get configuration paths
        session = HLAImputationSession(ctx.deps)
        orig_yaml_file = session.get_tool_config_path(tool_name)
        python_script_path = session.get_tool_script_path(tool_name)
        
        # Execute workchain with tool-specific output file suffixes
        wc_result = await execute_workchain_pa(
            orig_yaml_file=orig_yaml_file,
            python_script_path=python_script_path,
            output_file_prefixes=[],
            output_file_suffixes=[".hped", ".alleles", "_final.result.txt", ".tsv"]
        )
        
        if wc_result:
            # Add output files to session
            session.add_output_files(wc_result)
            
            logger.info(f"HLA imputation completed successfully. Generated {len(wc_result)} files")
            
            return HLAImputationResult(
                success=True,
                tool_used=tool_name,
                output_files=wc_result,
                message=f"HLA imputation using {tool_name} completed successfully! Generated {len(wc_result)} files."
            )
        else:
            logger.error("Workchain execution returned no results")
            return HLAImputationResult(
                success=False,
                tool_used=tool_name,
                output_files=[],
                message="HLA imputation failed - no output files generated",
                error="Workchain execution returned empty results"
            )
            
    except Exception as e:
        error_msg = f"Error in HLA imputation workflow: {str(e)}"
        logger.error(error_msg)
        
        return HLAImputationResult(
            success=False,
            tool_used=tool_name,
            output_files=[],
            message="HLA imputation failed due to an error",
            error=error_msg
        )


def format_tool_list(tools: List[HLAToolInfo]) -> str:
    """
    Format tool list for display in welcome message.
    
    Args:
        tools: List of HLA tool information
        
    Returns:
        Formatted string for display
    """
    if not tools:
        return "No HLA imputation tools available."
    
    tool_list = []
    for i, tool in enumerate(tools, 1):
        tool_list.append(f"[{i}] **{tool.name.upper()}** - {tool.description}")
    
    return "\n".join(tool_list)


def format_file_requirements(tools: List[HLAToolInfo]) -> str:
    """
    Format file requirements for display in welcome message.
    
    Args:
        tools: List of HLA tool information
        
    Returns:
        Formatted string for display
    """
    if not tools:
        return "No file requirements available."
    
    requirements = []
    for tool in tools:
        req_text = tool.required_files[0] if tool.required_files else "Unknown requirements"
        requirements.append(f"- **{tool.name.upper()}**: {req_text}")
    
    return "\n".join(requirements)


def format_tool_selection_options(tools: List[str]) -> str:
    """
    Format tool selection options for display.
    
    Args:
        tools: List of available tool names
        
    Returns:
        Formatted string for display
    """
    if not tools:
        return "No tools available for selection."
    
    options = []
    for i, tool in enumerate(tools, 1):
        requirements = TOOL_FILE_REQUIREMENTS.get(tool, "Unknown requirements")
        options.append(f"[{i}] **{tool.upper()}** - {requirements}")
    
    return "\n".join(options)


def format_output_files_message(output_files: List[str]) -> str:
    """
    Format output files list for user display.
    
    Args:
        output_files: List of output file paths
        
    Returns:
        Formatted message string
    """
    if not output_files:
        return "No output files generated."
    
    file_list = []
    for file_path in output_files:
        filename = os.path.basename(file_path)
        file_list.append(f"   - {filename}")
    
    return "\n".join(file_list)


def get_output_descriptions(tool_name: str) -> str:
    """
    Get tool-specific output file descriptions.
    
    Args:
        tool_name: Name of the HLA tool
        
    Returns:
        Formatted output descriptions
    """
    return TOOL_OUTPUT_DESCRIPTIONS.get(
        tool_name, 
        "- 📊 **Output files** - HLA imputation results"
    )