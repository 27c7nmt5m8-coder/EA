# OnTimer startup mixed scan診断

判定: **ON_TIMER_ROOT_CAUSE_PARTIAL / MIXED**。初回scanの主要call pathは特定。旧CPU外れ値内部の純CPU/OS待機/I/O割合はUNKNOWN。500kは **NEEDS_MORE_TESTING**、製品採用なし。

基点0ef79aff415fd9176d53a41b555262c29a5a3aee、origin/main 8bce9a51624fbe74b81ce9ea174bcb113cc2be9a。main merge/rebaseなし。exact HEADの最終CI証拠はcommit後に.validation/startup_final_proof.jsonへ保存し、旧SHAのCIを流用しない。

対象は4 Symbol（USDJPY/EURUSD/EURJPY/XAUUSD）NORMAL、20k/500kのみ。USDJPY M1、2026-09-14～09-19、real ticks、USD100000、1:1000、既存High setのTesterコピー、AUTO、最適化/Forwardなし。最小2＋詳細R2探索2＋詳細R3最終2の計6実行。全12条件再実行や追加CPU contention runは行っていない。

## 旧exact max cycle

512.207ms/464.959msはCPU_CONTENTIONの記録でありNORMALではない。以下は既存hash-bound原CSVの値。末端の新しいiTime割合を過去cycleへ転用しない。

|Load / mode|Timer / Symbol|total ms|scan ms|lines ms|candidate ms|actual MC ms|shadow MC ms|Journal ms|top残差 us|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
|NORMAL / 0|4 / XAUUSD|289.922|289.104|65.135|223.947|0.001|0.702|0.047|0|
|CPU_CONTENTION / 0|3 / EURJPY|512.207|511.102|142.921|368.154|0.001|0.990|0.042|0|
|NORMAL / 2|3 / EURJPY|288.736|273.292|75.391|197.886|0.002|15.349|0.048|0|
|CPU_CONTENTION / 2|3 / EURJPY|464.959|437.422|137.923|299.477|0.002|27.383|0.060|0|

line/candidate内のCopyBufferはnestedであり加算しない。Symbol scanの子4区間との差は各2us。トップ8区間はtotalと完全一致。startup Cycle1..4は同一server time1789344000で各Symbol初回scan。旧419.624msはJournal/FileMove（416.977ms）であり別call path。共通OS/I/O原因は未証明。

## 新しいNORMAL初回scanのexclusive内訳

|mode / Symbol|Timer|scan ms|製品iTime ms|製品horizontal lines ms|observer iTime ms|observer CopyBuffer ms|他exclusive ms|
|---|---|---:|---:|---:|---:|---:|---:|
|0 / USDJPY|1|286.494|50.891|31.972|162.976|39.150|1.505|
|0 / EURUSD|2|256.506|40.911|30.150|142.101|42.282|1.062|
|0 / EURJPY|3|236.815|41.609|28.160|127.624|38.350|1.072|
|0 / XAUUSD|4|228.975|32.308|27.126|126.346|42.098|1.097|
|2 / USDJPY|1|235.892|39.514|31.758|127.245|36.221|1.154|
|2 / EURUSD|2|237.546|40.636|32.706|125.089|38.113|1.002|
|2 / EURJPY|3|304.173|42.725|32.303|181.553|46.128|1.464|
|2 / XAUUSD|4|251.411|42.217|34.979|127.178|45.911|1.126|

Scan→LineTimeframe初回iTime→自動水平/トレンド線→RefreshCandidate→EntryPreflight→TPObserveBeforeSafety→独立SymbolStateのAnalyzeAllTimeframes→7時間足のiTime/AnalyzeTimeframe/CopyBuffer、という実call graph。observerはDIAGNOSTIC_ONLY。actual/observer native handle生成は小さい。上表の「他」は測定したexclusive区間の集計でありOS待機を割当てた値ではない。各scan子孫のexclusive総和はscan時間と完全一致。

iTimeは毎回時系列要求を行い、初回のデータ準備で時間を要し得る。[公式iTime仕様](https://www.mql5.com/en/docs/series/itime)。Testerの他Symbol/指標初回アクセス仕様も整合するが、MT5内部のディスクI/O・同期・CPU実行・OS preemption割合はこのwall測定から断定できない。[Tester仕様](https://www.mql5.com/en/docs/runtime/testing)。

## Startup / warmup / steady-state

STARTUP=初回4 scan、WARMUP=Timer5..100、STEADY_STATE=101以降。固定4銘柄実験の分類であり売買閾値ではない。詳細版は既存全Timer時系列を終了時だけpartition/sort、count/total/max保存則と前100 root統計を照合。

|mode / phase|count|median ms|p95 ms|p99 ms|max ms|
|---|---:|---:|---:|---:|---:|
|0 / STARTUP|4|247.148|283.732|287.506|288.450|
|0 / WARMUP|96|0.668|1.025|2.246|4.345|
|0 / STEADY_STATE|431898|0.418|1.602|6.038|96.822|
|2 / STARTUP|4|257.149|311.304|317.689|319.285|
|2 / WARMUP|96|0.254|14.818|19.683|21.115|
|2 / STEADY_STATE|431898|0.398|2.578|6.555|96.574|

OnInitはTimer0の別rootとして保持。history/initial risk/Positionの初回はanalysis.json first_accessに記録。初回診断CSV作成はOnTester終了時でありTimerに新たなFile I/Oを追加していない。既存Journal区間は別計測。未測定API内部I/O、純thread CPU、arrival/queue待ちはUNKNOWN。

## 診断overhead比較

最小版も既存Opportunity observerを含む。「製品のみ」との比較ではない。A/Bで追加nested instrumentationの影響を評価する。post100はspan記録を停止するが、wrapper呼出/branchおよびCachedIndicatorのArraySize bookkeepingは残る。記録32768上限/overflow UNKNOWN fail-closed。

|mode / variant|Timer count|median ms|p95 ms|p99 ms|max ms|Trades|
|---|---:|---:|---:|---:|---:|---:|
|0 / minimal|431998|0.420|1.647|5.935|292.175|117|
|2 / minimal|431998|0.561|3.923|10.211|277.236|119|
|0 / detailed|431998|0.418|1.602|6.041|288.450|117|
|2 / detailed|431998|0.398|2.584|6.593|319.285|119|

同modeのA/BでTick/Bar/Trade/Opportunity Funnel一致、各Tick584990・Timer431998。Runtime error/warning0。数値812比較mismatch0、MC許容差なし。単発A/Bのwall分布はhost変動と追加probe負荷を分離できないため、純overheadゼロやevent lossなしとは証明していない。既存observer自体が初回scanの大きなコストを持つことは直接区間計測で確認。

## Scope / 検証 / 再現

変更は新規tools/TesterStartupScanDiag.mqh、build_tester_startup_scan.py、prepare_startup_scan.py、analyze_startup_scan.py、tests/test_startup_scan.py、verification本ディレクトリと配布checksumのみ。生成EAコピーでcompile-time隔離、通常srcにincludeなし。baselineへ全byte復元を検証し、引数/default/呼出順/戻り値を維持。GetLastErrorはCopyBuffer直後に捕捉。製品13 source・元set・MC/RNG/Risk/Safety/注文ロジックは不変。

focused回帰9件（strict未知/parent/overlap、exclusive保存、scan subtree、phase root照合、case/profile/tool hash/observer証拠binding等）。全Python136件PASS。CLI parse errorも値を表示しない回帰を追加。exact HEAD gateの最終結果はstartup_final_proofで確認する。native Gate1/2のローカルCode Integrity BLOCKEDは解除せず、同一SHA CIを使用。

新環境で専用EAなしprofile/engine/hashを確認してから、以下をminimal/detailedで各mode0/2だけ実行。既存MT5/liveupdateがあれば起動しない。新namespace/working/evidenceを使い上書きしない。原文大量ログ/EX5はcommitしない。

```text
python -m tools.prepare_startup_scan --reference verification/mc_affinity_20261004/matrix/manifest.json --working <new bundle> --evidence <new evidence> --namespace CodexMCMultiStartupUnique --variant minimal
python -m tools.mc_isolated_contention --manifest <new evidence>/matrix/manifest.json --evidence <new evidence>/native --count 4 --mode 0 --load NORMAL
python -m tools.mc_isolated_contention --manifest <new evidence>/matrix/manifest.json --evidence <new evidence>/native --count 4 --mode 2 --load NORMAL
# 別namespaceでvariant detailedをprepare/runし、直後に以下で追加CSVのfreshness/hashを保持
python -m tools.analyze_startup_scan <minimal evidence> <detailed evidence> --output <analysis.json>
python -m unittest tests.test_startup_scan
```

first_scans.jsonは各modeの初回最大Timerだけの限定fixture、原trace SHAを保持。analysis.jsonはnative結果/attempt/observer/exportsのhash-bound要約。manifest/compile_results/provenanceでsource、binary、engine、set、profile、toolの対応を保持。秘密値は掲載せずplaintext既知識別子/credential scanを実施する。

## 停止判定

初回seriesアクセス＋product自動ライン＋診断observerのMIXED。主要call pathは判明したが、過去CPU外れ値のnative API内部時間を遡及分解できず、純CPU/OS/I/O原因と診断probeの純overheadはUNKNOWNのためON_TIMER_ROOT_CAUSE_PARTIAL。性能変更・新CPU run・product実行順変更はしない。

500k actual MCではなくstartup共通scanが旧maxの主要部分。ただし全callbackをscheduler-independentとしたりevent無影響を断定しない。natural500k3/4 simultaneous heavy、actualqueue、Symbol別Position latency、Forward/Liveは未検証。500k NEEDS_MORE_TESTING。Human decisionは今回は不要。

次に1つだけ行う作業：読み取り専用のthread CPU/OS scheduling計測で、初回iTime内部の実行時間と待機時間を切り分ける。製品最適化はそれまで行わない。
