---
name: model-orchestrator
description: Use when non-trivial software-engineering work would benefit from choosing among available model families or reasoning levels, escalating after evidence, or resolving a bounded semantic decision with TypeSafeAI/Jev.
---

# Model Orchestrator

## Purpose and scope

Route Codex development work to the lowest sufficient available model and reasoning level while preserving capability, correctness, EA safety, repository rules, and verification quality. Never save tokens by omitting evidence needed for a correct decision. This skill governs the development workflow only; it does not add model routing or Jev to the EA or Worker runtime. Follow [AGENTS.md](../../../AGENTS.md) and the current user request first.

## Evidence first

At the start of a task, inspect in this order: (1) the request, (2) relevant Git state and diff, (3) directly related files and functions, (4) relevant validation, then (5) dependencies and history when the evidence requires them. Expand the scope when needed; do not omit a necessary full-file check. Do not automatically reread the entire repository, all docs, all skills, or all history, or repeatedly run the full test suite during intermediate edits.

Prefer deterministic tools over model judgment: Git for repository state and changed code; filesystem inspection for existence; compiler, type checker, linter, formatter, and test runner for their respective results; code for numerical calculations. Do not ask Jev to rejudge a directly testable fact or a compiler/test result.

## Direct model routing

Check the actual host's available models, reasoning levels, and switching mechanism before choosing or reporting one. Do not invent a model or level. Choose directly from task type, complexity, risk, and evidence; never force a Luna Low → Medium → High → Sol → Astra chain. Routing guidance does not switch an active thread's model by itself: use only an available, authorized mechanism. If switching is unavailable, continue with the current model and report that limitation only when it matters; do not create a separate task solely to change models without authorization.

| Lane | Use when | Reasoning choice |
| --- | --- | --- |
| Luna | Bounded, repetitive, structured, or high-volume work: repeated test execution, log classification, CSV aggregation, bulk deterministic transforms, repeated repository inspection, or sorting many candidates. | Lowest available level sufficient for the actual ambiguity and volume. |
| GPT-6.1 Sol (`gpt-6.1-sol`) | Implementation, debugging, root-cause analysis, multi-file changes, MQL5/C++ compatibility, test design, review, Strategy Tester diagnosis, or component interactions. | Medium for routine implementation; High is the standard for complex implementation, important review, mandatory review, and independent review. xHigh is evidence-based escalation and second-pass verification only. |
| GPT-6 Astra | Exceptionally difficult architecture, system-wide redesign, or high-impact independent review only after GPT-6.1 Sol has demonstrated insufficient capability on collected evidence. | Choose an available level proportional to the unresolved judgment; no automatic Astra routing. |

Higher reasoning effort is not assumed to be always better. Route high-volume aggregation to Luna, routine implementation to GPT-6.1 Sol Medium, and complex diagnosis, architecture-sensitive work, mandatory review and independent review to GPT-6.1 Sol High. A stronger model's availability alone is not evidence for escalation. The model lane never replaces deterministic validation.

### Project roles and configuration

The project's [.codex/config.toml](../../../.codex/config.toml) sets GPT-6.1 Sol High for root/orchestrator/integrate/verify and unspecified subagents. Choose a worker's model and effort explicitly: Sol Medium for routine implementation, High for complex multi-module, protected, concurrent, architectural or orchestration work. Explorer/researcher use Luna High for bounded read-only scans and research, or Sol Medium for deep protected dependency analysis and complex specification comparisons. Reviewers use independent Sol High contexts and remain read-only. Reuse suitable existing agents; delegate only for concrete parallelism, specialization or independence benefits. Explicit supported spawn selections override defaults. `fork_turns` controls context propagation, not model choice; a full-history fork inherits its parent's settings. These defaults do not silently reconfigure an already running chat or CLI adapters that explicitly select a model in an isolated directory.

For delegated work, prefer a task-specific content-addressed context packet over a full-history fork when correctness does not require the full history. The packet should carry the task, actual diff, full changed/protected content needed for the decision, relevant specification constraints, deterministic verification digest, and unresolved questions. Exact SHA handles may replace only unchanged related context whose content hash matches prior evidence; protected work, unknown dependencies, stale evidence, or unresolved expansion disables reuse. A reviewer or worker must expand any handle needed to resolve uncertainty. Packet compression changes transport only: it never lowers the model/effort floor, narrows dependency investigation, skips review, or substitutes for deterministic validation.

Astra requires demonstrated Sol insufficiency plus advance explicit user approval after explaining the limitation, review scope and increased cost. It is never an automatic route or fallback. An offline fixture that includes Astra must include this approval as an intended precondition, not claim a live execution occurred.

### Minimum routing floor

Set a capability floor before optimizing speed or cost. Treat authentication, authorization, secrets/credentials, destructive operations or deletion, migrations, concurrency, cryptography, payments, security boundaries, and production-critical architecture as high-risk. In this EA, also treat live trading, order execution/ownership/duplicate prevention, Magic/Symbol ownership, SL/TP/BE/trailing, lot sizing, risk percentage/modes/Monte Carlo/portfolio/Fintokei, spread/cost safety, FailOpen, Worker protocol, price drift, unresolved orders, and other safety mechanisms as high-risk.

High-risk/protected/critical/EA/financial/order/safety work and unknown dependencies require review, prohibit review skip and Jev final approval, and require deterministic verification. Standard mandatory and independent reviews use GPT-6.1 Sol High. High-risk alone does not automatically imply xHigh or Astra. Increase verification depth first; bounded deterministic bulk subtasks may use Luna with checked results. Do not downgrade an active task when its accumulated context or unresolved risk would be lost.

New active Sol execution uses only `gpt-6.1-sol`. Old `gpt-6-sol` / `gpt-5.6-sol` identifiers may remain only for historical records, migration tests, past prices, or provenance. Historical parsing cannot become an execution fallback. If GPT-6.1 Sol or a required reasoning level is unavailable, stop that execution and report the limitation; never silently substitute another model or downgrade a required floor.

The workflow policy retains `review_skip_enabled=false` and `confidence_threshold=0.90`. Mandatory reasons mean review cannot be omitted; they do not impose xHigh. Explicit stricter project rules retain authority, except where the current user explicitly authorizes their migration.

## Jev as optional decision support

Jev is a bounded semantic judgment service, not a fourth implementation model. After deterministic inspection, consider it only when useful ambiguity remains: choosing among plausible implementation routes, ranking many candidate files/tests, classifying irregular logs, continue/stop or retry/escalation decisions, lightweight review triage, completion assessment, or semantic relevance. A clear task needs no Jev call. Never call it after every tool call.

Do not use Jev for code or patch generation, architecture design itself, calculations, Git/filesystem facts, deterministic parsing, or compiler/test/Strategy Tester outcomes. Exclude all EA trading and Risk/Safety design, implementation-route, review, completion, and settings decisions from Jev. Clear routing cases need no Jev call.

Before an external Jev request, make a minimal redacted summary. Prefer only structured fields such as `task_type`, `risk_level`, `candidate_count`, `test_state`, `failure_type`, `changed_area`, and `uncertainty_reason`. Do not send the full repository, unrelated files, chat history, credentials, account information, real trading logs, or unnecessary source code. Screen the intended payload for secret-like content; remove it or skip Jev when safe minimization is uncertain. Never put `TYPESAFE_API_KEY` in a prompt, stdout, log, report, fixture, or commit. For TypeSafe primitives, API behavior, and uncertainty handling, use the existing [typesafe-ai skill](../typesafe-ai/SKILL.md); do not duplicate its Choice/Score/Noul guidance here.

If the user says **bypass jev**, make no Jev calls for that task. On API/runtime unavailability, timeout, authentication or quota/rate failure, malformed/invalid response, low confidence, or ambiguous result, treat Jev as having no opinion and continue with the deterministic/default route. Do not call that a successful Jev judgment or stop ordinary Codex work. This fail-open behavior applies only to development routing; it never relaxes the EA's separate FailOpen or safety gates. Jev output cannot authorize actions or override the user request, EA specification, safety controls, Git rules, or validation gates.

### Shadow routing

Choose the **default route** independently first. When routing evaluation is useful and a safe, bounded Jev question remains, a **shadow route** may record what Jev would recommend, with confidence and a short reason. The **actual route** stays the default route; a shadow recommendation cannot switch the model, lower the risk floor, or change the task. Do not run shadow calls for every clear task. Keep evaluation records only when needed, with route family/level, result status, confidence, and outcome; omit prompts, raw logs, source, and secrets. Consider automatic routing only after representative measurements show preserved safety, task quality, verification, latency, and cost, and an authorized switching mechanism exists.

## Decision loop and escalation

At each meaningful decision boundary, inspect current state/diff, run relevant deterministic checks, collect concise evidence, and optionally use Jev only for residual semantic uncertainty. Choose one next action: **CONTINUE** (advance), **RETRY** (a changed hypothesis or method), **VERIFY** (check a claim), **ESCALATE** (raise model or reasoning level with a reason), or **COMPLETE** (all completion conditions met).

Use xHigh only as an additional independent check when concrete evidence remains: material uncertainty after Sol High review; significant disagreement between independent High reviews; root cause unresolved after appropriate investigation; unexplained deterministic-check behavior; or an explicit project rule requiring xHigh. Give the new reviewer the specification, actual diff, repository evidence, test results, and unresolved questions; require an independent assessment rather than confirmation of the previous review. Record the reason and evidence. Protected/critical/EA/financial status, mandatory review, stronger effort availability, or precaution alone cannot trigger escalation. Prefer deterministic validation plus High review first; do not use a fixed escalation chain. Astra is reserved for cases Sol demonstrably cannot resolve reliably. Do not repeat the same root-cause hypothesis and equivalent fix a third time after two failures with no new evidence.

Stop and report the evidence when the request conflicts with repository facts, constraints cannot coexist, a change requires unapproved trading/Risk/Safety behavior or large out-of-scope work, or continuing risks secret leakage, data corruption, a live order, or safety bypass. Ordinary compile errors, missing dependencies, and routine mistakes within scope should be resolved rather than treated as stop conditions.

## EA safety and verification

The current [AGENTS.md](../../../AGENTS.md), [README_JA.md](../../../README_JA.md), and [VALIDATION_JA.md](../../../VALIDATION_JA.md) govern exact EA behavior and checks. Model routing and Jev cannot change or bypass trading direction; M1 entry; pattern requirements, PatternScore, conflict or structure-reuse protection; MTF/Trend/MACD scores and thresholds; spread/cost gates; SL/TP/BE/trailing; lots, risk modes, Monte Carlo, portfolio limit, or Fintokei protections; order/close processing and duplicate prevention; Magic/Symbol ownership, Netting/Hedging, unresolved orders, mutex/owner lock; Worker protocol, JSON schema, AI timeout, price drift, FailOpen, or the prohibition on Worker orders; persistence, analytics-log failure isolation, CSV contracts, PositionIdentifier matching, initial risk R, UI/inputs, or other safety mechanisms. A formal specification change needs repository evidence and, where required, an explicit user request. Prefer real MQL5 behavior over mocks; never alter the product merely to pass a mock. Never place live orders.

Verify in proportion to the change: directly related → related → integration → required full gate before PR completion. Reuse a trustworthy success only for the same commit, diff, environment, and assumptions; reverify when code, mock, fixture, dependency, build environment, or relevant assumptions change. Do not delete or weaken existing tests. Documentation-only changes need link, command, diff, and checksum checks rather than invented EA runtime tests. Before completing a PR, follow the repository's `python3 tests/run_all.py` gate; keep it draft if the gate remains incomplete.

Keep short tool output intact. Preserve FAIL/WARNING/UNKNOWN and abnormal output; compress only long, clear success output with deterministic methods when the summary is shorter and the original remains available. Do not introduce Jev-based compaction for this workflow.

For MQL5 runtime changes, perform available native MetaEditor compilation, related Strategy Tester checks, and relevant reconnect/restart/reinitialization checks. Distinguish untested native compile, Strategy Tester, live broker, and real AI/API communication. Mock success does not establish any of those. For authentication, authorization, secrets, payments, migration, deletion, concurrency, cryptography, EA Risk/Safety, live trading, or major architecture work, deepen deterministic verification and perform Sol High review first, with independent High review when required. Add xHigh only for the concrete escalation evidence above; never skip deterministic checks.

Report **COMPLETE** only after the requested work is implemented, relevant deterministic checks pass, the actual diff fits scope, no blocking failure remains, required high-risk review is done, and untested areas are identified. Never describe an unrun test, build, compile, lint, review, Strategy Tester, forward/live check, or API test as passed. When useful, report the selected model family and reasoning level, the reason, Jev use, and any escalation in one concise note.

For a small offline routing check from the repository root, compare [fixture expectations](fixtures/routing_cases.json) with [dry-run observations](fixtures/routing_dry_run.json) using `python .agents/skills/model-orchestrator/scripts/evaluate_routing.py`. Their evidence fields describe intended inspection order, not tests actually run. These examples do not call Jev or prove live routing quality; use representative, privacy-safe observations before considering any automatic routing.
