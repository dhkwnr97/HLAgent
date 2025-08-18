import os
import asyncio
from src.core.llm_config import get_llm
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv

from .agent_types import AgentMode
from .prompts import HLA_TEACHER_PROMPTS
from .tools import WebSearchTools, KnowledgeSearchTools
from .chroma_knowledge_manager import ChromaKnowledgeManager
from .states import HLATeacherStateManager
from src.utils.logger import setup_logger

from mcp_use import MCPAgent, MCPClient

logger = setup_logger(__name__)
load_dotenv()

class HLATeacherAgent:
    """Interactive HLA teacher agent with ChatOllama for continuous Q&A until 'Done!' is received."""

    def __init__(self):
        self.llm = get_llm(temperature=0.7)
        self.system_prompt = HLA_TEACHER_PROMPTS["system"]
        
        # Initialize tools and knowledge manager
        self.db_path = os.path.join(
            os.getenv("HLAGENT_MAIN_DIRECTORY", "."), "data/chroma/hla_knowledge"
        )
        self.web_search_tools = WebSearchTools()
        self.knowledge_manager = ChromaKnowledgeManager(db_path=self.db_path)
        self.knowledge_search_tools = KnowledgeSearchTools(self.knowledge_manager)
        self._initialized = False
        
        # Initialize MCP components
        self.mcp_client = None
        self.mcp_agent = None
        
        # Initialize state manager
        self.state_manager = HLATeacherStateManager()

    async def initialize(self):
        """Initialize agent components."""
        if self._initialized:
            return
        logger.info("Initializing agent components...")
        await self.knowledge_manager.initialize()
        
        # Initialize MCP client and agent
        await self._initialize_mcp()
        
        self._initialized = True
        logger.info("HLATeacherAgent initialized successfully.")
        
    async def _initialize_mcp(self):
        """Initialize MCP client and agent."""
        try:
            # Create MCP client from config file
            self.mcp_client = MCPClient.from_config_file(
                os.path.join(
                    os.getenv("HLAGENT_MAIN_DIRECTORY", "."), "config/mcp_config_HLAgent.json"
                )
            )
            
            # Create MCP agent with the LLM and client
            # Use MCP-specific system prompt for enhanced capabilities
            mcp_system_prompt = HLA_TEACHER_PROMPTS.get("mcp_enhanced_system", self.system_prompt)
            self.mcp_agent = MCPAgent(
                llm=self.llm,
                client=self.mcp_client,
                max_steps=30,
                system_prompt=mcp_system_prompt,
                use_server_manager=True
            )
            
            # Initialize the MCP agent
            await self.mcp_agent.initialize()
            logger.info("MCP agent initialized successfully.")
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP agent: {e}")
            # Continue without MCP if initialization fails
            self.mcp_client = None
            self.mcp_agent = None

    async def chat_loop(self, mode: AgentMode = AgentMode.WEB_ONLY, requester_agent: str = "", task_id: str = ""):
        """Interactive chat loop until user types 'Done!'."""
        await self.initialize()
        
        # Initialize session with supervisor support
        self.state_manager.initialize_session(requester_agent, task_id, mode)
        
        # Display different welcome messages based on mode
        if self.state_manager.is_standalone():
            print("\n=== HLA Teacher Agent ===")
            print("Ask me anything about HLA, genetics, and biology!")
            print("Type 'Done!' to exit.")
            print("Type 'web' for web-only mode, 'rag' for RAG-enhanced mode, or 'mcp' for MCP-enhanced mode.")
            print(f"Current mode: {mode.name}\n")
        else:
            print(f"\n=== HLA Teacher Agent (via {requester_agent}) ===")
            print("Ask me anything about HLA, genetics, and biology!")
            print("Type 'Done!' to return to supervisor.")
            print("Type 'web' for web-only mode, 'rag' for RAG-enhanced mode, or 'mcp' for MCP-enhanced mode.")
            print(f"Current mode: {mode.name}\n")
        
        while True:
            try:
                user_input = input("To HLA Teacher Agent: ").strip()
                
                if user_input.lower() == "done!":
                    if self.state_manager.is_standalone():
                        print("\nAgent: Finish hla teacher agent. Goodbye! ")
                    else:
                        print(f"\nAgent: Returning to {self.state_manager.get_requester()}. Goodbye! ")
                    self.state_manager.end_session()
                    break
                    
                if user_input.lower() == "web":
                    mode = AgentMode.WEB_ONLY
                    self.state_manager.set_mode(mode)
                    print(f"Agent: Switched to {mode.name} mode.")
                    continue
                    
                if user_input.lower() == "rag":
                    mode = AgentMode.RAG_ENHANCED
                    self.state_manager.set_mode(mode)
                    print(f"Agent: Switched to {mode.name} mode.")
                    continue
                    
                if user_input.lower() == "mcp":
                    if self.mcp_agent:
                        mode = AgentMode.MCP_ENHANCED
                        self.state_manager.set_mode(mode)
                        print(f"Agent: Switched to {mode.name} mode.")
                    else:
                        print("Agent: MCP agent not available. Using web-only mode.")
                    continue
                    
                if not user_input:
                    print("Agent: Please ask a question or type 'Done!' to exit.")
                    continue
                    
                print("Agent: Let me search for information...")
                self.state_manager.set_current_query(user_input)
                self.state_manager.add_conversation("user", user_input)
                
                response = await self.run(user_input, self.state_manager.get_mode())
                print(f"Agent: {response}\n")
                
                self.state_manager.add_conversation("assistant", response)
                
            except KeyboardInterrupt:
                print("\n\nAgent: Goodbye! Happy learning!")
                break
            except Exception as e:
                logger.error(f"Error in chat loop: {e}")
                print(f"Agent: Sorry, I encountered an error: {e}\n")
        
        # Return session result
        return {
            "status": "completed",
            "mode": self.state_manager.get_mode().value,
            "conversation_count": len(self.state_manager.state.conversation_history),
            "requester": self.state_manager.get_requester(),
            "session_id": self.state_manager.state.task_id
        }

    async def run(self, query: str, mode: AgentMode = AgentMode.WEB_ONLY) -> str:
        """Process a single query and return response."""
        if not self._initialized:
            await self.initialize()

        logger.info(f"Processing query in {mode.name} mode: '{query}'")
        
        try:
            if mode == AgentMode.WEB_ONLY:
                return await self._generate_web_only_response(query)
            elif mode == AgentMode.RAG_ENHANCED:
                return await self._generate_rag_enhanced_response(query)
            elif mode == AgentMode.MCP_ENHANCED:
                return await self._generate_mcp_enhanced_response(query)
            else:
                return f"Unsupported mode: {mode}"
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return f"Sorry, I encountered an error while processing your question: {e}"

    async def _generate_web_only_response(self, query: str) -> str:
        """Generate response using web search only."""
        web_data_str = await self.web_search_tools.search_web(query)
        
        prompt_template = HLA_TEACHER_PROMPTS["web_only_response"]
        formatted_prompt = prompt_template.format(
            query=query,
            web_context=web_data_str
        )
        
        return await self._generate_llm_response(formatted_prompt)

    async def _generate_rag_enhanced_response(self, query: str) -> str:
        """Generate response using both web and knowledge base search."""
        web_search_task = self.web_search_tools.search_web(query)
        kb_search_task = self.knowledge_search_tools.search_knowledge_base(query)
        
        web_data_str, kb_data_str = await asyncio.gather(web_search_task, kb_search_task)
        
        prompt_template = HLA_TEACHER_PROMPTS["rag_enhanced_response"]
        formatted_prompt = prompt_template.format(
            query=query,
            web_context=web_data_str,
            kb_context=kb_data_str
        )
        
        return await self._generate_llm_response(formatted_prompt)
    
    async def _generate_mcp_enhanced_response(self, query: str) -> str:
        """Generate response using MCP server tools."""
        if not self.mcp_agent:
            logger.warning("MCP agent not initialized, falling back to web-only mode")
            return await self._generate_web_only_response(query)
        
        try:
            # Use MCP agent to process the query
            result = await self.mcp_agent.run(query)
            return result
        except Exception as e:
            logger.error(f"Error in MCP enhanced response: {e}")
            # Fallback to web-only mode if MCP fails
            return await self._generate_web_only_response(query)

    async def _generate_llm_response(self, formatted_prompt: str) -> str:
        """Generate response from LLM."""
        try:
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=formatted_prompt)
            ]
            response = await self.llm.ainvoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            return "Sorry, I couldn't generate a response right now."
    
    async def cleanup(self):
        """Clean up resources."""
        try:
            if self.mcp_agent:
                await self.mcp_agent.close()
            if self.mcp_client:
                await self.mcp_client.close_all_sessions()
            logger.info("Resources cleaned up successfully.")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def get_session_info(self) -> dict:
        """Get current session information for supervisor integration."""
        return self.state_manager.get_state_info()

