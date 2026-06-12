# SpecGuard

A local-first assistant that turns a one-paragraph idea into a structured product document (PRD, BRD, or technical scope). It drafts with an LLM, validates against a standard, self-reviews, revises, and saves a Markdown file to your machine. Nothing leaves your computer unless you explicitly choose a cloud provider.

Defaults to [Ollama](https://ollama.com) running `gemma4:latest`. Optional cloud providers: OpenAI and Anthropic.

## Table of Contents

- [Quick start (Web UI)](#quick-start-web-ui) — recommended for non-developers
- [Quick start (CLI)](#quick-start-cli) — for terminal users
- [Using the Web UI](#using-the-web-ui)
- [Switching providers and models](#switching-providers-and-models)
- [Adding cloud API keys](#adding-cloud-api-keys)
- [Where files are saved](#where-files-are-saved)
- [HTTP API](#http-api)
- [Architecture](#architecture)
- [Tests and quality gates](#tests-and-quality-gates)
- [Troubleshooting](#troubleshooting)
- [Project layout](#project-layout)
- [Implementation plan](#implementation-plan)

---

## Quick start (Web UI)

```bash
cd projects/specguard
uv sync --extra dev
cd frontend && npm install && cd ..
uv run specguard serve
```

A browser tab opens at `http://127.0.0.1:8765/`. You're ready to generate documents. No further configuration is needed if you want to use the default local model (Ollama + gemma4).

> Don't have Ollama yet? [Install it from ollama.com](https://ollama.com), then `ollama pull gemma4:latest`. The first time you generate, Ollama will need a few minutes to load the 9.6 GB model.

## Quick start (CLI)

```bash
cd projects/specguard
uv sync --extra dev
ollama pull gemma4:latest
uv run specguard models check
uv run specguard generate "Build an app for interior designers to manage quotation, billing, GST invoice, labour payments, and procurement." --mode prd
```

Subcommands: `generate` (one-shot), `models check` (verify provider), `serve` (start the web UI), `agent` (legacy Deep Agent path).

## Using the Web UI

The UI has three pages, switched via the top nav:

| Page | What it does |
|---|---|
| **Generate** | Type an idea, pick a mode (PRD / BRD / Tech scope), click Run pipeline. Watch the trace panel fill in as the model works through draft → validate → review → revise → save. |
| **History** | Every saved document, newest first. Filter by mode, see validation status, click a row to see its file path. |
| **Settings** | Pick provider (Ollama / OpenAI / Anthropic), pick a model, optionally edit the Ollama base URL, paste or clear cloud API keys. All changes persist across restarts. |

## Switching providers and models

Open **Settings** and choose from the dropdown. Switching providers auto-snaps the model to a sensible default for that provider:

- **Ollama** → `gemma4:latest` (also accepts `gemma3:4b`, `gemma3:12b`, `llama3.1:8b`, `qwen2.5:7b`, anything else you have locally)
- **OpenAI** → `gpt-4.1-mini` (also `gpt-4.1`, `gpt-4o-mini`, `o4-mini`)
- **Anthropic** → `claude-3-5-haiku-latest` (also `claude-3-5-sonnet-latest`, `claude-sonnet-4-5`)

You can type any custom model name in the model field — the dropdown is just suggestions based on what you have in `ollama list`.

## Adding cloud API keys

When you switch to OpenAI or Anthropic, a new "API key" card appears on the Settings page. Paste your key there and click Save — SpecGuard writes it to `.env` and the running server picks it up immediately (no restart needed). Click **Clear** to remove it. The key is stored locally; it's never sent anywhere except to the provider when you run a generation.

## Where files are saved

Two locations, two purposes:

| File | Holds | Shared safely? |
|---|---|---|
| `settings.json` | provider, model, Ollama URL, key-presence flags | Yes — no secrets |
| `.env` | actual API key values | No — gitignored |
| `outputs/<mode>/<timestamp>-<slug>.md` | generated documents | Up to you |

Both `settings.json` and `.env` are in `.gitignore` so you can't accidentally commit secrets. To back up your setup, copy both files. To wipe it, delete both.

## HTTP API

`specguard serve` boots a FastAPI app on `127.0.0.1:8765`. The web UI uses it; you can also hit it directly.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness check |
| GET | `/api/settings` | Current provider/model/URL + which keys exist |
| POST | `/api/settings` | Update provider/model/URL (persists to disk) |
| POST | `/api/api-key` | Save or clear a cloud-provider API key |
| GET | `/api/modes` | Supported document modes + their required sections |
| POST | `/api/generate` | SSE stream of pipeline events |
| GET | `/api/history` | List of saved documents, newest first |
| GET | `/api/document?path=...` | Read a single saved document (sandboxed to the output dir) |

Example: stream a generation with curl

```bash
curl -N -X POST http://127.0.0.1:8765/api/generate \
  -H "Content-Type: application/json" \
  -d '{"idea":"a tiny todo app","mode":"prd"}'
```

You'll see one `data:` line per pipeline event, ending with `data: [DONE]`.

## Architecture

```
[Browser]  → React (Vite, :5173 in dev or served by FastAPI in prod)
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

The generation pipeline is the same one the CLI uses: **draft → validate → review → revise → save**. SSE streams each step to the browser as it completes.

### Project layout

```
projects/specguard/
├── pyproject.toml
├── src/specguard/
│   ├── cli.py              ← Click CLI + `serve` subcommand
│   ├── server.py           ← FastAPI app + SSE
│   ├── pipeline.py         ← generate_document / generate_document_stream
│   ├── llm_gateway.py      ← provider factory (Ollama/OpenAI/Anthropic)
│   ├── config.py           ← env-driven Settings
│   ├── persistence.py      ← settings.json + .env helpers
│   ├── standards/          ← PRD/BRD/tech-scope templates
│   ├── prompts/            ← legacy Deep Agent system prompt
│   ├── tools/              ← legacy Deep Agent tools
│   ├── rubrics.py          ← legacy Deep Agent rubrics
│   └── agent.py            ← legacy Deep Agent entry point
├── frontend/               ← React + Vite + TypeScript app
│   ├── src/
│   │   ├── pages/GeneratePage.tsx
│   │   ├── pages/HistoryPage.tsx
│   │   ├── pages/SettingsPage.tsx
│   │   ├── components/MarkdownView.tsx
│   │   ├── api.ts          ← fetch + SSE client
│   │   └── styles.css      ← Apple-minimal dark theme
│   └── package.json
└── tests/                  ← pytest (53 passing)
```

## Tests and quality gates

```bash
uv run pytest -q          # 53 tests, fully offline
uv run pytest -m integration  # hits real LLM providers; needs API keys
uv run ruff check .       # lint (clean)
uv run mypy src           # type check (clean)
cd frontend && npm run build  # type-check + build the React app
```

Tests are deterministic and offline by default. The integration marker is reserved for live LLM tests that need keys.

## Troubleshooting

**"model 'gemma4:latest' not found"**
- Run `ollama list`. If gemma4:latest isn't there, run `ollama pull gemma4:latest`. If you have a different gemma tag, paste it into the model field on the Settings page.

**"connection refused" on Ollama**
- The Ollama server may not be running. Start it: `ollama serve` (or open the Ollama desktop app). Default base URL: `http://localhost:11434` — change it on the Settings page if your install listens elsewhere.

**"only one usage of each socket address" / port 8765 in use**
- Another process is bound to 8765. Either kill it (Windows: `netstat -ano | findstr :8765`, then `taskkill /F /PID <pid>`) or run `uv run specguard serve --port 8800` to use a different port.

**Web UI loads but settings are blank**
- Open browser DevTools → Console. If you see CORS errors, your browser is on a different origin than the API. Make sure the URL in the bar matches `http://127.0.0.1:8765/`. If you ran `npm run dev`, Vite's proxy expects FastAPI on `:8765`.

**OpenAI/Anthropic requests return 401**
- The key in the Settings page was saved but the server may need a moment. Click the provider again, re-save, and try a generation. If the key is correct, check `.env` on disk: the line should read `OPENAI_API_KEY=sk-...` (or `ANTHROPIC_API_KEY=sk-ant-...`).

**Generated Markdown is missing required sections**
- SpecGuard validates against the standard and refuses to save a document that's missing sections — it raises a `GenerationError` instead. The trace panel will show the missing sections in red. Rephrase your idea with more specificity, or pick a stronger model.

**`uv run specguard serve` opens nothing in the browser**
- Your OS may be blocking the auto-open. Click the URL it prints: `http://127.0.0.1:8765/`. To suppress the auto-open, run with `uv run specguard serve --no-browser` or set `SPECGUARD_NO_BROWSER=1`.

## Implementation plan

The original design spec lives at `../../docs/superpowers/plans/2026-06-12-local-slm-specguard.md`.
