# 固定12条件とexact HEAD検証

本記録は製品採用ではなく、build 6230で取得したTester専用診断の固定です。
測定時の製品HEADは `environment.json` の `benchmark_head` です。
診断コードを追加した検証HEADは `git rev-parse HEAD` で取得します。
測定時のレポートと `finish_validation.json` / `gate_result.json` は歴史的証拠です。
そこにある未commit状態やBLOCKEDは後続CIの成功として読み替えません。
新しいexact HEADのCIとcombined gate証拠は `.validation/` に保存します。

## 保存対象と再現性

- `matrix/manifest_final.json`: 有効な12条件、source/set/config/binary/engine SHA-256。
- `baseline_inputs.json`: 元High setの非機密入力を元のUTF-16 byte列へ復元可能な形で保持。
  元setは変更しません。TesterコピーのScanMode/CustomSymbolsだけが異なります。
- `frozen_configs.json`: 実測時のTester設定。口座・認証情報は含みません。
- `native/*/attempt.json` / `result.json` / `*_replay.csv`: 実行IDと終了、allowlisted export hashes、数値同値性証拠。
- `summary.json` / `observations.json` / `REPORT_JA.md`: 全12条件の集計と因果記録。
- `classification.json`: 固定対象とローカル保持対象の全件分類。

大量CSV、EX5、生成EAコピー、native Journal、旧6182環境の試行は配布しません。
大量のallowlisted CSVは元worktreeに保持され、各 `result.json` のexport hashで照合できます。
このcloneだけでは大量CSVから集計を再生成できません。集計再生成には同じハッシュの
ローカルexport、または承認済みの同じTester条件による再取得が必要です。
この作業では追加Testerを起動していません。

## 読み取り・生成・数値証拠の検証

```powershell
python -m unittest tests.test_mc_multisymbol_frozen tests.test_mc_multisymbol_runner tests.test_mc_multisymbol_instrument tests.test_mc_multisymbol_port tests.test_mc_validation -v
```

この検証はTesterを起動せず、12条件/元set/選択set/configのbyte hash、
生成診断source全件、1316 replay comparisonsを確認します。
N2/N3は当時の3,000,000記録容量、N4は12,000,000です。
生成時の `TesterMCSchedulerValidation.mqh` の記録容量だけを実測manifestへ合わせると
両方のsource hashが一致します。これは数式・演算chunk・売買条件ではありません。
Current=mode0、fixed500k=mode2。その他modeは許可しません。
CPU_CONTENTIONは専有可能なCPU coreへ所有プロセスだけをpinし、算術busy workerを重ねる条件です。
睡眠による擬似負荷ではありません。CPU使用率や実queue depthは未測定のままです。
SHADOWは同一EA event loopで重ねる非売買計算であり、自然発生3/4Symbol heavyの証明ではありません。

## 既存authoritative full 5-gate

```powershell
$env:PATH = 'C:\msys64\ucrt64\bin;' + $env:PATH
git status --porcelain
git rev-parse HEAD
# 同一HEADのpush CIが完了後、そのrun IDを使用する。
python tests/run_all.py --ci-run <exact-head-run-id> --metaeditor 'C:\Program Files\HFM Metatrader 5\metaeditor64.exe' --mql-include '<installed-terminal-data-root>\MQL5'
```

既存 `.github/workflows/ci.yml` のnative-windows jobはexact checkout、ABI/unittest、
C++ integration 582 / JSON 55を実行し、exact SHA付きartifactを生成します。
local Code Integrity BLOCKEDをPASSへ変更せず、runnerの既存仕様で同一HEADのCI native
PASSとlocal Gate3/4/5、MetaEditor 0 errors / 0 warnings、clean状態・scope PASSを合成します。
CI/MetaEditor/ローカル検証をTester成功やForward成功の代用にしません。

## 未解決事項

- OnTimer max 363.96ms: UNRESOLVED_DIAGNOSTIC_TARGET。
- natural 3/4Symbol heavy、real event queue wait、Symbol別Position latency: NOT_YET_VERIFIED。
- Forward / Live: NOT RUN。500k製品採用、main merge、PRは行いません。
