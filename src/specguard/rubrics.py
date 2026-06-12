"""Per-mode rubric strings consumed by RubricMiddleware.

Each rubric is a checklist the grader sub-agent uses to score the
writer's output. Items are written as plain English instructions; the
middleware's grader interprets them.
"""
from __future__ import annotations

PRD = """\
Evaluate the PRD using this checklist:

1. Clear product objective (one sentence).
2. Clear primary user persona with job-to-be-done.
3. MVP scope is explicitly separated from Phase 2.
4. At least 5 functional requirements, each testable.
5. At least 5 acceptance criteria in Given/When/Then form.
6. Data entities are listed with key fields.
7. Risks AND assumptions are both included.
8. Output is practical and specific — no vague AI/launch language.
9. Open questions for stakeholders are included.
10. Final answer is structured with the requested sections.

If any item fails, return needs_revision with the specific failed item(s) and a one-line directive.
"""

BRD = """\
Evaluate the BRD using this checklist:

1. Business objective is stated in measurable terms.
2. Stakeholders are listed (sponsor, owner, users, partners).
3. Scope is explicitly bounded (in / out).
4. At least 5 business requirements, each traceable to an objective.
5. Success metrics / KPIs are defined with baselines and targets.
6. Compliance, regulatory, and legal constraints are noted.
7. Risks, assumptions, and dependencies are listed.
8. High-level user journeys are described end-to-end.
9. Open questions for stakeholders are included.
10. Final answer is structured and readable.

If any item fails, return needs_revision with specific feedback.
"""

TECH_SCOPE = """\
Evaluate the Technical Scope using this checklist:

1. Architecture summary (components, data flow) is present.
2. List of services / modules with one-line responsibilities.
3. Data model is listed (entities + key fields + relationships).
4. API surface is enumerated (endpoints or RPCs, with auth notes).
5. UI surface is enumerated (screens or pages, with key states).
6. Non-functional requirements (latency, scale, security, observability).
7. Build vs buy decisions are called out where relevant.
8. Risks and assumptions are listed.
9. Phased delivery plan with rough effort estimate.
10. Final answer is structured and readable.

If any item fails, return needs_revision with specific feedback.
"""

_MODES = {
    "prd": PRD,
    "brd": BRD,
    "tech_scope": TECH_SCOPE,
}


class ModeError(ValueError):
    """Raised when an unknown mode is requested."""


def list_modes() -> list[str]:
    return list(_MODES.keys())


def get_rubric(mode: str) -> str:
    try:
        return _MODES[mode]
    except KeyError as exc:
        raise ModeError(f"unknown mode {mode!r}; valid: {list_modes()}") from exc
