"""
Pydantic models for Supervisor Agent structured outputs.
Following PRP guidelines to use string output by default.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class DelegationStatus(Enum):
    """Status of agent delegation."""
    IDLE = "idle"
    ANALYZING = "analyzing"
    DELEGATING = "delegating"
    ACTIVE = "active"
    COMPLETING = "completing"
    COMPLETED = "completed"
    ERROR = "error"


class AgentType(Enum):
    """Types of available agents."""
    SUPERVISOR = "supervisor"
    HLATEACHER = "hlateacher"
    # Extensible for future agents


class DelegationDecision(BaseModel):
    """Model for delegation decision analysis."""
    should_delegate: bool = Field(description="Whether query should be delegated")
    target_agent: Optional[str] = Field(None, description="Target agent for delegation")
    confidence: float = Field(description="Confidence score (0.0-1.0)")
    reasoning: str = Field(description="Explanation of the decision")
    query_category: Optional[str] = Field(None, description="Categorized query type")


class AgentCapability(BaseModel):
    """Model for agent capability description."""
    agent_name: str = Field(description="Name of the agent")
    description: str = Field(description="Agent description")
    capabilities: List[str] = Field(description="List of agent capabilities")
    modes: List[str] = Field(default_factory=list, description="Available operating modes")
    status: str = Field(default="available", description="Current agent status")


class DelegationResult(BaseModel):
    """Model for delegation execution results."""
    target_agent: str = Field(description="Agent that handled the request")
    success: bool = Field(description="Whether delegation was successful")
    response: str = Field(description="Response from delegated agent")
    execution_time: Optional[float] = Field(None, description="Execution time in seconds")
    error_message: Optional[str] = Field(None, description="Error message if failed")


class ConversationEntry(BaseModel):
    """Model for conversation history entries."""
    role: str = Field(description="Role (user, assistant)")
    content: str = Field(description="Message content")
    agent_source: str = Field(description="Agent that generated the message")
    timestamp: int = Field(description="Entry timestamp/index")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class SessionSummary(BaseModel):
    """Model for session summary information."""
    session_id: Optional[str] = Field(None, description="Session identifier")
    total_exchanges: int = Field(description="Total conversation exchanges")
    delegations_count: int = Field(description="Number of delegations made")
    agents_involved: List[str] = Field(description="List of agents involved")
    primary_topics: List[str] = Field(default_factory=list, description="Main topics discussed")
    session_duration: Optional[float] = Field(None, description="Session duration in seconds")
    success_rate: float = Field(description="Success rate of operations")


class A2AContext(BaseModel):
    """Model for A2A protocol context."""
    context_id: str = Field(description="A2A context identifier")
    external_agent: Optional[str] = Field(None, description="External agent identifier")
    protocol_version: str = Field(default="1.0", description="A2A protocol version")
    session_data: Dict[str, Any] = Field(default_factory=dict, description="Session data")
    active: bool = Field(default=True, description="Whether A2A session is active")


class SupervisorStatus(BaseModel):
    """Model for supervisor agent status."""
    status: str = Field(description="Current supervisor status")
    active_delegations: int = Field(description="Number of active delegations")
    available_agents: List[str] = Field(description="List of available sub-agents")
    current_context: str = Field(description="Current context/mode")
    session_active: bool = Field(description="Whether session is active")
    last_activity: Optional[str] = Field(None, description="Last activity timestamp")


class QueryAnalysis(BaseModel):
    """Model for user query analysis."""
    original_query: str = Field(description="Original user query")
    intent: str = Field(description="Detected user intent")
    domain: str = Field(description="Query domain (general, hla, genetics, etc.)")
    complexity: str = Field(description="Query complexity (simple, moderate, complex)")
    keywords: List[str] = Field(description="Extracted keywords")
    requires_specialist: bool = Field(description="Whether specialist knowledge is required")
    suggested_agent: Optional[str] = Field(None, description="Suggested specialist agent")


class HandoffContext(BaseModel):
    """Model for agent handoff context."""
    from_agent: str = Field(description="Source agent")
    to_agent: str = Field(description="Target agent")
    handoff_reason: str = Field(description="Reason for handoff")
    context_data: Dict[str, Any] = Field(description="Context data to preserve")
    conversation_summary: str = Field(description="Summary of conversation so far")
    user_intent: str = Field(description="User's intent/goal")


# Following PRP guidelines: These models are available for structured output when needed
# Default behavior uses string output for better compatibility and simpler implementation