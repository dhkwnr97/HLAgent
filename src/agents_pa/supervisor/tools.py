"""
PydanticAI tools for Supervisor Agent.
Implements agent delegation patterns following examples/agent_delegation_*.py
"""

import asyncio
from typing import Optional
from pydantic_ai import RunContext

from .dependencies import SupervisorDependencies
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def create_supervisor_tools(agent):
    """
    Create and register tools for Supervisor agent.
    Returns the agent with delegation tools registered.
    """
    
    # Global state store for A2A context persistence
    # This maintains delegation state across A2A calls using context_id
    _a2a_state_store = {}
    
    @agent.tool
    async def check_handover_status(
        ctx: RunContext[SupervisorDependencies]
    ) -> str:
        """
        Check current handover status and active specialist agents.
        
        Returns:
            Status information about current handovers
        """
        try:
            # Handle case where deps is None (A2A context)
            if ctx.deps is None:
                from ..supervisor.dependencies import SupervisorDependencies
                context_id = getattr(ctx, 'context_id', None) or 'a2a_default'
                ctx.deps = SupervisorDependencies.create_default(
                    external_context_id=context_id
                )
            
            if ctx.deps.delegation_active:
                return f"Currently in handover mode with {ctx.deps.active_sub_agent} for: {ctx.deps.delegation_reason}"
            else:
                return f"No active handovers. Available specialist agents: {', '.join(ctx.deps.available_agents)}"
                
        except Exception as e:
            logger.error(f"Error checking handover status: {e}")
            return f"Error checking handover status: {str(e)}"
    
    @agent.tool
    async def get_available_agents(
        ctx: RunContext[SupervisorDependencies]
    ) -> str:
        """
        Get list of available sub-agents for delegation.
        
        Returns:
            Information about available agents and their capabilities
        """
        try:
            # Handle case where deps is None (A2A context)
            if ctx.deps is None:
                from ..supervisor.dependencies import SupervisorDependencies
                context_id = getattr(ctx, 'context_id', None) or 'a2a_default'
                ctx.deps = SupervisorDependencies.create_default(
                    external_context_id=context_id
                )
                
            agents_info = {
                "hlateacher": {
                    "description": "Specialized agent for HLA, genetics, and biology questions",
                    "capabilities": ["Web search", "Knowledge base (RAG)", "MCP server tools"],
                    "modes": ["web_only", "rag_enhanced", "mcp_enhanced"]
                }
            }
            
            result = "Available agents for delegation:\n\n"
            for agent_name, info in agents_info.items():
                result += f"**{agent_name.upper()}**\n"
                result += f"- Description: {info['description']}\n"
                result += f"- Capabilities: {', '.join(info['capabilities'])}\n"
                result += f"- Modes: {', '.join(info['modes'])}\n\n"
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting available agents: {e}")
            return f"Error retrieving agent information: {str(e)}"
    
    @agent.tool
    async def analyze_query_for_handover(
        ctx: RunContext[SupervisorDependencies],
        query: str
    ) -> str:
        """
        Analyze a query to determine if it should trigger handover to a specialist agent.
        
        Args:
            query: User query to analyze
            
        Returns:
            Analysis result with handover recommendation
        """
        try:
            should_handover, reason = ctx.deps.should_delegate_to_hlateacher(query)
            
            if should_handover:
                return f"HANDOVER RECOMMENDED: {reason}\nSuggested specialist: hlateacher\nQuery: {query}"
            else:
                return f"NO HANDOVER NEEDED: {reason}\nI can handle this query directly."
                
        except Exception as e:
            logger.error(f"Error analyzing query for handover: {e}")
            return f"Error analyzing query: {str(e)}"
    
    @agent.tool
    async def get_session_info(
        ctx: RunContext[SupervisorDependencies]
    ) -> str:
        """
        Get comprehensive session information for debugging and monitoring.
        
        Returns:
            JSON string with current session state
        """
        try:
            import json
            session_info = ctx.deps.get_session_info()
            return json.dumps(session_info, indent=2)
        except Exception as e:
            logger.error(f"Error getting session info: {e}")
            return f"Error retrieving session info: {str(e)}"
    
    @agent.tool
    async def delegate_to_hlateacher(
        ctx: RunContext[SupervisorDependencies],
        query: str
    ) -> str:
        """
        Delegate query to HLA Teacher agent for specialist handling.
        Use this for any questions about HLA, genetics, biology, immunology.
        Also use this when users request to see or talk to the HLA Teacher agent.
        
        Args:
            query: The user's question about HLA/genetics/biology or handover request
            
        Returns:
            Response from HLA Teacher agent
        """
        try:
            from .Handover.ho_hlateacher import HLATeacherHandover
            from ..supervisor.dependencies import SupervisorDependencies
            
            logger.info(f"Delegating query to HLA Teacher: {query}")
            
            # Handle case where deps is None (A2A context)
            if ctx.deps is None:
                # Create default dependencies for A2A context
                # Try to get context ID from A2A message context if available
                context_id = getattr(ctx, 'context_id', None) or 'a2a_default'
                ctx.deps = SupervisorDependencies.create_default(
                    external_context_id=context_id
                )
            
            # Get A2A context ID if available (for state persistence)
            context_key = getattr(ctx.deps, 'external_context_id', None) or ctx.deps.session_id or 'default'
            
            # Restore delegation state from A2A context store
            if context_key in _a2a_state_store:
                stored_state = _a2a_state_store[context_key]
                ctx.deps.delegation_active = stored_state.get('delegation_active', False)
                ctx.deps.active_sub_agent = stored_state.get('active_sub_agent', None)
                ctx.deps.hlateacher_deps = stored_state.get('hlateacher_deps', None)
            
            # Check if this is a handover request vs direct question
            handover_keywords = ["want to see", "talk to", "connect to", "switch to", "handover to"]
            is_handover_request = any(keyword in query.lower() for keyword in handover_keywords)
            
            if is_handover_request or not ctx.deps.delegation_active:
                # This is a request to handover to HLA Teacher
                response = await HLATeacherHandover.process_with_hlateacher(query, ctx.deps)
                result = f"Supervisor agent handover to HLA teacher agent.\n\n{response}"
            else:
                # This is a direct question to be processed by HLA Teacher (follow-up)
                response = await HLATeacherHandover.process_hlateacher_followup(query, ctx.deps)
                result = response
                
            # Store delegation state in A2A context store
            _a2a_state_store[context_key] = {
                'delegation_active': ctx.deps.delegation_active,
                'active_sub_agent': ctx.deps.active_sub_agent,
                'hlateacher_deps': ctx.deps.hlateacher_deps
            }
            
            return result
                
        except Exception as e:
            logger.error(f"Error delegating to HLA Teacher: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return f"I encountered an error while connecting you with the HLA Teacher: {str(e)}. Please try asking your question directly."
    
    @agent.tool
    async def handle_agent_return(
        ctx: RunContext[SupervisorDependencies],
        query: str
    ) -> str:
        """
        Handle return from sub-agent when user says 'Done!' or similar.
        
        Args:
            query: The return signal (usually 'Done!')
            
        Returns:
            Supervisor welcome back message
        """
        try:
            # Handle case where deps is None (A2A context)
            if ctx.deps is None:
                from ..supervisor.dependencies import SupervisorDependencies
                context_id = getattr(ctx, 'context_id', None) or 'a2a_default'
                ctx.deps = SupervisorDependencies.create_default(
                    external_context_id=context_id
                )
            
            # Get A2A context ID if available (for state persistence)
            context_key = getattr(ctx.deps, 'external_context_id', None) or ctx.deps.session_id or 'default'
            
            # Restore delegation state from A2A context store
            if context_key in _a2a_state_store:
                stored_state = _a2a_state_store[context_key]
                ctx.deps.delegation_active = stored_state.get('delegation_active', False)
                ctx.deps.active_sub_agent = stored_state.get('active_sub_agent', None)
            
            if ctx.deps.delegation_active:
                active_agent = ctx.deps.active_sub_agent
                ctx.deps.end_delegation()
                
                # Clear delegation state from A2A context store
                _a2a_state_store[context_key] = {
                    'delegation_active': False,
                    'active_sub_agent': None,
                    'hlateacher_deps': None
                }
                
                return f"Welcome back from {active_agent}! What can I help you with now?"
            else:
                return "I'm here to help! What would you like to know?"
                
        except Exception as e:
            logger.error(f"Error handling agent return: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return f"Error processing return: {str(e)}"
    
    return agent