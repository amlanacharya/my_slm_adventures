\# PRD: Agent Workflow Blueprint \& Governance Harness



\*\*Label:\*\* `ready-for-agent`

\*\*Status:\*\* Draft for internal proposal / portfolio reference implementation



\---



\## Problem Statement



Teams building multi-step AI agents (10-12+ tool calls per task) have no systematic way to know whether an agent followed the correct business process before it took an action that matters. Today, evaluation is either absent or purely output-focused ("was the final answer good?"), not process-focused ("did the agent do the right things, in the right order, with the right approvals, before acting?").



This is acute in regulated, multi-step workflows like loan approval, claims processing, or procurement approval, where:



\- An agent might silently skip a mandatory step (e.g., risk evaluation) and still produce a plausible-looking decision.

\- An agent might take unnecessary or unexpected extra actions that don't change the final answer but indicate reasoning drift, wasted cost, or an underlying prompt/tool-design problem.

\- There is no mechanism to let a human safely intervene on a risky or unusual action \*before\* it commits, without halting every agent action indiscriminately.

\- When a human does override or approve an exception, that decision is not captured anywhere the system can reuse it — the same exception gets flagged, and asked about, over and over.

\- Business rules governing these workflows (approval thresholds, mandatory checks) change over time (new regulation, process simplification), and there's no versioned record of which rules were active when a given agent decision was made.



As an AI platform owner and business operations/governance owner, we need a way to define what an agent \*should\* do for a given process, observe what it \*actually\* does, intervene only where it matters, and have the system retain and apply what humans decide over time.



\---



\## Solution



A \*\*governance and evaluation harness\*\* for agentic workflows, built around four cooperating layers:



1\. \*\*Agent Workflow Blueprint\*\* — a versioned, human-editable definition of the expected action flow for a business process (e.g., loan approval), including required/optional/conditional/prohibited actions, approval thresholds, and allowed tools per action.

2\. \*\*Agent Harness\*\* — a tool-call wrapper that classifies every tool as read (side-effect-free) or write (state-mutating), logs every call to a trace, and gates only write actions pending evaluation.

3\. \*\*Evaluation Engine\*\* — compares the actual trace against the active blueprint using deterministic rules first, falling back to an LLM-as-judge for cases the blueprint doesn't explicitly cover, and short-circuits on previously-approved or previously-rejected patterns.

4\. \*\*HITL + Learning Layer\*\* — routes gated write actions to a human reviewer (via lightweight chat notification), captures approve/reject/append decisions as new blueprint variants, and lets a business admin review and cherry-pick these accumulated changes into a published blueprint version via a dedicated dashboard.



The system runs in two modes:



\- \*\*Live Mode\*\*: evaluates and, where necessary, pauses write actions before they commit, using async suspend-and-resume so no worker process blocks while waiting on a human.

\- \*\*Offline Mode\*\*: evaluates completed traces after the fact, using the identical evaluation engine and blueprint, for full-visibility auditing and pattern-mining — every deviation is logged here regardless of live-mode severity.



The flagship reference workflow is \*\*loan approval\*\* (NBFC domain), but the blueprint schema and evaluator are built workflow-agnostic (`workflow\_id` as a first-class dimension throughout) so a second workflow type can be onboarded without re-architecture, even though only loan approval is fully implemented and demoed in v1.



\---



\## User Stories



\### Blueprint Definition \& Versioning



1\. As a business admin, I want to define the expected action flow for a workflow as a structured blueprint, so that agent behavior has a clear baseline to be evaluated against.

2\. As a business admin, I want to mark each action in a blueprint as required, optional, conditional, or prohibited, so that the evaluator knows how strictly to treat deviations from each step.

3\. As a business admin, I want to define conditions under which a conditional action applies (e.g., loan amount thresholds, risk category), so that business rules are captured explicitly rather than implicitly in agent prompts.

4\. As a business admin, I want to specify allowed tools per action, so that the evaluator can detect when the wrong tool is used for a given step.

5\. As a business admin, I want every blueprint change to create a new version rather than overwriting history, so that I can audit how business rules evolved over time.

6\. As a business admin, I want to compare two blueprint versions side by side, so that I can understand exactly what changed between them.

7\. As a business admin, I want to roll back to a previous published blueprint version if a new version causes problems, so that I can recover quickly from a bad change.

8\. As a business admin, I want every agent run to record which blueprint version was active at runtime, so that evaluation results remain correct even after the blueprint is later updated.

9\. As a workflow owner, I want to define which mode (live or offline) a given workflow blueprint is evaluated under, so that lower-risk workflows can run offline-only if live gating isn't warranted.



\### Agent Harness \& Trace Capture



10\. As a developer, I want to wrap my agent's tools in a harness that classifies each as read or write, so that only state-mutating actions require gating.

11\. As a developer, I want every tool call (read or write, expected or not) logged to a persistent trace, so that nothing is lost even if it's never flagged as a deviation.

12\. As a developer, I want the harness to work regardless of which agent orchestration framework is used (LangGraph, raw SDK loop, custom orchestrator), so that the product isn't locked to one agent framework.

13\. As a developer, I want traces captured via our existing observability tool (LangFuse) rather than a duplicate custom trace store, so that I don't maintain two overlapping systems of record.

14\. As a developer, I want deviation flags and evaluation scores attached to LangFuse traces as custom metadata, so that trace data and evaluation data stay correlated without duplicating storage.

15\. As a platform owner, I want blueprint, variant, and HITL decision data to live in our own schema referencing LangFuse trace IDs, so that the genuinely novel governance logic isn't dependent on an external tool's data model.



\### Pre-Flight Input Validation



16\. As a system owner, I want tool arguments validated against a schema before the tool is called, so that malformed or invalid inputs are blocked before reaching an LLM or external API.

17\. As a system owner, I want invalid-input rejections to happen without an LLM-judge call, so that obviously bad calls don't incur unnecessary evaluation cost.

18\. As a system owner, I want pre-flight validation to run independently of deviation evaluation, so that "is this well-formed and permitted" stays separate from "is this expected given context."



\### Deviation Detection (Evaluation Engine)



19\. As an evaluator, I want to detect when a required action defined in the blueprint was skipped, so that missing mandatory steps are caught before a decision is finalized.

20\. As an evaluator, I want to detect when a prohibited action was taken, so that clearly disallowed behavior is caught deterministically without needing a judge call.

21\. As an evaluator, I want to detect when an extra, unexpected tool call occurs that isn't explicitly covered by the blueprint, so that novel deviations aren't silently ignored.

22\. As an evaluator, for deviations not covered by explicit blueprint rules, I want an LLM-as-judge to assess whether the action was necessary given the agent's task and context, so that reasonable flexibility isn't blocked by an overly rigid rule set.

23\. As an evaluator, I want deterministic rule checks (thresholds, required/prohibited actions) to never depend on the LLM judge, so that hard compliance requirements remain fully auditable and explainable.

24\. As an evaluator, I want unnecessary or unexpected read-tool calls to be logged and factored into the context of the next write-gate review rather than triggering their own separate live-mode pause, so that live mode stays low-noise while nothing is ignored.

25\. As an evaluator, I want every flagged deviation, regardless of severity or whether it blocked anything, recorded in the offline trace, so that full auditability is preserved independent of live-mode gating decisions.



\### Live-Mode Gating \& Async Approval



26\. As a system owner, I want only write (state-mutating) tool calls to trigger a live-mode pause, so that read-only information gathering never blocks agent execution.

27\. As a developer, I want a gated write action to suspend the agent run's state (trace so far, proposed action, deviation context) rather than block a worker thread, so that many concurrent pending approvals don't tie up compute resources.

28\. As a developer, I want a resume mechanism that reloads suspended state and continues execution once a HITL decision arrives, so that approval latency (minutes to hours) doesn't require dedicated idle infrastructure.

29\. As a system owner, I want a configurable timeout on pending write approvals, so that a stuck approval doesn't stall a loan application indefinitely.

30\. As a system owner, I want a write action to auto-reject if its timeout window elapses with no HITL response, so that the system fails closed rather than leaving state ambiguous.



\### HITL Review \& Decision Capture



31\. As a HITL reviewer, I want to receive a pending write-action approval as an actionable chat notification (e.g., Slack), so that I don't need to check a separate dashboard for routine approvals.

32\. As a HITL reviewer, I want to see the user request, the full action trace, the flagged deviation(s), and the reasoning behind the flag, so that I can make an informed approve/reject decision.

33\. As a HITL reviewer, I want to approve a flagged deviation and choose whether it should overwrite the existing expected pattern or be appended as an additional valid variant, so that my decision correctly reflects whether this is a new normal or an accepted exception alongside the old one.

34\. As a HITL reviewer, I want to reject a flagged deviation, so that the corresponding write action does not commit and the run is marked accordingly.

35\. As a HITL reviewer, I want my approve/reject decision to automatically create or update a draft blueprint version, so that my decision is captured as a reusable pattern without requiring a separate manual edit.

36\. As a system owner, I want a rejected deviation to be recorded as a negative variant symmetric to approved variants, so that repeat occurrences of the same disallowed pattern can be recognized automatically.

37\. As a system owner, I want the evaluator to check for a matching approved or rejected variant before invoking the LLM judge, so that previously-decided patterns don't incur repeated judge calls or repeated HITL prompts.

38\. As a system owner, I want a matched rejected-variant occurrence to short-circuit straight to a pre-contextualized HITL prompt (or auto-block if marked permanent), so that known-bad patterns are handled faster than novel ones.

39\. As a workflow owner, I want to be alerted if a rejected pattern recurs more than a configurable number of times, so that I can recognize when the underlying agent logic — not just the blueprint — needs to change.



\### Blueprint Draft \& Publish Workflow



40\. As a business admin, I want all HITL-approved or -rejected variants since the last published version to accumulate into a single running draft, so that I don't have to reconcile multiple conflicting draft versions.

41\. As a business admin, I want each variant within a draft to retain its own provenance (who approved/rejected it, when, from which run), so that I can audit the origin of every proposed change.

42\. As a business admin, I want to cherry-pick which variants within a draft to include when publishing, so that I retain full authority over what becomes an active business rule.

43\. As a business admin, I want a dedicated dashboard to review, compare, and publish blueprint drafts, so that I have a structured view for a decision that a chat notification isn't suited for.

44\. As a business admin, I want draft blueprint changes to have no effect on live evaluation until explicitly published, so that individual run-level HITL decisions can't silently alter production business rules.

45\. As a business admin, I want to optionally generalize a specific approved variant into a broader tolerance rule at publish time, so that trivially similar future cases aren't repeatedly re-flagged.



\### Compliance \& Data Handling



46\. As a compliance-conscious platform owner, I want known-sensitive fields (PAN numbers, account numbers, income figures) masked before being persisted to any trace or log, so that the reference implementation doesn't casually expose applicant PII.

47\. As a compliance-conscious platform owner, I want masking applied at the logging boundary rather than scattered throughout the evaluation logic, so that it's a single auditable control point.



\### Success Measurement



48\. As a platform owner, I want to track the false-positive rate of flagged deviations (flagged but approved as fine by reviewers), so that I can tell whether the evaluator is too aggressive.

49\. As a platform owner, I want to track mean HITL response time, so that I can tell whether live-mode gating introduces unacceptable delay to the business process.

50\. As a platform owner, I want to track the percentage of tool calls blocked at pre-flight validation, so that I have a proxy for token/API cost savings.

51\. As a platform owner, I want to track the repeat-offense rate of previously-rejected patterns, so that I can tell whether the negative-variant mechanism is actually reducing recurrence.



\---



\## Implementation Decisions



\*\*Scope framing:\*\* This PRD is written as an internal proposal with a reference implementation scoped to be fully buildable and defensible as a portfolio artifact. Standalone commercial/SaaS productization is explicitly out of scope (see Future Considerations).



\*\*Stack constraint:\*\* Python backend only. Vector store, LLM provider, and agent orchestration framework are not fixed dependencies of the core product — the reference implementation uses LangGraph, LangFuse, pgvector, and the Anthropic SDK, but the harness and evaluator must not hard-depend on any of these beyond the trace-backbone decision below.



\*\*Mode scope:\*\* Both Live Mode and Offline Mode are in v1 scope. They share the identical blueprint and evaluation engine; Live Mode adds the write-gate/suspend-resume mechanism on top.



\*\*Tool classification (read vs write):\*\* Every tool registered with the harness is tagged `read` or `write` at integration time. Read tools execute freely and are logged unconditionally. Write tools (state-mutating: e.g., `approve\_loan`, `reject\_loan`, `escalate\_to\_human`) are the only tools passed through the live-mode gate. This is a propose→approve→commit pattern, architecturally similar to AWS Step Functions' `waitForTaskToken`, Temporal signals, and BPMN user tasks; closest native analog in the reference stack is LangGraph's `interrupt()`, though the wrapper itself is framework-agnostic (implemented as a Python decorator/context manager around tool functions, not a framework-native hook), satisfying the multi-framework constraint.



\*\*Gating granularity:\*\* Live-mode pauses occur only at the write boundary. Deviations detected on read-tool calls (extra/unexpected reads) do not trigger their own pause; they are logged and escalated into the context presented at the next write-gate review (added to severity/reasoning shown to the reviewer). If a run never reaches a write action, read-tool deviations are still captured in full in the offline trace.



\*\*Pre-flight validation layer:\*\* Implemented as per-tool Pydantic schemas, run before any tool call (read or write) and before deviation evaluation. Validation failures block the call outright (no LLM judge, no HITL) and return a structured rejection to the agent. This is a distinct layer from the Evaluation Engine — it answers "is this well-formed and permitted," not "was this expected."



\*\*Evaluation Engine logic (rule-based first, judge fallback):\*\*

\- Deterministic checks (required action missing, prohibited action taken, threshold condition violated) are evaluated directly against the blueprint YAML. No LLM call.

\- Deviations not covered by an explicit rule are passed to an LLM-as-judge, which assesses necessity/appropriateness against task intent and returns a severity + reasoning, mirroring the existing Claude-as-judge pattern used in prior RAG evaluation work.

\- Before invoking the judge, the evaluator checks the incoming deviation against existing blueprint variants (see below) for a structural match. A match short-circuits the judge call entirely.



\*\*Blueprint schema — variants as first-class citizens:\*\* The blueprint is not a flat action list. Each workflow's blueprint supports multiple valid action-sequence \*\*variants\*\*, each carrying:

\- `status`: `active` (published) or `draft`

\- `polarity`: `approved` or `rejected` (rejected variants are symmetric negative patterns, not just absence of a positive one)

\- `scope`: `one-time`, `reusable`, or `permanent`

\- `provenance`: originating run ID, approving/rejecting reviewer, timestamp

\- `tolerance`: match strictness (exact structural signature by default; broadened only if an admin generalizes it at publish time)



A deviation's structural signature (tool name, triggering predecessor action, condition context) is matched against existing variants before the judge runs:

\- Match against an approved variant → auto-allow at recorded scope, skip judge, skip HITL.

\- Match against a rejected variant → short-circuit to a pre-contextualized HITL prompt (or auto-block without pausing if scope is `permanent`), skip judge.

\- No match → proceed to judge (Evaluation Engine, above).



\*\*Repeat-offense escalation:\*\* A counter is maintained per rejected-variant signature. Exceeding a configurable threshold (default 3) triggers a distinct alert to the workflow owner, separate from the standard HITL flow, framed as a probable upstream agent/prompt issue rather than a runtime policy gap.



\*\*Draft/publish workflow:\*\*

\- Every HITL approve/reject decision immediately writes to a single accumulating \*\*draft\*\* version per workflow (not a new version number per decision) — no separate exceptions table; the blueprint itself is the single source of truth, including its draft state.

\- HITL approval choice includes overwrite (replace an existing variant) vs append (add alongside).

\- The draft is never evaluated against live runs; only the currently `active`/published version is used for evaluation.

\- A business admin reviews the accumulated draft via a dedicated dashboard, can cherry-pick individual variants to include, optionally broaden a variant's tolerance, and publishes — which creates the next numbered active version.



\*\*Live-mode runtime mechanics (async suspend-and-resume):\*\* On a write-gate pause, the run's full resumable state (trace so far, proposed action, deviation context, blueprint version reference) is persisted. The worker process is released, not blocked. A separate resume trigger (webhook/event from the HITL decision channel) reloads this state and continues execution, potentially on a different worker. Modeled on LangGraph's checkpointer/interrupt pattern, but implemented so the persistence/resume contract does not require LangGraph specifically.



\*\*Timeout policy:\*\* Each pending write approval has a configurable timeout window (workflow-level default, overridable per action). If it elapses with no HITL response, the action is automatically rejected and the run is marked `timed\_out` for follow-up. Single-tier, no escalation tier in v1.



\*\*HITL routing:\*\* v1 uses a single, undifferentiated reviewer pool — no severity- or action-type-based routing. (Role-based routing, e.g., routing `manager\_approval` actions to a distinct manager role, is named in Future Considerations.)



\*\*HITL interaction surfaces:\*\*

\- Reviewer-facing: pending write approvals delivered as actionable chat notifications (Slack or equivalent) with approve/reject/append controls, deep-linking to full trace context if needed. This is also the resume trigger for the async suspend-and-resume mechanism.

\- Admin-facing: a dedicated dashboard for blueprint/draft management — comparing variants, cherry-picking at publish time, version history/rollback. This is the only full web UI in v1 scope.



\*\*Trace backbone:\*\* LangFuse is the system of record for raw execution traces (tool calls, arguments, outputs, timings, LLM spans) — not rebuilt from scratch. The harness and Evaluation Engine attach deviation flags and judge scores to LangFuse traces as custom metadata/scores. Blueprint definitions, variant provenance, and HITL decision records live in a separate, purpose-built schema that references LangFuse trace IDs rather than duplicating trace content. Full observability-layer pluggability (swapping LangFuse for another backend) is deferred until a second real adapter exists to justify the abstraction.



\*\*Multi-workflow architecture:\*\* `workflow\_id` is a first-class dimension across the blueprint schema, trace references, variant records, and dashboard — never hardcoded to loan approval. Only the loan-approval workflow is fully implemented and demoed in v1; a second workflow type is not built or validated in this phase, but the schema is not loan-approval-specific.



\*\*PII handling:\*\* A pattern-based redaction utility masks known-sensitive fields (PAN numbers, account numbers, income figures) at the trace-logging boundary, before persistence to LangFuse or the internal schema. This is a scoped, single-control-point mitigation, not a full compliance/encryption/access-control solution.



\*\*Success metrics (tracked from v1):\*\*

1\. False-positive rate on flagged deviations (flagged but reviewer-approved as fine)

2\. Mean HITL response time

3\. Percentage of tool calls blocked at pre-flight validation (cost-savings proxy)

4\. Repeat-offense rate of previously-rejected variant signatures



\---



\## Testing Decisions



\*\*Testing philosophy:\*\* Tests should verify external, observable behavior of each layer (blueprint evaluation outcomes, gating decisions, variant matching results) rather than internal implementation details (e.g., not asserting on internal function call order, only on the resulting deviation/approval state).



\*\*Modules to be tested:\*\*



\- \*\*Pre-flight validation layer\*\*: given a tool schema and a set of valid/invalid argument payloads, assert correct pass/block outcomes and that blocked calls never reach the Evaluation Engine or an LLM call (verified via call-count assertions on mocked judge/tool invocations, not internal code paths).

\- \*\*Evaluation Engine — deterministic rules\*\*: given a fixed blueprint and a set of synthetic traces (skipped required action, prohibited action taken, threshold breached), assert correct flag/no-flag outcomes without any LLM call being made.

\- \*\*Evaluation Engine — judge fallback\*\*: given a deviation not covered by explicit rules, assert the judge is invoked exactly once and its severity/reasoning output is correctly attached to the trace. LLM judge calls are mocked in unit tests; a small set of golden-trace integration tests with a real judge call validate actual reasoning quality.

\- \*\*Variant matching\*\*: given a blueprint with existing approved and rejected variants, assert that matching deviations correctly short-circuit (skip judge, correct auto-allow/auto-block/pre-contextualized-HITL outcome) and non-matching deviations correctly fall through to the judge.

\- \*\*Write-gate / suspend-resume\*\*: given a write-tool call, assert the run correctly suspends (state persisted, worker released) and correctly resumes to the right point given a mocked HITL decision event. Timeout behavior is tested by simulating elapsed time and asserting auto-rejection.

\- \*\*Draft/publish workflow\*\*: given a sequence of HITL approve/reject decisions, assert they accumulate correctly into a single draft, that cherry-picked publish produces the correct new active version, and that the draft never affects evaluation of runs prior to publish.

\- \*\*PII masking\*\*: given synthetic payloads containing known-sensitive field patterns, assert correct redaction before any persistence call is made (verified via inspecting the payload passed to the storage/LangFuse client mock).



\*\*Prior art / reference patterns:\*\* Evaluation Engine and judge-fallback tests follow the same golden-trace + mocked-LLM-judge pattern used in prior RAG evaluation work (Claude-as-judge rubric separating appropriate from inappropriate refusals, FinRAG project). Suspend/resume tests follow the same pattern as testing a LangGraph checkpointer-based interrupt flow — asserting on persisted state and correct resumption rather than on internal graph traversal.



\---



\## Out of Scope



\- Standalone commercial/SaaS productization (positioning as a market-facing product for external buyers) — explicitly deferred to a future phase.

\- Role-based HITL routing (severity- or action-type-based reviewer assignment) — v1 uses a single undifferentiated reviewer pool.

\- Escalation tiers on approval timeout — v1 uses a single configurable auto-reject timeout, no reassignment/escalation mechanism.

\- Semantic/embedding-based variant matching — v1 uses exact structural signature matching with admin-defined tolerance only.

\- Full observability-layer pluggability (swappable trace backbone beyond LangFuse) — deferred until a second real adapter is needed.

\- A second fully implemented and validated workflow type beyond loan approval — the schema is designed to be workflow-agnostic, but this is not proven with a second live example in v1.

\- Full compliance/data-protection layer (encryption at rest, field-level access control, regulatory audit trails beyond basic PII masking).

\- Native framework-specific fast-paths (e.g., using LangGraph's `interrupt()` directly instead of the framework-agnostic wrapper) — may be added later as an optional optimization, not required for v1.

\- Any UI/UX beyond the admin blueprint dashboard and reviewer chat notifications (e.g., no end-user-facing loan-status UI is part of this product).



\---



\## Further Notes



\- The evaluation engine's rule-first, judge-fallback design and the variant/provenance model are the most differentiated and defensible parts of this product; they should be the centerpiece of any prototype or demo, ahead of dashboard polish.

\- The loan-approval blueprint example (from the original concept docs) should be retained as the reference example throughout implementation, both because it maps to real NBFC domain experience and because it naturally exercises every category of blueprint action (required, conditional, threshold-based, approval-gated).

\- Given the "internal proposal + portfolio" framing, implementation should prioritize being explainable line-by-line over breadth of feature coverage — a smaller number of fully-understood, defensible mechanisms is preferred over a larger surface area of shallow features.

\- The negative-variant/rejection-symmetry mechanism (Q9 area of design discussion) is a meaningful design choice worth calling out explicitly in any interview or review of this work, since it directly addresses a gap ("what happens when the same bad pattern recurs after rejection") that a naive approve/reject-only design would miss.

