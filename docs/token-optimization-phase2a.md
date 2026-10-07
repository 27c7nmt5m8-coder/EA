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
