# MTFAutoTrader v2.44 — 日本語説明書

更新日: 2026-09-13（v2.44のまま再初期化ロック修正）

## v2.44 再初期化ロック修正版

チャート時間足の変更後に `Cannot initialize symbol:` が連続し、`initialization failed` でEAが終了する不具合を修正しました。実機では `GlobalVariableTemp()` が既存変数に対して失敗するため、終了処理で値を0へ戻したロックを次の初期化で再利用できなかったことが原因です。

修正対象は `SymbolState` の `g_lockKey`、本体の注文実行 `g_execKey`、Fintokeiの `g_propControllerKey`、AI Workerのowner lockの4か所です。存在しない変数だけを作成し、続けて `GlobalVariableSetOnCondition(key,1,0)` で排他的に取得します。既存値が1なら拒否し、取得のための無条件削除や0への上書きは行いません。作成や排他取得に失敗した場合も取得を拒否します。

売買ロジック、エントリー条件、スコア、SL、リスク計算、入力値、保存キー、AIプロトコル242、バージョン2.44を維持しています。`UpdateAutoTrendLines()` の8変数も、shiftは `-1`、priceは `0.0` の宣言時初期化を維持しました。今回の添付ZIPにはこの初期化が未適用だったため、修正版に反映しています。

既存500＋追加43の模擬チェック、JSON55、既存静的監査495、CSV集計20、13ソースの厳密な差分照合が通過しました。**ネイティブコンパイル未実測です。本体・Workerの最終的な `0 errors / 0 warnings` と時間足変更後の動作は、ユーザー実機で確認してください。**

同じv2.44表記の旧ファイルと混ざらないよう、旧EA・Workerを外してから下記13ファイルをまとめて入れ替え、本体とWorkerを再コンパイルします。動作確認のためにロック用Global Variableを削除する必要はありません。今回の修正は、正常終了で値0になったロックの再利用を可能にするものです。

以下はv2.44の機能説明です。

v2.43を基点に、総ポートフォリオリスク上限、全10パターンの構造SL、パターン別の成績ログ・集計ツールを追加しました。既存のM1エントリー、7時間足の重み付きスコア、複数銘柄監視、AI Worker、3つのリスク管理モード、裁量、注文照合、建値移動・トレーリング、Fintokei保護、チャート表示を引き継ぎます。

初期値は総リスク上限3%、分析ログ有効です。`MinimumSignalScore=70`、方向一致の初期下限55%、内部Trend/MACD 70/30、最終スコア比率80/15/5とその入力検証は変更していません。エントリー条件を追加で厳しくするのではなく、保有リスクと損切り位置を改善し、その結果を評価できるようにした版です。

**このパッケージはソースコード版です。MetaEditorでの実コンパイル、MT5実機での動作確認、バックテストによる勝率・取引頻度の比較は未実施です。** 同梱の模擬検証は、実市場での成績を示すものではありません。検証範囲は `VALIDATION_JA.md` を参照してください。

## 導入

1. MT5の「ファイル → データフォルダを開く」から `MQL5/Experts/MTFAutoTrader244/` を作成します。
2. ZIP内の `src/` にある次の13ファイルを、すべてそのフォルダにコピーします。MQ5だけではコンパイルできません。

| ファイル | 用途 |
| --- | --- |
| `MTFAutoTrader_3Mode_AI_v2_44.mq5` | 設置するEA本体・監視コントローラ |
| `MTFAutoTrader_AI_Worker.mq5` | AI/HYBRID用の通信EA |
| `MT3Types.mqh` | 列挙型・構造体 |
| `MT3Config.mqh` | 入力パラメータ |
| `MT3Scoring.mqh` | 重み・スコア計算 |
| `MT3SymbolState.mqh` | 銘柄別エンジン |
| `MT3ReversalPatterns.mqh` | 123・Failed Breakout・競合と再利用防止 |
| `MT3AIProtocol.mqh` | AIとの非同期通信 |
| `MT3Json.mqh` | 厳格なJSON解析 |
| `MT3PortfolioRisk.mqh` | 口座内のEA保有リスク計算 |
| `MT3PatternStops.mqh` | パターン別SLと総リスクゲート |
| `MT3TradeLog.mqh` | CSV/JSON形式・保存スコープ |
| `MT3TradeJournal.mqh` | 銘柄別のエントリー・決済照合ログ |

3. MetaEditorで本体を開き、F7でコンパイルします。AIを使う場合はWorkerもコンパイルします。エラーが出た場合は、エラー一覧の内容を確認してから進めてください。
4. デモ口座の任意の1チャートに本体を1つ設置します。表示中の時間足にかかわらず、エントリー基準はM1です。
5. 監視銘柄、リスク、スプレッド比率を確認してから、MT5側のアルゴリズム取引を有効にします。

初期設定は `ExecutionMode=EXECUTION_AUTO`、`ScanMode=MARKET_WATCH`、`EnableAutoTrading=true` です。取引許可が有効になると、気配値表示にある複数銘柄が新規発注の対象になります。

v2.43から移行するときは旧本体を停止してから新本体に入れ替えます。13ファイルを同じフォルダへまとめて配置してください。既存ポジションを引き継ぐ場合は、同じ口座・サーバー・銘柄名・`MagicNumber` を使用します。未解決注文、発注済みバー、損失履歴、初期リスクRなどの既存保存キーは変更していません。

同梱Workerの表示バージョンは2.44ですが、**通信プロトコルは242を維持**しています。v2.42/v2.43 Workerともプロトコル互換です。通常は同梱の本体・Workerを使用し、Workerを同じ口座で2つ起動しないでください。プロトコル241のWorkerは引き続き拒否します。v2.41の状態移行処理も保持しています。

旧 `.set` を読み込むと、旧版の固定points値も引き継ぐ場合があります。新しい入力項目を確認し、初期値どおり相対判定を使う場合は後述の旧points項目を0にしてください。

## エントリーモードとリスクモード

エントリーを決めるモードと、資金管理の3モードは独立しています。

| `ExecutionMode` | エントリー方法 |
| --- | --- |
| `EXECUTION_AUTO` | M1パターン＋ローカルの重み付きスコア |
| `EXECUTION_MANUAL` | 設置先チャートのBUY/SELLボタン。SLラインを指定して成行注文 |
| `EXECUTION_AI` | ローカルのMTF候補をAIが同方向で承認、または見送り。パターンは必須にしない |
| `EXECUTION_HYBRID` | AUTOと同じパターン候補をAIが承認、または見送り |

| `RiskMode` | リスクの決定 |
| --- | --- |
| `RISK_FIXED_ADJUST` | 基本リスクに、連敗・シグナルスコアによる上限を適用 |
| `RISK_MONTE_CARLO` | 完了取引の実績Rを使うMonte Carloの上限 |
| `RISK_COMBINED` | 固定調整とMonte Carloの小さい方 |

初期の基本リスクは有効証拠金の0.50%、最大1.00%です。既存のスコア別上限・連敗調整を適用します。ロットがブローカー最小数量に届かない場合は取引を見送ります。最小数量へ切り上げません。

1取引ごとのリスク計算に、v2.44では次の総ポートフォリオ上限を重ねます。Fintokeiモードの既存DD余力・保有リスク予約も維持します。

## v2.44の総ポートフォリオリスク

| 新規input | 初期値 | 用途 |
| --- | ---: | --- |
| `EnablePortfolioRiskLimit` | true | 新規注文へ口座内のEA保有リスク上限を適用 |
| `MaxPortfolioRiskPercent` | 3.0 | Equityに対する総想定損失上限、% |
| `EnableTradeLog` | true | 分析用の取引CSV・復元用JSONを出力 |

`MaxPortfolioRiskPercent` は有限かつ0より大きく100以下が必須です。上限無効時も入力の妥当性を検証します。無効化する場合は `EnablePortfolioRiskLimit=false` を使用します。

```text
CurrentPortfolioRisk = Σ max(0, −OrderCalcProfit(方向, 銘柄, 保有数量, 建値, 現在SL))
Limit = Account Equity × MaxPortfolioRiskPercent / 100
CurrentPortfolioRisk + NewTradePlannedRisk ≤ Limit のときだけ新規注文を許可
```

Equityが1,000,000円なら初期上限は30,000円。既存20,000円＋新規10,000円は許可、既存20,000円＋新規12,000円は拒否します。境界の計算には口座通貨でごく小さなdouble誤差許容を設けています。

- 保有リスクは**建値から現在のSLまで**を計算します。現在価格からSLへの含み益の戻し幅は、この新しい上限の保有リスクにはしません。
- BUY/SELL、FX・Gold・指数・原油・暗号CFDを同じ `OrderCalcProfit` 方式で扱います。建値SL・利益側SLは0。利益側SLの利益で別ポジションの損失を相殺しません。
- 同じ `MagicNumber` の全銘柄・全保有ポジションを対象とし、現在のScanModeの対象外銘柄も含めます。同一Magicを別EAにも割り当てないでください。
- Hedgingは各チケットを合算します。他Magic・手動ポジションは対象外です。Nettingでは約定履歴でも所有権を確認し、このEAと他所有者の混在・反転合流・履歴不明は安全側に拒否します。
- EAポジションのSL欠落、数量・価格異常、損益計算不可、EAの稼働中注文による未確定エクスポージャーがあれば新規拒否します。既存の `ORDER UNRESOLVED` 停止が先に適用されます。
- 新規予定リスクは、既存の数量計算と同じエントリー許容スリッページ、SLスリッページ予約、`RoundTurnCommissionPerLot` を含めます。既存保有分は指定の建値SL=0の定義に従い、手数料・swap・追加スリッページを加えないSL価格損失です。
- 口座実行ミューテックス内で保有リスクを読み直し、ロットを計算します。注文準備・ログ保存後、送信直前にも再計算します。同一TimerのA銘柄発注後にB銘柄を古いリスク値で通しません。
- AI/HYBRIDはWorker依頼前に予備判定し、承認後にも共通の注文経路で最新リスクを再評価します。承認中に他銘柄が枠を使った場合は見送ります。裁量注文にも適用します。
- 上限超過時にロットを自動縮小したり、既存ポジションをこの機能だけで強制決済したりしません。FintokeiのDD余力・保有リスク予約・決済は従来の別判定として維持し、両方を通す必要があります。同じリスクを同じ枠から二度減算する方式にはしていません。

EquityはMT5の値を使うため含み損益の影響を受けます。利益側SLを別の負のリスク枠として追加することはありません。SL約定の滑りやギャップ、換算レート・Equityの変化により、実損失が設定した想定枠を超える可能性は残ります。異なる端末や協調しないEA・手動操作の注文まで、この端末のミューテックスで直列化するものではありません。

拒否時はステータスに `PORTFOLIO RISK REJECT` と理由を表示します。集計用カウンターは「拒否が起きた銘柄別M1バー数」で、同一バー内の再チェックを重複加算しません。保存できたカウンターとバーは再起動後にも引き継ぎます。候補の件数や実際に送った注文の件数とは異なります。

## 監視銘柄

| `ScanMode` | 対象 |
| --- | --- |
| `CURRENT_SYMBOL` | 設置先の銘柄 |
| `MARKET_WATCH` | 気配値表示で表示中の銘柄。初期値 |
| `CUSTOM_LIST` | `CustomSymbols` に指定した銘柄 |
| `ALL_TRADABLE_SYMBOLS` | 接続ブローカーが提供する取引可能な銘柄を列挙 |

`CustomSymbols` の例は `EURUSD,USDJPY,XAUUSD` です。カンマ・セミコロン・改行を区切りとして扱い、空白を除去し、重複をまとめます。`EURUSD.a` など、実際のブローカー表記をそのまま指定してください。銘柄名を推測して置換しません。

各銘柄に独立した `SymbolState` を作り、M1バー、発注済みバー、パターン、7時間足の分析結果、インジケーターハンドル、ポジション履歴、裁量状態、AI依頼、Monte Carlo計算状態を保持します。

`OnTimer` が順番に銘柄を走査します。設置先にティックが来なくても走査できます。7時間足すべての確定足データがそろうまで、その銘柄の自動エントリーを待機します。初期データの取得には時間がかかる場合があります。

| 入力 | 初期値 | 意味 |
| --- | --- | --- |
| `ScanTimerMilliseconds` | 1000 | タイマー間隔、ミリ秒 |
| `SymbolsPerTimer` | 20 | 1回の走査銘柄数の上限 |
| `ScanBudgetMilliseconds` | 150 | 1回の走査時間の目安 |
| `UniverseRefreshSeconds` | 60 | 対象リストの再取得間隔 |
| `MaxEntriesPerTimer` | 2 | キューから処理する発注候補数の上限 |
| `DashboardRows` | 8 | 状態表示の銘柄行数。裁量時は最大3行 |
| `MonteCarloTimerBudgetMs` | 20 | 全銘柄のMonte Carlo計算に割り当てる時間の目安 |

時間予算は、個々のMT5 API呼び出しを途中で中断するものではありません。銘柄数・履歴取得・サーバー応答などで1周に要する時間は変わります。表示行数は監視銘柄数の制限ではありません。

取引無効、決済専用、カスタム銘柄、必要な成行注文・SL・TPに未対応の銘柄は新規エントリー対象から除外します。LONGONLY/SHORTONLYの方向制約を守ります。各銘柄の正の価格、tick size、数量仕様、履歴データ、証拠金計算が有効であることも必要です。

監視リストから外れた銘柄の候補とAI依頼は取り消します。気配値表示からの削除は発注前にも再確認します。既存の自分のポジションと未解決注文は、監視リストの外でも管理・照合を継続します。

## 重み付きMTF

| 時間足 | 重み | MACD初期値 Fast / Slow / Signal |
| --- | ---: | --- |
| M1 | 20% | 8 / 21 / 5 |
| M5 | 25% | 8 / 21 / 5 |
| M15 | 22% | 12 / 26 / 9 |
| M30 | 15% | 12 / 26 / 9 |
| H1 | 10% | 12 / 26 / 9 |
| H4 | 5% | 12 / 26 / 9 |
| D1 | 3% | 12 / 26 / 9 |

時間足と重みは固定です。MACDは `MACDM1Fast` / `MACDM1Slow` / `MACDM1Signal` など、時間足別の入力で変更できます。

`Weighted Agreement` はエントリー方向と一致するトレンド方向の時間足の重みを合計した割合です。初期値55%以上で候補になります。例えばM1・M5・H1の方向が一致すれば20+25+10=55%です。中立の足は一致に加算しません。データ不足の足を除いて分母を縮めることもしません。

トレンドの内部方向証拠は−100〜100で、絶対値10未満を中立とします。BUY方向の0〜100点は `50 + 証拠/2`、SELL方向は `50 − 証拠/2` です。各成分の中立は配点の半分になります。

| トレンド成分 | 最大配点 | 内容 |
| --- | ---: | --- |
| EMA20/50/200配列 | 30 | EMA20対50、EMA50対200に各15点の幅 |
| EMA slope | 20 | 3本前との差をATRと本数で正規化。短期/中期/長期を0.6/0.3/0.1で合成 |
| ADX＋DI | 25 | ADX強度とDI優位度を連続評価 |
| 価格のEMA位置 | 15 | 確定足終値と各EMAの距離をATRで正規化 |
| EMA間隔÷ATR | 10 | EMA20対200の間隔をATRで正規化 |

ADX強度係数は15で0.25、20で0.45、25で0.65、35で1.00となる区分線形の連続関数です。15未満は0〜0.25、35以上は1.00です。DI差はDI合計に対する比率で評価します。

slopeの満点基準は0.10 ATR/本、価格位置の距離尺度は0.10 ATR、EMA間隔は1.5 ATRです。`EMASlopeBars=3` が初期値です。これらは実装上の尺度であり、全銘柄の最適値を実証したものではありません。

MACDはヒストグラム45、メイン値25、ヒストグラム変化30の配分でATR正規化した方向証拠を計算します。各時間足の合成は **Trend 70% / MACD 30%**。さらに時間足の重みで集計して、方向別のMTFスコアを得ます。

通常の反対方向MACDはスコアに反映します。拒否する強い逆行条件は次の2つです。

- H1とH4の両方で、反対方向のトレンド点が75点以上、ADXが25以上、DIも反対方向。D1単独の逆行はこの拒否条件に入りません。
- M1とM5の両方で、反対方向のMACD証拠が50以上、かつヒストグラムの逆行幅が0.03 ATR以上。

旧「トレンド4/7一致」「MACD4/7一致」「H1/H4/D1の2/3一致必須」は廃止しています。

## 最終スコア比率

`MinimumSignalScore=70.0` を維持しています。AUTO/HYBRIDの最終点だけ、次の3入力で比率を変更できます。

| 既存input | 初期値 |
| --- | ---: |
| `FinalMTFWeight` | 80.0 |
| `FinalPatternWeight` | 15.0 |
| `FinalLineWeight` | 5.0 |

MTFScoreとPatternScoreを0〜100へ制限し、既存LineScoreの0〜20を5倍して0〜100へ正規化してから計算します。結果も0〜100へ制限します。

```text
NormalizedLineScore = clamp(LineScore × 5, 0, 100)
FinalScore = MTFScore × FinalMTFWeight / 100
           + PatternScore × FinalPatternWeight / 100
           + NormalizedLineScore × FinalLineWeight / 100
```

各入力は有限な0〜100で、合計100との差が0.001以下であることが必須です。負数、100超、NaN/無限大、合計誤りはOnInitで説明をログに出し、`INIT_PARAMETERS_INCORRECT` で停止します。入力比率を自動正規化しません。

| MTF / Pattern / Line | MTF=80、Pattern=70、旧Line=10の計算例 |
| --- | ---: |
| 80 / 15 / 5 | 77.0 |
| 85 / 10 / 5 | 77.5 |
| 75 / 20 / 5 | 76.5 |

80/15/4、80/15/6、-1/96/5、101/0/0はいずれも初期化拒否です。v2.42の固定配分は85/10/5でした。v2.43で80/15/5へ変更され、v2.44でも維持しています。

Trend/MACD比70/30、7時間足の重み20/25/22/15/10/5/3、内部Trend配点とMACD配点はコード固定のままです。`MinimumWeightedAgreement` は添付v2.42の時点ですでにinputだったため、既存設定と初期値55をそのまま残しています。今回新たにinput化していません。時間足別MACDなど、以前からある入力も削除していません。

AI単独モードは既存どおり、方向別の重み付きMTF点でローカル候補を作ります。このモードへパターン必須条件を追加したり、AIのconfidenceを最終スコアへ置き換えたりしません。裁量モードにも新しいパターン条件は強制しません。

## パターンの種類と確定

| 既存の6パターン | v2.43で追加した4パターン |
| --- | --- |
| Triple Bottom / Triple Top | Bullish / Bearish 1-2-3 Reversal |
| Double Bottom / Double Top | Bullish / Bearish Failed Breakout |
| Inverse Head and Shoulders / Head and Shoulders | — |

既存6パターンの検出関数は保持しています。ウェッジ、フラッグ、ペナントは追加していません。AUTO/HYBRIDは全10種類を候補として評価します。既存パターンのM1確定足によるネックライン突破条件も維持しています。

### 1-2-3 Reversal

Bullishは、古い順に「スイング安値P1 → スイング高値P2 → スイング安値P3」の構造です。Bearishは高値 → 安値 → 高値と逆になります。

- 既存の `SwingDepth` を使う確認済みピボットを使用します。初期値5なので、スイングの新しい側にも5本の確定足が必要です。
- BullishはP3 ≥ P1、BearishはP3 ≤ P1。等値を許容し、Higher Low / Lower Highが明瞭なほどPatternScoreを高くします。
- P1→P2は最低0.35 ATR、P2→P3は最低0.20 ATR。ATRはM1・14期間・最新確定足です。
- P3の後、M1確定終値がP2を方向に沿って突破したときに成立します。既存の `NecklineToleranceATR` も適用し、初期値ではP2からさらに0.10 ATRを超える終値を求めます。直前の確定足はそのトリガーの手前であることが必要です。
- P1/P2/P3は `PatternLookbackBars` 内に限ります。P3はさらに `3 × (SwingDepth + 1)` 本以内、初期値18本以内です。最新の確認済みP3から順に直前のP2/P1を選びます。
- 形成中の足の突破、P1を破った構造、P3以降にすでに確定足で突破済みの構造、古すぎる構造は拒否します。

点数は60点を基礎とし、HL/LHの改善幅で最大20点、P1→P2の追加値幅で最大10点、P2→P3の追加押し／戻し幅で最大10点です。すべてATR比で採点し、上限100です。これは構造の評価点で、勝率の推定値ではありません。

### Failed Breakout

Bullishは、確認済みスイング安値を一度下抜け、別のM1確定足で基準安値より上に戻る構造です。Bearishは確認済みスイング高値を上抜けてから下へ戻る構造です。

ノイズ対策として、**ブレイク足自体も基準価格の外側で確定していること**を求めます。ヒゲだけで抜けて同じ足の中で戻ったケースは検出しません。これはv2.43で採用した判定方式を維持しています。

| 条件 | 値・扱い |
| --- | --- |
| 基準レベル | ブレイク前に確認済みだった直近のM1 Swing Low / High |
| 基準レベルの古さ | `PatternLookbackBars` 内 |
| 最低ブレイク幅 | 0.05 ATR |
| 最大ブレイク幅 | 0.30 ATR。ブレイク足から復帰足までの最大逸脱で判定 |
| 復帰期限 | ブレイク後1〜3本のM1確定足以内 |
| 復帰終値の位置 | 元のレンジ側へ戻り、基準価格から0.35 ATR以内 |
| 発注価格の位置 | 復帰側にあり、基準価格から0.35 ATR以内 |
| 小さい復帰実体 | 0.03 ATR未満ならPatternScoreを最大60に制限 |

復帰足の実体方向が反転方向と逆の場合も最大60点に制限します。通常は55点を基礎に、反転方向の実体で最大20点、足の高安に対する終値位置で最大15点、早い復帰に最大10点を加え、上限100です。1本後の復帰は10点、2本後は5点、3本後は0点の速度加点です。実体の加点は0.20 ATRで上限になります。

小さすぎるブレイク、深すぎる逸脱、未確定の復帰、以前に突破・有効なスイープがあった基準を後から復活させる動きは拒否します。PatternScoreが低い場合も、`MinimumSignalScore` やWeighted MTFの条件は変更しません。

新パターンの上記数値に追加inputは設けていません。FX、Gold、指数、原油、暗号CFDなどで価格尺度に追従するようATRとtick sizeを使います。利用可能な銘柄・SL・数量の制約はブローカー条件に従います。

## パターン競合と再利用防止

同一M1バーに複数パターンが成立したら、Weighted MTFの方向条件を通る候補のうち、**最も高いPatternScoreの1件**を採用します。コンフルエンス加点は設けていません。同点は既存の列挙順を維持するため、Triple、Double、Head and Shoulders、123、Failed Breakoutの順です。検出時の一時変数はパターンごとに初期化し、候補配列を確保できなければ不完全な候補から選ばず見送ります。

反対方向が同時に成立し、片方向だけがWeighted MTFと強逆行拒否条件を通るなら、その方向を評価します。両方向が残るなど曖昧な場合は、点数だけで方向を決めず拒否します。方向が決まっても、最終点70、スプレッド、SL、リスク、鮮度などの既存条件をすべて通過する必要があります。

自動・AI・HYBRIDは1銘柄・1M1バーにつき最大1回の発注試行です。明確な発注拒否でも同一バーで繰り返し注文しません。裁量モードは従来どおり `OneEntryPerBar` に従います。

123は方向とP1/P2/P3の時刻、Failed Breakoutは方向と基準スイング時刻で再利用防止IDを作ります。ID自体にも口座・サーバー・Magic・銘柄のスコープを含めます。同じ時刻・価格形状の別銘柄と混線しません。同じFailed Breakout基準で別のブレイクが起きても、使用済みなら再利用しません。

注文を送る前に、選ばれた構造と同方向で同時成立した構造すべてを保存します。未選択のDouble等を次のエントリーへ使い回すことも防ぎます。保存失敗時は発注しません。この段階以降に価格が変わって見送った場合や、ブローカーが明確に拒否した場合も、記録済み構造は消費済みとする保守的な扱いです。通常の再起動で記録を解除しません。旧版の直近ピボット・方向によるガードも併用します。

ラインによる確認は加点要素です。設置していない銘柄でも、水平線とトレンドラインを数値として独立計算します。

## 相対スプレッド・SL・ロット

| 入力 | 初期値 |
| --- | ---: |
| `MaxSpreadATR` | 0.10 |
| `MaxSpreadSL` | 0.15 |
| `SLBufferATR` | 0.05 |
| `SlippageATR` | 0.02 |
| `StopSlippageATR` | 0.02 |
| `MinimumSLImprovementATR` | 0.01 |
| `OpenAIMaxPriceDriftATR` | 0.10 |

発注時は **Spread ≤ ATR(M1)×0.10** と **Spread ≤ エントリーからSLまでの距離×0.15** の両方を満たす必要があります。AIへの依頼前と、ロット計算・注文チェック後にも確認します。

自動SLバッファーは `max(ATR×0.05, broker StopsLevelの価格距離＋1 tick, 2 ticks, 任意の旧points値)` です。パターンの無効化価格を優先し、取得できない場合に従来の汎用SLへfallbackします。tick sizeで構造の外側へ丸めます。裁量のSLは指定価格をtickに丸め、距離不足なら拒否します。裁量SLを自動的に遠くへ動かしません。

ロットは `OrderCalcProfit` で口座通貨の損失を計算し、取引コストの見積もり、スリッページ予約、数量MIN/MAX/STEP、方向別 `SYMBOL_VOLUME_LIMIT`、必要証拠金を反映します。FX専用pips計算は使いません。手数料の見積もりは `RoundTurnCommissionPerLot` に口座通貨で設定してください。スリッページ予約は約定価格の保証ではありません。

旧互換項目 `MaxSpreadPoints`、`SLBufferPoints`、`SlippagePoints`、`StopSlippageBufferPoints`、`MinimumSLImprovementPoints`、`OpenAIMaxPriceDriftPoints` は残し、初期値を0にしています。正の値を設定すると、スプレッド／AI価格変動は追加の上限、各バッファー・改善幅は追加の下限として働きます。

## v2.44のパターン別SL

選択された最高PatternScoreのパターンの無効化価格を優先します。同時成立した各パターンへ別々の注文を出すことはありません。

| パターン | BUYの基準安値／SELLの基準高値 | `SLSource` |
| --- | --- | --- |
| Bullish / Bearish 1-2-3 | P3。P1を優先しない | `PATTERN_123_P3` |
| Bullish / Bearish Failed Breakout | ブレイク開始から復帰確定足までのepisode最安値／最高値 | `PATTERN_FAILED_BREAK_EXTREME` |
| Double Bottom / Top | 2つのBottomの最小／Topの最大 | `PATTERN_DOUBLE_EXTREME` |
| Triple Bottom / Top | 3つのBottomの最小／Topの最大 | `PATTERN_TRIPLE_EXTREME` |
| Inverse H&S / H&S | Headの安値／高値 | `PATTERN_HS_HEAD` |

BUYは基準−Adaptive Buffer、SELLは基準＋Adaptive Bufferです。BUYのSLはtick単位で下へ、SELLは上へ丸め、構造の内側へ入りません。Bufferは従来の `max(ATR×SLBufferATR, StopsLevelの価格距離＋1 tick, 2 ticks, SLBufferPointsの価格下限)` を再利用します。TPはそのSL距離に既存の `RiskRewardRatio` を適用します。

StopsLevelとFreezeLevelの大きい方＋1 tick、最新Bid/Ask、tick刻み、エントリーとの位置関係、SL比スプレッドを検証します。距離を満たすためにパターンSLをさらに任意に引き延ばすことはしません。

パターン価格の欠損・NaN・逆側、ATR/Buffer不足、距離・ブローカー条件の不適合時は従来の `BuildStops` へfallbackします。`UseSwingStopLoss` など従来の設定をそのまま使い、`SLSource=GENERIC_SWING_FALLBACK` と理由をCSVとJournalへ記録します。汎用側も安全条件を満たさなければ発注拒否です。

パターンを必須としないAI単独では従来の汎用SLを使い、`SLSource=GENERIC_SWING` になります。裁量モードは指定SLを使い `MANUAL` と記録します。品質フィルターやパターンの検出条件を追加で厳しくしたものではありませんが、SL変更によりSL比スプレッド、数量、TP、保有時間、総リスク上限への適合結果は変わり得ます。


## AI/HYBRID

本体で `EnableOpenAI=true` にし、同じMT5・同じ口座の別チャートに **Workerを1つだけ** 設置します。APIキーはWorkerの `OpenAIAPIKey` に入力します。MT5の「オプション → エキスパートアドバイザ」でWebRequestを許可し、`https://api.openai.com` を登録してください。

モデル名の初期値は元パッケージの `gpt-5.6-luna` を維持しています。利用するアカウントで使用可能なモデル名とreasoning設定を指定してください。モデル・認証の有効性をこのパッケージの模擬試験で確認したわけではありません。

監視するすべての銘柄をAPIへ送りません。ローカルの点数・方向一致・価格・パターン別SL・コスト・リスク条件と総ポートフォリオ上限を通過した候補だけを送ります。待機候補は高スコア順、同点は同一バー内で最初に候補となった順です。この順位は走査済み候補の順位です。未走査の銘柄まで含めた全世界同時比較ではありません。

WorkerのHTTP呼び出しは本体の外で実行されます。本体はその間もポジション管理を続けます。同時送信枠は1つで、HTTP処理中に依頼をキャンセルしても、Workerが処理を終えるまで枠を解放しません。

v2.43で追加した123・Failed BreakoutもAUTO/HYBRIDの同じ候補フローを維持します。AIへ送るsnapshotのpattern名にもこれらの種類を載せます。HYBRIDの回答後は構造を再検出し、種類だけでなく構造IDの一致、最新の同時成立候補、MTF方向、最終点を再検証します。基準レベルから離れすぎたFailed BreakoutはAI待ち後も見送ります。

AIにはローカル提案と同じ方向、またはWAITを求めます。AI/HYBRIDとも反対方向の回答は拒否します。AIのconfidenceは主観的な判定値で、実測勝率ではありません。confidenceをローカルのシグナル点に置き換えてリスクを増やしません。

初期の判定期限は10秒、銘柄の気配値期限は3秒、参照エントリー価格からの変動幅は0.10 ATR以内です。M1バーの変更、ID不一致、古い気配値、点数低下、方向変更、価格変動、監視対象の変更で回答を破棄します。注文準備後も確認します。ティックのない銘柄をタイマーで再読込しても、気配値の時刻を新しいものとして扱いません。

`OpenAIFailOpen=false` が初期値です。trueの場合でも、HYBRIDの通信障害・HTTP 408/429/5xxに限り、再検証したローカル条件での実行を許します。不正JSON、未完了回答、refusal、通常のWAIT、低confidenceには適用しません。AI単独モードには適用しません。

## 注文照合と口座方式

同じ口座・サーバー・銘柄・Magicの状態を永続キーで分離します。旧v2.41のキーは初回だけ新しい64bit相当の二重ハッシュ名前空間に移行します。読み込んだ異なる銘柄でキーが衝突した場合は、その銘柄の初期化を拒否します。

発注前に意図を保存し、同一MT5・同一口座の実行ミューテックスでリスク計算から注文送信まで直列化します。TIMEOUT、CONNECTION、結果不明の注文は、時間経過・バー変更・再起動だけでは再発注しません。**同一MT5・同一口座内に未解決の発注意図がある間、v2.44の他銘柄の新規注文も停止します。** 保護処理と照合は継続します。

注文ID、約定ID、固有コメントで照合します。注文履歴がFILLEDでも、関連するポジションの表示、または完了済みポジションの全履歴を確認するまで、口座の予約を解除しません。

画面に `ORDER UNRESOLVED` とtokenが出て、自動照合できない場合は、ターミナルの取引・履歴とブローカー側の結果を確認してください。結果を確認した特定の未解決注文だけを解除するための入力が `ReconciledOrderToken` です。対象tokenを正確に入力し、照合後は空欄へ戻してください。既存ポジション・注文が残る場合などは解除しません。以前のtokenで新しい不明注文を解除することはできません。

Hedgingでは `OnePositionPerSymbol=false` のとき複数ポジションを許容します。Nettingでは既存の同一銘柄ポジションがあれば、所有者を問わず新規エントリーを止めて混在を避けます。複数所有者が混じったnettingポジションを、このEAだけのものとして建値移動・DD決済しません。

`MagicNumber` は全監視銘柄で1つの設定を共用し、銘柄名と組み合わせて所有範囲を判断します。他のEA・手動注文全般を本体が制御する設計ではありません。

## 保護・Monte Carlo・裁量・表示

建値移動とトレーリングは、`POSITION_IDENTIFIER` ごとの変更前の初期リスクRを使います。SLを動かした後の距離を新しいRとして採用しません。SLを悪化させる更新を避け、StopsLevel・FreezeLevel・tick sizeを確認します。

Monte Carloは完了取引の利益・損失・手数料等から得た実績Rの再標本化を維持します。サンプル不足時のウォームアップ、勝率下限、95%点DDを使うリスク上限も保持します。計算を小分けにし、銘柄ごとに独立した乱数状態と実績スナップショットを使います。計算待ちの銘柄の新規取引を止めながら、他銘柄の監視と保護を継続します。

乱数生成器はv2.41のグローバルなMathRandから銘柄別xorshift32に変わったため、同じ実績・seedでもv2.41と数値結果が完全一致するとは限りません。v2.42以降は走査順による乱数の混線を防ぎます。v2.44でもこの乱数処理を維持しています。

FintokeiのDD基準、日次参照値、停止ラッチ、余力予約、建玉決済、リスク上限を引き継いでいます。連敗保護は、銘柄別に加えて**同じMagicの完了ポジションを全銘柄で集計した口座連敗**も参照します。契約プランに応じた `FintokeiInitialBalance`、公式の `FintokeiDailyReference`、対応する `FintokeiReferenceDateUTC` を設定してください。内蔵プラン数値はv2.41からの継承値で、現在の会社規則への適合を保証するものではありません。

裁量のBUY/SELL、ドラッグ可能なSL、TPと数量のプレビューは**設置先の銘柄**に作用します。裁量SLの未設定時はATRを取得できてから初期ラインを配置します。MTF分析は参考表示で、裁量エントリーにAUTOのパターン条件を強制しません。注文・コスト・リスク・DD・未解決注文の制限は適用します。

TradingView風テーマ、水平線、トレンドラインは設置先チャートに表示します。テーマはEA内蔵で、別の `.tpl` ファイルではありません。表示中のチャート設定は解除時に所有状態を確認して復元します。監視中の他銘柄の価格座標を設置先チャートへ描きません。ダッシュボードには監視状態と設置先銘柄のリスク・Monte Carlo・DD情報を表示します。

## v2.44の取引CSVと成績集計

`EnableTradeLog=true` で、MT5の共通データフォルダ内に保存します。Windowsでの通常の場所は `%APPDATA%/MetaQuotes/Terminal/Common/Files/MT3Logs_v244/` です。環境固有の共通フォルダはMQL5の `TerminalInfoString(TERMINAL_COMMONDATA_PATH)` で確認できます。通常の端末データフォルダの `MQL5/Files` とは保存先が異なります。

```text
MT3Logs_v244/<端末・口座・Magicのハッシュ>/LIVE/
MT3Logs_v244/<端末・口座・Magicのハッシュ>/TEST_<実行ID>/
```

実口座用のLIVEとテスターの実行ごとのフォルダを分けます。口座・サーバー・Magicに加えて端末パスを名前空間へ含めるため、同じ共通フォルダを使う別端末と分析ファイルを衝突させません。

1ポジションにつき `<銘柄ハッシュ>_position_<PositionIdentifier>.csv` が1つ生成されます。**1行のOPEN記録をCLOSED記録に更新する方式**で、エントリー行と決済行を別取引として数えません。再送されたイベントや再起動も同じファイルへ照合します。UTF-8 BOM付きのカンマ区切り、文字列中の引用符・改行をエスケープします。

| CSVの項目群 | 記録する列 |
| --- | --- |
| 識別 | SchemaVersion、DatasetID、RecordKey、Status、DateTime、Account、Symbol、MagicNumber、PositionIdentifier、OrderID、DealID、OrderIDs、DealIDs |
| 判定 | ExecutionMode、PatternName、PatternDirection、PatternID、FinalScore、MTFScore、PatternScore、NormalizedLineScore、WeightedAgreement |
| 初期注文・リスク | EntryPrice、InitialSL、InitialTP、InitialRiskPriceDistance、InitialRiskAccountCurrency、InitialRiskPercent、LotSize、EntryEquity、RiskMode |
| コスト・総リスク | Spread、SpreadATRRatio、SpreadSLRatio、ATR_M1、PortfolioRiskBeforeEntry、PortfolioRiskAfterEntry、PlannedNewTradeRisk |
| AI・構造 | AIUsed、AIConfidence、AIResult、P1、P2、P3、FailedBreakoutReference、PatternExtreme、SLSource、SLFallbackReason、ContextStatus |
| 決済・成績 | ExitDateTime、ExitPrice、ExitReason、GrossProfit、Commission、Swap、Fees、NetProfit、RealizedR、HoldingTimeSeconds、MFE_R、MAE_R、ExcursionCoverage、Result |

合計63列です。DateTime/ExitDateTimeはブローカーの履歴時刻です。Accountはサーバー名と口座番号を含みます。PositionIdentifier/Order/Dealの64bit整数は正確な10進文字列で出力します。Excelで長いIDを丸めないため、データ取込時にこれらの列を「テキスト」にしてください。

- EntryPrice/LotSizeは実約定の加重平均価格・合計新規数量。部分約定・部分決済をPositionIdentifierでまとめ、完全決済後だけCLOSEDとします。OrderID/DealIDは最初の新規約定のID、複数IDはセミコロン区切り列にも保存します。
- InitialRiskPriceDistanceは元のSLまでの価格距離、InitialRiskAccountCurrencyは実約定数量・価格と元SLに基づく口座通貨の価格損失です。記録済みの初期額を後日の換算レートで再評価せず、追加の部分約定があればその分だけ追加します。初期リスクに手数料を含めず、NetProfitに費用を含めるため、通常のSL決済でもRは−1と一致しない場合があります。
- `NetProfit = GrossProfit + Commission + Swap + Fees`。入場側・決済側の約定に紐付く費用を合計します。`RealizedR = NetProfit / InitialRiskAccountCurrency`。建値移動後・トレーリング後も分母は初期リスクです。別の口座入出金として課され、PositionIdentifierに紐付かない費用は自動配賦しません。
- `PortfolioRiskBeforeEntry` は送信前再計算値、`PortfolioRiskAfterEntry` はbefore＋保守的な新規予定リスクです。約定後の口座再観測値という意味ではありません。上限無効時に計算不能なら空欄にします。
- Spread/ATR/スコア/EntryEquityは注文準備時のローカル提案スナップショットです。最終価格の鮮度・ドリフトは別途送信直前に確認し、EntryPriceは実約定価格へ更新します。
- AIUsedはAI依頼を経た注文で1、AIなしで0。限定HYBRID FailOpenはAIUsed=1、AIResultに `LOCAL_FALLBACK` を残します。confidenceは実測勝率ではありません。
- P1/P2/P3は123なら時系列の3点、Tripleなら3つの極値、H&Sなら左肩/Head/右肩、Doubleなら2点です。Failed Breakoutでは専用のreference/extreme列を参照してください。
- ExitReasonはINITIAL_SL、TRAILING_SL、BREAKEVEN、TAKE_PROFIT、DD_PROTECTION、MANUAL_CLOSE、OTHER。履歴の決済理由と既存のSL更新・DD決済記録で分類します。スマート建値の利益確保もBREAKEVENへ分類し得ます。分類名とは独立に、WIN/LOSS/BREAKEVENのResultは費用後NetProfitと既存 `BreakEvenMoneyTolerance` で決めます。
- MFE_R/MAE_RはEA稼働中に観測したBid/Askと決済価格から得る最大有利/不利方向の価格変化÷初期距離です。全ティックの厳密な最大値ではありません。通常SAMPLED、再起動の観測欠損があればSAMPLED_WITH_GAPSと表示します。

### 保存失敗・再起動の扱い

分析用CSV/JSONと、注文前に必須のGlobal Variablesによる未解決注文・パターン消費記録を分離しています。必須の安全保存失敗は従来どおり新規発注停止。分析用保存失敗はJournalへ `TradeLog warning` を出し、メモリに保持して再試行します。分析失敗だけを理由に既存ポジションの建値移動・トレーリング・DD保護を止めません。

注文tokenの分析用intent JSON、ポジションJSON、稼働銘柄markerから復元します。監視リスト外で停止中に決済された銘柄もmarkerが残れば復元します。CSVは一時ファイルを書いて公開し、JSONとの片側失敗は後の照合で補修します。CLOSED記録に紐付く約定費用の後日更新も、履歴照合された時に同じ記録へ反映します。

EA稼働中の分析保存は、売買・保護処理の後に銘柄を巡回し、通常15秒おき、取引イベント・失敗時は次の処理機会に行います。全銘柄合計20msを巡回予算の目安にしていますが、1回の履歴取得・ファイルI/Oを中断するものではありません。メモリの不足・履歴の取得失敗時は分析履歴カーソルを進めず再試行します。

保存障害のまま端末終了した場合、履歴やコメントをブローカーが提供しない場合、旧版で新規エントリーした取引には、PatternName等を復元できないことがあります。推測で補わず `UNKNOWN`、`MISSING_ENTRY_CONTEXT` としてスコア等を空欄にします。混在Nettingや反転合流は独自の1パターン取引として帰属させません。分析ログだけから失われた取引履歴を完全復元する機能ではありません。

### 集計ツール

Python 3の標準機能だけを使用します。ログフォルダをコピーし、次のように実行します。

```bash
python tools/build_pattern_stats.py "C:/path/to/MT3Logs_v244" --output "C:/path/to/v244_analysis"
```

| 出力 | 用途 |
| --- | --- |
| `MTFAutoTrader_v244_TradeLog.csv` | 個別ポジションを統合した全63列の一覧。OPENも含む |
| `PatternStats.csv` | パターン別の完了取引成績 |
| `SLSourceStats.csv` | SLSource別の完了取引成績 |
| `RunSummary.csv` | 実行単位の成績とPortfolio Risk拒否数 |
| `PortfolioRejects.csv` | 銘柄ごとの総リスク拒否カウンター |
| `AggregationReport.json` | 読込数、重複除外数、データセット数 |

PatternStats/SLSourceStatsは、Trades、Wins、Losses、Breakevens、WinRate、TotalR、AverageR、ProfitFactor、AverageFinalScore、AverageMTFScore、AveragePatternScore、AverageSpreadATR、MaxConsecutiveLossesに加え、NetProfit、Expectancy、KnownRTradesを出します。銘柄は横断集計しますが、DatasetID・口座・Magicを混ぜません。

WinRateは全完了取引（BE含む）に対するWINの百分率。PFは費用後の正のNetProfit合計÷負のNetProfit絶対値合計。損失0で利益ありはINF、両方0は空欄。Rやスコアが不明な取引は、その項目の平均から除外しKnownRTradesでRの母数を示します。連敗数は決済日時順、同時刻はRecordKey順で算出し、BEで連敗を区切ります。

同じRecordKeyの完全一致コピーは除外、OPENとCLOSEDのコピーならCLOSEDを採用します。異なるCLOSED内容のコピーはどちらが最新かを推測せずエラーにします。最新の端末出力を1つだけ残して再実行してください。入力不正を検出してから出力するため、壊れたデータを黙って成績へ混ぜません。

CSV集計はEAから切り離しており、売買中に全履歴のパターン統計を再計算しません。真の最大DDはMT5のEquityレポートで確認します。

## ストラテジーテスターとv2.43比較

AUTO部分をテスターで動かせる構造を維持しています。AI/HYBRIDとWorkerはテスターで初期化を拒否します。HTTPによるAI処理は同梱のテスター検証対象ではありません。

同じブローカー、期間、銘柄、初期資金、手数料・スプレッド、入力設定でv2.43とv2.44を比較してください。M1のエントリーと保護を比較する場合は、利用可能なら実ティックに基づくモードを使用します。複数銘柄は `CUSTOM_LIST` で実在名を固定し、データ取得状況をそろえます。テスターの気配値表示集合が実運用と同じとは限りません。

| 比較項目 | 確認先・目的 |
| --- | --- |
| Total Trades | MT5レポート／RunSummary。保有上限やSL変更が取引数へ与えた影響 |
| Win Rate / Profit Factor | MT5レポート／パターン統計。費用の扱いをそろえる |
| Expectancy | RunSummaryの1完了ポジション当たり費用後平均損益 |
| Max Drawdown | MT5の残高・Equityレポート。保有中の含み損も評価 |
| Average R | PatternStats／RunSummary。KnownRTradesと欠損率も確認 |
| パターン別Win Rate / PF | PatternStats。サンプル数の小さな結果を区別 |
| Portfolio Risk Reject数 | PortfolioRejects。銘柄別の拒否M1バー数 |
| SLSource別成績 | SLSourceStats。構造SL・汎用fallbackを比較 |

v2.43は今回のCSVを出力しないため、旧版のパターン別比較には同条件の履歴・別途採取したパターン記録が必要です。v2.44の集計から旧版のパターン名を推定することはしません。最終比率は両版80/15/5でそろえられます。総リスク上限の影響を分ける研究用比較ではv2.44の上限ON/OFFを比較できますが、パターンSLの新機能をOFFにするinputは追加していません。

勝率、PF、取引頻度、DDの改善は実市場データで未測定です。今回の模擬検証を収益性のバックテスト結果として扱わないでください。

## 同梱ファイルと開発者向け検証

[AGENTS.md](AGENTS.md) にCodexを含む開発・確認・PRの共通ルール、[VALIDATION_JA.md](VALIDATION_JA.md#再現配布結果) に変更範囲別のテストコマンド・依存環境・未検証事項をまとめています。開発中は直接関連するテストから広げ、PR完成前・マージ前に全体の整合性を確認します。過去の変更点は [CHANGELOG.md](CHANGELOG.md) を参照してください。

GitHub Actions の CI も Ubuntu、Python 3.11、g++ で同じオフライン検証を実行し、失敗時を含めて `verification/` の診断JSON/TXTをartifactとして保存します。CIのC++検証はMT5モックであり、MetaEditorによるネイティブMQL5コンパイル、MT5実機・市場バックテスト、実AI/API通信、収益性の検証ではありません。

`verification/` の最終JSON結果は配布ソースのSHA-256と対応しています。`lock_regression_before.json` だけは修正前の失敗再現記録です。ZIP内の `SHA256SUMS.txt` で配布ファイルの整合性を確認できます。生成される検証用C++・バイナリはMT5用のEX5ではありません。

技術仕様の確認先: [MQL5 OnTimer](https://www.mql5.com/en/docs/event_handlers/ontimer)、[銘柄プロパティ](https://www.mql5.com/en/docs/constants/environment_state/marketinfoconstants)、[GlobalVariableSetOnCondition](https://www.mql5.com/en/docs/globals/globalvariablesetoncondition)、[ストラテジーテスター](https://www.mql5.com/en/docs/runtime/testing)。

v2.44初回開発時の参照仕様: [OrderCalcProfit](https://www.mql5.com/en/docs/trading/ordercalcprofit)、[Position properties](https://www.mql5.com/en/docs/constants/tradingconstants/positionproperties)、[Deal properties](https://www.mql5.com/en/docs/constants/tradingconstants/dealproperties)、[FileFindFirst](https://www.mql5.com/en/docs/files/filefindfirst)、[FileMove](https://www.mql5.com/en/docs/files/filemove)。
