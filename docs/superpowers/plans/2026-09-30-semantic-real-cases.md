# Real-derived Semantic Regression Implementation Plan

> **For agentic workers:** Execute the focused tasks below in this session; use a fresh GPT-6.1 Sol xhigh reviewer after implementation and measurements.

**Goal:** Add an independent shadow cohort from confirmed PR #11/#12/#17/#18 contracts, then create a draft stacked PR against PR #18.

**Architecture:** Reuse semantic response validation and numeric telemetry. Separate provenance/oracle fixture from a four-field provider payload; use a dedicated evaluator and command so synthetic experiments and real-task accounting cannot mix.

**Tech Stack:** Python standard library, unittest, existing TypeSafe HTTP choice primitive, Codex CLI.

**Spec:** User request dated 2026-09-30: real EA derived semantic fixtures and evaluation (15–20 distinct contracts), stacked on ca2f7da9d65cf68433fd7d791e6dafe16ea3c1f1.

## Global Constraints

- New branch `feat/semantic-regression-real-cases`, PR base `feat/jev-experimental-benchmarks`, draft and unmerged.
- No src, policy, existing fixtures/results, CI or cohort modifications; no Trace/Jevgrep calls.
- New Sol measurements `gpt-6.1-sol` / `xhigh`; no model fallback.
- Oracle and source review verdicts excluded from provider input. Secrets never saved.
- Missing measurements remain null with reasons and denominators. Critical Jev misses remain visible across retries and invalid comparisons.
- Explicit live flag; freeze fixture before live; no mandatory release gate or adoption.

## Review Focus

- Missing/malformed output with valid billed usage: retain usage, never infer quality.
- Duplicate retries with conflicting observations: unique denominator and conservative miss audit.
- Stale provenance/results: reject source mismatch; exclude obsolete measurement identities explicitly.
- Low-confidence/unknown predictions: report abstentions and safety misses separately.
- Absent provider pricing/backend metadata: null cost and explicit limitations.

## Tasks

### 1. Fixed contracts and provenance

- [x] Inspect primary source diffs/reviews/tests for four PRs; reject unsupported contracts.
- [x] Create `tests/fixtures/workflow_semantic_real_cases.json` and provenance manifest with pinned source file hashes and case fingerprints; 15–20 distinct contracts including controls.
- [x] Add failing offline fixture validation tests in `tests/test_workflow_semantic_real.py`.
- [x] Implement loading, provenance verification and payload separation in `tools/workflow_eval/semantic_real.py`; run focused tests.

### 2. Independent measurements and report

- [x] Add failing tests for null usage, retries, stale/model mismatch, miss retention, malformed answers, timeouts and cohort isolation.
- [x] Implement explicit live adapters and summaries using existing semantic schema/telemetry; add `semantic-real` command to existing CLI.
- [x] Commit fixed fixture before live; check credential presence without displaying it; run only this cohort into new exclusive output files.
- [x] Document quality, token, cost, time, coverage, context/rework limits separately in `docs/workflow-semantic-real.md`.

### 3. Verify and publish

- [x] Focused/workflow tests, full run_all, diff check, source/policy/history invariance and checksums.
- [x] Independent GPT-6.1 Sol xhigh review, fix Critical/Important findings and review fixes again.
- [ ] Publish dedicated branch, create/attach draft stacked PR with result and validation limitations; inspect CI and stop without merge/Ready.
