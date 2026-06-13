"""FastAPI server for the SpecGuard web UI.

Endpoints:
  GET  /api/health             — liveness
  GET  /api/settings           — current provider/model/output dir
  POST /api/settings           — update overrides (provider/model/output dir)
  GET  /api/modes              — supported modes with their required sections
  POST /api/generate           — SSE stream of pipeline events for a generation
  GET  /api/history            — list of saved documents (newest first)
  GET  /api/document?path=...  — read a single saved document

Static files:
  GET  /                       — serves the built React app (or a friendly hint during dev)
  GET  /assets/*               — built JS/CSS assets

Dev mode (SPECGUARD_DEV=1) does not serve the React app; Vite owns the root.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

from .config import DEFAULT_MODELS, SUPPORTED_PROVIDERS
from .llm_gateway import build_chat_model
from .persistence import (
    PersistedSettings,
    clear_env_var,
    read_env_var,
    write_env_var,
)
from .pipeline import (
    GenerationRequest,
    PipelineEvent,
    generate_document_stream,
)
from .standards import REQUIRED_SECTIONS


_settings_lock = threading.Lock()


def _get_persisted() -> PersistedSettings:
    with _settings_lock:
        s = PersistedSettings.load()
        # Also detect which API keys are set, so the UI can show "configured".
        s.has_openai_key = bool(read_env_var("OPENAI_API_KEY"))
        s.has_anthropic_key = bool(read_env_var("ANTHROPIC_API_KEY"))
        s.has_minimax_key = bool(read_env_var("MINIMAX_API_KEY"))
        return s


def _save_persisted(persisted: PersistedSettings) -> PersistedSettings:
    with _settings_lock:
        persisted.save()
        return persisted


def _output_dir() -> Path:
    raw = os.environ.get("SPECGUARD_OUTPUT_DIR")
    if raw:
        return Path(raw)
    return Path("outputs")


# ---------------------------------------------------------------------------
# Pydantic request/response models (the wire contract with the React client)
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str
    version: str
    server_time: str


class SettingsResponse(BaseModel):
    provider: str
    model: str
    ollama_base_url: str
    minimax_base_url: str
    output_dir: str
    has_openai_key: bool
    has_anthropic_key: bool
    has_minimax_key: bool


class SettingsUpdate(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    ollama_base_url: Optional[str] = None
    minimax_base_url: Optional[str] = None


class ApiKeyUpdate(BaseModel):
    provider: str  # "openai" | "anthropic" | "minimax"
    key: str
    clear: bool = False  # if True, delete the key


class GenerateRequest(BaseModel):
    idea: str = Field(min_length=3)
    mode: str
    output_dir: Optional[str] = None
    max_revisions: int = 2


class ModeInfo(BaseModel):
    name: str
    label: str
    sections: list[str]


class ModesResponse(BaseModel):
    modes: list[ModeInfo]


class DocumentSummary(BaseModel):
    path: str
    title: str
    mode: str
    created_at: str
    size_bytes: int
    valid: bool
    missing_sections: list[str] = []


class HistoryResponse(BaseModel):
    documents: list[DocumentSummary]


# ---------------------------------------------------------------------------
# SSE serialization
# ---------------------------------------------------------------------------


def _event_to_dict(event: PipelineEvent) -> dict:
    """Convert a PipelineEvent into a JSON-safe dict for SSE."""
    d: dict = {
        "kind": event.kind,
        "timestamp": event.timestamp,
        "degraded": event.degraded,
    }
    if event.tokens is not None:
        d["tokens"] = event.tokens
    if event.attempt is not None:
        d["attempt"] = event.attempt
    if event.validation is not None:
        d["validation"] = asdict(event.validation)
    if event.critic is not None:
        d["critic"] = asdict(event.critic)
    if event.markdown is not None:
        d["markdown"] = event.markdown
    if event.output_path is not None:
        d["output_path"] = str(event.output_path)
    if event.error is not None:
        d["error"] = event.error
    return d


# ---------------------------------------------------------------------------
# History scanning
# ---------------------------------------------------------------------------


def _scan_history(base: Path) -> list[DocumentSummary]:
    """Walk the outputs/ tree and return one DocumentSummary per file, newest first."""
    if not base.exists():
        return []
    files: list[Path] = []
    for path in base.rglob("*.md"):
        if path.is_file():
            files.append(path)
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    out: list[DocumentSummary] = []
    from .standards import REQUIRED_SECTIONS as REQUIRED
    from .validators import validate_required_sections

    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        # mode is encoded as the parent dir name.
        mode = path.parent.name
        sections = REQUIRED.get(mode, ())
        validation = validate_required_sections(text, sections) if sections else None
        stat = path.stat()
        # First non-empty H1 or H2 is the title.
        title = path.stem
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                title = stripped[2:].strip()
                break
        out.append(
            DocumentSummary(
                path=str(path),
                title=title or path.stem,
                mode=mode,
                created_at=_iso(stat.st_mtime),
                size_bytes=stat.st_size,
                valid=bool(validation.ok) if validation else True,
                missing_sections=list(validation.missing_sections) if validation else [],
            )
        )
    return out


def _iso(mtime: float) -> str:
    from datetime import datetime

    return datetime.fromtimestamp(mtime).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app(
    chat_model_factory: Optional[Callable] = None,
    static_dir: Optional[Path] = None,
) -> FastAPI:
    """Build the FastAPI app.

    `chat_model_factory` is used by tests to inject a deterministic model. In
    production the server falls back to `build_chat_model()` for every request.
    `static_dir` points at the built React app (projects/specguard/frontend/dist);
    pass None to disable static serving (used during Vite dev).
    """
    app = FastAPI(title="SpecGuard", version="0.2.0")

    def _model():
        if chat_model_factory is not None:
            return chat_model_factory()
        return build_chat_model(_get_persisted().to_settings())

    # ----- health & settings -----

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        from datetime import datetime

        return HealthResponse(status="ok", version="0.2.0", server_time=datetime.now().isoformat(timespec="seconds"))

    @app.get("/api/settings", response_model=SettingsResponse)
    def get_settings() -> SettingsResponse:
        s = _get_persisted()
        return SettingsResponse(
            provider=s.provider,
            model=s.model,
            ollama_base_url=s.ollama_base_url,
            minimax_base_url=s.minimax_base_url,
            output_dir=str(_output_dir()),
            has_openai_key=s.has_openai_key,
            has_anthropic_key=s.has_anthropic_key,
            has_minimax_key=s.has_minimax_key,
        )

    @app.post("/api/settings", response_model=SettingsResponse)
    def update_settings(patch: SettingsUpdate) -> SettingsResponse:
        if patch.provider is not None and patch.provider not in SUPPORTED_PROVIDERS:
            raise HTTPException(status_code=400, detail=f"unknown provider {patch.provider!r}")
        current = _get_persisted()
        if patch.provider is not None:
            current.provider = patch.provider
            current.model = DEFAULT_MODELS[patch.provider]
        if patch.model is not None:
            current.model = patch.model
        if patch.ollama_base_url is not None:
            current.ollama_base_url = patch.ollama_base_url
        if patch.minimax_base_url is not None:
            current.minimax_base_url = patch.minimax_base_url
        saved = _save_persisted(current)
        return SettingsResponse(
            provider=saved.provider,
            model=saved.model,
            ollama_base_url=saved.ollama_base_url,
            minimax_base_url=saved.minimax_base_url,
            output_dir=str(_output_dir()),
            has_openai_key=saved.has_openai_key,
            has_anthropic_key=saved.has_anthropic_key,
            has_minimax_key=saved.has_minimax_key,
        )

    @app.post("/api/api-key")
    def set_api_key(update: ApiKeyUpdate) -> dict:
        """Save or clear a cloud-provider API key in .env.

        Security: this endpoint binds only to 127.0.0.1 by default, so the
        key is never exposed to the network. Treat the saved key as
        sensitive — don't commit the resulting .env to git.
        """
        env_name = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "minimax": "MINIMAX_API_KEY",
        }.get(update.provider)
        if env_name is None:
            raise HTTPException(status_code=400, detail=f"unknown provider {update.provider!r}")
        if update.clear:
            clear_env_var(env_name)
        else:
            if not update.key.strip():
                raise HTTPException(status_code=400, detail="key cannot be empty")
            write_env_var(env_name, update.key.strip())
        return {
            "ok": True,
            "provider": update.provider,
            "configured": False if update.clear else True,
        }

    # ----- modes -----

    @app.get("/api/modes", response_model=ModesResponse)
    def list_modes() -> ModesResponse:
        labels = {"prd": "PRD", "brd": "BRD", "tech_scope": "Tech scope"}
        return ModesResponse(
            modes=[
                ModeInfo(name=k, label=labels.get(k, k), sections=list(v))
                for k, v in REQUIRED_SECTIONS.items()
            ]
        )

    # ----- generation (SSE) -----

    @app.post("/api/generate")
    def generate(req: GenerateRequest) -> StreamingResponse:
        if req.mode not in REQUIRED_SECTIONS:
            raise HTTPException(status_code=400, detail=f"unknown mode {req.mode!r}")
        out_dir = Path(req.output_dir) if req.output_dir else _output_dir()
        gen_req = GenerationRequest(idea=req.idea, mode=req.mode, output_dir=out_dir)
        model = _model()

        def event_stream():
            try:
                for event in generate_document_stream(gen_req, chat_model=model):
                    payload = _event_to_dict(event)
                    yield f"data: {json.dumps(payload)}\n\n".encode()
                yield b"data: [DONE]\n\n"
            except Exception as exc:  # pragma: no cover - defensive
                err = {"kind": "error", "error": str(exc)}
                yield f"data: {json.dumps(err)}\n\n".encode()
                yield b"data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    # ----- history & document retrieval -----

    @app.get("/api/history", response_model=HistoryResponse)
    def history() -> HistoryResponse:
        return HistoryResponse(documents=_scan_history(_output_dir()))

    @app.get("/api/document")
    def document(path: str = Query(...)) -> PlainTextResponse:
        p = Path(path)
        base = _output_dir().resolve()
        try:
            p_resolved = p.resolve()
        except OSError:
            raise HTTPException(status_code=400, detail="invalid path")
        # Sandbox: must live under the configured output dir.
        if base not in p_resolved.parents and p_resolved != base:
            raise HTTPException(status_code=403, detail="path is outside the output directory")
        if not p.exists() or not p.is_file():
            raise HTTPException(status_code=404, detail="not found")
        return PlainTextResponse(p.read_text(encoding="utf-8"), media_type="text/markdown")

    # ----- static (built React) -----

    if static_dir is not None and static_dir.exists():
        @app.get("/")
        def root() -> FileResponse:
            index = static_dir / "index.html"
            if index.exists():
                return FileResponse(index)
            raise HTTPException(status_code=404, detail="frontend not built")

        @app.get("/assets/{path:path}")
        def assets(path: str) -> FileResponse:
            f = static_dir / "assets" / path
            if not f.exists():
                raise HTTPException(status_code=404)
            return FileResponse(f)

        @app.get("/favicon.svg")
        def favicon() -> FileResponse:
            f = static_dir / "favicon.svg"
            if not f.exists():
                raise HTTPException(status_code=404)
            return FileResponse(f, media_type="image/svg+xml")

        # Catch-all for client-side routes (history-API). Must come AFTER /api/*
        # so API routes take precedence. Returns the React index.html so the
        # client-side router can take over.
        @app.get("/{full_path:path}")
        def spa_fallback(full_path: str) -> FileResponse:
            # Defense-in-depth: never serve index.html for anything that looks
            # like it should hit the API.
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404)
            return FileResponse(static_dir / "index.html")

    return app


# A module-level app for `uvicorn specguard.server:app` (used by the CLI).
app = create_app(static_dir=Path(__file__).parent.parent.parent / "frontend" / "dist")
