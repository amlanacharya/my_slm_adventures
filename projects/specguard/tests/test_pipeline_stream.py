from __future__ import annotations

from pathlib import Path

from langchain_core.messages import AIMessage

from specguard.pipeline import (
    GenerationRequest,
    generate_document_stream,
)


class FakeChatModel:
    """A chat model whose replies depend on the most recent human message."""

    def __init__(self, tokens: int = 100) -> None:
        self.tokens = tokens
        self.calls: list[str] = []

    def invoke(self, messages):
        text = messages[-1].content
        self.calls.append(text)
        if "Revise" in text:
            return AIMessage(
                content=(
                    "# Product Requirements Document\n\n"
                    "## Problem\nText.\n\n"
                    "## Goals\nText.\n\n"
                    "## Users\nText.\n\n"
                    "## Requirements\nText.\n\n"
                    "## Success Metrics\nText.\n\n"
                    "## Risks and Assumptions\nText.\n"
                )
            )
        if "Review" in text:
            return AIMessage(content="Missing required sections: Users, Requirements, Success Metrics.")
        return AIMessage(content="# Product Requirements Document\n\n## Problem\nText.\n\n## Goals\nText.\n")


def test_stream_yields_each_pipeline_step_in_order(tmp_path: Path):
    model = FakeChatModel()
    request = GenerationRequest(
        idea="Build an app for interior designers.",
        mode="prd",
        output_dir=tmp_path,
    )

    events = list(generate_document_stream(request, chat_model=model))

    kinds = [e.kind for e in events]
    assert kinds == [
        "draft",
        "validate",
        "review",
        "revise",
        "validate",
        "save",
    ]


def test_stream_final_event_carries_output_path_and_validation(tmp_path: Path):
    model = FakeChatModel()
    request = GenerationRequest(
        idea="Build an app for interior designers.",
        mode="prd",
        output_dir=tmp_path,
    )

    events = list(generate_document_stream(request, chat_model=model))
    final = events[-1]
    assert final.kind == "save"
    assert final.validation is not None
    assert final.validation.ok is True
    assert final.output_path is not None
    assert final.output_path.exists()
    assert final.output_path.suffix == ".md"
    assert final.markdown is not None
    assert "## Users" in final.markdown


def test_stream_draft_event_records_token_count(tmp_path: Path):
    # A 4-char-per-token estimate on 400 chars of draft → 100 tokens.
    model = FakeChatModel()
    request = GenerationRequest(
        idea="Build an app for interior designers.",
        mode="prd",
        output_dir=tmp_path,
    )

    events = list(generate_document_stream(request, chat_model=model))
    draft = next(e for e in events if e.kind == "draft")
    # The fake model returns ~62 chars → estimated 15-16 tokens.
    # We just want to assert a positive integer was captured.
    assert draft.tokens is not None
    assert draft.tokens > 0
    assert draft.timestamp is not None
