# 固定4条件の再現・Fallback

## MT5を起動しない検証

```powershell
python -m unittest tests.test_mc_natural_heavy tests.test_mc_natural_frozen -v
```

固定4条件、元入力/set/config bytes、全生成MQLソースhash、fresh attempt/result、ACTUAL lifecycle、数値replay、Opportunity Funnel、force/受付、取引系列の直接trace、top256 Timer partitionを確認する。ここでのPASSは保存された証拠の再解析であり、新しい市場テストやForward成功ではない。

manifestのsource_sha256は実際にコンパイルしたTester-only journal/IO bundleと一致する。`tools.build_tester_journal_io.build(<new-dir>, mode)`のmode0/2だけを使う。この実測はduration capacity12M、record3M、input10M、validation2Mの既存デフォルトであり、容量を変更して再現しない。製品13ソースは先行6230記録のproduct hashへ照合する。

## 保持した証拠

`retention.json`は保持ファイルhashと原export hashを結ぶ。snapshots/replay/detail/guards/requests/timings/Timer top256・summaryは元bytesをすべて保持する。`lifecycle.csv`はREQUEST/START/COMPLETE/CANCEL/CALCULATION_FAILED/INVALIDATE/RUN_ENDだけを必要列へ射影し、元global seq/clockを維持する。`opportunities.csv`は変更IDと先行claimantのtraceを必要列へ射影する。元ファイル名、hash、元/保持件数、列、選択方法を記録し、全原文を保持したようには扱わない。

Callback全母集団percentilesとJournal/IO詳細は保存集計を凍結したもの。独立に再計算するにはローカル `.validation/natural_june_evidence/native/<case>/` のfull exportsが必要。各`result.json`のexports SHAへ一致を確認してから、`tools.analyze_mc_multisymbol.describe_case`、`tools.analyze_mc_natural_heavy.natural_overlap`、Timer/Journal/IOの既存strict analyzerを用いる。原ファイルを入手できない場合はその再計算をNOT RUNとし、集計を新しい実測として扱わない。raw Journal/HTML/EX5や全callbackをcommitしない。

## 新しいTester実行が必要な場合

1. source/set/engine hashes、build6230、既存安全profile、所有外MT5/Tester/update不在を確認する。GUI/更新/手動再起動が必要なら停止する。
2. 新しい未使用出力先へmode0/2の診断bundleを生成する。MetaEditorで各EAをcompileし、strict UTF-16 Result0 errors/0 warningsと新規EX5を確認する。既存EA/元setを上書きしない。
3. `frozen_configs.json`のJune templateと元High set、mode別新bundleを`tools.mc_multisymbol_runner.prepare_matrix`へ渡す。`market_window='JUNE_NATURAL', counts=(3,4), loads=('NORMAL',)`、元set hash・engine hashをmanifestから維持し、新namespace/新destinationsを使う。ScanMode/CustomSymbolsはTesterコピーのみで、他設定を保持する。
4. 既存runnerの`--run-matrix --max-new 4 --manifest <new-manifest> --evidence-root <new-evidence>`を使用する。固定1800秒timeout、owned launcher、fresh completion/strict collectorを維持する。CPU条件、期間、候補を追加しない。
5. mode0/2の同一universeを対応付け、Tick/Barを確認し、変わったIDはguard/MC/positionの原traceへ戻る。Runtime/WARNING/UNKNOWN/不足・hash driftは失敗または未完として扱う。shadowを自然ACTUAL heavyの代用にしない。

市場データcache準備やOS wall timingは再実行で変わり得る。保存された同じ419.624ms外れ値が毎回出る保証はない。Juneは先行Baselineと重なり、独立OOSではない。

## exact HEAD gate

CIは診断commitのexact SHAだけを有効にする。既存`.github/workflows/ci.yml`の通常push CIが成功した後、同じHEADで以下を実行する。

```powershell
python tests/run_all.py --ci-run <same-head-run-id> `
  --metaeditor 'C:\Program Files\HFM Metatrader 5\metaeditor64.exe' `
  --mql-include '<installed-MQL5-root>'
```

local native Code Integrity BLOCKEDは維持し、同一HEAD native-windows artifactのGate1/2/ABI/MC deterministic結果を確認する。Gate3/4/5、MetaEditor、scope、clean input fingerprintを合わせてauthoritative PASSにする。基点790afbのCIは今回へ流用しない。新exact SHAの結果はローカル`.validation/natural_authoritative_proof.json`で実測commitへ対応付ける。security変更、main merge、PR、製品採用、Forward/Liveはこの手順に含まれない。
