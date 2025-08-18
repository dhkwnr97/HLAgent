"""
State management for Supervisor Agent.
"""

import uuid
from typing import Optional, Dict, Any, List
from .agent_types import SupervisorState, SupervisorWorkflowState, AgentInfo


class SupervisorStateManager:
    """State manager for supervisor agent workflow."""
    
    def __init__(self):
        self.state = SupervisorWorkflowState(
            current_state=SupervisorState.IDLE,
            active_agent=None,
            conversation_history=[],
            registered_agents={},
            current_task=None,
            error_message="",
            session_id=str(uuid.uuid4())
        )
    
    def initialize_session(self, session_id: str = None) -> bool:
        """Initialize a supervisor session."""
        try:
            self.state.session_id = session_id or str(uuid.uuid4())
            self.state.current_state = SupervisorState.IDLE
            self.state.active_agent = None
            self.state.conversation_history = []
            self.state.current_task = None
            self.state.error_message = ""
            return True
        except Exception as e:
            self.state.set_error(f"Failed to initialize session: {str(e)}")
            return False
    
    def transition(self, new_state: SupervisorState) -> bool:
        """Transition to a new state."""
        try:
            self.state.current_state = new_state
            return True
        except Exception as e:
            self.state.set_error(f"State transition failed: {str(e)}")
            return False
    
    def register_agent(self, agent_info: AgentInfo) -> bool:
        """Register an agent with the supervisor."""
        try:
            self.state.register_agent(agent_info)
            return True
        except Exception as e:
            self.state.set_error(f"Agent registration failed: {str(e)}")
            return False
    
    def set_active_agent(self, agent_name: str) -> bool:
        """Set the currently active agent."""
        try:
            if agent_name in self.state.registered_agents:
                self.state.active_agent = agent_name
                return True
            else:
                self.state.set_error(f"Agent '{agent_name}' not registered")
                return False
        except Exception as e:
            self.state.set_error(f"Failed to set active agent: {str(e)}")
            return False
    
    def add_message(self, role: str, content: str, agent_name: str = "") -> bool:
        """Add a message to conversation history."""
        try:
            self.state.add_message(role, content, agent_name)
            return True
        except Exception as e:
            self.state.set_error(f"Failed to add message: {str(e)}")
            return False
    
    def set_current_task(self, task: str):
        """Set the current task description."""
        self.state.current_task = task
    
    def clear_current_task(self):
        """Clear the current task."""
        self.state.current_task = None
    
    def set_error(self, error_msg: str):
        """Set error state."""
        self.state.set_error(error_msg)
    
    def is_session_complete(self) -> bool:
        """Check if the session is complete."""
        return self.state.current_state in [SupervisorState.COMPLETED, SupervisorState.ERROR]
    
    def get_current_state(self) -> SupervisorWorkflowState:
        """Get current state."""
        return self.state
    
    def get_state_info(self) -> Dict[str, Any]:
        """Get state information as dictionary."""
        return {
            "session_id": self.state.session_id,
            "current_state": self.state.current_state.value,
            "active_agent": self.state.active_agent,
            "registered_agents": list(self.state.registered_agents.keys()),
            "conversation_length": len(self.state.conversation_history),
            "current_task": self.state.current_task,
            "has_error": bool(self.state.error_message),
            "error_message": self.state.error_message
        }
    
    def get_agent_names(self) -> List[str]:
        """Get list of registered agent names."""
        return list(self.state.registered_agents.keys())
    
    def get_active_agents(self) -> List[str]:
        """Get list of active agent names."""
        return self.state.get_active_agents()
    
    def get_conversation_history(self, recent_count: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversation history."""
        return self.state.get_recent_messages(recent_count)
    
    def clear_conversation_history(self):
        """Clear conversation history."""
        self.state.conversation_history = []
    
    def get_agent_info(self, agent_name: str) -> Optional[AgentInfo]:
        """Get information about a specific agent."""
        return self.state.get_agent_info(agent_name)