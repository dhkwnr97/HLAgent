"""
Tools for Supervisor Agent.
"""

import asyncio
from typing import Dict, Any, List, Optional, Callable
from langchain_core.tools import tool, BaseTool, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from langgraph.prebuilt import InjectedState
from typing_extensions import Annotated

from .agent_types import HandoffRequest, HandoffResponse, AgentInfo
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class SupervisorTools:
    """Tools for supervisor agent operations."""
    
    def __init__(self):
        self.registered_agents: Dict[str, AgentInfo] = {}
    
    def register_agent(self, agent_info: AgentInfo) -> bool:
        """Register an agent with the supervisor."""
        try:
            self.registered_agents[agent_info.name] = agent_info
            logger.info(f"Agent '{agent_info.name}' registered successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to register agent '{agent_info.name}': {e}")
            return False
    
    def get_agent_info(self, agent_name: str) -> Optional[AgentInfo]:
        """Get information about a registered agent."""
        return self.registered_agents.get(agent_name)
    
    def get_available_agents(self) -> List[str]:
        """Get list of available agent names."""
        return list(self.registered_agents.keys())
    
    def is_agent_available(self, agent_name: str) -> bool:
        """Check if an agent is available."""
        agent_info = self.registered_agents.get(agent_name)
        return agent_info is not None and agent_info.is_active
    
    async def handoff_to_agent(self, request: HandoffRequest) -> HandoffResponse:
        """
        Handoff a task to a specific agent.
        
        Args:
            request: HandoffRequest with task details
            
        Returns:
            HandoffResponse with results
        """
        try:
            agent_info = self.get_agent_info(request.target_agent)
            if not agent_info:
                return HandoffResponse(
                    success=False,
                    message=f"Agent '{request.target_agent}' not found",
                    error=f"Agent '{request.target_agent}' is not registered"
                )
            
            if not agent_info.is_active:
                return HandoffResponse(
                    success=False,
                    message=f"Agent '{request.target_agent}' is not active",
                    error=f"Agent '{request.target_agent}' is currently inactive"
                )
            
            # Execute handoff
            if agent_info.handoff_tool:
                result = await agent_info.handoff_tool(request)
                return HandoffResponse(
                    success=True,
                    message=f"Successfully handed off to {request.target_agent}",
                    result_data=result
                )
            else:
                # Direct agent execution
                if hasattr(agent_info.agent_instance, 'chat_loop'):
                    result = await agent_info.agent_instance.chat_loop(
                        requester_agent=request.requester_agent,
                        task_id=request.context.get('task_id', '')
                    )
                    return HandoffResponse(
                        success=True,
                        message=f"Successfully executed {request.target_agent}",
                        result_data={"output": result}
                    )
                else:
                    return HandoffResponse(
                        success=False,
                        message=f"Agent '{request.target_agent}' has no execution method",
                        error="Agent does not support chat_loop or handoff_tool"
                    )
                    
        except Exception as e:
            logger.error(f"Handoff to {request.target_agent} failed: {e}")
            return HandoffResponse(
                success=False,
                message=f"Handoff to {request.target_agent} failed",
                error=str(e)
            )
    
    def create_handoff_tool(self, agent_name: str, description: str) -> BaseTool:
        """
        Create a custom handoff tool for an agent.
        
        Args:
            agent_name: Name of the target agent
            description: Description of what the agent does
            
        Returns:
            BaseTool for handoff
        """
        @tool(f"handoff_to_{agent_name}", description=description)
        def handoff_tool(
            task_description: Annotated[str, "Detailed description of what the next agent should do, including all relevant context."],
            state: Annotated[dict, InjectedState],
            tool_call_id: Annotated[str, InjectedToolCallId],
        ):
            tool_message = ToolMessage(
                content=f"Successfully transferred to {agent_name}",
                name=f"handoff_to_{agent_name}",
                tool_call_id=tool_call_id,
            )
            messages = state["messages"]
            return Command(
                goto=agent_name,
                graph=Command.PARENT,
                update={
                    "messages": messages + [tool_message],
                    "active_agent": agent_name,
                    "task_description": task_description,
                },
            )
        
        return handoff_tool
    
    def get_agents_summary(self) -> str:
        """Get a formatted summary of all registered agents."""
        if not self.registered_agents:
            return "No agents registered."
        
        summary = []
        for name, info in self.registered_agents.items():
            status = "🟢 Active" if info.is_active else "🔴 Inactive"
            summary.append(f"• {name}: {status}")
            summary.append(f"  {info.description}")
        
        return "\n".join(summary)


# Langchain tools for supervisor workflows
@tool
def list_available_agents(supervisor_tools: SupervisorTools) -> List[str]:
    """
    List all available agents.
    
    Args:
        supervisor_tools: SupervisorTools instance
        
    Returns:
        List of agent names
    """
    return supervisor_tools.get_available_agents()


@tool
def check_agent_availability(supervisor_tools: SupervisorTools, agent_name: str) -> bool:
    """
    Check if an agent is available.
    
    Args:
        supervisor_tools: SupervisorTools instance
        agent_name: Name of the agent to check
        
    Returns:
        True if agent is available, False otherwise
    """
    return supervisor_tools.is_agent_available(agent_name)


@tool
def get_agent_description(supervisor_tools: SupervisorTools, agent_name: str) -> str:
    """
    Get description of an agent.
    
    Args:
        supervisor_tools: SupervisorTools instance
        agent_name: Name of the agent
        
    Returns:
        Agent description or error message
    """
    agent_info = supervisor_tools.get_agent_info(agent_name)
    if agent_info:
        return agent_info.description
    else:
        return f"Agent '{agent_name}' not found"


@tool
async def execute_handoff(supervisor_tools: SupervisorTools, 
                         request: HandoffRequest) -> Dict[str, Any]:
    """
    Execute a handoff to another agent.
    
    Args:
        supervisor_tools: SupervisorTools instance
        request: HandoffRequest with task details
        
    Returns:
        Dictionary with handoff results
    """
    response = await supervisor_tools.handoff_to_agent(request)
    return {
        "success": response.success,
        "message": response.message,
        "result_data": response.result_data,
        "error": response.error
    }