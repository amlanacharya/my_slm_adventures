from __future__ import annotations

from pathlib import Path

from langchain_core.messages import AIMessage

import pytest

from specguard.pipeline import GenerationError, GenerationRequest, generate_document


class FakeChatModel:
    def __init__(self):
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


def test_generate_document_revises_and_saves_markdown(tmp_path: Path):
    model = FakeChatModel()
    request = GenerationRequest(
        idea="Build an app for interior designers.",
        mode="prd",
        output_dir=tmp_path,
    )

    result = generate_document(request, chat_model=model)

    assert result.validation.ok is True
    assert result.output_path.exists()
    assert result.output_path.suffix == ".md"
    assert "## Users" in result.markdown
    assert len(model.calls) == 3


class AlwaysValidChatModel:
    def invoke(self, messages):
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


class StillInvalidChatModel:
    def invoke(self, messages):
        return AIMessage(content="# Product Requirements Document\n\n## Problem\nText.\n")


def test_generate_document_fails_when_final_revision_is_invalid(tmp_path: Path):
    request = GenerationRequest(
        idea="Build an app for interior designers.",
        mode="prd",
        output_dir=tmp_path,
    )

    with pytest.raises(GenerationError, match="missing required sections") as exc_info:
        generate_document(request, chat_model=StillInvalidChatModel())

    assert "## Goals" in exc_info.value.validation.missing_sections
    assert not list((tmp_path / "prd").glob("*.md"))


def test_generate_document_does_not_overwrite_same_day_outputs(tmp_path: Path):
    request = GenerationRequest(
        idea="Build an app for interior designers.",
        mode="prd",
        output_dir=tmp_path,
    )

    first = generate_document(request, chat_model=AlwaysValidChatModel())
    second = generate_document(request, chat_model=AlwaysValidChatModel())

    assert first.output_path != second.output_path
    assert first.output_path.exists()
    assert second.output_path.exists()
