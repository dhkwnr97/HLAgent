"""Build Pydantic AI models from keys held in memory.

Keys come from `.env` (Settings) or are typed in the GUI; GUI keys win. Keys are passed to provider
objects explicitly and are never written to `os.environ`, logs or disk.

- chat model: the chosen provider first, then every other provider that has a key (FallbackModel);
  for Google the configured fallback model id follows the primary one.
- router model: Jev (TypeSafe decision model) when a TypeSafe key is set; when Jev is unsure
  (`UnsureRoute`/`UnfillableRoute`, both `ModelAPIError`s) FallbackModel hands the turn to the chat model.
- embedder: google:gemini-embedding-001 with the Google key, or a local sentence-transformers model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import SecretStr

from hlagent.config import Settings, get_settings
from hlagent.logging_utils import register_secret

ProviderName = Literal["google", "openai", "anthropic"]
PROVIDERS: tuple[ProviderName, ...] = ("google", "openai", "anthropic")


class NoModelAvailable(RuntimeError):
    """No provider key is configured for the requested capability."""


def _plain(v: SecretStr | str | None) -> str | None:
    if v is None:
        return None
    s = v.get_secret_value() if isinstance(v, SecretStr) else v
    return s.strip() or None


@dataclass
class Keys:
    """API keys for one session. Values stay SecretStr; `plain()` is used only at provider construction."""

    google: SecretStr | None = None
    openai: SecretStr | None = None
    anthropic: SecretStr | None = None
    tavily: SecretStr | None = None
    typesafe: SecretStr | None = None
    extra: dict[str, SecretStr] = field(default_factory=dict)

    @classmethod
    def resolve(
        cls, settings: Settings | None = None, overrides: dict[str, str | SecretStr | None] | None = None
    ) -> Keys:
        s = settings or get_settings()
        k = cls(
            google=s.google_api_key,
            openai=s.openai_api_key,
            anthropic=s.anthropic_api_key,
            tavily=s.tavily_api_key,
            typesafe=s.typesafe_api_key,
        )
        for name, v in (overrides or {}).items():
            pv = _plain(v)
            if pv:
                setattr(k, name, SecretStr(pv))
        for name in ("google", "openai", "anthropic", "tavily", "typesafe"):
            pv = _plain(getattr(k, name))
            if pv:
                register_secret(pv)
        return k

    def plain(self, name: str) -> str | None:
        return _plain(getattr(self, name))

    def has(self, name: str) -> bool:
        return self.plain(name) is not None

    def providers(self) -> list[ProviderName]:
        return [p for p in PROVIDERS if self.has(p)]


def _split(spec: str) -> tuple[str, str]:
    if ":" not in spec:
        raise ValueError(f"model id must look like 'provider:model', got {spec!r}")
    p, name = spec.split(":", 1)
    return p, name


def build_model(spec: str, keys: Keys):
    """One concrete model for 'provider:model-name' (explicit key, no environment lookup)."""
    provider, name = _split(spec)
    if provider == "test":
        from pydantic_ai.models.test import TestModel

        return TestModel()
    if provider == "ollama":  # local models (no API key; data stay on the machine)
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.ollama import OllamaProvider

        return OpenAIChatModel(name, provider=OllamaProvider(base_url=get_settings().ollama_base_url))
    key = keys.plain(provider)
    if key is None:
        raise NoModelAvailable(f"no API key for {provider}")
    if provider == "google":
        from pydantic_ai.models.google import GoogleModel
        from pydantic_ai.providers.google import GoogleProvider

        return GoogleModel(name, provider=GoogleProvider(api_key=key))
    if provider == "openai":
        from pydantic_ai.models.openai import OpenAIResponsesModel
        from pydantic_ai.providers.openai import OpenAIProvider

        return OpenAIResponsesModel(name, provider=OpenAIProvider(api_key=key))
    if provider == "anthropic":
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.providers.anthropic import AnthropicProvider

        return AnthropicModel(name, provider=AnthropicProvider(api_key=key))
    raise ValueError(f"unsupported provider {provider!r}")


def model_ids(settings: Settings, provider: ProviderName) -> list[str]:
    if provider == "google":
        return [settings.google_model] + (
            [settings.google_fallback_model] if settings.google_fallback_model else []
        )
    if provider == "openai":
        return [settings.openai_model]
    return [settings.anthropic_model]


def chat_model(
    keys: Keys,
    settings: Settings | None = None,
    provider: ProviderName | None = None,
    model_override: str | None = None,
):
    """Chat model with cross-provider fallback. Raises NoModelAvailable when no key is set."""
    s = settings or get_settings()
    first = provider or s.default_provider
    order = [first] + [p for p in PROVIDERS if p != first]
    specs: list[str] = []
    if model_override:
        specs.append(model_override)
    for p in order:
        if keys.has(p):
            specs += [m for m in model_ids(s, p) if m not in specs]
    models = []
    for spec in specs:
        try:
            models.append(build_model(spec, keys))
        except NoModelAvailable:
            continue
    if not models:
        raise NoModelAvailable(
            "No LLM key configured: set GOOGLE_API_KEY (or OpenAI/Anthropic) in .env or the GUI."
        )
    if len(models) == 1:
        return models[0]
    from pydantic_ai.models.fallback import FallbackModel

    return FallbackModel(*models)


def router_model(keys: Keys, settings: Settings | None = None, provider: ProviderName | None = None):
    """Jev decision model with LLM hand-off, or the chat model alone. Returns None when nothing is available."""
    s = settings or get_settings()
    try:
        chat = chat_model(keys, s, provider)
    except NoModelAvailable:
        chat = None
    if not keys.has("typesafe"):
        return chat
    from pydantic_ai.models.decision import DecisionModelSettings
    from pydantic_ai.models.typesafe import TypeSafeModel
    from pydantic_ai.providers.typesafe import TypeSafeProvider

    jev = TypeSafeModel(
        s.router_jev_model,
        provider=TypeSafeProvider(api_key=keys.plain("typesafe")),
        settings=DecisionModelSettings(decision_route_threshold=s.router_route_threshold),
    )
    if chat is None:
        return jev
    from pydantic_ai.models.fallback import FallbackModel

    return FallbackModel(jev, chat)


def embedder(keys: Keys, settings: Settings | None = None, spec: str | None = None):
    """Embedder for the knowledge base, or raise NoModelAvailable with the fix."""
    from pydantic_ai import Embedder

    s = settings or get_settings()
    spec = spec or s.embedding_model
    provider, name = _split(spec)
    if provider == "google":
        if not keys.has("google"):
            raise NoModelAvailable(
                "The embedding model google:gemini-embedding-001 needs GOOGLE_API_KEY "
                "(or set EMBEDDING_MODEL=sentence-transformers:BAAI/bge-m3 with the [local-embed] extra)."
            )
        from pydantic_ai.embeddings.google import GoogleEmbeddingModel
        from pydantic_ai.providers.google import GoogleProvider

        return Embedder(GoogleEmbeddingModel(name, provider=GoogleProvider(api_key=keys.plain("google"))))
    if provider == "sentence-transformers":
        try:
            import sentence_transformers  # noqa: F401  # pyright: ignore[reportMissingImports]
        except ImportError as e:
            raise NoModelAvailable(
                "Local embeddings need the [local-embed] extra: uv pip install -e '.[local-embed]'"
            ) from e
        return Embedder(spec)
    if provider == "test":
        from pydantic_ai.embeddings.test import TestEmbeddingModel

        return Embedder(TestEmbeddingModel())
    raise ValueError(f"unsupported embedding model {spec!r}")
