# MC affinity / isolated CPU contention診断

判定: **ISOLATED_CPU_CONTENTION_ENV_ESTABLISHED / AFFINITY_STABLE / CPU_CONTENTION_COMPARISON_VALID**。500kは **NEEDS_MORE_TESTING**。製品採用・main merge・PRは行っていない。

固定12条件: USDJPY chart M1、2026-09-14〜2026-09-19（Tester server time）、real ticks、USD100,000、1:1000、既存High setのTester専用コピー、AUTO、最適化/Forwardなし。2銘柄=USDJPY/EURUSD、3銘柄=追加EURJPY、4銘柄=追加XAUUSD。Current20k/fixed500k × NORMAL/CPU_CONTENTION。

既存検証VMは確認できず、Sandbox executableも不在。Windows機能を追加せずPriority Cを使用した。専用profile `CodexTesterAffinity_20261004` は4chart/EA0。個々のprocessはPID＋creation time＋live PPID＋same-user tokenで識別する。外部MT5/Tester/updateまたはunknown/drift検出時には除外し、環境を強制復旧しない。

負荷は所有する6個のPython childによる決定論的整数演算。positive CPU time/operationsを確認してからTerminalを起動する。Sleepだけの負荷ではない。affinity/priority/CPU Setsを設定するAPIは使わない。協調終了し、killしない。process default CPU Setsを観測し、threadごとの制約は証明していない。

250ms pollingの事前試験はone-core換算3.54%で除外し、1秒へ変更した。2%は観測器のCPU消費budgetであり、EA latencyの許容閾値ではない。中間のUNKNOWNもstickyに保持し、等しい初期/最終値で隠さない。短命MetaEditor補助processの全期間、polling間のtransient、API caller、実event queue待ちはUNKNOWN/UNATTRIBUTED。過去の1→255変更主体も未特定。

本系列12run完走後、別集計が一時重なった最初のN2 Current CPU runをlatency比較から除外し、同じN2 CPU pairだけを再測定した。最終matrixはR3の10条件＋R4の2条件。新しい市場期間・parameter・candidateは追加していない。元試行は削除せずselection.jsonに除外理由を保存する。

|Symbols|Load|Mode|Signals|Pre-position/MC|Trades|MC待ち失効|Observer CPU % one-core|OnTimer median/p95/p99/max ms|
|---|---|---|---:|---:|---:|---:|---:|---|
|2|CPU_CONTENTION|20k|142|72|47|3|1.283|0.324/1.454/5.738/411.917|
|2|CPU_CONTENTION|500k|141|71|48|1|1.522|0.312/0.858/5.347/452.021|
|2|NORMAL|20k|142|72|47|3|1.050|0.161/0.461/4.143/245.812|
|2|NORMAL|500k|141|71|48|1|0.966|0.157/0.477/4.208/242.124|
|3|CPU_CONTENTION|20k|221|112|77|3|1.330|0.492/1.492/5.914/449.481|
|3|CPU_CONTENTION|500k|220|111|78|1|1.324|0.480/1.749/6.244/456.065|
|3|NORMAL|20k|221|112|77|3|1.025|0.253/0.869/5.127/288.972|
|3|NORMAL|500k|220|111|78|1|1.014|0.247/1.039/5.236/287.725|
|4|CPU_CONTENTION|20k|295|167|117|5|1.236|0.726/3.214/7.612/512.207|
|4|CPU_CONTENTION|500k|294|166|119|1|1.259|0.720/4.473/8.800/464.959|
|4|NORMAL|20k|295|167|117|5|1.031|0.417/1.649/5.963/289.922|
|4|NORMAL|500k|294|166|119|1|1.044|0.393/2.619/6.123/288.736|

全12条件でRuntime error/warning 0。全6 NORMAL/CPU pairでchart Tick・Bar・Trades・Opportunity funnel一致。対象controller/Terminal/Tester/負荷生成器の観測配置はaffinity255/group0/default CPU Setsなし/NORMAL priority32で一致、drift/contaminationなし。外国Symbolの全input tick数・実arrival delay・queue深さ・Symbol別Position管理遅延・Live broker latencyはUNKNOWN。

Numerical: 1316 comparisons、mismatch0、許容差なし。RNG/sample selection/bootstrap/DD95/Risk bit/decision/operation countを既存strict replayで確認。Actual照合row数は1220。詳細のcycle数、callback分布、market duration、force/heavy duplicate/cost、Symbol別funnel/SHADOW完了、retained worst Timer partitionsはanalysis.jsonへ保存。

OnTimer全体のpercentileは全callback populationを使い、hash確認済みevents/timer_summaryとのcount/sum/maxを照合する。上位256件からp95/p99を推定しない。wall elapsedにはOS descheduling/IO待ちが含まれ、pure CPU timeやmarket timeとは異なる。区間最大はretained source partitionsと既存partition validatorで検証する。

過去の419.624msはjournal419.267ms、FileMove416.977ms（2call合計）、MC0の記録。保存経路で時間を観測した証拠であり、SSD/Defender/OS schedulingの原因確定ではない。今回も全体maxとjournal/IO partitionsを保存し、MC callbackのみでEA全体の安全性を決めない。今回12条件の全体最大はTimer ID 1〜4のinstrumented scan区間。製品処理とTester-only opportunity observerを含むため、PRODUCT_PATH単独とは分類しない。NORMAL全体最大289.922ms、CPU競合全体最大512.207ms。500k CPU全体最大464.959ms内はscan437.422ms/actual MC0.002ms/SHADOW27.383ms。Current CPU最大512.207msのnested indicator_observerは103.700ms、indicator_actualは0.330ms。500k CPU最大464.959msではそれぞれ62.114ms/0.313ms。TPObserveBeforeSafetyの診断用m_tpObserver計算もscanに含まれる。起動直後の混在経路であり、残るindicator/history準備・OS待ち・CPU競合の根本原因はUNKNOWN。旧419.624msのFileMove原因が再現したとは扱わない。

同一event loop内でSHADOW heavy stateが時間的に重なる2/3/4 Symbolを観測した。個々の計算実行は逐次であり、parallel threadsとは呼ばない。自然発生の500k 3/4 Symbol同時heavy、実event queue、Symbol別Position latency、Forward/Liveは未検証。これらとOnTimer外れ値のOS原因が残るため500kはNEEDS_MORE_TESTING。

Validation: fresh diagnostic native compile Current/500k各0 errors/0 warnings。MetaEditor CLI exit1は別記し、Result0/0＋fresh EX5で判定した。新observer/runner/analysis focused43 PASS、既存Python全体127 PASS（commit前に再実行済み）。製品EA/Worker native compileも各0/0。Local Gate1/2 BLOCKED、Gate3 numeric20/Gate4 static495/Gate5 scope13 PASS。native C++のlocal BLOCKEDはPASSへ置換しない。同一exact diagnostic HEADのCI native582/JSON55とlocal numeric/static/scopeをtests/run_all.py --ci-runで結合する。最終exact-SHA証拠はcommit後に `.validation/affinity_final_proof.json` と `AFFINITY_STATUS_JA.md` を生成する。過去928のCIは今回の差分のPASSとして流用しない。

Reproduction（新しいnamespace/destinationのみ。既存MT5設定の上書き禁止）:

```powershell
$env:PYTHONPATH=(Get-Location).Path
python -m tools.prepare_mc_affinity_matrix --reference verification/mc_journal_io_20261003_r1/matrix/manifest.json --working .validation/new_affinity_bundle --evidence .validation/new_affinity_evidence --namespace CodexMCMultiNewAffinity
# count=2からNORMAL mode0,2 → CPU mode0,2を実行。問題なしの場合だけ3,4へ。
python -m tools.mc_isolated_contention --manifest .validation/new_affinity_evidence/matrix/manifest.json --evidence .validation/new_affinity_evidence/native --count 2 --mode 0 --load NORMAL
# 各case終了後、負荷が協調終了してから集計。実行中に重い外部集計を並走させない。
python -m tools.analyze_mc_affinity .validation/new_affinity_evidence --output .validation/new_affinity_evidence/analysis.json
```

実際のsource/set/binary/engine/profile/config hashesはmatrix/manifest.jsonへ固定する。maskやpriorityを強制しない。GUI/admin/手動再起動・所有外process操作が必要ならNEEDS_USER_ACTIONとして停止する。raw native Journal/HTML/EX5/大量CSVはcommitせず、local masked exportsをhash付きfallbackとして保持する。

公式仕様: [GetProcessAffinityMask](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getprocessaffinitymask)、[GetProcessDefaultCpuSets](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocessdefaultcpusets)、[OnTimer event queue](https://www.mql5.com/en/docs/event_handlers/ontimer)。仕様は今回の実queue待ちの測定を代替しない。

MC ACTUAL callback（全Symbol pooled; median/p95/p99/max ms）: NORMAL Current0.121/0.169/1.00647/4.571、500k2.415/4.5758/5.27592/9.377。CPU Current0.192/0.280/1.57549/23.541、500k4.852/6.52135/8.259/23.850。poolは異なるinput/cycleを含む観測統計であり、pure CPU timeではない。

Secret/privacy scan: repository + masked diagnostic exports 913 text files、known private/generic credential検出0。新規差分はDIAGNOSTIC_ONLY10 / VALIDATION_INFRA3、PRODUCT0 / UNKNOWN0。製品13sourceとoriginal setのbyte hash一致。raw native MT5 Journal/HTMLはcommit対象外で、既存のMT5生ログ全体を秘匿済みとは主張しない。Windows/security/affinity/priorityの設定変更なし。

MC ACTUAL完了cycleの市場時間中央値（全Symbol pooled）とforce観測:

|Load|Mode|Completed cycles|市場中央値 s|Force requests|Heavy starts|即時判定|同input/state/fresh heavy|重複heavy callback wall合計 ms|
|---|---|---:|---:|---:|---:|---:|---:|---:|
|NORMAL|20k|111|899.0|491|48|443|22|2556.790|
|NORMAL|500k|176|47.0|499|56|443|26|3056.945|
|CPU_CONTENTION|20k|111|899.0|491|48|443|22|3801.495|
|CPU_CONTENTION|500k|176|47.0|499|56|443|26|5232.651|

表の完了cycle/input母集団はCurrent/500kで異なるため、899/47は同一入力のpaired causal ratioではない。force dedupは未変更。callback wall合計はdeschedulingを含みpure CPU costではない。重複heavy増加を修正したとは扱わない。

独立レビュー: requested GPT-6.1 Sol/xhigh（実execution metadataはNOT_OBSERVABLE）。12条件/192exportsのhash、R4 retakeのinput/engine equality、1316exact replay/1220Actual照合、6paired funnelとplacement replayを検証。scanのproduct/diagnostic混在について報告を訂正した。500k採用判断や実queue無遅延の証明には使わない。
