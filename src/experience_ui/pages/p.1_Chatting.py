"""
Streamlit Web UI for HLAgent multi-agent system.
Tests agent delegation between Supervisor and HLA Teacher agents.
"""

import streamlit as st
import asyncio
import sys
import os
import time
from typing import Dict, Any, Optional
from dotenv import load_dotenv


load_dotenv()


# Add the project root to Python path
project_root = os.getenv("HLAGENT_MAIN_DIRECTORY")
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.agents_pa.supervisor.agent import supervisor_agent_pa
from src.agents_pa.supervisor.dependencies import SupervisorDependencies

# Configure Streamlit page
st.set_page_config(
    page_title="HLAgent Multi-Agent Chat",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

def initialize_session_state():
    """Initialize Streamlit session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "supervisor_deps" not in st.session_state:
        st.session_state.supervisor_deps = SupervisorDependencies.create_default()
    
    if "handover_active" not in st.session_state:
        st.session_state.handover_active = False
    
    if "agents_initialized" not in st.session_state:
        st.session_state.agents_initialized = False
    
    if "streaming_enabled" not in st.session_state:
        st.session_state.streaming_enabled = True

async def initialize_agents():
    """Initialize supervisor agent asynchronously."""
    if not st.session_state.agents_initialized:
        with st.spinner("Initializing supervisor agent..."):
            await supervisor_agent_pa.initialize()
            st.session_state.agents_initialized = True

def display_chat_history():
    """Display chat messages from session history."""
    for message in st.session_state.messages:
        role = message["role"]
        content = message["content"]
        agent_info = message.get("agent", "")
        
        # Use different avatars for different agents
        if role == "user":
            avatar = "👤"
        elif "supervisor" in agent_info.lower():
            avatar = "🎯"
        elif "hlateacher" in agent_info.lower() or "hla teacher" in agent_info.lower():
            avatar = "🎓"
        elif "fileconverter" in agent_info.lower() or "file converter" in agent_info.lower():
            avatar = "📁"
        elif "parameterhandler" in agent_info.lower() or "parameter handler" in agent_info.lower():
            avatar = "⚙️"
        elif "genotypephasing" in agent_info.lower() or "genotype phasing" in agent_info.lower():
            avatar = "👨‍👩‍👧"
        elif "hlaimputation" in agent_info.lower() or "hla imputation" in agent_info.lower():
            avatar = "🧬"
        elif "hlafinemapping" in agent_info.lower() or "hla fine mapping" in agent_info.lower():
            avatar = "🔬"
        else:
            avatar = "🤖"
        
        with st.chat_message(role, avatar=avatar):
            if agent_info:
                st.caption(f"Agent: {agent_info}")
            st.markdown(content)

async def show_streaming_progress(placeholder, message="agent is thinking"):
    """Show animated progress indicator for streaming."""
    dots = ""
    for i in range(3):
        dots += "."
        placeholder.markdown(f"🤖 **{message}{dots}**\n\n💭 *Preparing to stream response...*")
        await asyncio.sleep(0.3)

async def process_user_message_stream(prompt: str, placeholder):
    """Process user message with streaming response through supervisor agent."""
    try:
        # Handle exit commands directly without processing through agent
        if prompt.strip().lower() in ["/exit"]:
            # End any active delegation
            if st.session_state.supervisor_deps.delegation_active:
                st.session_state.supervisor_deps.end_delegation()
                st.session_state.handover_active = False
            
            return "🎯 **Supervisor**: Thank you for using HLAgent! Session ended. You can refresh the page to start a new session.", "Supervisor"
        
        # Check if this should be handled by HLA Teacher (for streaming support)
        hla_teacher_keywords = ["hlateacher", "hla teacher", "hla teacher agent", "teacher agent"]
        should_use_hla_teacher = any(keyword in prompt.lower() for keyword in hla_teacher_keywords)
        
        # Force delegation if not already active for HLA queries
        if should_use_hla_teacher and not st.session_state.supervisor_deps.delegation_active:
            # First delegate to HLA Teacher through supervisor
            await supervisor_agent_pa.run(
                prompt, 
                st.session_state.supervisor_deps,
                message_history=None
            )
        
        if should_use_hla_teacher and st.session_state.supervisor_deps.delegation_active and st.session_state.supervisor_deps.active_sub_agent == "hlateacher":
            # Direct streaming to HLA Teacher
            from src.agents_pa.hlateacher.agent import hlateacher_agent_pa
            from src.agents_pa.hlateacher.dependencies import HLATeacherDependencies
            
            # Get HLA teacher dependencies from supervisor's stored dependencies
            hla_deps = st.session_state.supervisor_deps.hlateacher_deps
            if hla_deps is None:
                # Fallback to default if not available
                hla_deps = HLATeacherDependencies.create_default()
            
            # Initialize if needed
            if not hlateacher_agent_pa._initialized:
                await hlateacher_agent_pa.initialize(hla_deps)
            
            # Show animated thinking progress
            await show_streaming_progress(placeholder, "HLA Teacher is researching")
            
            # Stream the response
            full_response = ""
            chunk_count = 0
            streaming_patterns = ["🌊**Streaming** .", "🌊**Streaming** ..", "🌊**Streaming** ..."]
            async with await hlateacher_agent_pa.run_stream(prompt, hla_deps) as result:
                async for text in result.stream(debounce_by=0.01):
                    full_response = text
                    chunk_count += 1
                    
                    # Show streaming indicator with progress
                    streaming_indicator = streaming_patterns[chunk_count % len(streaming_patterns)]
                    placeholder.markdown(f"🎓 **HLA Teacher Response:** {streaming_indicator}\n\n{text}")
            
            # Add document citations for RAG mode
            if hla_deps.current_mode.name == "RAG_ENHANCED":
                try:
                    # Extract document sources used in knowledge base search
                    used_documents = await hlateacher_agent_pa._extract_used_documents(prompt, hla_deps)
                    
                    if used_documents:
                        citation_text = f"\n\n**📚 Documents used in this response:** {', '.join(used_documents)}"
                        full_response_with_citations = full_response + citation_text
                    else:
                        full_response_with_citations = full_response
                except Exception as e:
                    # If citation extraction fails, continue without citations
                    full_response_with_citations = full_response
            else:
                full_response_with_citations = full_response
            
            # Final response without streaming indicator but with citations
            placeholder.markdown(f"🎓 **HLA Teacher Response:** ✅ **Complete**\n\n{full_response_with_citations}")
            
            return full_response_with_citations, "HLA Teacher (via Supervisor)"
        
        else:
            # Use supervisor agent for non-HLA queries or initial delegation
            response = await supervisor_agent_pa.run(
                prompt, 
                st.session_state.supervisor_deps,
                message_history=None
            )
            
            # Determine agent status based on delegation state
            if st.session_state.supervisor_deps.delegation_active:
                if st.session_state.supervisor_deps.active_sub_agent == "hlateacher":
                    agent_used = "HLA Teacher (via Supervisor)"
                    st.session_state.handover_active = True
                elif st.session_state.supervisor_deps.active_sub_agent == "fileconverter":
                    agent_used = "File Converter (via Supervisor)"
                    st.session_state.handover_active = True
                elif st.session_state.supervisor_deps.active_sub_agent == "parameterhandler":
                    agent_used = "Parameter Handler (via Supervisor)"
                    st.session_state.handover_active = True
                elif st.session_state.supervisor_deps.active_sub_agent == "genotypephasing":
                    agent_used = "Genotype Phasing (via Supervisor)"
                    st.session_state.handover_active = True
                elif st.session_state.supervisor_deps.active_sub_agent == "hlaimputation":
                    agent_used = "HLA Imputation (via Supervisor)"
                    st.session_state.handover_active = True
                elif st.session_state.supervisor_deps.active_sub_agent == "hlafinemapping":
                    agent_used = "HLA Fine Mapping (via Supervisor)"
                    st.session_state.handover_active = True
                else:
                    agent_used = "Supervisor (delegating)"
            else:
                agent_used = "Supervisor"
                st.session_state.handover_active = False
            
            return response, agent_used
        
    except Exception as e:
        error_msg = f"Error processing message: {str(e)}"
        st.error(error_msg)
        return error_msg, "Error"


async def process_user_message(prompt: str) -> tuple[str, str]:
    """Process user message through supervisor agent with handover support (non-streaming fallback)."""
    try:
        # Handle exit commands directly without processing through agent
        if prompt.strip().lower() in ["/exit"]:
            # End any active delegation
            if st.session_state.supervisor_deps.delegation_active:
                st.session_state.supervisor_deps.end_delegation()
                st.session_state.handover_active = False
            
            return "🎯 **Supervisor**: Thank you for using HLAgent! Session ended. You can refresh the page to start a new session.", "Supervisor"
        
        # Always use supervisor agent - it handles handover automatically
        response = await supervisor_agent_pa.run(
            prompt, 
            st.session_state.supervisor_deps,
            message_history=None  # Let PydanticAI handle conversation internally
        )
        
        # Determine agent status based on delegation state
        if st.session_state.supervisor_deps.delegation_active:
            if st.session_state.supervisor_deps.active_sub_agent == "hlateacher":
                agent_used = "HLA Teacher (via Supervisor)"
                st.session_state.handover_active = True
            elif st.session_state.supervisor_deps.active_sub_agent == "fileconverter":
                agent_used = "File Converter (via Supervisor)"
                st.session_state.handover_active = True
            elif st.session_state.supervisor_deps.active_sub_agent == "parameterhandler":
                agent_used = "Parameter Handler (via Supervisor)"
                st.session_state.handover_active = True
            elif st.session_state.supervisor_deps.active_sub_agent == "genotypephasing":
                agent_used = "Genotype Phasing (via Supervisor)"
                st.session_state.handover_active = True
            elif st.session_state.supervisor_deps.active_sub_agent == "hlaimputation":
                agent_used = "HLA Imputation (via Supervisor)"
                st.session_state.handover_active = True
            elif st.session_state.supervisor_deps.active_sub_agent == "hlafinemapping":
                agent_used = "HLA Fine Mapping (via Supervisor)"
                st.session_state.handover_active = True
            else:
                agent_used = "Supervisor (delegating)"
        else:
            agent_used = "Supervisor"
            st.session_state.handover_active = False
        
        return response, agent_used
        
    except Exception as e:
        error_msg = f"Error processing message: {str(e)}"
        st.error(error_msg)
        return error_msg, "Error"

def create_sidebar():
    """Create sidebar with session information and handover status."""
    with st.sidebar:
        st.header("🤖 Agent Status")
        
        # Show current agent status
        if st.session_state.handover_active:
            if st.session_state.supervisor_deps.active_sub_agent == "hlateacher":
                st.success("🎓 **Active**: HLA Teacher (via Supervisor)")
                st.info("💡 Ask HLA/genetics questions or type 'Done!' to return to Supervisor")
            elif st.session_state.supervisor_deps.active_sub_agent == "fileconverter":
                st.success("📁 **Active**: File Converter (via Supervisor)")
                st.info("💡 Ask file conversion jobs or type 'Done!' to return to Supervisor")
            elif st.session_state.supervisor_deps.active_sub_agent == "parameterhandler":
                st.success("⚙️ **Active**: Parameter Handler (via Supervisor)")
                st.info("💡 Edit YAML parameters or type 'Done!' to return to Supervisor")
            elif st.session_state.supervisor_deps.active_sub_agent == "genotypephasing":
                st.success("👨‍👩‍👧 **Active**: Genotype Phasing (via Supervisor)")
                st.info("💡 Type 'Done!' to return to Supervisor")
            elif st.session_state.supervisor_deps.active_sub_agent == "hlaimputation":
                st.success("🧬 **Active**: HLA Imputation (via Supervisor)")
                st.info("💡 Type 'Done!' to return to Supervisor")
            elif st.session_state.supervisor_deps.active_sub_agent == "hlafinemapping":
                st.success("🔬 **Active**: HLA Fine Mapping (via Supervisor)")
                st.info("💡 Type 'Done!' to return to Supervisor")
            else: 
                st.success("🤖 **Active**: Specialist Agent (via Supervisor)")
                st.info("💡 Type 'Done!' to return to Supervisor")
        else:
            st.success("🎯 **Active**: Supervisor")
            st.info("💡 Ask any jobs - Supervisor agent will be handed over proper agent automatically")
        
        # Streaming toggle
#        st.session_state.streaming_enabled = st.toggle(
#            "🌊 Enable Streaming Responses", 
#            value=st.session_state.streaming_enabled,
#            help="Real-time streaming for HLA Teacher responses"
#        )

        st.divider()
        
        st.header("📊 Session Info")
        
        # Supervisor info
        with st.expander("🎯 Supervisor Agent", expanded=False):
            supervisor_info = st.session_state.supervisor_deps.get_session_info()
            st.json({
                "Session ID": supervisor_info.get("session_id", "N/A"),
                "Conversations": len(st.session_state.supervisor_deps.conversation_history),
                "Context": supervisor_info.get("current_context", "general")
            })
        
        # Handover Status
        with st.expander("🔄 Handover Status", expanded=False):
            active_agent_name = "Supervisor"
            if st.session_state.handover_active and st.session_state.supervisor_deps.active_sub_agent:
                if st.session_state.supervisor_deps.active_sub_agent == "hlateacher":
                    active_agent_name = "HLA Teacher"
                elif st.session_state.supervisor_deps.active_sub_agent == "fileconverter":
                    active_agent_name = "File Converter"
                elif st.session_state.supervisor_deps.active_sub_agent == "parameterhandler":
                    active_agent_name = "Parameter Handler"
                elif st.session_state.supervisor_deps.active_sub_agent == "genotypephasing":
                    active_agent_name = "Genotype Phasing"
                elif st.session_state.supervisor_deps.active_sub_agent == "hlaimputation":
                    active_agent_name = "HLA Imputation"
                elif st.session_state.supervisor_deps.active_sub_agent == "hlafinemapping":
                    active_agent_name = "HLA Fine Mapping"
                else:
                    active_agent_name = st.session_state.supervisor_deps.active_sub_agent.title()
            
            handover_info = {
                "Handover Active": st.session_state.handover_active,
                "Active Agent": active_agent_name,
                "Delegation State": st.session_state.supervisor_deps.delegation_active,
                "Active Sub-Agent": st.session_state.supervisor_deps.active_sub_agent
            }
            st.json(handover_info)
        
        st.divider()
        
        # Clear chat button
        if st.button("🗑️ Clear Chat", type="secondary"):
            st.session_state.messages = []
            st.session_state.supervisor_deps = SupervisorDependencies.create_default()
            st.session_state.handover_active = False
            st.rerun()
        
        # End session button
        if st.button("🚪 End Session", type="primary"):
            # End any active delegation
            if st.session_state.supervisor_deps.delegation_active:
                st.session_state.supervisor_deps.end_delegation()
                st.session_state.handover_active = False
            
            # Add exit message to chat
            st.session_state.messages.append({
                "role": "assistant", 
                "content": "🎯 **Supervisor**: Thank you for using HLAgent! Session ended. You can refresh the page to start a new session.",
                "agent": "Supervisor"
            })
            st.rerun()
        
        st.divider()
        
        # Agent capabilities info
        st.header("ℹ️ Agent Capabilities")
        
        with st.expander("🎯 Supervisor Agent"):
            st.markdown("""
            - **Intelligent Delegation**: Automatically routes queries to appropriate specialists
            - **General Queries**: Handles non-specialized questions directly  
            - **Context Management**: Maintains conversation context across delegations
            - **Multi-Agent Coordination**: Orchestrates interactions between agents
            """)
        
        with st.expander("🎓 HLA Teacher Specialist"):
            st.markdown("""
            - **HLA Expertise**: Deep knowledge of HLA typing and genetics
            - **Biology Education**: Comprehensive biology and genetics instruction
            - **Multiple Modes**: Web search, RAG-enhanced, and MCP-enhanced modes
            - **Research Tools**: Access to scientific databases and literature
            - **Streaming Responses**: Real-time answer generation (toggle in sidebar)
            - **Memory**: Remembers conversation context across questions
            - **Handover**: Automatically activated for HLA/genetics questions
            """)
        
        with st.expander("📁 File Converter Specialist"):
            st.markdown("""
            - **File Conversion**: Converts files to different formats
            - **Memory**: Remembers conversation context across questions
            - **Handover**: Automatically activated for file conversion questions
            """)
        
        with st.expander("⚙️ Parameter Handler Specialist"):
            st.markdown("""
            - **Parameter Handling**: Manages YAML parameter files
            - **Memory**: Remembers conversation context across questions
            - **Handover**: Automatically activated for parameter handling questions
            """)
        
        with st.expander("👨‍👩‍👧 Genotype Phasing Specialist"):
            st.markdown("""
            - **Genotype Phasing**: Performs genotype phasing on genomic data
            - **Memory**: Remembers conversation context across questions
            - **Handover**: Automatically activated for genotype phasing questions
            """)
        
        with st.expander("🧬 HLA Imputation Specialist"):
            st.markdown("""
            - **HLA Imputation**: Performs HLA imputation on genomic data
            - **Memory**: Remembers conversation context across questions
            - **Handover**: Automatically activated for HLA imputation questions
            """)
        
        with st.expander("🔬 HLA Fine Mapping Specialist"):
            st.markdown("""
            - **HLA Fine Mapping**: Performs HLA fine mapping on genomic data
            - **Memory**: Remembers conversation context across questions
            - **Handover**: Automatically activated for HLA fine mapping questions
            """)

def main():
    """Main Streamlit application for multi-agent chatting."""
    st.title("🤖 HLAgent Multi-Agent Chat Interface")
    st.markdown("**HLAgent: Crew of HLA Specialist agents**")
    
    # Initialize session state
    initialize_session_state()
    
    # Run async initialization
    asyncio.run(initialize_agents())
    
    # Create sidebar
    create_sidebar()
    
    # Main chat interface
    col1, col2 = st.columns([3, 1])
    
    with col1:
        if st.session_state.handover_active:
            if st.session_state.supervisor_deps.active_sub_agent == "hlateacher":
                st.subheader("🎓 Chat with HLA Teacher")
            elif st.session_state.supervisor_deps.active_sub_agent == "fileconverter":
                st.subheader("📁 Chat with File Converter")
            elif st.session_state.supervisor_deps.active_sub_agent == "genotypephasing":
                st.subheader("👨‍👩‍👧 Chat with Genotype Phasing")
            elif st.session_state.supervisor_deps.active_sub_agent == "hlaimputation":
                st.subheader("🧬 Chat with HLA Imputation")
            elif st.session_state.supervisor_deps.active_sub_agent == "hlafinemapping":
                st.subheader("🔬 Chat with HLA Fine Mapping")
            else:
                st.subheader("🤖 Chat with Specialist Agent")
        else:
            st.subheader("🎯 Chat with Supervisor")
    
    with col2:
        if st.session_state.handover_active:
            if st.session_state.supervisor_deps.active_sub_agent == "hlateacher":
                st.info("🎓 HLA specialist active")
            elif st.session_state.supervisor_deps.active_sub_agent == "fileconverter":
                st.info("📁 File converter active")
            elif st.session_state.supervisor_deps.active_sub_agent == "genotypephasing":
                st.info("👨‍👩‍👧 Genotype phasing active")
            elif st.session_state.supervisor_deps.active_sub_agent == "hlaimputation":
                st.info("🧬 HLA imputation active")
            elif st.session_state.supervisor_deps.active_sub_agent == "hlafinemapping":
                st.info("🔬 HLA fine mapping active")
            else:
                st.info("🤖 Specialist active")
        else:
            st.info("🎯 Auto-handover enabled")
    
    # Display chat history
    display_chat_history()
    
    # Chat input
    if prompt := st.chat_input("Ask me any jobs about HLA or questions ..."):
        # Add user message to chat history
        st.session_state.messages.append({
            "role": "user", 
            "content": prompt,
            "agent": "User"
        })
        
        # Display user message
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)
        
        # Process message and get response with streaming support
        with st.chat_message("assistant", avatar="🤖"):
            # Create placeholder for streaming content
            response_placeholder = st.empty()
            
            # Check if this should use streaming (HLA-related queries and streaming enabled)
            hla_keywords = ["hlateacher", "hla teacher", "hla teacher agent", "teacher agent"]
            should_stream = (
                st.session_state.streaming_enabled and 
                any(keyword in prompt.lower() for keyword in hla_keywords) and 
                st.session_state.handover_active
            )
            
            if should_stream:
                # Show initial dynamic loading indicator
                response_placeholder.markdown("🎓 🔄 *Initializing streaming response...*")
                
                # Use streaming response
                response, agent_used = asyncio.run(
                    process_user_message_stream(prompt, response_placeholder)
                )
            else:
                # Use regular response with spinner
                with st.spinner("Thinking..."):
                    response, agent_used = asyncio.run(
                        process_user_message(prompt)
                    )
                response_placeholder.markdown(response)
            
            # Display agent info
            st.caption(f"Agent: {agent_used}")
        
        # Add assistant response to chat history
        st.session_state.messages.append({
            "role": "assistant", 
            "content": response,
            "agent": agent_used
        })
        
        # Rerun to update the interface
        st.rerun()
    
    # Example prompts
    st.divider()
    st.subheader("🤖 Example Prompts")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🎓 Question about HLA", help="Biology question - will be delegated if using Supervisor"):
            st.session_state.example_prompt = "I want to see hla teacher agent"
    
    with col2:
        if st.button("🔬 HLA Fine Mapping anlaysis", help="Requesting HLA fine mapping analysis - will be delegated if using Supervisor"):
            st.session_state.example_prompt = "Lets do hla fine mapping analysis with hla fine mapping agent"
    
    with col3:
        if st.button("📁 File converting", help="Requesting file converting - will be delegated if using Supervisor"):
            st.session_state.example_prompt = "I want to do file converting my data"
    
    # Handle example prompt selection
    if hasattr(st.session_state, 'example_prompt'):
        st.info(f"Selected example: {st.session_state.example_prompt}")
        st.markdown("👆 **Use the chat input above to send this message**")
        delattr(st.session_state, 'example_prompt')

if __name__ == "__main__":
    main()