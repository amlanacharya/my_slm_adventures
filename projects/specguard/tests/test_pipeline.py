from __future__ import annotations

import json
from pathlib import Path

from langchain_core.messages import AIMessage

from specguard.pipeline import GenerationRequest, generate_document


FULL_DOC = (
    "# Product Requirements Document\n\n"
    "## Problem\nText.\n\n## Goals\nText.\n\n## Users\nText.\n\n"
    "## Requirements\nText.\n\n## Success Metrics\nText.\n\n## Risks and Assumptions\nText.\n"
)
PARTIAL_DOC = (
    "# Product Requirements Document\n\n"
    "## Problem\nText.\n\n## Goals\nText.\n"
)

PASS_JSON = json.dumps({"verdict": "pass", "criteria": [], "notes": "ok"})
FAIL_JSON = json.dumps({"verdict": "needs_revision", "criteria": [], "notes": "missing sections"})


class FakeChatModel:
    """Routes by system message role: planner → brief, critic → JSON, writer → docs."""

    def __init__(self, drafts: list[str], critic_replies: list[str]):
        self.drafts = drafts
        self.critic_replies = critic_replies[:]
        self._critic_index = 0
        self.calls: list[str] = []

    def invoke(self, messages):
        system = messages[0].content if messages else ""
        text = messages[-1].content
        self.calls.append(text)
        if "planner" in system.lower():
            return AIMessage(content="Brief: keep it concrete.")
        if "critic" in system.lower():
            idx = self._critic_index
            self._critic_index += 1
            reply = self.critic_replies[idx] if idx < len(self.critic_replies) else self.critic_replies[-1]
            return AIMessage(content=reply)
        return AIMessage(content=self.drafts.pop(0))


def test_generate_document_revises_and_saves_markdown(tmp_path: Path):
    # attempt 1: partial draft → validation fails → critic → revise
    # attempt 2: full draft → validation passes → finalize
    model = FakeChatModel(
        drafts=[PARTIAL_DOC, FULL_DOC],
        critic_replies=[FAIL_JSON, PASS_JSON],
    )
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


class AlwaysValidChatModel:
    """Always returns a complete valid PRD."""

    def __init__(self):
        self.calls: list[str] = []

    def invoke(self, messages):
        system = messages[0].content if messages else ""
        text = messages[-1].content
        self.calls.append(text)
        if "critic" in system.lower():
            return AIMessage(content=PASS_JSON)
        return AIMessage(content=FULL_DOC)


class StillInvalidChatModel:
    """Always returns a partial PRD that never passes validation."""

    def __init__(self):
        self.calls: list[str] = []

    def invoke(self, messages):
        system = messages[0].content if messages else ""
        text = messages[-1].content
        self.calls.append(text)
        if "critic" in system.lower():
            return AIMessage(content=FAIL_JSON)
        return AIMessage(content=PARTIAL_DOC)


def test_generate_document_fails_when_final_revision_is_invalid(tmp_path: Path):
    """Budget exhausted → degraded result, not GenerationError (degrade-not-block)."""
    request = GenerationRequest(
        idea="Build an app for interior designers.",
        mode="prd",
        output_dir=tmp_path,
    )

    result = generate_document(request, chat_model=StillInvalidChatModel())

    # Degrade-not-block: still saves the output
    assert result.degraded is True
    assert result.validation.ok is False
    assert result.output_path.exists()
    assert "## Users" in result.validation.missing_sections


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
