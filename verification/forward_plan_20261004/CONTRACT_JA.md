# FORWARD_VALIDATION_PLAN — Demo候補の準備契約

状態は **PREPARATION_ONLY**。Forward / Demo注文 / Liveは未実行。500kは製品採用しない。
実行段階と停止・復旧手順は [実施計画](../../docs/superpowers/plans/2026-10-04-demo-forward.md) を参照する。

## 候補と固定方法

- 専用branch：`codex/mc500k-demo-forward-preparation`。
- 基準source：`8751b8b923c78ed565c467fd7d8cd1a9f1bd4886`。最新main確認値は `8bce9a51624fbe74b81ce9ea174bcb113cc2be9a`。merge/rebaseしない。
- EA version：2.44。正本13ファイルから生成し、Tester bundleを流用しない。
- scheduler：500,000 operations / callback。既存Timer1000ms、MC deadline20ms、round-robin、force/expiry/history invalidationを維持。
- 別build内の演算上限だけ20k→500k。MC演算・RNG・bootstrap・sample数・判断式・Risk/Safety・注文分岐は変更しない。
- commit後のexact SHAとclean treeを、ローカルの `.validation/forward_candidate_20261004/frozen/frozen_build.json` に記録する。自己参照するcommit SHAを追跡文書へ埋め込まない。
- 同manifestにcanonical/generated source全hash、EA/Worker EX5 hash、MetaEditor/Include/terminal engine hash、set hash、ビルド集合hash、compile結果を保存する。生成ソース・EX5・set・生ログはcommitしない。
- ビルド集合hashは、generated source / EX5 / compiler / standard Include tree / setのhash mapをsorted canonical JSONへ変換したSHA-256。EX5は生成物をhashで固定する。再コンパイル時のEX5 byte再現性は未証明であり、同一バイナリになると主張しない。

## set / 環境（承認前の候補）

既存の4-Symbol bounded検証で実際に使ったN4選択setをbyte単位で再利用する。

`selected_set_sha256 = c6471d7d33406d7df79fc95c333c4502d147d492030c73860baf0d50494d8d46`

元High setのhashは `92e65170040b86bbdec33add10e077886cfd3be692fb824aeca6cc18c8e94e21`。
元setとの差は既存N4選択の `ScanMode` / `CustomSymbols` だけ。元setを変更しない。
AUTO / OpenAI=false / Score70 / SpreadATR2.60・SpreadSL0.40 / MC10000×200・minimum30 / COMBINED risk等をそのまま保持する。
これは以前のN4診断入力の継続候補であり、FXとXAUUSDへ共通Spreadを製品採用する提案ではない。
Demo承認時はこの既存入力を明示して確認する。今回別の値やsetを作らない。

HFM Demo / MT5 6230を仮定。専用Demo口座・専用MT5データディレクトリ・専用profileをユーザーが準備する。
資金はDemo USD100000、leverage1:1000をbrokerが提供する場合のみ。口座種別、費用、Symbol仕様、engine変更は環境差として記録する。
一つのUSDJPY M1チャート上のcontrollerで、USDJPY/EURUSD/EURJPY/XAUUSDをscanする。broker suffixがあれば本候補は起動を拒否し、再計画する。
既存Demo/Liveを移動・更新・破壊しない。20kとの将来比較には別Demo口座/instance/profileが必要で、同一口座で競合させない。

Workerは未変更のままcompileのみ。起動・WebRequest・DLL・API接続・API key・環境変数設定は不要。Jevは使用しない。
account identityはRAM内のDemo guardだけで使い、ファイル・stdout・fixture・CIへ出さない。fresh load時の承認済み口座照合はユーザーがローカル画面で行う。
別口座・real accountのcallbackは拒否する。同一RAM内での再初期化も拒否し、手動fresh loadを要求する。
切断後は既存製品の保護処理を維持し、通常callbackを一律停止しない。

## Source分類

| 対象 | 分類 | 候補への扱い |
|---|---|---|
| canonical `src/` 13ファイル | PRODUCT_REQUIRED | 元ファイルは不変、コピーのみ |
| generated main / SymbolStateのnamed hooks・Demo guard | FORWARD_OBSERVER | 元bodyを保持、guard外で売買判断を変更しない |
| generated SymbolStateのoperation cap | PRODUCT_REQUIRED候補差分 | schedulerだけ500k、未採用 |
| `tools/ForwardMCObserver.mqh` | FORWARD_OBSERVER | ローカルRAM集計/allowlisted export |
| generator / analyzer / tests / plan | DIAGNOSTIC_ONLY | 開発用、EA runtimeへ入れない |
| Tester timing / SHADOW / replay / counterfactual engines | TESTER_ONLY・DIAGNOSTIC_ONLY | 候補から除外、Forwardでは起動しない |

named substitutionsを逆変換するとcanonical13ファイルとbyte完全一致する。
この証明はprovenanceであり、observer非侵襲性や実時間挙動の証明ではない。

## 観測schema / 収集

`python -m tools.build_forward_mc --output <新規ローカル出力先>` で再生成する。既存先や`src/`配下を拒否する。
MetaEditor `/compile:<候補mq5>` `/inc:<既存MQL5ルート>` `/log:<ローカルlog>` でEA/Workerをcompileし、0 errors / 0 warningsとfresh EX5を確認する。terminalは起動しない。

Forward承認後だけ、candidateはterminal-local `MQL5/Files/ForwardMC500k_<UTC>_<Chart>.csv` を生成する。FILE_COMMONを使わない。
RAM上限65,536行、毎Tickの書き出しなし、60 wall秒ごとと通常deinitでflush。
上限/IO/パース異常はsticky UNKNOWNと警告。部分writeを自動再試行しない。製品RiskやPosition管理をobserverから止めない。
停止時はユーザーが曝露を確認して対応する。

| 観測 | 意味・制限 |
|---|---|
| MC_REQUEST / FORCE_REQUEST / PRIOR_RESULT | 実際の要求/force、前result時刻とexpiry。no-op通常pollを要求数に含めない |
| HISTORY_REFRESH / INPUT_VERSION / INPUT | refresh ordinalとbit完全な入力sequence。history content versionとrefresh回数を混同しない |
| START / DD95 / COMPLETE / IMMEDIATE / CANCEL_FORCE / PREPARATION_FAILED | ACTUALのみ。許可/不許可/初期sample不足/計算準備失敗を分離 |
| CYCLE_CALLBACKS / OPERATIONS | cycleのcallback数・wall処理総和/最大・実operation数。wall経過とserver経過は別 |
| active symbol count / lifecycle | 実active overlap。正の重なり区間とそのcycle完了が必要。2/3/4各々COMPLETE/PARTIAL/INVALID/UNOBSERVED |
| PREFLIGHT_WAIT_BAR / WAIT_WINDOW_END | Signal生成前のbar窓。eligible Opportunity数・MC原因の失効数にはしない |
| CANDIDATE | 実生成済みsequence/barをdedup。独立したeligible expiryの完全再構築はUNKNOWN |
| DURATION_TOTAL / HIST | MC / Position / observer export / Timer全体 / chart Tickのcount/sum/maxと累積histogram |
| POSITION_SAMPLE | first / 60秒 / 25ms以上のoutlierのstart/endとMC状態。25msは記録triggerで、許容閾値ではない。unsampled/exposure-specific latencyはUNKNOWN |
| ORDER_RESULT / POSITION_CLOSE_RESULT / POSITION_MODIFY_RESULT | call開始/終了/retcode/bool。bool成功を約定成功と混同しない。同期call時間はbrokerの純通信時間ではない |
| TRADE_TRANSACTION / REQUEST_RESULT / DEAL_PRICE・VOLUME | passed transactionからtype/価格/volumeだけ。raw口座/order/deal ID/commentは出さない。部分約定とclosed-trade数は未同義 |
| Tick / Bar / Timer progression | 処理進行。独立feed母数がなければinput tick lossやqueue待ちを0と断定しない |
| Runtime error/warning | private terminal Journal/Expertsをローカルで点検。MC準備/observer障害は専用記録も確認。生ログをrepoへコピーしない |

Position arrival timestamp、actual event queue depth、queue waiting delayはUNKNOWN。
histogramから得るpercentileはbucket boundsだけで、exact p95/p99はUNKNOWN。
observer export時間をOnTimer総時間へ含め、export自体も別集計する。

`python -m tools.analyze_forward_mc <observer.csv>` はstrict allowlist/header/連続seq/boolean/lifecycleを検査する。
payloadをエラーへechoしない。rawCSVをネットへ送信しない。集計のRECORDED_NOT_ACCEPTEDはForward合格ではない。
数値replayはこのreaderで未実行。同一inputのRNG/DD95/Risk/decision照合は将来のprivate offline再検証として残す。
実口座に由来する原文やcredentialはfixtureにしない。
製品既存Journal/CSV/JSONは口座識別子を含み得るためprivate terminal storageだけに置き、export前に既知secret/accountをRAMで照合する。

## Human Gate / 段階と判定

Stage0：専用Demo、flat/reconciled、Algo Trading OFF。通常market session一つとfresh restart境界を観測。build/init/schema/clock/MC/進行とobserver overheadを確認。注文・Position branchはNOT_OBSERVED。
Stage1：別の明示承認後だけDemo Algo Trading ON。最初の自然注文/約定/Position lifecycleを観測、最大5市場営業日。到達しなければINCOMPLETE、注文誘発・設定変更なし。
Stage2：最低10市場営業日/2週、最大20日。Asia/London/NY/rollover、Symbol別sample状態とactual MC完了、overlapを併記。
既存MC minimum30に対応する30 eligible closed-history samples/Symbolをcoverage目標とする。単なる30dealではない。
前回July N4は10市場日で31/30/52/91 tradesだったため、10〜20日のbounded窓を提案する。Demoで同率になる保証はない。
自然3/4 overlap未観測はUNOBSERVEDとして残し、無期限延長や合成historyを使わない。

acceptance：Risk/Safety/数値/状態破損/real操作/semantics driftはゼロ。eligibleなMC完了継続、説明不能なstarvationやexpiry増加なし、Tick/Bar/Position/Orderの説明不能な欠落なし、observerのmaterialな影響なしを必要とする。
既存offline latency分布は参考値で、任意のmax閾値を新設しない。生きたquote/opportunity/position状態とtimelineを根拠に外れ値を評価する。
calendar、trades、利益だけで合格にしない。Stage0で測定のintrusionが未確認ならStage1へ進めない。

即停止：wrong/real account、Risk/Safety違反、MC破損、starvation、Position/Order重大異常、critical runtime、semantics drift、observer overflow/侵襲。
復旧：専用Demoで新規自動発注をユーザーが停止し、残Position/pendingとbroker SL/TPを確認。Algo Trading OFFではBE/trailingも止まる点を理解し、Demo曝露を手動で安全に解消・reconcile後にdetach/restartする。
history/safety globals/locks/pendingを消して復旧しない。未解決注文中の自動retry/20k切替は禁止。

**開始前承認対象**：Demo環境、ローカルで確認したaccount/profile、4Symbols、candidate exact SHA/EX5/set、Stage0 scopeと監視計画。
口座IDやcredentialを会話・reportへ送らない。Stage1の注文許可は別途必要。
現在の停止はHuman Gate。Forward開始・口座作成・profile設置・EA attachは実施しない。

## 残る検証

Forward全部 / observer非侵襲性 / native reinitのglobals寿命 / 実broker order path / numerical replay / exposure-specific latency / queue・arrival / eligible MC待ち失効はNOT_RUNまたはUNKNOWN。
natural3/4 ACTUAL heavyは過去bounded試験でUNOBSERVEDを維持する。
READY_FOR_FORWARD_VALIDATIONは準備・検証へ進める分類であり、PRODUCT_ADOPTEDやForward PASSではない。
