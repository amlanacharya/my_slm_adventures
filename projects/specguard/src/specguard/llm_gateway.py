from __future__ import annotations

import os

from langchain_core.language_models.chat_models import BaseChatModel

from .config import SUPPORTED_PROVIDERS, Settings


def build_chat_model(settings: Settings | None = None, model: str | None = None) -> BaseChatModel:
    resolved = settings or Settings.from_env()
    resolved_model = model if model is not None else resolved.model

    if resolved.provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(model=resolved_model, base_url=resolved.ollama_base_url)

    if resolved.provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=resolved_model)

    if resolved.provider == "minimax":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=resolved_model,
            base_url=resolved.minimax_base_url,
            api_key=os.environ.get("MINIMAX_API_KEY"),
        )

    if resolved.provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:
            raise RuntimeError("install the anthropic extra to use SPECGUARD_PROVIDER=anthropic") from exc

        return ChatAnthropic(model=resolved_model)  # type: ignore[call-arg]

    raise ValueError(f"unknown provider {resolved.provider!r}; valid: {SUPPORTED_PROVIDERS}")
