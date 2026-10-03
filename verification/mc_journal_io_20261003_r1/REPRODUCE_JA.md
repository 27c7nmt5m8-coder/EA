# 診断の再現手順

この追加層は製品EAを変更しない。基点の12条件とは別に、既存N3/M2/NORMALだけを1回追加実行した。manifestの4行はN3の2方式×2負荷を準備した記録であり、4条件実行済みではない。

## Testerを起動しない検証

```powershell
python -m unittest tests.test_timer_latency tests.test_journal_latency tests.test_journal_io tests.test_timer_latency_frozen -v
```

Current20kとfixed500kの全生成ソースを実測manifestへ照合し、実測top256のTimer/Journal/IO区間と数値replayをhash照合後に再解析する。配布したのは約1.1MBのallowlisted保持区間・80行replay・result/attempt、集計、4行manifest。431,998 callbackすべての詳細、raw Journal、HTML口座情報、EX5、生成EAコピーは配布しない。

`analysis.json`のTimer/Journal/IO部分は配布CSVだけで再生成可能。全Opportunity Funnelの比較を再計算する場合は、ローカルで保持する他exportを各result.jsonのSHAへ照合する。同一hashの既存ログがなければ、同じ条件の新しいTester実行が必要であり過去集計を今回の実行成功として扱わない。

```powershell
$env:PYTHONPATH = (Get-Location).Path
python verification/mc_journal_io_20261003_r1/analyze_evidence.py `
  verification/mc_journal_io_20261003_r1/native/CodexMCMultiJournalIO20261003R1_N3_M2_NORMAL `
  verification/mc_multisymbol_20261002_6230/native/CodexMCMulti20261002B6230_N3_M2_NORMAL `
  --output .validation/journal_io_analysis.json
```

## 新しいTesterコピーを用意する場合

実行時のengine hashesはmatrix/manifest.jsonに固定。MetaEditor/terminal/metatesterのbuild6230 hash、既存安全profile、所有外プロセス不在を先に確認する。変更されていれば無断で新環境を同じ実験と扱わない。元High入力は親記録の`verification/mc_multisymbol_20261002_6230/baseline_inputs.json`で非機密内容とUTF-16 byte hashを照合する。原setは上書きしない。

1. 未使用のローカル出力先へ`python -m tools.build_tester_journal_io --mode 0 --output <new-dir0>`とmode2を実行する。
2. `TesterMCSchedulerValidation.mqh`の記録容量だけを12,000,000から3,000,000へ戻す。各source hashがmode別manifestへ一致することを確認する。chunkや売買設定ではない。
3. MetaEditor `/compile:<main.mq5> /inc:<installed-MQL5-root> /log:<new-log>`をhiddenで起動し、strict UTF-16 logを読む。Result 0 errors / 0 warningsと新規EX5のmtimeを必須にする。CLI exitは保存し、exit1だけで成功/失敗を決めない。
4. `tools.mc_multisymbol_runner.prepare_matrix`へ元High set、保存した`frozen_configs.json`の同条件template、mode別新bundle、新しいnamespace/outputを渡す。`counts=(3,)`、既存original_set_sha256/engine_sha256を維持する。prepareで作るScanMode/CustomSymbolsのコピー以外、条件変更を行わない。元ファイルと既存staged destinationsは上書きしない。
5. 実行する場合は既存`python -m tools.mc_multisymbol_runner --run-case <new-N3-M2-NORMAL> --manifest <new-manifest> --evidence-root <new-evidence>`を使用する。exit0/COLLECTABLE後のみ同じ引数の`--collect-case`を実行する。runnerはsource/set/binary/config/engineのhashとfresh completionを確認する。
6. 上の解析helperで既存同条件のTick/Bar/Funnel/結果/Tradesと比較する。Runtime error/WARNING/矛盾は停止し、古いPASSを流用しない。

CPU_CONTENTIONは今回は再実行しない。先行CPU試行でaffinityが外部から変化しBLOCKEDとなった事実を維持する。Windows securityや他のMT5プロセスを変更して突破しない。

## exact HEAD validation

診断commitをpush後、親記録のREPRODUCE_JA.mdと同じ既存authoritative runnerへ新HEADのCI run IDを渡す。基点0e3903cのCIは今回の追加codeを検証しない。native local BLOCKEDと同一SHAのCI PASSを区別する。

生成手順は同じ計算と条件を再現するが、OS wall timingの同じ230ms外れ値が毎回出る保証はない。固定fixtureの実測値、再実行の新しい観測、歴史的363.961msを混同しない。
