from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

import click

from .config import Settings
from .pipeline import GenerationError, GenerationRequest, generate_document
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
    try:
        result = generate_document(GenerationRequest(idea=idea, mode=mode, output_dir=output_dir))
    except GenerationError as exc:
        missing = ", ".join(exc.validation.missing_sections)
        raise click.ClickException(
            f"generation failed; missing required sections: {missing}"
        ) from exc
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


@main.command()
@click.option("--host", default="127.0.0.1", show_default=True, help="Bind host.")
@click.option("--port", default=8765, show_default=True, type=int, help="Bind port.")
@click.option("--no-browser", is_flag=True, help="Don't open the browser automatically.")
def serve(host: str, port: int, no_browser: bool) -> None:
    """Start the local web UI (FastAPI + React)."""
    import uvicorn

    from .server import create_app

    frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
    static_dir = frontend_dist if frontend_dist.exists() else None
    if static_dir is None:
        click.echo(
            click.style(
                "frontend not built — serving API only. Run "
                "`cd projects/specguard/frontend && npm install && npm run build` "
                "for the full UI.",
                fg="yellow",
            )
        )
    app = create_app(static_dir=static_dir)
    url = f"http://{host}:{port}/"
    click.echo(click.style(f"SpecGuard web UI: {url}", fg="green", bold=True))
    click.echo("Press Ctrl+C to stop.")
    if not no_browser and not _env_flag("SPECGUARD_NO_BROWSER"):
        try:
            webbrowser.open(url)
        except Exception:  # pragma: no cover - best effort
            pass
    uvicorn.run(app, host=host, port=port, log_level="info")


def _env_flag(name: str) -> bool:
    import os

    return os.environ.get(name, "").lower() in ("1", "true", "yes")
