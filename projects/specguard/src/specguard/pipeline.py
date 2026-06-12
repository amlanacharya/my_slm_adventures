from __future__ import annotations

import itertools
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

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


def generate_document(
    request: GenerationRequest,
    chat_model: ChatModel | None = None,
) -> GenerationResult:
    if request.mode not in REQUIRED_SECTIONS:
        raise ValueError(f"unknown mode {request.mode!r}; valid: {tuple(REQUIRED_SECTIONS)}")

    model = chat_model or build_chat_model()
    standard = load_standard(request.mode)
    draft = _message_content(
        model.invoke(
            [
                SystemMessage(content=_system_prompt(request.mode, standard)),
                HumanMessage(content=f"Generate the document for this idea:\n\n{request.idea}"),
            ]
        )
    )

    validation = validate_required_sections(draft, REQUIRED_SECTIONS[request.mode])
    review = _message_content(
        model.invoke(
            [
                SystemMessage(content="Review the document against the provided standard."),
                HumanMessage(content=_review_prompt(request.mode, standard, draft, validation)),
            ]
        )
    )

    final = _message_content(
        model.invoke(
            [
                SystemMessage(content=_system_prompt(request.mode, standard)),
                HumanMessage(content=_revision_prompt(request.idea, draft, review, validation)),
            ]
        )
    )
    final_validation = validate_required_sections(final, REQUIRED_SECTIONS[request.mode])
    if not final_validation.ok:
        raise GenerationError(final_validation)

    output_path = _write_output(request, final)
    return GenerationResult(
        markdown=final,
        output_path=output_path,
        validation=final_validation,
        review=review,
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
