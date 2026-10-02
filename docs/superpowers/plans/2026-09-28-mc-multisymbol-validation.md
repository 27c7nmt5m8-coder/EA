# Multi-symbol MC scheduler stress validation implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compare Current20k and fixed500k under 2/3/4-symbol Tester workloads and real CPU contention, preserving product decisions and recording event impact without claiming unavailable queue measurements.

**Architecture:** Start from canonical `9f9c553` on `codex/mc-multisymbol-validation`, port the prior Tester-only diagnostic generator, then add symbol-qualified actual-event diagnostics and independent shadow MC workload to the generated Tester copy. A same-process/event-loop shadow job is distinct from a naturally heavy product MC cycle. Use one real-tick USDJPY Sep14 High period and original High set copied for Tester symbol selection; do not treat XAU performance as its own preset result.

**Tech Stack:** MQL5/MetaEditor/MT5 Tester, Python stdlib, existing CI 5-gate and exact-HEAD Windows CI delegation. No new dependency/Jev.

**Global constraints:** Never modify product `src/`, original `.set`, MC formula/RNG/samples/minwin/DD/Risk/Safety/trading/force dedup; no 1m/adaptive/time budget change; no product adoption, PR, push, merge, security weakening, real orders. Shadow result must never enter product `g_symbols`, history, `g_mcReady`, risk, entry/order paths or persistence. Fail closed on changed source anchors, unknown records, overflow, missing symbols/history or identity drift. Do not claim shadow as natural history-driven heavy MC. Live queue depth and broker latency are UNKNOWN.

**Evidence baseline:** Canonical HEAD `9f9c553` was checked against GitHub main and exact-HEAD run 36324111714; local `run_all.py --ci-run 36324111714 --metaeditor ... --mql-include ...` reports full/release PASS, local native 1/2 BLOCKED with Windows CI PASS, static 3/4/5 PASS, native MetaEditor PASS. Prior `1200695` diagnostics are not authoritative for changed product source. Native multicurrency supported by official MT5 Tester docs; NewTick and Timer can coalesce. Old generator's `ReadIndicator` anchor must be ported to new source.

**Interfaces / planned files:**
- `tools/build_tester_mc_multisymbol.py`, `tools/TesterMCMultiDiag.mqh`, `tools/TesterMCMultiMethods.mqh`: generated Tester-only four-symbol harness, exact source hash/anchor checks, structured bounded exports.
- Reused prior diagnostic generator chain under `tools/` and `tests/`: port only current-source anchor differences, preserving prior measurement definitions; copy from existing local diagnostic worktree as source, no old result claims.
- `tools/mc_multisymbol_runner.py`, `tools/analyze_mc_multisymbol.py`: frozen case manifest, launch/recovery, strict schema, same-mode comparison, fairness/tail/causal classification; separate NORMAL and CPU_CONTENTION.
- `tests/test_mc_multisymbol*.py`: red/green generator contracts, cycle namespace/collision, unmodified product data flow, metric parser/unknown, ownership/affinity and privacy.
- `verification/mc_multisymbol_20260928/` and Japanese report: case evidence, totals, exclusions, limits; omit native account/log text.

## Task 1: canonical diagnostic port

- [ ] Copy only required prior Tester diagnostic source/test files to the new isolated branch, preserving prior worktree untouched.
- [ ] Write failing port regression: current `ReadIndicator` uses `CopyBuffer` followed by `BarsCalculated` and generated Tester code must preserve this exact order; wrong source anchor fails closed.
- [ ] Port generator exact replacements to canonical `9f9c553` without product edits; run direct Python regression and compile Current/500k with MetaEditor 0/0.
- [ ] Verify diff in `src/` and original set hashes remains empty/unchanged.

## Task 2: symbol-qualified actual and independent shadow instrumentation

- [ ] Add failing tests for `(symbol, kind, cycle)` identity, simultaneous shadow-active overlap, bounded overflow fail-closed, exact operation count, zero product state write and natural/shadow separation.
- [ ] In generated Tester-only code, instrument actual OnTimer/OnTick/ManagePositions/order and per-symbol MC starts/completions, preserving call order. Add independent per-symbol shadow MC using identical source-derived computation with deterministic copied/synthetic return input and own state; arm same server epoch, service round-robin within the same EA event loop. Qualify all exports by symbol and kind.
- [ ] Record source-linked callback ID, server timestamp, wall microseconds, operations, history/input version, candidate/order IDs, quote timestamp, per-symbol sampled ticks/bars, service gaps, and instrumented native order/position milestones; mark enqueue/queue depth and live broker latency UNKNOWN.
- [ ] Compile both modes 0/0 and run diagnostic selftest/numerical replay (bit comparisons, zero tolerance).

## Task 3: frozen workload and 2/3/4 × Current/500k × NORMAL/CPU_CONTENTION

- [ ] Add failing runner/analyzer tests for case binding, invalid set/source/binary hash, missing natural/shadow distinction, queue unknown, incomplete pair, privacy, wrong process affinity, and report/funnel parity.
- [ ] Freeze unchanged original High preset checksum; create Tester-only selection copies for 2FX, 3FX and 4 incl XAU. Keep every trading/Risk/Safety input unchanged; disclose 4-symbol XAU uses shared FX High test settings, not XAU canonical preset. Preload needed history and assert exact symbol names/quality before accepting a case.
- [ ] Run 12 native real-tick cases sequentially in isolated Tester profile: 2/3/4 symbols, two modes, two loads. CPU contention uses verified pinned terminal/tester descendants plus owned busy worker on same core, not Sleep. Keep original normal and stress attempt evidence but count only strict PASS.
- [ ] Require at least two simultaneous active shadow jobs in one process/event loop with nonzero operations per symbol. Report natural heavy counts independently; if none, do not claim natural-heavy validation.

## Task 4: analysis and final validation

- [ ] Compare per-symbol completed/start/cancel/restart, callback/operation shares, market and wall duration median/p90/p95/p99/max, wait/expiry/ready, Opportunity funnel, force/heavy duplicate, tick/bar/input integrity, Position and order milestones; explain unexpected differences by IDs and timeline or mark UNKNOWN.
- [ ] Apply no arbitrary latency cutoff; event loss/significant delay => REJECT. Missing natural-heavy/queue evidence => NEEDS_MORE_TESTING. Only mark READY if user criteria fully evidenced.
- [ ] Run diagnostic regression, MetaEditor 0/0, numerical/static and canonical full5. Distinguish exact-HEAD CI evidence for tracked canonical source from uncommitted diagnostic code; never reuse prior SHA/results as fresh verification.
- [ ] Scan new curated/native outputs and filenames for known account/secret in RAM; preserve raw Tester logs privately; verify product `src/`, original set, Risk/Safety and security setting scope. Write concise Japanese report and one next action, no adoption/PR/push/merge.

**Review focus:** original `ReadIndicator` semantics; shadow cannot affect product decision data; symbol-qualified cycle collision; native agent ownership/CPU attribution; XAU global-setting and missing-natural-heavy limits.
