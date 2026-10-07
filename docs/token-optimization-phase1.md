# Phase 1: exact duplicate transport and evidence reuse

## Specification

Implement roadmap items 01, 06, 07, 08 and 16 only. Preserve EA sources,
protected/unknown dependency behavior, mandatory independent fresh read-only
`gpt-6.1-sol / high` review, deterministic gates, `review_skip_enabled=false`,
Jev confidence 0.90 and existing role floors. No model fallback or live orders.
Optimization failure uses the original full-context/full-review route.

01: an explicit resume API binds recipient identity, continuity and actual prior
full-body possession to a validated packet, repository identity, current
fingerprint and source SHA. Only exact unchanged related bytes may be reused;
changed files remain full. Protected, unknown, expansion, stale evidence or
questions requiring expansion disable delta. Reviewers always use fresh full
context. Prior handles alone cannot establish possession.

06/07: content-addressed attestations bind repository, Git tree, base, actual
diff, changed paths/content, dependency hashes, task, specification, rules,
policy/version, classification, verification, questions, reviewer model/effort,
schema and instructions. Only completed independent OK reviews with observed
provenance, no missing context/material uncertainty/staleness and acquired
required verification are reusable. A tree match is necessary, never sufficient.
Any differing review input falls back to a new review. High cannot satisfy xHigh.

08: retain original artifacts. A successful check transfers an artifact-backed
manifest (source/tree/command/platform/toolchain/exit/status/counts/warnings/
path/hash/CI identity/equivalence/time); never infer PASS from a digest. Expand
original logs on fail, material warning, blocked judgment, any mismatch,
unexplained/contradictory/missing evidence, reviewer request or xHigh.

16: model JSON uses deterministic sorted keys, compact separators, UTF-8,
`ensure_ascii=False`, `allow_nan=False`. Human files may remain pretty.

## Implementation plan

- [x] Capture Phase 0 baseline using existing telemetry; missing values remain
  null with reasons. Preserve raw local logs and do not count synthetic cases
  as prospective cohort tasks.
- [x] Add canonical serialization with failing key-order/Unicode/nonfinite tests.
- [x] Extend spawn with recipient-bound resume and full fallback tests.
- [x] Add exact review attestation and equal-tree reuse with mutation tests.
- [x] Add artifact-backed failure-on-demand verification and expansion tests.
- [x] Integrate CLI, telemetry, documentation and rollback instructions.
- [ ] Run focused/regression/full Python and existing offline gates, update
  tracked distribution checksums, self-review, independent Sol High review,
  fix findings, reverify and check Linux/Windows CI on the exact PR HEAD.
- [ ] Publish a Draft PR and report remaining gates; never merge automatically.

Review focus: forged possession, stale/aliased repository identity, modified
attestation input/provenance, unavailable or mismatched original artifacts,
and semantic changes hidden by serialization. Each must fail closed.

## Rollback

Do not call `resume-request`, attestation lookup or verification manifest APIs;
use existing `spawn-request` and original verification logs. Alternatively revert
this phase commit. No EA or routing configuration migration is involved.

Phase 2 is gated on Phase 1 merge approval and at least three distinct real
prospective development tasks without material regressions. 30/50-task cohort
milestones and semantic slicing remain outside this phase. Unknown token usage
is not zero or proof of savings. Byte savings do not prove token savings.

## Baseline and measured transport

Latest fetched main: `8bce9a51624fbe74b81ce9ea174bcb113cc2be9a`, tree
`4186a96a522e669d651e05265714c552cd15cf4f`. Initial worktree was clean;
the existing user's branch remains untouched. Open PRs were checked for changed
files; none implements this phase. GitHub main branch rules API returned no
active rules; local AGENTS/model policy and explicit merge approval still apply.

Initial Python discovery: 355 tests, 0 failures, 1 skip (symlink privilege),
194.700 seconds. Existing product offline gates: BLOCKED, BLOCKED, PASS, PASS,
PASS; overall INCOMPLETE. These product gates ran after tooling edits began,
with every EA source byte unchanged. Application Control matched the existing
compiler binary hash; no policy bypass was attempted. Baseline metadata,
source hashes and numeric null/missing reasons remain under ignored
`.workflow-eval/phase0-baseline.json`. Nine directly relevant baseline authority/
implementation files total 82,105 UTF-8 bytes; this is an inspection footprint,
not a complete task context or token count.

The root host's actual `turn_context` metadata reports `gpt-6.1-sol / high`.
Ongoing cumulative usage is available as a separately labeled numeric snapshot;
completed whole-task usage and an A/B difference for this development task
remain null. These counters are not substituted for the baseline or pair data.

One synthetic full-body serialization pair used the existing Codex CLI with
explicit requested `gpt-6.1-sol / high`, without reviews, tools or routing
changes. Both responses were ACK. Provider-reported metrics:

| Metric | Pretty | Canonical compact | Difference |
| --- | ---: | ---: | ---: |
| Input tokens | 25,190 | 21,821 | -3,369 |
| Cached input tokens | 12,544 | 12,544 | 0 |
| Cache write input tokens | 0 | 0 | 0 |
| Output tokens | 5 | 5 | 0 |
| Reasoning output tokens | 0 | 0 | 0 |
| Total tokens | 25,195 | 21,826 | -3,369 |
| Payload bytes | 34,967 | 23,591 | -11,376 |

Model/effort execution metadata and exact backend call counts were not emitted;
those observed fields remain null, separate from requested settings. Raw CLI
events were not saved. Numeric results are in ignored
`.workflow-eval/provider-serialization-probe.json`. This fixture demonstrates
formatting overhead only, not review quality parity, real-development savings,
Delta token savings or cohort coverage. No synthetic arm/retry counts as a
prospective task. Whole-task usage for this development session is unavailable.

## Public APIs and CLI

All paths below are from the repository root. Human output files remain pretty;
the `message` field sent to models and new identities use canonical JSON.

- `serialization.canonical_json(value)` / `canonical_hash(value)` preserve all
  JSON values and reject nonfinite numbers/nonstring keys.
- `resume.retention_receipt(...)` requires explicit recipient/session identity,
  acknowledged delivery, confirmed retained full bodies, recorded model/effort
  and current source. The helper cannot inspect model memory: the host caller
  must obtain those observations, never infer them from settings or handles.
- `resume.build_resume_request(...)` returns either `route=delta` with the
  existing agent's `followup_task` arguments, or `route=full` with a fresh
  `spawn_agent` request. It never executes a host call. Any unresolved question
  conservatively requests full context. Receipt/source invalidation is normal.
- `attestation.build_identity`, `create_attestation`, `save_attestation` and
  `lookup_attestation` bind actual Git evidence and exact inputs. Cache hits
  identify completed review evidence; `new_review_executed=false` and
  `mandatory_review_satisfied_by=matching_attestation` explicitly distinguish
  reuse from execution. The trusted local cache cannot authenticate invented
  receipts; unobserved provenance must use a new review. Eligibility preserves
  the existing narrow known/docs-only/unprotected/clean-context classifier.
- `verification_context.build_verification_manifest` acquires original runner
  JSON plus declared logs. `verification_transport` reacquires originals before
  choosing manifest/original/blocked. Generic APIs require caller-acquired
  current identity because artifacts may reside outside a checkout. The CLI
  checks actual Git HEAD/tree and forces originals for dirty working scopes.
  A trusted runner record must declare `log_paths` and record source/tree,
  scope, command, platform/toolchain, exit, counts, warnings and equivalence.
  Missing fields in existing `run_all.py` records deliberately keep the original
  route; no release or native PASS is inferred.
- `optimization_telemetry.measurement` extends existing numeric telemetry with
  null/missing reasons. CLI `optimization-measurement` accepts observed fields
  only. It does not create cohort membership; existing prospective validators
  retain that authority. Actual host metadata is required for observed models.

```text
python -m tools.workflow_eval.cli retention-receipt .workflow-eval/full-packet.json --recipient AGENT_ID --continuity SESSION_ID --acknowledgement DELIVERY_ID --role worker --observed-model gpt-6.1-sol --observed-effort high --possession-confirmed
python -m tools.workflow_eval.cli resume-request .workflow-eval/bundle.json --prior .workflow-eval/full-packet.json --receipt .workflow-eval/retention-receipt.json --recipient AGENT_ID --continuity SESSION_ID --role worker --task-name continue_task --spec-file .workflow-eval/spec.md --complex-work
python -m tools.workflow_eval.cli attestation-identity .workflow-eval/bundle.json --spec-file .workflow-eval/spec.md --test-evidence .workflow-eval/acquired-verification.json --instruction-version review-v1
python -m tools.workflow_eval.cli attestation-record .workflow-eval/bundle.json --spec-file .workflow-eval/spec.md --test-evidence .workflow-eval/acquired-verification.json --instruction-version review-v1 --review .workflow-eval/review.json --host-receipt .workflow-eval/host-receipt.json
python -m tools.workflow_eval.cli attestation-lookup .workflow-eval/bundle.json --spec-file .workflow-eval/spec.md --test-evidence .workflow-eval/acquired-verification.json --instruction-version review-v1
python -m tools.workflow_eval.cli verification-manifest .workflow-eval/runner.json --log .workflow-eval/test.log
python -m tools.workflow_eval.cli verification-context .workflow-eval/verification-manifest.json --current .workflow-eval/current-verification-scope.json
```

Attestation requires original acquired verification with `status=PASS`,
`acquired=true`, `stale=false`, `commit`, `tree`, nonempty `required_checks` and
matching `checks` (`name/status/exit_code/warnings`). The completed review has
`status=OK`, `verdict=pass`, `completed/independent/fresh_context/read_only/
acquired_verification=true`, `material_uncertainty/stale_evidence=false`,
`findings` and empty `missing_context_ids`. The host receipt records observed
model/effort, `fork_turns=none`, completed independent fresh read-only context,
receipt identity and exact canonical identity/review hashes. See strict schemas
in `attestation.py`; unavailable observations are not fabricated.

Verification also declares complete `log_paths` and top-level `artifacts`
(`path/role/sha256/size_bytes`), with exactly one original JSON record plus logs.
Each required check references its original logs. The original record equals
the verification envelope excluding top-level artifact descriptors, avoiding a
circular self-hash. Lookup reacquires every declared original and checks exact
bytes/types; missing or changed artifacts require full review. An acquisition
flag or digest without the original bodies cannot establish reusable evidence.

Original declared failures, nonzero/unknown exit codes, material/unknown warnings,
stale flags and missing-context assertions are checked recursively, including
inside otherwise PASS checks. Nested source/tree identities and timestamp-prefixed
log diagnostics/counts are also checked. Any contradiction forces original/full review.
Manifest-only transport also requires a valid timezone-aware `recorded_at`;
missing/invalid timestamps expand originals rather than inventing freshness.
The trusted runner record and actual current scope must explicitly agree on
`protected=false` and `dependency=known`; absent/uncertain classification expands originals.

Metadata-only commit reuse additionally requires original verification declaring
`source_equivalence=git_tree_exact`, `commit_sensitive=false` and Git-proven equal
source trees. Never label commit-sensitive CI evidence this way. Base/diff/spec/
rules/policy/verification and every other identity input must still match.

## Roadmap boundaries

| Stage | Items | Prerequisite |
| --- | --- | --- |
| Phase 1 | 01, 06, 07, 08, 16 | Exact duplicate only; this PR |
| Phase 2A | 02, 04, 05, 09, 10, 14, 15 | Approved Phase 1 merge and at least 3 distinct successful prospective tasks; shadow/comparison first |
| Phase 2B | 11, 12, 13, 17, 18, 19 | Stable Phase 2A, quality metrics |
| Phase 3 | 03 | 30-task evaluation, no material quality regression; unchanged dependencies only, shadow first |
| Phase 4 | 20 | Sufficient 50-task evaluation, shadow first; production adoption needs approval |

Production semantic slicing remains disabled. Cohort growth cannot be synthetic
retries, CI reruns, aliases or comparison arms. Keep 30/50 summaries separate,
do not lower thresholds or infer quality parity from the serialization fixture.
