"""Clarifier tool.

Returns a list of clarifying questions the agent should consider
(or surface to the user) before producing a spec.
"""
from __future__ import annotations

_BASE = [
    "Who is the single most important user and what is their job-to-be-done?",
    "What is the smallest workflow that delivers value end-to-end?",
    "What does success look like 30 / 90 / 180 days after launch?",
    "Which existing tool is the user replacing, and why is it failing?",
    "What is the rough budget and team size?",
    "Are there regulatory or compliance constraints (e.g. GST, KYC, PCI)?",
    "What is explicitly out of scope for the MVP?",
]

_DOMAIN = {
    "interior": [
        "How are quotations revised after client feedback?",
        "What payment methods must be supported (UPI, NEFT, card, cash)?",
    ],
    "fintech": [
        "Which regulator(s) apply (RBI, SEBI, IRDA)?",
        "What is the collections strategy for default cases?",
    ],
    "coworking": [
        "How are deposits, refunds, and pro-rata billing handled?",
        "Which access-control hardware is in scope?",
    ],
    "kyc": [
        "Which document types and languages must be supported?",
        "Is the masking reversible (tokenisation) or destructive (redaction)?",
    ],
    "forecast": [
        "What is the acceptable inference latency and cost per request?",
        "How is ground truth collected for evaluation?",
    ],
}


def get_clarifying_questions(idea: str) -> list[str]:
    idea_l = (idea or "").lower()
    extras: list[str] = []
    for key, qs in _DOMAIN.items():
        if key in idea_l:
            extras.extend(qs)
    # Dedupe, cap at 10.
    seen: set[str] = set()
    out: list[str] = []
    for q in _BASE + extras:
        if q not in seen:
            seen.add(q)
            out.append(q)
        if len(out) >= 10:
            break
    return out
