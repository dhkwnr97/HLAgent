"""
New Supervisor Agent Package
===========================

A professional supervisor agent for orchestrating multi-agent workflows.
Uses langgraph_supervisor for advanced handoff management.
"""

from .agent import SupervisorAgent
from .agent_types import SupervisorState, SupervisorResponse, AgentInfo
from .states import SupervisorStateManager
from .tools import SupervisorTools
from .prompts import SUPERVISOR_PROMPTS

__all__ = [
    'SupervisorAgent',
    'SupervisorState',
    'SupervisorResponse',
    'AgentInfo',
    'SupervisorStateManager',
    'SupervisorTools',
    'SUPERVISOR_PROMPTS'
]