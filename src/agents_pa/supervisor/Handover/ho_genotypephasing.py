"""
Genotype Phasing handover module for supervisor agent delegation.
Handles all Genotype Phasing agent handover operations for professional genotype phasing.
"""

from src.agents_pa.supervisor.dependencies import SupervisorDependencies
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class GenotypePhasingHandover:
    @staticmethod
    async def handover_to_genotypephasing(
        initial_query: str, 
        deps: SupervisorDependencies
    ) -> str:
        """
        Hand over control to Genotype Phasing agent for interactive phasing session.
        
        Args:
            initial_query: The genotype phasing query that triggered handover
            deps: Supervisor dependencies
            
        Returns:
            Summary of the handover session
        """
        try:
            from src.agents_pa.genotypephasing.agent import genotypephasing_agent_pa
            from src.agents_pa.genotypephasing.dependencies import GenotypePhasingDependencies
            
            # Start handover tracking
            deps.start_delegation("genotypephasing", f"Genotype phasing handover for: {initial_query[:50]}...")
            
            # Create Genotype Phasing dependencies with supervisor context
            genotypephasing_deps = GenotypePhasingDependencies.create_default(
                session_id=deps.session_id,
                requester_agent="supervisor",
                task_id=f"handover_{len(deps.conversation_history)}"
            )
            
            # Initialize genotype phasing agent if needed
            await genotypephasing_agent_pa.initialize(genotypephasing_deps)
            
            # Display handover message
            print(f"\nSupervisor: I'll connect you with our Genotype Phasing specialist for professional genotype phasing.")
            print(f"Initial request: {initial_query}")
            print("You can perform multiple phasing operations. Type 'Done!' when finished.\n")
            
            # Start with the initial query to Genotype Phasing agent
            print("Genotype Phasing Agent: Let me help you with genotype phasing...")
            initial_response = await genotypephasing_agent_pa.run(initial_query, genotypephasing_deps)
            print(f"Genotype Phasing Agent: {initial_response}\n")
            
            # Hand over control to Genotype Phasing agent for interactive session
            session_result = await genotypephasing_agent_pa.chat_loop(
                deps=genotypephasing_deps,
                standalone=False
            )
            
            # End handover
            deps.end_delegation()
            
            # Return summary
            session_summary = f"Completed interactive genotype phasing session. Phasing operations completed: {session_result.get('phasings_completed', 0)}. Output files: {len(session_result.get('output_files', []))}. Session status: {session_result.get('status', 'unknown')}"
            
            logger.info(f"Genotype Phasing handover completed: {session_summary}")
            return session_summary
            
        except Exception as e:
            logger.error(f"Error in Genotype Phasing handover: {e}")
            deps.end_delegation()
            return f"I encountered an error while connecting you with the Genotype Phasing agent: {str(e)}. Please try asking your request directly."
    
    @staticmethod
    async def process_with_genotypephasing(
        query: str, 
        deps: SupervisorDependencies
    ) -> str:
        """
        Process query with Genotype Phasing agent (Streamlit-compatible).
        
        Args:
            query: The genotype phasing query
            deps: Supervisor dependencies
            
        Returns:
            Welcome message from Genotype Phasing agent instead of processing the initial query
        """
        try:
            from src.agents_pa.genotypephasing.agent import genotypephasing_agent_pa
            from src.agents_pa.genotypephasing.dependencies import GenotypePhasingDependencies
            
            # Start handover tracking
            deps.start_delegation("genotypephasing", f"Genotype phasing handover initiated: {query[:30]}...")
            
            # Create Genotype Phasing dependencies with supervisor context
            genotypephasing_deps = GenotypePhasingDependencies.create_default(
                session_id=deps.session_id,
                requester_agent="supervisor",
                task_id=f"handover_{len(deps.conversation_history)}"
            )
            
            # Store dependencies in supervisor for persistence
            deps.genotypephasing_deps = genotypephasing_deps
            
            # Initialize genotype phasing agent if needed
            await genotypephasing_agent_pa.initialize(genotypephasing_deps)
            
            # Store the initial query for potential later use
            deps.add_conversation("user", query, "handover_trigger")
            
            # Return welcome message instead of processing the query
            welcome_response = f"**Genotype Phasing Agent**: Hello! I'm the Genotype Phasing Agent, specialized in professional genotype phasing using Beagle tools.\n\n> **My capabilities**:\n\n**Supported Input Formats:**\n**VCF files** (.vcf)\n- **Beagle v3 format** (.bgl, .markers)\n- **PLINK binary format** (.bed, .bim, .fam)\n\n**What I do:**\n- Perform high-quality genotype phasing using industry-standard Beagle algorithms\n- Handle large-scale genomic datasets efficiently  \n- Generate phased outputs in multiple formats (.aa, .phased, .bgl, .markers)\n\n**File Conversion Support:**\n- If your files need format conversion, I can connect you with the File Converter agent\n\n*Please let me know your file readiness status: 'ready', 'not ready', or 'other types'. Type 'Done!' when finished to return to the Supervisor.*"
            
            logger.info("Successfully initiated handover to Genotype Phasing agent with welcome message")
            return welcome_response
            
        except Exception as e:
            logger.error(f"Error initiating handover to Genotype Phasing agent: {e}")
            deps.end_delegation()
            return f"I encountered an error while connecting you with the Genotype Phasing agent: {str(e)}. Please try asking your request directly."
    
    @staticmethod
    async def process_genotypephasing_followup(
        query: str,
        deps: SupervisorDependencies
    ) -> str:
        """
        Process follow-up query with Genotype Phasing agent (when already in handover mode).
        
        Args:
            query: Follow-up query for Genotype Phasing agent
            deps: Supervisor dependencies
            
        Returns:
            Response from Genotype Phasing agent
        """
        try:
            from src.agents_pa.genotypephasing.agent import genotypephasing_agent_pa
            from src.agents_pa.genotypephasing.dependencies import GenotypePhasingDependencies
            
            # Check if "Done!" to end handover
            if query.lower().strip() == "done!":
                deps.end_delegation()
                return "**Supervisor**: Welcome back! The Genotype Phasing session is complete. What can I do for you now?"
            
            # Reuse existing Genotype Phasing dependencies to preserve session state
            genotypephasing_deps = deps.genotypephasing_deps
            
            # If no existing deps, create new ones (fallback)
            if genotypephasing_deps is None:
                genotypephasing_deps = GenotypePhasingDependencies.create_default(
                    session_id=deps.session_id,
                    requester_agent="supervisor",
                    task_id=f"followup_{len(deps.conversation_history)}"
                )
                deps.genotypephasing_deps = genotypephasing_deps
            
            await genotypephasing_agent_pa.initialize(genotypephasing_deps)
            response = await genotypephasing_agent_pa.run(query, genotypephasing_deps)
            
            # Add to conversation history
            deps.add_conversation("user", query, "genotypephasing_session")
            deps.add_conversation("assistant", response, "genotypephasing")
            
            return f"**Genotype Phasing Agent**: {response}\n\n*Continue with genotype phasing operations, or type 'Done!' to return to Supervisor.*"
            
        except Exception as e:
            logger.error(f"Error in Genotype Phasing follow-up: {e}")
            return f"**Genotype Phasing Agent**: I encountered an error: {str(e)}. Type 'Done!' to return to Supervisor."