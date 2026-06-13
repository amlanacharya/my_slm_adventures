from __future__ import annotations

from langchain_core.messages import AIMessage

from specguard.roles.planner import Brief, plan


class EchoModel:
    def __init__(self):
        self.last_prompt: str | None = None

    def invoke(self, messages):
        self.last_prompt = messages[-1].content
        return AIMessage(content="Assume a small team. Focus the Problem section on quotation delays.")


def test_plan_returns_brief_with_tool_outputs():
    model = EchoModel()
    brief = plan(model, idea="An app for interior designers", mode="prd", standard="## Problem\n...")

    assert isinstance(brief, Brief)
    assert "quotation delays" in brief.guidance
    assert len(brief.questions) > 0
    assert len(brief.checklist) > 0
    assert brief.scope["size"] in ("small", "medium", "large")


def test_plan_prompt_includes_tool_outputs_and_standard():
    model = EchoModel()
    plan(model, idea="An app for interior designers", mode="prd", standard="THE-STANDARD-TEXT")

    assert "THE-STANDARD-TEXT" in model.last_prompt
    assert "job-to-be-done" in model.last_prompt  # a clarifier question made it in
    assert "writing brief" in model.last_prompt.lower()
