"""
State management for HLA Imputation Agent.

Handles the workflow state transitions and data management throughout the HLA imputation process.
"""

from typing import Dict, Any, List, Optional
from .agent_types import (
    HLAImputationState, HLAImputationTool, HLAToolInfo, WorkflowState
)
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class StateManager:
    """
    Manages the state of the HLA imputation agent workflow.
    
    This class handles:
    - State transitions
    - Tool selection and configuration
    - Output file tracking
    - Session management
    """
    
    def __init__(self):
        self.state = WorkflowState(
            current_state=HLAImputationState.IDLE,
            selected_tool=None,
            tool_info=None,
            output_files=[],
            requester_agent="",
            task_id="",
            is_standalone=True
        )
    
    def initialize_session(self, requester_agent: str = "", task_id: str = ""):
        """
        Initialize a new session.
        
        Args:
            requester_agent: Name of the requesting agent (empty for standalone)
            task_id: Unique task identifier
        """
        self.state.requester_agent = requester_agent
        self.state.task_id = task_id
        self.state.is_standalone = not bool(requester_agent)
        self.state.current_state = HLAImputationState.IDLE
        self.state.output_files = []
        self.state.selected_tool = None
        self.state.tool_info = None
        self.state.error_message = None
        
        logger.info(f"Session initialized - Requester: {requester_agent}, Task ID: {task_id}")
    
    def transition(self, new_state: HLAImputationState):
        """
        Transition to a new state.
        
        Args:
            new_state: The new state to transition to
        """
        old_state = self.state.current_state
        self.state.current_state = new_state
        logger.info(f"State transition: {old_state.value} -> {new_state.value}")
    
    def set_selected_tool(self, tool: HLAImputationTool, tool_info: HLAToolInfo):
        """
        Set the selected HLA imputation tool.
        
        Args:
            tool: The selected tool enum
            tool_info: Information about the selected tool
        """
        self.state.selected_tool = tool
        self.state.tool_info = tool_info
        logger.info(f"Tool selected: {tool.value}")
    
    def add_output_file(self, file_path: str):
        """
        Add an output file to the tracked list.
        
        Args:
            file_path: Path to the output file
        """
        self.state.output_files.append(file_path)
        logger.info(f"Output file added: {file_path}")
    
    def clear_output_files(self):
        """Clear the output files list."""
        self.state.output_files = []
        logger.info("Output files cleared")
    
    def set_error(self, error_message: str):
        """
        Set error state with message.
        
        Args:
            error_message: Error message to store
        """
        self.state.error_message = error_message
        self.state.current_state = HLAImputationState.ERROR
        logger.error(f"Error state set: {error_message}")
    
    def is_session_complete(self) -> bool:
        """
        Check if the session is complete.
        
        Returns:
            True if session is complete or in error/cancelled state
        """
        return self.state.current_state in [
            HLAImputationState.COMPLETED,
            HLAImputationState.ERROR,
            HLAImputationState.CANCELLED
        ]
    
    def is_standalone(self) -> bool:
        """
        Check if running in standalone mode.
        
        Returns:
            True if running standalone (not called by supervisor)
        """
        return self.state.is_standalone
    
    def get_requester(self) -> str:
        """
        Get the requester agent name.
        
        Returns:
            Name of the requesting agent
        """
        return self.state.requester_agent
    
    def get_current_state(self) -> WorkflowState:
        """
        Get the current workflow state.
        
        Returns:
            Current WorkflowState object
        """
        return self.state
    
    def get_state_info(self) -> Dict[str, Any]:
        """
        Get detailed state information for debugging/monitoring.
        
        Returns:
            Dictionary containing current state information
        """
        return {
            "current_state": self.state.current_state.value,
            "selected_tool": self.state.selected_tool.value if self.state.selected_tool else None,
            "tool_name": self.state.tool_info.name if self.state.tool_info else None,
            "output_files_count": len(self.state.output_files),
            "output_files": self.state.output_files,
            "requester_agent": self.state.requester_agent,
            "task_id": self.state.task_id,
            "is_standalone": self.state.is_standalone,
            "has_error": bool(self.state.error_message),
            "error_message": self.state.error_message,
            "session_complete": self.is_session_complete()
        }
    
    def get_output_files(self) -> List[str]:
        """
        Get the list of output files.
        
        Returns:
            List of output file paths
        """
        return self.state.output_files.copy()
    
    def get_selected_tool_info(self) -> Optional[HLAToolInfo]:
        """
        Get information about the selected tool.
        
        Returns:
            HLAToolInfo object or None if no tool selected
        """
        return self.state.tool_info