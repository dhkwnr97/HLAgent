"""
Type definitions for New Supervisor Agent.
"""

from enum import Enum
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass


class SupervisorState(Enum):
    """States for the supervisor agent."""
    IDLE = "idle"
    CHATTING = "chatting"
    HANDOFF = "handoff"
    WAITING_RESPONSE = "waiting_response"
    COMPLETED = "completed"
    ERROR = "error"


class ResponseType(Enum):
    """Response types for supervisor communication."""
    INFO = "info"
    REQUEST_INPUT = "request_input"
    HANDOFF = "handoff"
    SUCCESS = "success"
    ERROR = "error"
    COMPLETION = "completion"


@dataclass
class SupervisorResponse:
    """Response structure for supervisor agent."""
    response_type: ResponseType
    message: str
    requires_input: bool = False
    session_complete: bool = False
    data: Optional[Dict[str, Any]] = None
    target_agent: Optional[str] = None


@dataclass
class AgentInfo:
    """Information about registered agents."""
    name: str
    description: str
    agent_instance: Any
    handoff_tool: Optional[Callable] = None
    is_active: bool = True


@dataclass
class SupervisorWorkflowState:
    """State information for the supervisor workflow."""
    current_state: SupervisorState
    active_agent: Optional[str]
    conversation_history: List[Dict[str, Any]]
    registered_agents: Dict[str, AgentInfo]
    current_task: Optional[str]
    error_message: str
    session_id: str
    
    def __post_init__(self):
        if self.conversation_history is None:
            self.conversation_history = []
        if self.registered_agents is None:
            self.registered_agents = {}
    
    def add_message(self, role: str, content: str, agent_name: str = ""):
        """Add a message to conversation history."""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "agent": agent_name,
            "timestamp": None  # Could add datetime.now() if needed
        })
    
    def get_recent_messages(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get recent messages from conversation history."""
        return self.conversation_history[-count:] if self.conversation_history else []
    
    def set_error(self, error_msg: str):
        """Set error state."""
        self.error_message = error_msg
        self.current_state = SupervisorState.ERROR
    
    def register_agent(self, agent_info: AgentInfo):
        """Register an agent."""
        self.registered_agents[agent_info.name] = agent_info
    
    def get_agent_info(self, agent_name: str) -> Optional[AgentInfo]:
        """Get information about a registered agent."""
        return self.registered_agents.get(agent_name)
    
    def get_active_agents(self) -> List[str]:
        """Get list of active agent names."""
        return [name for name, info in self.registered_agents.items() if info.is_active]


@dataclass
class HandoffRequest:
    """Request structure for agent handoff."""
    target_agent: str
    task_description: str
    context: Dict[str, Any]
    requester_agent: str
    priority: str = "normal"
    
    def __post_init__(self):
        if self.context is None:
            self.context = {}


@dataclass
class HandoffResponse:
    """Response structure for agent handoff."""
    success: bool
    message: str
    result_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.result_data is None:
            self.result_data = {}


@dataclass
class SupervisorConfig:
    """Configuration for supervisor agent."""
    max_conversation_history: int = 100
    enable_logging: bool = True
    handoff_timeout: int = 300  # seconds
    auto_handoff: bool = True
    supported_agents: List[str] = None
    
    def __post_init__(self):
        if self.supported_agents is None:
            self.supported_agents = [
                "hlateacher",
                "genotypephasing", 
                "parameterhandler",
                "fileconverter",
                "hlaimputation",
                "hlafinemapping"
            ]