from __future__ import annotations

import sys
from pathlib import Path

import click

from .config import Settings
from .pipeline import GenerationRequest, generate_document
from .standards import REQUIRED_SECTIONS


@click.group()
def main() -> None:
    """Generate SpecGuard documents."""


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


# Compatibility entry point: `specguard "idea" --mode prd` dispatches to `generate`.
def _compat_entry() -> None:
    """Dispatch `specguard [idea...]` to the `generate` subcommand, or print help."""
    if len(sys.argv) >= 2 and not sys.argv[1].startswith("-") and sys.argv[1] not in main.commands:
        sys.argv.insert(1, "generate")
    main()
