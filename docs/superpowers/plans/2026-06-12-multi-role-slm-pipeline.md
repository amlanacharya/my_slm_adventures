# Multi-Role SLM Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace SpecGuard's fixed two-pass generation loop with a Planner/Writer/Critic multi-role pipeline coordinated by a deterministic Router with a retry budget.

**Architecture:** Three role modules (`roles/planner.py`, `roles/writer.py`, `roles/critic.py`) each expose one pure-ish function taking a chat model + inputs. A pure-Python `router.py` decides finalize/revise/degrade from validator + critic results. `pipeline.py` keeps its public contract (`generate_document`, `generate_document_stream`, `PipelineEvent`) but orchestrates the new loop and emits new event kinds (`plan`, `attempt`, `critique`). Budget exhaustion saves a draft-with-warnings (`degraded=True`) instead of raising.

**Tech Stack:** Python 3.11+, LangChain core messages, Ollama via `llm_gateway`, pytest. All work under `projects/specguard/`.

**Spec:** `docs/superpowers/specs/2026-06-12-multi-role-slm-pipeline-design.md`

**Run tests from:** `C:\agent_rubric\projects\specguard` with `python -m pytest` (the project venv is `projects/specguard/.venv`).

---

### Task 1: Per-role model config + retry budget in Settings

**Files:**
- Modify: `projects/specguard/src/specguard/config.py`
- Test: `projects/specguard/tests/test_config.py` (create)

- [ ] **Step 1: Write the failing tests**

```python
# projects/specguard/tests/test_config.py
from __future__ import annotations

from specguard.config import Settings


def test_role_models_default_to_shared_model():
    s = Settings.from_env(env={"SPECGUARD_MODEL": "gemma4:latest"})
    assert s.planner_model == "gemma4:latest"
    assert s.writer_model == "gemma4:latest"
    assert s.critic_model == "gemma4:latest"


def test_role_models_overridable_per_role():
    s = Settings.from_env(
        env={
            "SPECGUARD_MODEL": "gemma4:latest",
            "SPECGUARD_CRITIC_MODEL": "phi4:latest",
        }
    )
    assert s.writer_model == "gemma4:latest"
    assert s.critic_model == "phi4:latest"


def test_max_attempts_default_and_override():
    assert Settings.from_env(env={}).max_attempts == 3
    assert Settings.from_env(env={"SPECGUARD_MAX_ATTEMPTS": "5"}).max_attempts == 5


def test_max_attempts_floor_is_one():
    assert Settings.from_env(env={"SPECGUARD_MAX_ATTEMPTS": "0"}).max_attempts == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL — `Settings` has no attribute `planner_model` / `max_attempts`.

- [ ] **Step 3: Implement**

Replace `projects/specguard/src/specguard/config.py` content with:

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
    ollama_base_url: str = "http://localhost:11434"
    planner_model: str = "gemma4:latest"
    writer_model: str = "gemma4:latest"
    critic_model: str = "gemma4:latest"
    max_attempts: int = 3

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
            ollama_base_url=source.get("OLLAMA_BASE_URL", "http://localhost:11434"),
            planner_model=source.get("SPECGUARD_PLANNER_MODEL", model),
            writer_model=source.get("SPECGUARD_WRITER_MODEL", model),
            critic_model=source.get("SPECGUARD_CRITIC_MODEL", model),
            max_attempts=max(1, max_attempts),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Run the whole suite (config is widely imported)**

Run: `python -m pytest -q`
Expected: all pass (existing `Settings(...)` constructions still work — new fields have defaults).

- [ ] **Step 6: Commit**

```bash
git add projects/specguard/src/specguard/config.py projects/specguard/tests/test_config.py
git commit -m "feat(specguard): per-role model config and retry budget in Settings"
```

---

### Task 2: Model override in llm_gateway

**Files:**
- Modify: `projects/specguard/src/specguard/llm_gateway.py`
- Test: `projects/specguard/tests/test_llm_gateway.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `projects/specguard/tests/test_llm_gateway.py`:

```python
def test_build_chat_model_accepts_model_override():
    from specguard.config import Settings
    from specguard.llm_gateway import build_chat_model

    settings = Settings(provider="ollama", model="gemma4:latest")
    chat = build_chat_model(settings, model="phi4:latest")
    assert chat.model == "phi4:latest"


def test_build_chat_model_without_override_uses_settings_model():
    from specguard.config import Settings
    from specguard.llm_gateway import build_chat_model

    settings = Settings(provider="ollama", model="gemma4:latest")
    chat = build_chat_model(settings)
    assert chat.model == "gemma4:latest"
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_llm_gateway.py -v`
Expected: FAIL — `build_chat_model() got an unexpected keyword argument 'model'`.

- [ ] **Step 3: Implement**

Replace `build_chat_model` in `projects/specguard/src/specguard/llm_gateway.py` with:

```python
def build_chat_model(settings: Settings | None = None, model: str | None = None) -> BaseChatModel:
    resolved = settings or Settings.from_env()
    model_name = model or resolved.model

    if resolved.provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(model=model_name, base_url=resolved.ollama_base_url)

    if resolved.provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model_name)

    if resolved.provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:
            raise RuntimeError("install the anthropic extra to use SPECGUARD_PROVIDER=anthropic") from exc

        return ChatAnthropic(model=model_name)  # type: ignore[call-arg]

    raise ValueError(f"unknown provider {resolved.provider!r}; valid: {SUPPORTED_PROVIDERS}")
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_llm_gateway.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add projects/specguard/src/specguard/llm_gateway.py projects/specguard/tests/test_llm_gateway.py
git commit -m "feat(specguard): optional model override in build_chat_model"
```

---

### Task 3: Structured rubric criteria

**Files:**
- Modify: `projects/specguard/src/specguard/rubrics.py`
- Test: `projects/specguard/tests/test_rubrics.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `projects/specguard/tests/test_rubrics.py`:

```python
def test_get_rubric_criteria_returns_one_criterion_per_numbered_item():
    from specguard.rubrics import get_rubric_criteria

    criteria = get_rubric_criteria("prd")
    assert len(criteria) == 10
    assert criteria[0].id == "prd-1"
    assert "objective" in criteria[0].text.lower()


def test_get_rubric_criteria_unknown_mode_raises():
    import pytest

    from specguard.rubrics import ModeError, get_rubric_criteria

    with pytest.raises(ModeError):
        get_rubric_criteria("nope")
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_rubrics.py -v`
Expected: FAIL — cannot import `get_rubric_criteria`.

- [ ] **Step 3: Implement**

Append to `projects/specguard/src/specguard/rubrics.py` (keep everything existing — `get_rubric` stays for `agent.py`):

```python
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RubricCriterion:
    id: str
    text: str


_ITEM = re.compile(r"^(\d+)\.\s+(.*)$")


def get_rubric_criteria(mode: str) -> tuple[RubricCriterion, ...]:
    """Parse the numbered checklist items of a mode's rubric into criteria."""
    prose = get_rubric(mode)  # raises ModeError for unknown modes
    out: list[RubricCriterion] = []
    for line in prose.splitlines():
        m = _ITEM.match(line.strip())
        if m:
            out.append(RubricCriterion(id=f"{mode}-{m.group(1)}", text=m.group(2)))
    return tuple(out)
```

(Place the `import re` and `from dataclasses import dataclass` at the top of the file with the other imports.)

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_rubrics.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add projects/specguard/src/specguard/rubrics.py projects/specguard/tests/test_rubrics.py
git commit -m "feat(specguard): structured rubric criteria accessor"
```

---

### Task 4: Router decision function

**Files:**
- Create: `projects/specguard/src/specguard/router.py`
- Test: `projects/specguard/tests/test_router.py` (create)

- [ ] **Step 1: Write the failing tests**

```python
# projects/specguard/tests/test_router.py
from __future__ import annotations

from specguard.router import decide


def test_finalize_when_validators_and_critic_pass():
    assert decide(validation_ok=True, critic_passed=True, attempt=1, budget=3) == "finalize"


def test_revise_when_validators_fail_and_budget_remains():
    assert decide(validation_ok=False, critic_passed=True, attempt=1, budget=3) == "revise"


def test_revise_when_critic_fails_and_budget_remains():
    assert decide(validation_ok=True, critic_passed=False, attempt=2, budget=3) == "revise"


def test_degrade_when_budget_exhausted():
    assert decide(validation_ok=False, critic_passed=False, attempt=3, budget=3) == "degrade"


def test_finalize_wins_even_on_last_attempt():
    assert decide(validation_ok=True, critic_passed=True, attempt=3, budget=3) == "finalize"
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_router.py -v`
Expected: FAIL — no module `specguard.router`.

- [ ] **Step 3: Implement**

```python
# projects/specguard/src/specguard/router.py
"""Deterministic routing for the multi-role pipeline. No SLM calls here."""
from __future__ import annotations

from typing import Literal

Decision = Literal["finalize", "revise", "degrade"]


def decide(*, validation_ok: bool, critic_passed: bool, attempt: int, budget: int) -> Decision:
    """Combine deterministic validation with the critic verdict.

    finalize — both gates pass.
    revise   — a gate failed but attempts remain.
    degrade  — budget exhausted; the caller saves a draft-with-warnings.
    """
    if validation_ok and critic_passed:
        return "finalize"
    if attempt < budget:
        return "revise"
    return "degrade"
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_router.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add projects/specguard/src/specguard/router.py projects/specguard/tests/test_router.py
git commit -m "feat(specguard): deterministic router decision function"
```

---

### Task 5: Critic role — JSON extraction, verdict, fallback

**Files:**
- Create: `projects/specguard/src/specguard/roles/__init__.py` (empty file)
- Create: `projects/specguard/src/specguard/roles/critic.py`
- Test: `projects/specguard/tests/test_critic.py` (create)

- [ ] **Step 1: Write the failing tests**

```python
# projects/specguard/tests/test_critic.py
from __future__ import annotations

import json

from langchain_core.messages import AIMessage

from specguard.roles.critic import CriticVerdict, critique, extract_json


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


def test_critique_parses_verdict():
    verdict = critique(JsonModel(), mode="prd", draft="## Problem\nText.")
    assert isinstance(verdict, CriticVerdict)
    assert verdict.passed is False
    assert verdict.fallback is False
    assert verdict.criteria[0].id == "prd-1"
    assert verdict.criteria[0].score == 1
    assert "Tighten" in verdict.notes


def test_critique_retries_once_then_falls_back():
    model = GarbageModel()
    verdict = critique(model, mode="prd", draft="## Problem\nText.")
    assert model.calls == 2  # initial + one retry
    assert verdict.fallback is True
    assert verdict.passed is True  # fallback never blocks; validators gate alone
    assert verdict.criteria == ()
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_critic.py -v`
Expected: FAIL — no module `specguard.roles`.

- [ ] **Step 3: Implement**

Create empty `projects/specguard/src/specguard/roles/__init__.py`, then:

```python
# projects/specguard/src/specguard/roles/critic.py
"""Critic role: score a draft against the mode rubric as structured JSON.

SLMs are unreliable at structured output, so parsing is a ladder:
tolerant extraction -> one retry -> validator-only fallback (never fatal).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage

from ..rubrics import get_rubric_criteria


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


def critique(model, mode: str, draft: str) -> CriticVerdict:
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

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_critic.py -v`
Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add projects/specguard/src/specguard/roles/ projects/specguard/tests/test_critic.py
git commit -m "feat(specguard): critic role with scored rubric JSON and fallback ladder"
```

---

### Task 6: Planner role — deterministic tools + writing brief

**Files:**
- Create: `projects/specguard/src/specguard/roles/planner.py`
- Test: `projects/specguard/tests/test_planner.py` (create)

- [ ] **Step 1: Write the failing tests**

```python
# projects/specguard/tests/test_planner.py
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

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_planner.py -v`
Expected: FAIL — no module `specguard.roles.planner`.

- [ ] **Step 3: Implement**

```python
# projects/specguard/src/specguard/roles/planner.py
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

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_planner.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add projects/specguard/src/specguard/roles/planner.py projects/specguard/tests/test_planner.py
git commit -m "feat(specguard): planner role with deterministic tools and writing brief"
```

---

### Task 7: Writer role — draft and revise

**Files:**
- Create: `projects/specguard/src/specguard/roles/writer.py`
- Test: `projects/specguard/tests/test_writer.py` (create)

- [ ] **Step 1: Write the failing tests**

```python
# projects/specguard/tests/test_writer.py
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_writer.py -v`
Expected: FAIL — no module `specguard.roles.writer`.

- [ ] **Step 3: Implement**

```python
# projects/specguard/src/specguard/roles/writer.py
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
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_writer.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add projects/specguard/src/specguard/roles/writer.py projects/specguard/tests/test_writer.py
git commit -m "feat(specguard): writer role with draft and revise prompts"
```

---

### Task 8: Rewrite the pipeline orchestrator

**Files:**
- Modify: `projects/specguard/src/specguard/pipeline.py`
- Test: `projects/specguard/tests/test_pipeline_multirole.py` (create)

This task replaces the loop internals. The public names stay: `GenerationRequest`, `GenerationResult`, `GenerationError`, `PipelineEvent`, `generate_document`, `generate_document_stream`. New `PipelineEvent` fields: `attempt`, `budget`, `critic`, `degraded`. New kinds: `plan`, `attempt`, `critique`. The `review` kind is no longer emitted. `GenerationResult` gains `degraded: bool = False`. Budget exhaustion **saves** with `degraded=True` instead of raising.

- [ ] **Step 1: Write the failing tests**

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
    critique = next(e for e in events if e.kind == "critique")
    assert critique.critic is not None
    assert critique.critic.fallback is True
    assert events[-1].kind == "save"
    assert events[-1].degraded is False  # validators passed; fallback critic doesn't block
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_pipeline_multirole.py -v`
Expected: FAIL — wrong event kinds / unknown `degraded` attribute.

- [ ] **Step 3: Implement**

Replace `projects/specguard/src/specguard/pipeline.py` with:

```python
from __future__ import annotations

import itertools
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Protocol

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

    # 1. Plan
    brief = plan(planner_model, idea=request.idea, mode=request.mode, standard=standard)
    yield PipelineEvent(
        kind="plan",
        timestamp=_now(),
        tokens=_estimate_tokens(brief.guidance),
        review_notes=brief.guidance,
    )

    # 2. Draft / critique / revise loop
    current_draft = ""
    validation = ValidationResult(ok=False, missing_sections=())
    verdict = CriticVerdict(passed=False, criteria=(), notes="")
    for attempt in range(1, budget + 1):
        yield PipelineEvent(kind="attempt", timestamp=_now(), attempt=attempt, budget=budget)

        if attempt == 1:
            current_draft = write_draft(
                writer_model, idea=request.idea, mode=request.mode, standard=standard, brief=brief
            )
            kind = "draft"
        else:
            current_draft = write_revision(
                writer_model,
                idea=request.idea,
                mode=request.mode,
                standard=standard,
                brief=brief,
                previous_draft=current_draft,
                critic_notes=verdict.notes,
                missing_sections=validation.missing_sections,
            )
            kind = "revise"
        yield PipelineEvent(
            kind=kind, timestamp=_now(), tokens=_estimate_tokens(current_draft), attempt=attempt
        )

        validation = validate_required_sections(current_draft, REQUIRED_SECTIONS[request.mode])
        yield PipelineEvent(kind="validate", timestamp=_now(), validation=validation, attempt=attempt)

        verdict = critique(critic_model, mode=request.mode, draft=current_draft)
        yield PipelineEvent(
            kind="critique",
            timestamp=_now(),
            critic=verdict,
            review_notes=verdict.notes,
            attempt=attempt,
        )

        decision = decide(
            validation_ok=validation.ok,
            critic_passed=verdict.passed,
            attempt=attempt,
            budget=budget,
        )
        if decision == "finalize":
            break
        if decision == "degrade":
            break
        # decision == "revise": loop continues

    degraded = not (validation.ok and verdict.passed)
    output_path = _write_output(request, current_draft)
    yield PipelineEvent(
        kind="save",
        timestamp=_now(),
        validation=validation,
        markdown=current_draft,
        output_path=output_path,
        degraded=degraded,
        error="budget exhausted; saved draft with warnings" if degraded else None,
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

Note the `degraded` computation: a critic in fallback mode reports `passed=True`, so a validator-pass + fallback-critic save is NOT degraded — by design (validator-only gating).

- [ ] **Step 4: Run the new tests**

Run: `python -m pytest tests/test_pipeline_multirole.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit (old tests are fixed in Task 9 — commit just the new unit)**

```bash
git add projects/specguard/src/specguard/pipeline.py projects/specguard/tests/test_pipeline_multirole.py
git commit -m "feat(specguard): multi-role pipeline loop with router and degrade path"
```

---

### Task 9: Update legacy pipeline tests to the new contract

**Files:**
- Modify: `projects/specguard/tests/test_pipeline.py`
- Modify: `projects/specguard/tests/test_pipeline_stream.py`

The old fakes route on "Review"/"Revise" markers and expect the old event order. Rewrite both files against the new contract. The old `test_generate_document_fails_when_final_revision_is_invalid` inverts: degraded results are now *returned*, not raised.

- [ ] **Step 1: Replace `tests/test_pipeline.py`**

```python
from __future__ import annotations

import json
from pathlib import Path

from langchain_core.messages import AIMessage

from specguard.pipeline import GenerationRequest, generate_document

FULL_DOC = (
    "# Product Requirements Document\n\n"
    "## Problem\nText.\n\n## Goals\nText.\n\n## Users\nText.\n\n"
    "## Requirements\nText.\n\n## Success Metrics\nText.\n\n## Risks and Assumptions\nText.\n"
)
PARTIAL_DOC = "# Product Requirements Document\n\n## Problem\nText.\n"
PASS_JSON = json.dumps({"verdict": "pass", "criteria": [], "notes": "ok"})
FAIL_JSON = json.dumps({"verdict": "needs_revision", "criteria": [], "notes": "incomplete"})


class RoleFake:
    """Minimal marker-routing fake: planner -> brief, critic -> scripted JSON, writer -> scripted docs."""

    def __init__(self, drafts: list[str], critic_replies: list[str]):
        self.drafts = drafts
        self.critic_replies = critic_replies
        self.calls: list[str] = []

    def invoke(self, messages):
        text = messages[-1].content
        self.calls.append(text)
        if "writing brief" in text.lower():
            return AIMessage(content="Brief: be concrete.")
        if "Return ONLY a JSON object" in text:
            return AIMessage(content=self.critic_replies.pop(0))
        return AIMessage(content=self.drafts.pop(0))


def _request(tmp_path: Path) -> GenerationRequest:
    return GenerationRequest(idea="Build an app for interior designers.", mode="prd", output_dir=tmp_path)


def test_generate_document_revises_and_saves_markdown(tmp_path: Path):
    model = RoleFake(drafts=[PARTIAL_DOC, FULL_DOC], critic_replies=[FAIL_JSON, PASS_JSON])

    result = generate_document(_request(tmp_path), chat_model=model)

    assert result.validation.ok is True
    assert result.degraded is False
    assert result.output_path.exists()
    assert "## Users" in result.markdown


def test_generate_document_returns_degraded_when_never_valid(tmp_path: Path):
    model = RoleFake(
        drafts=[PARTIAL_DOC, PARTIAL_DOC, PARTIAL_DOC],
        critic_replies=[FAIL_JSON, FAIL_JSON, FAIL_JSON],
    )

    result = generate_document(_request(tmp_path), chat_model=model)

    assert result.degraded is True
    assert result.validation.ok is False
    assert "## Goals" in result.validation.missing_sections
    assert result.output_path.exists()  # degraded draft is still saved


def test_generate_document_does_not_overwrite_same_day_outputs(tmp_path: Path):
    def fresh():
        return RoleFake(drafts=[FULL_DOC], critic_replies=[PASS_JSON])

    first = generate_document(_request(tmp_path), chat_model=fresh())
    second = generate_document(_request(tmp_path), chat_model=fresh())

    assert first.output_path != second.output_path
    assert first.output_path.exists()
    assert second.output_path.exists()
```

- [ ] **Step 2: Replace `tests/test_pipeline_stream.py`**

```python
from __future__ import annotations

import json
from pathlib import Path

from langchain_core.messages import AIMessage

from specguard.pipeline import GenerationRequest, generate_document_stream

FULL_DOC = (
    "# Product Requirements Document\n\n"
    "## Problem\nText.\n\n## Goals\nText.\n\n## Users\nText.\n\n"
    "## Requirements\nText.\n\n## Success Metrics\nText.\n\n## Risks and Assumptions\nText.\n"
)
PASS_JSON = json.dumps({"verdict": "pass", "criteria": [], "notes": "ok"})


class PassFirstTryFake:
    def invoke(self, messages):
        text = messages[-1].content
        if "writing brief" in text.lower():
            return AIMessage(content="Brief: be concrete.")
        if "Return ONLY a JSON object" in text:
            return AIMessage(content=PASS_JSON)
        return AIMessage(content=FULL_DOC)


def _request(tmp_path: Path) -> GenerationRequest:
    return GenerationRequest(idea="Build an app for interior designers.", mode="prd", output_dir=tmp_path)


def test_stream_yields_each_pipeline_step_in_order(tmp_path: Path):
    events = list(generate_document_stream(_request(tmp_path), chat_model=PassFirstTryFake()))
    kinds = [e.kind for e in events]
    assert kinds == ["plan", "attempt", "draft", "validate", "critique", "save"]


def test_stream_final_event_carries_output_path_and_validation(tmp_path: Path):
    events = list(generate_document_stream(_request(tmp_path), chat_model=PassFirstTryFake()))
    final = events[-1]
    assert final.kind == "save"
    assert final.validation is not None and final.validation.ok is True
    assert final.degraded is False
    assert final.output_path is not None and final.output_path.exists()
    assert final.markdown is not None and "## Users" in final.markdown


def test_stream_draft_event_records_token_count(tmp_path: Path):
    events = list(generate_document_stream(_request(tmp_path), chat_model=PassFirstTryFake()))
    draft = next(e for e in events if e.kind == "draft")
    assert draft.tokens is not None and draft.tokens > 0
    assert draft.timestamp is not None
    assert draft.attempt == 1
```

- [ ] **Step 3: Run both files**

Run: `python -m pytest tests/test_pipeline.py tests/test_pipeline_stream.py -v`
Expected: all PASS.

- [ ] **Step 4: Run the full suite — fix any remaining consumers**

Run: `python -m pytest -q`

Expected wrinkles to fix if they appear:
- `tests/test_cli.py` — if it asserts on `GenerationError` for invalid output, change the assertion: the CLI now reports a degraded save (see Task 10) instead of failing.
- `tests/test_server.py` — its injected fake returns a full valid doc for every call; under the new loop the critic receives that doc, fails to parse it as JSON twice, and falls back to validator-only gating, so generations still succeed. If the test asserts an exact event-kind sequence, update it to `["plan", "attempt", "draft", "validate", "critique", "save"]`.

- [ ] **Step 5: Commit**

```bash
git add projects/specguard/tests/
git commit -m "test(specguard): migrate pipeline tests to multi-role contract"
```

---

### Task 10: Surface new events in server SSE + CLI degrade reporting

**Files:**
- Modify: `projects/specguard/src/specguard/server.py` (`_event_to_dict`, around line 140)
- Modify: `projects/specguard/src/specguard/cli.py` (`generate` command and `_print_result`)
- Test: `projects/specguard/tests/test_server.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `projects/specguard/tests/test_server.py`:

```python
def test_event_to_dict_serializes_multirole_fields():
    from dataclasses import asdict

    from specguard.pipeline import PipelineEvent
    from specguard.roles.critic import CriterionScore, CriticVerdict
    from specguard.server import _event_to_dict

    verdict = CriticVerdict(
        passed=False,
        criteria=(CriterionScore(id="prd-1", score=1, reason="vague"),),
        notes="tighten",
        fallback=False,
    )
    event = PipelineEvent(
        kind="critique",
        timestamp="12:00:00.000",
        critic=verdict,
        review_notes="tighten",
        attempt=2,
        budget=3,
        degraded=False,
    )
    d = _event_to_dict(event)
    assert d["attempt"] == 2
    assert d["budget"] == 3
    assert d["critic"]["passed"] is False
    assert d["critic"]["criteria"][0]["id"] == "prd-1"
    assert "degraded" not in d  # only serialized when True


def test_event_to_dict_serializes_degraded_save():
    from specguard.pipeline import PipelineEvent
    from specguard.server import _event_to_dict

    event = PipelineEvent(kind="save", timestamp="12:00:00.000", degraded=True)
    assert _event_to_dict(event)["degraded"] is True
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_server.py -v -k multirole or degraded`
(Exact command: `python -m pytest tests/test_server.py -v -k "multirole or degraded"`)
Expected: FAIL — KeyError `attempt`.

- [ ] **Step 3: Update `_event_to_dict` in server.py**

Replace the existing `_event_to_dict` with:

```python
def _event_to_dict(event: PipelineEvent) -> dict:
    """Convert a PipelineEvent into a JSON-safe dict for SSE."""
    d: dict = {"kind": event.kind, "timestamp": event.timestamp}
    if event.tokens is not None:
        d["tokens"] = event.tokens
    if event.validation is not None:
        d["validation"] = asdict(event.validation)
    if event.review_notes is not None:
        d["review_notes"] = event.review_notes
    if event.markdown is not None:
        d["markdown"] = event.markdown
    if event.output_path is not None:
        d["output_path"] = str(event.output_path)
    if event.error is not None:
        d["error"] = event.error
    if event.attempt is not None:
        d["attempt"] = event.attempt
    if event.budget is not None:
        d["budget"] = event.budget
    if event.critic is not None:
        d["critic"] = asdict(event.critic)
    if event.degraded:
        d["degraded"] = True
    return d
```

- [ ] **Step 4: Update the CLI for the degrade path**

In `projects/specguard/src/specguard/cli.py`, replace the `generate` command body and `_print_result`:

```python
@main.command()
@click.argument("idea")
@click.option("--mode", type=click.Choice(tuple(REQUIRED_SECTIONS)), default="prd", show_default=True)
@click.option("--output-dir", type=click.Path(path_type=Path), default=Path("outputs"), show_default=True)
def generate(idea: str, mode: str, output_dir: Path) -> None:
    """Generate a PRD, BRD, or technical scope."""
    result = generate_document(GenerationRequest(idea=idea, mode=mode, output_dir=output_dir))
    _print_result(result)


def _print_result(result) -> None:
    click.echo(f"wrote: {result.output_path}")
    if result.degraded:
        missing = ", ".join(result.validation.missing_sections) or "rubric criteria not met"
        click.echo(
            click.style(
                f"saved with warnings after retry budget: {missing}",
                fg="yellow",
            )
        )
```

Keep the `GenerationError` import in `cli.py` removed if now unused (drop `GenerationError` from the import line; keep `GenerationRequest` and `generate_document`).

- [ ] **Step 5: Run server + CLI tests, then the full suite**

Run: `python -m pytest tests/test_server.py tests/test_cli.py -v`
Expected: PASS (fix any CLI test that asserted the old hard-failure behavior to assert the yellow warning path instead).

Run: `python -m pytest -q`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add projects/specguard/src/specguard/server.py projects/specguard/src/specguard/cli.py projects/specguard/tests/
git commit -m "feat(specguard): surface multi-role events over SSE and degrade warnings in CLI"
```

---

### Task 11: End-to-end smoke against local Ollama (manual gate)

**Files:** none (verification only)

- [ ] **Step 1: Confirm Ollama is up**

Run: `curl -s http://localhost:11434/api/tags`
Expected: JSON listing models including the configured default. If Ollama is not running, skip this task and note it in the handoff — automated tests above already cover the loop with fakes.

- [ ] **Step 2: Run a real generation**

Run from `projects/specguard`: `python -m specguard.cli generate "A booking app for yoga studios" --mode prd --output-dir outputs-smoke`
Expected: `wrote: outputs-smoke/prd/<file>.md` — possibly with a yellow degraded warning (acceptable for a small model; the file must still exist).

- [ ] **Step 3: Inspect the output file**

Open the written file; confirm it is Markdown with at least some of the six required PRD sections, and that the run produced `plan`/`critique` activity (visible in server SSE if run through the UI).

- [ ] **Step 4: Clean up**

```bash
rm -rf outputs-smoke
```

- [ ] **Step 5: Final commit if anything was adjusted**

```bash
git status
# commit any fixes discovered during smoke with message:
# fix(specguard): smoke-test fixes for multi-role pipeline
```
