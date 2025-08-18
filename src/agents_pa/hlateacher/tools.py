"""
PydanticAI tools for HLATeacher Agent.
Converts existing tools to use @agent.tool decorators with RunContext.
"""

import json
import os
import asyncio
from typing import Dict, Any, List, Optional
from pydantic_ai import RunContext
from tavily import TavilyClient
from pydantic_ai.mcp import MCPServerStdio

from .dependencies import HLATeacherDependencies
from src.agents.hlateacher.agent_types import AgentMode
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def create_hlateacher_tools(agent):
    """
    Create and register tools for HLATeacher agent.
    Returns the agent with tools registered.
    """
    
    @agent.tool
    async def web_search_tool(
        ctx: RunContext[HLATeacherDependencies], 
        query: str, 
        max_results: int = 3
    ) -> str:
        """
        Perform web search using Tavily API for HLA/genetics questions.
        
        Args:
            query: Search query for HLA/genetics topics
            max_results: Maximum number of results to return (default: 3)
            
        Returns:
            JSON string with search results
        """
        try:
            if not ctx.deps.tavily_api_key:
                logger.warning("Tavily API key not available for web search")
                return json.dumps({"error": "Web search not available - API key not configured"})
            
            logger.info(f"Performing web search for HLA query: {query}")
            
            client = TavilyClient(api_key=ctx.deps.tavily_api_key)
            response = client.search(
                query=f"HLA genetics biology {query}",  # Enhanced query for HLA focus
                max_results=max_results,
                include_answer=False
            )
            
            results = response.get('results', [])
            logger.info(f"Web search found {len(results)} results for HLA query")
            
            # Format results for educational use
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "title": result.get('title', ''),
                    "content": result.get('content', ''),
                    "url": result.get('url', ''),
                    "published_date": result.get('published_date', '')
                })
            
            return json.dumps(formatted_results, indent=2)
            
        except Exception as e:
            logger.error(f"Error in web search tool: {e}")
            return json.dumps({"error": f"Web search failed: {str(e)}"})
    
    @agent.tool
    async def knowledge_base_search_tool(
        ctx: RunContext[HLATeacherDependencies],
        query: str,
        limit: int = 5
    ) -> str:
        """
        Search ChromaDB knowledge base for HLA/genetics information.
        
        Args:
            query: Search query for knowledge base
            limit: Maximum number of results to return (default: 5)
            
        Returns:
            JSON string with knowledge base search results
        """
        try:
            if not ctx.deps.knowledge_manager.is_initialized():
                logger.warning("Knowledge base not initialized, attempting to initialize")
                await ctx.deps.knowledge_manager.initialize()
            
            if not ctx.deps.knowledge_manager.is_initialized():
                return json.dumps({"error": "Knowledge base not available"})
            
            logger.info(f"Searching knowledge base for: {query}")
            
            # Perform semantic search
            results = await ctx.deps.knowledge_manager.search_async(
                query=query,
                limit=limit
            )
            
            logger.info(f"Knowledge base search found {len(results)} results")
            
            # Format results for educational use
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "content": result.get('content', ''),
                    "source": result.get('source', ''),
                    "relevance_score": result.get('relevance_score', 0.0),
                    "metadata": result.get('metadata', {})
                })
            
            return json.dumps(formatted_results, indent=2)
            
        except Exception as e:
            logger.error(f"Error in knowledge base search: {e}")
            return json.dumps({"error": f"Knowledge base search failed: {str(e)}"})
    
    @agent.tool
    async def switch_mode_tool(
        ctx: RunContext[HLATeacherDependencies],
        mode: str
    ) -> str:
        """
        Switch HLATeacher agent operating mode.
        
        Args:
            mode: Operating mode ('web_only', 'rag_enhanced', or 'mcp_enhanced')
            
        Returns:
            Confirmation message
        """
        try:
            if mode.lower() == "web_only":
                ctx.deps.set_mode(AgentMode.WEB_ONLY)
                return "Switched to web-only mode. I'll use web search for your questions."
            elif mode.lower() == "rag_enhanced":
                ctx.deps.set_mode(AgentMode.RAG_ENHANCED)
                return "Switched to RAG-enhanced mode. I'll use both web search and knowledge base."
            elif mode.lower() == "mcp_enhanced":
                ctx.deps.set_mode(AgentMode.MCP_ENHANCED)
                return "Switched to MCP-enhanced mode. I'll use advanced MCP server tools."
            else:
                return f"Unknown mode: {mode}. Available modes: web_only, rag_enhanced, mcp_enhanced"
        except Exception as e:
            logger.error(f"Error switching mode: {e}")
            return f"Error switching mode: {str(e)}"
    
    @agent.tool
    async def get_session_info_tool(
        ctx: RunContext[HLATeacherDependencies]
    ) -> str:
        """
        Get current session information for debugging and supervisor integration.
        
        Returns:
            JSON string with current session information
        """
        try:
            session_info = ctx.deps.get_session_info()
            return json.dumps(session_info, indent=2)
        except Exception as e:
            logger.error(f"Error getting session info: {e}")
            return json.dumps({"error": f"Could not get session info: {str(e)}"})
    
    @agent.tool
    async def initialize_knowledge_base_tool(
        ctx: RunContext[HLATeacherDependencies],
        articles_path: Optional[str] = None
    ) -> str:
        """
        Initialize or refresh the ChromaDB knowledge base with articles.
        
        Args:
            articles_path: Optional path to articles directory
            
        Returns:
            Status message
        """
        try:
            if articles_path is None:
                articles_path = os.path.join(os.getcwd(), "data/knowledge/Articles")
            
            logger.info(f"Initializing knowledge base from: {articles_path}")
            
            # Initialize the knowledge manager
            await ctx.deps.knowledge_manager.initialize()
            
            # Process articles if directory exists
            if os.path.exists(articles_path):
                processed_count = await ctx.deps.knowledge_manager.process_articles_directory(articles_path)
                return f"Knowledge base initialized successfully. Processed {processed_count} articles."
            else:
                return f"Knowledge base initialized, but articles directory not found at: {articles_path}"
                
        except Exception as e:
            logger.error(f"Error initializing knowledge base: {e}")
            return f"Error initializing knowledge base: {str(e)}"
    
    return agent


def create_web_only_tools(agent):
    """
    Create and register only web search tool for web-only mode agent.
    Returns the agent with only tavily web search tool registered.
    """
    
    @agent.tool
    async def web_search_tool(
        ctx: RunContext[HLATeacherDependencies], 
        query: str, 
        max_results: int = 3
    ) -> str:
        """
        Perform web search using Tavily API for HLA/genetics questions.
        
        Args:
            query: Search query for HLA/genetics topics
            max_results: Maximum number of results to return (default: 3)
            
        Returns:
            JSON string with search results
        """
        try:
            if not ctx.deps.tavily_api_key:
                logger.warning("Tavily API key not available for web search")
                return json.dumps({"error": "Web search not available - API key not configured"})
            
            logger.info(f"Performing web search for HLA query: {query}")
            
            client = TavilyClient(api_key=ctx.deps.tavily_api_key)
            response = client.search(
                query=f"HLA genetics biology {query}",  # Enhanced query for HLA focus
                max_results=max_results,
                include_answer=False
            )
            
            results = response.get('results', [])
            logger.info(f"Web search found {len(results)} results for HLA query")
            
            # Format results for educational use
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "title": result.get('title', ''),
                    "content": result.get('content', ''),
                    "url": result.get('url', ''),
                    "published_date": result.get('published_date', '')
                })
            
            return json.dumps(formatted_results, indent=2)
            
        except Exception as e:
            logger.error(f"Error in web search tool: {e}")
            return json.dumps({"error": f"Web search failed: {str(e)}"})
    
    return agent


def create_mcp_servers(mcp_servers_config: Dict[str, Any]) -> List[MCPServerStdio]:
    """
    Create MCP server instances from configuration.
    
    Args:
        mcp_servers_config: Dictionary of MCP server configurations
        
    Returns:
        List of configured MCP server instances
    """
    servers = []
    
    for server_name, config in mcp_servers_config.items():
        try:
            if config.get("command") and config.get("args"):
                server = MCPServerStdio(
                    command=config["command"],
                    args=config["args"],
                    env=config.get("env", {})
                )
                servers.append(server)
                logger.info(f"Created MCP server: {server_name}")
            else:
                logger.warning(f"Invalid MCP server config for {server_name}")
        except Exception as e:
            logger.error(f"Error creating MCP server {server_name}: {e}")
    
    return servers