"""SpecGuard agent factory.

Builds a Deep Agent with:
  - the writer model (gpt-4.1-mini by default)
  - the RubricMiddleware (grader = same model by default)
  - the InMemorySaver checkpointer
  - the three domain tools
"""
from __future__ import annotations

import os
from typing import Any, cast

from dotenv import load_dotenv

load_dotenv()

from deepagents import RubricMiddleware, create_deep_agent  # noqa: E402
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

from .prompts.system import build_system_prompt  # noqa: E402
from .rubrics import get_rubric  # noqa: E402
from .tools.clarifier import get_clarifying_questions  # noqa: E402
from .tools.domain_checklist import get_checklist  # noqa: E402
from .tools.scope_estimator import ScopeEstimate, estimate_scope  # noqa: E402

SUPPORTED_MODES = ("prd", "brd", "tech_scope")

DEFAULT_MODEL = "openai:gpt-4.1-mini"


def _clarifier_tool(idea: str) -> list[str]:
    """Return clarifying questions the agent should consider for the idea."""
    return get_clarifying_questions(idea)


def _checklist_tool(idea: str) -> list[str]:
    """Return a domain-aware checklist for the idea."""
    return get_checklist(idea)


def _scope_tool(idea: str) -> ScopeEstimate:
    """Return a rough MVP scope estimate (size, team, weeks, risks)."""
    return estimate_scope(idea)


def build_agent(mode: str, model: str | None = None, grader_model: str | None = None):
    """Construct a SpecGuard deep agent for the given mode."""
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"unknown mode {mode!r}; valid: {SUPPORTED_MODES}")

    writer_model = model if model is not None else os.getenv("SPECGUARD_MODEL") or DEFAULT_MODEL
    grader = (
        grader_model
        if grader_model is not None
        else os.getenv("SPECGUARD_GRADER_MODEL") or writer_model
    )

    return create_deep_agent(
        model=writer_model,
        system_prompt=build_system_prompt(mode),
        tools=[_clarifier_tool, _checklist_tool, _scope_tool],
        middleware=[
            cast(Any, RubricMiddleware(model=grader, max_iterations=3)),
        ],
        checkpointer=InMemorySaver(),
    )


def run(agent, idea: str, mode: str, thread_id: str) -> str:
    """Invoke the agent and return the final assistant message content."""
    from langchain_core.messages import HumanMessage

    result = agent.invoke(
        {
            "messages": [HumanMessage(content=idea)],
            "rubric": get_rubric(mode),
        },
        config={"configurable": {"thread_id": thread_id}},
    )
    return result["messages"][-1].content
