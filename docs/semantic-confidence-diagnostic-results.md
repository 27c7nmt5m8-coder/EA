# Frozen-input diagnostic live results (2026-10-01 JST)

## Identity and scope

Dependency: PR19 head `766343e1f52411c8bb49a6d7fcfd0e65a64e343a`.
Execution commit: `bb3227d` (protocol committed before live).
Local safe metadata prefix: `semantic-confidence-20260930T211752113111`.
Provider: TypeSafe, returned Jev model `jev-1.13.0`. Sol requested
`gpt-6.1-sol/xhigh` for all primary/blind calls. Backend identity is not exposed.

Frozen fixture SHA-256:
`0cf1b672be68ab83188cbed89b2e33ebce1e0ed8ee118e4bf39c70388844a2e0`.
Frozen provenance SHA-256:
`350c0a075bcd7f747e6c6980cecbe6501f2a4c85134e624c6b6cdfce918b61a5`.
2 unique targets, 3 historical anomaly observations, 4 controls, not 38 cases.
The [precommitted selection/protocol](semantic-confidence-diagnostic.md) was
frozen before calls. No paraphrases, oracle edits or post-hoc input tuning.

## Quality and repeatability

All 30 Jev calls and 6 primary Sol calls returned valid responses; 0 malformed,
0 unavailable, 0 retries, 0 binary oracle mismatches. This is observed diagnostic
agreement, not a new official 19-case score. ER003's unknown is not a binary
success or a measured false negative. No Critical/Important binary miss was
observed in these selected cases; this small selected subset is not general
critical-miss coverage.

| Case/group | Jev repeats/choice | Confidence min–max | Mean | Population SD | Mean probability margin | <0.90 |
|---|---|---|---:|---:|---:|---:|
| ER003 target | 5/5 no_regression | 0.51–0.61 | 0.564 | 0.036661 | 0.476 | 5/5 |
| ER013 target | 5/5 no_regression | 0.69–0.76 | 0.726 | 0.025768 | 0.640 | 5/5 |
| ER007 control | 5/5 no_regression | 0.86–0.94 | 0.902 | 0.028566 | 0.872 | 2/5 |
| ER016 control | 5/5 no_regression | 1.00–1.00 | 1.000 | 0 | 1.000 | 0/5 |
| ER001 control | 5/5 regression | 1.00–1.00 | 1.000 | 0 | 1.000 | 0/5 |
| ER010 control | 5/5 regression | 1.00–1.00 | 1.000 | 0 | 1.000 | 0/5 |
| Targets pooled | 10 valid | 0.51–0.76 | 0.645 | 0.086977 | 0.558 | 10/10 |
| Controls pooled | 20 valid | 0.86–1.00 | 0.9755 | 0.044774 | 0.968 | 2/20 |

Jev vectors, in repeat order: ER003 `[.61,.55,.60,.51,.55]`,
ER013 `[.71,.72,.75,.76,.69]`, ER007 `[.92,.91,.88,.94,.86]`,
ER016/ER001/ER010 each `[1,1,1,1,1]`.
Target-minus-control confidence mean = -0.3305; pooled SD difference =
0.042203. Mean **within-case** SD difference = 0.024073 (0.031214 versus
0.007141). Within-case choice stability = 1.0 in both groups, difference 0.
Pooled confidence variance mixes case differences; it is not input instability.
ER007 was historically high confidence but now crosses the unchanged threshold
twice; control selection remains fixed.

| Sol case | Distribution | Unknown | Stable binary count | Confidence min–max / mean / SD | Mean margin |
|---|---|---:|---:|---|---:|
| ER003 | unknown 3/3 | 3 | 0 | .88–.90 / .886667 / .009428 | .806667 |
| ER013 | no_regression 3/3 | 0 | 3 | .97–.98 / .976667 / .004714 | .963333 |
| Targets pooled | unknown 3, no_regression 3 | 3 | 3 | .88–.98 / .931667 / .045613 | .885 |

Sol within-case stability is 1.0. ER003 repeats the historical unknown; this is
semantic uncertainty with successful runtime, not a provider failure. No Sol
controls were planned: their choice/usage metrics are null (not measured).

## Blind ambiguity review

Two separate fresh ephemeral `gpt-6.1-sol/xhigh` executions received only the
four original provider fields, no fixture ID, expected result, severity,
historical output/confidence, repository or tools. Both were valid, without retry.

| Target | Category | Public explanation |
|---|---|---|
| ER003 | materially_ambiguous | ON/OFF equality supports preservation; live silence does not establish execution only in Tester AUTO. Outside-mode execution remains unspecified. |
| ER013 | materially_ambiguous | Identity across heads/retries/arms is stable; fixture exclusion is unaddressed, preventing unique classification of the full contract. |

These are diagnostic explanations, not the unrecorded reasons for the original
Sol unknown. The primary repeat protocol was unchanged and requested no reasons.

## Independent source/provenance audit

Separate GPT-6.1 Sol xHigh read-only audit: **PRIMARY_EVIDENCE_SUPPORTED** for
both oracles, partial coverage of the **complete contract in the provider
summary**. No `GROUND_TRUTH_ISSUE_FOUND`. Actual pinned source objects,
hashes/fingerprints/anchors verified, no fallback manifest-only check.

- ER003: [original parity/live test](https://github.com/27c7nmt5m8-coder/EA/blob/56f4805e57c48cc611a87174ea2abecc5950a044/tests/entry_diagnostic_scenarios.cpp#L55),
  [Tester AUTO guard](https://github.com/27c7nmt5m8-coder/EA/blob/56f4805e57c48cc611a87174ea2abecc5950a044/src/MT3SymbolState.mqh#L174).
  Reverse projection of 20 observational hunks across 3 headers matched the
  original base bytes. This is a static check, not native/MQL5 execution.
- ER013: [original identity/count logic](https://github.com/27c7nmt5m8-coder/EA/blob/c5ecf7683ba0d61c83974270d86d5287fb65fb4e/tools/workflow_eval/real_tasks.py#L144),
  [duplicate and fixture exclusion tests](https://github.com/27c7nmt5m8-coder/EA/blob/c5ecf7683ba0d61c83974270d86d5287fb65fb4e/tests/test_workflow_real_tasks.py#L35).
  Three original Python tests plus head-independent identity/one-record-two-arm
  count assertions passed. Identity stability does not authorize mutating a
  historical audit record's head; the original update API rejects that change.

## Cause assessment and shadow verdict

Both: `INPUT_AMBIGUITY` and `INSUFFICIENT_EVIDENCE` apply to missing summary
evidence, not unsupported source oracles. `PROVIDER_VARIABILITY` describes
observed confidence/probability jitter with unchanged choices. There is no
observed within-case Sol classification instability or parser/runtime defect.
`CONFIDENCE_CALIBRATION` and the causal link between omission and low confidence
remain **UNEXPLAINED**: this experiment has no calibration dataset or intervention.
No claim that adding wording would fix either anomaly.

Diagnostic candidate: **SHADOW_CONTINUE_WITH_LOW_CONF_ESCALATION**. Choices
are stable, low Jev confidence reproduces, and source oracles are supported.
This permits continued shadow diagnosis only. Every low-confidence case still
requires Sol xHigh. ER003 remains unknown even there, so further original source
context is required before any semantic decision. **The original PR19 19-case
verdict stays UNMEASURED**. No review skip, final approval or adoption.

## Tokens, cost and time

| Calls | Input | Output | Total | Sum provider/CLI elapsed seconds |
|---|---:|---:|---:|---:|
| Jev targets (10) | 5,020 | 490 | 5,510 | 3.033601 |
| Jev controls (20) | 10,005 | 970 | 10,975 | 5.191989 |
| All Jev (30) | 15,025 | 1,460 | 16,485 | 8.225590 |
| Sol ER003 (3) | 47,215 | 1,104 | 48,319 | 60.663578 |
| Sol ER013 (3) | 47,205 | 505 | 47,710 | 36.665573 |
| All primary Sol (6) | 94,420 | 1,609 | 96,029 | 97.329151 |
| Blind Sol (2) | 31,436 | 730 | 32,166 | 35.843827 |
| All diagnostic calls (38) | 140,881 | 3,799 | **144,680** | **141.398568** |

Jev case total tokens / elapsed: ER003 2770 / 1.862432s; ER013 2740 /
1.171169s; ER007 2805 / 1.240006s; ER016 2725 / 1.246470s; ER001 2720 /
1.419484s; ER010 2725 / 1.286029s. Primary combined tokens = 112,514.
Primary serial wall = 106.111486s (includes runner overhead).
End-to-end wall including blind review is null: not explicitly instrumented in
the execution version; sums of call times are not substituted for wall time.
Source audit/final engineering review tokens are outside diagnostic billing;
their usage is unmeasured, not free or zero. No token reduction claim: repeat
counts/protocols differ and this is not an A/B savings benchmark.
Cost is null, pricing not verified (coverage 0/38).

## Coverage, preservation and limits

Response/choice/confidence/probability/usage/elapsed coverage: Jev 30/30,
primary Sol 6/6, blind 2/2. Binary Sol decisions: only 3/6; unknown 3/6.
Source audit: 2/2. Additional context retrieval, rework/test failures as task
outcomes: null/not a development-task experiment; no invented zero counters.
Sampling is selected, small and temporally narrow, with unmatched severity and
partially matched labels. No probability-calibration, MQL5-runtime, profitability
or production-safety claim.

The start-of-task hash snapshot contains 98 existing records/fixture/provenance/
policy/AGENTS files; all remain byte-identical. src and original evaluators are
unchanged in Git diff. No raw streams, keys or trace are saved. Real-task cohort
is not written; no Trace/Jevgrep reruns. New exclusive local records and this
static safe summary preserve prior unavailable/results history.

## Verification

New focused offline tests: 30. Full Python discovery: 213, one Windows-specific
skip. Local `tests/run_all.py`: gates 3/4/5 PASS, native gates 1/2 blocked by
Windows Application Control; full and authoritative release INCOMPLETE.
Linux/Windows CI and final independent xHigh review are recorded in the PR.
The initial independent review found 4 Important diagnostic-validator/accounting
issues: blind usage-reason injection, malformed events discarding known usage,
orphan/unplanned retry and malformed-result escalation, and model-mismatch
normalization roundtrip. Five focused regression tests plus the existing retry
billing test reproduce the failures and verify fixes. No original evaluator,
fixture, provider request, or live observation changed. Earlier derived audited
reports remain as history; new exclusive reaggregations fix the cost denominator
and include within-case variance comparison. Primary usage/time/choices and
combined 144,680 tokens are unchanged. Re-review is recorded in the PR.
No gate weakened; Draft is retained. Rollback: close this stacked Draft PR or
remove/revert only its diagnostic module/tests/docs/checksum changes.
