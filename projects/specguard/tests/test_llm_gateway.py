import sys
import types

import pytest

from specguard.config import Settings
from specguard.llm_gateway import build_chat_model


def test_build_chat_model_uses_override_model_and_keeps_provider_specific_args(monkeypatch):
    records: list[dict[str, str]] = []

    class FakeChatOllama:
        def __init__(self, **kwargs):
            records.append(kwargs)

    monkeypatch.setitem(
        sys.modules,
        "langchain_ollama",
        types.SimpleNamespace(ChatOllama=FakeChatOllama),
    )

    settings = Settings(provider="ollama", model="base-model", ollama_base_url="http://example")
    build_chat_model(settings, model="override-model")

    assert records == [{"model": "override-model", "base_url": "http://example"}]


def test_build_chat_model_uses_openai_compatible_minimax_endpoint(monkeypatch):
    records: list[dict[str, str]] = []

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            records.append(kwargs)

    monkeypatch.setitem(
        sys.modules,
        "langchain_openai",
        types.SimpleNamespace(ChatOpenAI=FakeChatOpenAI),
    )
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-minimax")

    settings = Settings(
        provider="minimax",
        model="MiniMax-M3",
        minimax_base_url="https://example.minimax/v1",
    )
    build_chat_model(settings, model="MiniMax-M3")

    assert records == [
        {
            "model": "MiniMax-M3",
            "base_url": "https://example.minimax/v1",
            "api_key": "sk-minimax",
        }
    ]


def test_build_chat_model_rejects_unknown_provider_directly():
    settings = Settings(provider="madeup", model="x")
    with pytest.raises(ValueError, match="unknown provider"):
        build_chat_model(settings)
