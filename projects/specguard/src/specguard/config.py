from __future__ import annotations

from dataclasses import dataclass
from os import environ
from typing import Mapping


SUPPORTED_PROVIDERS = ("ollama", "openai", "anthropic", "minimax")
DEFAULT_MODELS = {
    "ollama": "gemma4:latest",
    "openai": "gpt-4.1-mini",
    "anthropic": "claude-3-5-haiku-latest",
    "minimax": "MiniMax-M3",
}


@dataclass(frozen=True)
class Settings:
    provider: str = "ollama"
    model: str = "gemma4:latest"
    planner_model: str = "gemma4:latest"
    writer_model: str = "gemma4:latest"
    critic_model: str = "gemma4:latest"
    max_attempts: int = 3
    ollama_base_url: str = "http://localhost:11434"
    minimax_base_url: str = "https://api.minimax.io/v1"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        source = environ if env is None else env
        provider = source.get("SPECGUARD_PROVIDER", "ollama").lower()
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"unknown provider {provider!r}; valid: {SUPPORTED_PROVIDERS}")

        default_model = DEFAULT_MODELS[provider]
        model = source.get("SPECGUARD_MODEL", default_model)
        try:
            max_attempts = int(source.get("SPECGUARD_MAX_ATTEMPTS", "3"))
        except ValueError:
            max_attempts = 3
        return cls(
            provider=provider,
            model=model,
            planner_model=source.get("SPECGUARD_PLANNER_MODEL", model),
            writer_model=source.get("SPECGUARD_WRITER_MODEL", model),
            critic_model=source.get("SPECGUARD_CRITIC_MODEL", model),
            max_attempts=max(1, max_attempts),
            ollama_base_url=source.get("OLLAMA_BASE_URL", "http://localhost:11434"),
            minimax_base_url=source.get("MINIMAX_BASE_URL", "https://api.minimax.io/v1"),
        )
