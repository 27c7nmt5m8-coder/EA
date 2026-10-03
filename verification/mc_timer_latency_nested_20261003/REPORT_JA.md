# OnTimer診断の途中結果（2026-10-03）

製品採用は行っていない。branchは`codex/mc-timer-latency-diagnostics`、基点は`0e3903c077c44aad80c6273d945cb2e3fa266f58`。今回の追加診断は未commitであり、基点のauthoritative CI PASSを追加差分の検証として流用しない。

## 実測

固定済みN3 / fixed500k / NORMAL、USDJPY・EURUSD・EURJPY、2026-09-14～09-19、real ticks、既存High診断条件を維持した。新しいSpread候補・期間・製品設定は追加していない。

`CodexMCMultiTimerNested20261003_N3_M2_NORMAL`はexit 0、345秒で完走。Runtime error 0、warning 0、MC数値照合80件・mismatch 0。既存同条件とTick、Bar、各SymbolのOpportunity Funnel・最終結果が一致。Trades 78、注文受理USDJPY 35 / EURUSD 13 / EURJPY 30も一致。

厳格解析は`analysis.json`。OnTimer観測431,998回、最大256回を保持、UNKNOWN 0。最大の計測body区間はTimer ID 164227の338.653msで、その内訳はJournal 338.274ms、Scan 0.226ms、Dashboard 0.130ms、Maintain 0.022ms、Shadow 0.001ms、実MC 0µs。過去の363.961msとは別runであり、同一原因とは断定しない。

初回Scanの内訳：

| Symbol | Scan | lines | candidate | 実CopyBuffer合計 | observer CopyBuffer合計 |
|---|---:|---:|---:|---:|---:|
| USDJPY | 278.822ms | 83.250ms | 195.544ms | 0.360ms | 49.599ms |
| EURUSD | 248.043ms | 67.697ms | 180.333ms | 0.224ms | 47.866ms |
| EURJPY | 263.770ms | 77.750ms | 186.006ms | 0.235ms | 46.606ms |

CopyBufferは実110回・observer108回ずつ、すべて成功。last_error 4202は成功後のスナップショットであり、失敗の証拠とは扱わない。CopyBuffer区間はScan内に包含され、二重加算しない。handle作成や他のseries APIはCopyBuffer計測対象外。

## 未完了・計測の限界

- 追加CPU_CONTENTION試行2回は起動時CPU affinityが1から255へ変化し、既存runnerがBLOCKED。設定を弱めず再試行を停止した。残留した所有Testerは自然終了。killは実施していない。
- 先行coarse CPU試行はFunnel・Tick・Tradesが一致したが、未使用Symbolスロットの264行が空欄となり厳格なattributionではINVALID/PARTIAL。成功証拠に流用しない。numeric seen-maskで修正し、今回NORMALで空欄なしを確認した。
- nestedは最初の100 callbacksのみ、さらにtop256保持による打切りがある。保持レコードから母集団p95等を推定しない。
- body計測は既存MCSMeasureとTLFinishのtailを除外。TLFinish内部bookkeeping最大74µsは観測したが、診断全体のoverheadではない。
- wall elapsedとCPU実計算時間は同一ではない。event arrival、実queue depth、broker Live latencyはUNKNOWN。
- Journal stage内部のどの処理が338.274msを占有したかは未特定。ServiceTradeJournalsの20msチェックは各呼出し前の条件であり、1回のJournalMaintenanceを中断する上限ではない。History処理・同期ファイル処理等のどれかは、現段階では推測しない。
- 過去363.961ms、natural 3/4 Symbol同時heavy、実event queue待ち、Symbol別Position latency、Forward / Liveは未検証のまま。

## 検証と範囲

- MetaEditor：Current20k・fixed500kの新しいnested Testerコピーとも0 errors / 0 warnings、fresh EX5。CLI exit 1はそのまま記録。
- Python unittest 48 PASS、うちTimer focused 11 PASS。独立GPT-6.1 Sol / xhigh review PASS。計測窓外のnested、欠落Symbol detail、矛盾した重複span等を拒否する回帰を追加。
- 製品13ファイルは基点とbyte/hash一致、元High setのSHAも一致。MC数式・Risk/Safety・注文・売買条件・force dedup変更なし。Windows security変更なし。
- 対象47ファイルの既知secret・口座識別子scanで検出0。値は出力・保存していない。raw Journalはartifactへ保存していない。
- 追加未commit診断についてexact SHA CI/full 5-gateはNOT RUN。基点のauthoritative PASS証拠は`.validation/AUTHORITATIVE_REPORT_JA.md`に独立して維持。

次に1つ行うべき作業：Tester専用コピーでJournal処理内部を追加計測し、長いbody区間の直接原因を絞る。製品処理や同期I/Oを変更する前に証拠を取得する。
