# High-first workflow policy migration

Goal: Move active workflow reviews to GPT-6.1 Sol High while preserving mandatory review, deterministic verification, EA safety, and historical provenance.

Architecture: Keep mandatory-review reasons independent of reasoning effort. Require an explicit reason and evidence for additional xHigh review; retain old model IDs only in read-only record parsing and historical pricing.

Spec: The user's 2026-10-01 migration request; AGENTS.md remains authoritative for EA behavior. Execute inline, then obtain an isolated GPT-6.1 Sol High review. No plan approval gate is added to the authorized migration.

Constraints: Do not change src/, past measurements, confidence_threshold=0.90, review_skip_enabled=false, or deterministic gates. Draft PR only; no merge or Ready transition.

Review focus: Unsupported model/effort must fail without fallback; mandatory High must reach the provider; unsupported xHigh reasons must fail before execution; historical prices must never price new-model calls; mixed effort/model pairs must not be treated as comparable.

- [ ] Update boundary tests first and observe the old policy fail.
- [ ] Update policy, triage, benchmark, real-task execution and record/report/telemetry compatibility.
- [ ] Synchronize Skill and offline routing fixtures from the High-first specification; document active versus historical policy.
- [ ] Run focused tests, offline routing evaluation, full Python discovery, tests/run_all.py and diff checks; update checksums.
- [ ] Obtain isolated Sol High review, resolve actionable findings, and reverify changed areas. Escalate only on concrete unresolved evidence.
- [ ] Commit only this scope, push the dedicated branch, create/attach a Draft PR, and inspect CI/reviews.
