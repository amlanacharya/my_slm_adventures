import pytest

from specguard.config import Settings
from specguard.llm_gateway import build_chat_model


def test_settings_defaults_to_ollama_gemma():
    settings = Settings.from_env({})
    assert settings.provider == "ollama"
    assert settings.model == "gemma3:4b"
    assert settings.ollama_base_url == "http://localhost:11434"


def test_settings_supports_openai_provider():
    settings = Settings.from_env({"SPECGUARD_PROVIDER": "openai", "SPECGUARD_MODEL": "gpt-4.1-mini"})
    assert settings.provider == "openai"
    assert settings.model == "gpt-4.1-mini"


def test_unknown_provider_is_rejected():
    with pytest.raises(ValueError, match="unknown provider"):
        Settings.from_env({"SPECGUARD_PROVIDER": "madeup"})


def test_build_chat_model_rejects_unknown_provider_directly():
    settings = Settings(provider="madeup", model="x")
    with pytest.raises(ValueError, match="unknown provider"):
        build_chat_model(settings)
