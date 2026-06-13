import pytest

from specguard.config import Settings


def test_settings_defaults_to_ollama_gemma_and_reuses_it_for_roles():
    settings = Settings.from_env({})
    assert settings.provider == "ollama"
    assert settings.model == "gemma4:latest"
    assert settings.planner_model == "gemma4:latest"
    assert settings.writer_model == "gemma4:latest"
    assert settings.critic_model == "gemma4:latest"
    assert settings.max_attempts == 3
    assert settings.ollama_base_url == "http://localhost:11434"


def test_settings_supports_role_model_overrides_and_attempt_budget():
    settings = Settings.from_env(
        {
            "SPECGUARD_PROVIDER": "openai",
            "SPECGUARD_MODEL": "gpt-4.1-mini",
            "SPECGUARD_PLANNER_MODEL": "o3-mini",
            "SPECGUARD_WRITER_MODEL": "gpt-4.1",
            "SPECGUARD_CRITIC_MODEL": "o4-mini",
            "SPECGUARD_MAX_ATTEMPTS": "5",
        }
    )
    assert settings.provider == "openai"
    assert settings.model == "gpt-4.1-mini"
    assert settings.planner_model == "o3-mini"
    assert settings.writer_model == "gpt-4.1"
    assert settings.critic_model == "o4-mini"
    assert settings.max_attempts == 5


def test_settings_supports_minimax_defaults_and_base_url():
    settings = Settings.from_env({"SPECGUARD_PROVIDER": "minimax"})

    assert settings.provider == "minimax"
    assert settings.model == "MiniMax-M3"
    assert settings.planner_model == "MiniMax-M3"
    assert settings.writer_model == "MiniMax-M3"
    assert settings.critic_model == "MiniMax-M3"
    assert settings.minimax_base_url == "https://api.minimax.io/v1"


def test_settings_clamps_attempt_budget_to_one():
    settings = Settings.from_env({"SPECGUARD_MAX_ATTEMPTS": "0"})
    assert settings.max_attempts == 1


def test_unknown_provider_is_rejected():
    with pytest.raises(ValueError, match="unknown provider"):
        Settings.from_env({"SPECGUARD_PROVIDER": "madeup"})
