"""
Type definitions for HLA Imputation Agent.

Defines enums and data structures used throughout the HLA Imputation Agent system.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


class HLAImputationState(Enum):
    """States for the HLA Imputation Agent workflow."""
    IDLE = "idle"                           # Initial state, scanning tools
    TOOL_SELECTION = "tool_selection"       # Showing available tools to user
    INPUT_VALIDATION = "input_validation"   # Validating user input format requirements
    READY_CHECK = "ready_check"             # Checking if user is ready to proceed
    FILE_CONVERSION = "file_conversion"     # Converting input files
    PARAMETER_HANDOFF = "parameter_handoff" # Handing off to parameter handler
    EXECUTION = "execution"                 # Executing the HLA imputation tool
    COMPLETED = "completed"                 # Task completed successfully
    ERROR = "error"                         # Error state
    CANCELLED = "cancelled"                 # User cancelled the workflow


class HLAImputationTool(Enum):
    """Supported HLA imputation tools."""
    COOKHLA = "cookhla"
    HLAHD = "hlahd"
    OPTITYPE = "optitype"


class InputFormat(Enum):
    """Input data formats required by different tools."""
    PLINK_BINARY = "plink_binary"  # .bed, .bim, .fam files
    FASTQ_PAIRED = "fastq_paired"  # R1.fastq, R2.fastq files
    OTHER = "other"                # Other format requiring conversion


class ResponseType(Enum):
    """Types of responses from the agent."""
    INFO = "info"
    REQUEST_INPUT = "request_input"
    CONFIRMATION = "confirmation"
    COMPLETION = "completion"
    ERROR = "error"


@dataclass
class HLAToolInfo:
    """Information about an HLA imputation tool."""
    name: str
    display_name: str
    description: str
    input_format: InputFormat
    input_description: str
    output_extensions: List[str]
    output_prefixes: List[str]
    yaml_path: str
    python_script_path: str
    advantages: List[str]
    is_supported: bool = True


@dataclass
class WorkflowState:
    """Current state of the HLA imputation workflow."""
    current_state: HLAImputationState
    selected_tool: Optional[HLAImputationTool]
    tool_info: Optional[HLAToolInfo]
    output_files: List[str]
    requester_agent: str
    task_id: str
    is_standalone: bool
    error_message: Optional[str] = None


@dataclass
class AgentResponse:
    """Response from the HLA imputation agent."""
    response_type: ResponseType
    message: str
    requires_input: bool
    session_complete: bool = False
    data: Optional[Dict[str, Any]] = None


@dataclass
class HLAImputationRequest:
    """Request for HLA imputation from supervisor or direct usage."""
    tool_name: Optional[str]
    requester_agent: str
    task_id: str
    context: Optional[str] = None