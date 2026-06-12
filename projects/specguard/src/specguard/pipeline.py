from __future__ import annotations

import itertools
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Protocol

from langchain_core.messages import HumanMessage, SystemMessage

from .llm_gateway import build_chat_model
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


class GenerationError(RuntimeError):
    """Raised when the model cannot produce a valid document after revision."""

    def __init__(self, validation: ValidationResult) -> None:
        self.validation = validation
        missing = ", ".join(validation.missing_sections)
        super().__init__(f"generated document is missing required sections: {missing}")


@dataclass(frozen=True)
class PipelineEvent:
    """One step of the generation pipeline, yielded to consumers (SSE, tests)."""

    kind: str  # "draft" | "validate" | "review" | "revise" | "save"
    timestamp: str
    tokens: int | None = None
    validation: ValidationResult | None = None
    review_notes: str | None = None
    markdown: str | None = None
    output_path: Path | None = None
    error: str | None = None


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def _estimate_tokens(text: str) -> int:
    """Cheap token estimate: chars/4. Real model returns the real count, but for
    streaming we surface an estimate to the UI immediately after each call."""
    return max(1, len(text) // 4)


def generate_document(
    request: GenerationRequest,
    chat_model: ChatModel | None = None,
) -> GenerationResult:
    """Run the full pipeline and return the final result. Raises GenerationError on failure."""
    final_event: PipelineEvent | None = None
    error_event: PipelineEvent | None = None
    for event in generate_document_stream(request, chat_model=chat_model):
        if event.kind == "save":
            final_event = event
        if event.error:
            error_event = event
    if error_event is not None:
        # Re-raise to match the legacy contract. ValidationError carries the result.
        if final_event is not None and final_event.validation is not None:
            raise GenerationError(final_event.validation)
        raise GenerationError(
            ValidationResult(ok=False, missing_sections=())
        )
    assert final_event is not None
    assert final_event.validation is not None
    assert final_event.output_path is not None
    assert final_event.markdown is not None
    return GenerationResult(
        markdown=final_event.markdown,
        output_path=final_event.output_path,
        validation=final_event.validation,
        review=error_event.review_notes if error_event else "",
    )


def generate_document_stream(
    request: GenerationRequest,
    chat_model: ChatModel | None = None,
) -> Iterator[PipelineEvent]:
    """Run the pipeline, yielding a PipelineEvent after each step."""
    if request.mode not in REQUIRED_SECTIONS:
        raise ValueError(f"unknown mode {request.mode!r}; valid: {tuple(REQUIRED_SECTIONS)}")

    model = chat_model or build_chat_model()
    standard = load_standard(request.mode)

    # 1. Draft
    draft_text = _message_content(
        model.invoke(
            [
                SystemMessage(content=_system_prompt(request.mode, standard)),
                HumanMessage(content=f"Generate the document for this idea:\n\n{request.idea}"),
            ]
        )
    )
    yield PipelineEvent(
        kind="draft",
        timestamp=_now(),
        tokens=_estimate_tokens(draft_text),
    )

    # 2. Validate draft
    draft_validation = validate_required_sections(draft_text, REQUIRED_SECTIONS[request.mode])
    yield PipelineEvent(
        kind="validate",
        timestamp=_now(),
        validation=draft_validation,
    )

    # 3. Review
    review_text = _message_content(
        model.invoke(
            [
                SystemMessage(content="Review the document against the provided standard."),
                HumanMessage(content=_review_prompt(request.mode, standard, draft_text, draft_validation)),
            ]
        )
    )
    yield PipelineEvent(
        kind="review",
        timestamp=_now(),
        review_notes=review_text,
    )

    # 4. Revise
    final_text = _message_content(
        model.invoke(
            [
                SystemMessage(content=_system_prompt(request.mode, standard)),
                HumanMessage(content=_revision_prompt(request.idea, draft_text, review_text, draft_validation)),
            ]
        )
    )
    yield PipelineEvent(
        kind="revise",
        timestamp=_now(),
        tokens=_estimate_tokens(final_text),
    )

    # 5. Validate revision
    final_validation = validate_required_sections(final_text, REQUIRED_SECTIONS[request.mode])
    yield PipelineEvent(
        kind="validate",
        timestamp=_now(),
        validation=final_validation,
    )

    if not final_validation.ok:
        # Yield a final error event so the SSE consumer can surface the failure,
        # then stop. generate_document will turn this into a GenerationError.
        yield PipelineEvent(
            kind="save",
            timestamp=_now(),
            validation=final_validation,
            error="missing required sections",
            review_notes=review_text,
        )
        return

    output_path = _write_output(request, final_text)
    yield PipelineEvent(
        kind="save",
        timestamp=_now(),
        validation=final_validation,
        markdown=final_text,
        output_path=output_path,
    )



def _system_prompt(mode: str, standard: str) -> str:
    return (
        f"You are SpecGuard. Generate a {mode} document in Markdown. "
        "Follow the standard exactly and include every required section.\n\n"
        f"{standard}"
    )


def _review_prompt(
    mode: str,
    standard: str,
    draft: str,
    validation: ValidationResult,
) -> str:
    missing = ", ".join(validation.missing_sections) if validation.missing_sections else "none"
    return (
        f"Review this {mode} draft against the standard.\n\n"
        f"Missing required sections from validator: {missing}\n\n"
        f"Standard:\n{standard}\n\nDraft:\n{draft}"
    )


def _revision_prompt(
    idea: str,
    draft: str,
    review: str,
    validation: ValidationResult,
) -> str:
    missing = ", ".join(validation.missing_sections) if validation.missing_sections else "none"
    return (
        "Revise the draft into final Markdown. Preserve useful content, fix the review findings, "
        "and include all required sections.\n\n"
        f"Idea:\n{idea}\n\nMissing sections:\n{missing}\n\nReview:\n{review}\n\nDraft:\n{draft}"
    )


def _message_content(message) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    return str(content)


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
