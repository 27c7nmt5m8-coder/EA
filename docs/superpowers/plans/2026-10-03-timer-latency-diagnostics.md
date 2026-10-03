# OnTimer latency diagnostic implementation plan

> Execute inline using executing-plans; independent xhigh review for complex event timing. Autopilot explicitly authorizes continued Tester-only investigation without a new approval exchange.

**Goal:** Attribute long OnTimer callbacks using timestamped stage evidence, preserving product source, original inputs and all trading decisions.

**Architecture:** Layer a small diagnostic header and fail-closed source transforms over the frozen multi-symbol generator. Store the largest 256 callbacks in preallocated storage, with complete population counts/sums/maxima, and export only on OnTester. Partition OnTimer into maintain, universe, scan, actual MC, shadow MC, dispatch, journal and dashboard stages. Measure diagnostic record-storage overhead separately.

**Constraints:** Base exact validated commit 0e3903c077c44aad80c6273d945cb2e3fa266f58. Current main checked 4cd1ced. Reuse isolated worktree with child branch. No product/set/MC formula/Risk/Safety/chunk/force-dedup changes. No unowned process or Windows security changes. No credentials/account values in artifacts. Queue arrival remains UNKNOWN.

**Review focus:** Observer overhead can change wall-clock budget iteration; require frozen funnel/tick/bar/numeric comparison. Top-256 timings are censored and cannot supply population percentiles. Per-Symbol Scan is nested in scan stage and must not be summed twice. TimeCurrent is last-quote server time, not event arrival. End-of-run export/sorting is not OnTimer.

## Task 1 — Observational generator and strict analysis

- [x] Add failing tests for reversible main-only transforms, unchanged other generated files/MC core, fail-closed unsupported mode/destination, and invalid timing partitions.
- [x] Run tests and observe missing functionality failure.
- [x] Add tools/build_tester_timer_latency.py and TesterTimerLatencyDiag.mqh. Add strict analyze_timer_trace(rows, summaries), requiring complete timer/stage groups and finite nonnegative integer timing fields.
- [x] Re-run focused and full Python tests. Compile native Tester copy; require 0 errors / 0 warnings and fresh EX5.

## Task 2 — Minimal native evidence

- [x] Read-only verify terminal engine hashes, empty terminal/tester process inventory, safe existing Tester profile and original input hashes.
- [x] Reuse N3/M2/CPU_CONTENTION, 2026-09-14–09-19, unchanged real ticks/high diagnostic inputs. New owned diagnostic destination only.
- [x] Launch existing unattended owned-process runner. Collect fresh allowlisted exports and compare exact funnel/tick/bar/trades/numeric evidence with prior same-condition record.
- [x] Attribute maximum callback to measured code stage; if needed add only the next nested section probe. Never infer the historical 363.961ms call ID from a different run.

## Task 3 — Validation and report

- [ ] Independent review, diagnostic regression, syntax/scope/privacy/hash verification. If committing diagnostics, regenerate distribution checksum and obtain exact-head CI again; previous CI applies only to frozen parent.
- [ ] Keep prior authoritative gate proof intact. Record new source hashes, actual run evidence, observer limitations and remaining UNKNOWNs separately.
- [ ] Continue Autopilot only if next action is safe; product-timing/decision changes remain a human gate.

## Actual continuation evidence

Coarse CPU attribution was INVALID/PARTIAL (empty symbol rows). Two nested CPU starts were BLOCKED by affinity drift; no security/affinity relaxation or further CPU retries. Three successive same-condition N3/M2/NORMAL probes completed and matched ticks/bars/funnels/trades. IO-layer retained Journal maximum attributes 230170us to two FileMove intervals; separate startup Scan is this run's maximum body. Historical 363961us is a different unpartitioned event and remains unresolved. Product synchronous I/O changes are not part of this plan.

Focused 22 and frozen-native 3 regressions pass; full unittest 62 PASS. Independent review and fresh MetaEditor mode0/mode2 0/0 obtained. Exact-child commit/CI validation remains pending until the diagnostic evidence is fixed.
