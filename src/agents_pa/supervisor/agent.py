"""
PydanticAI Supervisor Agent for HLAgent multi-agent system.
Orchestrates conversations and delegates to specialized sub-agents.
"""

import os
import asyncio
from typing import Optional, List
from pydantic_ai import Agent

# Fix for event loop issues with Gemini models
from src.utils.event_loop_fix import apply_event_loop_fix
apply_event_loop_fix()

from src.agents_pa.shared.universal_providers import get_supervisor_model
from src.agents_pa.shared.settings import settings
from .dependencies import SupervisorDependencies
from .tools import create_supervisor_tools
from src.utils.logger import setup_logger
from .prompts import SUPERVISOR_SYSTEM_PROMPT
from .Handover.ho_hlateacher import HLATeacherHandover
from .Handover.ho_fileconverter import FileConverterHandover
from .Handover.ho_parameterhandler import ParameterHandlerHandover
from .Handover.ho_genotypephasing import GenotypePhasingHandover
from .Handover.ho_hlaimputation import HLAImputationHandover
from .Handover.ho_hlafinemapping import HLAFineMappingHandover

logger = setup_logger(__name__)

# Fresh agent creation function to prevent event loop issues
def get_fresh_supervisor_agent():
    """Create a fresh supervisor agent to prevent event loop binding issues."""
    agent = Agent(
        model=get_supervisor_model(),
        deps_type=SupervisorDependencies,
        system_prompt=SUPERVISOR_SYSTEM_PROMPT
    )
    # Register tools with the agent
    return create_supervisor_tools(agent)

# Create global agent with fresh creation pattern
supervisor_agent = get_fresh_supervisor_agent()


class SupervisorAgentPA:
    """
    PydanticAI-based Supervisor Agent for multi-agent orchestration.
    Main entry point for user interactions with delegation capabilities.
    """
    
    def __init__(self):
        self.agent = None  # Will be created fresh on initialization
        self._initialized = False
    
    async def initialize(self):
        """Initialize supervisor agent components."""
        if self._initialized:
            return
        
        logger.info("Initializing PydanticAI Supervisor agent...")
        
        # Create fresh agent to prevent event loop binding issues
        try:
            self.agent = get_fresh_supervisor_agent()
            logger.info("Initialized fresh Supervisor agent successfully")
        except Exception as e:
            if "event loop" in str(e).lower() or "bound to a different" in str(e).lower():
                logger.warning(f"Event loop issue detected, creating fresh agent: {e}")
                # Reset any cached models and create fresh agent
                from src.agents_pa.shared.universal_providers import universal_provider
                universal_provider.clear_cache()
                
                self.agent = get_fresh_supervisor_agent()
                logger.info("Successfully created fresh Supervisor agent after event loop fix")
            else:
                raise
        
        self._initialized = True
        logger.info("Supervisor agent initialized successfully")
    
    async def run(
        self,
        query: str,
        deps: SupervisorDependencies,
        message_history: Optional[List] = None
    ) -> str:
        """
        Process user query with intelligent handover to specialist agents.
        
        Args:
            query: User query
            deps: Supervisor dependencies
            message_history: Optional conversation history
            
        Returns:
            Response (either direct or handover result)
        """
        if not self._initialized:
            await self.initialize()
        
        logger.info(f"Supervisor processing query: '{query}'")
        
        try:
            # Add query to conversation history
            deps.add_conversation("user", query, "supervisor")
            
            # Check if we're in handover mode or need to start handover
            if deps.delegation_active:
                if deps.active_sub_agent == "hlateacher":
                    # We're already in HLA Teacher mode, process follow-up
                    return await HLATeacherHandover.process_hlateacher_followup(query, deps)
                elif deps.active_sub_agent == "fileconverter":
                    # We're already in File Converter mode, process follow-up
                    return await FileConverterHandover.process_fileconverter_followup(query, deps)
                elif deps.active_sub_agent == "parameterhandler":
                    # We're already in Parameter Handler mode, process follow-up
                    return await ParameterHandlerHandover.process_parameterhandler_followup(query, deps)
                elif deps.active_sub_agent == "genotypephasing":
                    # We're already in Genotype Phasing mode, process follow-up
                    return await GenotypePhasingHandover.process_genotypephasing_followup(query, deps)
                elif deps.active_sub_agent == "hlaimputation":
                    # We're already in HLA Imputation mode, process follow-up
                    return await HLAImputationHandover.process_hlaimputation_followup(query, deps)
                elif deps.active_sub_agent == "hlafinemapping":
                    # We're already in HLA Fine Mapping mode, process follow-up
                    return await HLAFineMappingHandover.process_hlafinemapping_followup(query, deps)
            
            # Use intelligent agent selection to determine best agent
            best_agent, confidence, reason = deps.select_best_agent(query)
            
            if best_agent == "hlateacher" and confidence > 0.7:
                logger.info(f"Starting handover to HLATeacher: {reason}")
                return await HLATeacherHandover.process_with_hlateacher(query, deps)
            elif best_agent == "fileconverter" and confidence > 0.7:
                logger.info(f"Starting handover to FileConverter: {reason}")
                return await FileConverterHandover.process_with_fileconverter(query, deps)
            elif best_agent == "parameterhandler" and confidence > 0.7:
                logger.info(f"Starting handover to ParameterHandler: {reason}")
                return await ParameterHandlerHandover.process_with_parameterhandler(query, deps)
            elif best_agent == "genotypephasing" and confidence > 0.7:
                logger.info(f"Starting handover to Genotype Phasing: {reason}")
                return await GenotypePhasingHandover.process_with_genotypephasing(query, deps)
            elif best_agent == "hlaimputation" and confidence > 0.7:
                logger.info(f"Starting handover to HLA Imputation: {reason}")
                return await HLAImputationHandover.process_with_hlaimputation(query, deps)
            elif best_agent == "hlafinemapping" and confidence > 0.7:
                logger.info(f"Starting handover to HLA Fine Mapping: {reason}")
                return await HLAFineMappingHandover.process_with_hlafinemapping(query, deps)
            else:
                logger.info(f"Handling directly: {reason}")
                
                # Handle general queries directly
                if message_history and len(message_history) > 0:
                    result = await self.agent.run(
                        query,
                        deps=deps,
                        message_history=message_history
                    )
                else:
                    result = await self.agent.run(query, deps=deps)
                response = result.output
                
                # Add response to conversation history
                deps.add_conversation("assistant", response, "supervisor")
                
                return response
            
        except Exception as e:
            logger.error(f"Error in supervisor processing: {e}")
            error_response = f"I encountered an error while processing your request. Please try again or ask for help with available agents. Error: {str(e)}"
            deps.add_conversation("assistant", error_response, "supervisor")
            return error_response
    
    async def chat_loop(
        self,
        deps: Optional[SupervisorDependencies] = None,
        a2a_mode: bool = False
    ) -> dict:
        """
        Interactive chat loop for direct user interaction.
        
        Args:
            deps: Optional dependencies (will create default if not provided)
            a2a_mode: Whether running in A2A protocol mode
            
        Returns:
            Session completion information
        """
        if deps is None:
            deps = SupervisorDependencies.create_default()
        
        await self.initialize()
        
        # Display welcome message
        if a2a_mode:
            print("\n=== HLAgent Supervisor (A2A Mode) ===")
            print("Connected via Agent-to-Agent protocol")
        else:
            print("\n=== HLAgent Supervisor ===")
            print("Welcome to the HLAgent multi-agent system!")
        
        print("I can help you directly or connect you with specialist agents:")
        print("• HLA Teacher - for HLA, genetics, and biology questions")
        print("• Type 'exit' to end the conversation")
        print("• Type 'agents' to see available specialists\n")
        
        while True:
            try:
                if a2a_mode:
                    user_input = input("A2A User: ").strip()
                else:
                    user_input = input("User: ").strip()
                
                # Handle exit commands
                if user_input.lower() in ["exit", "quit", "Done!"]:
                    print("\nSupervisor: Thank you for using HLAgent! Goodbye!")
                    break
                
                # Handle special commands
                if user_input.lower() == "agents":
                    print("\nSupervisor: Let me show you the available specialist agents...")
                    agents_info = await self.agent.run(
                        "show me available agents",
                        deps=deps
                    )
                    print(f"Supervisor: {agents_info.output}\n")
                    continue
                
                # Handle empty input
                if not user_input:
                    print("Supervisor: Please ask jobs or type 'exit' to end the conversation.")
                    continue
                
                # Process the query
                print("Supervisor: Let me help you with that...")
                response = await self.run(user_input, deps)
                print(f"Supervisor: {response}\n")
                
            except KeyboardInterrupt:
                print("\n\nSupervisor: Goodbye! Thank you for using HLAgent!")
                break
            except Exception as e:
                logger.error(f"Error in supervisor chat loop: {e}")
                print(f"Supervisor: I encountered an error: {e}\n")
        
        # Return session completion info
        return {
            "status": "completed",
            "session_id": deps.session_id,
            "conversation_count": len(deps.conversation_history),
            "delegations_made": sum(1 for conv in deps.conversation_history if conv.get("agent_source") != "supervisor"),
            "a2a_mode": a2a_mode,
            "final_context": deps.current_context
        }
    
    def to_a2a(self):
        """
        Create A2A (Agent-to-Agent) protocol endpoint.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                coro = self.initialize()
                asyncio.ensure_future(coro)
            else:
                loop.run_until_complete(self.initialize())
        except RuntimeError:
            # For environments with no running loop
            asyncio.run(self.initialize())
        return self.agent.to_a2a()
    
    async def handover_to_hlateacher(
        self, 
        initial_query: str, 
        deps: SupervisorDependencies
    ) -> str:
        """
        Hand over control to HLATeacher agent for interactive session.
        Delegates to HLATeacherHandover class.
        
        Args:
            initial_query: The HLA-related query that triggered handover
            deps: Supervisor dependencies
            
        Returns:
            Summary of the handover session
        """
        return await HLATeacherHandover.handover_to_hlateacher(initial_query, deps)
    
    async def handover_to_fileconverter(
        self, 
        initial_query: str, 
        deps: SupervisorDependencies
    ) -> str:
        """
        Hand over control to HLATeacher agent for interactive session.
        Delegates to FileConverterHandover class.
        
        Args:
            initial_query: The HLA-related query that triggered handover
            deps: Supervisor dependencies
            
        Returns:
            Summary of the handover session
        """
        return await FileConverterHandover.handover_to_fileconverter(initial_query, deps)
    
    async def handover_to_parameterhandler(
        self, 
        initial_query: str, 
        deps: SupervisorDependencies
    ) -> str:
        """
        Hand over control to ParameterHandler agent for interactive session.
        Delegates to ParameterHandlerHandover class.
        
        Args:
            initial_query: The HLA-related query that triggered handover
            deps: Supervisor dependencies
            
        Returns:
            Summary of the handover session
        """
        return await ParameterHandlerHandover.handover_to_parameterhandler(initial_query, deps)

    async def handover_to_genotypephasing(
        self, 
        initial_query: str, 
        deps: SupervisorDependencies
    ) -> str:
        """
        Hand over control to GenotypePhasing agent for interactive session.
        Delegates to GenotypePhasingHandover class.
        
        Args:
            initial_query: genotype phasing agent query that triggered handover
            deps: Supervisor dependencies
            
        Returns:
            Summary of the handover session
        """
        return await GenotypePhasingHandover.handover_to_genotypephasing(initial_query, deps)

    async def handover_to_hlaimputation(
        self, 
        initial_query: str, 
        deps: SupervisorDependencies
    ) -> str:
        """
        Hand over control to hlaimputation agent for interactive session.
        Delegates to HLAImputationHandover class.
        
        Args:
            initial_query: HLA imputation agent query that triggered handover
            deps: Supervisor dependencies
            
        Returns:
            Summary of the handover session
        """
        return await HLAImputationHandover.handover_to_hlaimputation(initial_query, deps)

    async def handover_to_hlafinemapping(
        self, 
        initial_query: str, 
        deps: SupervisorDependencies
    ) -> str:
        """
        Hand over control to hlafinemapping agent for interactive session.
        Delegates to HLAFineMappingHandover class.
        
        Args:
            initial_query: HLA fine mapping agent query that triggered handover
            deps: Supervisor dependencies
            
        Returns:
            Summary of the handover session
        """
        return await HLAFineMappingHandover.handover_to_hlafinemapping(initial_query, deps)            
    
    def get_session_info(self, deps: SupervisorDependencies) -> dict:
        """Get current session information."""
        return deps.get_session_info()
    


# Global instance for easy import
supervisor_agent_pa = SupervisorAgentPA()


if __name__ == "__main__":
    async def main():
        deps = SupervisorDependencies.create_default()
        await supervisor_agent_pa.chat_loop(deps, a2a_mode=False)
    
    asyncio.run(main())