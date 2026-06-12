# SpecGuard AI

An AI product-spec assistant that generates PRDs/BRDs/tech scopes and self-reviews them using rubric-based Deep Agent middleware.

## Quick start

```bash
# one-time: install uv (https://docs.astral.sh/uv/)
uv sync --extra dev
cp .env.example .env      # add your OPENAI_API_KEY
uv run specguard "Build an app for interior designers to manage quotation, billing, GST invoice, labour payments, and procurement." --mode prd
```

See `.hermes/plans/2026-06-12_073900-specguard-ai.md` for the full build plan.
