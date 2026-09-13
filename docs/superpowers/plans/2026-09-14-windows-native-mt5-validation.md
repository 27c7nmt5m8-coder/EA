# Windows Native MT5 Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a secure Windows self-hosted GitHub Actions lane that natively compiles both shipped MQL5 entry points with MetaEditor and runs a one-month USDJPY/M1 Strategy Tester sanity backtest, while supporting manual 1m/3m/1y/2y/3y runs.

**Architecture:** Keep the existing Ubuntu CI unchanged as the fast mock/static gate. A new default-branch-controlled workflow is triggered after successful `CI` pull-request runs, authorizes only same-repository owner-authored heads, then dispatches the exact trusted SHA to a dedicated `self-hosted, Windows, X64, mt5-native` runner. Repository code provides deterministic configuration/report parsing in Python and Windows orchestration in PowerShell; machine-specific MT5 paths and credentials stay local to the runner.

**Tech Stack:** GitHub Actions YAML, PowerShell 7/Windows PowerShell-compatible scripting, Python 3 stdlib, MetaEditor 5 command line, MetaTrader 5 `/config:` Strategy Tester launch.

**Spec:** `docs/superpowers/specs/2026-09-14-windows-native-mt5-validation-design.md`

## Global Constraints

- Do not change `src/` trading logic, entry conditions, scores, SL/TP, lot sizing, portfolio risk, order handling, saved-state semantics, AI protocol, or version `2.44`.
- Existing `.github/workflows/ci.yml` remains the normal Ubuntu/offline gate and must continue to run `python3 tests/run_all.py`.
- Native MetaEditor success requires exactly `0 errors / 0 warnings`; mock/C++ success must never be reported as native compile success.
- Automatic Windows execution must never run arbitrary fork PR code on the self-hosted PC.
- Automatic PR profile is USDJPY / M1 / one month / AUTO / OpenAI disabled / CURRENT_SYMBOL / optimization disabled.
- Manual profiles are exactly `1m`, `3m`, `1y`, `2y`, `3y` for the initial version.
- Zero trades is a distinct diagnostic result, not an infrastructure failure in the initial rollout.
- No profitability threshold such as PF >= 1.3 is a merge gate in this infrastructure version.
- No API key, broker password, account secret, or runner registration token may enter the repository or uploaded artifacts.
- Real native compile/test status remains `未実測` until the user's Windows runner actually completes the corresponding step.

## File Structure

- Create `.github/workflows/windows-native-validation.yml`: trusted workflow-run/manual dispatch gate and artifact upload.
- Create `tools/windows/mt5_validation.py`: deterministic date ranges, compile-log parsing, tester INI rendering, HTML report parsing, summary JSON helpers/CLI.
- Create `tools/windows/Invoke-MT5NativeValidation.ps1`: runner path validation, source synchronization, MetaEditor compile, tester launch/timeout, log collection and Python helper calls.
- Create `validation/mt5/profiles/usdjpy_m1_sanity.set`: explicit critical tester inputs only; no optimization ranges and no secrets.
- Create `validation/mt5/README_JA.md`: Windows runner/MT5 validation setup and operator instructions.
- Create `tests/verify_windows_native_validation.py`: offline tests for date/config/log/report/security/artifact behavior.
- Create `tests/fixtures/windows_validation/*`: synthetic compile/report fixtures only; no real account/log data.
- Modify `tests/run_all.py`: append the new offline infrastructure verification.
- Modify `README_JA.md`, `VALIDATION_JA.md`, `CHANGELOG.md`: document the added validation lane without claiming unmeasured native success.
- Modify `SHA256SUMS.txt`: regenerate hashes for all tracked files except itself after implementation is complete.

---

### Task 1: Offline validation core and fixtures

**Files:**
- Create: `tools/windows/mt5_validation.py`
- Create: `tests/verify_windows_native_validation.py`
- Create: `tests/fixtures/windows_validation/compile_ok.log`
- Create: `tests/fixtures/windows_validation/compile_warning.log`
- Create: `tests/fixtures/windows_validation/compile_error.log`
- Create: `tests/fixtures/windows_validation/report_zero_trades.htm`
- Create: `tests/fixtures/windows_validation/report_with_trades.htm`
- Modify: `tests/run_all.py`

**Interfaces:**
- Produces: `resolve_date_range(profile: str, end_date: date) -> tuple[date,date]`
- Produces: `parse_compile_log(text: str) -> dict`
- Produces: `render_tester_ini(...) -> str`
- Produces: `parse_tester_report(path: Path) -> dict`
- Produces CLI commands `prepare`, `check-compile`, `parse-report` used by Task 3.

- [ ] **Step 1: Write failing offline tests for exact profile date ranges**

Use a fixed end date so CI is deterministic:

```python
assert v.resolve_date_range('1m', date(2026, 9, 1)) == (date(2026, 8, 1), date(2026, 9, 1))
assert v.resolve_date_range('3m', date(2026, 9, 1)) == (date(2026, 6, 1), date(2026, 9, 1))
assert v.resolve_date_range('1y', date(2026, 9, 1)) == (date(2025, 9, 1), date(2026, 9, 1))
assert v.resolve_date_range('2y', date(2026, 9, 1)) == (date(2024, 9, 1), date(2026, 9, 1))
assert v.resolve_date_range('3y', date(2026, 9, 1)) == (date(2023, 9, 1), date(2026, 9, 1))
```

Also test month-end clamping with `2026-03-31 -> 2026-02-28` through the helper used internally.

- [ ] **Step 2: Run the new test and verify RED**

Run:

```bash
python3 tests/verify_windows_native_validation.py
```

Expected: import/file/function failure because `tools/windows/mt5_validation.py` does not exist yet.

- [ ] **Step 3: Implement deterministic date profile resolution**

Use only stdlib `datetime`/`calendar`; accepted profiles are a closed map:

```python
PROFILE_MONTHS = {'1m': 1, '3m': 3, '1y': 12, '2y': 24, '3y': 36}

def subtract_months(value, months):
    target = value.year * 12 + value.month - 1 - months
    year, month0 = divmod(target, 12)
    month = month0 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)

def resolve_date_range(profile, end_date):
    if profile not in PROFILE_MONTHS:
        raise ValueError('unsupported profile: ' + profile)
    return subtract_months(end_date, PROFILE_MONTHS[profile]), end_date
```

- [ ] **Step 4: Add compile-log parser fixtures/tests**

Fixtures must cover:

```text
Result: 0 errors, 0 warnings, 842 msec elapsed
Result: 0 errors, 1 warnings, 900 msec elapsed
Result: 2 errors, 0 warnings, 450 msec elapsed
```

Expected parser results:

```python
{'errors': 0, 'warnings': 0, 'status': 'OK'}
{'errors': 0, 'warnings': 1, 'status': 'NATIVE_COMPILE_WARNING'}
{'errors': 2, 'warnings': 0, 'status': 'NATIVE_COMPILE_ERROR'}
```

The parser must fail closed with `ValueError('compile summary not found')` when no summary exists.

- [ ] **Step 5: Implement compile-log parsing**

Use a case-insensitive regex that chooses the last summary occurrence:

```python
COMPILE_RE = re.compile(r'(\d+)\s+errors?\s*,\s*(\d+)\s+warnings?', re.I)
```

Warnings are not success.

- [ ] **Step 6: Add tester INI generation tests**

Assert rendered INI includes exactly the requested baseline and report path:

```text
[Tester]
Expert=MTFAutoTraderNativeValidation\MTFAutoTrader_3Mode_AI_v2_44.ex5
ExpertParameters=usdjpy_m1_sanity.set
Symbol=USDJPY
Period=M1
Model=4
Optimization=0
FromDate=2026.08.01
ToDate=2026.09.01
Report=<absolute run output>\strategy-tester.htm
ReplaceReport=1
ShutdownTerminal=1
Visual=0
```

Also assert no `Login=`, `Password=`, `OpenAIAPIKey`, GitHub token, or URL credential string can appear in generated config.

- [ ] **Step 7: Implement `render_tester_ini()`**

Function signature:

```python
def render_tester_ini(*, expert, parameter_file, symbol, period, model,
                      from_date, to_date, report_path, deposit='100000',
                      currency='USD', leverage='1:1000') -> str:
```

Keep `Optimization=0`, `Visual=0`, `ReplaceReport=1`, and `ShutdownTerminal=1` hard-coded for this lane.

- [ ] **Step 8: Add synthetic report parser tests**

`report_zero_trades.htm` must represent a completed USDJPY/M1 test with zero trades. `report_with_trades.htm` must contain a deterministic example such as 20 trades, 12 wins, 8 losses, net profit 1250.50, PF 1.42, expected payoff 62.525, max drawdown 4.8%, average profit 210, average loss -158, max consecutive losses 3.

Assert zero-trade report returns `status='ZERO_TRADES'` while nonzero report returns `status='OK'` and numeric metrics.

- [ ] **Step 9: Implement localized HTML cell parsing without third-party packages**

Use `html.parser.HTMLParser` to collect table-cell text and normalize NBSP/whitespace. Label aliases must include English plus the Japanese labels observed in MT5 reports for the required metrics. Missing required structural fields (`Symbol`, `Period`, total trades/deals) raises `ValueError`; optional performance fields may be `None` and are recorded as unavailable rather than invented.

- [ ] **Step 10: Add CLI entry points and machine-readable output**

CLI shape:

```text
python tools/windows/mt5_validation.py prepare --profile 1m --end-date 2026-09-01 --report ... --out tester.ini
python tools/windows/mt5_validation.py check-compile --log compile-main.log --json compile-main.json
python tools/windows/mt5_validation.py parse-report --report strategy-tester.htm --json summary.json
```

Every JSON output must use UTF-8, sorted keys, indentation, and no secret environment dump.

- [ ] **Step 11: Add the new verification script to the shipped offline gate**

Change the list in `tests/run_all.py` to append `verify_windows_native_validation.py`; do not remove or reorder existing gates unnecessarily.

- [ ] **Step 12: Run focused and full offline tests**

Run:

```bash
python3 tests/verify_windows_native_validation.py
python3 tests/run_all.py
```

Expected: new test passes and all existing checks still pass.

- [ ] **Step 13: Commit Task 1**

```bash
git add tools/windows/mt5_validation.py tests/verify_windows_native_validation.py tests/fixtures/windows_validation tests/run_all.py
git commit -m "test: add offline MT5 native validation helpers"
```

---

### Task 2: Explicit sanity-test input profile

**Files:**
- Create: `validation/mt5/profiles/usdjpy_m1_sanity.set`
- Modify: `tests/verify_windows_native_validation.py`

**Interfaces:**
- Produces tester parameter file consumed by Task 3 via `ExpertParameters=usdjpy_m1_sanity.set`.

- [ ] **Step 1: Add failing tests for critical input values**

The test must parse the committed file and require these exact entries:

```text
ExecutionMode=0
EnableOpenAI=false
EnableAutoTrading=true
AccountMode=0
ScanMode=0
MinimumSignalScore=70.0
MinimumWeightedAgreement=55.0
RiskMode=2
```

Also assert the source enums still map `EXECUTION_AUTO=0`, `NORMAL=0`, `CURRENT_SYMBOL=0`, `RISK_COMBINED=2` and that the source defaults for `MinimumSignalScore` and `MinimumWeightedAgreement` remain 70/55. This catches accidental mismatch between the test profile and v2.44 semantics.

- [ ] **Step 2: Verify RED before creating the profile**

Run:

```bash
python3 tests/verify_windows_native_validation.py
```

Expected: missing profile file.

- [ ] **Step 3: Create the minimal non-secret `.set` profile**

Use MT5 tester parameter syntax with only the critical overrides required to make the lane deterministic. Do not add optimization ranges or tune strategy values.

- [ ] **Step 4: Run the focused test and full suite**

```bash
python3 tests/verify_windows_native_validation.py
python3 tests/run_all.py
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add validation/mt5/profiles/usdjpy_m1_sanity.set tests/verify_windows_native_validation.py
git commit -m "test: pin MT5 sanity profile inputs"
```

---

### Task 3: Windows orchestration script with dry-run, compile, tester and artifacts

**Files:**
- Create: `tools/windows/Invoke-MT5NativeValidation.ps1`
- Modify: `tests/verify_windows_native_validation.py`

**Interfaces:**
- Consumes: Task 1 CLI helpers and Task 2 `.set` file.
- Consumes local environment variables: `MT5_METAEDITOR_PATH`, `MT5_TERMINAL_PATH`, `MT5_DATA_PATH`, `MT5_VALIDATION_WORKDIR`.
- Produces an artifact directory containing `compile-main.log`, `compile-worker.log`, `tester.ini`, `usdjpy_m1_sanity.set`, `strategy-tester.htm`, `summary.json`, and copied relevant logs when available.
- PowerShell parameters: `-Profile 1m|3m|1y|2y|3y`, `-DryRun`, `-CompileOnly`, `-EndDate yyyy-MM-dd`, `-TimeoutMinutes <int>`.

- [ ] **Step 1: Add static/offline tests for script safety contract**

Assert script text contains:

```text
MT5_METAEDITOR_PATH
MT5_TERMINAL_PATH
MT5_DATA_PATH
MT5_VALIDATION_WORKDIR
MTFAutoTraderNativeValidation
MTFAutoTrader_3Mode_AI_v2_44.mq5
MTFAutoTrader_AI_Worker.mq5
/config:
```

And assert it does not contain `Remove-Item` against the whole MT5 data folder, repository secrets, hard-coded user paths, live account numbers, or network upload commands.

- [ ] **Step 2: Implement environment/path validation and isolated run directories**

Required behavior:

```powershell
$required = @('MT5_METAEDITOR_PATH','MT5_TERMINAL_PATH','MT5_DATA_PATH','MT5_VALIDATION_WORKDIR')
foreach ($name in $required) {
    $value = [Environment]::GetEnvironmentVariable($name)
    if ([string]::IsNullOrWhiteSpace($value)) { throw "RUNNER_CONFIG_ERROR: missing $name" }
}
```

Validate MetaEditor/terminal are files; data/work paths are directories or can be safely created under configured roots. Each run uses a unique child directory based on `GITHUB_RUN_ID`/`GITHUB_RUN_ATTEMPT`, falling back to a UTC timestamp for local use.

- [ ] **Step 3: Implement dry-run before any process launch**

`-DryRun` must validate paths, resolve dates, confirm all 13 `src` files exist, confirm the `.set` profile passes presence checks, render `tester.ini`, write `summary.json` with `status='DRY_RUN_OK'`, and exit without starting MetaEditor or terminal.

- [ ] **Step 4: Implement source synchronization into the dedicated validation Expert folder**

Copy exactly the 13 runtime files from repository `src/` to:

```text
$MT5_DATA_PATH\MQL5\Experts\MTFAutoTraderNativeValidation\
```

Before copy, remove only files in that dedicated validation subfolder that match the 13 known runtime filenames; never clean parent `Experts` or unrelated EA folders.

Copy `usdjpy_m1_sanity.set` to:

```text
$MT5_DATA_PATH\MQL5\Profiles\Tester\usdjpy_m1_sanity.set
```

- [ ] **Step 5: Implement native compilation of both entry points**

Invoke MetaEditor separately for main and worker with absolute `/compile:` target and `/log:` path. After each process exits, call Task 1 `check-compile`; any nonzero errors becomes `NATIVE_COMPILE_ERROR`, any warning becomes `NATIVE_COMPILE_WARNING`, and the PowerShell step fails after preserving logs.

- [ ] **Step 6: Implement `-CompileOnly`**

After both native compiles pass, write summary `status='COMPILE_OK'`, include commit SHA/runner name and compile counts, and exit without launching MT5.

- [ ] **Step 7: Generate tester config and run terminal with hard timeout**

Use Task 1 `prepare` to render the exact test period. Launch:

```powershell
$proc = Start-Process -FilePath $terminalPath -ArgumentList "/config:`"$testerIni`"" -PassThru
```

Wait up to the configured timeout. On timeout, copy available tester/terminal logs to the run output, stop only the process started by this script, set `TESTER_TIMEOUT`, and fail.

- [ ] **Step 8: Validate report and classify zero trades**

After normal process exit, require the report file. Use Task 1 `parse-report`; missing report is `REPORT_MISSING`, parser failure is `REPORT_PARSE_ERROR`, initialization/fatal markers collected from run logs are `TESTER_RUNTIME_ERROR`. `ZERO_TRADES` remains a successful infrastructure completion with explicit diagnostic status during rollout.

- [ ] **Step 9: Enforce artifact allowlist**

Before final exit, enumerate the run output directory and reject unexpected sensitive filenames/extensions. Allowed outputs are generated logs/config/profile/report/JSON only. The script must never copy terminal credential/config files such as account databases, `origin.txt`, saved passwords, API key files, or whole MT5 directories.

- [ ] **Step 10: Run offline static tests**

```bash
python3 tests/verify_windows_native_validation.py
python3 tests/run_all.py
```

Native launch remains `未実測` at this task because the current environment is not the user's Windows MT5 PC.

- [ ] **Step 11: Commit Task 3**

```bash
git add tools/windows/Invoke-MT5NativeValidation.ps1 tests/verify_windows_native_validation.py
git commit -m "feat: add Windows MT5 native validation runner"
```

---

### Task 4: Secure GitHub Actions workflow

**Files:**
- Create: `.github/workflows/windows-native-validation.yml`
- Modify: `tests/verify_windows_native_validation.py`

**Interfaces:**
- Automatic trigger: `workflow_run` for workflow name `CI`, type `completed`.
- Manual trigger: `workflow_dispatch` with profile choice `1m/3m/1y/2y/3y` and optional compile-only/dry-run booleans.
- Self-hosted runner label: `mt5-native` in addition to `self-hosted`, `Windows`, `X64`.

- [ ] **Step 1: Add failing workflow-security assertions**

Test YAML text/parsed structure requires:

```yaml
on:
  workflow_run:
    workflows: [CI]
    types: [completed]
  workflow_dispatch:
```

The self-hosted job must depend on a GitHub-hosted `authorize` job and must not be scheduled directly from `pull_request`.

- [ ] **Step 2: Implement `authorize` on `ubuntu-latest`**

For `workflow_run`, approve only when all are true:

```text
conclusion == success
event == pull_request
head_repository.full_name == github.repository
actor.login == github.repository_owner
head_sha is a full 40-hex SHA
```

For manual dispatch, approve only `github.actor == github.repository_owner`. Output `approved`, exact `sha`, and selected profile. Do not execute checked-out PR code in this authorization job.

- [ ] **Step 3: Implement the self-hosted native job**

Job condition is `needs.authorize.outputs.approved == 'true'` and runner is:

```yaml
runs-on: [self-hosted, Windows, X64, mt5-native]
```

Checkout must use `ref: ${{ needs.authorize.outputs.sha }}` so the exact already-authorized head SHA is tested.

- [ ] **Step 4: Invoke PowerShell orchestration and always upload allowlisted artifacts**

Automatic workflow-run uses profile `1m`; manual uses selected profile. Upload only the per-run output directory returned by the script, with `if: always()` and finite retention. Do not upload `%APPDATA%`, MT5 data directories, runner directories, or environment dumps.

- [ ] **Step 5: Add concurrency to prevent simultaneous terminal control**

Use one native validation group per repository/runner, e.g.:

```yaml
concurrency:
  group: mt5-native-${{ github.repository }}
  cancel-in-progress: false
```

This serializes tester/MetaEditor control on the single PC.

- [ ] **Step 6: Run security/offline tests**

```bash
python3 tests/verify_windows_native_validation.py
python3 tests/run_all.py
```

Expected: fork/untrusted paths cannot satisfy the static authorization contract; existing CI remains untouched.

- [ ] **Step 7: Commit Task 4**

```bash
git add .github/workflows/windows-native-validation.yml tests/verify_windows_native_validation.py
git commit -m "ci: add trusted Windows MT5 native validation"
```

---

### Task 5: Windows operator setup documentation

**Files:**
- Create: `validation/mt5/README_JA.md`
- Modify: `README_JA.md`
- Modify: `VALIDATION_JA.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Gives the user the exact manual steps required before first real native run.

- [ ] **Step 1: Document dedicated validation terminal isolation**

Instructions must require a validation-only MT5 installation/data directory, preferably a writable copied installation launched for validation, and a demo account. Explicitly state not to point automation at a live/manual terminal used for trading.

- [ ] **Step 2: Document GitHub runner registration**

Guide the user to repository `Settings -> Actions -> Runners -> New self-hosted runner`, Windows/x64, execute GitHub's generated registration commands locally, add custom label `mt5-native`, and never paste the temporary runner registration token into chat/repository/docs.

For startup, use Windows Task Scheduler triggered `At log on` for the MT5 Windows user to launch `run.cmd` from the runner folder. Do not install the runner as a Windows service in v1.

- [ ] **Step 3: Document required local environment variables**

Example names only, not real account-specific values:

```text
MT5_METAEDITOR_PATH=C:\MT5-CI\metaeditor64.exe
MT5_TERMINAL_PATH=C:\MT5-CI\terminal64.exe
MT5_DATA_PATH=C:\MT5-CI
MT5_VALIDATION_WORKDIR=C:\MT5-CI\validation-runs
```

If the broker terminal uses a separate actual data directory, `MT5_DATA_PATH` must point to that dedicated validation data folder. The docs must tell the user to verify with MT5 `File -> Open Data Folder` before enabling automatic runs.

- [ ] **Step 4: Document staged rollout commands/results**

Order:

```text
1. runner online
2. dry-run
3. compile-only
4. manual 1m tester
5. inspect artifacts
6. only then rely on automatic PR native validation
```

Every stage must distinguish `未実測`, `0 errors / 0 warnings`, `ZERO_TRADES`, and actual completed backtest.

- [ ] **Step 5: Update top-level validation docs without overclaiming**

Before the user's real runner succeeds, `VALIDATION_JA.md` must continue to say native compile and real MT5 backtest are unmeasured. `CHANGELOG.md` should classify this as validation infrastructure, not a v2.45 trading-logic release.

- [ ] **Step 6: Run full offline suite**

```bash
python3 tests/run_all.py
```

- [ ] **Step 7: Commit Task 5**

```bash
git add validation/mt5/README_JA.md README_JA.md VALIDATION_JA.md CHANGELOG.md
git commit -m "docs: add Windows MT5 runner setup guide"
```

---

### Task 6: Manifest, diff review, CI and draft PR

**Files:**
- Modify: `SHA256SUMS.txt`
- Potentially modify only implementation files from Tasks 1-5 if review finds a defect.

**Interfaces:**
- Produces the reviewable PR against `main`; does not merge before real Windows validation.

- [ ] **Step 1: Run complete offline validation from repository root**

```bash
python3 tests/run_all.py
```

Record exact check counts/results. Do not translate C++ adapter warnings into MetaEditor warning counts.

- [ ] **Step 2: Regenerate `SHA256SUMS.txt`**

Hash every tracked file except `SHA256SUMS.txt` itself, sorted by repository path. Confirm the design and plan files are included and no generated runtime artifact/output folder is committed.

- [ ] **Step 3: Review production-source scope**

Verify `git diff main...HEAD -- src` is empty. If any `src/` change exists, stop and remove it unless explicitly approved separately.

- [ ] **Step 4: Review workflow security**

Verify:

```text
no direct pull_request self-hosted job
workflow_run requires upstream success
same repo required
owner/trusted actor required
exact head SHA checkout
single mt5-native concurrency group
no secrets in artifacts/config/profile
```

- [ ] **Step 5: Review documentation truthfulness**

Until a real Windows run occurs, all docs/PR text must state:

```text
ネイティブコンパイル未実測
MT5 Strategy Tester自動実行 未実測
```

- [ ] **Step 6: Commit the final manifest/review corrections**

```bash
git add SHA256SUMS.txt
git commit -m "chore: finalize Windows MT5 validation manifest"
```

- [ ] **Step 7: Open a draft PR to `main`**

PR title:

```text
ci: Windows実機でMetaEditorコンパイルとMT5バックテストを自動化
```

PR body must include architecture/security summary, changed files, offline test results, and unmeasured Windows/native items. Keep it draft until the user completes runner registration and the real compile/test rollout.

- [ ] **Step 8: Review PR diff and GitHub-hosted CI**

Confirm existing Ubuntu CI passes. Do not mark the Windows native lane successful merely because it is skipped/waiting for a runner.

- [ ] **Step 9: User performs first real Windows rollout**

Run in order: dry-run -> compile-only -> manual `1m`. Capture artifacts and classify any failure using `RUNNER_CONFIG_ERROR`, `NATIVE_COMPILE_ERROR`, `NATIVE_COMPILE_WARNING`, `TESTER_START_ERROR`, `TESTER_TIMEOUT`, `TESTER_RUNTIME_ERROR`, `REPORT_MISSING`, `REPORT_PARSE_ERROR`, or `ZERO_TRADES`.

- [ ] **Step 10: Only after real evidence, update validation result and consider merge**

If main EA and Worker both report `0 errors / 0 warnings` and the manual one-month tester completes with a valid report, update PR/validation docs with the measured evidence. If anything fails, fix the same branch/PR with minimal changes and rerun; do not merge simply to activate the workflow.
