"""
State management for Genotype Phasing Agent.
"""

from typing import Optional
from .agent_types import PhasingState, PhasingWorkflowState, InputFormat


class PhasingStateManager:
    """State manager for genotype phasing workflow."""
    
    def __init__(self):
        self.state = PhasingWorkflowState(
            current_state=PhasingState.IDLE,
            input_format=InputFormat.UNKNOWN,
            output_files=[],
            error_message="",
            requester_agent="",
            task_id="",
            is_standalone=True
        )
    
    def initialize_session(self, requester: str = "", task_id: str = "") -> bool:
        """Initialize a new phasing session."""
        try:
            self.state.requester_agent = requester
            self.state.task_id = task_id
            self.state.is_standalone = not bool(requester)
            self.state.current_state = PhasingState.IDLE
            self.state.error_message = ""
            self.state.output_files = []
            self.state.input_format = InputFormat.UNKNOWN
            return True
        except Exception as e:
            self.state.set_error(f"Failed to initialize session: {str(e)}")
            return False
    
    def transition(self, new_state: PhasingState) -> bool:
        """Transition to a new state."""
        try:
            self.state.current_state = new_state
            return True
        except Exception as e:
            self.state.set_error(f"State transition failed: {str(e)}")
            return False
    
    def set_input_format(self, format_type: InputFormat):
        """Set the detected input format."""
        self.state.input_format = format_type
    
    def add_output_file(self, file_path: str):
        """Add an output file to the state."""
        self.state.add_output_file(file_path)
    
    def clear_output_files(self):
        """Clear output files."""
        self.state.clear_output_files()
    
    def set_error(self, error_msg: str):
        """Set error state."""
        self.state.set_error(error_msg)
    
    def is_session_complete(self) -> bool:
        """Check if the session is complete."""
        return self.state.current_state in [PhasingState.COMPLETED, PhasingState.ERROR]
    
    def get_current_state(self) -> PhasingWorkflowState:
        """Get current state."""
        return self.state
    
    def get_state_info(self) -> dict:
        """Get state information as dictionary."""
        return {
            "current_state": self.state.current_state.value,
            "input_format": self.state.input_format.value,
            "output_files": self.state.output_files,
            "has_error": bool(self.state.error_message),
            "error_message": self.state.error_message,
            "requester": self.state.requester_agent,
            "task_id": self.state.task_id,
            "is_standalone": self.state.is_standalone
        }