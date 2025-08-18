"""
Type definitions for HLA Teacher Agent.

Defines enums and data structures used throughout the HLA Teacher Agent system.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


class AgentMode(Enum):
    """Operating modes for the HLA Teacher Agent."""
    WEB_ONLY = "web_only"              # Default mode: Use Tavily web search.
    RAG_ENHANCED = "rag_enhanced"      # Enhanced mode: Use web search + RAG from ChromaDB.
    MCP_ENHANCED = "mcp_enhanced"      # MCP mode: Use MCP server tools for enhanced capabilities.


class ResponseStatus(Enum):
    """Status of agent responses."""
    SUCCESS = "success"
    ERROR = "error"
    NO_RESULTS = "no_results"
    UNAVAILABLE = "unavailable"


@dataclass
class SearchResult:
    """Structure for search results."""
    title: str
    content: str
    source: str
    url: Optional[str] = None
    score: float = 0.0
    published_date: Optional[str] = None


@dataclass
class AgentResponse:
    """Structure for agent responses."""
    response: str
    tool_used: str
    query: str
    status: ResponseStatus = ResponseStatus.SUCCESS
    sources: List[SearchResult] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = None


@dataclass
class HLAQuery:
    """Structure for HLA-related queries."""
    text: str
    mode: AgentMode = AgentMode.WEB_ONLY
    context: Dict[str, Any] = None
    user_level: str = "intermediate"  # beginner, intermediate, advanced


class HLATopic(Enum):
    """Common HLA genetics topics."""
    HLA_BASICS = "hla_basics"
    HLA_TYPING = "hla_typing"
    HLA_IMPUTATION = "hla_imputation"
    DISEASE_ASSOCIATION = "disease_association"
    POPULATION_GENETICS = "population_genetics"
    TRANSPLANT_IMMUNOLOGY = "transplant_immunology"
    AUTOIMMUNE_DISEASES = "autoimmune_diseases"
    BIOINFORMATICS = "bioinformatics"
    MHC_BIOLOGY = "mhc_biology"


class KnowledgeLevel(Enum):
    """User knowledge levels for educational content."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


@dataclass
class EducationalContent:
    """Structure for educational content."""
    topic: HLATopic
    level: KnowledgeLevel
    content: str
    prerequisites: List[str] = None
    learning_objectives: List[str] = None
    further_reading: List[str] = None
    examples: List[str] = None


@dataclass
class KnowledgeBaseStats:
    """Structure for knowledge base statistics."""
    total_documents: int
    unique_sources: int
    file_types: Dict[str, int]
    last_updated: Optional[str] = None
    status: str = "unknown"


class FileType(Enum):
    """Supported file types for knowledge base."""
    PDF = ".pdf"
    MARKDOWN = ".md"
    TEXT = ".txt"
    DOCX = ".docx"


@dataclass
class DocumentMetadata:
    """Metadata for knowledge base documents."""
    file_path: str
    file_type: str
    title: str
    file_size: int
    last_modified: float
    chunk_index: Optional[int] = None
    chunk_count: Optional[int] = None


class SearchType(Enum):
    """Types of searches supported."""
    SEMANTIC = "semantic"      # Vector-based semantic search
    KEYWORD = "keyword"        # Keyword-based search
    HYBRID = "hybrid"          # Combination of semantic and keyword