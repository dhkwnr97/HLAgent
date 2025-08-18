"""
Tools for HLA Fine Mapping Agent.

Contains utility functions and tools for workflow management, file validation,
node execution, and integration with workchains.
"""

import os
import re
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime

from .agent_types import (
    NodeType, WorkflowValidationResult, FileValidationResult,
    ReadinessState, ContinueDecision, NodeResult, WorkflowConfiguration
)
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def validate_user_readiness(user_input: str) -> ReadinessState:
    """
    Validate user readiness response.
    
    Args:
        user_input: User's input string
        
    Returns:
        ReadinessState enum value
    """
    user_input = user_input.lower().strip()
    
    if user_input == "ready":
        return ReadinessState.READY
    elif user_input == "not ready":
        return ReadinessState.NOT_READY
    else:
        return ReadinessState.UNKNOWN


def validate_continue_decision(user_input: str) -> ContinueDecision:
    """
    Validate user's continue decision.
    
    Args:
        user_input: User's input string
        
    Returns:
        ContinueDecision enum value
    """
    user_input = user_input.lower().strip()
    
    if user_input == "continue":
        return ContinueDecision.CONTINUE
    elif user_input == "done!":
        return ContinueDecision.DONE
    else:
        return ContinueDecision.UNKNOWN


def parse_node_selection(user_input: str) -> WorkflowValidationResult:
    """
    Parse and validate user's node selection.
    
    Args:
        user_input: User's input string with node selections
        
    Returns:
        WorkflowValidationResult with validation results
    """
    try:
        # Extract nodes from input using regex
        node_pattern = r'node[1-5]'
        found_nodes = re.findall(node_pattern, user_input.lower())
        
        if not found_nodes:
            return WorkflowValidationResult(
                is_valid=False,
                selected_nodes=[],
                invalid_nodes=[],
                missing_dependencies=[],
                workflow_sequence=[],
                error_message="No valid nodes found in input"
            )
        
        # Remove duplicates while preserving order
        unique_nodes = []
        seen = set()
        for node in found_nodes:
            if node not in seen:
                unique_nodes.append(node)
                seen.add(node)
        
        # Validate nodes exist
        valid_nodes = [node.value for node in NodeType]
        invalid_nodes = [node for node in unique_nodes if node not in valid_nodes]
        
        if invalid_nodes:
            return WorkflowValidationResult(
                is_valid=False,
                selected_nodes=unique_nodes,
                invalid_nodes=invalid_nodes,
                missing_dependencies=[],
                workflow_sequence=[],
                error_message=f"Invalid nodes: {invalid_nodes}"
            )
        
        # Check dependencies
        missing_dependencies = validate_node_dependencies(unique_nodes)
        
        return WorkflowValidationResult(
            is_valid=len(missing_dependencies) == 0,
            selected_nodes=unique_nodes,
            invalid_nodes=[],
            missing_dependencies=missing_dependencies,
            workflow_sequence=unique_nodes,
            error_message=f"Missing dependencies: {missing_dependencies}" if missing_dependencies else None
        )
        
    except Exception as e:
        logger.error(f"Error parsing node selection: {e}")
        return WorkflowValidationResult(
            is_valid=False,
            selected_nodes=[],
            invalid_nodes=[],
            missing_dependencies=[],
            workflow_sequence=[],
            error_message=f"Error parsing node selection: {str(e)}"
        )


def validate_node_dependencies(selected_nodes: List[str]) -> List[str]:
    """
    Validate node dependencies and return missing dependencies.
    
    Args:
        selected_nodes: List of selected node names
        
    Returns:
        List of missing dependencies
    """
    missing_dependencies = []
    
    # Define node dependencies
    dependencies = {
        "node2": ["node1"],  # Node2 requires Node1 (unless previous run)
        "node3": ["node1"],  # Node3 requires Node1 (unless previous run)
        "node4": ["node1"],  # Node4 requires Node1 (unless previous run)
        "node5": []  # Node5 can run independently with existing results
    }
    
    # Check for missing dependencies
    for node in selected_nodes:
        if node in dependencies:
            for dep in dependencies[node]:
                if dep not in selected_nodes:
                    # Check if dependency was satisfied in previous runs
                    if not check_previous_node_results(dep):
                        missing_dependencies.append(f"{node} requires {dep}")
    
    return missing_dependencies


def check_previous_node_results(node_name: str) -> bool:
    """
    Check if a node was executed in previous runs by looking for output files.
    
    Args:
        node_name: Name of the node to check
        
    Returns:
        True if node was previously executed
    """
    try:
        output_dir = Path(os.getenv("HLAGENT_MAIN_DIRECTORY", ".")) / "data" / "output"
        
        # Define expected output patterns for each node
        expected_outputs = {
            "node1": [".hat", ".chped", ".bed", ".bim", ".fam"],
            "node2": [".assoc.logistic", ".assoc.linear"],
            "node3": [".txt", ".json", ".csv"],
            "node4": [".omnibus"],
            "node5": [".meta", "_summary.txt"]
        }
        
        if node_name not in expected_outputs:
            return False
        
        # Check if any expected output files exist
        for pattern in expected_outputs[node_name]:
            if pattern.startswith("."):
                # File extension pattern
                matching_files = list(output_dir.rglob(f"*{pattern}"))
            else:
                # Suffix pattern
                matching_files = list(output_dir.rglob(f"*{pattern}*"))
            
            if matching_files:
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error checking previous node results: {e}")
        return False


def validate_required_files(node_name: str) -> FileValidationResult:
    """
    Validate that required files exist for a specific node.
    
    Args:
        node_name: Name of the node to validate files for
        
    Returns:
        FileValidationResult with validation status
    """
    try:
        output_dir = Path(os.getenv("HLAGENT_MAIN_DIRECTORY", ".")) / "data" / "output"
        
        # Define required files for each node
        required_files = {
            "node1": [".hped", ".phe"],
            "node2": [".bed", ".bim", ".fam", ".phe"],
            "node3": [".bed", ".bim", ".fam", ".phe"],
            "node4": [".aa", ".phe", ".fam"],
            "node5": [".assoc.logistic", ".assoc.linear"]  # At least 2 files
        }
        
        if node_name not in required_files:
            return FileValidationResult(
                is_valid=False,
                has_hped=False,
                has_phe=False,
                missing_files=[],
                error_message=f"Unknown node: {node_name}"
            )
        
        missing_files = []
        has_hped = False
        has_phe = False
        
        for pattern in required_files[node_name]:
            if pattern.startswith("."):
                # File extension pattern
                matching_files = list(output_dir.rglob(f"*{pattern}"))
            else:
                # Suffix pattern  
                matching_files = list(output_dir.rglob(f"*{pattern}*"))
            
            if not matching_files:
                missing_files.append(pattern)
            else:
                if pattern == ".hped":
                    has_hped = True
                elif pattern == ".phe":
                    has_phe = True
        
        is_valid = len(missing_files) == 0
        
        return FileValidationResult(
            is_valid=is_valid,
            has_hped=has_hped,
            has_phe=has_phe,
            missing_files=missing_files,
            error_message=f"Missing required files: {missing_files}" if missing_files else None
        )
        
    except Exception as e:
        logger.error(f"Error validating required files: {e}")
        return FileValidationResult(
            is_valid=False,
            has_hped=False,
            has_phe=False,
            missing_files=[],
            error_message=f"Error validating files: {str(e)}"
        )


def get_node_description(node_name: str) -> str:
    """
    Get description for a specific node.
    
    Args:
        node_name: Name of the node
        
    Returns:
        Node description string
    """
    descriptions = {
        "node1": "HLA binary marker panel creation (IMGT2SEQ → Nomencleaner → Binary Marker Generator)",
        "node2": "Regression analysis from HLA binary marker panel with visualization",
        "node3": "Stepwise conditional regression from HLA binary marker panel",
        "node4": "Omnibus test from HLA binary marker panel (requires genotype phasing)",
        "node5": "Meta analysis from over 2 HLA binary marker panels"
    }
    
    return descriptions.get(node_name, f"Unknown node: {node_name}")


def get_node_requirements(node_name: str) -> str:
    """
    Get requirements for a specific node.
    
    Args:
        node_name: Name of the node
        
    Returns:
        Node requirements string
    """
    requirements = {
        "node1": "Required .hped and .phe files. Essential for first-time users.",
        "node2": "Requires HLA binary marker panel from Node1 (.bed, .bim, .fam, .phe files).",
        "node3": "Requires HLA binary marker panel from Node1 (.bed, .bim, .fam, .phe files).",
        "node4": "Requires HLA binary marker panel from Node1 and genotype phasing (.aa, .phe, .fam files).",
        "node5": "Requires 2+ .assoc.logistic/.linear files from Node2 runs on different datasets."
    }
    
    return requirements.get(node_name, f"Unknown requirements for node: {node_name}")


def get_node_outputs(node_name: str) -> List[str]:
    """
    Get expected output file extensions for a specific node.
    
    Args:
        node_name: Name of the node
        
    Returns:
        List of expected output file extensions
    """
    outputs = {
        "node1": [".hat", ".chped", ".bed", ".bim", ".fam"],
        "node2": [".assoc.logistic", ".assoc.linear", ".html", ".png", ".pdf", ".svg"],
        "node3": [".txt", ".json", ".csv"],
        "node4": [".omnibus", ".html", ".png", ".pdf", ".svg"],
        "node5": [".meta", "_summary.txt", ".png"]
    }
    
    return outputs.get(node_name, [])


def format_output_files_list(output_files: List[str], node_results: Dict[str, NodeResult] = None) -> str:
    """
    Format output files list for display.
    
    Args:
        output_files: List of output file paths
        node_results: Optional dictionary of node results
        
    Returns:
        Formatted string of output files
    """
    if not output_files:
        return "No output files generated."
    
    formatted_lines = []
    
    # Group files by node if node_results is provided
    if node_results:
        for node_name, result in node_results.items():
            if result.output_files:
                formatted_lines.append(f"📁 **{node_name.upper()}:**")
                for file_path in result.output_files:
                    file_name = os.path.basename(file_path)
                    formatted_lines.append(f"   • {file_name}")
                formatted_lines.append("")
    else:
        # Simple list format
        formatted_lines.append("📁 **Generated Files:**")
        for file_path in output_files:
            file_name = os.path.basename(file_path)
            formatted_lines.append(f"   • {file_name}")
    
    return "\n".join(formatted_lines)


def create_workflow_execution_plan(workflow_sequence: List[str]) -> str:
    """
    Create a formatted execution plan for the workflow.
    
    Args:
        workflow_sequence: List of nodes in execution order
        
    Returns:
        Formatted execution plan string
    """
    plan_lines = []
    
    for i, node_name in enumerate(workflow_sequence, 1):
        description = get_node_description(node_name)
        requirements = get_node_requirements(node_name)
        outputs = get_node_outputs(node_name)
        
        plan_lines.append(f"{i}. **{node_name.upper()}:** {description}")
        plan_lines.append(f"   📋 Requirements: {requirements}")
        plan_lines.append(f"   📤 Outputs: {', '.join(outputs)}")
        plan_lines.append("")
    
    return "\n".join(plan_lines)


def estimate_workflow_duration(workflow_sequence: List[str]) -> str:
    """
    Estimate workflow duration based on selected nodes.
    
    Args:
        workflow_sequence: List of nodes in execution order
        
    Returns:
        Estimated duration string
    """
    # Rough time estimates per node (in minutes)
    node_durations = {
        "node1": 15,  # HLA binary marker panel creation
        "node2": 10,  # Regression analysis
        "node3": 8,   # Stepwise regression
        "node4": 12,  # Omnibus test (includes phasing)
        "node5": 5    # Meta analysis
    }
    
    total_minutes = sum(node_durations.get(node, 5) for node in workflow_sequence)
    
    if total_minutes < 60:
        return f"~{total_minutes} minutes"
    else:
        hours = total_minutes // 60
        minutes = total_minutes % 60
        return f"~{hours}h {minutes}m"


def validate_output_directory() -> bool:
    """
    Validate that the output directory exists and is writable.
    
    Returns:
        True if output directory is accessible
    """
    try:
        output_dir = Path(os.getenv("HLAGENT_MAIN_DIRECTORY", ".")) / "data" / "output"
        
        # Create directory if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Test write access
        test_file = output_dir / ".test_write_access"
        test_file.write_text("test")
        test_file.unlink()
        
        return True
        
    except Exception as e:
        logger.error(f"Cannot access output directory: {e}")
        return False


def cleanup_temporary_files(file_patterns: List[str]) -> int:
    """
    Clean up temporary files matching the given patterns.
    
    Args:
        file_patterns: List of file patterns to clean up
        
    Returns:
        Number of files cleaned up
    """
    try:
        output_dir = Path(os.getenv("HLAGENT_MAIN_DIRECTORY", ".")) / "data" / "output"
        cleaned_count = 0
        
        for pattern in file_patterns:
            matching_files = list(output_dir.rglob(pattern))
            for file_path in matching_files:
                try:
                    file_path.unlink()
                    cleaned_count += 1
                except Exception as e:
                    logger.warning(f"Could not delete {file_path}: {e}")
        
        return cleaned_count
        
    except Exception as e:
        logger.error(f"Error cleaning up temporary files: {e}")
        return 0


def generate_workflow_summary(workflow_config: WorkflowConfiguration, 
                            node_results: Dict[str, NodeResult],
                            start_time: datetime,
                            end_time: datetime) -> str:
    """
    Generate a summary of the workflow execution.
    
    Args:
        workflow_config: Workflow configuration
        node_results: Dictionary of node results
        start_time: Workflow start time
        end_time: Workflow end time
        
    Returns:
        Formatted workflow summary string
    """
    try:
        duration = end_time - start_time
        total_files = sum(len(result.output_files) for result in node_results.values())
        successful_nodes = [name for name, result in node_results.items() if result.status == "completed"]
        failed_nodes = [name for name, result in node_results.items() if result.status == "error"]
        
        summary_lines = [
            f"**Workflow Summary:**",
            f"├── Nodes executed: {', '.join(workflow_config.workflow_sequence)}",
            f"├── Successful: {len(successful_nodes)}/{len(workflow_config.workflow_sequence)}",
            f"├── Duration: {duration}",
            f"├── Output files: {total_files}",
            f"└── Status: {'✅ Completed' if not failed_nodes else '❌ Partial completion'}"
        ]
        
        if failed_nodes:
            summary_lines.append(f"**Failed nodes:** {', '.join(failed_nodes)}")
        
        return "\n".join(summary_lines)
        
    except Exception as e:
        logger.error(f"Error generating workflow summary: {e}")
        return f"Error generating summary: {str(e)}"


def get_workflow_recommendations(selected_nodes: List[str]) -> List[str]:
    """
    Get recommendations for improving the workflow.
    
    Args:
        selected_nodes: List of selected nodes
        
    Returns:
        List of recommendation strings
    """
    recommendations = []
    
    # Check for first-time user recommendations
    if "node1" not in selected_nodes:
        if check_previous_node_results("node1"):
            recommendations.append("✓ Node1 results found from previous runs - good to proceed")
        else:
            recommendations.append("⚠️ Consider including Node1 if this is your first HLA fine mapping analysis")
    
    # Check for visualization recommendations
    if "node2" in selected_nodes:
        recommendations.append("✓ Node2 includes visualization plots for results interpretation")
    
    # Check for advanced analysis recommendations
    if "node3" in selected_nodes:
        recommendations.append("✓ Node3 provides stepwise regression for independent signal identification")
    
    # Check for omnibus test recommendations
    if "node4" in selected_nodes:
        recommendations.append("ℹ️ Node4 requires genotype phasing - will be handled automatically")
    
    # Check for meta-analysis recommendations
    if "node5" in selected_nodes:
        recommendations.append("ℹ️ Node5 requires multiple dataset results - ensure you have previous Node2 outputs")
    
    return recommendations