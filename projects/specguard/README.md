# SpecGuard AI

An AI product-spec assistant that generates PRDs/BRDs/tech scopes and self-reviews them using rubric-based Deep Agent middleware, plus a standards-driven LangChain pipeline for local Ollama. Ships with a small React web UI that runs locally on your machine.

## Quick start (CLI)

```bash
uv sync --extra dev
ollama pull gemma3:4b
uv run specguard models check
uv run specguard generate "Build an app for interior designers to manage quotation, billing, GST invoice, labour payments, and procurement." --mode prd
```

## Quick start (Web UI)

```bash
uv sync --extra dev
cd frontend && npm install && cd ..
uv run specguard serve
```

Then open `http://127.0.0.1:8765/` in your browser. The server auto-opens it
on first launch. Everything (provider, model, Ollama URL, and cloud API keys)
is editable from the Settings page; nothing requires a terminal after the
first run.

For frontend dev with hot reload, run two terminals:

```bash
# terminal 1
uv run specguard serve --port 8765

# terminal 2
cd frontend
npm run dev          # Vite serves on :5173 with /api proxied to FastAPI
```

## Configuration

Set local defaults in `.env` (the server reads these on startup; the
Settings page writes them back when you change anything via the UI):

```env
SPECGUARD_PROVIDER=ollama
SPECGUARD_MODEL=gemma3:4b
OLLAMA_BASE_URL=http://localhost:11434
OPENAI_API_KEY=sk-...           # only if you switch provider to OpenAI
ANTHROPIC_API_KEY=sk-ant-...    # only if you switch provider to Anthropic
```

The Settings page also writes user-controlled settings to `settings.json`
(provider, model, Ollama URL). API keys are written to `.env` so they
coexist with any keys you set by other means. `settings.json` and `.env` are
gitignored; don't commit them.

## HTTP API

The web UI uses the same FastAPI app that `specguard serve` boots. For
non-UI use, the endpoints are:

| Method | Path                | Purpose                                       |
|--------|---------------------|-----------------------------------------------|
| GET    | `/api/health`       | Liveness check                                |
| GET    | `/api/settings`     | Current provider/model/URL + which keys exist |
| POST   | `/api/settings`     | Update provider/model/URL (persists to disk)  |
| POST   | `/api/api-key`      | Save or clear a cloud-provider API key        |
| GET    | `/api/modes`        | Supported document modes + their sections     |
| POST   | `/api/generate`     | SSE stream of pipeline events                 |
| GET    | `/api/history`      | List of saved documents, newest first         |
| GET    | `/api/document`     | Read a single saved document (sandboxed)      |

## Architecture

```
[Browser]  → React (Vite, :5173 dev or served by FastAPI)
   │              │
   │ HTTP+JSON    │ dev: Vite proxies /api to FastAPI
   │ SSE          │ prod: FastAPI serves built React
   ▼              ▼
[FastAPI :8765]  src/specguard/server.py
   │
   │ uses (no duplication)
   ▼
[specguard.pipeline + specguard.llm_gateway + specguard.persistence]
```

The generation pipeline is the same one the CLI uses: draft → validate →
review → revise → save. SSE streams each step to the browser as it
completes, so the trace panel fills in in real time.

## Test commands

```bash
uv run pytest -q          # Python tests (52 passing)
uv run pytest -m integration  # tests that hit real LLM providers
uv run ruff check .       # lint
uv run mypy src           # type check
cd frontend && npm run build  # type-check + build the React app
```

See `../../docs/superpowers/plans/2026-06-12-local-slm-specguard.md` for the implementation plan.
