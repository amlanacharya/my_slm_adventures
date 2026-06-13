# Local SLM SpecGuard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current SpecGuard package into the first subproject under `my_slm_adventures`, with a LangChain provider gateway, Ollama/Gemma default, standards-driven Markdown generation, validation, rubric revision, and a subcommand CLI.

**Architecture:** The repository becomes a lightweight monorepo with SpecGuard under `projects/specguard/`. SpecGuard uses a config-driven LangChain model gateway so pipeline code is provider-neutral. The default generation path is explicit: load standard, draft, validate, review, revise, and save Markdown.

**Tech Stack:** Python 3.11, uv, Click, Pydantic, pytest, Ruff, mypy, LangChain Core, LangChain OpenAI, LangChain Ollama, optional LangChain Anthropic.

---

## File Structure

- Move to `projects/specguard/`: `pyproject.toml`, `uv.lock`, `.env.example`, `README.md`, `src/specguard/`, `tests/`.
- Keep at repo root: `AGENTS.md`, `docs/superpowers/specs/`, `docs/superpowers/plans/`.
- Create `projects/specguard/standards/prd.md`: PRD standard sections and rubric hints.
- Create `projects/specguard/standards/brd.md`: BRD standard sections and rubric hints.
- Create `projects/specguard/standards/tech_scope.md`: technical scope standard sections and rubric hints.
- Create `projects/specguard/src/specguard/config.py`: environment-backed settings and supported provider names.
- Create `projects/specguard/src/specguard/llm_gateway.py`: LangChain chat-model factory.
- Create `projects/specguard/src/specguard/standards.py`: standard file loading and required-section definitions.
- Create `projects/specguard/src/specguard/validators.py`: Markdown section validation.
- Create `projects/specguard/src/specguard/pipeline.py`: generation, validation, review, revision, and save orchestration.
- Create `projects/specguard/src/specguard/cli.py`: Click subcommands and compatibility invocation.
- Modify `projects/specguard/src/specguard/agent.py`: keep Deep Agents path available and separate from the new default pipeline.
- Modify `projects/specguard/pyproject.toml`: add local backend dependencies and keep package metadata.
- Modify root `README.md`: describe `my_slm_adventures` and point to `projects/specguard/`.
- Modify `projects/specguard/README.md`: document SpecGuard setup and commands.

---

### Task 1: Restructure Into Umbrella Repository

**Files:**
- Move: `pyproject.toml` to `projects/specguard/pyproject.toml`
- Move: `uv.lock` to `projects/specguard/uv.lock`
- Move: `.env.example` to `projects/specguard/.env.example`
- Move: `README.md` to `projects/specguard/README.md`
- Move: `src/` to `projects/specguard/src/`
- Move: `tests/` to `projects/specguard/tests/`
- Create: `README.md`

- [ ] **Step 1: Inspect dirty files before moving**

Run:

```powershell
git status --short
```

Expected: shows the current uncommitted files. Do not discard them.

- [ ] **Step 2: Create destination directory**

Run:

```powershell
New-Item -ItemType Directory -Force projects\specguard
```

Expected: `projects/specguard/` exists.

- [ ] **Step 3: Move SpecGuard files with git**

Run:

```powershell
git mv pyproject.toml projects\specguard\pyproject.toml
git mv uv.lock projects\specguard\uv.lock
git mv .env.example projects\specguard\.env.example
git mv README.md projects\specguard\README.md
git mv src projects\specguard\src
git mv tests projects\specguard\tests
```

Expected: Git records renames instead of deletions plus additions.

- [ ] **Step 4: Create root README**

Write `README.md`:

```markdown
# my_slm_adventures

Local small-language-model experiments and tools.

## Projects

- [SpecGuard](projects/specguard/README.md): LangChain-powered PRD, BRD, and technical-scope generator with local Ollama support.

## Working With SpecGuard

```bash
cd projects/specguard
uv sync --extra dev
uv run specguard generate "Build an app for interior designers..." --mode prd
```
```

- [ ] **Step 5: Verify tests still discover from subproject**

Run:

```powershell
cd projects\specguard
uv run pytest
```

Expected: existing tests run from the subproject. Failures caused by the missing CLI are acceptable until Task 6.

- [ ] **Step 6: Commit restructure**

Run:

```powershell
git add README.md projects/specguard
git commit -m "chore: move SpecGuard into projects directory"
```

Expected: commit succeeds and root docs remain in place.

---

### Task 2: Add SpecGuard Standards

**Files:**
- Create: `projects/specguard/standards/prd.md`
- Create: `projects/specguard/standards/brd.md`
- Create: `projects/specguard/standards/tech_scope.md`
- Create: `projects/specguard/src/specguard/standards.py`
- Test: `projects/specguard/tests/test_standards.py`

- [ ] **Step 1: Write failing tests**

Create `projects/specguard/tests/test_standards.py`:

```python
from specguard.standards import REQUIRED_SECTIONS, load_standard


def test_load_standard_returns_markdown_for_each_mode():
    for mode in ("prd", "brd", "tech_scope"):
        standard = load_standard(mode)
        assert standard.startswith("# ")
        assert len(standard) > 200


def test_required_sections_are_defined_for_each_mode():
    assert set(REQUIRED_SECTIONS) == {"prd", "brd", "tech_scope"}
    for sections in REQUIRED_SECTIONS.values():
        assert len(sections) >= 5
        assert all(section.startswith("## ") for section in sections)


def test_load_standard_rejects_unknown_mode():
    try:
        load_standard("memo")
    except ValueError as exc:
        assert "unknown mode" in str(exc)
    else:
        raise AssertionError("expected ValueError")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd projects\specguard
uv run pytest tests/test_standards.py -v
```

Expected: FAIL because `specguard.standards` does not exist.

- [ ] **Step 3: Add standards implementation**

Create `projects/specguard/src/specguard/standards.py`:

```python
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
```

- [ ] **Step 4: Package standards as import resources**

Create directory `projects/specguard/src/specguard/standards/` and add `__init__.py`:

```python
"""Bundled SpecGuard document standards."""
```

Move the three Markdown standard files into `projects/specguard/src/specguard/standards/` so `importlib.resources` can load them.

- [ ] **Step 5: Write PRD standard**

Create `projects/specguard/src/specguard/standards/prd.md`:

```markdown
# SpecGuard PRD Standard

## Required Sections

## Problem
State the user or market problem in concrete terms.

## Goals
List measurable product goals and non-goals.

## Users
Describe primary users, secondary users, and their jobs to be done.

## Requirements
Separate functional requirements, non-functional requirements, and constraints.

## Success Metrics
Define adoption, quality, business, and operational metrics.

## Risks and Assumptions
Call out uncertain assumptions, dependencies, and major product risks.

## Review Criteria

A strong PRD is specific, testable, scoped for an MVP, explicit about tradeoffs, and clear enough for engineering and design to estimate.
```

- [ ] **Step 6: Write BRD standard**

Create `projects/specguard/src/specguard/standards/brd.md`:

```markdown
# SpecGuard BRD Standard

## Required Sections

## Business Context
Explain the business situation, opportunity, and current operating pain.

## Objectives
State business outcomes, constraints, and success thresholds.

## Stakeholders
Identify decision makers, operators, customers, and affected teams.

## Scope
Define included capabilities, excluded capabilities, and rollout boundaries.

## Business Rules
Capture policies, compliance rules, approvals, calculations, and exceptions.

## Risks and Dependencies
Describe operational risks, vendor dependencies, compliance concerns, and adoption blockers.

## Review Criteria

A strong BRD connects the initiative to business value, makes scope decisions visible, and gives delivery teams enough context to plan implementation.
```

- [ ] **Step 7: Write technical-scope standard**

Create `projects/specguard/src/specguard/standards/tech_scope.md`:

```markdown
# SpecGuard Technical Scope Standard

## Required Sections

## Technical Overview
Summarize the system, constraints, and intended technical outcome.

## Architecture
Describe components, boundaries, responsibilities, and data flow.

## Data Model
List core entities, relationships, storage needs, and retention concerns.

## Integrations
Identify external services, APIs, authentication, and failure modes.

## Delivery Plan
Break the build into milestones with implementation and verification steps.

## Risks and Open Questions
Name technical unknowns, scaling risks, security concerns, and decisions that need owners.

## Review Criteria

A strong technical scope is implementable, testable, explicit about boundaries, and honest about risks.
```

- [ ] **Step 8: Include Markdown package data**

Modify `projects/specguard/pyproject.toml`:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/specguard"]
artifacts = ["src/specguard/standards/*.md"]
```

- [ ] **Step 9: Run standards tests**

Run:

```powershell
cd projects\specguard
uv run pytest tests/test_standards.py -v
```

Expected: PASS.

- [ ] **Step 10: Commit standards**

Run:

```powershell
git add projects/specguard
git commit -m "feat(specguard): add document standards"
```

Expected: commit succeeds.

---

### Task 3: Add Config and LangChain Provider Gateway

**Files:**
- Modify: `projects/specguard/pyproject.toml`
- Create: `projects/specguard/src/specguard/config.py`
- Create: `projects/specguard/src/specguard/llm_gateway.py`
- Test: `projects/specguard/tests/test_llm_gateway.py`

- [ ] **Step 1: Write failing gateway tests**

Create `projects/specguard/tests/test_llm_gateway.py`:

```python
import pytest

from specguard.config import Settings
from specguard.llm_gateway import build_chat_model


def test_settings_defaults_to_ollama_gemma():
    settings = Settings.from_env({})
    assert settings.provider == "ollama"
    assert settings.model == "gemma3:4b"
    assert settings.ollama_base_url == "http://localhost:11434"


def test_settings_supports_openai_provider():
    settings = Settings.from_env({"SPECGUARD_PROVIDER": "openai", "SPECGUARD_MODEL": "gpt-4.1-mini"})
    assert settings.provider == "openai"
    assert settings.model == "gpt-4.1-mini"


def test_unknown_provider_is_rejected():
    with pytest.raises(ValueError, match="unknown provider"):
        Settings.from_env({"SPECGUARD_PROVIDER": "madeup"})


def test_build_chat_model_rejects_unknown_provider_directly():
    settings = Settings(provider="madeup", model="x")
    with pytest.raises(ValueError, match="unknown provider"):
        build_chat_model(settings)
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd projects\specguard
uv run pytest tests/test_llm_gateway.py -v
```

Expected: FAIL because `config.py` and `llm_gateway.py` do not exist.

- [ ] **Step 3: Add dependencies**

Modify `projects/specguard/pyproject.toml` dependencies:

```toml
dependencies = [
    "click>=8.1",
    "deepagents>=0.6,<1.0",
    "langchain-core>=0.3,<2.0.0",
    "langchain-openai>=0.2,<1.0",
    "langchain-ollama>=0.2,<1.0",
    "langgraph>=0.2,<2.0.0",
    "pydantic>=2.6,<3.0",
    "python-dotenv>=1.0",
    "rich>=13.7",
]

[project.optional-dependencies]
dev = [
    "mypy>=1.10",
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.5",
]
anthropic = [
    "langchain-anthropic>=0.2",
]
```

- [ ] **Step 4: Implement settings**

Create `projects/specguard/src/specguard/config.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from os import environ
from typing import Mapping


SUPPORTED_PROVIDERS = ("ollama", "openai", "anthropic")


@dataclass(frozen=True)
class Settings:
    provider: str = "ollama"
    model: str = "gemma3:4b"
    ollama_base_url: str = "http://localhost:11434"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        source = environ if env is None else env
        provider = source.get("SPECGUARD_PROVIDER", "ollama").lower()
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"unknown provider {provider!r}; valid: {SUPPORTED_PROVIDERS}")

        default_model = "gemma3:4b" if provider == "ollama" else "gpt-4.1-mini"
        return cls(
            provider=provider,
            model=source.get("SPECGUARD_MODEL", default_model),
            ollama_base_url=source.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        )
```

- [ ] **Step 5: Implement gateway**

Create `projects/specguard/src/specguard/llm_gateway.py`:

```python
from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from .config import SUPPORTED_PROVIDERS, Settings


def build_chat_model(settings: Settings | None = None) -> BaseChatModel:
    resolved = settings or Settings.from_env()

    if resolved.provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(model=resolved.model, base_url=resolved.ollama_base_url)

    if resolved.provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=resolved.model)

    if resolved.provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:
            raise RuntimeError("install the anthropic extra to use SPECGUARD_PROVIDER=anthropic") from exc

        return ChatAnthropic(model=resolved.model)

    raise ValueError(f"unknown provider {resolved.provider!r}; valid: {SUPPORTED_PROVIDERS}")
```

- [ ] **Step 6: Run gateway tests**

Run:

```powershell
cd projects\specguard
uv sync --extra dev
uv run pytest tests/test_llm_gateway.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit gateway**

Run:

```powershell
git add projects/specguard
git commit -m "feat(specguard): add LangChain model gateway"
```

Expected: commit succeeds.

---

### Task 4: Add Markdown Section Validation

**Files:**
- Create: `projects/specguard/src/specguard/validators.py`
- Test: `projects/specguard/tests/test_validators.py`

- [ ] **Step 1: Write failing validator tests**

Create `projects/specguard/tests/test_validators.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd projects\specguard
uv run pytest tests/test_validators.py -v
```

Expected: FAIL because `validators.py` does not exist.

- [ ] **Step 3: Implement validator**

Create `projects/specguard/src/specguard/validators.py`:

```python
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
```

- [ ] **Step 4: Run validator tests**

Run:

```powershell
cd projects\specguard
uv run pytest tests/test_validators.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit validator**

Run:

```powershell
git add projects/specguard
git commit -m "feat(specguard): validate generated document sections"
```

Expected: commit succeeds.

---

### Task 5: Add Explicit Generation Pipeline

**Files:**
- Create: `projects/specguard/src/specguard/pipeline.py`
- Test: `projects/specguard/tests/test_pipeline.py`

- [ ] **Step 1: Write failing pipeline tests**

Create `projects/specguard/tests/test_pipeline.py`:

```python
from __future__ import annotations

from pathlib import Path

from langchain_core.messages import AIMessage

from specguard.pipeline import GenerationRequest, generate_document


class FakeChatModel:
    def __init__(self):
        self.calls: list[str] = []

    def invoke(self, messages):
        text = messages[-1].content
        self.calls.append(text)
        if "Revise" in text:
            return AIMessage(
                content=(
                    "# Product Requirements Document\n\n"
                    "## Problem\nText.\n\n"
                    "## Goals\nText.\n\n"
                    "## Users\nText.\n\n"
                    "## Requirements\nText.\n\n"
                    "## Success Metrics\nText.\n\n"
                    "## Risks and Assumptions\nText.\n"
                )
            )
        if "Review" in text:
            return AIMessage(content="Missing required sections: Users, Requirements, Success Metrics.")
        return AIMessage(content="# Product Requirements Document\n\n## Problem\nText.\n\n## Goals\nText.\n")


def test_generate_document_revises_and_saves_markdown(tmp_path: Path):
    model = FakeChatModel()
    request = GenerationRequest(
        idea="Build an app for interior designers.",
        mode="prd",
        output_dir=tmp_path,
    )

    result = generate_document(request, chat_model=model)

    assert result.validation.ok is True
    assert result.output_path.exists()
    assert result.output_path.suffix == ".md"
    assert "## Users" in result.markdown
    assert len(model.calls) == 3
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd projects\specguard
uv run pytest tests/test_pipeline.py -v
```

Expected: FAIL because `pipeline.py` does not exist.

- [ ] **Step 3: Implement pipeline**

Create `projects/specguard/src/specguard/pipeline.py`:

```python
from __future__ import annotations

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
    filename = f"{datetime.now().strftime('%Y-%m-%d')}-{_slugify(request.idea)}.md"
    path = mode_dir / filename
    path.write_text(markdown, encoding="utf-8")
    return path


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return (slug[:60] or "specguard-document").strip("-")
```

- [ ] **Step 4: Run pipeline tests**

Run:

```powershell
cd projects\specguard
uv run pytest tests/test_pipeline.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit pipeline**

Run:

```powershell
git add projects/specguard
git commit -m "feat(specguard): add explicit generation pipeline"
```

Expected: commit succeeds.

---

### Task 6: Add Subcommand CLI

**Files:**
- Create: `projects/specguard/src/specguard/cli.py`
- Test: `projects/specguard/tests/test_cli.py`
- Modify: `projects/specguard/README.md`

- [ ] **Step 1: Write failing CLI tests**

Create `projects/specguard/tests/test_cli.py`:

```python
from pathlib import Path

from click.testing import CliRunner

from specguard import cli


def test_models_check_prints_config(monkeypatch):
    monkeypatch.setenv("SPECGUARD_PROVIDER", "ollama")
    monkeypatch.setenv("SPECGUARD_MODEL", "gemma3:4b")
    runner = CliRunner()

    result = runner.invoke(cli.main, ["models", "check"])

    assert result.exit_code == 0
    assert "provider: ollama" in result.output
    assert "model: gemma3:4b" in result.output


def test_generate_writes_output_with_fake_pipeline(monkeypatch, tmp_path: Path):
    def fake_generate_document(request):
        out = tmp_path / "prd" / "fake.md"
        out.parent.mkdir(parents=True)
        out.write_text("# Product Requirements Document\n", encoding="utf-8")
        return type(
            "Result",
            (),
            {
                "output_path": out,
                "validation": type("Validation", (), {"ok": True, "missing_sections": ()})(),
            },
        )()

    monkeypatch.setattr(cli, "generate_document", fake_generate_document)
    runner = CliRunner()

    result = runner.invoke(cli.main, ["generate", "Build an app", "--mode", "prd", "--output-dir", str(tmp_path)])

    assert result.exit_code == 0
    assert "wrote:" in result.output
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd projects\specguard
uv run pytest tests/test_cli.py -v
```

Expected: FAIL because `cli.py` does not exist.

- [ ] **Step 3: Implement CLI**

Create `projects/specguard/src/specguard/cli.py`:

```python
from __future__ import annotations

from pathlib import Path

import click

from .config import Settings
from .pipeline import GenerationRequest, generate_document
from .standards import REQUIRED_SECTIONS


@click.group(invoke_without_command=True)
@click.argument("idea", required=False)
@click.option("--mode", type=click.Choice(tuple(REQUIRED_SECTIONS)), default="prd", show_default=True)
@click.pass_context
def main(ctx: click.Context, idea: str | None, mode: str) -> None:
    """Generate SpecGuard documents."""
    if ctx.invoked_subcommand is None:
        if idea is None:
            click.echo(ctx.get_help())
            return
        result = generate_document(GenerationRequest(idea=idea, mode=mode))
        _print_result(result)


@main.command()
@click.argument("idea")
@click.option("--mode", type=click.Choice(tuple(REQUIRED_SECTIONS)), default="prd", show_default=True)
@click.option("--output-dir", type=click.Path(path_type=Path), default=Path("outputs"), show_default=True)
def generate(idea: str, mode: str, output_dir: Path) -> None:
    """Generate a PRD, BRD, or technical scope."""
    result = generate_document(GenerationRequest(idea=idea, mode=mode, output_dir=output_dir))
    _print_result(result)


@main.group()
def models() -> None:
    """Inspect configured model backends."""


@models.command("check")
def models_check() -> None:
    """Print the configured provider and model."""
    settings = Settings.from_env()
    click.echo(f"provider: {settings.provider}")
    click.echo(f"model: {settings.model}")
    if settings.provider == "ollama":
        click.echo(f"ollama_base_url: {settings.ollama_base_url}")


def _print_result(result) -> None:
    click.echo(f"wrote: {result.output_path}")
    if not result.validation.ok:
        missing = ", ".join(result.validation.missing_sections)
        click.echo(f"missing sections after revision: {missing}")
```

- [ ] **Step 4: Run CLI tests**

Run:

```powershell
cd projects\specguard
uv run pytest tests/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 5: Update SpecGuard README commands**

Modify `projects/specguard/README.md` quick start:

```markdown
## Quick start

```bash
uv sync --extra dev
ollama pull gemma3:4b
uv run specguard models check
uv run specguard generate "Build an app for interior designers to manage quotation, billing, GST invoice, labour payments, and procurement." --mode prd
```

Set local defaults in `.env`:

```env
SPECGUARD_PROVIDER=ollama
SPECGUARD_MODEL=gemma3:4b
OLLAMA_BASE_URL=http://localhost:11434
```
```

- [ ] **Step 6: Run full test suite**

Run:

```powershell
cd projects\specguard
uv run pytest
```

Expected: PASS.

- [ ] **Step 7: Commit CLI**

Run:

```powershell
git add projects/specguard
git commit -m "feat(specguard): add generation CLI"
```

Expected: commit succeeds.

---

### Task 7: Final Verification and GitHub Repo Setup

**Files:**
- Modify: root `AGENTS.md` if paths now need monorepo wording.
- No code creation required.

- [ ] **Step 1: Run formatting and linting**

Run:

```powershell
cd projects\specguard
uv run ruff check .
uv run mypy src
uv run pytest
```

Expected: all commands pass. If mypy fails because external model classes lack precise stubs, narrow the annotation in `llm_gateway.py` to the common LangChain base type already used in Task 3.

- [ ] **Step 2: Run local model smoke check without generating**

Run:

```powershell
cd projects\specguard
uv run specguard models check
```

Expected:

```text
provider: ollama
model: gemma3:4b
ollama_base_url: http://localhost:11434
```

- [ ] **Step 3: Create GitHub repository**

Run:

```powershell
gh repo create my_slm_adventures --private --source . --remote origin
```

Expected: GitHub repository exists and `origin` points to it.

- [ ] **Step 4: Push current branch**

Run:

```powershell
git push -u origin main
```

Expected: branch pushes to GitHub.

- [ ] **Step 5: Commit final docs adjustment if needed**

Run:

```powershell
git status --short
```

Expected: clean worktree. If only path documentation changed, commit it:

```powershell
git add AGENTS.md README.md projects/specguard/README.md
git commit -m "docs: align contributor guide with monorepo layout"
```

---

## Self-Review

Spec coverage:

- Umbrella repo and `projects/specguard/` layout: Task 1.
- LangChain provider gateway with Ollama/Gemma default and cloud options: Task 3.
- Explicit generation pipeline with validation, review, revision, and Markdown save: Tasks 4 and 5.
- Subcommand CLI plus compatibility invocation: Task 6.
- Repo-owned standards for PRD, BRD, and technical scope: Task 2.
- Markdown-only output and deferred training/export: enforced by omission from implementation tasks.
- Tests with mocked model calls and integration boundary: Tasks 3 through 7.
- GitHub repo named `my_slm_adventures`: Task 7.

Completeness scan:

- Executable steps include concrete files, commands, code, and expected results.
- Each implementation task includes file paths, test code, implementation code, commands, and expected results.

Type consistency:

- `Settings`, `GenerationRequest`, `GenerationResult`, `ValidationResult`, `build_chat_model`, and `generate_document` are introduced before downstream use.
- The CLI imports the same names defined in pipeline/config tasks.
