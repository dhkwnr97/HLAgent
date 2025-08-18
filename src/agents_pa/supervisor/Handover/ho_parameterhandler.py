"""
Parameter Handler handover module for supervisor agent delegation.
Handles all Parameter Handler agent handover operations for YAML file modifications.
"""

from src.agents_pa.supervisor.dependencies import SupervisorDependencies
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class ParameterHandlerHandover:
    @staticmethod
    async def handover_to_parameterhandler(
        original_yaml_path: str, 
        deps: SupervisorDependencies
    ) -> str:
        """
        Hand over control to Parameter Handler agent for YAML file modification (workchain step 2).
        
        Args:
            original_yaml_path: Path to the original YAML file to be modified
            deps: Supervisor dependencies
            
        Returns:
            Summary of the handover session
        """
        try:
            from src.agents_pa.parameterhandler.agent import handle_workchain_request
            
            # Start handover tracking
            deps.start_delegation("parameterhandler", f"YAML modification for: {original_yaml_path}")
            
            # Display handover message
            print(f"\nSupervisor: I'll connect you with our Parameter Handler specialist for YAML modification.")
            print("You can modify multiple parameters. Type 'Done!' when finished.\n")
            
            # Start Parameter Handler session
            print("Parameter Handler: Let me help you modify that YAML file...")
            session_result = await handle_workchain_request(
                original_yaml_path=original_yaml_path,
                requester_agent="workchain_pa",
                task_id=f"workchain_step2_{len(deps.conversation_history)}"
            )
            
            # End handover
            deps.end_delegation()
            
            # Return summary based on session result
            status = session_result.get('status', 'unknown')
            working_file = session_result.get('working_file', 'N/A')
            
            if status == "completed":
                session_summary = f"YAML modification completed successfully. Ready for workchain step 3 (Python script execution)."
            elif status == "aborted":
                session_summary = f"YAML modification was aborted. Workchain cannot proceed."
            elif status == "interrupted":
                session_summary = f"YAML modification was interrupted. Workchain may be incomplete."
            else:
                session_summary = f"YAML modification ended with status: {status}. Working file: {working_file}"
            
            logger.info(f"Parameter Handler handover completed: {session_summary}")
            return session_summary
            
        except Exception as e:
            logger.error(f"Error in Parameter Handler handover: {e}")
            deps.end_delegation()
            return f"I encountered an error while connecting you with the Parameter Handler: {str(e)}. Please try asking your question directly."
    
    @staticmethod
    async def process_with_parameterhandler(
        query: str, 
        deps: SupervisorDependencies
    ) -> str:
        """
        Process query with Parameter Handler agent (Streamlit-compatible).
        
        Args:
            query: The YAML modification query
            deps: Supervisor dependencies
            
        Returns:
            Welcome message from Parameter Handler instead of processing the initial query
        """
        try:
            from src.agents_pa.parameterhandler.dependencies import ParameterHandlerDependencies
            
            # Start handover tracking
            deps.start_delegation("parameterhandler", f"YAML modification initiated: {query[:30]}...")
            
            # Create Parameter Handler dependencies with supervisor context
            parameterhandler_deps = ParameterHandlerDependencies.create_default(
                session_id=deps.session_id,
                requester_agent="supervisor",
                task_id=f"handover_{len(deps.conversation_history)}"
            )
            
            # Store dependencies in supervisor for persistence
            deps.parameterhandler_deps = parameterhandler_deps
            
            # Store the initial query for potential later use
            deps.add_conversation("user", query, "handover_trigger")
            
            # Return welcome message instead of processing the query
            welcome_response = f"""**Parameter Handler**: Hello! I'm the Parameter Handler agent, specialized in YAML configuration file modifications for bioinformatics workflows.

**My capabilities**:
- Parse natural language modification requests
- Apply modifications safely while preserving file structure  
- Validate YAML syntax after changes
- Show before/after values for transparency

**Examples of requests I can handle**:
- "Change line 19 to 18"
- "Set line 47 to ['A', 'B', 'C']"
- "Line 58 to false"
- "Update line 23 to 'new_value'"

Please provide the YAML file path you want to modify, or describe what changes you need. Type 'Done!' when finished to return to the Supervisor."""
            
            logger.info("Successfully initiated handover to Parameter Handler with welcome message")
            return welcome_response
            
        except Exception as e:
            logger.error(f"Error initiating handover to Parameter Handler: {e}")
            deps.end_delegation()
            return f"I encountered an error while connecting you with the Parameter Handler: {str(e)}. Please try asking your question directly."
    
    @staticmethod
    async def process_parameterhandler_followup(
        query: str,
        deps: SupervisorDependencies
    ) -> str:
        """
        Process follow-up query with Parameter Handler (when already in handover mode).
        
        Args:
            query: Follow-up query for Parameter Handler
            deps: Supervisor dependencies
            
        Returns:
            Response from Parameter Handler
        """
        try:
            from src.agents_pa.parameterhandler.agent import parameter_handler_agent
            from src.agents_pa.parameterhandler.dependencies import ParameterHandlerDependencies
            
            # Check if "Done!" to end handover
            if query.lower().strip() == "done!":
                deps.end_delegation()
                return "**Supervisor**: Welcome back! The Parameter Handler session is complete. What can I do for you now?"
            
            # Reuse existing Parameter Handler dependencies to preserve session state
            parameterhandler_deps = deps.parameterhandler_deps
            
            # If no existing deps, create new ones (fallback)
            if parameterhandler_deps is None:
                parameterhandler_deps = ParameterHandlerDependencies.create_default(
                    session_id=deps.session_id,
                    requester_agent="supervisor",
                    task_id=f"followup_{len(deps.conversation_history)}"
                )
                deps.parameterhandler_deps = parameterhandler_deps
            
            # Process the query with Parameter Handler
            response = await parameter_handler_agent.run(query, parameterhandler_deps)
            
            # Add to conversation history
            deps.add_conversation("user", query, "parameterhandler_session")
            deps.add_conversation("assistant", response, "parameterhandler")
            
            return f"=' **Parameter Handler**: {response}\n\n*Continue with YAML modifications, or type 'Done!' to return to Supervisor.*"
            
        except Exception as e:
            logger.error(f"Error in Parameter Handler follow-up: {e}")
            return f"=' **Parameter Handler**: I encountered an error: {str(e)}. Type 'Done!' to return to Supervisor."