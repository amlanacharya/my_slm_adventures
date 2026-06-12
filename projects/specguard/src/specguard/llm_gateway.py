from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from .config import SUPPORTED_PROVIDERS, Settings


def build_chat_model(settings: Settings | None = None) -> BaseChatModel:
    resolved = settings or Settings.from_env()

    if resolved.provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(model=resolved.model, base_url=resolved.ollama_base_url)

    if resolved.provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=resolved.model)

    if resolved.provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:
            raise RuntimeError("install the anthropic extra to use SPECGUARD_PROVIDER=anthropic") from exc

        return ChatAnthropic(model=resolved.model)

    raise ValueError(f"unknown provider {resolved.provider!r}; valid: {SUPPORTED_PROVIDERS}")
