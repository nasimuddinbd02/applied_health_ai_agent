"""Provider-priority + LiteLLM fallback resolution (offline, no network)."""

from app.common.config import Settings


def make(**kw) -> Settings:
    # _env_file=None so the test ignores any local .env; explicit kwargs win.
    return Settings(_env_file=None, **kw)


def test_openai_primary_with_anthropic_then_gemini_fallback():
    s = make(openai_api_key="o", anthropic_api_key="a", gemini_api_key="g")
    assert s.primary_provider == "openai"
    assert s.model_quality == "openai/gpt-4o"
    assert s.model_cheap == "openai/gpt-4o-mini"
    assert s.fallback_models(quality=True) == [
        "anthropic/claude-opus-4-8",
        "gemini/gemini-1.5-pro",
    ]
    assert s.has_provider_key is True


def test_falls_back_to_anthropic_when_no_openai_key():
    s = make(openai_api_key="", anthropic_api_key="a", gemini_api_key="g")
    assert s.primary_provider == "anthropic"
    assert s.fallback_models(quality=False) == ["gemini/gemini-1.5-flash"]


def test_gemini_only():
    s = make(openai_api_key="", anthropic_api_key="", gemini_api_key="g")
    assert s.primary_provider == "gemini"
    assert s.fallback_models() == []
    assert s.has_provider_key is True


def test_no_keys_has_no_provider_key():
    s = make(openai_api_key="", anthropic_api_key="", gemini_api_key="")
    assert s.has_provider_key is False
    assert s.primary_provider == "openai"  # display default when nothing available


def test_custom_priority_order():
    s = make(openai_api_key="o", anthropic_api_key="a", provider_priority="anthropic,openai")
    assert s.primary_provider == "anthropic"
    assert s.fallback_models() == ["openai/gpt-4o"]


def test_export_keys_to_env(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    s = make(openai_api_key="sk-test", gemini_api_key="gm-test")
    s.export_provider_keys_to_env()
    import os

    assert os.environ["OPENAI_API_KEY"] == "sk-test"
    assert os.environ["GEMINI_API_KEY"] == "gm-test"
