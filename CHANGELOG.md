# CHANGELOG — v2.43 → v2.44

## 2026-09-20：診断PRを最新mainへ統合・ネイティブ検証

- main `98323ea` の開発・検証文書を保持して既存の診断PRを更新。診断コード、売買仕様、既存回帰テストの内容は変更しない。
- MetaEditor 5.0.0.6182で本体・Workerとも0 errors / 0 warnings。対象ソースのSHA-256と結果は `verification/native_compile.json` に記録。Strategy Testerによる取引数0の原因特定は未実測。

## 2026-09-13：Strategy Tester診断ログを追加（売買挙動は変更しない）

- Strategy Tester時だけ、`g_status` が変化したときに `[MT3 TESTER DIAG]` を1行出力する診断を追加。実運用では出力しない。
- 診断行には銘柄、現在status、scan/universe、接続・売買許可、履歴、Monte Carlo ready/allowed、RiskMode、サンプル数、MC上限、口座/銘柄の未解決注文、既存エクスポージャ状態を含める。
- 同じstatusの連続出力は抑制し、`EnableTradeLog=false` でもテスター診断は有効。注文可否、スコア、SL/TP、ロット、リスク計算、保存キー、AI protocolは変更しない。
- 診断回帰8チェックを追加し、統合模擬実行は573 / 573。既存JSON 55、静的監査495、CSV20、13ソース差分監査も通過。
- **MetaEditorネイティブコンパイルと、この診断版を使った実機Strategy Tester再実行は未実測。**

## 2026-09-13：Strategy Testerのライブ接続必須条件を修正

- `EntryPreflight()` のライブ接続拒否を `!MQL_TESTER && !TERMINAL_CONNECTED` に限定し、Strategy Tester時だけライブサーバー接続を不要にした。
- 実運用時の未接続拒否、端末・MQL・口座の売買許可、未解決注文、総ポートフォリオリスク、スコア、SL/TP、ロット計算は維持。
- 未接続テスター／実運用、売買許可OFF、OnInit→OnTimer発注、同一M1重複防止、再接続、総リスク上限、未解決注文の22チェックを追加。
- 既存の再初期化ロック修正43チェックと合わせ、模擬565チェックを実行する。過去の監査ハッシュは変更せず、監査時だけ承認済みの接続式を旧式へ投影して比較する。
- **MetaEditorネイティブコンパイルと、修正後の実機Strategy Testerバックテストはこの統合作業では未実測。**

## 2026-09-13：v2.44 再初期化ロック修正（バージョン据え置き）

- `MT3SymbolState.mqh` の `g_lockKey`、本体 `AcquireExecution()` の `g_execKey`、Fintokei `g_propControllerKey`、Worker owner lockの4か所を修正。Global Variableが存在しない場合だけ `GlobalVariableTemp()` を呼び、その後の `GlobalVariableSetOnCondition(key,1,0)` で排他的に取得する。
- `OnDeinit(REASON_CHARTCHANGE)` 等で値0のまま残ったロックを再利用可能にした。既存値1は取得を拒否し、ロック取得のためのDelete・強制0リセット・タイムアウト奪取は追加していない。ロック解放処理と所有フラグは変更なし。
- `UpdateAutoTrendLines()` の `highShift1/2`、`lowShift1/2` を `-1`、`highPrice1/2`、`lowPrice1/2` を `0.0` で明示初期化する前回修正を維持。添付ZIPでは未適用だったため再反映した。
- `mock_mt5.hpp` の `GlobalVariableTemp()` は既存変数ならfalseを返し、エラー4502（`ERR_GLOBALVARIABLE_EXISTS`）を保持するよう修正。既存値0と1のどちらも上書きしない。
- SymbolStateの同一オブジェクト／同一銘柄の再Init、複数銘柄の時間足変更、注文mutexの再Acquire、Worker再Init、Fintokei再Init、別インスタンス相当の競合拒否、取得失敗側の終了処理、作成／CAS失敗の回帰を追加。
- 修正前の再現と修正後の結果を `verification/lock_regression_before.json` / `lock_regression_after.json` に保存。
- 模擬543（既存500＋追加43）、JSON55、既存静的監査495、CSV集計20が通過。13ソースを添付ZIPのSHA-256へ照合し、差分は4ロック条件＋8初期化のみ。履歴監査の基準ハッシュは変更せず、承認された差分だけを厳密に戻して照合する。
- 本体とWorkerのバージョンは2.44。売買・エントリー・スコア・SL・リスク計算、input、保存キー、Workerプロトコルは変更していない。
- **ネイティブコンパイル未実測。MetaEditorの最終 `0 errors / 0 warnings` はユーザー実機で確認する。** MT5の時間足切替、バックテスト、実ブローカー約定、外部AI通信も本環境では未実測。

以下はv2.44初回機能追加時の変更履歴。

日付: 2026-09-08

基点: 添付 `MTFAutoTrader_3Mode_AI_v2_43_Package(1).zip`。

```text
SHA-256: 86d92447782e8bc72ce28264b2c8040c41b46040248948b234912ca4ea97e00a
```

## 総ポートフォリオリスク上限

- `EnablePortfolioRiskLimit=true`、`MaxPortfolioRiskPercent=3.0` を追加。比率はOnInitで有限・0超〜100以下を検証する。
- 同じMagicの全銘柄の保有ポジションについて、建値→現在SLの想定価格損失をOrderCalcProfitで口座通貨に換算して合算する。
- 建値SL・利益側SLは0。含み益を負の保有リスクとして他の損失と相殺しない。
- SLなし、価格/数量異常、損益計算失敗、管理中の未確定注文は新規拒否。Nettingは履歴で所有権を確認し、混在・反転合流・判定不能も安全拒否。
- 口座実行ミューテックス内で保有リスク再計算→既存ロット計算→予定リスク確認を行う。ログを含む注文準備後、送信直前にも再計算し、同一Timer・AI承認待ちの間の他銘柄保有増加を反映する。
- 予定リスクは既存のエントリー/SLスリッページ予約・手数料見積もりを含む。Fintokeiの従来のDD余力計算は独立して維持し、新上限と両方を通す。
- 超過時は見送り。上限に合わせたロット縮小や、この上限だけを理由にした既存保有の強制決済は追加しない。
- 分析用に銘柄ごとの拒否M1バー数を保存。重複再評価を加算せず、保存済みの同一バーは再起動後も重複させない。

## パターン別SL

- 123はP3、Failed Breakoutは実episode極値、Double/Tripleは全構造の最安値/最高値、H&SはHeadを優先アンカーにする。
- BUYはアンカー−既存Adaptive Buffer、SELLはアンカー＋Buffer。tick刻みで外側へ丸める。
- 従来のATR/StopsLevel/2 ticks/互換points下限のBufferを再利用。StopsLevel、FreezeLevel、Bid/Ask、tick、SL比スプレッドを再確認する。
- パターンアンカーやSLが無効な場合だけ従来の汎用BuildStopsへfallbackし、SLSourceと理由を記録する。fallback側も無効なら見送り。
- パターンSLをブローカー距離に合わせて任意にさらに広げない。TPのRRとロット計算本体は既存のまま、新SLへ追従させる。
- 裁量の指定SLはMANUAL、パターンを使わないAI単独の汎用SLはGENERIC_SWINGとして区別する。

## 成績ログ・集計

- `EnableTradeLog=true` を追加。口座/サーバー/Magic/端末ごと、およびLIVE/テスター実行ごとに分析フォルダを分離する。
- 実PositionIdentifierごとに63列のUTF-8 BOM付きCSVを保存。実約定のEntryPrice/数量、初期SL/TP/R、パターン、全スコア、コスト比率、総リスク、AI情報、構造価格、SLSourceとfallback理由を記録する。
- 部分約定・部分決済を同じ行へ集約し、完全決済でOPEN→CLOSEDへ更新。決済価格・理由・利益/手数料/swap/fees・費用後NetProfit・RealizedR・保有秒数・WIN/LOSS/BEを記録する。
- InitialRiskは記録済み金額を後日の換算で書き換えず、追加部分約定だけ加える。建値/トレーリング後も元のリスクをRの分母に使う。
- 同一履歴の再通知、再起動、遅延約定をPositionIdentifierと注文tokenで照合。履歴へ反映された費用訂正も同じ記録に反映する。
- MFE/MAEは稼働中の観測値をRで出力。SAMPLED/SAMPLED_WITH_GAPSを明記し、真の全ティック最大値とは区別する。
- 分析文脈が欠落した旧取引はUNKNOWN/MISSING_ENTRY_CONTEXTとし、スコアやパターンを推測しない。混在Nettingを1つのパターン成績へ帰属させない。
- 分析用CSV/JSONと重要な注文/パターン消費永続化を分離。分析保存失敗は警告・再試行し、既存保護を停止しない。重要保存失敗の発注停止は維持する。
- 売買後の分析保存は銘柄を巡回。パターン統計はEAで重く計算せず、付属 `tools/build_pattern_stats.py` でオフライン生成する。
- 統合TradeLog、PatternStats、SLSourceStats、RunSummary、PortfolioRejects、AggregationReportを生成。Dataset/口座/Magicを分離し、重複・欠損・不正値・不一致コピーを明示的に処理する。

## 変更していないエントリー・安全機構

10種の既存パターンと検出条件、M1エントリー、MinimumSignalScore=70、最終比率80/15/5とinput検証、MTF重み20/25/22/15/10/5/3、Trend/MACD 70/30、各足MACD、Weighted Agreement、H1/H4両強逆行・M1/M5両強MACD逆行拒否を維持。

1銘柄1M1バー最大1自動発注試行、最高PatternScore選択、反対方向競合の安全拒否、同方向の同時成立パターン消費・再利用防止も維持。

4種ScanMode、OnTimer、SymbolState、ATR相対スプレッド、OrderCalcProfit数量、MIN/MAX/STEP/VOLUME_LIMIT、Netting/Hedging、Magic＋銘柄所有、ORDER UNRESOLVED、他銘柄新規停止、口座ミューテックス、価格鮮度・AI期限/ドリフト、共有Worker・高スコアキュー・限定FailOpenを保持。

3リスクモード、Monte Carlo、Fintokei、Smart BreakEven、ATR/Structure Trailing、裁量、TradingView風テーマ、水平線・トレンドラインを保持。SL計算結果が変わるため、数量・TP・コスト比率や実際のエントリー可否・決済結果は旧版と一致するとは限らない。

## バージョン・互換性

本体/Workerの表示バージョンを2.44へ更新。本体名は `MTFAutoTrader_3Mode_AI_v2_44.mq5`。新ヘッダーはPortfolioRisk、PatternStops、TradeLog、TradeJournalの4個で、srcは計13ファイル。

Worker通信プロトコル242・JSON schemaを維持し、v2.42/v2.43 Workerとソース上で互換。ScopeDigestの既存salt、口座予約・注文token・発注バー・パターン消費・初期リスク等のキーは変更しない。v2.41からの移行処理も保持する。

全既存inputを残し、今回の追加inputは総リスク2個とEnableTradeLogの3個。旧本体を停止して13ソースをまとめて入れ替え、同じ口座・銘柄名・Magicで引き継ぐ。

## 検証・配布

本体/Worker模擬500チェック（既存326＋新規174）、JSON回帰55、静的監査495、CSV集計20が通過。全ソースのSHA-256、再現用テストと監査、README_JA、VALIDATION_JAを同梱。

ネイティブMQL5コンパイル、MT5実機・市場バックテスト、実API接続、頻度/勝率/PF/DD改善の実測は未実施。EX5なしのソースパッケージとして配布する。検証の具体的な限界とv2.43比較項目はVALIDATION_JAを参照。

## 以前の変更

v2.43は123/Failed Breakoutと最終比率input、最高点選択・構造IDの消費を追加。v2.42は重み付きMTF、マルチシンボル、相対コスト、共有AIキュー、口座共通注文保護、銘柄別Monte Carloを追加。v2.44はこれらの品質フィルターを維持する。
