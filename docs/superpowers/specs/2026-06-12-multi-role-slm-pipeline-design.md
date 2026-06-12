# Multi-Role SLM Pipeline — Design

**Date:** 2026-06-12
**Project:** SpecGuard (`projects/specguard`)
**Status:** Approved by user (pending spec review)

## Goal

Evolve SpecGuard's generation pipeline from a single-model, fixed two-pass loop into a
multi-role SLM harness: Planner, Writer, and Critic roles coordinated by a deterministic
Router with a retry budget. This is the first slice of the larger "SLM-first agentic OS
for governed specification work" direction. The harness — not the model — is the product;
each SLM is a replaceable worker inside it.

## Scope

**In scope (this slice):**

- Planner / Writer / Critic roles, each its own module with one public function.
- Deterministic Router (pure Python, no SLM) with configurable retry budget.
- Scored rubric JSON from the Critic, with tolerant parsing and fallback.
- Per-role model configuration with a shared default.
- New `PipelineEvent` kinds (`plan`, `critique`, `attempt`) consumed by the existing
  CLI and web UI SSE stream without breaking current event shapes.
- Draft-with-warnings degradation instead of hard failure when the budget is exhausted.

**Out of scope (later slices, each its own spec):**

- Memory/state store across sessions.
- Policy/approval layer (human checkpoints, tool-access control).
- Eval harness (fixed prompt suite, regression scoring).
- Retiring `agent.py` (the deep-agent path stays as-is).
- Ask-user interrupts when the loop is stuck.

## Architecture

### Roles

All SLM calls go through the existing `llm_gateway.build_chat_model`. One shared default
model (gemma4 via Ollama today); each role has a config override slot.

**Planner** (`roles/planner.py`)
- Runs the three deterministic tools directly in Python — `clarifier`,
  `domain_checklist`, `scope_estimator`. No tool-calling protocol: small models are
  unreliable at it, and the tools take the same input (the idea), so plain function
  calls are strictly better.
- Makes one SLM call to synthesize a **writing brief**: key assumptions, inferred
  answers to the clarifying questions, and per-section guidance grounded in the
  checklist and scope estimate.
- Output: `Brief` dataclass (assumptions, guidance text, raw tool outputs).

**Writer** (`roles/writer.py`)
- Drafts the document from idea + brief + mode standard.
- Also handles revisions: the revision prompt includes the Critic's findings and the
  validator's missing-section list. Same role, two prompt builders.

**Critic** (`roles/critic.py`)
- One SLM call returning **scored rubric JSON**:
  ```json
  {
    "verdict": "pass" | "needs_revision",
    "criteria": [{"id": "...", "score": 0 | 1 | 2, "reason": "..."}],
    "notes": "free-text findings for the Writer"
  }
  ```
- Rubrics come from `rubrics.py`, restructured from prose strings into criterion lists
  (`RubricCriterion(id, text)` per item). The existing checklist text is the source
  content; `get_rubric(mode)` keeps returning the prose form for `agent.py`
  compatibility, and a new `get_rubric_criteria(mode)` returns the structured form.

**Router** (`router.py`)
- Pure Python, no SLM call. Trivially unit-testable.
- `decide(validation, verdict, attempt, budget) -> "finalize" | "revise" | "degrade"`
  - Validators pass AND critic verdict is `pass` → `finalize`.
  - Otherwise, if `attempt < budget` → `revise`.
  - Budget exhausted → `degrade`: the document is still saved, the save event is
    marked degraded and carries the validation result and critic report. The pipeline
    never silently blocks output.
- Budget default 3, env `SPECGUARD_MAX_ATTEMPTS`.

### Critic JSON robustness

The known weak point of SLMs is structured output. Mitigation ladder:

1. Tolerant extraction: strip code fences, locate the first `{...}` JSON object,
   parse with `json.loads`.
2. On parse failure, retry the Critic call once.
3. On second failure, fall back to **validator-only gating** for that iteration and
   record the fallback in the event stream (`critique` event with `fallback: true`).

The loop never dies because the critic emitted bad JSON.

### Data flow

```
idea ─→ Planner(tools + 1 SLM call) ─→ brief
brief ─→ Writer ─→ draft ─→ [validators + Critic] ─→ Router
                     ▲                                 │
                     └──── revise (attempt < N) ←──────┘
                                                       └→ finalize / draft-with-warnings → save
```

## Module layout

```
specguard/
  pipeline.py        # orchestrator; keeps public contract
  router.py          # pure decision function
  roles/
    __init__.py
    planner.py       # plan(model, idea, mode, standard) -> Brief
    writer.py        # draft(...) -> str, revise(...) -> str
    critic.py        # critique(model, mode, draft) -> CriticVerdict
  rubrics.py         # + structured criteria accessor
  config.py          # + per-role model fields
```

`pipeline.py` keeps its public contract: `generate_document`, `generate_document_stream`,
`GenerationRequest`, `GenerationResult`, `PipelineEvent`. CLI and web UI keep working
unchanged.

## Configuration

`Settings` grows three optional per-role fields, each defaulting to the shared model:

| Field | Env var | Default |
|---|---|---|
| `planner_model` | `SPECGUARD_PLANNER_MODEL` | `SPECGUARD_MODEL` |
| `writer_model` | `SPECGUARD_WRITER_MODEL` | `SPECGUARD_MODEL` |
| `critic_model` | `SPECGUARD_CRITIC_MODEL` | `SPECGUARD_MODEL` |
| `max_attempts` | `SPECGUARD_MAX_ATTEMPTS` | `3` |

All roles share one provider (`SPECGUARD_PROVIDER`); heterogeneous providers per role
are out of scope for this slice.

## Events

New `PipelineEvent` kinds, added without changing existing shapes:

- `plan` — carries the brief summary and tool outputs.
- `attempt` — loop iteration marker with attempt number and budget.
- `critique` — carries rubric scores, verdict, notes, and `fallback` flag.
- `save` — gains a `degraded: bool` field (default `False`).

Existing kinds (`draft`, `validate`, `revise`, `review`) keep their shapes; `review`
is superseded by `critique` and no longer emitted (the web UI timeline renders unknown
kinds generically, so this is additive).

## Error handling

- Unknown mode: unchanged (`ValueError` before any model call).
- Model/provider errors: propagate as today (no new retry layer for transport errors
  in this slice).
- Critic JSON failure: mitigation ladder above; never fatal.
- Budget exhausted: `degrade` path — file saved, warnings attached, no exception from
  `generate_document_stream`. `generate_document` returns a `GenerationResult` with
  the degraded validation attached instead of raising `GenerationError`; the exception
  remains only for truly unrecoverable states (e.g. unknown mode).

## Testing

- `router.py`: pure unit tests over the decision table.
- Critic JSON extraction: unit tests for fenced JSON, prefixed prose, garbage input.
- Full loop with a fake `ChatModel` (existing test pattern), covering:
  1. Pass on first attempt.
  2. Pass after one revision.
  3. Budget exhausted → degraded save with warnings.
  4. Critic emits garbage twice → validator-only fallback recorded, loop continues.
- Existing CLI/server tests keep passing (public contract unchanged).

## Design decisions log

| Decision | Choice | Why |
|---|---|---|
| First slice of SLM-OS | Multi-role pipeline | Core thesis; builds directly on existing loop |
| Models per role | Same model, per-role config slots | Cheapest to run; validates harness before heterogeneity |
| Router behavior | Retry loop with budget, degrade not block | Never silently blocks output with weak SLMs |
| Critic output | Scored rubric JSON + notes | Router can act on it; trend data for future eval harness |
| Placement | Replace pipeline.py internals | One code path; UI gets richer events for free |
| Planner job | Brief + deterministic tool synthesis | Grounds drafts in tool output; no flaky tool-calling protocol |
