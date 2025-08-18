"""
PydanticAI HLATeacher Agent for HLA/genetics/biology education.
"""

import os
import asyncio
import json
from typing import Optional
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from pydantic_ai.messages import ModelMessage
from rich.console import Console, ConsoleOptions, RenderResult
from rich.live import Live
from rich.markdown import CodeBlock, Markdown
from rich.syntax import Syntax
from rich.text import Text

# Fix for event loop issues with Gemini models
from src.utils.event_loop_fix import apply_event_loop_fix, ensure_event_loop, safe_run_async
apply_event_loop_fix()

from src.agents_pa.shared.universal_providers import get_hlateacher_model
from src.agents_pa.shared.settings import settings
from .dependencies import HLATeacherDependencies
from .tools import create_hlateacher_tools, create_web_only_tools, create_mcp_servers
from src.agents.hlateacher.prompts import HLA_TEACHER_PROMPTS
from src.agents.hlateacher.agent_types import AgentMode
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

# System prompt for HLATeacher agent
HLATEACHER_SYSTEM_PROMPT = HLA_TEACHER_PROMPTS["system"]


def prettier_code_blocks():
    class SimpleCodeBlock(CodeBlock):
        def __rich_console__(
            self, console: Console, options: ConsoleOptions
        ) -> RenderResult:
            code = str(self.text).rstrip()
            yield Text(self.lexer_name, style='dim')
            yield Syntax(
                code,
                self.lexer_name,
                theme=self.theme,
                background_color='default',
                word_wrap=True,
            )
            yield Text(f'/{self.lexer_name}', style='dim')

    Markdown.elements['fence'] = SimpleCodeBlock


async def keep_recent_messages(messages: list[ModelMessage]) -> list[ModelMessage]:
    """Keep only the last 10 messages to manage token usage while maintaining context."""
    return messages[-10:] if len(messages) > 10 else messages

# Fresh agent creation function to prevent event loop issues
def get_fresh_hlateacher_agent():
    """Create a fresh HLATeacher agent to prevent event loop binding issues."""
    agent = Agent(
        model=get_hlateacher_model(),
        deps_type=HLATeacherDependencies,
        system_prompt=HLATEACHER_SYSTEM_PROMPT,
        history_processors=[keep_recent_messages]
    )
    # Register tools with the agent
    return create_hlateacher_tools(agent)

def get_fresh_mcp_enhanced_agent(mcp_servers, system_prompt=None):
    """Create a fresh MCP-enhanced HLATeacher agent to prevent event loop binding issues."""
    prompt = system_prompt or HLA_TEACHER_PROMPTS.get("mcp_enhanced_system", HLATEACHER_SYSTEM_PROMPT)
    agent = Agent(
        model=get_hlateacher_model(),
        deps_type=HLATeacherDependencies,
        system_prompt=prompt,
        toolsets=mcp_servers,
        history_processors=[keep_recent_messages]
    )
    # Register tools with the agent
    return create_hlateacher_tools(agent)

# Fallback global agent for compatibility
hlateacher_agent = None


class HLATeacherAgentPA:
    """
    PydanticAI-based HLATeacher Agent for multi-agent system.
    Provides HLA/genetics/biology education with multiple operational modes.
    """
    
    def __init__(self):
        self.agent = None  # Will be created fresh on initialization
        self.agent_womcp = None
        self._initialized = False
        self.mcp_servers = []
        self.console = Console()
        prettier_code_blocks()
    
    async def initialize(self, deps: Optional[HLATeacherDependencies] = None):
        """Initialize agent components."""
        if self._initialized:
            return
        
        logger.info("Initializing PydanticAI HLATeacher agent...")
        
        # Create fresh agents to prevent event loop binding issues
        try:
            # Initialize HLA Teacher agent without mcp server - only with web search tool
            self.agent_womcp = Agent(
                model=get_hlateacher_model(),
                deps_type=HLATeacherDependencies,
                system_prompt=HLA_TEACHER_PROMPTS.get("web_only_response", HLATEACHER_SYSTEM_PROMPT),
                history_processors=[keep_recent_messages]
            )
            self.agent_womcp = create_web_only_tools(self.agent_womcp)
            logger.info("Initialized HLATeacher(without MCP servers agent) with web search tool only")
        except Exception as e:
            if "event loop" in str(e).lower() or "bound to a different" in str(e).lower():
                logger.warning(f"Event loop issue detected, creating fresh agent: {e}")
                # Reset any cached models and create fresh agent
                from src.agents_pa.shared.universal_providers import universal_provider
                universal_provider.clear_cache()
                
                self.agent_womcp = Agent(
                    model=get_hlateacher_model(),
                    deps_type=HLATeacherDependencies,
                    system_prompt=HLA_TEACHER_PROMPTS.get("web_only_response", HLATEACHER_SYSTEM_PROMPT),
                    history_processors=[keep_recent_messages]
                )
                self.agent_womcp = create_web_only_tools(self.agent_womcp)
                logger.info("Successfully created fresh HLATeacher agent after event loop fix")
            else:
                raise

        # Initialize ChromaDB knowledge manager
        if deps and deps.knowledge_manager:
            await deps.knowledge_manager.initialize()
            
        # Initialize MCP servers if available
        if deps and deps.mcp_servers:
            self.mcp_servers = create_mcp_servers(deps.mcp_servers)
            if self.mcp_servers:
                try:
                    # Create new agent with MCP toolsets and history processors
                    self.agent = Agent(
                        model=get_hlateacher_model(),
                        deps_type=HLATeacherDependencies,
                        system_prompt=HLA_TEACHER_PROMPTS.get("mcp_enhanced_system", HLATEACHER_SYSTEM_PROMPT),
                        toolsets=self.mcp_servers,
                        history_processors=[keep_recent_messages]
                    )
                    # Re-register tools
                    self.agent = create_hlateacher_tools(self.agent)
                    logger.info(f"Initialized HLATeacher with {len(self.mcp_servers)} MCP servers")
                except Exception as e:
                    if "event loop" in str(e).lower() or "bound to a different" in str(e).lower():
                        logger.warning(f"Event loop issue detected during MCP agent creation, creating fresh agent: {e}")
                        # Reset any cached models and create fresh agent
                        from src.agents_pa.shared.universal_providers import universal_provider
                        universal_provider.clear_cache()
                        
                        self.agent = Agent(
                            model=get_hlateacher_model(),
                            deps_type=HLATeacherDependencies,
                            system_prompt=HLA_TEACHER_PROMPTS.get("mcp_enhanced_system", HLATEACHER_SYSTEM_PROMPT),
                            toolsets=self.mcp_servers,
                            history_processors=[keep_recent_messages]
                        )
                        # Re-register tools
                        self.agent = create_hlateacher_tools(self.agent)
                        logger.info(f"Successfully created fresh MCP HLATeacher agent after event loop fix")
                    else:
                        raise
        
        self._initialized = True
        logger.info("HLATeacher agent initialized successfully")
    
    async def run(
        self, 
        query: str, 
        deps: HLATeacherDependencies,
        message_history: Optional[list] = None
    ) -> str:
        """
        Process a single query and return response.
        
        Args:
            query: User query about HLA/genetics/biology
            deps: Agent dependencies
            message_history: Optional conversation history
            
        Returns:
            Agent response string
        """
        if not self._initialized:
            await self.initialize(deps)
        
        # Handle mode switching commands first
        if query.strip().lower() in ["/web", "/rag", "/mcp"]:
            if query.strip().lower() == "/web":
                deps.set_mode(AgentMode.WEB_ONLY)
                return f"🎓 Switched to {AgentMode.WEB_ONLY.name} mode."
            elif query.strip().lower() == "/rag":
                deps.set_mode(AgentMode.RAG_ENHANCED)
                return f"🎓 Switched to {AgentMode.RAG_ENHANCED.name} mode."
            elif query.strip().lower() == "/mcp":
                if self.mcp_servers:
                    deps.set_mode(AgentMode.MCP_ENHANCED)
                    return f"🎓 Switched to {AgentMode.MCP_ENHANCED.name} mode."
                else:
                    return "🎓 MCP servers not available. Staying in current mode."
        
        logger.info(f"Processing query in {deps.current_mode.name} mode: '{query}'")
        
        try:
            # Add query to conversation history
            deps.add_conversation("user", query)
            
            # Generate response based on current mode
            if deps.current_mode == AgentMode.WEB_ONLY:
                response = await self._generate_web_response(query, deps, message_history)
            elif deps.current_mode == AgentMode.RAG_ENHANCED:
                response = await self._generate_rag_response(query, deps, message_history)
            elif deps.current_mode == AgentMode.MCP_ENHANCED:
                response = await self._generate_mcp_response(query, deps, message_history)
            else:
                response = "Unsupported mode. Please use 'web_only', 'rag_enhanced', or 'mcp_enhanced'."
            
            # Add response to conversation history
            deps.add_conversation("assistant", response)
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            error_response = f"I encountered an error while processing your question about HLA/genetics. Please try rephrasing your question or switching modes. Error: {str(e)}"
            deps.add_conversation("assistant", error_response)
            return error_response
            
    async def run_stream(
        self, 
        query: str, 
        deps: HLATeacherDependencies,
        message_history: Optional[list[ModelMessage]] = None
    ):
        """
        Process a query and return streaming response with message history.
        
        Args:
            query: User query about HLA/genetics/biology
            deps: Agent dependencies
            message_history: Optional conversation history (ModelMessage objects)
            
        Returns:
            StreamedRunResult for streaming responses
        """
        if not self._initialized:
            await self.initialize(deps)
        
        # Handle mode switching commands first
        if query.strip().lower() in ["/web", "/rag", "/mcp"]:
            if query.strip().lower() == "/web":
                deps.set_mode(AgentMode.WEB_ONLY)
                return f"🎓 Switched to {AgentMode.WEB_ONLY.name} mode."
            elif query.strip().lower() == "/rag":
                deps.set_mode(AgentMode.RAG_ENHANCED)
                return f"🎓 Switched to {AgentMode.RAG_ENHANCED.name} mode."
            elif query.strip().lower() == "/mcp":
                if self.mcp_servers:
                    deps.set_mode(AgentMode.MCP_ENHANCED)
                    return f"🎓 Switched to {AgentMode.MCP_ENHANCED.name} mode."
                else:
                    return "🎓 MCP servers not available. Staying in current mode."
        
        logger.info(f"Processing streaming query in {deps.current_mode.name} mode: '{query}'")
        
        try:
            # Add query to conversation history
            deps.add_conversation("user", query)
            
            # Generate streaming response based on current mode
            if deps.current_mode == AgentMode.WEB_ONLY:
                return await self._generate_web_stream(query, deps, message_history)
            elif deps.current_mode == AgentMode.RAG_ENHANCED:
                return await self._generate_rag_stream(query, deps, message_history)
            elif deps.current_mode == AgentMode.MCP_ENHANCED:
                return await self._generate_mcp_stream(query, deps, message_history)
            else:
                # Return a simple error message for unsupported modes
                error_msg = "Unsupported mode. Please use 'web_only', 'rag_enhanced', or 'mcp_enhanced'."
                deps.add_conversation("assistant", error_msg)
                return error_msg
            
        except Exception as e:
            logger.error(f"Error processing streaming query: {e}")
            error_response = f"I encountered an error while processing your question about HLA/genetics. Please try rephrasing your question or switching modes. Error: {str(e)}"
            deps.add_conversation("assistant", error_response)
            return error_response
    
    async def _generate_web_response(
        self, 
        query: str, 
        deps: HLATeacherDependencies,
        message_history: Optional[list] = None
    ) -> str:
        """Generate response using web search only."""
        enhanced_query = f"Please search the web for information about: {query}. Focus on HLA, genetics, and biology topics. Provide a comprehensive educational answer with proper citations."
        
        try:
            # Ensure we have a proper event loop
            ensure_event_loop()
            
            # Only pass message_history if it's a proper list of ModelMessage objects
            if message_history and len(message_history) > 0:
                result = await self.agent_womcp.run(
                    enhanced_query,
                    deps=deps,
                    message_history=message_history
                )
            else:
                result = await self.agent_womcp.run(enhanced_query, deps=deps)
            
            return result.output
            
        except Exception as e:
            if "event loop" in str(e).lower() or "bound to a different" in str(e).lower():
                logger.warning(f"Event loop issue detected in web response, creating fresh agent: {e}")
                # Reset any cached models and create fresh agent
                from src.agents_pa.shared.universal_providers import universal_provider
                universal_provider.clear_cache()
                
                # Create fresh web-only agent
                self.agent_womcp = Agent(
                    model=get_hlateacher_model(),
                    deps_type=HLATeacherDependencies,
                    system_prompt=HLA_TEACHER_PROMPTS.get("web_only_response", HLATEACHER_SYSTEM_PROMPT),
                    history_processors=[keep_recent_messages]
                )
                self.agent_womcp = create_web_only_tools(self.agent_womcp)
                
                # Try again with fresh agent
                if message_history and len(message_history) > 0:
                    result = await self.agent_womcp.run(
                        enhanced_query,
                        deps=deps,
                        message_history=message_history
                    )
                else:
                    result = await self.agent_womcp.run(enhanced_query, deps=deps)
                
                logger.info("Successfully created fresh web agent after event loop fix")
                return result.output
            else:
                raise
    
    async def _generate_web_stream(
        self, 
        query: str, 
        deps: HLATeacherDependencies,
        message_history: Optional[list[ModelMessage]] = None
    ):
        """Generate streaming response using web search only."""
        enhanced_query = f"Please search the web for information about: {query}. Focus on HLA, genetics, and biology topics. Provide a comprehensive educational answer with proper citations."
        
        try:
            # Ensure we have a proper event loop
            ensure_event_loop()
            
            # Use agent.run_stream with proper message history
            if message_history and len(message_history) > 0:
                return self.agent_womcp.run_stream(
                    enhanced_query,
                    deps=deps,
                    message_history=message_history
                )
            else:
                return self.agent_womcp.run_stream(enhanced_query, deps=deps)
                
        except Exception as e:
            if "event loop" in str(e).lower() or "bound to a different" in str(e).lower():
                logger.warning(f"Event loop issue detected in web stream, creating fresh agent: {e}")
                # Reset any cached models and create fresh agent
                from src.agents_pa.shared.universal_providers import universal_provider
                universal_provider.clear_cache()
                
                # Create fresh web-only agent
                self.agent_womcp = Agent(
                    model=get_hlateacher_model(),
                    deps_type=HLATeacherDependencies,
                    system_prompt=HLA_TEACHER_PROMPTS.get("web_only_response", HLATEACHER_SYSTEM_PROMPT),
                    history_processors=[keep_recent_messages]
                )
                self.agent_womcp = create_web_only_tools(self.agent_womcp)
                
                # Try again with fresh agent
                if message_history and len(message_history) > 0:
                    return self.agent_womcp.run_stream(
                        enhanced_query,
                        deps=deps,
                        message_history=message_history
                    )
                else:
                    return self.agent_womcp.run_stream(enhanced_query, deps=deps)
                    
                logger.info("Successfully created fresh web stream agent after event loop fix")
            else:
                raise
    
    async def _generate_rag_response(
        self, 
        query: str, 
        deps: HLATeacherDependencies,
        message_history: Optional[list] = None
    ) -> str:
        """Generate response using both web search and knowledge base (RAG)."""
        enhanced_query = f"Please search both web and knowledge base for information about: {query}. Use web search for current information and the knowledge base for detailed scientific papers. Provide a comprehensive educational answer combining both sources with proper citations."
        
        # Create fresh MCP-enhanced agent to prevent event loop issues
        try:
            if self.mcp_servers:
                fresh_agent = get_fresh_mcp_enhanced_agent(
                    self.mcp_servers, 
                    HLA_TEACHER_PROMPTS.get("mcp_enhanced_system", HLATEACHER_SYSTEM_PROMPT)
                )
            else:
                # Fallback to web-only agent if no MCP servers
                fresh_agent = self.agent_womcp
            
            # Only pass message_history if it's a proper list of ModelMessage objects
            if message_history and len(message_history) > 0:
                result = await fresh_agent.run(
                    enhanced_query,
                    deps=deps,
                    message_history=message_history
                )
            else:
                result = await fresh_agent.run(enhanced_query, deps=deps)
                
        except Exception as e:
            if "event loop" in str(e).lower() or "bound to a different" in str(e).lower():
                logger.warning(f"Event loop issue detected in RAG mode, creating fresh agent: {e}")
                # Reset any cached models and create fresh agent
                from src.agents_pa.shared.universal_providers import universal_provider
                universal_provider.clear_cache()
                
                if self.mcp_servers:
                    fresh_agent = get_fresh_mcp_enhanced_agent(
                        self.mcp_servers, 
                        HLA_TEACHER_PROMPTS.get("mcp_enhanced_system", HLATEACHER_SYSTEM_PROMPT)
                    )
                else:
                    # Fallback to web-only agent if no MCP servers
                    fresh_agent = self.agent_womcp
                
                # Only pass message_history if it's a proper list of ModelMessage objects
                if message_history and len(message_history) > 0:
                    result = await fresh_agent.run(
                        enhanced_query,
                        deps=deps,
                        message_history=message_history
                    )
                else:
                    result = await fresh_agent.run(enhanced_query, deps=deps)
                    
                logger.info("Successfully created fresh RAG agent after event loop fix")
            else:
                raise
        
        # Get the main response
        main_response = result.output
        
        # Extract document sources used in knowledge base search
        used_documents = await self._extract_used_documents(query, deps)
        
        # Append document citations if any were used
        if used_documents:
            citation_text = f"\n\n**📚 Documents used in this response:** {', '.join(used_documents)}"
            return main_response + citation_text

        return main_response
    
    async def _extract_used_documents(self, query: str, deps: HLATeacherDependencies) -> list:
        """
        Extract document sources that would be used for this query.
        
        Args:
            query: User query to search for
            deps: HLA Teacher dependencies
            
        Returns:
            List of document filenames used
        """
        try:
            if not deps.knowledge_manager or not deps.knowledge_manager.is_initialized():
                return []
            
            # Perform the same search that would be done during RAG
            results = await deps.knowledge_manager.search_async(
                query=query,
                limit=5  # Same limit as in the tool
            )
            
            # Extract unique document sources
            document_sources = set()
            for result in results:
                source = result.get('source', '')
                if source:
                    # Extract just the filename from the path
                    filename = os.path.basename(source) if source else ''
                    if filename:
                        document_sources.add(filename)
            
            return sorted(list(document_sources))
            
        except Exception as e:
            logger.error(f"Error extracting used documents: {e}")
            return []
    
    async def _generate_rag_stream(
        self, 
        query: str, 
        deps: HLATeacherDependencies,
        message_history: Optional[list[ModelMessage]] = None
    ):
        """Generate streaming response using both web search and knowledge base (RAG)."""
        enhanced_query = f"Please search both web and knowledge base for information about: {query}. Use web search for current information and the knowledge base for detailed scientific papers. Provide a comprehensive educational answer combining both sources with proper citations."
        
        # Create fresh MCP-enhanced agent to prevent event loop issues
        try:
            if self.mcp_servers:
                fresh_agent = get_fresh_mcp_enhanced_agent(
                    self.mcp_servers, 
                    HLA_TEACHER_PROMPTS.get("mcp_enhanced_system", HLATEACHER_SYSTEM_PROMPT)
                )
            else:
                # Fallback to web-only agent if no MCP servers
                fresh_agent = self.agent_womcp
            
            # Use fresh agent.run_stream with proper message history
            if message_history and len(message_history) > 0:
                return fresh_agent.run_stream(
                    enhanced_query,
                    deps=deps,
                    message_history=message_history
                )
            else:
                return fresh_agent.run_stream(enhanced_query, deps=deps)
                
        except Exception as e:
            if "event loop" in str(e).lower() or "bound to a different" in str(e).lower():
                logger.warning(f"Event loop issue detected in RAG stream mode, creating fresh agent: {e}")
                # Reset any cached models and create fresh agent
                from src.agents_pa.shared.universal_providers import universal_provider
                universal_provider.clear_cache()
                
                if self.mcp_servers:
                    fresh_agent = get_fresh_mcp_enhanced_agent(
                        self.mcp_servers, 
                        HLA_TEACHER_PROMPTS.get("mcp_enhanced_system", HLATEACHER_SYSTEM_PROMPT)
                    )
                else:
                    # Fallback to web-only agent if no MCP servers
                    fresh_agent = self.agent_womcp
                
                # Use fresh agent.run_stream with proper message history
                if message_history and len(message_history) > 0:
                    return fresh_agent.run_stream(
                        enhanced_query,
                        deps=deps,
                        message_history=message_history
                    )
                else:
                    return fresh_agent.run_stream(enhanced_query, deps=deps)
                    
                logger.info("Successfully created fresh RAG stream agent after event loop fix")
            else:
                raise
    
    async def _generate_mcp_response(
        self, 
        query: str, 
        deps: HLATeacherDependencies,
        message_history: Optional[list] = None
    ) -> str:
        """Generate response using MCP server tools."""
        if not self.mcp_servers:
            logger.warning("MCP mode requested but no MCP servers available, falling back to web search")
            return await self._generate_web_response(query, deps, message_history)
        
        enhanced_query = f"Please use available MCP tools to research and answer: {query}. Focus on providing comprehensive information about HLA, genetics, and biology topics with proper citations."
        
        # Create fresh MCP-enhanced agent to prevent event loop issues
        try:
            fresh_agent = get_fresh_mcp_enhanced_agent(
                self.mcp_servers, 
                HLA_TEACHER_PROMPTS.get("mcp_enhanced_system", HLATEACHER_SYSTEM_PROMPT)
            )
            
            # Only pass message_history if it's a proper list of ModelMessage objects
            if message_history and len(message_history) > 0:
                result = await fresh_agent.run(
                    enhanced_query,
                    deps=deps,
                    message_history=message_history
                )
            else:
                result = await fresh_agent.run(enhanced_query, deps=deps)
                
        except Exception as e:
            if "event loop" in str(e).lower() or "bound to a different" in str(e).lower():
                logger.warning(f"Event loop issue detected in MCP mode, creating fresh agent: {e}")
                # Reset any cached models and create fresh agent
                from src.agents_pa.shared.universal_providers import universal_provider
                universal_provider.clear_cache()
                
                fresh_agent = get_fresh_mcp_enhanced_agent(
                    self.mcp_servers, 
                    HLA_TEACHER_PROMPTS.get("mcp_enhanced_system", HLATEACHER_SYSTEM_PROMPT)
                )
                
                # Only pass message_history if it's a proper list of ModelMessage objects
                if message_history and len(message_history) > 0:
                    result = await fresh_agent.run(
                        enhanced_query,
                        deps=deps,
                        message_history=message_history
                    )
                else:
                    result = await fresh_agent.run(enhanced_query, deps=deps)
                    
                logger.info("Successfully created fresh MCP agent after event loop fix")
            else:
                raise
        
        return result.output
    
    async def _generate_mcp_stream(
        self, 
        query: str, 
        deps: HLATeacherDependencies,
        message_history: Optional[list[ModelMessage]] = None
    ):
        """Generate streaming response using MCP server tools."""
        if not self.mcp_servers:
            logger.warning("MCP mode requested but no MCP servers available, falling back to web search")
            return await self._generate_web_stream(query, deps, message_history)
        
        enhanced_query = f"Please use available MCP tools to research and answer: {query}. Focus on providing comprehensive information about HLA, genetics, and biology topics with proper citations."
        
        # Create fresh MCP-enhanced agent to prevent event loop issues
        try:
            fresh_agent = get_fresh_mcp_enhanced_agent(
                self.mcp_servers, 
                HLA_TEACHER_PROMPTS.get("mcp_enhanced_system", HLATEACHER_SYSTEM_PROMPT)
            )
            
            # Use fresh agent.run_stream with proper message history
            if message_history and len(message_history) > 0:
                return fresh_agent.run_stream(
                    enhanced_query,
                    deps=deps,
                    message_history=message_history
                )
            else:
                return fresh_agent.run_stream(enhanced_query, deps=deps)
                
        except Exception as e:
            if "event loop" in str(e).lower() or "bound to a different" in str(e).lower():
                logger.warning(f"Event loop issue detected in MCP stream mode, creating fresh agent: {e}")
                # Reset any cached models and create fresh agent
                from src.agents_pa.shared.universal_providers import universal_provider
                universal_provider.clear_cache()
                
                fresh_agent = get_fresh_mcp_enhanced_agent(
                    self.mcp_servers, 
                    HLA_TEACHER_PROMPTS.get("mcp_enhanced_system", HLATEACHER_SYSTEM_PROMPT)
                )
                
                # Use fresh agent.run_stream with proper message history
                if message_history and len(message_history) > 0:
                    return fresh_agent.run_stream(
                        enhanced_query,
                        deps=deps,
                        message_history=message_history
                    )
                else:
                    return fresh_agent.run_stream(enhanced_query, deps=deps)
                    
                logger.info("Successfully created fresh MCP stream agent after event loop fix")
            else:
                raise
    
    async def chat_loop(
        self, 
        deps: Optional[HLATeacherDependencies] = None,
        standalone: bool = True
    ) -> dict:
        """
        Interactive chat loop for direct interaction or supervisor delegation.
        
        Args:
            deps: Optional dependencies (will create default if not provided)
            standalone: Whether running in standalone mode
            
        Returns:
            Session completion information for supervisor integration
        """
        if deps is None:
            deps = HLATeacherDependencies.create_default()
        
        await self.initialize(deps)
        
        # Display welcome message based on context
        if standalone:
            print("\n=== HLA Teacher Agent (PydanticAI) ===")
            print("Ask me anything about HLA, genetics, and biology!")
            print("Type 'Done!' to exit.")
            print("Commands: '/web' (web search-only), '/rag' (RAG-enhanced), '/mcp' (MCP-enhanced)")
            print(f"Current mode: {deps.current_mode.name}\n")
        else:
            requester = deps.requester_agent or "supervisor"
            print(f"🎓 HLA Teacher: Hello! I'm the HLA Teacher agent, specialized in HLA, genetics, biology, and immunology topics.")
            print(f"📝 Available modes: Simply type '/web' (web search-only), '/rag' (knowledge base enhanced), or '/mcp' (MCP tools) to change modes.")
            print(f"Current mode: {deps.current_mode.name}")
            print(f"💬 Ask me anything about HLA, genetics, or biology. Type 'Done!' when finished to return to {requester}.\n")
        
        while True:
            try:
                user_input = input("To HLA Teacher: ").strip()
                
                # Handle exit command
                if user_input.lower() == "done!":
                    if standalone:
                        print("\nGoodbye!")
                    else:
                        requester = deps.requester_agent or "supervisor"
                        print(f"\nThank you for the great questions! Returning control to {requester}.")
                        print(f"🎯 {requester.title()}: Welcome back! What can I do for you now?")
                    break
                
                # Handle mode switching commands
                if user_input.lower() in ["/web", "/rag", "/mcp"]:
                    if user_input.lower() == "/web":
                        deps.set_mode(AgentMode.WEB_ONLY)
                        print(f"🎓 Switched to {AgentMode.WEB_ONLY.name} mode.")
                    elif user_input.lower() == "/rag":
                        deps.set_mode(AgentMode.RAG_ENHANCED)
                        print(f"🎓 Switched to {AgentMode.RAG_ENHANCED.name} mode.")
                    elif user_input.lower() == "/mcp":
                        if self.mcp_servers:
                            deps.set_mode(AgentMode.MCP_ENHANCED)
                            print(f"🎓 Switched to {AgentMode.MCP_ENHANCED.name} mode.")
                        else:
                            print("🎓 MCP servers not available. Staying in current mode.")
                    continue
                
                # Handle empty input
                if not user_input:
                    exit_text = "exit" if standalone else "type 'Done!' to return to supervisor"
                    print(f"🎓 Please ask a question about HLA, genetics, or biology, or {exit_text}.")
                    continue
                
                # Process the query with streaming
                print("🎓 Let me research that for you...")
                
                # Get message history for context
                message_history = getattr(deps, 'conversation_history', [])
                
                # Use streaming response with rich console
                with Live('', console=self.console, vertical_overflow='visible') as live:
                    async with await self.run_stream(user_input, deps, message_history) as result:
                        full_response = ""
                        async for text in result.stream(debounce_by=0.01):
                            full_response = text
                            live.update(Markdown(f"🎓 **HLA Teacher Response:**\n\n{text}"))
                
                # Add the final response to conversation history
                deps.add_conversation("assistant", full_response)
                print()  # Add newline for better formatting
                
            except KeyboardInterrupt:
                if standalone:
                    print("\n\nGoodbye!")
                else:
                    requester = deps.requester_agent or "supervisor"
                    print(f"\n\nSession interrupted. Returning to {requester}.")
                    print(f"🎯 {requester.title()}: What can I do for you now?")
                break
            except Exception as e:
                logger.error(f"Error in chat loop: {e}")
                print(f"🎓 I encountered an error: {e}\n")
        
        # Return session completion info for supervisor integration
        return {
            "status": "completed",
            "mode": deps.current_mode.value,
            "conversation_count": len(deps.conversation_history),
            "requester": deps.requester_agent,
            "session_id": deps.session_id,
            "is_standalone": standalone
        }
    
    def get_session_info(self, deps: HLATeacherDependencies) -> dict:
        """Get current session information for supervisor integration."""
        return deps.get_session_info()


# Global instance for easy import
hlateacher_agent_pa = HLATeacherAgentPA()


# Convenience functions for testing and integration
async def test_hlateacher_with_test_model():
    """Test HLATeacher agent with TestModel for development."""
    test_model = TestModel()
    
    # Create fresh agent for testing to prevent event loop issues
    fresh_agent = get_fresh_hlateacher_agent()
    
    # Override the agent's model with TestModel
    with fresh_agent.override(model=test_model):
        deps = HLATeacherDependencies.create_default()
        
        result = await fresh_agent.run(
            "What is HLA typing?",
            deps=deps
        )
        
        print(f"Test result: {result.output}")
        return result


async def test_hlateacher_streaming():
    """Test HLATeacher agent with streaming capabilities."""
    print("Testing HLA Teacher Streaming...")
    
    # Use the global agent instance
    agent_instance = hlateacher_agent_pa
    deps = HLATeacherDependencies.create_default()
    
    # Initialize the agent
    await agent_instance.initialize(deps)
    
    # Test query
    test_query = "What is HLA typing?"
    print(f"Testing query: {test_query}")
    
    try:
        # Test streaming
        console = Console()
        print("\n=== Streaming Response ===")
        with Live('', console=console, vertical_overflow='visible') as live:
            stream_result = await agent_instance.run_stream(test_query, deps)
            async with stream_result as result:
                full_response = ""
                async for text in result.stream(debounce_by=0.01):
                    full_response = text
                    live.update(Markdown(f"**HLA Teacher:**\n\n{text}"))
        
        print(f"\n=== Final Response ===\n{full_response}")
        
        # Test message history
        print(f"\nConversation history entries: {len(deps.conversation_history)}")
        
        return True
        
    except Exception as e:
        print(f"Error in streaming test: {e}")
        return False


if __name__ == "__main__":
    # Run standalone for testing
    async def main():
        # You can uncomment one of these to test different features:
        
        # Test streaming functionality
        # await test_hlateacher_streaming()
        
        # Run interactive chat loop with streaming
        deps = HLATeacherDependencies.create_default()
        await hlateacher_agent_pa.chat_loop(deps, standalone=True)
    
    asyncio.run(main())