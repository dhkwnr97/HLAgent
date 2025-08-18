"""
HLA Teacher handover module for supervisor agent delegation.
Handles all HLA Teacher agent handover operations.
"""

from src.agents_pa.supervisor.dependencies import SupervisorDependencies
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class HLATeacherHandover:
    @staticmethod
    async def handover_to_hlateacher(
        initial_query: str, 
        deps: SupervisorDependencies
    ) -> str:
        """
        Hand over control to HLATeacher agent for interactive session.
        
        Args:
            initial_query: The HLA-related query that triggered handover
            deps: Supervisor dependencies
            
        Returns:
            Summary of the handover session
        """
        try:
            from src.agents_pa.hlateacher.agent import hlateacher_agent_pa
            from src.agents_pa.hlateacher.dependencies import HLATeacherDependencies
            
            # Start handover tracking
            deps.start_delegation("hlateacher", f"HLA handover for: {initial_query[:50]}...")
            
            # Create HLATeacher dependencies with supervisor context
            hlateacher_deps = HLATeacherDependencies.create_default(
                session_id=deps.session_id,
                requester_agent="supervisor",
                task_id=f"handover_{len(deps.conversation_history)}"
            )
            
            # Initialize hlateacher if needed
            await hlateacher_agent_pa.initialize(hlateacher_deps)
            
            # Display handover message
            print(f"\n🎯 Supervisor: I'll connect you with our HLA Teacher specialist for this question.")
            print(f"Initial question: {initial_query}")
            print("You can ask multiple questions to the HLA Teacher. Type 'Done!' when finished.\n")
            
            # Start with the initial query to HLA Teacher
            print("HLA Teacher: Let me help you with that question...")
            initial_response = await hlateacher_agent_pa.run(initial_query, hlateacher_deps)
            print(f"HLA Teacher: {initial_response}\n")
            
            # Hand over control to HLA Teacher for interactive session
            session_result = await hlateacher_agent_pa.chat_loop(
                deps=hlateacher_deps,
                standalone=False
            )
            
            # End handover
            deps.end_delegation()
            
            # Return summary
            session_summary = f"Completed interactive session with HLA Teacher. Conversation count: {session_result.get('conversation_count', 0)}. Session status: {session_result.get('status', 'unknown')}"
            
            logger.info(f"Handover completed: {session_summary}")
            return session_summary
            
        except Exception as e:
            logger.error(f"Error in HLATeacher handover: {e}")
            deps.end_delegation()
            return f"I encountered an error while connecting you with the HLA Teacher: {str(e)}. Please try asking your question directly."
    
    @staticmethod
    async def process_with_hlateacher(
        query: str, 
        deps: SupervisorDependencies
    ) -> str:
        """
        Process query with HLATeacher agent (Streamlit-compatible).
        
        Args:
            query: The HLA-related query
            deps: Supervisor dependencies
            
        Returns:
            Welcome message from HLATeacher instead of processing the initial query
        """
        try:
            from src.agents_pa.hlateacher.agent import hlateacher_agent_pa
            from src.agents_pa.hlateacher.dependencies import HLATeacherDependencies
            
            # Start handover tracking
            deps.start_delegation("hlateacher", f"HLA handover initiated: {query[:30]}...")
            
            # Create HLATeacher dependencies with supervisor context
            hlateacher_deps = HLATeacherDependencies.create_default(
                session_id=deps.session_id,
                requester_agent="supervisor",
                task_id=f"handover_{len(deps.conversation_history)}"
            )
            
            # Store dependencies in supervisor for persistence
            deps.hlateacher_deps = hlateacher_deps
            
            # Initialize hlateacher if needed
            await hlateacher_agent_pa.initialize(hlateacher_deps)
            
            # Store the initial query for potential later use
            deps.add_conversation("user", query, "handover_trigger")
            
            # Return welcome message instead of processing the query
            welcome_response = f"Supervisor agent handover to HLA teacher agent.\n\n🎓 **HLA Teacher**: Hello! I'm the HLA Teacher agent, specialized in HLA, genetics, biology, and immunology topics. Please ask me any questions you have about these subjects.\n\n📝 **Available modes**: Simply type '/web' (web search-only), '/rag' (knowledge base enhanced), or '/mcp' (MCP tools) to change modes.\n\n💬 *Ask me anything about HLA, genetics, or biology. Type 'Done!' when finished to return to the Supervisor.*"
            
            logger.info("Successfully initiated handover to HLATeacher with welcome message")
            return welcome_response
            
        except Exception as e:
            logger.error(f"Error initiating handover to HLATeacher: {e}")
            deps.end_delegation()
            return f"I encountered an error while connecting you with the HLA Teacher: {str(e)}. Please try asking your question directly."
    
    @staticmethod
    async def process_hlateacher_followup(
        query: str,
        deps: SupervisorDependencies
    ) -> str:
        """
        Process follow-up query with HLATeacher (when already in handover mode).
        
        Args:
            query: Follow-up query for HLATeacher
            deps: Supervisor dependencies
            
        Returns:
            Response from HLATeacher
        """
        try:
            from src.agents_pa.hlateacher.agent import hlateacher_agent_pa
            from src.agents_pa.hlateacher.dependencies import HLATeacherDependencies
            
            # Check if "Done!" to end handover
            if query.lower().strip() == "done!":
                deps.end_delegation()
                return "🎯 **Supervisor**: Welcome back! The HLA Teacher session is complete. What can I do for you now?"
            
            # Reuse existing HLATeacher dependencies to preserve mode
            hlateacher_deps = deps.hlateacher_deps
            
            # If no existing deps, create new ones (fallback)
            if hlateacher_deps is None:
                hlateacher_deps = HLATeacherDependencies.create_default(
                    session_id=deps.session_id,
                    requester_agent="supervisor",
                    task_id=f"followup_{len(deps.conversation_history)}"
                )
                deps.hlateacher_deps = hlateacher_deps
            
            # Ensure HLA Teacher is initialized
            await hlateacher_agent_pa.initialize(hlateacher_deps)
            
            # Use the HLA Teacher's run method which properly handles commands like /rag
            response = await hlateacher_agent_pa.run(query, hlateacher_deps)
            
            # Add to conversation history
            deps.add_conversation("user", query, "hlateacher_session")
            deps.add_conversation("assistant", response, "hlateacher")
            
            # Format response based on content
            if response.startswith("🎓"):
                # Response already formatted by HLA Teacher
                return f"{response}\n\n💬 *Continue asking HLA/genetics questions, or type 'Done!' to return to Supervisor.*"
            else:
                return f"🎓 **HLA Teacher**: {response}\n\n💬 *Continue asking HLA/genetics questions, or type 'Done!' to return to Supervisor.*"
            
        except Exception as e:
            logger.error(f"Error in HLATeacher follow-up: {e}")
            return f"🎓 **HLA Teacher**: I encountered an error: {str(e)}. Type 'Done!' to return to Supervisor."
