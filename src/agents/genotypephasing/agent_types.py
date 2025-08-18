"""
Type definitions for Genotype Phasing Agent.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


class PhasingState(Enum):
    """States for the genotype phasing workflow."""
    IDLE = "idle"
    CHECKING_INPUT = "checking_input"
    WAITING_USER_READY = "waiting_user_ready"
    PARAMETER_HANDOFF = "parameter_handoff"
    EXECUTING_PHASING = "executing_phasing"
    COMPLETED = "completed"
    ERROR = "error"


class InputFormat(Enum):
    """Supported input formats for genotype phasing."""
    VCF = "vcf"
    PLINK = "plink"  # .bed, .bim, .fam
    BEAGLE = "beagle"  # .bgl, .markers
    UNKNOWN = "unknown"


class ResponseType(Enum):
    """Response types for agent communication."""
    INFO = "info"
    REQUEST_INPUT = "request_input"
    SUCCESS = "success"
    ERROR = "error"
    HANDOFF = "handoff"
    COMPLETION = "completion"


@dataclass
class PhasingResponse:
    """Response structure for genotype phasing agent."""
    response_type: ResponseType
    message: str
    requires_input: bool = False
    session_complete: bool = False
    data: Optional[Dict[str, Any]] = None
    output_files: Optional[List[str]] = None


@dataclass
class InputValidationResult:
    """Result of input file validation."""
    is_valid: bool
    format_type: InputFormat
    message: str
    files_found: List[str] = None


@dataclass
class PhasingWorkflowState:
    """State information for the phasing workflow."""
    current_state: PhasingState
    input_format: InputFormat
    output_files: List[str]
    error_message: str
    requester_agent: str
    task_id: str
    is_standalone: bool
    
    def __post_init__(self):
        if self.output_files is None:
            self.output_files = []
    
    def add_output_file(self, file_path: str):
        """Add an output file to the list."""
        if file_path not in self.output_files:
            self.output_files.append(file_path)
    
    def clear_output_files(self):
        """Clear the output files list."""
        self.output_files = []
    
    def set_error(self, error_msg: str):
        """Set error state."""
        self.error_message = error_msg
        self.current_state = PhasingState.ERROR


@dataclass
class PhasingRequest:
    """Request structure for genotype phasing."""
    requester_agent: str
    task_id: str
    input_files: List[str]
    output_prefix: str
    parameters: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}


@dataclass
class PhasingResult:
    """Result structure for completed phasing."""
    success: bool
    output_files: List[str]
    input_format: InputFormat
    execution_time: float
    error_message: str = ""
    
    def __post_init__(self):
        if self.output_files is None:
            self.output_files = []