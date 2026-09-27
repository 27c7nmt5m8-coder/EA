# Native gate implementation plan

Goal: preserve Windows security and make exact-commit Windows CI native results
composable with required local gates. Scope: validation infrastructure only.
The user's ten phases and acceptance criteria are the governing specification.

- [x] Inventory current Git and the five shipped gates; inspect existing CI first.
- [x] Read Code Integrity events, correlate current byte hashes, PE architecture,
  signatures and compiler. Separate historical block evidence from current launch results.
- [x] Add false-green regression tests before the combined runner implementation.
- [x] Add read-only preflight, preserve BLOCKED, continue independent Python gates.
- [x] Correct MQL integer representation in the C++ adapter only; add width and
  post-2038 UTC conversion assertions without changing existing test expectations.
- [x] Extend existing CI with Windows UCRT64 native-only job and SHA-tagged evidence.
- [x] Local Python gates and MetaEditor compilation on isolated source copies.
- [x] Review exact diff, secret scan, checksum update, commit, draft PR, actual CI.
- [ ] Final exact HEAD CI verification plus fresh local combined run; results are
  recorded in .validation/gate_result.json and the PR, not self-referencing source commits.

Review focus: stale/foreign SHA; skipped jobs or failed steps; unknown or unreadable
events; dirty or changing worktree; Linux LP64 versus Windows LLP64; stale output
reports. CI delegation requires the same repository, branch, workflow path, current
attempt, complete success, required native steps and unexpired SHA-named artifact.
An offline gate result never implies MetaEditor, broker, API or market success.

Ruling: reuse existing checkout on a new branch based on fetched origin/main;
starting checkout was clean. No unrelated branch changes are imported.
Ruling: use wevtutil read-only XML through Python because local PowerShell script
execution is disabled. Execution policy and all security settings remain unchanged.
Ruling: Git push credentials were unavailable. With user approval, preserve the
original local branch and register its identical Git tree on a separate connected
GitHub branch. Subsequent updates are ordinary fast-forwards, never force updates.
