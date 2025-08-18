"""
Pydantic models for HLATeacher Agent structured outputs.
Following PRP guidelines to use string output by default.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

# Re-export agent types for convenience
from src.agents.hlateacher.agent_types import (
    AgentMode,
    ResponseStatus, 
    HLATopic,
    KnowledgeLevel
)


class HLAResponse(BaseModel):
    """
    Structured response model for HLA educational content.
    Used only when structured output validation is specifically needed.
    """
    answer: str = Field(description="Educational answer about HLA/genetics topic")
    topic: Optional[HLATopic] = Field(None, description="Identified HLA topic category")
    knowledge_level: Optional[KnowledgeLevel] = Field(None, description="Recommended knowledge level")
    sources: List[str] = Field(default_factory=list, description="List of source URLs or documents")
    key_concepts: List[str] = Field(default_factory=list, description="Key concepts covered")
    further_reading: List[str] = Field(default_factory=list, description="Recommended further reading")


class SearchResultModel(BaseModel):
    """Model for individual search results."""
    title: str = Field(description="Result title")
    content: str = Field(description="Result content/snippet")
    source: str = Field(description="Source name or URL")
    relevance_score: Optional[float] = Field(None, description="Relevance score if available")


class KnowledgeBaseResult(BaseModel):
    """Model for knowledge base search results."""
    content: str = Field(description="Document content snippet")
    source: str = Field(description="Document source file")
    distance: float = Field(description="Semantic distance score")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")


class AgentModeSwitch(BaseModel):
    """Model for mode switching responses."""
    old_mode: AgentMode = Field(description="Previous agent mode")
    new_mode: AgentMode = Field(description="New agent mode") 
    success: bool = Field(description="Whether mode switch was successful")
    message: str = Field(description="Status message")


class SessionInfo(BaseModel):
    """Model for session information."""
    session_id: Optional[str] = Field(None, description="Session identifier")
    requester_agent: Optional[str] = Field(None, description="Requesting agent name")
    task_id: Optional[str] = Field(None, description="Task identifier")
    current_mode: AgentMode = Field(description="Current operating mode")
    conversation_count: int = Field(description="Number of conversation exchanges")
    is_standalone: bool = Field(description="Whether running in standalone mode")


class HLAEducationalContent(BaseModel):
    """Model for structured educational content about HLA topics."""
    topic: HLATopic = Field(description="HLA topic covered")
    content: str = Field(description="Educational content")
    level: KnowledgeLevel = Field(description="Complexity level")
    prerequisites: List[str] = Field(default_factory=list, description="Required background knowledge")
    learning_objectives: List[str] = Field(default_factory=list, description="Learning objectives")
    examples: List[str] = Field(default_factory=list, description="Practical examples")
    quiz_questions: List[str] = Field(default_factory=list, description="Self-assessment questions")


class ToolResult(BaseModel):
    """Generic model for tool execution results."""
    tool_name: str = Field(description="Name of the tool executed")
    success: bool = Field(description="Whether tool execution was successful")
    result: Any = Field(description="Tool execution result")
    error_message: Optional[str] = Field(None, description="Error message if execution failed")
    execution_time: Optional[float] = Field(None, description="Execution time in seconds")


class MCPServerStatus(BaseModel):
    """Model for MCP server status information."""
    server_name: str = Field(description="MCP server name")
    status: str = Field(description="Server status (active, inactive, error)")
    tools_available: List[str] = Field(default_factory=list, description="Available tools")
    last_used: Optional[str] = Field(None, description="Last usage timestamp")

