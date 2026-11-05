"""Application settings (pydantic-settings).

All API keys are optional `SecretStr` values; a missing key disables the feature that needs it
instead of failing at import (v1 defect D7). Keys typed in the GUI are passed explicitly and
never written back into this object or into `os.environ`.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from hlagent.paths import project_root

Provider = Literal["google", "openai", "anthropic"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(project_root() / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    default_provider: Provider = "google"

    google_api_key: SecretStr | None = None
    google_model: str = "google:gemini-3-flash-preview"
    google_fallback_model: str | None = "google:gemini-3.6-flash"

    openai_api_key: SecretStr | None = None
    openai_model: str = "openai:gpt-5.5"

    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "anthropic:claude-sonnet-5-5"

    tavily_api_key: SecretStr | None = None
    typesafe_api_key: SecretStr | None = None
    router_jev_model: str = "jev-latest"
    router_route_threshold: float = Field(default=0.80, ge=0.0, le=1.0)

    embedding_model: str = "google:gemini-embedding-001"

    # local models through Ollama's OpenAI-compatible endpoint (model ids like "ollama:llama3.1:8b")
    ollama_base_url: str = "http://localhost:11434/v1"

    hlagent_max_parallel_jobs: int = Field(default=1, ge=1, le=8)
    hlagent_plink: str = "plink"
    hlagent_plink2: str = "plink2"
    hlagent_rscript: str = "Rscript"
    hlagent_java: str = "java"
    hlagent_docker: str = "docker"

    def secret_values(self) -> list[str]:
        """Plain values of every configured secret (for log redaction only)."""
        out: list[str] = []
        for name in (
            "google_api_key",
            "openai_api_key",
            "anthropic_api_key",
            "tavily_api_key",
            "typesafe_api_key",
        ):
            v = getattr(self, name)
            if v is not None and v.get_secret_value():
                out.append(v.get_secret_value())
        return out


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
