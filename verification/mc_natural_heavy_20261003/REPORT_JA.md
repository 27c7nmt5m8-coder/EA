# Natural heavy MC診断（June固定4条件）

判定は **NEEDS_MORE_TESTING**。製品採用・main merge・Forward/Liveは行っていない。
2026.06.01–06.13（Tester server date、終了日排他）のN3/N4 × Current20k/fixed500k × NORMALだけを事前固定し、4/4新規実行がexit0で完走した。USDJPY chart/M1/real ticks/USD100000/1:1000/AUTO、既存High入力コピー2.60×0.40、最適化/Forwardなし。新しいSpread候補、history/force注入なし。Juneは先行Baselineに重なり、独立OOSサンプルとは扱わない。
CPU_CONTENTIONは前回のaffinity drift（変更主体UNKNOWN）が未解明のため追加実行していない。通常負荷はbusy workerを起動しない条件であり、workstationが完全無負荷という意味ではない。

## Funnel（Opportunity単位）

|Universe/方式|Signal|Score pass|Valid SL|Spread pass|Position前|Position pass|MC ready/permitted|Risk pass|Order/accepted/Trades|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|N3/20k|499|336|324|183|183|136|121/121|106|106/106/106|
|N3/500k|496|333|321|180|180|130|130/130|115|115/115/115|
|N4/20k|699|473|461|320|318|247|203/203|188|188/188/188|
|N4/500k|692|469|457|316|314|227|227/227|212|212/212/212|

N4のSpread passからPosition前の差2件は既存Entry location拒否。全4条件でrisk sizing失敗/注文拒否/Runtime error/warning=0。Risk capは各15 Opportunityを遮断し、解除していない。Score拒否N3=163→163、N4=226→223。Position拒否N3=47→50、N4=71→87。

|Universe/方式|chart ticks|Symbol bar処理合計|MC wait|MC完了前失効|Started/Completed/Cancelled/Censored|MC完了市場時間median (s)|
|---|---:|---:|---:|---:|---:|---:|
|N3/20k|670979|42857|15|15|159/149/9/1|1399.0|
|N3/500k|670979|42857|1|0|270/270/0/0|55.0|
|N4/20k|670979|56647|47|44|437/392/43/2|1099.0|
|N4/500k|670979|56647|2|0|684/682/2/0|47.0|

Current/500kのchart input/processed Tickは各670,979で一致。Barは同一universe内で一致。外国Symbolの実入力Tick母数、missed/duplicateの完全証明、event到着時刻/queue depthはUNKNOWN。quote更新観測を全入力Tickとはみなさない。

## 自然同時heavyの到達範囲

ACTUAL lifecycle/input snapshotを同一EAのGetMicrosecondCount順に照合。REQUEST/START/終了とinput/history digestが一致したsample>=30・win rate gate通過cycleのみ。完了resultのcapture時点でactive区間を終え、遅いCOMPLETE markerによって区間を延長しない。キャンセル/終了打切りを完了と扱わない。synthetic SHADOWは除外。

N3 Current/500kは最大2 active Symbol。N4 CurrentでEURUSD/EURJPY/XAUUSDの自然3 activeを37区間、合計15.693681秒のEA wall clock範囲で観測した。そのうち全cycle完了の32区間は14.637146秒。N4 500kは最大2。USDJPYはheavy開始0（sample不足による即時判断経路）。したがって**500kの自然3同時・自然4同時はUNOBSERVED**。四銘柄universeで自然3を観測したことと、四銘柄同時検証を混同しない。

これは同一event loopでactive cycleを交互に進める観測であり、並列CPU実行の証拠ではない。計算が短くなったことが500kの重なり減少と整合するが、未観測条件の安全性を推論でPASSにはしない。Symbol別completion/operation/funnelはanalysis.json、実測区間はnative/*/lifecycle.csv・snapshotsへhash対応。

## callback / OnTimer

ACTUAL MC callback全母集団。wall-clock占有（OS待ち・descheduleも含む）でありpure CPU時間ではない。

|Universe/方式|Callback n|median ms|p95 ms|p99 ms|max ms|Callback wall合計ms|OnTimer body max ms|最大Timer支配区間|
|---|---:|---:|---:|---:|---:|---:|---:|---|
|N3/20k|213619|0.091|0.164|0.622|1.932|24919.047|365.963|journal|
|N3/500k|15536|2.318|4.003|5.025|11.079|42771.745|419.624|journal|
|N4/20k|479990|0.092|0.163|0.563|5.816|56517.572|374.804|journal|
|N4/500k|32996|2.325|4.033|5.053|11.413|91570.507|277.803|scan|

MC callbackの正常負荷tailは記録したが、OnTimer全体の長時間占有は解消していない。N3/500k最大419.624msのうちJournal419.267ms。N4/500k最大277.803msはTimer1のstartup scan259.618ms＋shadow17.211ms。歴史的363.961ms自体はUNRESOLVED_HISTORICAL_EVENT。新規eventを歴史的eventの原因確定の代用にはしない。top256保持区間からOnTimer全母集団p95を算出しない。

Symbol別Position管理到着遅延、実event queue待ち、Live broker latencyはUNKNOWN。ENTRY_SENDの同期call占有と受付結果をnative/*/timings.csvに保存したが、event到着待ちやLive通信遅延の計測ではない。

## 取引系列の直接照合

N3は500kのみの約定11 − Currentのみの約定2 = 純増9。N4は32 − 8 = 純増24。増分を単純な失効救済数とはみなさない。増えた43約定はCurrentでpositionなし/MC active・not ready、500kでready/permitted/ACCEPTEDを直接照合。後続のPosition拒否とpattern/receipt再利用guardも一意IDで対応付けた。

N3の異なる終端理由はMC_STATE_CHANGE11 / POSITION_STATE_CHANGE3 / EXPECTED_SEQUENCE_CHANGE3。N4は32 / 13 / 13。INSUFFICIENT_EVIDENCE分類0（分類対象の直接理由のみ）。これは全後続履歴の単一原因を証明したという意味ではない。

N4でCurrentにない3 ID（415E4C6A33AD9013 / ABCDC594C279C5F9 / 558D8CD03229EAA5）はCurrentのRECEIPT guardと先行ACTUAL約定2018E320FEABC081（server1781194735）へ接続。guardは65/365/845秒後のcounterfactual pre-filter観測、shadow_seen=1/actual_seen=0。これらがCurrentの実Entry資格まで到達したとは主張しない。500kでは既存owned同方向positionで拒否された。sequence_differences.jsonと保持opportunities/guards/detailが直接根拠。

## force（未修正）

|Universe/方式|force request|heavy force|即時return|同input/state/fresh heavy|request処理wall ms|重複heavy callback wall合計ms|
|---|---:|---:|---:|---:|---:|---:|
|N3/20k|215|44|171|21|1.065|3477.674|
|N3/500k|233|62|171|30|1.932|4887.789|
|N4/20k|380|149|231|73|9.161|7973.421|
|N4/500k|428|197|231|97|16.005|13079.330|

force dedup、history/expiry/MC計算式は変更していない。MC完了回数と先行取引系列が変わり、重複heavyの発生数も変わる。request処理時間と後続計算占有を混ぜない。

## 数値同値性・検証・保持範囲

3,144 replay comparisons、不一致0、許容差なし。うち実完了ACTUAL結果とのbit照合2,986、SHADOW完了照合28。未完了cycleは20k/500kの同input replayを比較するが、実完了結果を検証した数へ含めない。RNG/sample sequence、operation count、bootstrap/DD95、risk bit pattern、decision/min win rateを既存strict replay契約で比較。

診断コピーMetaEditor mode0/2各0 errors/0 warnings、新規EX5を確認。CLI exit1はログ0/0とfresh EX5とは別に保存。OnDeinit=1、history quality100%。新規15 adapter/overlap＋7 frozen evidence regression PASS、直接関連63 tests PASS。生成ソースの全hash、入力/config byte hash、ACTUAL overlap、replay、Funnel、force、注文受付、因果traceとtop256 Timerを再検証する。

製品13ソース（Worker含む）、元High set、MC式・Risk/Safety・売買条件に変更なし。Windows security・所有外process・Live口座操作なし。既存CIで新exact HEADを検証する。基点790afb93b4c125574e68486fc75d00058410892cのCI run37114924405は新diffへ流用しない。exact HEAD authoritative結果はローカル .validation/natural_authoritative_proof.json と .validation/NATURAL_STATUS_JA.md に別記し、自己参照SHAを本文へ埋め込まない。

保持したのはprivacy-check済みallowlisted lifecycle/changed-opportunity列、detail、snapshot、replay、force/order、top256 Timer partition/summary、hash/result/attempt、集計。巨大callbacksやfull timeline、native Journal、HTML、EX5はcommitしない。全原exportはローカル .validation/natural_june_evidence/native に残し、result.jsonのSHAでFallbackできる。callback母集団percentile/Journal・IO詳細の再計算にはそのfull exportが必要。

N4/Current開始時にmarket progressのない待機があり、その後自然に進み1666.8秒で完走した。XAUUSD履歴/cache更新が同時期に観測されたが、exact blocking call/唯一の原因はUNKNOWN。GUI/kill/security変更で突破していない。

## 次の安全境界

500kの自然3/4 heavy＋CPU競合、queue待ち、Symbol別Position遅延、低速実機、Forward/Liveは未検証。未解明affinity driftや更新環境を勝手に変更して追加試験しない。今回の結果だけで製品採用・設定変更・Spread正式決定へは進めない。次に行う作業はCPU競合環境のaffinity driftを読み取り専用で特定し、再現可能な無干渉条件を確立すること。
