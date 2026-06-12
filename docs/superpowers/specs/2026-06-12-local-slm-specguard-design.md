# Local SLM SpecGuard Design

## Purpose

`my_slm_adventures` is an umbrella repository for local small-language-model experiments and tools. The first subproject is SpecGuard: a LangChain-powered document generator that creates PRDs, BRDs, and technical scopes from a user idea using a configurable model gateway.

The first milestone prioritizes reliable local inference on an 8GB VRAM laptop. Training and fine-tuning are deferred until the generator produces enough useful examples to justify a dataset workflow.

## Repository Shape

The repository will become a lightweight monorepo:

```text
my_slm_adventures/
  AGENTS.md
  README.md
  docs/
    adr/
    agents/
    superpowers/specs/
  projects/
    specguard/
      pyproject.toml
      uv.lock
      .env.example
      README.md
      standards/
        prd.md
        brd.md
        tech_scope.md
      outputs/
      src/specguard/
      tests/
```

SpecGuard owns its Python package, lockfile, tests, standards, and generated outputs. The root owns umbrella documentation and future shared agent configuration.

## Model Gateway

SpecGuard will use LangChain as the orchestration layer. Pipeline code will request a chat model from a provider gateway instead of importing provider-specific classes directly.

Supported providers for the first design:

- `ollama`: local default, targeting `gemma3:4b` for 8GB VRAM laptops.
- `openai`: optional cloud comparison path.
- `anthropic`: optional cloud comparison path.

Example configuration:

```env
SPECGUARD_PROVIDER=ollama
SPECGUARD_MODEL=gemma3:4b
OLLAMA_BASE_URL=http://localhost:11434
```

Fallback local model options will be documented: `llama3.2:3b` for speed and `qwen3:8b` for quality if the machine handles it.

## Generation Pipeline

The main path will be an explicit LangChain pipeline:

1. Load the selected document standard: `prd`, `brd`, or `tech_scope`.
2. Build a mode-specific prompt from the user idea and standard.
3. Draft Markdown with the configured chat model.
4. Validate required sections.
5. Run a rubric review pass.
6. Revise once using validation and rubric feedback.
7. Save the final Markdown to `outputs/<mode>/`.

The existing Deep Agents/RubricMiddleware path can remain as an experimental or legacy path, but it will not be the default local-SLM workflow.

## CLI

The CLI will move toward subcommands while preserving the simple invocation where practical:

```bash
uv run specguard generate "Build an app for interior designers..." --mode prd
uv run specguard generate "..." --mode brd
uv run specguard generate "..." --mode tech_scope
uv run specguard models check
```

Generated documents will be Markdown only in the first milestone. PDF, DOCX, and structured JSON exports are future additions.

## Standards

SpecGuard will define repo-owned standards before supporting external company templates:

- `standards/prd.md`
- `standards/brd.md`
- `standards/tech_scope.md`

Each standard will state required sections, quality expectations, and review criteria. The pipeline will fail or revise when required sections are missing.

## Deferred Work

Fine-tuning, LoRA/QLoRA scripts, PDF/DOCX export, and dataset export are intentionally out of scope for the first implementation. Run capture may be added later only if it stays lightweight and avoids storing secrets.

## Testing

Tests should cover provider-gateway configuration, prompt/standard loading, section validation, output-path generation, and CLI behavior. Model calls should be mocked by default. Real Ollama/cloud tests must be marked as integration tests.
