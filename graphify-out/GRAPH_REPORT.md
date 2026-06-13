# Graph Report - .  (2026-06-13)

## Corpus Check
- Corpus is ~37,202 words - fits in a single context window. You may not need a graph.

## Summary
- 397 nodes · 748 edges · 22 communities (20 shown, 2 thin omitted)
- Extraction: 83% EXTRACTED · 17% INFERRED · 0% AMBIGUOUS · INFERRED: 129 edges (avg confidence: 0.6)
- Token cost: 103,972 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 18|Community 18]]

## God Nodes (most connected - your core abstractions)
1. `GenerationRequest` - 39 edges
2. `generate_document_stream()` - 26 edges
3. `Settings` - 19 edges
4. `PersistedSettings` - 19 edges
5. `PipelineEvent` - 19 edges
6. `generate_document()` - 15 edges
7. `GenerationError` - 14 edges
8. `critique()` - 13 edges
9. `create_app()` - 13 edges
10. `ValidationResult` - 13 edges

## Surprising Connections (you probably didn't know these)
- `GenerationRequest` --uses--> `GenerationRequest`  [INFERRED]
  tests/test_pipeline_multirole.py → src/specguard/pipeline.py
- `SpecGuard AI: Rubric-Guided PRD Generator` --semantically_similar_to--> `Local SLM SpecGuard Implementation Plan`  [INFERRED] [semantically similar]
  .hermes/plans/2026-06-12_073900-specguard-ai.md → docs/superpowers/plans/2026-06-12-local-slm-specguard.md
- `AlwaysValidChatModel` --uses--> `GenerationRequest`  [INFERRED]
  tests/test_pipeline.py → src/specguard/pipeline.py
- `FakeChatModel` --uses--> `GenerationRequest`  [INFERRED]
  tests/test_pipeline.py → src/specguard/pipeline.py
- `Path` --uses--> `GenerationRequest`  [INFERRED]
  tests/test_pipeline_multirole.py → src/specguard/pipeline.py

## Import Cycles
- 1-file cycle: `src/specguard/server.py -> src/specguard/server.py`

## Hyperedges (group relationships)
- **Multi-Role SLM Architecture: Planner / Writer / Critic / Router** — planner_role, writer_role, critic_role, router_decision_function [EXTRACTED 1.00]
- **Three Document Standards: PRD / BRD / Tech Scope** — prd_standard_requirement, brd_standard_requirement, tech_scope_standard_requirement [EXTRACTED 1.00]
- **Deterministic Tools: Clarifier / Checklist / Scope Estimator** — clarifier_tool, domain_checklist_tool, scope_estimator_tool [EXTRACTED 1.00]
- **Provider Options: Ollama / OpenAI / Anthropic** — ollama_default_model, openai_provider_option, anthropic_provider_option [EXTRACTED 1.00]

## Communities (22 total, 2 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (46): Brief, SpecGuard role helpers., Brief, plan(), _planner_prompt(), Planner role: run the deterministic tools, then one SLM call to write a brief., _content(), draft() (+38 more)

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (37): BaseChatModel, RuntimeError, _compat_entry(), _env_flag(), generate(), main(), models(), models_check() (+29 more)

### Community 2 - "Community 2"
Cohesion: 0.11
Nodes (39): BaseModel, FastAPI, PersistedSettings, PipelineEvent, clear_env_var(), PersistedSettings, Persistent settings store.  User-controlled settings (provider, model, ollama UR, Idempotently set a key in .env. Creates the file if missing. (+31 more)

### Community 3 - "Community 3"
Cohesion: 0.08
Nodes (30): Block, MarkdownView(), GeneratePage(), STEP_LABELS, TraceRow, Filter, FILTERS, HistoryPage() (+22 more)

### Community 4 - "Community 4"
Cohesion: 0.11
Nodes (26): Protocol, CriterionScore, _critic_prompt(), CriticVerdict, critique(), extract_json(), Critic role: score a draft against the mode rubric as structured JSON.  SLMs are, Validates a draft against required sections. Returns ValidationResult. (+18 more)

### Community 5 - "Community 5"
Cohesion: 0.11
Nodes (25): GenerationRequest, ChatModel, _estimate_tokens(), generate_document(), generate_document_stream(), _now(), Run the multi-role loop, yielding a PipelineEvent after each step.      `chat_mo, Cheap token estimate: chars/4. Surfaced to the UI immediately after each call. (+17 more)

### Community 6 - "Community 6"
Cohesion: 0.08
Nodes (17): _ai(), client(), FakeChatModel, _parse_sse(), Path, Switching from ollama to openai should auto-set the model to gpt-4.1-mini     un, The fixture's FakeChatModel returns a complete PRD on revise, so PRD     generat, Parse text/event-stream body into a list of {kind, ...} dicts. (+9 more)

### Community 7 - "Community 7"
Cohesion: 0.11
Nodes (15): build_system_prompt(), System prompt construction for the SpecGuard writer agent., build_agent(), Construct a SpecGuard deep agent for the given mode., load_standard(), Bundled SpecGuard document standards., test_build_agent_returns_compiled_graph(), test_build_agent_unknown_mode_raises() (+7 more)

### Community 8 - "Community 8"
Cohesion: 0.11
Nodes (21): BRD Standard with Six Required Sections, Clarifier Tool: Domain-Specific Questions, CLI Subcommands: generate, models check, serve, Critic JSON Robustness Ladder: Extraction, Retry, Fallback, Critic Role: Scored Rubric JSON Evaluation, Degraded Draft Path: Save with Warnings on Budget Exhaustion, Domain Checklist Tool: Context-Aware Items, Markdown-Only Output Format (+13 more)

### Community 9 - "Community 9"
Cohesion: 0.14
Nodes (11): AlwaysValidChatModel, FakeChatModel, Path, Budget exhausted → degraded result, not GenerationError (degrade-not-block)., Routes by system message role: planner → brief, critic → JSON, writer → docs., Always returns a complete valid PRD., Always returns a partial PRD that never passes validation., StillInvalidChatModel (+3 more)

### Community 10 - "Community 10"
Cohesion: 0.23
Nodes (14): get_rubric(), get_rubric_criteria(), list_modes(), ModeError, Per-mode rubric strings consumed by RubricMiddleware.  Each rubric is a checklis, Raised when an unknown mode is requested., RubricCriterion, test_brd_rubric_mentions_stakeholders() (+6 more)

### Community 11 - "Community 11"
Cohesion: 0.43
Nodes (5): RouteDecision, decide(), test_decide_degrades_when_budget_is_exhausted(), test_decide_finalizes_when_validation_and_critic_pass(), test_decide_revises_when_budget_remains()

### Community 12 - "Community 12"
Cohesion: 0.33
Nodes (6): Config-Driven LangChain Provider Gateway, Local SLM SpecGuard Implementation Plan, Monorepo: Root Docs + projects/specguard Subproject, Multi-Role SLM Pipeline Implementation Plan, Rubric-Based Self-Correction Loop, SpecGuard AI: Rubric-Guided PRD Generator

### Community 14 - "Community 14"
Cohesion: 0.40
Nodes (5): Anthropic Cloud Provider Option, LangChain Provider Gateway, Local SLM SpecGuard Design, Ollama Default: gemma4:latest for 8GB VRAM, OpenAI Cloud Provider Option

## Knowledge Gaps
- **21 isolated node(s):** `Block`, `queryClient`, `root`, `TraceRow`, `STEP_LABELS` (+16 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `generate_document_stream()` connect `Community 5` to `Community 0`, `Community 1`, `Community 2`, `Community 4`, `Community 7`, `Community 11`?**
  _High betweenness centrality (0.112) - this node is a cross-community bridge._
- **Why does `GenerationRequest` connect `Community 2` to `Community 1`, `Community 5`, `Community 9`?**
  _High betweenness centrality (0.100) - this node is a cross-community bridge._
- **Why does `plan()` connect `Community 0` to `Community 1`, `Community 5`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._
- **Are the 25 inferred relationships involving `GenerationRequest` (e.g. with `FastAPI` and `GenerationRequest`) actually correct?**
  _`GenerationRequest` has 25 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `Settings` (e.g. with `BaseChatModel` and `PersistedSettings`) actually correct?**
  _`Settings` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `PersistedSettings` (e.g. with `FastAPI` and `PersistedSettings`) actually correct?**
  _`PersistedSettings` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `PipelineEvent` (e.g. with `FastAPI` and `PersistedSettings`) actually correct?**
  _`PipelineEvent` has 15 INFERRED edges - model-reasoned connections that need verification._