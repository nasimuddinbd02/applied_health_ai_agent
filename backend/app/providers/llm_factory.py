"""LLM factory — the single place that constructs the ChatLiteLLM client.

Resolves the **primary** model string from the provider-priority chain and
attaches the remaining available providers as **LiteLLM fallbacks**, so a single
client transparently fails over OpenAI → Anthropic → Gemini (whichever have
keys). This is the only class that instantiates an LLM.
"""

from typing import Any

from app.common.config import Settings


class LLMFactory:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        # Ensure LiteLLM can read the provider keys from the environment.
        settings.export_provider_keys_to_env()

    def model_string(self, *, quality: bool = True) -> str:
        """Primary model string (first available provider's quality/cheap model)."""
        return self._settings.model_quality if quality else self._settings.model_cheap

    def fallback_models(self, *, quality: bool = True) -> list[str]:
        return self._settings.fallback_models(quality=quality)

    def get_llm(self, *, quality: bool = True) -> Any:
        """Build the ChatLiteLLM client for the primary provider + fallbacks.

        LiteLLM applies ``fallbacks`` per request, so generation, RAG and the
        tool-calling agent all share one client that fails over automatically.
        """
        from langchain_litellm import ChatLiteLLM

        kwargs: dict[str, Any] = {
            "model": self.model_string(quality=quality),
            "temperature": 0.2,
        }
        fallbacks = self.fallback_models(quality=quality)
        if fallbacks:
            # ChatLiteLLM forwards model_kwargs into litellm.completion(...).
            kwargs["model_kwargs"] = {"fallbacks": fallbacks}
        return ChatLiteLLM(**kwargs)
