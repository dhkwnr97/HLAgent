"""
Agent types and data structures for Parameter Handler Agent.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


class AgentState(Enum):
    """States for the Parameter Handler Agent."""
    IDLE = "idle"
    COPY_FILE = "copy_file"
    SHOW_CONTENT = "show_content"
    INTERACTIVE_EDIT = "interactive_edit"
    CONFIRMATION = "confirmation"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class YamlModificationRequest:
    """Request data for YAML modification."""
    original_yaml_path: str
    working_yaml_path: str
    requester_agent: str
    task_id: str


@dataclass 
class YamlEditCommand:
    """Command for editing a YAML line."""
    line_number: int
    new_value: str
    

@dataclass
class AgentSession:
    """Session data for the agent."""
    current_state: AgentState
    modification_request: Optional[YamlModificationRequest]
    yaml_content: List[str]
    pending_edits: List[YamlEditCommand]
    is_standalone: bool
    task_complete: bool
    awaiting_confirmation: bool
    
    
class ResponseType(Enum):
    """Types of responses from the agent."""
    INFO = "info"
    REQUEST_INPUT = "request_input"
    CONFIRMATION = "confirmation"  
    COMPLETION = "completion"
    ERROR = "error"


@dataclass
class AgentResponse:
    """Structured response from the agent."""
    response_type: ResponseType
    message: str
    requires_input: bool = False
    session_complete: bool = False
    data: Optional[Dict[str, Any]] = None