# OnTimer / Journal保存の診断結果

製品採用は行っていない。基点は`0e3903c077c44aad80c6273d945cb2e3fa266f58`。変更はTesterコピー生成・計測・厳格解析・回帰・検証記録のみ。製品EA、Worker、元set、MC数式/RNG、Risk/Safety、売買判断、force dedup、500k候補は変更していない。

## 直接確認したこと

固定N3 / fixed500k / NORMAL、USDJPY・EURUSD・EURJPY、2026-09-14～09-19、real ticks、既存High診断入力で1回実行した。R1コピーのCurrent20k/500kはMetaEditor各0 errors / 0 warnings、fresh EX5。CLI exit 1はそのまま記録した。先行のconst参照wrapperは2 errors / 2 warningsで失敗し、Testerを起動せず既存関数と同じ可変参照へ修正した。生成物は新しいR1出力先で再作成した。

実行`CodexMCMultiJournalIO20261003R1_N3_M2_NORMAL`はexit 0、242.437秒で完走。Runtime error 0、warning 0、OnDeinit reason 1。Tick 584,990、全Symbol新Bar処理21,583、Opportunity Funnel/結果、注文受理USDJPY 35・EURUSD 13・EURJPY 30、Trades 78が既存同条件と完全一致した。replay 80行でmismatch 0、うち74行は実完了結果と照合。再生Current/500kのbit/sequence一致を確認した。

Timer観測431,998回、最大256回を保持。今回の最大bodyは初回Timerの275.089msで、Scan 266.291ms、Shadow 8.216ms、実MC 0µs。初期Scan内部のlines 86.286ms / candidate 179.917msを確認したが、これら内部のOS待ちや各APIまでは分解していない。

最大Journalは別のTimer ID 348694で232.001ms。そのUSDJPYのPersist 231.984msを以下へ分解した。

| 区間 | 合計時間 | 呼出し回数 |
|---|---:|---:|
| JSON生成 | 0.090ms | 1 |
| CSV生成 | 0.092ms | 1 |
| 文字列変換 | 0.005ms | 2 |
| FileOpen | 1.079ms | 2 |
| FileWriteArray | 0.003ms | 2 |
| FileFlush | 0.294ms | 2 |
| FileClose | 0.234ms | 2 |
| FileMove | **230.170ms** | **2** |
| FileDelete | 0ms | 0 |

2回のFileMove区間の合計がPersistの約99.22%を占めた。どちらの1回に何msかは未計測。実MCは当該Timerで0µs。同期したファイル公開区間に長いwall elapsedが存在することを直接確認した。ストレージ、セキュリティソフト、OSスケジューリング等の下位原因はUNKNOWNであり、これらを故障・犯人と断定しない。

製品の`OnTimer → ServiceTradeJournals → JournalMaintenance → JournalPersist → WriteAIFile → FileMove`経路が根拠。20ms予算は各JournalMaintenance呼出し前に確認するだけで、開始済みの呼出しを中断しない。JSON/CSVの生成、UTF-8変換、write/flush/close/moveの順序・引数・戻り値・短絡評価は生成コピーでもそのまま維持した。元`MT3AIProtocol`はbyte一致、計測用cloneも時計挿入を戻すと元helperへbyte一致する。

[FileMove公式仕様](https://www.mql5.com/en/docs/files/filemove)はファイルの移動・名称変更とFILE_COMMON/FILE_REWRITEの扱いを定義するが、今回の230msの下位原因を証明するものではない。[OnTimer公式仕様](https://www.mql5.com/en/docs/event_handlers/ontimer)のTimerイベント重複抑止も、今回の実queue待ち時間を測定した証拠にはしない。

## 他runと区別する

- nested NORMAL: 最大body 338.653ms中Journal 338.274ms。初回Scanにも約248～279msを観測。
- Journal細分化NORMAL: 最大body 311.222ms中Journal 310.865ms、EURJPY Persist 310.686ms。
- 今回IO NORMAL: 最大bodyは初期Scan。最大Journalの長い区間はFileMove合計に帰属。
- 過去CPU条件の363.961msは別run・別イベントで、当時はsection記録がない。同じFileMove原因と断定せず`UNRESOLVED_HISTORICAL_EVENT`を維持する。
- 先行coarse CPU結果は空Symbol行のためattribution INVALID/PARTIAL。nested CPU再試行2回は起動時affinity driftでBLOCKED。これらを成功に数えず、security/affinity条件を弱めなかった。

## 検証と限界

Python unittest 62 PASS、Timer/Journal/IO focused 22 PASS、実測固定fixture回帰3 PASS。独立レビューPASS。パーサは欠落・未知・重複・時刻混在・親時間超過に加え、未訪問PersistのIO件数、atomic処理完了のmove/delete矛盾、JSON成功後のCSV短絡評価に反する件数も拒否する。正常・失敗I/O経路の回帰を残す。全baseline生成ファイルとhelperの可逆性はCurrent/500k両方で検証した。

製品13ファイルhashおよび元High set hash一致。既知secret/口座識別子と一般credential形式のscanは1,112ファイルで検出0。値は出力・保存していない。raw Journal・口座ログ・生成EA・EX5は配布しない。Windows security変更なし。

局所のfull gateはnative Gate1/2 BLOCKED、Gate3/4/5 PASS（20 / 495 / 13）。基点のauthoritative CI PASSを今回の未commit追加差分へ流用しない。追加差分のexact HEAD CIは固定後に別途取得する。

計測はwall elapsedでありCPU時間ではない。上位256保持・最初の100 Scan詳細は打切りがある。population p95、event arrival、queue depth、broker latencyはUNKNOWN。IO固定field追加はframe当たり640 bytesでobserver overheadも存在する。今回一致したTesterのTick/FunnelをLiveでのevent lossなしの証明へ拡張しない。FileFlushはvoidのためsuccess status UNKNOWNを維持する。

natural 3/4 Symbol同時heavy、Symbol別Position管理遅延、実event queue待ち、Forward/Liveは未検証。500k判定はNEEDS_MORE_TESTINGのまま。同期保存を非同期化・間引き・Flush省略する修正は実施していない。

次の作業はこの診断差分・証拠を固定し、同一HEADのauthoritative gateを確認する。その後、自然な3/4 Symbol同時heavyを既存条件で再現できるか調査する。製品保存仕様の変更は別の人間判断が必要。
