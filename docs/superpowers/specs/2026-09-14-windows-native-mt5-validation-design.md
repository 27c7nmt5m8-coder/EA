# Windows Native MT5 Validation Design

Date: 2026-09-14
Status: Draft for user review
Repository: `27c7nmt5m8-coder/EA`
Target version: v2.44 validation infrastructure only; no trading-logic change

## 1. Goal

Add a Windows-based native validation lane that uses the user's always-on Windows PC, installed broker MetaTrader 5/MetaEditor, and a GitHub self-hosted runner to verify the real MQL5 build and Strategy Tester path.

The new lane complements the existing Ubuntu/offline mock CI; it does not replace it.

Success means:

- Native MetaEditor compilation is automated and treated as the final compile authority.
- A pull request can automatically run a one-month USDJPY/M1 Strategy Tester sanity backtest.
- A manual GitHub run can choose longer validation horizons such as 3 months, 1 year, or 2–3 years.
- Compile logs, tester logs, reports, and a machine-readable summary are retained as GitHub artifacts.
- No existing entry logic, scoring, SL/TP, lot sizing, portfolio risk, order handling, or AI protocol is changed.
- Failures in native validation block a validation result but do not alter or trade from the EA.

## 2. Existing State

The repository currently has an Ubuntu GitHub Actions workflow that runs `python tests/run_all.py` with the C++/MT5 mock, JSON regression, static source audit, and statistics checks. This remains the fast offline gate.

The repository development policy already requires native MetaEditor compile results to be distinguished from mock/static checks and targets `0 errors / 0 warnings` on the native compiler.

## 3. Architecture Choice

### Recommended: dedicated self-hosted Windows runner in the logged-in Windows user session

The runner is started automatically after the MT5 Windows user logs in. It is not installed as a Windows service for the first version because MT5/MetaEditor, terminal data folders, broker login state, and Strategy Tester behavior are easier to keep deterministic inside the normal interactive user profile.

The PC is expected to remain powered on and logged in.

### Why not replace the Ubuntu CI

The Ubuntu CI is fast, isolated, and suitable for every push/PR. The Windows runner is a scarce machine tied to the user's broker terminal and historical data. Keeping them separate makes failures easier to classify:

- Ubuntu lane failure = mock/static/test regression.
- Windows compile failure = native MQL5 compile problem.
- Windows tester failure = terminal, data, broker/tester configuration, or EA runtime problem.

## 4. Trigger Model

Two paths are supported.

### 4.1 Automatic PR validation

On pull-request creation/update, native validation runs only when the PR head belongs to the same repository and is created by the repository owner/approved trusted actor. Fork PRs must never execute arbitrary code on the user's self-hosted PC.

Automatic PR scope:

1. checkout the PR revision;
2. synchronize the 13 runtime source files into an isolated MT5 validation workspace;
3. native compile with MetaEditor;
4. require 0 compile errors and 0 compile warnings;
5. run USDJPY / M1 / one-month Strategy Tester sanity test;
6. collect report, tester journal/log, compile log, and summary artifact.

The one-month range is rolling and resolved at run time from a deterministic end date. For reproducibility, the workflow records the exact `FromDate` and `ToDate` in the artifact summary.

### 4.2 Manual long-run validation

A `workflow_dispatch` path allows the user to choose a profile such as:

- 1 month
- 3 months
- 1 year
- 2 years
- 3 years

The first version keeps the same USDJPY/M1 baseline. Additional symbols such as EURUSD, EURJPY, and XAUUSD are future extensions, not part of the initial implementation.

## 5. Native Compile Flow

The workflow uses the installed broker `metaeditor64.exe` with command-line compilation and a compile log. MetaEditor supports command-line compilation with `/compile:` and `/log`.

The exact executable paths are machine configuration, not committed secrets. They are supplied through runner environment variables or a local machine configuration file outside the repository, for example:

- `MT5_METAEDITOR_PATH`
- `MT5_TERMINAL_PATH`
- `MT5_DATA_PATH`
- `MT5_VALIDATION_WORKDIR`

The repository workflow validates these paths before doing any destructive copy or launch.

The compile target is `MTFAutoTrader_3Mode_AI_v2_44.mq5`. The AI Worker is also compiled so the native gate covers both shipped `.mq5` entry points.

The workflow parser fails the job if either entry point has any compile error or warning. The raw native compiler log remains attached as an artifact.

## 6. Strategy Tester Flow

After a successful native compile, the workflow creates a temporary tester `.ini` in the validation work directory and launches the broker terminal with `/config:<path>`.

The initial automatic profile is:

- Expert: `MTFAutoTrader_3Mode_AI_v2_44.ex5`
- Symbol: USDJPY
- Period: M1
- ExecutionMode: AUTO
- OpenAI: disabled
- ScanMode: CURRENT_SYMBOL
- Optimization: disabled
- Test duration: 1 month
- `ShutdownTerminal=1` or equivalent controlled termination behavior

Other EA inputs use a committed baseline `.set` file or generated tester parameters whose source is version-controlled. The implementation must not silently change strategy parameters to force trades.

The automation waits for terminal completion with a hard timeout. A hung terminal/tester is terminated only after logs are copied to a failure artifact.

## 7. Backtest Result Policy

For the first version, the one-month PR test is a sanity/runtime gate, not a profitability optimization gate.

Required successful-run conditions:

- terminal/tester process exits normally;
- tester report is generated;
- report is parseable;
- no initialization/runtime fatal error is present;
- requested symbol/timeframe/date range match the configuration;
- report metrics are extracted.

The summary records at least:

- trades/deals
- total net profit
- Profit Factor
- Expected Payoff
- maximum drawdown
- win rate
- average profit
- average loss
- maximum consecutive losses, if exposed by the report

A trade count of zero is reported explicitly and may be configured as a failure for the sanity profile once the current zero-trade bug is resolved. During the diagnostic phase it should remain distinguishable from infrastructure failure.

Profitability thresholds such as `PF >= 1.3` are deliberately not used as merge gates in v1 because that would turn infrastructure validation into strategy optimization and could encourage overfitting.

## 8. Artifacts and Traceability

Each Windows run uploads a uniquely named artifact containing:

- native compile log for main EA;
- native compile log for AI Worker;
- tester configuration used;
- `.set` file or exact parameter snapshot;
- Strategy Tester report;
- tester/terminal journal excerpts relevant to the run;
- machine-readable JSON summary;
- Git commit SHA;
- runner label/name;
- MT5/MetaEditor build number when detectable;
- exact test dates;
- symbol/timeframe/model/account-test parameters that can be safely recorded.

No API key, broker password, account secret, GitHub runner registration token, or other credential is uploaded.

## 9. Security Model

This repository is public, so the self-hosted runner must be treated as a sensitive local machine.

The Windows workflow must not execute for arbitrary fork pull requests. Initial implementation should require all of the following for automatic PR native validation:

- PR head repository equals `27c7nmt5m8-coder/EA`;
- actor is the repository owner or an explicit allowlisted trusted actor;
- job targets a dedicated self-hosted label such as `mt5-native`;
- workflow has minimum GitHub permissions (`contents: read`; artifact permissions only as needed).

The runner should have no broker withdrawal capability and no API keys in the repository. The test terminal should preferably use a demo account dedicated to CI. Live trading should be disabled in the validation terminal profile.

GitHub runner registration tokens are entered locally during setup and never committed.

## 10. Isolation From Daily MT5 Use

The safest first version uses a separate MT5 validation installation/profile or dedicated data directory from the user's normal manual/live terminal.

This prevents an automated `/config` launch, tester shutdown, data synchronization, or compiled EX5 replacement from disturbing a terminal used for discretionary or live trading.

If only one broker MT5 installation is available, implementation must create a dedicated validation copy/data directory before automated testing rather than controlling the user's normal live terminal directly.

## 11. Repository Components To Add

Expected implementation files, subject to the implementation plan:

- `.github/workflows/windows-native-validation.yml`
- `tools/windows/Invoke-MT5NativeValidation.ps1`
- `tools/windows/Compile-MQL5.ps1` or equivalent helper module
- `tools/windows/Run-MT5Tester.ps1` or equivalent helper module
- `tools/windows/Parse-MT5Report.py` or PowerShell parser
- `validation/mt5/profiles/usdjpy_m1_sanity.set`
- `validation/mt5/README_JA.md`
- tests for configuration generation/report parsing that can run on Ubuntu without MT5 where practical

A small number of scripts is preferred over a large framework. Exact file split can be reduced during implementation if one focused PowerShell script is clearer and easier to test.

## 12. Error Handling

Failures are categorized so the user and ChatGPT can act on the right layer:

- `RUNNER_CONFIG_ERROR`: missing/invalid local path or runner setup.
- `NATIVE_COMPILE_ERROR`: MetaEditor reports errors.
- `NATIVE_COMPILE_WARNING`: MetaEditor reports warnings; treated as failure by policy.
- `TESTER_START_ERROR`: terminal did not launch/configure.
- `TESTER_TIMEOUT`: terminal/tester did not finish within configured timeout.
- `TESTER_RUNTIME_ERROR`: tester/EA fatal initialization/runtime error.
- `REPORT_MISSING` / `REPORT_PARSE_ERROR`: output generation/parse failure.
- `ZERO_TRADES`: tester completed but no trades; diagnostic signal, not initially conflated with infrastructure failure.

The generated summary JSON carries the category, message, and paths to relevant artifact files.

## 13. Testing Strategy

Implementation must preserve the existing `python3 tests/run_all.py` lane.

New infrastructure tests should include at minimum:

- tester `.ini` generation with deterministic dates/inputs;
- validation of required environment paths;
- compile-log parser fixtures: 0/0, errors, warnings;
- tester report parser fixtures including zero trades and nonzero trades;
- secret-redaction/artifact allowlist checks;
- trigger/security condition review so fork PRs cannot reach the self-hosted runner;
- dry-run mode that validates configuration without launching MetaEditor/MT5.

Native behavior remains `未実測` until the Windows PC is actually registered and a real native run completes.

## 14. Installation / Operator Flow

The eventual setup sequence on the Windows PC is:

1. create a dedicated local folder for the GitHub runner;
2. register the runner to `27c7nmt5m8-coder/EA` with dedicated labels such as `self-hosted`, `Windows`, `X64`, `mt5-native`;
3. configure it to start after Windows user login;
4. create a separate MT5 validation installation/data folder;
5. log the validation terminal into the broker demo environment and download required USDJPY histories;
6. define local environment variables for terminal/metaeditor/data/work paths;
7. run repository dry-run validation;
8. run native compile only;
9. run one-month USDJPY/M1 tester manually via `workflow_dispatch`;
10. only after that succeeds, enable/use the automatic PR native-validation gate.

## 15. Out of Scope For Initial Version

- live account order execution;
- real-money validation;
- AI/OpenAI API testing;
- automatic parameter optimization;
- multi-symbol matrix on every PR;
- profitability-based automatic parameter tuning;
- cloud agents/MQL5 Cloud Network;
- replacing the existing Ubuntu CI;
- changing EA trading logic to make a test pass.

## 16. Rollout

Phase 1: repository scripts/workflow plus dry-run tests, no self-hosted execution assumed.

Phase 2: user registers the Windows runner and supplies local MT5 paths.

Phase 3: native compile succeeds at `0 errors / 0 warnings`.

Phase 4: manual one-month USDJPY/M1 tester run succeeds and artifacts are reviewed.

Phase 5: automatic same-repository PR native validation is enabled/treated as the normal native gate.

Longer 3-month/1-year/2–3-year tests remain manual and are used for deeper validation before important releases.
