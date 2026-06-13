"""Writer role: draft the document, and revise it from critic + validator findings."""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from .planner import Brief


def draft(model, idea: str, mode: str, standard: str, brief: Brief) -> str:
    raw = model.invoke(
        [
            SystemMessage(content=_system_prompt(mode, standard)),
            HumanMessage(
                content=(
                    f"Generate the document for this idea:\n\n{idea}\n\n"
                    f"Writing brief from the planner:\n{brief.guidance}"
                )
            ),
        ]
    )
    return _content(raw)


def revise(
    model,
    idea: str,
    mode: str,
    standard: str,
    brief: Brief,
    previous_draft: str,
    critic_notes: str,
    missing_sections: tuple[str, ...],
) -> str:
    missing = ", ".join(missing_sections) if missing_sections else "none"
    raw = model.invoke(
        [
            SystemMessage(content=_system_prompt(mode, standard)),
            HumanMessage(
                content=(
                    "Revise the draft into final Markdown. Preserve useful content, fix the "
                    "critic findings, and include all required sections.\n\n"
                    f"Idea:\n{idea}\n\n"
                    f"Writing brief:\n{brief.guidance}\n\n"
                    f"Missing sections:\n{missing}\n\n"
                    f"Critic findings:\n{critic_notes}\n\n"
                    f"Draft:\n{previous_draft}"
                )
            ),
        ]
    )
    return _content(raw)


def _system_prompt(mode: str, standard: str) -> str:
    return (
        f"You are SpecGuard. Generate a {mode} document in Markdown. "
        "Follow the standard exactly and include every required section.\n\n"
        f"{standard}"
    )


def _content(message) -> str:
    content = getattr(message, "content", message)
    return content if isinstance(content, str) else str(content)
