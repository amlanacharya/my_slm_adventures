from __future__ import annotations

import json
from pathlib import Path

from langchain_core.messages import AIMessage

from specguard.pipeline import GenerationRequest, generate_document, generate_document_stream

FULL_DOC = (
    "# Product Requirements Document\n\n"
    "## Problem\nText.\n\n## Goals\nText.\n\n## Users\nText.\n\n"
    "## Requirements\nText.\n\n## Success Metrics\nText.\n\n## Risks and Assumptions\nText.\n"
)
PARTIAL_DOC = "# Product Requirements Document\n\n## Problem\nText.\n\n## Goals\nText.\n"

PASS_JSON = json.dumps({"verdict": "pass", "criteria": [], "notes": "ok"})
FAIL_JSON = json.dumps({"verdict": "needs_revision", "criteria": [], "notes": "missing sections"})


class ScriptedModel:
    """Routes by prompt markers: planner -> brief, critic -> JSON, writer -> docs.

    The critic calls model.invoke() twice per attempt when it retries on bad JSON.
    We pre-populate critic_replies with enough entries to cover all attempts.
    """

    def __init__(self, drafts: list[str], critic_replies: list[str]):
        self.drafts = drafts
        # Pre-populate so retries don't exhaust the list
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


def _request(tmp_path: Path) -> GenerationRequest:
    return GenerationRequest(idea="An app for interior designers.", mode="prd", output_dir=tmp_path)


def test_pass_first_attempt_event_order(tmp_path: Path):
    model = ScriptedModel(drafts=[FULL_DOC], critic_replies=[PASS_JSON])
    events = list(generate_document_stream(_request(tmp_path), chat_model=model))
    kinds = [e.kind for e in events]
    assert kinds == ["plan", "attempt", "draft", "validate", "critique", "save"]
    assert events[-1].degraded is False
    assert events[-1].output_path is not None and events[-1].output_path.exists()


def test_pass_after_one_revision(tmp_path: Path):
    model = ScriptedModel(drafts=[PARTIAL_DOC, FULL_DOC], critic_replies=[FAIL_JSON, PASS_JSON])
    events = list(generate_document_stream(_request(tmp_path), chat_model=model))
    kinds = [e.kind for e in events]
    assert kinds == [
        "plan",
        "attempt", "draft", "validate", "critique",
        "attempt", "revise", "validate", "critique",
        "save",
    ]
    assert events[-1].degraded is False


def test_budget_exhausted_saves_degraded(tmp_path: Path):
    model = ScriptedModel(
        drafts=[PARTIAL_DOC, PARTIAL_DOC, PARTIAL_DOC],
        critic_replies=[FAIL_JSON, FAIL_JSON, FAIL_JSON],
    )
    result = generate_document(_request(tmp_path), chat_model=model)
    assert result.degraded is True
    assert result.validation.ok is False
    assert "## Users" in result.validation.missing_sections
    assert result.output_path.exists()  # degraded output is still written


def test_critic_garbage_twice_falls_back_to_validators(tmp_path: Path):
    model = ScriptedModel(drafts=[FULL_DOC], critic_replies=["garbage", "more garbage"])
    events = list(generate_document_stream(_request(tmp_path), chat_model=model))
    critique_event = next(e for e in events if e.kind == "critique")
    assert critique_event.critic is not None
    assert critique_event.critic.fallback is True
    assert events[-1].kind == "save"
    assert events[-1].degraded is False  # validators passed; fallback critic doesn't block
