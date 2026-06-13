from __future__ import annotations

from langchain_core.messages import AIMessage

from specguard.roles.planner import Brief
from specguard.roles.writer import draft, revise


class EchoModel:
    def __init__(self):
        self.last_prompt: str | None = None
        self.last_system: str | None = None

    def invoke(self, messages):
        self.last_system = messages[0].content
        self.last_prompt = messages[-1].content
        return AIMessage(content="# Doc\n\n## Problem\nText.")


def _brief() -> Brief:
    return Brief(
        guidance="Focus on quotation delays.",
        questions=("Who is the user?",),
        checklist=("Billing",),
        scope={"size": "small", "team": "1 fullstack", "weeks": 4, "risks": ["Scope creep"]},
    )


def test_draft_includes_idea_brief_and_standard():
    model = EchoModel()
    text = draft(model, idea="THE-IDEA", mode="prd", standard="THE-STANDARD", brief=_brief())

    assert text.startswith("# Doc")
    assert "THE-IDEA" in model.last_prompt
    assert "quotation delays" in model.last_prompt
    assert "THE-STANDARD" in model.last_system


def test_revise_includes_critic_notes_and_missing_sections():
    model = EchoModel()
    revise(
        model,
        idea="THE-IDEA",
        mode="prd",
        standard="THE-STANDARD",
        brief=_brief(),
        previous_draft="OLD-DRAFT",
        critic_notes="Add metrics.",
        missing_sections=("## Users",),
    )

    assert "OLD-DRAFT" in model.last_prompt
    assert "Add metrics." in model.last_prompt
    assert "## Users" in model.last_prompt
    assert "Revise" in model.last_prompt
