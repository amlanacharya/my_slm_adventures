from __future__ import annotations

import json
from pathlib import Path

from langchain_core.messages import AIMessage

from specguard.pipeline import GenerationRequest, generate_document_stream


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

    def __init__(self, tokens: int = 100):
        self.tokens = tokens
        self.calls: list[str] = []
        self._critic_index = 0
        self._critic_replies = [PASS_JSON]
        self._drafts = [PARTIAL_DOC, FULL_DOC]

    def invoke(self, messages):
        system = messages[0].content if messages else ""
        text = messages[-1].content
        self.calls.append(text)
        if "planner" in system.lower():
            return AIMessage(content="Brief: keep it concrete.")
        if "critic" in system.lower():
            idx = self._critic_index
            self._critic_index += 1
            reply = self._critic_replies[idx] if idx < len(self._critic_replies) else self._critic_replies[-1]
            return AIMessage(content=reply)
        return AIMessage(content=self._drafts.pop(0) if self._drafts else FULL_DOC)


def test_stream_yields_each_pipeline_step_in_order(tmp_path: Path):
    """Attempt 1: partial draft → revision → attempt 2: full draft → pass."""
    model = FakeChatModel()
    model._drafts = [PARTIAL_DOC, FULL_DOC]
    model._critic_replies = [FAIL_JSON, PASS_JSON]

    request = GenerationRequest(
        idea="Build an app for interior designers.",
        mode="prd",
        output_dir=tmp_path,
    )

    events = list(generate_document_stream(request, chat_model=model))

    kinds = [e.kind for e in events]
    assert kinds == [
        "plan",
        "attempt", "draft", "validate", "critique",
        "attempt", "revise", "validate", "critique",
        "save",
    ]


def test_stream_final_event_carries_output_path_and_validation(tmp_path: Path):
    model = FakeChatModel()
    model._drafts = [FULL_DOC]
    model._critic_replies = [PASS_JSON]

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
    """Both 'draft' and 'revise' events carry a token estimate."""
    model = FakeChatModel()
    model._drafts = [PARTIAL_DOC, FULL_DOC]
    model._critic_replies = [FAIL_JSON, PASS_JSON]

    request = GenerationRequest(
        idea="Build an app for interior designers.",
        mode="prd",
        output_dir=tmp_path,
    )

    events = list(generate_document_stream(request, chat_model=model))
    draft_events = [e for e in events if e.kind in ("draft", "revise")]
    assert len(draft_events) == 2
    for e in draft_events:
        assert e.tokens is not None
        assert e.tokens > 0
        assert e.timestamp is not None
