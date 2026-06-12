"""Bundled SpecGuard document standards."""

from __future__ import annotations

from importlib.resources import files


REQUIRED_SECTIONS: dict[str, tuple[str, ...]] = {
    "prd": (
        "## Problem",
        "## Goals",
        "## Users",
        "## Requirements",
        "## Success Metrics",
        "## Risks and Assumptions",
    ),
    "brd": (
        "## Business Context",
        "## Objectives",
        "## Stakeholders",
        "## Scope",
        "## Business Rules",
        "## Risks and Dependencies",
    ),
    "tech_scope": (
        "## Technical Overview",
        "## Architecture",
        "## Data Model",
        "## Integrations",
        "## Delivery Plan",
        "## Risks and Open Questions",
    ),
}


def load_standard(mode: str) -> str:
    if mode not in REQUIRED_SECTIONS:
        raise ValueError(f"unknown mode {mode!r}; valid: {tuple(REQUIRED_SECTIONS)}")
    path = files("specguard").joinpath("standards", f"{mode}.md")
    return path.read_text(encoding="utf-8")
