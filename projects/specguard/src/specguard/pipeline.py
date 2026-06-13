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

    # ── Planner ────────────────────────────────────────────────────────────────
    brief: Brief = plan(planner_model, request.idea, request.mode, standard)
    yield PipelineEvent(
        kind="plan",
        timestamp=_now(),
        review_notes=brief.guidance,
    )

    # ── Retry loop ─────────────────────────────────────────────────────────────
    draft_text = ""
    last_critic_notes = ""
    last_missing: tuple[str, ...] = ()
    for attempt in range(1, budget + 1):
        yield PipelineEvent(kind="attempt", timestamp=_now(), attempt=attempt, budget=budget)

        # Writer
        is_revise = attempt > 1
        if is_revise:
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
        else:
            draft_text = write_draft(writer_model, request.idea, request.mode, standard, brief)

        yield PipelineEvent(
            kind="revise" if is_revise else "draft",
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

        # Prepare revision context for next iteration
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
