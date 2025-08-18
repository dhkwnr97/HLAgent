"""
HLA Imputation Agent.

A professional HLA imputation agent that supports multiple bioinformatics tools
through an intelligent workflow system with supervisor integration.
"""

import asyncio
from typing import Dict, Any, List, Optional, Callable
from src.core.llm_config import get_llm

from .agent_types import (
    HLAImputationState, HLAImputationRequest, AgentResponse, 
    ResponseType
)
from .workflows import HLAImputationWorkflow
from .prompts import HLA_IMPUTATION_PROMPTS
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class HLAImputationAgent:
    """
    HLA Imputation Agent.
    
    This agent provides a comprehensive HLA imputation service supporting:
    - Multiple HLA imputation tools (CookHLA, HLA-HD, OptiType)
    - Automatic tool discovery and configuration
    - Interactive user workflow
    - Supervisor agent integration
    - Workchain-based parameter handling
    - Output file tracking and return
    """
    
    def __init__(self, supervisor_handoff_callback: Optional[Callable] = None):
        self.llm = get_llm()
        
        self.supervisor_handoff_callback = supervisor_handoff_callback
        self.workflow = HLAImputationWorkflow(supervisor_handoff_callback)
        self.state_manager = self.workflow.state_manager

    
    async def run(self, requester_agent: str = "", task_id: str = "") -> List[str]:
        """
        Main entry point for HLA imputation workflow.
        
        Args:
            requester_agent: Name of requesting agent (empty for standalone)
            task_id: Task identifier
            
        Returns:
            List of output file paths generated
        """
        try:
            # Initialize session
            self.state_manager.initialize_session(requester_agent, task_id)
            
            logger.info(f"Starting HLA imputation workflow - Requester: {requester_agent}")
            
            # Start with IDLE workflow
            response = await self.workflow.execute_idle_workflow()
            print(response.message)
            
            if response.response_type == ResponseType.ERROR:
                return []
            
            # Interactive workflow loop
            while not self.workflow.is_session_complete():
                try:
                    # Get user input
                    user_input = await self._get_user_input()
                    
                    # Process based on current state
                    current_state = self.workflow.get_current_state()
                    
                    if current_state == HLAImputationState.TOOL_SELECTION:
                        response = await self.workflow.handle_tool_selection(user_input)
                    
                    elif current_state == HLAImputationState.READY_CHECK:
                        response = await self.workflow.handle_ready_response(user_input)
                    
                    else:
                        # Unexpected state
                        logger.warning(f"Unexpected state for user input: {current_state}")
                        response = AgentResponse(
                            response_type=ResponseType.ERROR,
                            message="❌ Workflow error - unexpected state",
                            requires_input=False,
                            session_complete=True
                        )
                    
                    # Display response
                    print(f"\n{response.message}")
                    
                    # Check if session is complete
                    if response.session_complete:
                        break
                        
                except KeyboardInterrupt:
                    print("\n\n🛑 Workflow interrupted by user.")
                    self.state_manager.transition(HLAImputationState.CANCELLED)
                    return []
                except Exception as e:
                    logger.error(f"Error in workflow loop: {e}")
                    print(f"\n❌ Error: {e}")
                    return []
            
            # Return output files
            output_files = self.workflow.get_output_files()
            
            # Show completion message
            if self.state_manager.is_standalone():
                print(HLA_IMPUTATION_PROMPTS["standalone_completion"])
            else:
                print(HLA_IMPUTATION_PROMPTS["return_to_supervisor"])
            
            return output_files
            
        except Exception as e:
            logger.error(f"Error in main workflow: {e}")
            print(f"\n❌ Workflow failed: {e}")
            return []
    
    async def _get_user_input(self) -> str:
        """Get user input (async wrapper for input())."""
        return await asyncio.get_event_loop().run_in_executor(
            None, lambda: input().strip()
        )
    
    async def chat_loop(self, requester_agent: str = "", task_id: str = "") -> Dict[str, Any]:
        """
        Interactive chat loop for both standalone and supervised operation.
        
        Args:
            requester_agent: Name of requesting agent
            task_id: Task identifier
            
        Returns:
            Dictionary with session results
        """
        try:
            if self.state_manager.is_standalone():
                print("\n=== HLA IMPUTATION AGENT ===")
                print("Advanced HLA imputation service")
                print("Type Ctrl+C to cancel at any time\n")
            else:
                print(f"\n=== HLA Imputation (via {requester_agent}) ===")
            
            # Run the main workflow
            output_files = await self.run(requester_agent, task_id)
            
            # Return session result
            return {
                "status": "completed" if output_files else "failed",
                "output_files": output_files,
                "file_count": len(output_files),
                "requester": requester_agent,
                "task_id": task_id,
                "selected_tool": (
                    self.state_manager.get_selected_tool_info().name 
                    if self.state_manager.get_selected_tool_info() else None
                )
            }
            
        except KeyboardInterrupt:
            print("\n\n🛑 Operation cancelled by user.")
            return {"status": "cancelled", "output_files": []}
        except Exception as e:
            logger.error(f"Chat loop error: {e}")
            print(f"\n❌ Error: {e}")
            return {"status": "error", "error": str(e), "output_files": []}
    
    async def handle_supervisor_request(self, request: HLAImputationRequest) -> Dict[str, Any]:
        """
        Handle a request from the supervisor agent.
        
        Args:
            request: HLAImputationRequest object
            
        Returns:
            Dictionary with execution results
        """
        try:
            logger.info(f"Handling supervisor request from {request.requester_agent}")
            
            # If specific tool requested, we could pre-select it here
            # For now, let user choose interactively
            
            result = await self.chat_loop(request.requester_agent, request.task_id)
            
            # Add request context to result
            result["request_context"] = request.context
            result["requested_tool"] = request.tool_name
            
            return result
            
        except Exception as e:
            logger.error(f"Error handling supervisor request: {e}")
            return {
                "status": "error",
                "error": str(e),
                "output_files": [],
                "requester": request.requester_agent
            }
    
    def get_session_info(self) -> Dict[str, Any]:
        """Get current session information for monitoring."""
        return self.workflow.get_state_info()
    
    def get_available_tools(self) -> List[str]:
        """Get list of available HLA imputation tools."""
        try:
            available_tools = self.workflow.tool_scanner.scan_available_tools()
            return [tool.name for tool in available_tools if tool.is_supported]
        except Exception as e:
            logger.error(f"Error getting available tools: {e}")
            return []
    
    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Dictionary with tool information or None if not found
        """
        try:
            tool_info = self.workflow.tool_scanner.get_tool_by_name(tool_name)
            if tool_info:
                return {
                    "name": tool_info.name,
                    "display_name": tool_info.display_name,
                    "description": tool_info.description,
                    "input_format": tool_info.input_format.value,
                    "input_description": tool_info.input_description,
                    "advantages": tool_info.advantages,
                    "is_supported": tool_info.is_supported
                }
            return None
        except Exception as e:
            logger.error(f"Error getting tool info: {e}")
            return None


# Convenience function for creating the agent
def create_hla_imputation_agent(supervisor_handoff_callback: Optional[Callable] = None) -> HLAImputationAgent:
    """
    Create a HLA Imputation Agent instance.
    
    Args:
        supervisor_handoff_callback: Callback for supervisor handoff
        
    Returns:
        HLAImputationAgent instance
    """
    return HLAImputationAgent(supervisor_handoff_callback=supervisor_handoff_callback)