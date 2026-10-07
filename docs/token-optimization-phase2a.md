# Phase 2A: canonical authority and shadow selection

## Accepted scope

The current user authorizes development before Phase 1 operational confirmation
reaches 3/3. This is a merge gate, not a development gate. Phase 2A, synthetic
fixtures, replays and CI/review retries do not qualify as normal development
tasks. Main merge also requires explicit approval. No EA source, trading,
Risk/Safety, model floor, Jev 0.90 or review-skip policy change is authorized.

## Ordered implementation plan

1. Inspect latest main, applied rules, existing Phase 1 APIs and cohort evidence.
   Preserve unrelated work and open PRs; use a dedicated branch.
2. Phase 2A-1: 04 verification-body deduplication; 05 canonical fixed spawn
   instructions; 10 source-bound versioned Decision Ledger; 14 semantic-preserving
   AGENTS compression; 15 shared canonical rules with skill-specific guidance.
   Add Red tests first. Do not change dependency selection.
3. Run focused and Phase 1 regression tests; inspect source/rule coverage and
   exact original evidence reachability before proceeding to Phase 2A-2.
4. Phase 2A-2: 02 deterministic Policy Capsule and 09 content-hash Dependency
   Index. Shadow comparison only: existing full-policy/context/exploration route
   remains authoritative. Unknown/unsupported/stale/protected scope falls back.
   Changed-file and dependency symbol slicing are outside this phase.
5. Measure full versus canonical bytes and available tokens without inventing
   unavailable values. Use the existing cohort; do not create artificial tasks.
6. Verify focused/regression/full Python, existing offline gates, checksums,
   Linux and Windows CI. Perform a fresh read-only independent Sol High review,
   repair Critical/Important findings and reverify the final diff.
7. Publish a Draft PR and finish as a Ready candidate. Preserve the worktree and
   original artifacts. No automatic merge or production selection promotion.

## Safety and trust contracts

Canonical IDs cannot replace required body delivery to fresh recipients. Resolve
all required rules and retain exact full source files. Verification aliases retain
source identity, original bodies, hashes and reachability; an ID/digest alone is
never PASS. Ledger omissions are unknown, not evidence that a rule does not exist.
Ledger mutation retains superseded decisions, reasons and replacement IDs.

Canonical rule corruption, missing/circular references, unknown versions or hash
mismatches fail closed. Dependency indices do not prove absence: dynamic imports,
reflection, unresolved includes/symbols/configuration and parsing uncertainty
require ordinary exploration. Shadow comparison records false negatives and
cannot silently affect production context selection.

## Commands and evidence

Run from the repository root with a working Python 3.11+ interpreter:

```text
python -m tools.workflow_eval.cli rules-expand AGENTS.md --consumer agents
python -m tools.workflow_eval.cli verification-delivery sources.json
python -m tools.workflow_eval.cli ledger-create accepted-inputs.json
python -m tools.workflow_eval.cli ledger-validate .workflow-eval/ledger-create.json
python -m tools.workflow_eval.cli policy-capsule bundle.json --input classification.json
python -m tools.workflow_eval.cli dependency-index --path tools/workflow_eval/spawn.py
python -m tools.workflow_eval.cli dependency-shadow .workflow-eval/dependency-index.json --root-path tools/workflow_eval/spawn.py --dependency known --legacy acquired-dependencies.json
```

Outputs are ignored `.workflow-eval/` artifacts. CLI JSON inputs reject duplicate
keys and nonfinite values. Verification sources contain distinct source identities,
Phase 1 manifests and current source/tree identities; the CLI binds current Git
identity before reacquiring originals. `--reviewer-request`, `--xhigh`,
`--blocked-judgment` or `--unexplained` expands original evidence. Spawn consumes
`--verification-delivery` instead of a second copy of `--test-evidence`.

Ledger inputs explicitly supply the accepted specification/decisions, forbidden
changes, unresolved questions and tracked source provenance. Creation is a record
of caller-supplied acceptance, not proof of user approval. Updates require a new
timestamp; replacement decisions retain reasons and superseded identities.
Rendering stale/incomplete ledgers requires all current authority categories and
the previously verified full specification; missing authority is BLOCKED.

Capsule classification contains `role`, `task_type`, `changed_paths`, `protected`,
`dependency`, `repository_area`, `operation_type` and `review_mode`. The report
binds the bundle, canonical graph, repository/skill documents, current config and
workflow policy. Required bodies remain complete in `actual_policy`. Candidate
IDs/hashes are shadow metadata and cannot be delivered alone as policy authority.
The only smaller candidate profile is routine unprotected documentation work;
unknown classifications use full rules. Missing or contradictory authority blocks.

The dependency parser records tracked Python AST imports, public interfaces,
direct symbol/call candidates, literal file/config references and MQL include
metadata with exact source/dependency hashes. It does not infer runtime semantics
or completeness. Dynamic imports, reflection, external imports, unsupported syntax,
generated files, ambiguous resolution and MQL semantics remain unresolved.
Validation rebuilds facts against current source, index, parser/runtime and Git
identity. The legacy comparison must separately supply acquired/independent
provenance, paths, material paths, current source/tree/fingerprint and file hashes.
These caller assertions do not prove independent exploration. Missing/stale legacy
evidence produces null TP/FP/FN metrics with reasons. Material false negatives block
promotion; actual routing always remains ordinary full exploration.

## Measurement limits

Semantic-coverage audit retains original document clauses and exact hashes, mapped
to acquired canonical rule bodies. Structural coverage tests are not proof of
language equivalence; independent review evaluates the meaning. Raw AGENTS byte
reduction alone is not a model-token saving: resolved full bodies must be counted.
Transport probes compare all required bodies once versus repeated full documents.
Synthetic verification probes preserve original artifacts and each source alias.
Neither probe counts as normal development/cohort evidence or quality parity.
Unavailable token/model-execution observations remain null with missing reasons.

## Rollback

Use the legacy full spawn payload, full policy/specification, ordinary repository
exploration, original verification and mandatory fresh independent review. New
optimizations are optional; their failures cannot authorize unsafe continuation.
Revert this phase's commits to remove the tooling without product migration.

## Completion evidence

Final source SHAs, test/CI/review results, shadow comparisons, measurements,
limitations and the Phase 1 operational merge gate are recorded against the exact
PR HEAD. Existing product release INCOMPLETE/NOT_RUN/BLOCKED statuses remain
distinct from tooling and C++ mock gate results.
