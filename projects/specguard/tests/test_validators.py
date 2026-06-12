from specguard.validators import ValidationResult, validate_required_sections


def test_validate_required_sections_passes_when_all_sections_exist():
    markdown = """
# Product Requirements Document

## Problem
Text.

## Goals
Text.
"""
    result = validate_required_sections(markdown, ("## Problem", "## Goals"))
    assert result == ValidationResult(ok=True, missing_sections=())


def test_validate_required_sections_reports_missing_sections():
    markdown = "# Product Requirements Document\n\n## Problem\nText."
    result = validate_required_sections(markdown, ("## Problem", "## Goals"))
    assert result.ok is False
    assert result.missing_sections == ("## Goals",)
