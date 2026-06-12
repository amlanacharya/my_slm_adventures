from __future__ import annotations

from dataclasses import dataclass
from os import environ
from typing import Mapping


SUPPORTED_PROVIDERS = ("ollama", "openai", "anthropic")


@dataclass(frozen=True)
class Settings:
    provider: str = "ollama"
    model: str = "gemma3:4b"
    ollama_base_url: str = "http://localhost:11434"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        source = environ if env is None else env
        provider = source.get("SPECGUARD_PROVIDER", "ollama").lower()
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"unknown provider {provider!r}; valid: {SUPPORTED_PROVIDERS}")

        default_model = "gemma3:4b" if provider == "ollama" else "gpt-4.1-mini"
        return cls(
            provider=provider,
            model=source.get("SPECGUARD_MODEL", default_model),
            ollama_base_url=source.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        )
