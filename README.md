# my_slm_adventures

Local small-language-model experiments and tools.

## Projects

- [SpecGuard](projects/specguard/README.md): LangChain-powered PRD, BRD, and technical-scope generator with local Ollama support.

## Working With SpecGuard

```bash
cd projects/specguard
uv sync --extra dev
uv run specguard generate "Build an app for interior designers..." --mode prd
```
