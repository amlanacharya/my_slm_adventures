"""Critic role: score a draft against the mode rubric as structured JSON.

SLMs are unreliable at structured output, so parsing is a ladder:
tolerant extraction -> one retry -> validator-only fallback (never fatal).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol

from langchain_core.messages import HumanMessage, SystemMessage

from ..rubrics import get_rubric_criteria


class Validator(Protocol):
    """Validates a draft against required sections. Returns ValidationResult."""
    def __call__(self, text: str, sections: tuple[str, ...]) -> "ValidationResult": ...


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    missing_sections: tuple[str, ...]


@dataclass(frozen=True)
class CriterionScore:
    id: str
    score: int
    reason: str


@dataclass(frozen=True)
class CriticVerdict:
    passed: bool
    criteria: tuple[CriterionScore, ...]
    notes: str
    fallback: bool = False


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)
_FIRST_OBJECT = re.compile(r"\{.*\}", re.S)


def extract_json(text: str) -> dict | None:
    """Pull the first JSON object out of model output, tolerating fences and prose."""
    fenced = _FENCE.search(text)
    candidate = fenced.group(1) if fenced else text
    start = candidate.find("{")
    if start == -1:
        return None
    decoder = json.JSONDecoder()
    try:
        obj, _ = decoder.raw_decode(candidate[start:])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def critique(
    model,
    mode: str,
    draft: str,
    *,
    validator: Validator,
) -> CriticVerdict:
    """Score the draft. Retries bad JSON once, then falls back to a non-blocking verdict."""
    prompt = _critic_prompt(mode, draft)
    for _ in range(2):
        raw = model.invoke(
            [
                SystemMessage(content="You are SpecGuard's critic. Respond with JSON only."),
                HumanMessage(content=prompt),
            ]
        )
        content = getattr(raw, "content", raw)
        data = extract_json(content if isinstance(content, str) else str(content))
        if data is not None:
            return _verdict_from(data)
    # Fallback: never block the loop on critic failure; validators gate alone.
    return CriticVerdict(passed=True, criteria=(), notes="critic unavailable (invalid JSON)", fallback=True)


def _verdict_from(data: dict) -> CriticVerdict:
    criteria = tuple(
        CriterionScore(
            id=str(c.get("id", "")),
            score=int(c.get("score", 0)),
            reason=str(c.get("reason", "")),
        )
        for c in data.get("criteria", [])
        if isinstance(c, dict)
    )
    return CriticVerdict(
        passed=data.get("verdict") == "pass",
        criteria=criteria,
        notes=str(data.get("notes", "")),
        fallback=False,
    )


def _critic_prompt(mode: str, draft: str) -> str:
    criteria = get_rubric_criteria(mode)
    criteria_lines = "\n".join(f"- {c.id}: {c.text}" for c in criteria)
    return (
        f"Score this {mode} draft against each criterion (0=fail, 1=partial, 2=pass).\n"
        "Return ONLY a JSON object with this exact shape:\n"
        '{"verdict": "pass" | "needs_revision", '
        '"criteria": [{"id": "...", "score": 0, "reason": "..."}], '
        '"notes": "actionable findings for the writer"}\n'
        'Use "pass" only if every criterion scores 2.\n\n'
        f"Criteria:\n{criteria_lines}\n\nDraft:\n{draft}"
    )
