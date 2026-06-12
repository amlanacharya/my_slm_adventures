from __future__ import annotations

from pathlib import Path

from langchain_core.messages import AIMessage

from specguard.pipeline import GenerationRequest, generate_document


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
