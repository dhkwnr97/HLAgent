"""
State management for HLA Teacher Agent.
"""

from typing import Optional, Dict, Any, List
from .agent_types import AgentMode


class HLATeacherState:
    """State information for HLA Teacher Agent."""
    
    def __init__(self):
        self.mode = AgentMode.WEB_ONLY
        self.requester_agent = ""
        self.task_id = ""
        self.is_standalone = True
        self.session_active = False
        self.conversation_history = []
        self.current_query = ""
        self.error_message = ""
    
    def initialize_session(self, requester: str = "", task_id: str = "", mode: AgentMode = AgentMode.WEB_ONLY):
        """Initialize a new session."""
        self.requester_agent = requester
        self.task_id = task_id
        self.mode = mode
        self.is_standalone = not bool(requester)
        self.session_active = True
        self.conversation_history = []
        self.current_query = ""
        self.error_message = ""
    
    def add_conversation(self, role: str, content: str):
        """Add a conversation entry."""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "mode": self.mode.value
        })
    
    def set_current_query(self, query: str):
        """Set the current query."""
        self.current_query = query
    
    def set_error(self, error: str):
        """Set error message."""
        self.error_message = error
    
    def end_session(self):
        """End the current session."""
        self.session_active = False
        self.current_query = ""
    
    def get_state_info(self) -> Dict[str, Any]:
        """Get state information as dictionary."""
        return {
            "mode": self.mode.value,
            "requester_agent": self.requester_agent,
            "task_id": self.task_id,
            "is_standalone": self.is_standalone,
            "session_active": self.session_active,
            "conversation_count": len(self.conversation_history),
            "current_query": self.current_query,
            "has_error": bool(self.error_message),
            "error_message": self.error_message
        }


class HLATeacherStateManager:
    """State manager for HLA Teacher Agent."""
    
    def __init__(self):
        self.state = HLATeacherState()
    
    def initialize_session(self, requester: str = "", task_id: str = "", mode: AgentMode = AgentMode.WEB_ONLY):
        """Initialize a new session."""
        self.state.initialize_session(requester, task_id, mode)
    
    def add_conversation(self, role: str, content: str):
        """Add a conversation entry."""
        self.state.add_conversation(role, content)
    
    def set_current_query(self, query: str):
        """Set the current query."""
        self.state.set_current_query(query)
    
    def set_error(self, error: str):
        """Set error message."""
        self.state.set_error(error)
    
    def end_session(self):
        """End the current session."""
        self.state.end_session()
    
    def get_state_info(self) -> Dict[str, Any]:
        """Get state information."""
        return self.state.get_state_info()
    
    def is_session_active(self) -> bool:
        """Check if session is active."""
        return self.state.session_active
    
    def get_mode(self) -> AgentMode:
        """Get current mode."""
        return self.state.mode
    
    def set_mode(self, mode: AgentMode):
        """Set mode."""
        self.state.mode = mode
    
    def is_standalone(self) -> bool:
        """Check if running in standalone mode."""
        return self.state.is_standalone
    
    def get_requester(self) -> str:
        """Get requester agent."""
        return self.state.requester_agent