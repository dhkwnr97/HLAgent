"""
State management for Parameter Handler Agent.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from .agent_types import AgentState, YamlModificationRequest, AgentResponse, ResponseType


@dataclass
class SessionState:
    """Complete state for an agent session."""
    
    # Core state
    current_state: AgentState = AgentState.IDLE
    task_complete: bool = False
    awaiting_confirmation: bool = False
    
    # File handling
    original_yaml_path: str = ""
    working_yaml_path: str = ""
    yaml_content: List[str] = field(default_factory=list)
    
    # Request context
    modification_request: Optional[YamlModificationRequest] = None
    requester_agent: str = ""
    task_id: str = ""
    
    # Session management
    is_standalone: bool = True
    session_messages: List[str] = field(default_factory=list)
    
    # Error handling
    last_error: Optional[str] = None
    
    def reset(self):
        """Reset the session state."""
        self.current_state = AgentState.IDLE
        self.task_complete = False
        self.awaiting_confirmation = False
        self.original_yaml_path = ""
        self.working_yaml_path = ""
        self.yaml_content = []
        self.modification_request = None
        self.requester_agent = ""
        self.task_id = ""
        self.session_messages = []
        self.last_error = None
    
    def add_message(self, message: str):
        """Add a message to the session history."""
        self.session_messages.append(message)
    
    def set_error(self, error: str):
        """Set an error and transition to error state."""
        self.last_error = error
        self.current_state = AgentState.ERROR
        
    def transition_to(self, new_state: AgentState):
        """Transition to a new state."""
        self.current_state = new_state
        
    def is_ready_for_editing(self) -> bool:
        """Check if the session is ready for interactive editing."""
        return (
            self.working_yaml_path and 
            self.yaml_content and
            self.current_state in [AgentState.INTERACTIVE_EDIT, AgentState.SHOW_CONTENT]
        )
    
    def get_file_info(self) -> Dict[str, Any]:
        """Get information about the current files."""
        return {
            "original_path": self.original_yaml_path,
            "working_path": self.working_yaml_path,
            "line_count": len(self.yaml_content),
            "has_content": bool(self.yaml_content)
        }


class StateManager:
    """Manages state transitions and validations."""
    
    def __init__(self):
        self.state = SessionState()
    
    def initialize_session(self, yaml_path: str, requester: str = "", task_id: str = "") -> AgentResponse:
        """Initialize a new session."""
        try:
            self.state.reset()
            self.state.original_yaml_path = yaml_path
            self.state.requester_agent = requester
            self.state.task_id = task_id
            self.state.is_standalone = not bool(requester)
            
            # Create modification request if from another agent
            if requester:
                self.state.modification_request = YamlModificationRequest(
                    original_yaml_path=yaml_path,
                    working_yaml_path="",  # Will be set during copy
                    requester_agent=requester,
                    task_id=task_id
                )
            
            self.state.transition_to(AgentState.COPY_FILE)
            
            return AgentResponse(
                response_type=ResponseType.INFO,
                message=f"Session initialized for {yaml_path}",
                requires_input=False
            )
            
        except Exception as e:
            self.state.set_error(str(e))
            return AgentResponse(
                response_type=ResponseType.ERROR,
                message=f"Failed to initialize session: {str(e)}",
                requires_input=False
            )
    
    def can_transition(self, from_state: AgentState, to_state: AgentState) -> bool:
        """Check if a state transition is valid."""
        valid_transitions = {
            AgentState.IDLE: [AgentState.COPY_FILE, AgentState.ERROR],
            AgentState.COPY_FILE: [AgentState.SHOW_CONTENT, AgentState.ERROR],
            AgentState.SHOW_CONTENT: [AgentState.INTERACTIVE_EDIT, AgentState.ERROR],
            AgentState.INTERACTIVE_EDIT: [
                AgentState.INTERACTIVE_EDIT,  # Loop for more edits
                AgentState.CONFIRMATION,
                AgentState.SHOW_CONTENT,
                AgentState.ERROR
            ],
            AgentState.CONFIRMATION: [
                AgentState.COMPLETED,
                AgentState.INTERACTIVE_EDIT,  # If user says "No"
                AgentState.ERROR
            ],
            AgentState.COMPLETED: [AgentState.IDLE],  # For new sessions
            AgentState.ERROR: [AgentState.IDLE, AgentState.COPY_FILE]  # Recovery
        }
        
        return to_state in valid_transitions.get(from_state, [])
    
    def transition(self, new_state: AgentState) -> bool:
        """Perform a state transition with validation."""
        if self.can_transition(self.state.current_state, new_state):
            self.state.transition_to(new_state)
            return True
        return False
    
    def get_current_state(self) -> SessionState:
        """Get the current session state."""
        return self.state
    
    def is_session_complete(self) -> bool:
        """Check if the session is complete."""
        return self.state.task_complete or self.state.current_state == AgentState.COMPLETED