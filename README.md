# my_slm_adventures

Local small-language-model experiments and tools. Everything in this monorepo runs offline first — your ideas never leave your machine.

## Projects

- [SpecGuard](projects/specguard/README.md): a local PRD/BRD/tech-scope generator that drafts, validates, reviews, revises, and saves Markdown documents. Ships with a React web UI (FastAPI + Vite) and a CLI. Defaults to Ollama with `gemma4:latest`.

## Working With SpecGuard (CLI)

```bash
cd projects/specguard
uv sync --extra dev
uv run specguard generate "Build an app for interior designers..." --mode prd
```

## Working With SpecGuard (Web UI)

```bash
cd projects/specguard
uv sync --extra dev
cd frontend && npm install && cd ..
uv run specguard serve
```

Then open `http://127.0.0.1:8765/` (the command auto-opens your browser). Use the Settings page to pick a provider/model and paste cloud API keys; everything persists across restarts.

For frontend dev with hot reload, run the API and Vite in two terminals:

```bash
# terminal 1
uv run specguard serve --port 8765

# terminal 2
cd frontend
npm run dev          # Vite serves on :5173, proxies /api to FastAPI
```

## Subproject Layout

```
my_slm_adventures/
├── AGENTS.md
├── README.md                   ← you are here
└── projects/
    └── specguard/              ← the first subproject
        ├── pyproject.toml
        ├── src/specguard/      ← Python package (CLI, server, pipeline, gateway)
        ├── frontend/           ← React + Vite + TypeScript app
        ├── standards/          ← PRD/BRD/tech-scope section templates
        ├── tests/
        └── README.md            ← detailed SpecGuard docs
```

## Documentation

- [SpecGuard full README](projects/specguard/README.md) — install, web UI, CLI, HTTP API, architecture, tests
- [Local SLM SpecGuard implementation plan](docs/superpowers/plans/2026-06-12-local-slm-specguard.md) — original design spec
