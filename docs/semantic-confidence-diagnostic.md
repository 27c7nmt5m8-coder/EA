# PR19 frozen-input confidence diagnosis

This independent shadow diagnostic is stacked on PR19 head
`766343e1f52411c8bb49a6d7fcfd0e65a64e343a` (`feat/semantic-regression-real-cases`).
It neither reruns the official 19-case cohort nor modifies its results/oracles.

## Frozen protocol (before live calls)

- Fixture SHA-256: `0cf1b672be68ab83188cbed89b2e33ebce1e0ed8ee118e4bf39c70388844a2e0`.
- Provenance SHA-256: `350c0a075bcd7f747e6c6980cecbe6501f2a4c85134e624c6b6cdfce918b61a5`.
- Targets: ER003 / ER013, **2 unique cases, 3 historical anomaly observations**.
- Jev: 5 identical-input repeats each for targets and 4 controls (30 planned).
- Sol: 3 identical-input repeats each for both targets (6 planned),
  `gpt-6.1-sol` / `high`, no model fallback.
- Controls: first all remaining same-label `no_regression` controls with original
  Jev confidence >=0.90 (ER007, ER016); then lowest-ID high-confidence Important
  cases from the missing PR11/17 sources (ER001, ER010). All four are Important;
  labels match only 2/4. There is no matched high-confidence Critical
  no-regression control. This is an exploratory reference, not a balanced cohort.
- Blind review: fresh isolated ephemeral Codex executions, one per target;
  only the four original provider fields, no ID/oracle/severity/history/confidence,
  no repository or tools. Category plus short public explanation only.
- No paraphrases. Original adapters, instructions, criteria, payloads and request
  model remain unchanged. Canonical payload/request digests are frozen on disk
  before the first call. Sol CLI identity is evidenced by requested flags; actual
  backend identity is not exposed by its events.
- Variability diagnostic bounds fixed before execution: any within-case choice
  change, confidence range >=0.20, or population standard deviation >=0.10
  blocks the experiment. These conservative exploratory bounds do not tune the
  confidence threshold or grant approval.

## Accounting and interpretation

Every attempt has a unique ID; duplicate IDs or slots are rejected. A same-model
Sol runtime retry is separately billed but occupies the same case/repeat slot.
At most one retry follows a timeout/nonzero exit. First valid attempt per slot
determines repeat statistics; all attempts contribute known billing and time.
Jev outage stops; no fake calls or implicit fallback. Unknown remains unknown.
Missing usage/probabilities/time/cost stays null with reason and coverage; partial
subtotals are labeled, never represented as complete totals. Aggregate choice
stability is weighted **within-case** stability, because controls have different
expected labels. Group confidence variance is pooled across cases and must not
be mistaken for within-input variability.

TypeSafe confidence is a statistic of the distribution, not the probability of
the chosen label. We preserve its reported confidence without inventing an
undocumented formula. Probability margin is largest minus second-largest
probability, reported separately. Sol self-reported confidence is not a
calibrated probability or directly comparable to TypeSafe confidence.
[TypeSafe confidence documentation](https://docs.typesafe.ai/confidence).

The original Sol protocol returns no explanation. Historical unknown reasons
cannot be recovered retrospectively. Blind explanations diagnose possible input
ambiguity; they are not the original model's private reasoning. Source audit
checks the complete primary contract separately from summary completeness.
If the oracle is unsupported, report `GROUND_TRUTH_ISSUE_FOUND`, stop and never
rewrite the fixture. Low confidence always requires Sol High; no PASS/approval.
Only the requested shadow verdicts are allowed. Repeatability alone yields
UNMEASURED until separate blind/source audits are assessed; observed instability
is BLOCKED even when other coverage is missing.

## Usage and boundaries

```sh
python -m unittest tests.test_workflow_semantic_diagnostics
python -m tools.workflow_eval.semantic_diagnostics --live
python -m tools.workflow_eval.semantic_diagnostics --report semantic-confidence-TIMESTAMP
python -m tools.workflow_eval.semantic_diagnostics --report semantic-confidence-TIMESTAMP --source-audit PATH_TO_INDEPENDENT_AUDIT_JSON
```

Outputs use new exclusive `.workflow-eval/semantic-confidence-*` files. Provider
transcripts, raw trace, prompt text and credentials are never saved. Blind public
explanations are explicitly requested and checked before saving. No outputs are
written to the 30/50 real-task cohort or official PR18/19 records. The runner is
standalone so the official evaluators/CLI remain unchanged.

The audit JSON is an explicit independent assessment mapping only ER003/ER013
to PRIMARY_EVIDENCE_SUPPORTED or GROUND_TRUTH_ISSUE_FOUND. It is not an automatic
oracle verifier. Without completed blind and source audits, repetition alone
remains UNMEASURED. Orphan/unplanned retries are rejected; malformed or
model-mismatched attempts block even if subsequent data is valid. Blind metadata
uses canonical missing-usage reasons; malformed stream events do not erase a
single completed, validated usage event. Runtime failures remain unavailable.

EA/src, trading, safety, policy and AGENTS remain unchanged. Threshold 0.90,
review_skip_enabled=false and mandatory Sol High routing remain in force.
This is not EA quality assurance, a release gate, review skip or permanent Jev
adoption. No Trace/Jevgrep calls. Rollback: close this Draft stacked PR/remove its
diagnostic files; ignored local diagnostic records may be archived separately.
