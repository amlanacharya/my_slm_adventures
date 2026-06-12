"""Scope estimator tool.

Produces a deterministic, keyword-based MVP scope estimate. Not a
substitute for real engineering planning — used to seed the PRD's
'Commercial estimate' section.
"""
from __future__ import annotations

import re
from typing import TypedDict

_HEAVY = re.compile(r"\b(kyc|compliance|nbfc|lending|bank|insurance|health|erp)\b", re.I)
_MEDIUM = re.compile(r"\b(billing|invoice|booking|payment|marketplace|workspace|coworking)\b", re.I)
_AI = re.compile(r"\b(ml|llm|forecast|vision|voice|rag|recommend)\b", re.I)


class ScopeEstimate(TypedDict):
    size: str
    team: str
    weeks: int
    risks: list[str]


def estimate_scope(idea: str) -> ScopeEstimate:
    text = idea or ""
    heavy = bool(_HEAVY.search(text))
    medium = bool(_MEDIUM.search(text)) or heavy
    ai = bool(_AI.search(text))

    if heavy and ai:
        size = "large"
        team = "2 backend, 1 frontend, 1 ML, 1 designer, 0.5 PM, 0.5 SRE"
        weeks = 16
    elif heavy:
        size = "large"
        team = "2 backend, 1 frontend, 1 designer, 0.5 PM"
        weeks = 12
    elif medium or ai:
        size = "medium"
        team = "1 backend, 1 frontend, 0.5 designer, 0.5 PM"
        weeks = 8
    else:
        size = "small"
        team = "1 fullstack, 0.5 designer, 0.25 PM"
        weeks = 4

    risks: list[str] = []
    if heavy:
        risks.append("Regulatory approvals may extend timeline.")
        risks.append("Compliance audit logging adds non-trivial work.")
    if ai:
        risks.append("Model accuracy and latency SLAs need validation.")
        risks.append("Data licensing and PII handling must be confirmed.")
    if medium and not heavy:
        risks.append("Payment/booking edge cases (refunds, no-shows, partial payments).")
    if not risks:
        risks.append("Scope creep without an explicit Phase 2 cut.")

    return ScopeEstimate(size=size, team=team, weeks=weeks, risks=risks)
