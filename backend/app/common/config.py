"""Application settings, loaded from environment / .env via pydantic-settings.

Single source of truth for provider keys, the provider-priority chain, the
per-provider model strings, the MCP tool-server URL, and the global
``mock_mode`` flag.

Model routing: the first provider in ``provider_priority`` that has an API key
is the **primary**; the remaining available providers become **fallbacks**
(applied by LiteLLM). Swapping providers is a pure config change.
"""

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# provider -> the Settings field holding its key / the env var LiteLLM reads.
_PROVIDER_KEY_FIELD = {
    "openai": "openai_api_key",
    "anthropic": "anthropic_api_key",
    "gemini": "gemini_api_key",
}
_PROVIDER_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Provider keys
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""

    # Ordered provider preference. The first provider that has a key is primary;
    # the rest (that have keys) become LiteLLM fallbacks, in order.
    provider_priority: str = "openai,anthropic,gemini"

    # Per-provider model strings (LiteLLM). Override any via env, e.g.
    # OPENAI_MODEL_QUALITY=openai/gpt-4.1
    openai_model_quality: str = "openai/gpt-4o"
    openai_model_cheap: str = "openai/gpt-4o-mini"
    anthropic_model_quality: str = "anthropic/claude-opus-4-8"
    anthropic_model_cheap: str = "anthropic/claude-haiku-4-5-20251001"
    gemini_model_quality: str = "gemini/gemini-1.5-pro"
    gemini_model_cheap: str = "gemini/gemini-1.5-flash"

    # MCP tool server (FastMCP SSE transport)
    mcp_url: str = "http://localhost:8077/sse"
    mcp_transport: str = "sse"

    # Database (SQLite file lives under the backend/database/ folder)
    database_url: str = "sqlite:///database/hospital.db"

    # CORS origin for the Next.js dev server
    frontend_origin: str = "http://localhost:3000"

    # Auth (JWT)
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 12

    # ------------------------------------------------------------------ #
    # Provider / model resolution
    # ------------------------------------------------------------------ #
    def _priority(self) -> list[str]:
        return [p.strip().lower() for p in self.provider_priority.split(",") if p.strip()]

    def available_providers(self) -> list[str]:
        """Providers (in priority order) that have an API key configured."""
        return [p for p in self._priority() if getattr(self, _PROVIDER_KEY_FIELD.get(p, ""), "")]

    @property
    def primary_provider(self) -> str:
        """First available provider, or the first listed one (for display) if none."""
        avail = self.available_providers()
        if avail:
            return avail[0]
        order = self._priority()
        return order[0] if order else "openai"

    def _provider_model(self, provider: str, *, quality: bool) -> str:
        suffix = "model_quality" if quality else "model_cheap"
        return getattr(self, f"{provider}_{suffix}")

    @property
    def model_quality(self) -> str:
        return self._provider_model(self.primary_provider, quality=True)

    @property
    def model_cheap(self) -> str:
        return self._provider_model(self.primary_provider, quality=False)

    def fallback_models(self, *, quality: bool = True) -> list[str]:
        """Model strings for the available providers *after* the primary."""
        avail = self.available_providers()
        return [self._provider_model(p, quality=quality) for p in avail[1:]]

    @property
    def has_provider_key(self) -> bool:
        return any(getattr(self, f) for f in _PROVIDER_KEY_FIELD.values())

    def export_provider_keys_to_env(self) -> None:
        """Push configured keys into the environment so LiteLLM can read them.

        Uses ``setdefault`` so an explicit shell env var always wins over .env.
        """
        for provider, field in _PROVIDER_KEY_FIELD.items():
            value = getattr(self, field)
            if value:
                os.environ.setdefault(_PROVIDER_ENV[provider], value)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
