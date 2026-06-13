"""Planner role: run the deterministic tools, then one SLM call to write a brief.

Tools are called as plain Python — no tool-calling protocol, because small
models are unreliable at it and every tool takes the same input (the idea).
"""
from __future__ import annotations

from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage

from ..tools.clarifier import get_clarifying_questions
from ..tools.domain_checklist import get_checklist
from ..tools.scope_estimator import ScopeEstimate, estimate_scope


@dataclass(frozen=True)
class Brief:
    guidance: str
    questions: tuple[str, ...]
    checklist: tuple[str, ...]
    scope: ScopeEstimate


def plan(model, idea: str, mode: str, standard: str) -> Brief:
    questions = tuple(get_clarifying_questions(idea))
    checklist = tuple(get_checklist(idea))
    scope = estimate_scope(idea)

    raw = model.invoke(
        [
            SystemMessage(
                content=(
                    "You are SpecGuard's planner. Produce a short writing brief for the writer: "
                    "key assumptions, your best inferred answers to the clarifying questions, "
                    "and per-section guidance. Be concrete; do not write the document itself."
                )
            ),
            HumanMessage(content=_planner_prompt(idea, mode, standard, questions, checklist, scope)),
        ]
    )
    content = getattr(raw, "content", raw)
    guidance = content if isinstance(content, str) else str(content)
    return Brief(guidance=guidance, questions=questions, checklist=checklist, scope=scope)


def _planner_prompt(
    idea: str,
    mode: str,
    standard: str,
    questions: tuple[str, ...],
    checklist: tuple[str, ...],
    scope: ScopeEstimate,
) -> str:
    q = "\n".join(f"- {x}" for x in questions)
    c = "\n".join(f"- {x}" for x in checklist)
    risks = "\n".join(f"- {r}" for r in scope["risks"])
    return (
        f"Write the writing brief for a {mode} document.\n\n"
        f"Idea:\n{idea}\n\n"
        f"Document standard:\n{standard}\n\n"
        f"Clarifying questions to address with assumptions:\n{q}\n\n"
        f"Domain checklist:\n{c}\n\n"
        f"Scope estimate: size={scope['size']}, team={scope['team']}, weeks={scope['weeks']}\n"
        f"Scope risks:\n{risks}"
    )
