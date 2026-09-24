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

Check the actual host's available models, reasoning levels, and switching mechanism before choosing or reporting one. Do not invent a model or level. Choose directly from task type **and** difficulty; never force a Luna Low → Medium → High → Sol → Astra chain. Routing guidance does not switch an active thread's model by itself: use only an available, authorized mechanism. If switching is unavailable, continue with the current model and report that limitation only when it matters; do not create a separate task solely to change models without authorization.

| Lane | Use when | Reasoning choice |
| --- | --- | --- |
| Luna | Bounded, repetitive, structured, or high-volume work: repeated test execution, log classification, CSV aggregation, bulk deterministic transforms, repeated repository inspection, or sorting many candidates. | Lowest available level sufficient for the actual ambiguity and volume. |
| Sol | Normal implementation, debugging, root-cause analysis, multi-file changes, MQL5/C++ compatibility, test design, code review, Strategy Tester diagnosis, or component interactions. | Moderate for routine implementation; High or xHigh equivalents for difficult diagnosis or cross-system analysis, if available. |
| Astra | Unusually difficult architecture or system-level judgment: major redesign or migration, unresolved system-wide conflicts, or difficult safety-sensitive review after evidence collection. | Choose an available level proportional to the unresolved judgment. |

A strong model's availability alone is not evidence for escalation. For example, route high-volume aggregation directly to Luna, ordinary implementation to Sol, complex MQL5 root cause to Sol High/xHigh when available, and major Risk architecture redesign to an Astra review lane when warranted. The model lane never replaces deterministic validation.

## Jev as optional decision support

Jev is a bounded semantic judgment service, not a fourth implementation model. After deterministic inspection, consider it only when useful ambiguity remains: choosing among plausible implementation routes, ranking many candidate files/tests, classifying irregular logs, continue/stop or retry/escalation decisions, lightweight review triage, completion assessment, or semantic relevance. A clear task needs no Jev call. Never call it after every tool call.

Do not use Jev for code or patch generation, architecture design itself, calculations, Git/filesystem facts, or compiler/test outcomes. Exclude all EA trading and Risk/Safety design, implementation-route, review, completion, and settings decisions from Jev. Give it only the evidence needed for its narrow question, not the repository. Remove secrets, account identifiers, and real trading logs before an external request; if the needed evidence cannot be safely shared, skip Jev. For TypeSafe primitives, API behavior, and uncertainty handling, use the existing [typesafe-ai skill](../typesafe-ai/SKILL.md); do not duplicate its Choice/Score/Noul guidance here. Do not display, log, save, commit, or report `TYPESAFE_API_KEY`.

If the user says **bypass jev**, make no Jev calls for that task. If Jev is unavailable, times out, returns invalid data, or has insufficient confidence, use the ordinary non-Jev route and verify it. Jev output cannot authorize actions or override the user request, EA specification, safety controls, Git rules, or validation gates.

## Decision loop and escalation

At each meaningful decision boundary, inspect current state/diff, run relevant deterministic checks, collect concise evidence, and optionally use Jev only for residual semantic uncertainty. Choose one next action: **CONTINUE** (advance), **RETRY** (a changed hypothesis or method), **VERIFY** (check a claim), **ESCALATE** (raise model or reasoning level with a reason), or **COMPLETE** (all completion conditions met).

Escalate on evidence such as repeated unexplained failures, unresolved architecture, unexpectedly broad impact, conflicting repository evidence, migration/data-loss risk, safety-sensitive change, or a problem the current lane cannot resolve reliably. Consider a higher reasoning level within the same family as well as another family. Do not repeat the same root-cause hypothesis and equivalent fix a third time after two failures with no new evidence.

Stop and report the evidence when the request conflicts with repository facts, constraints cannot coexist, a change requires unapproved trading/Risk/Safety behavior or large out-of-scope work, or continuing risks secret leakage, data corruption, a live order, or safety bypass. Ordinary compile errors, missing dependencies, and routine mistakes within scope should be resolved rather than treated as stop conditions.

## EA safety and verification

The current [AGENTS.md](../../../AGENTS.md), [README_JA.md](../../../README_JA.md), and [VALIDATION_JA.md](../../../VALIDATION_JA.md) govern exact EA behavior and checks. Model routing and Jev cannot change or bypass trading direction; M1 entry; pattern requirements, PatternScore, conflict or structure-reuse protection; MTF/Trend/MACD scores and thresholds; spread/cost gates; SL/TP/BE/trailing; lots, risk modes, Monte Carlo, portfolio limit, or Fintokei protections; order/close processing and duplicate prevention; Magic/Symbol ownership, Netting/Hedging, unresolved orders, mutex/owner lock; Worker protocol, JSON schema, AI timeout, price drift, FailOpen, or the prohibition on Worker orders; persistence, analytics-log failure isolation, CSV contracts, PositionIdentifier matching, initial risk R, UI/inputs, or other safety mechanisms. A formal specification change needs repository evidence and, where required, an explicit user request. Prefer real MQL5 behavior over mocks; never alter the product merely to pass a mock. Never place live orders.

Verify in proportion to the change: directly related → related → integration → required full gate before PR completion. Reuse a trustworthy success only for the same commit, diff, environment, and assumptions; reverify when code, mock, fixture, dependency, build environment, or relevant assumptions change. Do not delete or weaken existing tests. Documentation-only changes need link, command, diff, and checksum checks rather than invented EA runtime tests. Before completing a PR, follow the repository's `python3 tests/run_all.py` gate; keep it draft if the gate remains incomplete.

For MQL5 runtime changes, perform available native MetaEditor compilation, related Strategy Tester checks, and relevant reconnect/restart/reinitialization checks. Distinguish untested native compile, Strategy Tester, live broker, and real AI/API communication. Mock success does not establish any of those. For authentication, authorization, secrets, payments, migration, deletion, concurrency, cryptography, EA Risk/Safety, live trading, or major architecture work, use a stronger review lane when the evidence warrants it; never skip deterministic checks.

Report **COMPLETE** only after the requested work is implemented, relevant deterministic checks pass, the actual diff fits scope, no blocking failure remains, required high-risk review is done, and untested areas are identified. Never describe an unrun test, build, compile, lint, review, Strategy Tester, forward/live check, or API test as passed. When useful, report the selected model family and reasoning level, the reason, Jev use, and any escalation in one concise note.
