"""Domain checklist tool.

Returns a list of practical checklist items the agent should consider
when drafting a PRD/BRD, biased by detected domain keywords.
"""
from __future__ import annotations

import re
from typing import Callable

GENERIC = [
    "Define primary user persona and one-line job-to-be-done.",
    "List 3-5 core workflows end-to-end.",
    "Capture at least 5 functional requirements.",
    "Capture at least 5 acceptance criteria (Given/When/Then).",
    "Enumerate data entities and key fields.",
    "Identify at least 3 risks and assumptions.",
    "Separate MVP from Phase 2 explicitly.",
    "Note open questions for stakeholders.",
]

_DOMAIN_RULES: list[tuple[re.Pattern[str], Callable[[], list[str]]]] = [
    (re.compile(r"\binterior|designer|furnish|quotation|gst\b", re.I),
     lambda: [
         "Capture GST/tax handling per line item and per invoice.",
         "Define labour vs material vs subcontractor payment flows.",
         "Specify quotation revision and approval workflow.",
         "Track procurement status (ordered / received / installed).",
     ]),
    (re.compile(r"\bfintech|nbfc|lending|loan|emi\b", re.I),
     lambda: [
         "Define KYC, AML, and regulator compliance scope.",
         "Specify EMI schedule, late fees, and collections workflow.",
         "Document data residency and audit log requirements.",
         "Identify partner integrations (bureau, eSign, eNACH).",
     ]),
    (re.compile(r"\bcoworking|co-working|workspace|erp\b", re.I),
     lambda: [
         "Model memberships, plans, add-ons, and renewals.",
         "Capture meeting-room booking and no-show policy.",
         "Define invoice, deposit, and refund flows.",
         "Specify access control and visitor management.",
     ]),
    (re.compile(r"\bkyc|masking|pii|redact|compliance\b", re.I),
     lambda: [
         "Define detection rules (regex + ML) and confidence thresholds.",
         "Specify masking strategy (full, partial, tokenisation).",
         "Document audit log and rollback behaviour.",
         "List supported languages and document formats.",
     ]),
    (re.compile(r"\bforecast|forecasting|ml|model|rag\b", re.I),
     lambda: [
         "Define training data sources, freshness, and licensing.",
         "Specify evaluation metrics and acceptable baselines.",
         "Document inference latency and cost budgets.",
         "Capture feedback loop for model improvement.",
     ]),
]


def get_checklist(idea: str) -> list[str]:
    """Return a checklist for the given product idea string."""
    idea = idea or ""
    extras: list[str] = []
    for pattern, fn in _DOMAIN_RULES:
        if pattern.search(idea):
            extras.extend(fn())
    # Dedupe while preserving order, cap at 12 items total.
    seen: set[str] = set()
    out: list[str] = []
    for item in GENERIC + extras:
        if item not in seen:
            seen.add(item)
            out.append(item)
        if len(out) >= 12:
            break
    return out
