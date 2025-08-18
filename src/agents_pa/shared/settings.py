"""
Configuration management for HLAgent multi-agent system using pydantic-settings.
Based on main_agent_reference/settings.py and examples/imsi.py patterns.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, ConfigDict
from dotenv import load_dotenv


load_dotenv()


class Settings(BaseSettings):
    """Application settings with environment variable support for HLAgent multi-agent system."""
    
    model_config = ConfigDict(
        env_file=os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"), ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Universal LLM Provider Configuration
    default_llm_provider: str = Field(default=os.getenv("DEFAULT_LLM_PROVIDER", "ollama"), description="Default LLM provider")
    default_llm_model: str = Field(default=os.getenv("DEFAULT_LLM_MODEL", "mistral:7b"), description="Default LLM model")
    default_llm_base_url: Optional[str] = Field(default=os.getenv("DEFAULT_LLM_BASE_URL"), description="Default LLM base URL")
    default_llm_temperature: float = Field(default=float(os.getenv("DEFAULT_LLM_TEMPERATURE", "0.2")), description="Default LLM temperature")
    default_max_tokens: Optional[int] = Field(default=int(os.getenv("DEFAULT_MAX_TOKENS")) if os.getenv("DEFAULT_MAX_TOKENS") else None, description="Default max tokens")
    default_timeout: Optional[int] = Field(default=int(os.getenv("DEFAULT_TIMEOUT")) if os.getenv("DEFAULT_TIMEOUT") else None, description="Default timeout")
    default_max_retries: int = Field(default=int(os.getenv("DEFAULT_MAX_RETRIES", "2")), description="Default max retries")
    
    # Provider-specific Configuration
    # Ollama
    ollama_base_url: str = Field(default=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"), description="Ollama API base URL")
    ollama_model: str = Field(default=os.getenv("OLLAMA_LLM_MODEL", "mistral:7b"), description="Ollama local LLM model")
    
    # OpenAI
    openai_api_key: Optional[str] = Field(default=os.getenv("OPENAI_API_KEY"), description="OpenAI API key")
    openai_model: str = Field(default=os.getenv("OPENAI_LLM_MODEL", "gpt-4o"), description="OpenAI model")
    
    # Anthropic
    anthropic_api_key: Optional[str] = Field(default=os.getenv("ANTHROPIC_API_KEY"), description="Anthropic API key")
    anthropic_model: str = Field(default=os.getenv("ANTHROPIC_LLM_MODEL", "claude-3-5-sonnet-latest"), description="Anthropic model")
    
    # Google/Gemini
    google_api_key: Optional[str] = Field(default=os.getenv("GOOGLE_API_KEY"), description="Google API key")
    google_model: str = Field(default=os.getenv("GOOGLE_LLM_MODEL", "gemini-2.0-flash"), description="Google/Gemini model")
    
    # Groq
    groq_api_key: Optional[str] = Field(default=os.getenv("GROQ_API_KEY"), description="Groq API key")
    groq_model: str = Field(default=os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile"), description="Groq model")
    
    # HuggingFace
    huggingface_token: Optional[str] = Field(default=os.getenv("HUGGINGFACE_TOKEN"), description="HuggingFace token (alternative)")
    huggingface_model: str = Field(default=os.getenv("HUGGINGFACE_LLM_MODEL", "Qwen/Qwen3-235B-A22B"), description="HuggingFace model")
    
    # VertexAI
    vertex_api_key: Optional[str] = Field(default=os.getenv("VERTEX_API_KEY"), description="Vertex AI API key")
    vertex_model: str = Field(default=os.getenv("VERTEX_LLM_MODEL", "gemini-2.0-flash"), description="Vertex AI model")
    
    # External Service Configuration
    tavily_api_key: str = Field(..., description="Tavily API key for web search")
    
    # ChromaDB Configuration
    chroma_db_path: str = Field(
        default=os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"), "data/chroma/hla_knowledge_pa"), 
        description="Path to ChromaDB database"
    )
    knowledge_articles_path: str = Field(
        default=os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"), "data/knowledge/Articles"),
        description="Path to knowledge articles for RAG"
    )
    
    # MCP Configuration
    mcp_config_path: str = Field(
        default=os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"), "config/mcp_config_HLAgent.json"),
        description="Path to MCP server configuration"
    )
    
    # Application Configuration
    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")
    debug: bool = Field(default=False)
    
    # Multi-Agent Configuration
    supervisor_system_prompt: str = Field(
        default="You are a supervisor agent that orchestrates conversations and delegates tasks to specialized sub-agents. When users ask about HLA, genetics, or biology topics, delegate to the hlateacher agent.",
        description="System prompt for supervisor agent"
    )
    
    @field_validator("tavily_api_key")
    @classmethod
    def validate_required_api_keys(cls, v):
        """Ensure required API keys are not empty."""
        if not v or v.strip() == "":
            raise ValueError("Required API key cannot be empty")
        return v
    
    @field_validator("ollama_base_url")
    @classmethod
    def validate_ollama_url(cls, v):
        """Ensure Ollama base URL is properly formatted."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("Ollama base URL must start with http:// or https://")
        # Ensure URL ends with /v1 for OpenAI compatibility
        v = v.rstrip("/")
        if not v.endswith("/v1"):
            v += "/v1"
        return v


def load_settings() -> Settings:
    """Load settings with proper error handling and environment loading."""
    # Load environment variables from .env file
    load_dotenv()
    
    try:
        return Settings()
    except Exception as e:
        error_msg = f"Failed to load settings: {e}"
        if "tavily_api_key" in str(e).lower():
            error_msg += "\nMake sure to set TAVILY_API_KEY in your .env file"
        raise ValueError(error_msg) from e


# Global settings instance
try:
    settings = load_settings()
except Exception:
    # For testing, create settings with dummy values if needed
    import os
    os.environ.setdefault("TAVILY_API_KEY", "test_key")
    settings = Settings()