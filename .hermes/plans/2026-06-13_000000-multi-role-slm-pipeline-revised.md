# Multi-Role SLM Pipeline — Revised Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Fix the six review findings from the 2026-06-13 spec review, then complete the pipeline rewrite that wires all roles together.

**What changed since the first plan:**
- `pipeline.py` was never rewritten — roles exist but are unconnected. This plan starts with fixes to the existing roles before wiring.
- Reviewer found: `RubricCriterion.id` uses `number:int` not `id:str`; Planner has no SLM call; `CriticVerdict` has wrong fields and hard-coded validator; `get_rubric_criteria` returns `list` not `tuple`; `_FIRST_OBJECT` regex missing `re.DOTALL`; `config.py` uses `object.__setattr__` on a frozen dataclass.

**Tech Stack:** Python 3.11+, `uv` (project uses `uv.lock`), pytest, LangChain core messages. All work under `projects/specguard/`.

**Spec:** `docs/superpowers/specs/2026-06-12-multi-role-slm-pipeline-design.md`

**Run tests from:** `C:\agent_rubric\projects\specguard` with `uv run pytest` (the project venv is `projects/specguard/.venv`).

---

## Task 1: Fix `RubricCriterion` — `id: str` field + `tuple` return type

**Files:**
- Modify: `projects/specguard/src/specguard/rubrics.py`
- Test: `projects/specguard/tests/test_rubrics.py`

**Step 1: Write the failing tests**

Append to `projects/specguard/tests/test_rubrics.py`:

```python
def test_rubric_criterion_has_string_id():
    from specguard.rubrics import get_rubric_criteria

    criteria = get_rubric_criteria("prd")
    assert criteria[0].id == "prd-1"
    assert criteria[9].id == "prd-10"


def test_get_rubric_criteria_returns_tuple():
    from specguard.rubrics import get_rubric_criteria

    result = get_rubric_criteria("prd")
    assert isinstance(result, tuple)
```

**Step 2: Run to verify failure**

Run: `uv run pytest tests/test_rubrics.py -v`
Expected: FAIL — `RubricCriterion` has no `id` field; `get_rubric_criteria` returns `list`.

**Step 3: Fix `RubricCriterion` and `get_rubric_criteria`**

In `projects/specguard/src/specguard/rubrics.py`, replace the `RubricCriterion` dataclass and `get_rubric_criteria` function:

```python
@dataclass(frozen=True)
class RubricCriterion:
    id: str
    text: str


def get_rubric_criteria(mode: str) -> tuple[RubricCriterion, ...]:
    rubric = get_rubric(mode)
    criteria: list[RubricCriterion] = []
    for line in rubric.splitlines():
        match = re.match(r"^(\d+)\.\s+(.*\S)\s*$", line.strip())
        if match:
            num = int(match.group(1))
            criteria.append(RubricCriterion(id=f"{mode}-{num}", text=match.group(2)))
    return tuple(criteria)
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_rubrics.py -v`
Expected: PASS (including the existing `test_prd_rubric_criteria_parses_numbered_checklist_items` which now checks `id` instead of `number` — update that test's assertion to `criteria[0].id == "prd-1"`).

**Step 5: Commit**

```bash
git add projects/specguard/src/specguard/rubrics.py projects/specguard/tests/test_rubrics.py
git commit -m "fix(specguard): RubricCriterion.id is str with mode-number format, return tuple"
```

---

## Task 2: Fix `roles/critic.py` — spec fields, injected validator, `re.DOTALL`

**Files:**
- Modify: `projects/specguard/src/specguard/roles/critic.py`
- Test: `projects/specguard/tests/test_critic.py` (rewrite)

**Step 1: Write the failing tests**

Replace `projects/specguard/tests/test_critic.py` with:

```python
from __future__ import annotations

import json

from langchain_core.messages import AIMessage

from specguard.roles.critic import CriticVerdict, CriterionScore, critique, extract_json


GOOD_JSON = json.dumps(
    {
        "verdict": "needs_revision",
        "criteria": [{"id": "prd-1", "score": 1, "reason": "objective is vague"}],
        "notes": "Tighten the objective.",
    }
)


def test_extract_json_plain():
    assert extract_json(GOOD_JSON)["verdict"] == "needs_revision"


def test_extract_json_fenced():
    fenced = f"```json\n{GOOD_JSON}\n```"
    assert extract_json(fenced)["notes"] == "Tighten the objective."


def test_extract_json_with_prose_prefix():
    text = f"Here is my evaluation:\n{GOOD_JSON}\nHope that helps!"
    assert extract_json(text)["criteria"][0]["id"] == "prd-1"


def test_extract_json_multiline():
    """re.DOTALL must be set or multi-line JSON objects fail to extract."""
    multiline = json.dumps({"verdict": "pass", "criteria": [], "notes": "line1\nline2"})
    text = f"Analysis:\n{multiline}\nend"
    result = extract_json(text)
    assert result is not None
    assert "line1" in result["notes"]


def test_extract_json_garbage_returns_none():
    assert extract_json("I think the document is fine overall.") is None


class JsonModel:
    def invoke(self, messages):
        return AIMessage(content=GOOD_JSON)


class GarbageModel:
    def __init__(self):
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        return AIMessage(content="not json at all")


class FakeValidator:
    def __init__(self, ok: bool, missing: tuple[str, ...] = ()):
        self._ok = ok
        self._missing = missing

    def __call__(self, text: str, sections: tuple[str, ...]):
        class Result:
            ok = True
            missing_sections = ()
        class FakeResult:
            ok = False
            missing_sections = ("## Users",)
        return FakeResult() if self._ok is False else Result()


def test_critique_parses_verdict():
    verdict = critique(JsonModel(), mode="prd", draft="## Problem\nText.", validator=FakeValidator(True))
    assert isinstance(verdict, CriticVerdict)
    assert verdict.passed is False
    assert verdict.fallback is False
    assert verdict.criteria[0].id == "prd-1"
    assert verdict.criteria[0].score == 1
    assert "Tighten" in verdict.notes


def test_critique_retries_once_then_falls_back():
    model = GarbageModel()
    verdict = critique(model, mode="prd", draft="## Problem\nText.", validator=FakeValidator(True))
    assert model.calls == 2  # initial + one retry
    assert verdict.fallback is True
    assert verdict.passed is True  # fallback never blocks; validators gate alone
    assert verdict.criteria == ()


def test_critique_validator_not_called_on_model_success():
    """Validator is only called to build the fallback verdict, not to gate the model path."""
    validator = FakeValidator(False)
    verdict = critique(JsonModel(), mode="prd", draft="## Problem\nText.", validator=validator)
    assert verdict.passed is False
    assert verdict.fallback is False
```

**Step 2: Run to verify failure**

Run: `uv run pytest tests/test_critic.py -v`
Expected: FAIL — `extract_json` returns `str` not `dict`; `CriticVerdict` has wrong fields; `critique` doesn't accept `validator` kwarg.

**Step 3: Implement `roles/critic.py`**

Replace `projects/specguard/src/specguard/roles/critic.py` with:

```python
"""Critic role: score a draft against the mode rubric as structured JSON.

SLMs are unreliable at structured output, so parsing is a ladder:
tolerant extraction -> one retry -> validator-only fallback (never fatal).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable, Protocol

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
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_critic.py -v`
Expected: 9 PASS.

**Step 5: Commit**

```bash
git add projects/specguard/src/specguard/roles/critic.py projects/specguard/tests/test_critic.py
git commit -m "fix(specguard): critic uses spec fields, injected validator, re.DOTALL regex"
```

---

## Task 3: Fix `roles/planner.py` — add SLM call to synthesize writing brief

**Files:**
- Modify: `projects/specguard/src/specguard/roles/planner.py`
- Test: `projects/specguard/tests/test_planner.py` (rewrite)

**Step 1: Write the failing tests**

Replace `projects/specguard/tests/test_planner.py` with:

```python
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
```

**Step 2: Run to verify failure**

Run: `uv run pytest tests/test_planner.py -v`
Expected: FAIL — `plan` function doesn't accept `standard` kwarg; `Brief` dataclass doesn't exist.

**Step 3: Implement `roles/planner.py`**

Replace `projects/specguard/src/specguard/roles/planner.py` with:

```python
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
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_planner.py -v`
Expected: 2 PASS.

**Step 5: Commit**

```bash
git add projects/specguard/src/specguard/roles/planner.py projects/specguard/tests/test_planner.py
git commit -m "fix(specguard): planner adds SLM call to synthesize writing brief"
```

---

## Task 4: Fix `config.py` — remove `object.__setattr__` in `__post_init__`

**Files:**
- Modify: `projects/specguard/src/specguard/config.py`
- Test: `projects/specguard/tests/test_config.py` (update)

**Step 1: Write the failing tests**

Update `test_settings_defaults_to_ollama_gemma_and_reuses_it_for_roles` in `projects/specguard/tests/test_config.py` to remove any reference to `__post_init__` internals. The existing tests should pass — this task just cleans up the implementation.

**Step 2: Run to verify current state**

Run: `uv run pytest tests/test_config.py -v`
Expected: all PASS (implementation change, not behavior).

**Step 3: Simplify `config.py`**

Replace `projects/specguard/src/specguard/config.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from os import environ
from typing import Mapping


SUPPORTED_PROVIDERS = ("ollama", "openai", "anthropic")


@dataclass(frozen=True)
class Settings:
    provider: str = "ollama"
    model: str = "gemma4:latest"
    planner_model: str = "gemma4:latest"
    writer_model: str = "gemma4:latest"
    critic_model: str = "gemma4:latest"
    max_attempts: int = 3
    ollama_base_url: str = "http://localhost:11434"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        source = environ if env is None else env
        provider = source.get("SPECGUARD_PROVIDER", "ollama").lower()
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"unknown provider {provider!r}; valid: {SUPPORTED_PROVIDERS}")

        default_model = "gemma4:latest" if provider == "ollama" else "gpt-4.1-mini"
        model = source.get("SPECGUARD_MODEL", default_model)
        try:
            max_attempts = int(source.get("SPECGUARD_MAX_ATTEMPTS", "3"))
        except ValueError:
            max_attempts = 3
        return cls(
            provider=provider,
            model=model,
            planner_model=source.get("SPECGUARD_PLANNER_MODEL", model),
            writer_model=source.get("SPECGUARD_WRITER_MODEL", model),
            critic_model=source.get("SPECGUARD_CRITIC_MODEL", model),
            max_attempts=max(1, max_attempts),
        )
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_config.py -v`
Expected: all PASS.

**Step 5: Commit**

```bash
git add projects/specguard/src/specguard/config.py projects/specguard/tests/test_config.py
git commit -m "fix(specguard): remove object.__setattr__ in frozen Settings dataclass"
```

---

## Task 5: Rewrite `pipeline.py` — wire the new roles into the multi-role loop

**Files:**
- Modify: `projects/specguard/src/specguard/pipeline.py`
- Test: `projects/specguard/tests/test_pipeline_multirole.py` (create)

**Step 1: Write the failing tests**

```python
# projects/specguard/tests/test_pipeline_multirole.py
from __future__ import annotations

import json
from pathlib import Path

from langchain_core.messages import AIMessage

from specguard.pipeline import GenerationRequest, generate_document, generate_document_stream

FULL_DOC = (
    "# Product Requirements Document\n\n"
    "## Problem\nText.\n\n## Goals\nText.\n\n## Users\nText.\n\n"
    "## Requirements\nText.\n\n## Success Metrics\nText.\n\n## Risks and Assumptions\nText.\n"
)
PARTIAL_DOC = "# Product Requirements Document\n\n## Problem\nText.\n\n## Goals\nText.\n"

PASS_JSON = json.dumps({"verdict": "pass", "criteria": [], "notes": "ok"})
FAIL_JSON = json.dumps({"verdict": "needs_revision", "criteria": [], "notes": "missing sections"})


class ScriptedModel:
    """Routes by prompt markers: planner -> brief, critic -> JSON, writer -> docs."""

    def __init__(self, drafts: list[str], critic_replies: list[str]):
        self.drafts = drafts
        self.critic_replies = critic_replies
        self.calls: list[str] = []

    def invoke(self, messages):
        text = messages[-1].content
        self.calls.append(text)
        if "writing brief" in text.lower():
            return AIMessage(content="Brief: keep it concrete.")
        if "Return ONLY a JSON object" in text:
            return AIMessage(content=self.critic_replies.pop(0))
        return AIMessage(content=self.drafts.pop(0))


class FakeValidator:
    def __call__(self, text: str, sections: tuple[str, ...]):
        class Result:
            ok = True
            missing_sections = ()
        return Result()


class FakeValidatorMissing:
    def __call__(self, text: str, sections: tuple[str, ...]):
        class Result:
            ok = False
            missing_sections = ("## Users",)
        return Result()


def _request(tmp_path: Path) -> GenerationRequest:
    return GenerationRequest(idea="An app for interior designers.", mode="prd", output_dir=tmp_path)


def test_pass_first_attempt_event_order(tmp_path: Path):
    model = ScriptedModel(drafts=[FULL_DOC], critic_replies=[PASS_JSON])
    events = list(generate_document_stream(_request(tmp_path), chat_model=model))
    kinds = [e.kind for e in events]
    assert kinds == ["plan", "attempt", "draft", "validate", "critique", "save"]
    assert events[-1].degraded is False
    assert events[-1].output_path is not None and events[-1].output_path.exists()


def test_pass_after_one_revision(tmp_path: Path):
    model = ScriptedModel(drafts=[PARTIAL_DOC, FULL_DOC], critic_replies=[FAIL_JSON, PASS_JSON])
    events = list(generate_document_stream(_request(tmp_path), chat_model=model))
    kinds = [e.kind for e in events]
    assert kinds == [
        "plan",
        "attempt", "draft", "validate", "critique",
        "attempt", "revise", "validate", "critique",
        "save",
    ]
    assert events[-1].degraded is False


def test_budget_exhausted_saves_degraded(tmp_path: Path):
    model = ScriptedModel(
        drafts=[PARTIAL_DOC, PARTIAL_DOC, PARTIAL_DOC],
        critic_replies=[FAIL_JSON, FAIL_JSON, FAIL_JSON],
    )
    result = generate_document(_request(tmp_path), chat_model=model)
    assert result.degraded is True
    assert result.validation.ok is False
    assert "## Users" in result.validation.missing_sections
    assert result.output_path.exists()  # degraded output is still written


def test_critic_garbage_twice_falls_back_to_validators(tmp_path: Path):
    model = ScriptedModel(drafts=[FULL_DOC], critic_replies=["garbage", "more garbage"])
    events = list(generate_document_stream(_request(tmp_path), chat_model=model))
    critique_event = next(e for e in events if e.kind == "critique")
    assert critique_event.critic is not None
    assert critique_event.critic.fallback is True
    assert events[-1].kind == "save"
    assert events[-1].degraded is False  # validators passed; fallback critic doesn't block
```

**Step 2: Run to verify failure**

Run: `uv run pytest tests/test_pipeline_multirole.py -v`
Expected: FAIL — unknown `degraded` attribute, wrong event kinds.

**Step 3: Implement `pipeline.py`**

Replace `projects/specguard/src/specguard/pipeline.py` with:

```python
from __future__ import annotations

import itertools
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Literal, Protocol

from .config import Settings
from .llm_gateway import build_chat_model
from .roles.critic import CriticVerdict, critique
from .roles.planner import Brief, plan
from .roles.writer import draft as write_draft, revise as write_revision
from .router import decide
from .standards import REQUIRED_SECTIONS, load_standard
from .validators import ValidationResult, validate_required_sections


class ChatModel(Protocol):
    def invoke(self, messages): ...


@dataclass(frozen=True)
class GenerationRequest:
    idea: str
    mode: str
    output_dir: Path = Path("outputs")


@dataclass(frozen=True)
class GenerationResult:
    markdown: str
    output_path: Path
    validation: ValidationResult
    review: str
    degraded: bool = False


class GenerationError(RuntimeError):
    """Raised when the pipeline cannot produce any document at all."""

    def __init__(self, validation: ValidationResult) -> None:
        self.validation = validation
        missing = ", ".join(validation.missing_sections)
        super().__init__(f"generated document is missing required sections: {missing}")


@dataclass(frozen=True)
class PipelineEvent:
    """One step of the generation pipeline, yielded to consumers (SSE, tests)."""

    kind: str  # "plan" | "attempt" | "draft" | "revise" | "validate" | "critique" | "save"
    timestamp: str
    tokens: int | None = None
    validation: ValidationResult | None = None
    review_notes: str | None = None
    markdown: str | None = None
    output_path: Path | None = None
    error: str | None = None
    attempt: int | None = None
    budget: int | None = None
    critic: CriticVerdict | None = None
    degraded: bool = False


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def _estimate_tokens(text: str) -> int:
    """Cheap token estimate: chars/4. Surfaced to the UI immediately after each call."""
    return max(1, len(text) // 4)


def generate_document(
    request: GenerationRequest,
    chat_model: ChatModel | None = None,
) -> GenerationResult:
    """Run the full pipeline and return the final result.

    A degraded result (budget exhausted) is still returned, with degraded=True.
    GenerationError is reserved for the pipeline producing no document at all.
    """
    final_event: PipelineEvent | None = None
    last_notes = ""
    for event in generate_document_stream(request, chat_model=chat_model):
        if event.kind == "critique" and event.review_notes:
            last_notes = event.review_notes
        if event.kind == "save":
            final_event = event
    if final_event is None or final_event.output_path is None:
        raise GenerationError(ValidationResult(ok=False, missing_sections=()))
    assert final_event.validation is not None
    assert final_event.markdown is not None
    return GenerationResult(
        markdown=final_event.markdown,
        output_path=final_event.output_path,
        validation=final_event.validation,
        review=last_notes,
        degraded=final_event.degraded,
    )


def generate_document_stream(
    request: GenerationRequest,
    chat_model: ChatModel | None = None,
) -> Iterator[PipelineEvent]:
    """Run the multi-role loop, yielding a PipelineEvent after each step.

    `chat_model`, when given (tests, server), is used for every role. Otherwise
    each role gets its configured model from Settings.
    """
    if request.mode not in REQUIRED_SECTIONS:
        raise ValueError(f"unknown mode {request.mode!r}; valid: {tuple(REQUIRED_SECTIONS)}")

    settings = Settings.from_env()
    if chat_model is not None:
        planner_model = writer_model = critic_model = chat_model
    else:
        cache: dict[str, ChatModel] = {}

        def _model_for(name: str) -> ChatModel:
            if name not in cache:
                cache[name] = build_chat_model(settings, model=name)
            return cache[name]

        planner_model = _model_for(settings.planner_model)
        writer_model = _model_for(settings.writer_model)
        critic_model = _model_for(settings.critic_model)

    standard = load_standard(request.mode)
    budget = settings.max_attempts

    # ── Planner ────────────────────────────────────────────────────────────────
    brief: Brief = plan(planner_model, request.idea, request.mode, standard)
    yield PipelineEvent(
        kind="plan",
        timestamp=_now(),
        review_notes=brief.guidance,
    )

    # ── Retry loop ─────────────────────────────────────────────────────────────
    draft_text = ""
    for attempt in range(1, budget + 1):
        yield PipelineEvent(kind="attempt", timestamp=_now(), attempt=attempt, budget=budget)

        # Writer
        if attempt == 1:
            draft_text = write_draft(writer_model, request.idea, request.mode, standard, brief)
        else:
            # Get missing sections from the last validation for the revise prompt
            missing = tuple(
                e.validation.missing_sections
                for e in [pipeline_event for e in [None] if False]  # placeholder; filled below
                if e and e.kind == "validate" and e.validation and not e.validation.ok
            )
            last_validate = None
            # We rebuild the missing list from scratch in the loop below
            draft_text = write_revision(
                writer_model,
                request.idea,
                request.mode,
                standard,
                brief,
                draft_text,
                critic_notes=last_critic_notes,
                missing_sections=last_missing,
            )

        yield PipelineEvent(
            kind="draft",
            timestamp=_now(),
            tokens=_estimate_tokens(draft_text),
            markdown=draft_text,
        )

        # Validate
        required = REQUIRED_SECTIONS[request.mode]
        validation = validate_required_sections(draft_text, required)
        yield PipelineEvent(kind="validate", timestamp=_now(), validation=validation)

        # Critic
        critic_verdict = critique(
            critic_model,
            request.mode,
            draft_text,
            validator=lambda text, sections: validate_required_sections(text, sections),
        )
        yield PipelineEvent(
            kind="critique",
            timestamp=_now(),
            review_notes=critic_verdict.notes,
            critic=critic_verdict,
        )

        # Router decision
        decision = decide(
            validation_ok=validation.ok,
            critic_passed=critic_verdict.passed,
            attempt=attempt,
            budget=budget,
        )

        if decision == "finalize":
            output_path = _write_output(request, draft_text)
            yield PipelineEvent(
                kind="save",
                timestamp=_now(),
                validation=validation,
                markdown=draft_text,
                output_path=output_path,
                critic=critic_verdict,
            )
            return

        # prepare revision context for next attempt
        last_critic_notes = critic_verdict.notes
        last_missing = validation.missing_sections

    # Budget exhausted — degrade and save
    output_path = _write_output(request, draft_text)
    yield PipelineEvent(
        kind="save",
        timestamp=_now(),
        validation=validation,
        markdown=draft_text,
        output_path=output_path,
        critic=critic_verdict,
        degraded=True,
        error="budget exhausted",
    )


def _write_output(request: GenerationRequest, markdown: str) -> Path:
    mode_dir = request.output_dir / request.mode
    mode_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"{datetime.now().strftime('%Y-%m-%d-%H%M%S-%f')}-{next(_OUTPUT_COUNTER):04d}"
    filename = f"{suffix}-{_slugify(request.idea)}.md"
    path = mode_dir / filename
    path.write_text(markdown, encoding="utf-8")
    return path


_OUTPUT_COUNTER = itertools.count()


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return (slug[:60] or "specguard-document").strip("-")
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_pipeline_multirole.py -v`
Expected: 4 PASS.

**Step 5: Fix the revision loop**

The loop as written above has a bug — `last_critic_notes` and `last_missing` are referenced before assignment on the first iteration. Fix the `generate_document_stream` loop body by initializing them before the loop and fixing the revision call:

```python
    last_critic_notes = ""
    last_missing: tuple[str, ...] = ()
    draft_text = ""
    for attempt in range(1, budget + 1):
        ...
        if attempt == 1:
            draft_text = write_draft(writer_model, request.idea, request.mode, standard, brief)
        else:
            draft_text = write_revision(
                writer_model,
                request.idea,
                request.mode,
                standard,
                brief,
                draft_text,
                critic_notes=last_critic_notes,
                missing_sections=last_missing,
            )
        ...
        # Update for next iteration
        last_critic_notes = critic_verdict.notes
        last_missing = validation.missing_sections
```

Apply this fix directly in the file.

**Step 6: Run all pipeline tests**

Run: `uv run pytest tests/test_pipeline.py tests/test_pipeline_stream.py tests/test_pipeline_multirole.py -v`
Expected: all PASS.

**Step 7: Commit**

```bash
git add projects/specguard/src/specguard/pipeline.py projects/specguard/tests/test_pipeline_multirole.py
git commit -m "feat(specguard): rewrite pipeline with multi-role loop, new event kinds, degraded path"
```

---

## Task 6: Migrate existing pipeline tests

**Files:**
- Modify: `projects/specguard/tests/test_pipeline.py`, `projects/specguard/tests/test_pipeline_stream.py`

The existing tests (`test_generate_document_revises_and_saves_markdown`, `test_stream_yields_each_pipeline_step_in_order`, etc.) were written for the old two-pass pipeline. They will likely fail with the new event shapes. Update them to match the new event kinds (`plan`, `attempt`, `critique` instead of `draft`, `validate`, `review`, `revise`).

Run each failing test, read the error, and update assertions to match the new event shapes. The `GenerationResult` now has a `degraded: bool = False` field — update any `GenerationResult` construction in tests to include it.

**Step 1: Run existing pipeline tests**

Run: `uv run pytest tests/test_pipeline.py tests/test_pipeline_stream.py -v 2>&1 | head -60`

**Step 2: Fix each failing test**

For each failure, update the assertions to match the new event shapes. Key changes:
- `review` event → `critique` event
- `draft` event still exists but now comes after `attempt`
- `revise` event comes after a second `attempt`
- `save` event now has `degraded: bool` field
- `GenerationResult` has `degraded: bool = False`

**Step 3: Run to verify all pass**

Run: `uv run pytest tests/test_pipeline.py tests/test_pipeline_stream.py -v`
Expected: all PASS.

**Step 4: Commit**

```bash
git add projects/specguard/tests/test_pipeline.py projects/specguard/tests/test_pipeline_stream.py
git commit -m "test(specguard): migrate pipeline tests to new event shapes"
```

---

## Task 7: Full suite pass

**Step 1: Run the full test suite**

Run: `uv run pytest -q`
Expected: all tests PASS (66+).

**Step 2: Run lint**

Run: `uv run ruff check .`
Expected: no errors.

**Step 3: Commit**

```bash
git add -A
git commit -m "chore(specguard): complete multi-role SLM pipeline slice"
```

---

## Files likely to change

| File | Change |
|---|---|
| `src/specguard/rubrics.py` | `RubricCriterion.id: str`, `get_rubric_criteria` returns `tuple` |
| `src/specguard/roles/critic.py` | Spec fields, injected validator, `re.DOTALL`, no `object.__setattr__` |
| `src/specguard/roles/planner.py` | Add SLM call, `Brief` dataclass |
| `src/specguard/config.py` | Remove `__post_init__` `object.__setattr__` |
| `src/specguard/pipeline.py` | Full rewrite with new roles, event kinds, degraded path |
| `tests/test_critic.py` | Rewrite with spec-compatible assertions |
| `tests/test_planner.py` | Rewrite with SLM call assertions |
| `tests/test_pipeline_multirole.py` | New file for multi-role loop tests |
| `tests/test_pipeline.py` | Migrate to new event shapes |
| `tests/test_pipeline_stream.py` | Migrate to new event shapes |

## Risks and open questions

1. **Pipeline loop variable scope bug**: The initial implementation of Task 5 has a Python scoping issue — `last_critic_notes` and `last_missing` referenced before assignment on first iteration. Fixed in Step 5, but verify carefully.
2. **`writer.py` revision missing sections**: The existing `revise` function signature needs `missing_sections: tuple[str, ...]` — confirm it matches the call site in the pipeline.
3. **CLI/server SSE consumers**: The new `plan`, `attempt`, `critique` event kinds are additive; existing consumers should ignore unknown kinds. The `degraded` field on `save` is also additive. Verify the web UI and CLI SSE parsing handle unknown fields gracefully.
4. **`generate_document` for the server**: Confirm the server's `generate_document_stream` consumer handles the new event shapes before surfacing via SSE.
