"""
Type definitions for HLA Fine Mapping Agent.

Defines enums and data structures used throughout the HLA Fine Mapping Agent system.
"""

from enum import Enum
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from datetime import datetime


class HLAFineMappingState(Enum):
    """States for the HLA Fine Mapping Agent."""
    IDLE = "idle"
    WAITING_USER_READY = "waiting_user_ready"
    READY_CHECK = "ready_check"
    NODE_EXPLANATION = "node_explanation"
    WORKFLOW_CUSTOMIZATION = "workflow_customization"
    WORKFLOW_EXECUTION = "workflow_execution"
    WORKFLOW_COMPLETE = "workflow_complete"
    CONTINUE_PROMPT = "continue_prompt"
    COMPLETED = "completed"
    ERROR = "error"


class NodeType(Enum):
    """Available node types for HLA Fine Mapping workflows."""
    NODE1 = "node1"  # HLA binary marker panel creation
    NODE2 = "node2"  # Regression analysis from HLA binary marker panel
    NODE3 = "node3"  # Stepwise conditional regression from HLA binary marker panel
    NODE4 = "node4"  # Omnibus test from HLA binary marker panel
    NODE5 = "node5"  # Meta analysis from over 2 HLA binary marker panel


class WorkflowExecutionState(Enum):
    """States during workflow execution."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class NodeResult:
    """Result of a node execution."""
    node_name: str
    status: str  # "completed", "error", "paused"
    output_files: List[str]
    error_message: Optional[str] = None
    execution_time: Optional[float] = None
    metadata: Dict[str, Any] = None


@dataclass
class WorkflowConfiguration:
    """Configuration for a workflow."""
    selected_nodes: List[str]
    workflow_sequence: List[str]
    description: str
    estimated_duration: Optional[str] = None
    dependencies: Dict[str, List[str]] = None


@dataclass
class AgentSession:
    """Session information for the agent."""
    session_id: str
    requester_agent: str
    task_id: str
    is_standalone: bool
    start_time: datetime
    current_state: HLAFineMappingState
    workflow_config: Optional[WorkflowConfiguration] = None
    output_files: List[str] = None
    conversation_history: List[Dict[str, str]] = None


class ResponseType(Enum):
    """Types of responses from the agent."""
    INFO = "info"
    REQUEST_INPUT = "request_input"
    WORKFLOW_STATUS = "workflow_status"
    ERROR = "error"
    COMPLETION = "completion"
    CONTINUE_PROMPT = "continue_prompt"


@dataclass
class AgentResponse:
    """Response from the agent."""
    response_type: ResponseType
    message: str
    current_state: HLAFineMappingState
    session_complete: bool = False
    requires_input: bool = False
    output_files: List[str] = None
    workflow_status: Dict[str, Any] = None
    error_details: Optional[str] = None


class ReadinessState(Enum):
    """User readiness states."""
    READY = "ready"
    NOT_READY = "not_ready"
    UNKNOWN = "unknown"


@dataclass
class FileValidationResult:
    """Result of file validation."""
    is_valid: bool
    has_hped: bool
    has_phe: bool
    missing_files: List[str]
    error_message: Optional[str] = None


@dataclass
class WorkflowValidationResult:
    """Result of workflow validation."""
    is_valid: bool
    selected_nodes: List[str]
    invalid_nodes: List[str]
    missing_dependencies: List[str]
    workflow_sequence: List[str]
    error_message: Optional[str] = None


class ContinueDecision(Enum):
    """User's decision to continue or finish."""
    CONTINUE = "continue"
    DONE = "done"
    UNKNOWN = "unknown"


@dataclass
class NodeExecutionContext:
    """Context for node execution."""
    node_name: str
    agent_session: AgentSession
    output_files: List[str]
    supervisor_handoff_callback: Optional[callable] = None
    workflow_pause_callback: Optional[callable] = None
    resume_callback: Optional[callable] = None


class PauseReason(Enum):
    """Reasons for workflow pause."""
    PARAMETER_MODIFICATION = "parameter_modification"
    SUPERVISOR_HANDOFF = "supervisor_handoff"
    USER_INPUT_REQUIRED = "user_input_required"
    ERROR_RECOVERY = "error_recovery"
    EXTERNAL_DEPENDENCY = "external_dependency"


@dataclass
class WorkflowPauseInfo:
    """Information about workflow pause."""
    reason: PauseReason
    pause_location: str
    resume_instructions: str
    required_files: List[str] = None
    handoff_agent: Optional[str] = None
    additional_context: Dict[str, Any] = None


@dataclass
class OutputFileInfo:
    """Information about output files."""
    file_path: str
    file_type: str
    generated_by_node: str
    size_bytes: int
    creation_time: datetime
    description: Optional[str] = None


@dataclass
class WorkflowMetrics:
    """Metrics for workflow execution."""
    total_nodes: int
    completed_nodes: int
    failed_nodes: int
    total_output_files: int
    total_execution_time: float
    start_time: datetime
    end_time: Optional[datetime] = None
    node_results: List[NodeResult] = None