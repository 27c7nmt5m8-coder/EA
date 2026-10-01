# Workflow experiment integration after High-first

Base main: `82d1371b6c2b62608b33171d5f3f068cf6111d98` (PR #21 merged).

This integration consolidates the useful developer-tooling from Draft PRs #18, #19, #20, and #22 without merging their obsolete stacked history into main.

## Preserved

- synthetic Agent Trace / Semantic Regression / Jevgrep experiments
- real-case semantic regression fixtures and provenance
- low-confidence diagnostic tooling and historical result documents
- future-only prospective shadow ledger/report tooling
- historical model/effort labels and measured results
- `review_skip_enabled=false`
- `confidence_threshold=0.90`
- deterministic CI and native-gate separation

## Active-policy migration

New live execution uses GPT-6.1 Sol High. Risk category, protected status, critical severity, or unknown dependency makes review mandatory but does not automatically make xHigh mandatory.

Historical GPT-6 Sol / xHigh and GPT-6.1 Sol / xHigh observations remain historical and are never rewritten into High.

Evidence-based xHigh escalation remains available through the active workflow review policy introduced by PR #21. The imported experiment tools do not create a second automatic xHigh floor.

## Scope

No `src/` EA trading logic, Risk/Safety behavior, Worker runtime, order logic, SL/TP/BE/trailing, lot sizing, Monte Carlo, Fintokei, portfolio risk, or persistence behavior is changed by this integration.
