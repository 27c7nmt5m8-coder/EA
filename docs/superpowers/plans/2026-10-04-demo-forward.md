# Isolated Demo Forward Validation Implementation Plan

> **For agentic workers:** Execute the preparation tasks inline with `superpowers:executing-plans`. The explicit Human Gate below applies before any Forward connection or execution.

**Goal:** Freeze a reproducible 500k Demo-only candidate and a bounded observation plan; do not start Forward or adopt the scheduler.

**Architecture:** Generate from canonical `src/`, never from a Tester bundle. Preserve every product byte after removing named observer substitutions and reversing only the operation cap. A separate read-only observer buffers lifecycle records, aggregates frequent events, and writes locally at bounded intervals; observations never authorize or suppress an order.

**Tech Stack:** Existing Python standard library, MQL5, installed MetaEditor, existing exact-head authoritative CI. No dependencies, API, DLL, service, security or process placement changes.

**Spec:** User attachment `Isolated Demo Forward Validation Planning`; source contract in `AGENTS.md`, prior bounded evidence at `.validation/natural_final_bounded_20261004/REPORT_JA.md`.

## Global Constraints

- No Forward startup, account connection, terminal/profile installation, real orders, product adoption, release, main merge, tuning, MC/RNG/Risk/Safety changes.
- Allowed scheduler difference: `operations<20000` to `operations<500000` only; existing deadline, Timer, cursor, event order, expiry, invalidation and force paths remain.
- Canonical EA/Worker/13 files and original set are immutable. Only generated Demo candidate plus new preparation tooling/tests/docs.
- `ACCOUNT_TRADE_MODE_DEMO` required before init and executable callbacks; refuse disconnected initialization and wrong-account callbacks; preserve the product disconnect-handling paths after successful initialization. Account identity remains in RAM, never exports.
- AUTO/OpenAI false, no Worker attachment/WebRequest/API key/DLL. Worker is compiled unchanged as a delivery integrity check only.
- Existing N4 frozen High diagnostic set is the input candidate, with SHA verification. No new Spread/Score/Risk values or FX/XAU product configuration proposal.
- Arrival time/queue depth cannot be manufactured from handler entry or quote timestamp; explicitly UNKNOWN.

## Review Focus

1. Switching to a real/different account must not run candidate trading handlers.
2. Observer overflow/I/O failure must be visible and cannot alter existing risk/order/position decisions. A failed export becomes sticky; no automatic retry of a partly written file.
3. A completed/immediate/cancelled MC cycle must not be misclassified as heavy or synthetic.
4. An expired candidate due to position/receipt/score must not be attributed solely to MC wait.
5. Generated source cannot retain Tester observers, history resets, synthetic requests, replay or synthetic shadow engines.

## Task 1: Pure generation and observation boundary

**Files:** create `tools/build_forward_mc.py`, `tools/ForwardMCObserver.mqh`, `tests/test_forward_mc.py`.
**Interface:** `build(output: Path, source: Path=SOURCE) -> dict` returns source hashes, provenance/classification and projection proof; refuses existing/in-src destinations. `restore(name: str, data: bytes) -> bytes` removes named substitutions exactly. No install/launch function.

- [ ] Add failing generation tests: new outside-src output, exact restored 13-file bytes, collision/mutated-source rejection, forbidden Tester engine exclusion, immutable input set copy.
- [ ] Implement a 500k clean candidate, Demo identity guard and bounded observer. Lifecycle hooks surround existing functions without changing their body/decision/order. Frequent Tick/Position/callback timings aggregate in RAM; candidate wait records are stage-qualified observed state only.
- [ ] Verify focused tests; native compile candidate and unchanged Worker 0/0. Preserve logs locally and record fresh EX5 hashes/compiler source/engine hashes. Do not install into MT5 Experts or start it.

## Task 2: Frozen plan/metrics and candidate validation

**Files:** this plan, `verification/forward_plan_20261004/CONTRACT_JA.md`; local ignored build/proof/selected set.

- [ ] Bind source commit, generator/header hashes, 13 canonical hashes, generated hashes, EX5 hashes and exact N4 set hash. Classify all included/excluded paths.
- [ ] Use the July two-week fixed500k baseline frequencies as descriptive coverage guidance, not profit optimization. State insufficient-history and win-rate gate may prevent heavy naturally; never inject history/force.
- [ ] Focused regression, Python discovery, native compile, numeric/static/product scope, secret scan and independent review. If a new commit is made, normal diagnostic branch push and exact-head CI validation only; no PR/main merge/release.
- [ ] Final stop before Forward. Do not treat compile or build hashes as runtime evidence.

## Proposed Forward protocol (not executed)

### Environment and identity

New dedicated Demo account and dedicated MT5 instance/data directory/profile, user-operated setup. Broker assumption: HFM Demo on the same installed 6230 engine family; USD balance near the offline USD100000 and leverage 1:1000 only if broker offers it. A different engine/server/cost/account type is recorded as an environment change, not silently deemed identical.

One controller on USDJPY M1, selected USDJPY/EURUSD/EURJPY/XAUUSD matching exact broker names. Existing selected N4 set stays byte-identical. Do not activate 20k and 500k on one account. Optional future control needs separate Demo account/instance/profile and independently approved scope. Terminal-local files are isolated but FILE_COMMON and product account-scoped state are shared on a Windows user; a distinct account and no Worker prevent accidental reuse. Never copy prior product safety globals/history or unrelated account files; never delete safety locks.

Before each start: Demo flag + approved account shown locally, isolated data path, exact EX5/set/source/engine hashes, no existing/pending/manual trades, no other EA/controller, no worker, appropriate history synchronization, correct Symbol specs and timezone, no real-account login files, no auto reconnect to another account. Codex must not select credentials or log in automatically.

Candidate-only lifecycle guard: one fresh program load per observer run. A repeated `FOInit` within the same RAM context refuses initialization; it cannot silently bind another Demo or reuse prior observations. Account/parameter/chart changes require stop-review, flat/reconciled state, and a user-operated fresh detach/load or terminal restart. Whether a native MT5 reinitialization retains globals is checked at Stage 0, never assumed. A fresh program load still requires manual confirmation of the approved Demo account; the RAM self-binding guard alone cannot recognize the user's account approval.

### Stage 0: Observer-only sanity

User leaves terminal Algo Trading OFF before attaching the candidate. Keep original `EnableAutoTrading` input unchanged; terminal permission gates existing order logic. Check clocks, init/symbol/MC state, buffer/export/header/sequence, Tick/Bar/Timer progression, Demo guard, shutdown/reinit and account isolation. No manual signal injection or sample seeding. At least one normal open-market session and a restart boundary; stopping earlier on any failure. Existing position management/order latency remain NOT_OBSERVED because the account starts flat and trading permission is OFF.

### Stage 1: Short Demo orders

Separate explicit approval enables terminal Algo Trading for this Demo candidate only. Observe the first natural request/result/deal and complete position lifecycle; do not generate manual orders to hit a quota. Proposed bounded window: up to five open-market days. If no natural order/close occurs, stage is INCOMPLETE, not PASS; no tuning. Record SL/TP/BE/trailing/close paths only when they actually occur. Never assert every management branch is covered by a closed trade.

### Stage 2: Extended multi-session Demo

Proposed minimum observation: ten open-market days spanning two weekly cycles, Asia/London/New York and rollover. Maximum initial window: twenty open-market days; extensions require a new decision, not automatic search.

Coverage proposal: at least 30 eligible closed-history samples per Symbol to reach the unchanged `MonteCarloMinimumSamples=30`; this is a state-coverage requirement, not a performance target. July N4 fixed500k had USDJPY31/EURUSD30/EURJPY52/XAUUSD91 accepted trades in ten market days, descriptively 3.1/3.0/5.2/9.1 per day. Demo costs/quotes/series can change these rates. Eligible closed samples are not equivalent to orders/deals; aggregate partial deals by the existing product position/history semantics. No win-rate threshold changes: low win rate may correctly yield a completed immediate decision and zero bootstrap.

At least one real heavy completion per naturally eligible Symbol and completion/restart/expiry visibility are coverage goals. Distinct ACTUAL overlaps 2/3/4 remain separate OBSERVED_COMPLETE/PARTIAL/UNOBSERVED/INVALID. Rare 3/4 overlap not seen within the bound is UNOBSERVED, not a reason to force history or extend indefinitely. Record incomplete coverage and obtain a final review; calendar time or profit alone cannot establish acceptance.

### Monitoring, privacy and time interpretation

Lifecycle request/start/end/ready/permitted plus actual active Symbol count, input/history state evidence, reason-coded invalidation and completion; no SHADOW, replay or bootstrap fabricated in Forward. Timer/callback/Tick and Symbol Position durations aggregate count/sum/max/histogram. Retain bounded lifecycle/transition/outlier records in RAM, flush at most once per 60 wall seconds and on normal shutdown. Buffer/file failures become sticky observer UNKNOWN with visible warning; the observer never changes product safety state or disables position management.

MC wait/expiry: MC_PREFLIGHT_WAIT_BAR / MC_WAIT_WINDOW_END observe bar windows before Signal qualification. They are never counted as eligible opportunities. Eligible-opportunity expiry is UNKNOWN without independent qualified evidence. Actual formed candidates retain deduplicated source sequence/bar identity; no counterfactual Signal computation and no invented opportunity loss.

Position arrival timestamp = UNKNOWN (method has no independent queued arrival event). All calls have cumulative duration counts/histograms; first/60-wall-second/outlier samples retain processing start/end + simultaneous MC count. Unsampled timestamps and exposure presence are UNKNOWN. Order request/result elapsed is an EA synchronous-call span, not exclusive broker transit time. Trade transactions get local ordinal IDs, not raw account/order/deal IDs. Market-closed return code is not a critical runtime failure. Tick quote time/server/UTC/monotonic clocks stay distinct; quote→handler age is not actual queue wait. Cross-Symbol quote observations are not all input ticks.

Raw terminal Journal/trade CSV/JSON may contain account identifiers under unchanged product contracts: keep in private terminal storage, never commit/upload raw. Publish only an allowlisted export scanned against known secrets/account values, with account alias assigned offline; no reversible masking or raw tickets. No API/credentials in inputs/artifacts. ETW/UAC is not needed for this phase and not started.

### Acceptance / stop / recovery

Hard zero tolerance: MC numerical/state corruption, RNG/DD95/Risk/decision mismatch for same inputs, Risk/Safety violation, real/wrong-account operation, semantics drift, critical runtime failures. Existing offline callbacks (NORMAL p95 about4–5ms, CPU contention about6–20ms and observed max up to37ms) are descriptive reference ranges, not arbitrary hard limits or a promise of live latency. Report full distributions/outliers and event timeline for any position/order gap.

Require continuous completed MC when eligible, no unexplained starvation/expiry increase, no unexplained Tick/Bar/Timer/position/order gaps, correctly enforced Risk/Safety, and nonmaterial observer influence. No numeric max-latency acceptance threshold is invented; visible long delays are investigated against quote validity, opportunity lifetime, real position state and expected management cadence. Minimal-observer comparison is a separate same-source/different-observation diagnostic comparison, never two competing EAs on one account.

Immediate stop-review: wrong environment, corrupted result, Risk/Safety violation, persistent starvation, unexplained missed position management, repeated critical runtime/order failures, observer overflow/intrusion or semantics drift. Do not call `ExpertRemove()` from the observer or delete locks to stop errors. Operator blocks new automated orders in the dedicated Demo terminal, records any remaining positions/pending requests and broker SL/TP, manually resolves Demo exposure, and only then detaches/restarts under approval. Turning Algo Trading OFF also disables EA modifications; static broker SL/TP remain, but BE/trailing is not guaranteed. Preserve all product reconciliation/history/safety state. No auto retry or baseline switch while positions/pending outcomes are unresolved.

## Human Gate

No account connection, MT5 profile creation, EA attachment, automated orders, Forward or Live is performed by preparation tooling. Final report distinguishes candidate build/tests from runtime NOT_RUN. User approval must identify the Demo environment/profile, approved account (locally, no identifier in report), Symbols, frozen candidate SHA/set/build hashes, Stage 0 scope/monitoring and later Stage 1 orders. Stage 0 failure cannot advance to Stage 1.

## Preparation rulings / execution ledger

- Ruling: generate from all 13 canonical files rather than stripping a Tester bundle — exact reverse projection protects product provenance; hook behavior still requires independent review and Stage 0 nonintrusion checks.
- Ruling: use the previously frozen N4 High diagnostic input unchanged — it supports four-Symbol observation, not a product Spread recommendation. Broker names must match literally; suffix differences require a new plan.
- Ruling: preserve disconnected product handling after Demo initialization — a blanket disconnected callback block could suppress protective management. Account/environment mismatch blocks trading callbacks and deinit releases only already-bound owned locks/handles, without new-account history/journal activity.
- Ruling: wait-bar observations are not qualified opportunities — true MC-caused eligible expiry remains UNKNOWN; no counterfactual Signal evaluation is inserted.
- Ruling: ordinary Position spans are sampled (first / 60 wall seconds / outlier), all calls aggregate — limits observer load; unsampled event latency and exposure-specific latency remain UNKNOWN.
- Ruling: histograms provide percentile bucket bounds only — exact p95/p99 cannot be claimed. File-export time is included in Timer duration and separately aggregated.
- Ruling: compile/test preparation never starts an MT5 terminal — runtime nonintrusion, broker behavior, restart recovery and Demo execution stay NOT_RUN until Human Gate.
- Independent review identified cleanup, consecutive wait-window, Position sampling, request-symbol fallback and invalid overlap-evidence issues. Corrections and regression coverage are required before commit.
