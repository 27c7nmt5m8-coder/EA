# Context relevance trial (opt-in diagnostics only)

This harness does not install hooks, select production models, modify EA files,
summarize original entries, delete history, or authorize operations. It uses the
existing TypeSafeAI/Model Orchestrator policies unchanged. The user explicitly
authorized only this isolated experiment. Do not infer permission to deploy it.

## Run

Use the isolated `trial/jev-context-compaction` worktree, Python 3.10+, and the
existing authenticated Codex CLI. No Python dependencies are required. Do not
put credentials on command lines or in files. `TYPESAFE_API_KEY` is read only
from the environment in the parent process and excluded from Replay children.

```bash
python3 -B -m unittest discover -s tests -p test_context_trial.py
python3 -B .agents/skills/model-orchestrator/scripts/evaluate_routing.py
python3 -B -m tools.context_trial.run --out ../new-offline-run --bypass-jev
python3 -B -m tools.context_trial.run --out ../new-live-run --live-jev --replay
```

Output must be a new directory. The fixed default source revision is the trial's
main baseline, not a claim that it is the newest main. `--revision` explicitly
selects another recorded Git revision. Changing it requires rechecking exact
source spans, annotations and expected facts before drawing conclusions.

Live mode makes nine bounded relevance requests for the current curated corpus.
Without `--live-jev`, no API calls occur. `--bypass-jev` takes precedence even if
both flags are supplied. No API retries are performed. Missing credentials,
HTTP/authentication/quota errors, timeouts, malformed results or uncertainty
retain entries. They never weaken any EA safety gate. Relevance confidence must
be at least 0.8 to apply a Choice; Score is recorded, not used as a drop threshold.
This threshold was fixed before measurement and was not tuned for reduction.

The API contract comes from the existing Skill's official references:
[HTTP API](https://docs.typesafe.ai/api),
[Choice](https://docs.typesafe.ai/primitives/choice),
[re-ranking cookbook](https://docs.typesafe.ai/cookbooks/rerank_typesafe).
The corpus is small enough to send one entry per call with Choice and Score
together. No batch ever contains the full context. HTTP redirects are rejected;
provider error bodies, request headers and credentials are never recorded.

## Data and boundaries

`corpus.py` extracts original text spans from Git. `Entry` is immutable. IDs,
source locations and SHA-256 bind the separate classification/audit records to
the originals. `originals.json` preserves all entries; selection only builds
Replay views. DROP_CANDIDATE originals also remain retrievable in this trial.

This is a **curated retrospective evidence pilot**, not an arbitrary-session
ingestor. Typed metadata and manually checked labels are required. Goals,
specifications, prohibitions, completion criteria, safety, state, confirmed
causes, baselines, OOS, important Tester/compiler/regression results, unresolved
or unverified work, user-kept information and direct working code are PINNED.
Failed hypotheses are conservatively PINNED. Dependency closure, unknown entry
kinds and unknown state relations also pin. Jev cannot unpin anything.

Do not apply the classifier to automatically typed or unreviewed conversation
data: detecting user specifications or implicit safety constraints within
arbitrary text is not implemented or validated. This restriction is one reason
the experiment cannot establish production adoption readiness.

Exact nonpinned duplicates become ARCHIVE before Jev. A large success log can
be archived only when its caller identifies a complete preserved summary as a
dependency and it contains no failure/warning/unknown/error marker. Such a
summary is not generated here. Important compiler/test results are pinned first.
There was no eligible success-log compression or duplicate in the pilot corpus.

Jev receives only a bounded reviewed goal, type, short manually redacted
description, state relation and boolean dependency flags. Original text, source
code, entry IDs/paths, raw logs, audit labels and answer keys are absent. A
defensive sensitive-pattern screen rejects the entire payload; it does not
pretend regex filtering can certify arbitrary personal information. Manual
representation review is mandatory. No user sessions are sent to Jev.

## Replay and metrics

Every entry needs a separate audit label. Hash/coverage/pin checks plus zero
critical false drops gate Replay. At least one applied live Jev decision is
also required, so an offline bypass is never misreported as Jev-filtered A/B.
Later baseline citations and B restores trigger an additional false-drop audit.

A uses current deterministic policy only. B uses that same policy plus Jev.
Both see the same task, frozen source revision and requested model/effort.
Each stage is an ephemeral Codex CLI invocation with the previous stage answers
and current exact originals. Native tools, plugins and hooks are disabled in
these children only; the task is an evidence-only replay. This is not a full
autonomous investigation with compiler, filesystem and retrial decisions.
No persistent Codex setting is changed. Native tool events invalidate a round.

An omitted-entry catalog contains IDs/types/source locations, not summaries.
The model can request IDs; original text is restored and its extra rounds,
tokens and latency are counted. The bound is three rounds per stage. Fact
grading is exact and independent of Jev. **Fact PASS is not overall PASS**:
the harness leaves overall correctness pending until a separate narrative and
deliverable review. Empty answers cannot pass completion. Archive retrieval and
failure behavior have offline tests; the live pilot required no restores.

Context size means UTF-8 bytes of original entries, excluding wrappers,
catalogs and system prompts. It is not a tokenizer estimate or Codex internal
context occupancy. Actual CLI `turn.completed.usage` supplies root input/output
tokens; TypeSafe response `usage` supplies Jev tokens. All rounds count, including
restores; total B adds Jev input and output. Missing measurements are UNKNOWN.
Latency B includes filtering. Cached-token discount, billed cost and hidden
context occupancy are UNKNOWN in the first run. No price estimate is substituted.

File/tool counts apply only to the explicit replay protocol. Source preparation
and setup are outside each arm; repeated investigation is UNKNOWN. Generation,
review and experiment-development overhead in the outer chat are not included
in per-arm totals. Absolute savings for normal Codex task completion cannot be
inferred from these measurements.

Keep local run output outside the distribution. Only sanitized aggregate
measurements and provenance hashes belong in the report. Do not commit user
session contents, logs, credentials, binaries or generated full contexts.
