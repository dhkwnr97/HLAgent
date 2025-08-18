"""
State management for File Converter Agent.

Handles state transitions and session management.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

from .agent_types import ConverterState, ConverterResponse, ResponseType


class SessionState:
    """Session state for file converter agent."""
    
    def __init__(self):
        self.session_id: str = str(uuid.uuid4())
        self.current_state: ConverterState = ConverterState.IDLE
        self.requester_agent: str = ""
        self.task_id: str = ""
        self.is_standalone: bool = True
        self.created_at: datetime = datetime.now()
        self.conversation_history: List[Dict[str, str]] = []
        self.output_files: List[str] = []
        self.current_mode: Optional[str] = None
        self.error_message: Optional[str] = None
        self.task_complete: bool = False
        
    def set_requester(self, requester: str, task_id: str = ""):
        """Set the requesting agent information."""
        self.requester_agent = requester
        self.task_id = task_id
        self.is_standalone = (requester == "")
        
    def add_message(self, role: str, content: str):
        """Add a message to conversation history."""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        
    def add_output_file(self, file_path: str):
        """Add an output file to the list."""
        if file_path not in self.output_files:
            self.output_files.append(file_path)
            
    def clear_output_files(self):
        """Clear the output files list."""
        self.output_files.clear()
        
    def set_error(self, error_message: str):
        """Set error state."""
        self.error_message = error_message
        self.current_state = ConverterState.ERROR
        
    def get_session_info(self) -> Dict[str, Any]:
        """Get session information."""
        return {
            "session_id": self.session_id,
            "current_state": self.current_state.value,
            "requester_agent": self.requester_agent,
            "task_id": self.task_id,
            "is_standalone": self.is_standalone,
            "created_at": self.created_at.isoformat(),
            "conversation_length": len(self.conversation_history),
            "output_files_count": len(self.output_files),
            "current_mode": self.current_mode,
            "task_complete": self.task_complete
        }


class StateManager:
    """Manages state transitions for file converter agent."""
    
    def __init__(self):
        self.state = SessionState()
        
    def initialize_session(self, requester: str = "", task_id: str = "") -> ConverterResponse:
        """Initialize a new session."""
        try:
            self.state = SessionState()
            self.state.set_requester(requester, task_id)
            self.state.current_state = ConverterState.IDLE
            
            return ConverterResponse(
                response_type=ResponseType.SUCCESS,
                message="Session initialized successfully",
                requires_input=False
            )
        except Exception as e:
            return ConverterResponse(
                response_type=ResponseType.ERROR,
                message=f"Failed to initialize session: {str(e)}",
                requires_input=False
            )
    
    def transition(self, new_state: ConverterState):
        """Transition to a new state."""
        old_state = self.state.current_state
        self.state.current_state = new_state
        
        # Log state transition
        self.state.add_message("system", f"State transition: {old_state.value} → {new_state.value}")
        
    def is_session_complete(self) -> bool:
        """Check if session is complete."""
        return (self.state.current_state == ConverterState.COMPLETED or 
                self.state.task_complete)
    
    def get_current_state(self) -> SessionState:
        """Get current session state."""
        return self.state
        
    def get_state_info(self) -> Dict[str, Any]:
        """Get current state information."""
        return self.state.get_session_info()