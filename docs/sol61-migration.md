# Project-local GPT-6.1 Sol configuration

Current main's High-first policy and experiment contracts are authoritative. This addition carries only missing project defaults, role guidance and request-based pricing from the earlier migration proposal. It does not rewrite historical measurements.

| Role | Standard model / effort | Boundary |
| --- | --- | --- |
| root / orchestrator / integrate / verify | `gpt-6.1-sol / high` | Directly handle simple work; verify delegated changes and evidence. |
| worker | `gpt-6.1-sol / medium` | High for complex, multi-module, protected, concurrent or orchestration work. |
| explorer / researcher | `gpt-6.1-sol / medium` | Read-only; actual explicit role settings follow the current canonical policy. |
| reviewer | `gpt-6.1-sol / high` | Independent context, read-only. |
| unspecified subagent | `gpt-6.1-sol / high` | Explicit supported spawn settings override defaults. |

Mandatory review cannot be omitted. Protected, critical, EA, financial and unknown-dependency tasks retain mandatory review, no Jev final approval, no skip and deterministic verification, with Sol High as the standard. Additional xHigh requires material uncertainty after High, material High-review disagreement, an unresolved root cause after investigation, unexplained deterministic behavior or an explicit project xHigh rule. Availability and precaution alone are insufficient. Active xHigh records retain reason and evidence; historical records are never backfilled. Astra requires demonstrated Sol insufficiency and explicit advance user approval after explaining the limitation, scope and cost. No automatic Astra or old-Sol fallback is introduced.

## Loading and actual execution

[.codex/config.toml](../.codex/config.toml) uses the official `model`, `model_reasoning_effort`, `agents.default_subagent_model` and `agents.default_subagent_reasoning_effort` keys. See the [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference) and [subagent reference](https://learn.chatgpt.com/docs/agent-configuration/subagents). Role choices use explicit supported spawn settings under [AGENTS.md](../AGENTS.md); no duplicate custom agents are installed. Existing role files may override initial defaults, so inspect actual execution metadata.

Project layers require a trusted project/worktree and a client that loads them. Existing chats are not retroactively switched by editing TOML. `fork_turns` controls context propagation, not model selection; a full-history fork inherits parent settings. The isolated workflow CLI adapters already pin their model and effort explicitly; their temporary directories do not obtain these project defaults. Unsupported requested settings stop execution rather than silently substituting models/efforts. Global config, personal instructions and automations are outside this change.

## Request-based pricing

[pricing_rates.json](../tools/workflow_eval/pricing_rates.json) records dated USD per-million text-token rates from [GPT-6.1 Sol's reference](https://developers.openai.com/api/docs/models/gpt-6.1-sol) and [prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching). This is an offline API equivalent, never actual Codex subscription or CLI billing. Old Sol rates are historical scenarios only and cannot select an execution model.

Optional review `pricing_requests` describe observed requests with safe opaque `request_id`, `usage_scope="request"`, response `model`, response `effective_service_tier`, `regional_processing`, `context_input_tokens` and `usage`. Batch also requires observed `processing_mode="batch"`. Usage requires nonnegative integer input, cache-read, cache-write and output counts; optional reasoning output is a subset of output. Raw responses, prompts, credentials and arbitrary nested fields are rejected before persistence. Input categories are disjoint; cache-write pricing replaces the uncached rate rather than adding a fee.

Price each request separately: 272000 input tokens is short context; 272001 applies the long-context multiplier across that request. Requested `auto` cannot prove effective tier, and cumulative session usage is not one request's context. Ledger IDs must be unique and model/usage totals must reconcile with the review. Both synthetic and real-task reports add `observed_text_token_api_equivalent` with known subtotals, coverage and missing reasons. Incomplete evidence leaves the total `null`; a known subset is never the total. The legacy `standard_short_context_sol_api_equivalent_usd` remains historical-only. Jev pricing stays unknown, so `all_provider_cost_usd` stays `null`.

## Verification and rollback

Run focused pricing/migration/review-boundary tests, offline routing, all Python discovery and `python3 tests/run_all.py`. Validate TOML with the installed client's strict-config mode and check runtime role metadata when available. Audit current-main diff, model IDs, no-skip/confidence invariants and checksums. Prior migration/review results do not validate a new diff.

This change contains no MQL5 product changes; a new MetaEditor compile or market test is unnecessary for the tooling-only diff. Python/offline mocks do not establish broker, Strategy Tester or live provider behavior. Existing deterministic gates remain required; report native blocks and unexecuted checks explicitly. Live Jev smoke checks use minimal synthetic data under the existing skill. Native Windows JEVGrep is unsupported; do not call it a successful live check.

Rollback the migration commit and regenerate checksums. Historical snapshots, previous migration branches, measurements, personal settings and EA runtime require no migration or restoration.
