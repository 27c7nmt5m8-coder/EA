# Jev context relevance Shadow / Replay trial

> Implementation method: inline, with a fresh whole-change reviewer. User's explicit trial specification is the design authority; no additional generic approval gate is added (AGENTS.md, Skill section).

Goal: measure whether relevance selection can reduce total completion tokens without losing evidence, safety, correctness, or verification. This is a diagnostic experiment, not production compaction.

Architecture: immutable original entries plus separate classification records. Deterministic pinning and duplicate selection precede bounded Jev Choice/Score calls. Replay only follows a complete, zero-critical-false-drop audit; both arms use the same frozen repository, task, model and evidence. No EA source, existing Skills, AGENTS, routing policy, or production hook changes.

Files: `tools/context_trial/{core.py,corpus.py,replay.py,run.py,README.md}`, `tests/test_context_trial.py`, a final report under `docs/`, and SHA256SUMS.txt. Generated run data remain local outside tracked files.

- [ ] Classifier: immutable entries, all mandatory pins, dependency closure, exact duplicates, bounded reviewed representations, bypass, conservative failure handling. Test pin immunity, malformed responses, privacy skips, missing dependencies, API failures and no mutation before implementation.
- [ ] Audit and corpus: entry hashes and independent required-evidence labels; later-use and failed-hypothesis checks. Extract exact original spans from existing tracked, sanitized evidence. Keep future evidence labels out of classifier inputs. Mark retrospective selection and limited representativeness explicitly.
- [ ] Replay: fixed A/current deterministic view versus B/Jev view, original archive restore via IDs, bounded model rounds, actual CLI usage and elapsed time. UNKNOWN for unavailable internal context, cost and investigation metrics. Deterministic correctness rubric and strict phase gate.
- [ ] Execute Shadow and three task types (historical cause analysis, aggregate Tester/log analysis, short documentation change); retain failures and avoid tuning for reduction. Report both bytes and measured tokens without converting bytes to token estimates.
- [ ] Verify related tests, syntax, secret scan, existing routing fixture and fail-open behavior; run existing full gate once, record Windows execution blocks honestly. Review the diff, update checksums, commit and create an unmerged PR (draft if gates incomplete).

Review focus: accidentally dropping user/safety evidence; privacy representation not matching retained source; unavailable usage appearing as zero; baseline contaminated by hindsight; archive cost omitted from total; provider output/error leaking secrets; apparent completion without a completed replay.

Limitations to preserve: reconstructed historical evidence tasks are not full autonomous prior sessions; future-reference annotations are retrospective audit evidence only; no claim of adoption from context byte reduction alone.

Execution ledger: classifier/audit/replay implementation and 3-pair pilot executed. Initial tests failed for absent implementation, then passed; reviewer findings were reproduced as two failures before fixes. Final related suite is 19/19, routing 11/11, AST 5/5, credential/pattern scan and local links pass. Source protections remain unchanged. The full Windows gate stopped on cp932 encoding, then on compiler launch; direct launch confirmed WinError 4551. Python-only existing gates passed 20/495/13. No security setting was changed.

Review: independent Sol/high reviewer found exception-state fail-open and fact-only completion issues, both fixed with regression coverage; archive restore coverage added. No deferred code-review findings. Primary model reviewed all twelve replay narratives separately, finding one baseline-arm static-explanation omission. Report and raw local results preserve this distinction. No production adoption; exact trial outcome and remaining full-session validation are in the report. PR/CI status belongs to the PR, not this persistent plan.
