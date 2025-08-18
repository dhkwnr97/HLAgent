"""
Universal LLM Provider System for HLAgent.
Supports OpenAI, Anthropic, Gemini, VertexAI, HuggingFace, Groq, and Ollama
based on .env configuration.
"""

import os
from typing import Union, Optional, Dict, Any

# Fix for Gemini event loop issues
from src.utils.event_loop_fix import apply_event_loop_fix
apply_event_loop_fix()
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.models.huggingface import HuggingFaceModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.google_gla import GoogleGLAProvider
from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.providers.huggingface import HuggingFaceProvider

from .settings import settings
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

# Type alias for all supported model types
LLMModel = Union[OpenAIModel, AnthropicModel, GeminiModel, GroqModel, HuggingFaceModel]


class UniversalLLMProvider:
    """
    Universal LLM Provider that creates models based on environment configuration.
    Supports all major LLM providers with fallback options.
    """
    
    def __init__(self):
        self._provider = settings.default_llm_provider.lower()
        self._model_name = settings.default_llm_model
        self._cache: Dict[str, LLMModel] = {}
    
    def get_model(self, 
                  provider: Optional[str] = None, 
                  model_name: Optional[str] = None,
                  **kwargs) -> LLMModel:
        """
        Get LLM model based on provider and model name.
        
        Args:
            provider: Override default provider
            model_name: Override default model name
            **kwargs: Additional model parameters
            
        Returns:
            Configured LLM model instance
        """
        provider = provider or self._provider
        model_name = model_name or self._model_name
        
        cache_key = f"{provider}:{model_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            model = self._create_model(provider, model_name, **kwargs)
            self._cache[cache_key] = model
            logger.info(f"Created {provider} model: {model_name}")
            return model
        except Exception as e:
            logger.error(f"Failed to create {provider} model {model_name}: {e}")
            # Try fallback
            return self._get_fallback_model(**kwargs)
    
    def _create_model(self, provider: str, model_name: str, **kwargs) -> LLMModel:
        """Create model instance for specified provider."""
        
        if provider == "openai":
            return self._create_openai_model(model_name, **kwargs)
        elif provider == "anthropic":
            return self._create_anthropic_model(model_name, **kwargs)
        elif provider == "gemini":
            return self._create_gemini_model(model_name, **kwargs)
        elif provider == "vertex":
            return self._create_vertex_model(model_name, **kwargs)
        elif provider == "groq":
            return self._create_groq_model(model_name, **kwargs)
        elif provider == "huggingface":
            return self._create_huggingface_model(model_name, **kwargs)
        elif provider == "ollama":
            return self._create_ollama_model(model_name, **kwargs)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    def _create_ollama_model(self, model_name: str, **kwargs) -> OpenAIModel:
        """Create Ollama model using OpenAI-compatible interface."""
        base_url = kwargs.get("base_url", settings.ollama_base_url)
        
        # Ollama uses OpenAI-compatible API
        provider = OpenAIProvider(base_url=base_url)
        return OpenAIModel(model_name, provider=provider)
    
    def _create_openai_model(self, model_name: str, **kwargs) -> OpenAIModel:
        """Create OpenAI model instance."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        
        provider = OpenAIProvider(api_key=api_key)
        return OpenAIModel(model_name, provider=provider)
    
    def _create_anthropic_model(self, model_name: str, **kwargs) -> AnthropicModel:
        """Create Anthropic model instance."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")
        
        provider = AnthropicProvider(api_key=api_key)
        return AnthropicModel(model_name, provider=provider)
    
    def _create_gemini_model(self, model_name: str, **kwargs) -> GeminiModel:
        """Create Gemini model instance with event loop protection."""
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment")
        
        try:
            # Create Gemini model with custom HTTP client settings for better async handling
            from httpx import AsyncClient, Limits
            
            # Configure async client with longer timeout and connection limits
            limits = kwargs.get("limits") or Limits(
                max_keepalive_connections=10,
                max_connections=100,
                keepalive_expiry=30.0
            )
            
            custom_http_client = AsyncClient(
                timeout=60.0,
                limits=limits
            )
            
            provider = GoogleGLAProvider(
                api_key=api_key, 
                http_client=custom_http_client
            )
            return GeminiModel(model_name, provider=provider)
            
        except Exception as e:
            logger.warning(f"Failed to create Gemini model with custom client: {e}")
            # Fallback to basic provider
            provider = GoogleGLAProvider(api_key=api_key)
            return GeminiModel(model_name, provider=provider)

    def _create_vertex_model(self, model_name: str, **kwargs) -> GeminiModel:
        """Create Vertex model instance."""
        service_account_file = Path(os.getenv("SERVICE_ACCOUNT_FILE"))
        if not service_account_file:
            raise ValueError("SERVICE_ACCOUNT_FILE not found in environment")
        
        provider = GoogleVertexProvider(service_account_file=service_account_file)
        return GeminiModel(model_name, provider=provider)

    def _create_groq_model(self, model_name: str, **kwargs) -> GroqModel:
        """Create Groq model instance."""
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not found in environment")
        
        provider = GroqProvider(api_key=api_key)
        return GroqModel(model_name, provider=provider)
    
    def _create_huggingface_model(self, model_name: str, **kwargs) -> HuggingFaceModel:
        """Create HuggingFace model instance."""
        hf_token = os.getenv("HUGGINGFACE_TOKEN")
        hf_provider = os.getenv("HUGGINGFACE_PROVIDER")
        if not hf_token:
            raise ValueError("HUGGINGFACE_TOKEN not found in environment")
        
        provider = HuggingFaceProvider(api_key=hf_token, provider_name=hf_provider)
        return HuggingFaceModel(model_name, provider=provider)
    
    def _get_fallback_model(self, **kwargs) -> LLMModel:
        """Get fallback model when primary provider fails."""
        fallback_order = [
            ("ollama", True),  # Ollama usually available locally
            ("gemini", os.getenv("GOOGLE_API_KEY")),
            ("openai", os.getenv("OPENAI_API_KEY")),
            ("anthropic", os.getenv("ANTHROPIC_API_KEY"))
        ]
        
        for provider, available in fallback_order:
            if available and provider != self._provider:
                try:
                    fallback_models = {
                        "ollama": "mistral:7b",
                        "gemini": "gemini-2.0-flash",
                        "openai": "gpt-4o-mini",
                        "anthropic": "claude-3-5-haiku-latest"
                    }
                    model_name = fallback_models.get(provider, "default")
                    logger.warning(f"Using fallback provider: {provider} with model: {model_name}")
                    return self._create_model(provider, model_name, **kwargs)
                except Exception as e:
                    logger.error(f"Fallback {provider} also failed: {e}")
                    continue
        
        raise RuntimeError("All LLM providers failed, no fallback available")
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get information about current provider configuration."""
        return {
            "primary_provider": self._provider,
            "primary_model": self._model_name,
            "available_providers": self._get_available_providers(),
            "cache_size": len(self._cache)
        }
    
    def _get_available_providers(self) -> Dict[str, bool]:
        """Check which providers are available based on environment variables."""
        return {
            "ollama": True, # Ollama is free local LLM.
            "openai": bool(os.getenv("OPENAI_API_KEY")),
            "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
            "gemini": bool(os.getenv("GOOGLE_API_KEY")),
            "vertex": bool(os.getenv("VERTEX_API_KEY")),
            "groq": bool(os.getenv("GROQ_API_KEY")),
            "huggingface": bool(os.getenv("HUGGINGFACE_TOKEN"))
        }
    
    def clear_cache(self):
        """Clear the model cache."""
        self._cache.clear()
        logger.info("Model cache cleared")


# Global instance
universal_provider = UniversalLLMProvider()

def get_provider_info() -> Dict[str, Any]:
    """Get information about current provider configuration."""
    return universal_provider.get_provider_info()

def get_default_model(**kwargs) -> LLMModel:
    """Get default model based on environment configuration."""
    return universal_provider.get_model(**kwargs)

def get_model(provider: str, model_name: str, **kwargs) -> LLMModel:
    """Get specific model by provider and name."""
    return universal_provider.get_model(provider=provider, model_name=model_name, **kwargs)


####################################
# HLAgent sub agents LLM providers #
####################################
def get_supervisor_model(**kwargs) -> LLMModel:
    """Get model specifically for supervisor agent."""
    # Use environment configured model or fallback
    return get_default_model(**kwargs)

def get_hlateacher_model(**kwargs) -> LLMModel:
    """Get model specifically for HLA teacher agent."""
    # Use environment configured model or fallback  
    return get_default_model(**kwargs)

def get_parameterhandler_model(**kwargs) -> LLMModel:
    """Get model specifically for Parameter Handler agent."""
    # Use environment configured model or fallback  
    return get_default_model(**kwargs)

def get_fileconverter_model(**kwargs) -> LLMModel:
    """Get model specifically for File Converter agent."""
    # Use environment configured model or fallback  
    return get_default_model(**kwargs)

def get_hlafinemapping_model(**kwargs) -> LLMModel:
    """Get model specifically for HLA Fine Mapping agent."""
    # Use environment configured model or fallback  
    return get_default_model(**kwargs)

def get_genotypephasing_model(**kwargs) -> LLMModel:
    """Get model specifically for Genotype Phasing agent."""
    # Use environment configured model or fallback  
    return get_default_model(**kwargs)

def get_hlaimputation_model(**kwargs) -> LLMModel:
    """Get model specifically for HLA Imputation agent."""
    # Use environment configured model or fallback  
    return get_default_model(**kwargs)

