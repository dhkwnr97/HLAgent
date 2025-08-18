"""
Dependencies for HLATeacher Agent in PydanticAI multi-agent system.
Defines dataclass dependencies for dependency injection.
"""

import json
import os
from dataclasses import dataclass
from typing import Optional, Dict, Any
from pathlib import Path

# Import existing tools and managers
from src.agents.hlateacher.chroma_knowledge_manager import ChromaKnowledgeManager
from src.agents.hlateacher.agent_types import AgentMode
from src.agents_pa.shared.settings import settings


@dataclass
class HLATeacherDependencies:
    """
    Dependencies for HLATeacher agent following PydanticAI patterns.
    Based on existing hlateacher agent structure with PydanticAI integration.
    """
    
    # External API Keys
    tavily_api_key: str
    
    # Knowledge Management
    knowledge_manager: ChromaKnowledgeManager
    chroma_db_path: str
    
    # Session Management  
    session_id: Optional[str] = None
    requester_agent: Optional[str] = None
    task_id: Optional[str] = None
    
    # Agent Configuration
    current_mode: AgentMode = AgentMode.WEB_ONLY
    conversation_history: list = None
    
    # MCP Configuration
    mcp_config_path: str = None
    mcp_servers: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Initialize conversation history if not provided."""
        if self.conversation_history is None:
            self.conversation_history = []
    
    @classmethod
    def create_default(
        cls, 
        session_id: Optional[str] = None,
        requester_agent: Optional[str] = None,
        task_id: Optional[str] = None
    ) -> "HLATeacherDependencies":
        """
        Create default dependencies using shared settings.
        
        Args:
            session_id: Optional session identifier
            requester_agent: Optional name of agent making the request
            task_id: Optional task identifier
            
        Returns:
            Configured HLATeacherDependencies instance
        """
        # Initialize ChromaDB knowledge manager
        knowledge_manager = ChromaKnowledgeManager(
            db_path=os.path.join(os.getcwd(), settings.chroma_db_path)
        )
        
        # Load MCP configuration if available
        mcp_servers = None
        mcp_config_path = os.path.join(os.getcwd(), settings.mcp_config_path)
        if os.path.exists(mcp_config_path):
            try:
                with open(mcp_config_path, 'r') as f:
                    mcp_config = json.load(f)
                    mcp_servers = mcp_config.get('mcpServers', {})
            except Exception as e:
                print(f"Warning: Could not load MCP config: {e}")
        
        return cls(
            tavily_api_key=settings.tavily_api_key,
            knowledge_manager=knowledge_manager,
            chroma_db_path=settings.chroma_db_path,
            session_id=session_id,
            requester_agent=requester_agent,
            task_id=task_id,
            current_mode=AgentMode.WEB_ONLY,
            conversation_history=[],
            mcp_config_path=mcp_config_path,
            mcp_servers=mcp_servers
        )
    
    def is_standalone(self) -> bool:
        """Check if running in standalone mode (not delegated from supervisor)."""
        return self.requester_agent is None
    
    def add_conversation(self, role: str, content: str):
        """Add conversation entry to history."""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "mode": self.current_mode.value,
            "timestamp": str(len(self.conversation_history))
        })
    
    def set_mode(self, mode: AgentMode):
        """Update current operating mode."""
        self.current_mode = mode
    
    def get_session_info(self) -> Dict[str, Any]:
        """Get session information for supervisor integration."""
        return {
            "session_id": self.session_id,
            "requester_agent": self.requester_agent,
            "task_id": self.task_id,
            "current_mode": self.current_mode.value,
            "conversation_count": len(self.conversation_history),
            "is_standalone": self.is_standalone()
        }