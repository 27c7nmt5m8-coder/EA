# Prospective Semantic Regression shadow protocol v1

## Scope and dependency

Sibling of PR20, based on PR19 head
`766343e1f52411c8bb49a6d7fcfd0e65a64e343a`, branch
`feat/semantic-regression-real-cases` (base of PR19:
`feat/jev-experimental-benchmarks`). PR20 head
`41684723a380a27525482ed6fe290f26795aa56c` is verified to branch from that
PR19 head. No diagnostic module from PR20 is a code dependency.
[PR20](https://github.com/27c7nmt5m8-coder/EA/pull/20) supports preserving the
0.90 threshold, requiring review for low confidence, and explicitly handling insufficient
input evidence. It does not establish calibration or permit skipping reviews.

## Implementation plan and trust boundary

1. Add a dedicated immutable protocol and append-only metadata recorder.
2. Freeze authoritative GitHub PR identity/creation/review metadata and actual
   Git merge-base/diff/source hashes with pre-review contract inputs.
3. Record every Jev attempt before issuing a blinded normal-review ticket.
4. Import allowlisted metadata from the normal GPT-6.1 Sol High review;
   freeze its findings before source/test-backed ground-truth adjudication.
5. Report PR and item denominators separately, all-attempt billing, confidence
   bands, persistent misses and counterfactual estimates. Add offline tests.
6. Verify unchanged protected files/history, full gates, Linux/Windows CI, and
   independent Sol High review; create a Draft sibling stacked PR.

The recorder enforces mechanical order, identity, hashes and schemas. It cannot
prove that a person has never seen an unpublished review or that an external
reviewer ignored information outside its packet. Attestations are explicit,
not cryptographic proof of human knowledge. A false/unknown blinding or prior
review attestation is excluded. GitHub review history is also checked before
freeze. Normal reviews are performed by the existing development workflow;
the recorder never substitutes a small classification call for a full review.
Evidence digests document adjudication provenance, not automatic proof of
semantic correctness. Independent adjudication remains necessary when disputed.

## Frozen collection rules

One unique future EA development PR is one task. PR11/12/17/18/19/20 and this
tooling PR cannot enter primary collection. Creation must follow the protocol's
activation timestamp, set only after this tooling is completed. Tooling-only
changes are excluded. No prospective cases are collected in this implementation
PR; the primary cohort starts at **0**.

The first pre-review head is primary forever. Revisions, retries, reviewers,
contract items and A/B observations do not create tasks. Contract input may use
requirements, task specifications, project rules, known behavior, deterministic
test intent and protected behavior; oracle/review/fix/merge outcomes are forbidden.
Unclear contracts are preflight NOT_ELIGIBLE_CONTRACT_UNCLEAR, outside the task
denominator. Protocol and item inputs are immutable; changing threshold requires
closing collection and a distinct cohort/protocol, not editing the active one.

Strict order: snapshot/contract freeze -> Jev attempts/result digests freeze ->
blinded review ticket -> normal Sol High findings freeze -> evidence-backed
ground truth. Sol reviewer sees no Jev choice/confidence/probability/routing/
rationale. Blinding violation is CONTAMINATED_REVIEW, excluded from comparison
with all known usage preserved. Prior externally executed reviews, retrospective
imports and stale head/diff/contract metadata are rejected/excluded.

Actual reviews always use gpt-6.1-sol/high. Requested model/effort and effective
metadata are separate; unavailable backend identity stays null. Wrong model,
unavailable or unknown results never become binary no_regression.

Mandatory xHigh takes precedence for src/protected/critical/unknown dependency,
including Entry, SL/TP, BE, Trailing, Risk, Monte Carlo, Fintokei, portfolio,
Worker failures, orders/ownership/mutex/persistence, routing and safety policy.
Otherwise routing metadata distinguishes PROVIDER_REVIEW, UNKNOWN_REVIEW,
LOW_CONF_REVIEW (<0.90), SHADOW_HIGH_CONF (valid binary >=0.90). These are
counterfactual recommendations; Jev cannot approve product behavior or merge.

## Evaluation

10 unique eligible completed PRs: checkpoint only. 20: primary assessment and at
most a proposal, never automatic adoption. PR-level eligible/ineligible,
contaminated, unresolved, complete coverage and routing counts are separate
from item TP/TN/FP/FN, recall/precision/specificity/accuracy/agreement and misses.
Unknown/unresolved never enter binary confusion counts. Confirmed misses remain
visible even if excluded from comparison, recovered by Sol, or fixed later.
Critical miss >=1 yields BLOCKED_CRITICAL_MISS; Important miss is individually
IMPORTANT_MISS. Contamination/Important misses/instability require shadow
remediation; incomplete evidence/count yields SHADOW_CONTINUE. A 20-case
proposal requires complete coverage and no Critical/Important/high-confidence
FN/provider/blinding problems. Confidence bands <.50, [.50,.70), [.70,.90),
>=.90 report counts, accuracy, misses/FP, agreement and review-required routing separately;
neither 20 PRs nor small per-band samples establish calibration.

Primary-head billing sums every uniquely identified Jev and normal-review
attempt including retries, contaminated and unavailable calls. Missing stays
null + reason + coverage with
labeled known subtotals. Cost requires actual price/tier/cache/billing evidence;
otherwise null. Counterfactual-only savings use measured eligible high-confidence
no-regression *nonmandatory* reviews, subtract experimental Jev overhead, and
are never actual savings. Negative estimates are retained. Processing/CLI time,
orchestration wall and retry time are separate. Unobserved rework/context/test
outcomes remain null; blinded Jev cannot be credited with reducing rework.

Resolved items remain in item-level comparison when another item in the same PR
has unresolved ground truth. That PR cannot count toward the 10/20 eligible-PR
milestones until all items resolve. Primary labels use the first valid frozen
result; miss auditing checks every valid retry and reports unique missed items
with their attempt IDs, never additional tasks. Confirmed Critical misses block
even when a different retry caught the regression. Known model/effort violations
exclude comparison and retain failed-attempt usage.

Band accuracy/FN/FP/agreement denominators use primary first-valid item results.
Band Critical/Important safety misses audit every valid retry using its actual
observed confidence, with a separately labeled `safety_audit_item_count` (unique
PR/item per band). One item can appear in multiple safety bands; these counts
are nonadditive and must not inflate the PR or primary item denominator.

Token/time scope is the first frozen head's Jev and normal Sol review attempts.
Later remediation and independent adjudication review billing is not collected
by this recorder: `complete_development_billing` stays null with a reason.
These primary-head totals must not be described as complete development cost.
`processing_seconds` is measured client/CLI elapsed, not provider-server compute
time or human effort. Human/orchestration wall is explicit observational metadata.

## Storage and rollback

Only dedicated gitignored `.workflow-eval/semantic-prospective/` is written.
Immutable protocol, safe summaries, hashes, numeric metadata, attempts, ticket,
findings/item labels and adjudication evidence IDs/digests are retained; raw
source/diff, provider streams, private traces, credentials/accounts/logs are not.
Separate IDs/storage/metrics from the 30/50 real-task cohort in both directions.
No CI gate, routing policy, EA/source, historical fixtures/results or review skip
changes. Stop collection and revert dedicated tools/tests/docs/checksums to
rollback; existing cohorts and product state require no migration.

## Explicit CLI workflow

Use `python -m tools.workflow_eval.semantic_prospective_cli --help`. This is a
separate recorder entry point so the existing fixture/real-task CLIs keep their
historical behavior. No normal test/CI command issues Jev calls or collects cases.

After tooling verification, initialize **once**, with the actual tooling PR
number and its verified head (not a historical sample or guessed next PR):

```console
python -m tools.workflow_eval.semantic_prospective_cli init --tooling-pr N --completion-sha VERIFIED_HEAD
python -m tools.workflow_eval.semantic_prospective_cli report
```

Only a future real development PR created after that activation can be frozen.
Before any external final review, prepare a safe contract file, then:

```console
python -m tools.workflow_eval.semantic_prospective_cli freeze --pr FUTURE_PR --contract-file contract.json
python -m tools.workflow_eval.semantic_prospective_cli jev TASK_ID --live
python -m tools.workflow_eval.semantic_prospective_cli review-start TASK_ID --blinded --no-prior-external-review
python -m tools.workflow_eval.semantic_prospective_cli sol-record TASK_ID review-metadata.json
python -m tools.workflow_eval.semantic_prospective_cli revision TASK_ID revision-metadata.json
python -m tools.workflow_eval.semantic_prospective_cli truth TASK_ID truth-metadata.json
python -m tools.workflow_eval.semantic_prospective_cli rework TASK_ID rework-metadata.json
python -m tools.workflow_eval.semantic_prospective_cli report
```

`revision`/`rework` are optional observations. Run the complete normal pinned-head
review in a fresh GPT-6.1 Sol High context using the neutral ticket packet, real
source/dependencies and deterministic evidence. Do not expose the dedicated
ledger or experiment report to that reviewer. The review is externally executed;
`sol-record` imports measured metadata and does not run a classifier masquerading
as a review. Missing backend identity/usage must stay null, never invented.

Jev requests are reserved before the API call. An existing pending reservation
or overlapping start is rejected before another paid call. A crashed request
stays pending with missing usage and blocks the experiment review ticket.
Recover only with its actual response/verified failure metadata through the
typed ledger; never fabricate zero usage. This recorder cannot block the normal
EA development review or GitHub merge. An unavailable completed attempt allows
normal review while the experiment records incomplete/provider-unavailable review.

## Typed metadata reference

All objects reject extra fields; timestamps include timezone; SHA/digests use
lowercase hex. Constructors/constants in `semantic_prospective.py` are the
authoritative versioned schema. Safe JSON summaries only:

| Object | Fields / constraints |
| --- | --- |
| Contract file | `items`, `known_requirements`, `known_protected_areas`, `test_evidence`, `prior_review_known=false`, `kind=ea_development` |
| Contract item | unique `item_id` (I1 etc.), `requirement`, `baseline`, `candidate`, `evidence` summaries; `origins` drawn from user_requirement/task_spec/project_rules/changed_behavior/test_intent/protected_behavior; `dependency` known/unknown; `protected_areas`; boolean `critical_dependency` |
| Test evidence | `kind`, `digest`, `status` PASS/FAIL/BLOCKED/UNKNOWN/UNAVAILABLE; digest of actual evidence available before review, no raw logs |
| Sol attempt | `ATTEMPT_FIELDS`: unique attempt_id; item_id/choice/confidence/probabilities null; fixed requested_model/requested_effort; effective identity nullable; status/reason; nullable canonical usage and usage_reason; elapsed_seconds; raw_result_digest or null/raw_digest_reason; execution live; findings; exposed_to_jev; started_at/completed_at; snapshot_digest/contract_digest/head_sha/diff_digest/source_fingerprint |
| Sol findings | one record per frozen item: item_id, choice regression/no_regression/unknown, counts (critical/important/minor) |
| Truth envelope | frozen snapshot_digest/head_sha/diff_digest and items; per-item state RESOLVED or GROUND_TRUTH_UNRESOLVED, choice/severity, evidence [{kind,digest}], adjudicator_model/effort fixed; unresolved choice/severity null and evidence empty |
| Resolved truth | >=2 evidence kinds, at least one test/compiler/ci/source/specification; regression severity critical/important/minor; no_regression severity null. Cannot rewrite a confirmed oracle/miss |
| Revision | head_sha, diff_digest, nullable fix_commits/red_green_tests; never changes primary head |
| Rework | nullable confirmed_findings/fix_commits/red_green_tests/review_rounds/reopened_issues/regressions_after_fix/context_retrieval/test_failures/orchestration_wall_seconds |

Every event has a unique ID, sequence, previous/event digest and timestamp;
files are exclusively created and replay validated before each append. This
detects stale edits/order errors; it is not a signed remote immutable audit log.
GitHub checks formal reviews plus explicit unpublished-review attestations.
Review content in general comments and private conversations cannot be proved
absent by the API. Unknown attestation must exclude the case.

Product eligibility is conservatively limited to PRs touching src/, C++ EA tests,
README_JA.md or VALIDATION_JA.md; Python/tooling-only PRs are excluded. Every src/
change is mandatory xHigh even when an item summary fails to name a protected
area. This conservative filter can reduce the nonmandatory candidate sample.

This remains a shadow experiment, not assurance of EA product quality. MetaEditor
is not required for this product-unchanged tooling validation; authoritative
release status is reported separately. PR verification results are recorded in
the Draft PR, not substituted for future prospective case evidence.
