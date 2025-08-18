"""
Supervisor Agent.

A professional supervisor agent for orchestrating multi-agent workflows.
Uses langgraph_supervisor for advanced handoff management.
"""

import asyncio
from typing import Dict, Any, List, Optional, Callable
from src.core.llm_config import get_llm
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor

from .agent_types import (
    SupervisorState, SupervisorResponse, ResponseType, AgentInfo,
    HandoffRequest, HandoffResponse, SupervisorConfig
)
from .states import SupervisorStateManager
from .tools import SupervisorTools
from .prompts import SUPERVISOR_PROMPTS, AVAILABLE_AGENT_PROMPTS
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class SupervisorAgent:
    """
    Supervisor Agent for multi-agent orchestration.
    
    Features:
    - Agent registration and management
    - Intelligent handoff decision making
    - Conversation flow management
    - Error handling and recovery
    - Both standalone and integrated operation
    """
    
    def __init__(self, config: SupervisorConfig = None):
        self.llm = get_llm()
        self.config = config or SupervisorConfig()
        self.state_manager = SupervisorStateManager()
        self.tools = SupervisorTools()
        self.registered_agents = {}
        self.workflow = None
        
        # Initialize system prompt
        self.system_prompt = SUPERVISOR_PROMPTS["system_prompt"].format(
            available_agents=self._format_agents_for_prompt()
        )
    
    def _format_agents_for_prompt(self) -> str:
        """Format available agents for system prompt."""
        formatted = []
        for name, description in AVAILABLE_AGENT_PROMPTS.items():
            formatted.append(f"• {name}: {description}")
        return "\n".join(formatted)
    
    def register_agent(self, 
                      agent_name: str, 
                      agent_instance: Any, 
                      description: str = None) -> bool:
        """
        Register an agent with the supervisor.
        
        Args:
            agent_name: Name of the agent
            agent_instance: Instance of the agent
            description: Description of the agent's capabilities
            
        Returns:
            True if registration successful
        """
        try:
            # Use predefined description if available
            if description is None:
                description = AVAILABLE_AGENT_PROMPTS.get(
                    agent_name, 
                    f"Agent: {agent_name}"
                )
            
            # Create agent info
            agent_info = AgentInfo(
                name=agent_name,
                description=description,
                agent_instance=agent_instance,
                is_active=True
            )
            
            # Register with both tools and state manager
            self.tools.register_agent(agent_info)
            self.state_manager.register_agent(agent_info)
            self.registered_agents[agent_name] = agent_instance
            
            logger.info(f"Agent '{agent_name}' registered successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register agent '{agent_name}': {e}")
            return False
    
    def _build_supervisor_workflow(self):
        """Build the supervisor workflow using langgraph_supervisor."""
        try:
            # Create handoff tools for registered agents
            handoff_tools = []
            agents_for_supervisor = []
            
            for agent_name, agent_instance in self.registered_agents.items():
                # Create handoff tool
                description = AVAILABLE_AGENT_PROMPTS.get(
                    agent_name, 
                    f"Handoff to {agent_name} agent"
                )
                handoff_tool = self.tools.create_handoff_tool(agent_name, description)
                handoff_tools.append(handoff_tool)
                
                # Create react agent wrapper if needed
                if hasattr(agent_instance, 'chat_loop'):
                    react_agent = create_react_agent(
                        model=self.llm,
                        tools=[],
                        name=agent_name,
                        prompt=f"You are the {agent_name} agent. {description}"
                    )
                    agents_for_supervisor.append(react_agent)
            
            # Create supervisor workflow
            self.workflow = create_supervisor(
                agents=agents_for_supervisor,
                model=self.llm,
                tools=handoff_tools,
                prompt=self.system_prompt,
                supervisor_name="supervisor"
            )
            
            logger.info("Supervisor workflow built successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to build supervisor workflow: {e}")
            return False
    
    async def _determine_target_agent(self, user_request: str) -> Optional[str]:
        """
        Use LLM to determine the target agent for a user request.
        
        Args:
            user_request: User's request
            
        Returns:
            Name of target agent or None
        """
        try:
            # Create prompt for agent selection
            selection_prompt = SUPERVISOR_PROMPTS["agent_selection_prompt"].format(
                user_request=user_request,
                available_agents=self._format_agents_for_prompt()
            )
            
            # Get LLM response
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=selection_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            # Parse response to extract agent name
            response_text = response.content.lower()
            
            # Check for agent names in response (exact match)
            for agent_name in self.registered_agents.keys():
                if agent_name.lower() in response_text:
                    return agent_name
            
            # Check for keyword-based matching if exact match fails
            keyword_mapping = {
                # Order matters: Question/learning keywords first, then execution
                "hlateacher": ["question", "questions", "what is", "how does", "explain", "tell me about", "learn about", "what are", "help me understand", "genetics", "biology", "teacher", "learning", "answer", "research", "web search", "rag", "mcp", "mcp server", "search"],
                "hlafinemapping": ["do fine mapping", "perform fine mapping", "run fine mapping", "execute fine mapping", "fine mapping analysis", "hla fine mapping", "hla finemapping", "fine mapping", "finemapping", "association", "customizable fine mapping", "node1", "node2", "node3", "node4", "node5", "workflow customization", "custom workflow", "hatk"],
                "hlaimputation": ["do imputation", "perform imputation", "run imputation", "execute imputation", "imputation analysis", "hla imputation", "imputation", "cookhla", "hla-hd", "hlahd", "optitype", "hla typing", "impute"],
                "genotypephasing": ["do phasing", "perform phasing", "run phasing", "genotype phasing", "phasing", "beagle", "genotype", "phasing analysis"],
                "parameterhandler": ["modify parameter", "parameter modification", "parameter configuration", "parameter", "yaml", "config", "configuration"],
                "fileconverter": ["do conversion", "perform conversion", "run conversion", "modify file", "converting", "modifying", "convert", "format", "file conversion", "vcf", "plink", "bed", "bim", "fam", "beagle", "hped", "genotype conversion", "beagle2vcf", "vcf2beagle"]
            }
            
            for agent_name, keywords in keyword_mapping.items():
                if agent_name in self.registered_agents:
                    for keyword in keywords:
                        if keyword in response_text or keyword in user_request.lower():
                            return agent_name
            
            return None
            
        except Exception as e:
            logger.error(f"Error determining target agent: {e}")
            return None
    
    async def _handoff_to_agent(self, 
                               agent_name: str, 
                               task_description: str,
                               user_request: str) -> HandoffResponse:
        """
        Handoff a task to a specific agent.
        
        Args:
            agent_name: Name of target agent
            task_description: Description of the task
            user_request: Original user request
            
        Returns:
            HandoffResponse with results
        """
        try:
            # Check if agent is available
            if not self.tools.is_agent_available(agent_name):
                return HandoffResponse(
                    success=False,
                    message=f"Agent '{agent_name}' is not available",
                    error=f"Agent '{agent_name}' is not registered or inactive"
                )
            
            # Get agent instance
            agent_instance = self.registered_agents.get(agent_name)
            if not agent_instance:
                return HandoffResponse(
                    success=False,
                    message=f"Agent '{agent_name}' not found",
                    error=f"Agent instance for '{agent_name}' not found"
                )
            
            # Set active agent
            self.state_manager.set_active_agent(agent_name)
            self.state_manager.set_current_task(task_description)
            
            # Execute handoff
            print(SUPERVISOR_PROMPTS["handoff_message"].format(
                agent_name=agent_name,
                task_description=task_description
            ))
            
            # For agents that support nested handoffs, inject the supervisor callback
            if hasattr(agent_instance, 'supervisor_handoff_callback'):
                # Create nested handoff callback for this handoff session
                async def nested_handoff_callback(agent_name: str, task_description: str, **kwargs) -> bool:
                    """Nested handoff callback for agents that need to handoff to other agents."""
                    try:
                        logger.info(f"Nested handoff requested: {agent_name} - {task_description}")
                        
                        # Get target agent instance
                        target_agent = self.registered_agents.get(agent_name)
                        if not target_agent:
                            logger.error(f"Agent '{agent_name}' not found for nested handoff")
                            return False
                        
                        # Handle parameter handler specifically (needs yaml_path)
                        if agent_name == "parameterhandler" and "yaml_path" in kwargs:
                            result = await target_agent.chat_loop(
                                yaml_path=kwargs["yaml_path"],
                                requester="workchain",
                                task_id=f"nested_{self.state_manager.state.session_id}"
                            )
                            success = result.get("status") == "completed" if isinstance(result, dict) else bool(result)
                            logger.info(f"Parameter handler nested handoff completed with success={success}")
                            return success
                        
                        # Handle other agents with normal chat_loop
                        elif hasattr(target_agent, 'chat_loop'):
                            # Inject nested callback into target agent for further nested handoffs
                            if hasattr(target_agent, 'supervisor_handoff_callback'):
                                target_agent.supervisor_handoff_callback = nested_handoff_callback
                                
                                # Also inject into target agent's workchain if it exists
                                if hasattr(target_agent, 'workchain') and target_agent.workchain:
                                    target_agent.workchain.supervisor_handoff_callback = nested_handoff_callback
                            
                            result = await target_agent.chat_loop(
                                requester_agent="supervisor_nested",
                                task_id=f"nested_{self.state_manager.state.session_id}"
                            )
                            success = bool(result)
                            logger.info(f"Nested handoff to {agent_name} completed with success={success}")
                            return success
                        
                        else:
                            logger.error(f"Agent '{agent_name}' does not support chat_loop")
                            return False
                            
                    except Exception as e:
                        logger.error(f"Nested handoff to {agent_name} failed: {e}")
                        return False
                
                # Inject the nested callback
                agent_instance.supervisor_handoff_callback = nested_handoff_callback
                
                # Also inject into workchain if it exists
                if hasattr(agent_instance, 'workchain') and agent_instance.workchain:
                    agent_instance.workchain.supervisor_handoff_callback = nested_handoff_callback
                
                # For HLA imputation agent, inject into workflow and workchain_manager
                if hasattr(agent_instance, 'workflow') and agent_instance.workflow:
                    agent_instance.workflow.supervisor_handoff_callback = nested_handoff_callback
                    if hasattr(agent_instance.workflow, 'workchain_manager') and agent_instance.workflow.workchain_manager:
                        agent_instance.workflow.workchain_manager.supervisor_handoff_callback = nested_handoff_callback
                        if hasattr(agent_instance.workflow.workchain_manager, 'workchain') and agent_instance.workflow.workchain_manager.workchain:
                            agent_instance.workflow.workchain_manager.workchain.supervisor_handoff_callback = nested_handoff_callback
            
            # Call agent's chat_loop method
            if hasattr(agent_instance, 'chat_loop'):
                result = await agent_instance.chat_loop(
                    requester_agent="supervisor",
                    task_id=self.state_manager.state.session_id
                )
                
                # Clear active agent after completion
                self.state_manager.set_active_agent(None)
                self.state_manager.clear_current_task()
                
                # Ensure supervisor remains in CHATTING state after handoff
                self.state_manager.transition(SupervisorState.CHATTING)
                
                return HandoffResponse(
                    success=True,
                    message=f"Successfully completed handoff to {agent_name}",
                    result_data={"output": result}
                )
            else:
                return HandoffResponse(
                    success=False,
                    message=f"Agent '{agent_name}' does not support chat_loop",
                    error="Agent does not have chat_loop method"
                )
                
        except Exception as e:
            logger.error(f"Handoff to {agent_name} failed: {e}")
            self.state_manager.set_active_agent(None)
            self.state_manager.clear_current_task()
            return HandoffResponse(
                success=False,
                message=f"Handoff to {agent_name} failed",
                error=str(e)
            )
    
    async def process_user_input(self, user_input: str) -> SupervisorResponse:
        """
        Process user input and determine appropriate action.
        
        Args:
            user_input: User's input
            
        Returns:
            SupervisorResponse with action to take
        """
        try:
            user_input = user_input.strip()
            
            # Handle special commands
            if user_input.lower() == "done!" or user_input.lower() == "exit!":
                self.state_manager.transition(SupervisorState.COMPLETED)
                return SupervisorResponse(
                    response_type=ResponseType.COMPLETION,
                    message=SUPERVISOR_PROMPTS["goodbye_message"],
                    session_complete=True
                )
            
            elif user_input.lower() == "help":
                return SupervisorResponse(
                    response_type=ResponseType.INFO,
                    message=SUPERVISOR_PROMPTS["help_message"],
                    requires_input=True
                )
            
            elif user_input.lower() == "agents":
                agents_info = self.tools.get_agents_summary()
                message = SUPERVISOR_PROMPTS["agents_list"].format(agents_info=agents_info)
                return SupervisorResponse(
                    response_type=ResponseType.INFO,
                    message=message,
                    requires_input=True
                )
            
            elif user_input.lower() == "status":
                state_info = self.state_manager.get_state_info()
                message = SUPERVISOR_PROMPTS["session_status"].format(
                    session_id=state_info["session_id"],
                    current_state=state_info["current_state"],
                    active_agent=state_info["active_agent"] or "None",
                    agent_count=len(state_info["registered_agents"]),
                    message_count=state_info["conversation_length"],
                    current_task=state_info["current_task"] or "None"
                )
                return SupervisorResponse(
                    response_type=ResponseType.INFO,
                    message=message,
                    requires_input=True
                )
            
            # Regular request processing
            self.state_manager.add_message("user", user_input)
            
            # Determine target agent
            target_agent = await self._determine_target_agent(user_input)
            
            if target_agent:
                # Execute handoff
                handoff_response = await self._handoff_to_agent(
                    target_agent, 
                    user_input, 
                    user_input
                )
                
                if handoff_response.success:
                    completion_message = SUPERVISOR_PROMPTS["handoff_complete"].format(
                        agent_name=target_agent
                    )
                    return SupervisorResponse(
                        response_type=ResponseType.SUCCESS,
                        message=completion_message,
                        requires_input=True,
                        data=handoff_response.result_data
                    )
                else:
                    error_message = SUPERVISOR_PROMPTS["handoff_error"].format(
                        agent_name=target_agent,
                        error_message=handoff_response.error
                    )
                    return SupervisorResponse(
                        response_type=ResponseType.ERROR,
                        message=error_message,
                        requires_input=True
                    )
            else:
                # No suitable agent found
                return SupervisorResponse(
                    response_type=ResponseType.INFO,
                    message=SUPERVISOR_PROMPTS["invalid_input"],
                    requires_input=True
                )
                
        except Exception as e:
            logger.error(f"Error processing user input: {e}")
            return SupervisorResponse(
                response_type=ResponseType.ERROR,
                message=SUPERVISOR_PROMPTS["error_message"].format(error_message=str(e)),
                requires_input=True
            )
    
    async def chat_loop(self) -> Dict[str, Any]:
        """
        Main interactive chat loop for standalone operation.
        
        Returns:
            Final session result
        """
        try:
            # Initialize session
            self.state_manager.initialize_session()
            self.state_manager.transition(SupervisorState.CHATTING)
            
            # Print welcome message
            print(SUPERVISOR_PROMPTS["welcome_message"])
            print(" /$$   /$$ /$$        /$$$$$$                                  /$$    ")
            print("| $$  | $$| $$       /$$__  $$                                | $$    ")
            print("| $$  | $$| $$      | $$  \ $$  /$$$$$$   /$$$$$$  /$$$$$$$  /$$$$$$  ")
            print("| $$$$$$$$| $$      | $$$$$$$$ /$$__  $$ /$$__  $$| $$__  $$|_  $$_/  ")
            print("| $$__  $$| $$      | $$__  $$| $$  \ $$| $$$$$$$$| $$  \ $$  | $$    ")
            print("| $$  | $$| $$      | $$  | $$| $$  | $$| $$_____/| $$  | $$  | $$ /$$")
            print("| $$  | $$| $$$$$$$$| $$  | $$|  $$$$$$$|  $$$$$$$| $$  | $$  |  $$$$/")
            print("|__/  |__/|________/|__/  |__/ \____  $$ \_______/|__/  |__/   \___/  ")
            print("                               /$$  \ $$                              ")
            print("                              |  $$$$$$/                              ")
            print("                               \______/                               ")


            # Main interaction loop
            while not self.state_manager.is_session_complete():
                try:
                    user_input = input("\n>>To Supervisor Agent>>").strip()
                    
                    if not user_input:
                        continue
                    
                    response = await self.process_user_input(user_input)
                    print(f"\n{response.message}")
                    
                    if response.session_complete:
                        break
                        
                except KeyboardInterrupt:
                    print("\n\nSession interrupted by user.")
                    break
                except Exception as e:
                    logger.error(f"Error in chat loop: {e}")
                    print(f"\nError: {e}")
                    continue
            
            # Return final result
            state_info = self.state_manager.get_state_info()
            return {
                "status": "completed",
                "session_id": state_info["session_id"],
                "final_state": state_info["current_state"],
                "conversation_length": state_info["conversation_length"]
            }
            
        except Exception as e:
            logger.error(f"Fatal error in chat loop: {e}")
            print(f"\n❌ Fatal error: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_session_info(self) -> Dict[str, Any]:
        """Get current session information."""
        return self.state_manager.get_state_info()
    
    def get_registered_agents(self) -> List[str]:
        """Get list of registered agent names."""
        return list(self.registered_agents.keys())


# Convenience function for creating the supervisor
def create_supervisor_agent(config: SupervisorConfig = None) -> SupervisorAgent:
    """
    Create a supervisor agent instance.
    
    Args:
        config: SupervisorConfig for configuration
        
    Returns:
        SupervisorAgent instance
    """
    return SupervisorAgent(config=config)