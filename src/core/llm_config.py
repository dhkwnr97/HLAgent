"""
LLM Configuration Module

Centralized LLM configuration that reads from .env file.
All agents should use get_llm() function to get their LLM instance.
"""

import os
from typing import Optional
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama

# Load environment variables
load_dotenv()


def get_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    **kwargs
):
    """
    Get LLM instance based on .env configuration.
    
    Args:
        provider: Override DEFAULT_LLM_PROVIDER from .env
        model: Override specific model from .env
        temperature: Override DEFAULT_LLM_TEMPERATURE from .env
        **kwargs: Additional LLM parameters
        
    Returns:
        Configured LLM instance
    """
    # Get configuration from .env with defaults
    provider = provider or os.getenv("DEFAULT_LLM_PROVIDER", "ollama").lower()
    temperature = temperature or float(os.getenv("DEFAULT_LLM_TEMPERATURE", "0.2"))
    
    # Get provider-specific model
    if provider == "openai":
        model = model or os.getenv("OPENAI_LLM_MODEL", "gpt-4o")
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI provider")
        
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            openai_api_key=api_key,
            **kwargs
        )
    
    elif provider == "anthropic":
        model = model or os.getenv("ANTHROPIC_LLM_MODEL", "claude-sonnet-4-0")
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for Anthropic provider")
        
        return ChatAnthropic(
            model=model,
            temperature=temperature,
            anthropic_api_key=api_key,
            **kwargs
        )
    
    elif provider == "gemini":
        model = model or os.getenv("GOOGLE_LLM_MODEL", "gemini-2.5-flash")
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is required for Google provider")
        
        return ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            google_api_key=api_key,
            **kwargs
        )
    
    elif provider == "ollama":
        model = model or os.getenv("OLLAMA_LLM_MODEL", "phi4-mini:3.8b")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        
        return ChatOllama(
            model=model,
            temperature=temperature,
            base_url=base_url,
            **kwargs
        )
    
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}. Supported: openai, anthropic, google, ollama")