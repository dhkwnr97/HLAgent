"""
HLA Imputation handover module for supervisor agent delegation.
Handles all HLA Imputation agent handover operations for professional HLA imputation.
"""

from src.agents_pa.supervisor.dependencies import SupervisorDependencies
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class HLAImputationHandover:
    @staticmethod
    async def handover_to_hlaimputation(
        initial_query: str, 
        deps: SupervisorDependencies
    ) -> str:
        """
        Hand over control to HLA Imputation agent for interactive imputation session.
        
        Args:
            initial_query: The HLA imputation query that triggered handover
            deps: Supervisor dependencies
            
        Returns:
            Summary of the handover session
        """
        try:
            from src.agents_pa.hlaimputation.agent import hlaimputation_agent_pa
            from src.agents_pa.hlaimputation.dependencies import HLAImputationDependencies
            
            # Start handover tracking
            deps.start_delegation("hlaimputation", f"HLA imputation handover for: {initial_query[:50]}...")
            
            # Create HLA Imputation dependencies with supervisor context
            hlaimputation_deps = HLAImputationDependencies.create_default(
                session_id=deps.session_id,
                requester_agent="supervisor",
                task_id=f"handover_{len(deps.conversation_history)}"
            )
            
            # Initialize HLA imputation agent if needed
            await hlaimputation_agent_pa.initialize(hlaimputation_deps)
            
            # Display handover message
            print(f"\n**Supervisor**: I'll connect you with our HLA Imputation specialist for professional HLA imputation.")
            print(f"Initial request: {initial_query}")
            print("You can perform multiple imputation operations. Type 'Done!' when finished.\n")
            
            # Start with the initial query to HLA Imputation agent
            print("HLA Imputation Agent: Let me help you with HLA imputation...")
            initial_response = await hlaimputation_agent_pa.run(initial_query, hlaimputation_deps)
            print(f"HLA Imputation Agent: {initial_response}\n")
            
            # Hand over control to HLA Imputation agent for interactive session
            session_result = await hlaimputation_agent_pa.chat_loop(
                deps=hlaimputation_deps,
                standalone=False
            )
            
            # End handover
            deps.end_delegation()
            
            # Return summary
            session_summary = f"Completed interactive HLA imputation session. Imputation operations completed: {session_result.get('imputations_completed', 0)}. Output files: {len(session_result.get('output_files', []))}. Session status: {session_result.get('status', 'unknown')}"
            
            logger.info(f"HLA Imputation handover completed: {session_summary}")
            return session_summary
            
        except Exception as e:
            logger.error(f"Error in HLA Imputation handover: {e}")
            deps.end_delegation()
            return f"I encountered an error while connecting you with the HLA Imputation agent: {str(e)}. Please try asking your request directly."
    
    @staticmethod
    async def process_with_hlaimputation(
        query: str, 
        deps: SupervisorDependencies
    ) -> str:
        """
        Process query with HLA Imputation agent (Streamlit-compatible).
        
        Args:
            query: The HLA imputation query
            deps: Supervisor dependencies
            
        Returns:
            Welcome message from HLA Imputation agent instead of processing the initial query
        """
        try:
            from src.agents_pa.hlaimputation.agent import hlaimputation_agent_pa
            from src.agents_pa.hlaimputation.dependencies import HLAImputationDependencies
            
            # Start handover tracking
            deps.start_delegation("hlaimputation", f"HLA imputation handover initiated: {query[:30]}...")
            
            # Create HLA Imputation dependencies with supervisor context
            hlaimputation_deps = HLAImputationDependencies.create_default(
                session_id=deps.session_id,
                requester_agent="supervisor",
                task_id=f"handover_{len(deps.conversation_history)}"
            )
            
            # Store dependencies in supervisor for persistence
            deps.hlaimputation_deps = hlaimputation_deps
            
            # Initialize HLA imputation agent if needed
            await hlaimputation_agent_pa.initialize(hlaimputation_deps)
            
            # Store the initial query for potential later use
            deps.add_conversation("user", query, "handover_trigger")
            
            # Return welcome message instead of processing the query
            welcome_response = f"**HLA Imputation Agent**: Hello! I'm the HLA Imputation Agent, specialized in professional HLA imputation using multiple bioinformatics tools.\n\n> **My capabilities**:\n\n**Available HLA Imputation Tools:**\n- =, **CookHLA** - PLINK v1 binary format (.bed, .bim, .fam)\n- >� **HLA-HD** - FASTQ format (.R1.fastq, .R2.fastq)\n**OptiType** - FASTQ format (.R1.fastq, .R2.fastq)\n\n**What I do:**\n- Perform high-quality HLA imputation using industry-standard algorithms\n- Support multiple HLA imputation tools with different input requirements\n- Generate comprehensive imputation results in various formats\n\n**File Conversion Support:**\n- If your files need format conversion, I can connect you with the File Converter agent\n\n*Please let me know your file readiness status: 'ready', 'not ready', or 'other types'. Type 'Done!' when finished to return to the Supervisor.*"
            
            logger.info("Successfully initiated handover to HLA Imputation agent with welcome message")
            return welcome_response
            
        except Exception as e:
            logger.error(f"Error initiating handover to HLA Imputation agent: {e}")
            deps.end_delegation()
            return f"I encountered an error while connecting you with the HLA Imputation agent: {str(e)}. Please try asking your request directly."
    
    @staticmethod
    async def process_hlaimputation_followup(
        query: str,
        deps: SupervisorDependencies
    ) -> str:
        """
        Process follow-up query with HLA Imputation agent (when already in handover mode).
        
        Args:
            query: Follow-up query for HLA Imputation agent
            deps: Supervisor dependencies
            
        Returns:
            Response from HLA Imputation agent
        """
        try:
            from src.agents_pa.hlaimputation.agent import hlaimputation_agent_pa
            from src.agents_pa.hlaimputation.dependencies import HLAImputationDependencies
            
            # Check if "Done!" to end handover
            if query.lower().strip() == "done!":
                deps.end_delegation()
                return "**Supervisor**: Welcome back! The HLA Imputation session is complete. What can I do for you now?"
            
            # Reuse existing HLA Imputation dependencies to preserve session state
            hlaimputation_deps = deps.hlaimputation_deps
            
            # If no existing deps, create new ones (fallback)
            if hlaimputation_deps is None:
                hlaimputation_deps = HLAImputationDependencies.create_default(
                    session_id=deps.session_id,
                    requester_agent="supervisor",
                    task_id=f"followup_{len(deps.conversation_history)}"
                )
                deps.hlaimputation_deps = hlaimputation_deps
            
            await hlaimputation_agent_pa.initialize(hlaimputation_deps)
            response = await hlaimputation_agent_pa.run(query, hlaimputation_deps)
            
            # Add to conversation history
            deps.add_conversation("user", query, "hlaimputation_session")
            deps.add_conversation("assistant", response, "hlaimputation")
            
            return f"**HLA Imputation Agent**: {response}\n\n*Continue with HLA imputation operations, or type 'Done!' to return to Supervisor.*"
            
        except Exception as e:
            logger.error(f"Error in HLA Imputation follow-up: {e}")
            return f"**HLA Imputation Agent**: I encountered an error: {str(e)}. Type 'Done!' to return to Supervisor."