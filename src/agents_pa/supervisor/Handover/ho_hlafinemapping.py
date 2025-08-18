"""
HLA Fine Mapping handover module for supervisor agent delegation.
Handles all HLA Fine Mapping agent handover operations for customizable workflow execution.
"""

from src.agents_pa.supervisor.dependencies import SupervisorDependencies
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class HLAFineMappingHandover:
    @staticmethod
    async def handover_to_hlafinemapping(
        initial_query: str, 
        deps: SupervisorDependencies
    ) -> str:
        """
        Hand over control to HLA Fine Mapping agent for interactive workflow session.
        
        Args:
            initial_query: The HLA fine mapping query that triggered handover
            deps: Supervisor dependencies
            
        Returns:
            Summary of the handover session
        """
        try:
            from src.agents_pa.hlafinemapping.agent import hlafinemapping_agent_pa
            from src.agents_pa.hlafinemapping.dependencies import HLAFineMappingDependencies
            
            # Start handover tracking
            deps.start_delegation("hlafinemapping", f"HLA fine mapping handover for: {initial_query[:50]}...")
            
            # Create HLA Fine Mapping dependencies with supervisor context
            hlafinemapping_deps = HLAFineMappingDependencies.create_default(
                session_id=deps.session_id,
                requester_agent="supervisor",
                task_id=f"handover_{len(deps.conversation_history)}"
            )
            
            # Initialize HLA fine mapping agent if needed
            await hlafinemapping_agent_pa.initialize(hlafinemapping_deps)
            
            # Display handover message
            print(f"\nSupervisor: I'll connect you with our HLA Fine Mapping specialist for customizable workflow analysis.")
            print(f"Initial request: {initial_query}")
            print("You can execute customizable workflows with Node1-5. Type 'Done!' when finished.\n")
            
            # Start with the initial query to HLA Fine Mapping agent
            print("HLA Fine Mapping: Let me help you with HLA fine mapping analysis...")
            initial_response = await hlafinemapping_agent_pa.run(initial_query, hlafinemapping_deps)
            print(f"HLA Fine Mapping: {initial_response}\n")
            
            # Hand over control to HLA Fine Mapping agent for interactive session
            session_result = await hlafinemapping_agent_pa.chat_loop(
                deps=hlafinemapping_deps,
                standalone=False
            )
            
            # End handover
            deps.end_delegation()
            
            # Return summary
            session_summary = f"Completed interactive HLA fine mapping session. Nodes completed: {session_result.get('nodes_completed', 0)}. Output files: {len(session_result.get('output_files', []))}. Session status: {session_result.get('status', 'unknown')}"
            
            logger.info(f"HLA Fine Mapping handover completed: {session_summary}")
            return session_summary
            
        except Exception as e:
            logger.error(f"Error in HLA Fine Mapping handover: {e}")
            deps.end_delegation()
            return f"I encountered an error while connecting you with the HLA Fine Mapping agent: {str(e)}. Please try asking your question directly."
    
    @staticmethod
    async def process_with_hlafinemapping(
        query: str, 
        deps: SupervisorDependencies
    ) -> str:
        """
        Process query with HLA Fine Mapping agent (Streamlit-compatible).
        
        Args:
            query: The HLA fine mapping query
            deps: Supervisor dependencies
            
        Returns:
            Welcome message from HLA Fine Mapping agent
        """
        try:
            from src.agents_pa.hlafinemapping.agent import hlafinemapping_agent_pa
            from src.agents_pa.hlafinemapping.dependencies import HLAFineMappingDependencies
            
            # Start handover tracking
            deps.start_delegation("hlafinemapping", f"HLA fine mapping handover initiated: {query[:30]}...")
            
            # Create HLA Fine Mapping dependencies with supervisor context
            hlafinemapping_deps = HLAFineMappingDependencies.create_default(
                session_id=deps.session_id,
                requester_agent="supervisor",
                task_id=f"handover_{len(deps.conversation_history)}"
            )
            
            # Store dependencies in supervisor for persistence
            deps.hlafinemapping_deps = hlafinemapping_deps
            
            # Initialize HLA fine mapping agent with error handling
            try:
                await hlafinemapping_agent_pa.initialize(hlafinemapping_deps)
            except Exception as init_error:
                logger.error(f"Failed to initialize HLA Fine Mapping agent: {init_error}")
                # Continue with handover despite initialization error
                pass
            
            # Store the initial query for potential later use
            deps.add_conversation("user", query, "handover_trigger")
            
            # Return welcome message instead of processing the query
            welcome_response = f"**HLA Fine Mapping Agent**: Hello! I'm the HLA Fine Mapping agent, specialized in customizable HLA fine mapping workflows using HATK (HLA Analysis ToolKit).\n\n> **My capabilities**:\n\n**Customizable Workflow Execution**\n- **Node1**: HLA binary marker panel creation (essential for new users)\n- **Node2**: Regression analysis from binary marker panel\n- **Node3**: Stepwise conditional regression\n- **Node4**: Omnibus test (requires genotype phasing output)\n- **Node5**: Meta analysis from 2+ datasets\n\n**Workflow Examples:**\n- Standard workflow: Node1, Node2, Node3\n- Extended analysis: Node1, Node2, Node4, Node3\n- Meta analysis: Node1, Node2, Node5\n\n**Getting Started:**\n- For HLA fine mapping, you'll need `.hped` files (from CookHLA) and phenotype files (`.phe`)\n- Phenotype format: `FID IID Phenotype state`\n- Example file: `data/examples/wtccc_filtered_58C_RA.hatk.300+300.phe`\n\n*Say 'Yes' to start workflow customization, or type 'Done!' to return to Supervisor.*"
            
            logger.info("Successfully initiated handover to HLA Fine Mapping with welcome message")
            return welcome_response
            
        except Exception as e:
            logger.error(f"Error initiating handover to HLA Fine Mapping: {e}")
            deps.end_delegation()
            return f"I encountered an error while connecting you with the HLA Fine Mapping agent: {str(e)}. Please try asking your question directly."
    
    @staticmethod
    async def process_hlafinemapping_followup(
        query: str,
        deps: SupervisorDependencies
    ) -> str:
        """
        Process follow-up query with HLA Fine Mapping agent (when already in handover mode).
        
        Args:
            query: Follow-up query for HLA Fine Mapping agent
            deps: Supervisor dependencies
            
        Returns:
            Response from HLA Fine Mapping agent
        """
        try:
            from src.agents_pa.hlafinemapping.agent import hlafinemapping_agent_pa
            from src.agents_pa.hlafinemapping.dependencies import HLAFineMappingDependencies
            
            # Check if "Done!" to end handover
            if query.lower().strip() == "done!":
                deps.end_delegation()
                return "**Supervisor**: Welcome back! The HLA Fine Mapping session is complete. What can I do for you now?"
            
            # Reuse existing HLA Fine Mapping dependencies to preserve session state
            hlafinemapping_deps = deps.hlafinemapping_deps
            
            # If no existing deps, create new ones (fallback)
            if hlafinemapping_deps is None:
                hlafinemapping_deps = HLAFineMappingDependencies.create_default(
                    session_id=deps.session_id,
                    requester_agent="supervisor",
                    task_id=f"followup_{len(deps.conversation_history)}"
                )
                deps.hlafinemapping_deps = hlafinemapping_deps
            
            try:
                await hlafinemapping_agent_pa.initialize(hlafinemapping_deps)
            except Exception as init_error:
                logger.error(f"Failed to initialize HLA Fine Mapping agent in followup: {init_error}")
                # Continue despite initialization error
                pass
            
            response = await hlafinemapping_agent_pa.run(query, hlafinemapping_deps)
            
            # Add to conversation history
            deps.add_conversation("user", query, "hlafinemapping_session")
            deps.add_conversation("assistant", response, "hlafinemapping")
            
            return f"**HLA Fine Mapping**: {response}\n\n*Continue with workflow customization and execution, or type 'Done!' to return to Supervisor.*"
            
        except Exception as e:
            logger.error(f"Error in HLA Fine Mapping follow-up: {e}")
            return f"**HLA Fine Mapping**: I encountered an error: {str(e)}. Type 'Done!' to return to Supervisor."