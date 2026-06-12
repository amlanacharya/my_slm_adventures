from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    missing_sections: tuple[str, ...]


def validate_required_sections(markdown: str, required_sections: tuple[str, ...]) -> ValidationResult:
    normalized_lines = {line.strip().lower() for line in markdown.splitlines()}
    missing = tuple(
        section for section in required_sections if section.strip().lower() not in normalized_lines
    )
    return ValidationResult(ok=not missing, missing_sections=missing)
