# Repository Guidelines

## Project Structure & Module Organization

This is a monorepo (`my_slm_adventures`) of small-language-model experiments. The first subproject is `specguard-ai` at `projects/specguard/`. Runtime code lives in `projects/specguard/src/specguard/`, with the CLI entry point exposed as `specguard = "specguard.cli:_compat_entry"` (compatibility wrapper that dispatches `specguard "idea" --mode prd` to `specguard generate "idea" --mode prd`). Core agent construction is in `src/specguard/agent.py`; rubrics are in `src/specguard/rubrics.py`; prompt builders live under `src/specguard/prompts/`; deterministic helper tools live under `src/specguard/tools/`. Document standards (PRD/BRD/tech-scope) live in `src/specguard/standards/`. The LangChain provider gateway and explicit generation pipeline live in `src/specguard/llm_gateway.py` and `src/specguard/pipeline.py` respectively. Tests are in `projects/specguard/tests/`. Keep generated caches such as `__pycache__/` and `.pytest_cache/` out of commits.

## Build, Test, and Development Commands

All commands run from `projects/specguard/`:

- `uv sync --extra dev`: install the package with development tools.
- `uv run specguard models check`: print the configured LLM provider and model.
- `uv run specguard generate "Build an app..." --mode prd`: generate a document.
- `uv run specguard "Build an app..." --mode prd`: compatibility invocation (same as `generate`).
- `uv run pytest`: run the unit test suite.
- `uv run pytest -m integration`: run tests marked as real provider integrations; requires API keys.
- `uv run ruff check .`: lint Python files using the configured Ruff rules.
- `uv run mypy src`: type-check the package source.

Copy `projects/specguard/.env.example` to `projects/specguard/.env` for local LLM-backed runs. Defaults to Ollama with `gemma3:4b`; override with `SPECGUARD_PROVIDER`, `SPECGUARD_MODEL`, `OLLAMA_BASE_URL`. Set `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY` after `uv sync --extra anthropic`) for cloud providers.

## Coding Style & Naming Conventions

Use Python 3.11 syntax and four-space indentation. Ruff is configured for a 100-character line length. Prefer small, deterministic helpers in `src/specguard/tools/` and keep provider-specific logic near the gateway/agent boundary. Use `snake_case` for functions, variables, and modules; `UPPER_SNAKE_CASE` for constants such as `SUPPORTED_PROVIDERS`; and descriptive `test_...` names for pytest tests.

## Testing Guidelines

The project uses `pytest`. Add or update tests for every behavioral change, especially rubric content, prompt construction, tool output, validator behavior, pipeline output, and CLI/agent smoke behavior. Keep default tests deterministic and offline. Mark real LLM/provider tests with `@pytest.mark.integration` so they are skipped unless explicitly selected. Name test files `test_<area>.py` and test functions `test_<behavior>()`.

## Commit & Pull Request Guidelines

Recent history follows Conventional Commit style, for example `feat(tools): deterministic scope estimator`, `chore(deps): add deepagents, langgraph, openai, cli deps`, and `feat(specguard): add document standards`. Use concise imperative subjects with an optional scope: `feat(prompts): ...`, `fix(agent): ...`, `test(rubrics): ...`.

Pull requests should include a short problem statement, the implemented change, test evidence such as `uv run pytest`, and any API-key requirements. Link related issues or plans when available, and include CLI output examples when changing user-facing behavior.

## Security & Configuration Tips

Never commit `.env` or real API keys. Prefer `.env.example` for documenting required variables. Treat integration tests and CLI runs as potentially billable because they may call external LLM providers.
