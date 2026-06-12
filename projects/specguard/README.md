# SpecGuard AI

An AI product-spec assistant that generates PRDs/BRDs/tech scopes and self-reviews them using rubric-based Deep Agent middleware, plus a standards-driven LangChain pipeline for local Ollama.

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

See `.hermes/plans/2026-06-12_073900-specguard-ai.md` and `docs/superpowers/plans/2026-06-12-local-slm-specguard.md` for the build plans.
