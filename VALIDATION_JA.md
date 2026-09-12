# v2.44 検証報告

実施日: 2026-09-08

**配布する実ソースの模擬実行500チェック、JSON回帰55チェック、静的監査495チェック、CSV集計20チェックが通過しました。ネイティブMQL5コンパイル・市場バックテスト・実際のAI API通信は未実施です。EX5は同梱していません。**

件数には初期化、方向違い、倍率違い、同一試験内の複数確認を含みます。500件の独立した相場シナリオや、収益性の検証という意味ではありません。

## 基点・環境

基点は今回添付された `MTFAutoTrader_3Mode_AI_v2_43_Package(1).zip` です。

```text
SHA-256: 86d92447782e8bc72ce28264b2c8040c41b46040248948b234912ca4ea97e00a
```

元のv2.43を別ディレクトリに展開し、未変更ソースでも326チェックの通過を確認しました。v2.44では既存326（v2.42由来207＋v2.43追加119）を維持し、174チェックを追加しています。旧版の試験ケースの削除はありません。共通reset処理に新入力・ログ・故障注入用の初期化を追加しました。

Linux、Python 3、g++ C++17を使用しました。MT5/MetaEditor/Wineが利用できないため、本体・全include・Workerを展開してMQLの配列・UTF-16文字列・クラス参照等をC++へ適応し、MT5サービスを模擬して実ソースを実行しました。判定関数を別言語に複製したものだけを試験したわけではありません。

価格、指標、履歴、注文、SL変更、チャート、ファイル、イベント、HTTPは模擬実装です。C++アダプターのコンパイルエラーは0。短い複数文行のインデント、未使用引数・変数等の警告が31件あります。これはMetaEditorでのコンパイル結果ではありません。

## 結果

| 区分 | 結果 | 内容 |
| --- | --- | --- |
| 本体・Worker模擬実行 | 500 / 500 | 既存326＋v2.44追加174 |
| JSON回帰 | 55 / 55 | 厳格JSON、UTF-16、Responses回答状態・schema |
| ソース監査 | 495 / 495 | 既存監査の継承、変更関数の限定、総リスク・SL・ログ監査 |
| オフラインCSV集計 | 20 / 20 | 独立した数値例、重複・不正・不明値・データセット分離 |
| `_Symbol` 全検索 | 1か所 | 本体OnInitの設置先取得のみ |
| `_Point` / `_Digits` / `_Period` / `PERIOD_CURRENT` | 実行ソースに残存なし | 新モジュールも銘柄別参照 |
| ネイティブMQL5コンパイル | 未実施 | EX5なし |
| MT5テスター・デモ・実API | 未実施 | 約定、UI、実成績、通信遅延は未測定 |

## 総ポートフォリオリスク

| 試験 | 確認結果 |
| --- | --- |
| 保有なし＋新規1%、上限3% | 許可 |
| 既存2%＋新規1% | 境界を含め許可 |
| 既存2.1%＋新規1% | 拒否 |
| BUY建値SL、利益側SL | リスク0、利益を負のリスク枠にしない |
| BUY利益側SL＋SELL損失SL | SELL損失を相殺しない |
| SLなしEAポジション | 新規拒否 |
| FX＋Gold＋指数、Hedging複数チケット | 模擬契約数量・口座通貨で合算 |
| 他MagicのHedgingポジション | 対象外 |
| Netting単独所有 | 計算可能 |
| Netting履歴不明、他Magic混在、現在Magicだけ変更 | 所有不明を安全拒否 |
| OrderCalcProfit失敗 | 拒否 |
| 上限を明示無効にして計算不可 | 既存ルールを通し、ログ値を既知の0と偽らない |
| 同一OnTimerで2候補 | 1件目の保有増加後に2件目を再拒否 |
| AI待ち中に他銘柄のリスク増加 | AI承認後の注文を拒否 |
| OrderCheck中に保有増加を故障注入 | 実行ミューテックス所有と、送信前の再計算による拒否 |
| 負・0・NaNの上限input | OnInit拒否 |
| 同一M1の繰返し拒否・再起動 | 保存済み拒否バーの二重加算防止 |

既存保有は建値→現在SLの価格損失、新規予定分は既存スリッページ・手数料予約込みです。この異なる定義をREADMEに明記しています。保有中のSLなし・未確定注文は、既存のORDER UNRESOLVED等と合わせて新規安全停止します。Fintokeiの従来の現在価格ベースDD余力計算を、この建値ベース上限へ置き換えていません。

## パターンSL

全10方向（123、Failed Breakout、Double、Triple、H&SのBUY/SELL）で、正しい無効化価格とSLSource、Adaptive Bufferの外側、最新価格に対する安全距離を確認しました。

- 123はP3、Failed Breakoutはepisode極値、Double/Tripleは構造の最安/最高、H&SはHead。
- StopsLevelをBufferへ反映。0.25など10進小数桁だけでは扱えないtick sizeでも外向きに丸める。
- NaN・逆側のパターン価格は理由付き汎用fallback。
- FreezeLevelでパターンSLが近すぎる場合は汎用fallback。汎用SLも不正なら拒否し、任意に遠くへ広げない。
- 汎用BuildStops、BuildManualStops、StopBuffer、CalculateLotByRiskの実装はv2.43と一致。

検出器とスコアは元のままなので、PatternLookbackBars、確定足、再利用ID、最高点選択、反対方向の曖昧性拒否は従来の試験で継続検証しています。

## 取引ログ・集計

| 試験 | 確認結果 |
| --- | --- |
| エントリーログ | 123のPatternName/ID、SLSource、実Position/Order/Deal、初期価格リスク・口座通貨リスク、総リスクbefore/after |
| 決済ログ | OPEN→CLOSEDを同じファイルへ更新 |
| INITIAL_SL / BREAKEVEN / TRAILING_SL | 初期リスクを保持し、費用後損益÷元のリスクでRを計算 |
| TP / Manual / DD決済 | TAKE_PROFIT / MANUAL_CLOSE / DD_PROTECTIONを分類 |
| 複数の新規約定・部分決済 | 合算し、部分決済を完了取引に数えず、完全決済で1回だけ集計 |
| 初回ログ前に異価格の部分約定が追加 | 実価格・数量で加重した初期リスクを保存 |
| 後日の換算条件変化 | 保存した初期金額を再評価せずRの分母を固定 |
| 約定に紐付く後日のcommission訂正 | 同じCLOSED記録を修正、二重記録なし |
| 同じ決済履歴の再通知・再起動 | 1ポジション1ファイルを維持 |
| CSV書込み失敗 | 警告、エントリー・建値/トレーリング保護を継続、復旧時に再保存 |
| 分析用intent/position JSON失敗 | 安全注文照合と分離し、メモリから再試行 |
| AI承認 | AIUsed、confidence、AIResult、AI_ONLYを保存 |
| 複数銘柄 | 銘柄・PositionIdentifier・Patternの記録混線なし |
| 注文結果不明→再起動→遅延約定 | intentの分析文脈を回収し、照合後に実ポジションを1件記録 |
| 監視対象外の銘柄が停止中に決済 | markerから状態を復元し、走査を再有効化せず決済を記録 |
| 分析文脈の欠損 | UNKNOWN/MISSING_ENTRY_CONTEXTを明示、取得できる初期リスクのみ復元 |
| JSON/CSV | 2^53超の64bit ID、Unicode・引用符・改行、数式先頭文字のエスケープ |
| テスター/LIVE | フォルダ分離とテスター実行ごとのID分離 |

Python集計は、利益200、損失−100/−50、BE0など独立した既知の数値例を使用し、勝率25%、PF=200/150、TotalR=0.5、AverageR=0.125、Expectancy=12.5、最大連敗2を確認しました。異なるDataset/口座/Magicを混ぜず、OPENの除外、完全一致コピーの除外、OPEN→CLOSED優先、異なるCLOSEDコピーの拒否、欠損R/スコアを平均の0にしないこと、不正NaNの拒否、Excel BOM、SLSource集計、拒否数合算を確認しました。

MFE/MAEは観測サンプルに基づく値です。ギャップ・端末停止中・ポーリング間の真の最大値は未再現。履歴の費用やSLの提供方法、ファイルロック、電源断時のJSON/CSV公開途中状態は実機確認が残ります。

## 既存エントリー・安全機構の継承

既存326チェックには、10パターンの両方向、幾何条件、未確定足/古い構造の拒否、実OHLCでの同時成立、同方向の消費ID、反対方向競合、パターン配列・永続化の失敗が含まれます。80/15/5、85/10/5、75/20/5の計算と、不正な比率・NaNの初期化拒否も維持しました。

MTF重み20/25/22/15/10/5/3、Trend/MACD 70/30、MACD時間足別設定、ADX連続配点、55%境界、H1/H4両強逆行、M1/M5両強MACD逆行、M1一回発注、ATRスプレッド/SL、OrderCalcProfit数量、SYMBOL_VOLUME_LIMITを継続確認しています。

AUTO/MANUAL/AI/HYBRIDの不明注文、他銘柄新規停止、再起動・新バー後の未解決維持、FILLED履歴と保有表示の時間差、正確な照合token、口座実行ミューテックス、Netting混在拒否、Hedging複数保有の試験を残しています。

AIの高スコア順キュー、HTTP中の枠保持、全銘柄送信の禁止、依頼元銘柄への応答、期限・M1・価格ドリフト・不正回答・低confidenceの拒否、HYBRID通信障害だけの限定FailOpen、AI単独のFailOpen禁止、Worker旧プロトコル拒否を継続確認しました。

4種ScanMode、OnTimer走査、銘柄別インジケーター・状態、Fintokeiの日次/全体DDと口座連敗、Smart BreakEven、ATR/Structure Trailing、Monte Carlo分割実行、裁量・テーマ・水平線・トレンドラインの保持も旧ケースとソース比較で確認しました。画面そのもののMT5実機表示を確認したものではありません。

## 静的監査・ネイティブコンパイル候補

- 全13ソースの括弧・コメント・文字列構造、ローカルinclude解決、宣言順、クラス内メソッド、参照渡し配列、文字列を含む構造体初期化・コピーを確認。
- `_Symbol` は本体の設置先取得1か所のみ。新しい総リスクは全保有ポジションから銘柄名を取得し、SL・ログはSymbolStateのm_symbolを使用。
- v2.43エンジン171関数のうち160関数は、コメントと書式を除き文字列を残すSHA-256で一致。変更した11関数は初期入力、初期化/終了、候補・AI・実行へのSL/総リスク追加、分析フックに限定。
- v2.42由来162関数の比較も保持。そのうち6関数は追加された分析フックだけを厳密なテキスト一致で除去してから旧ハッシュへ照合し、元の保護計算・条件・注文引数の一致を確認。
- `MT3Types`、`MT3Scoring`、`MT3ReversalPatterns`、`MT3AIProtocol`、`MT3Json` はv2.43のモジュール全体と一致。既存inputの宣言・初期値をすべて保持し、新しいinputは総リスク2個＋EnableTradeLogの3個のみ。
- コントローラは分析サービス・復元・初期化フィールドだけを厳密に除いて旧版と比較。Workerは表示バージョン以外が一致。プロトコル242、request/response schema、状態キーsalt、Magic/銘柄・口座予約スコープは変更なし。
- 注文直前の総リスク再計算と鮮度再確認の順序、SLの外向き丸め、分析I/Oから注文承認へ戻り値を接続しないこと、重要保存失敗の発注停止を監査。
- 公式のOrderCalcProfit、Position/Deal properties、FileFindFirst/FileMove仕様を参照し、口座通貨計算・64bit識別子・FILE_COMMONの使用を確認。

比較は変更範囲の限定を確認するものです。旧版の未知の不具合やネイティブMQL固有の型規則、ブローカー固有仕様がないことを証明するものではありません。将来変更する場合、監査の除外範囲を雑に広げず、追加フックと試験内容を再レビューしてください。

## 実機で残る確認とv2.43比較

1. MetaEditorで本体とWorkerをコンパイルしてEX5を生成し、警告・エラーを確認する。
2. 同じブローカー・期間・銘柄・初期資金・費用・80/15/5等の入力で、v2.43とv2.44のAUTOをMT5テスター実行する。
3. Total Trades、Win Rate、Profit Factor、Expectancy、Max Drawdown、Average R、パターン別Win Rate/PF、Portfolio Risk拒否数、SLSource別成績を比較する。旧版にないパターンログは履歴だけから推定しない。
4. デモのNetting/Hedgingで実約定・部分約定・遅延履歴、複数銘柄同時候補、AI待ち中の保有増加、FILE_COMMONのロック・保存失敗と復帰、再接続・再起動を確認する。
5. 建値・トレーリング・DD決済の実ExitReasonとCSV、裁量UI、テーマ・水平線/トレンドラインを確認する。
6. AIの実認証・利用可能モデル・応答遅延と、Fintokei契約プランの実際の規則・参照値を確認する。今回それらの適合性・有効性を実通信で検証していない。

総リスク上限は新規追加の制限であり、ギャップでSL約定が保証されるものではありません。勝率やPFの向上は未測定です。

## 再現・配布結果

```bash
python3 tests/run_all.py
```

個別には `verify_v244.py`、`verify_json_regression.py`、`verify_stats.py`、`audit_source.py` を実行できます。旧 `verify_v242.py` / `verify_v243.py` は互換エントリーとして全500模擬チェックを実行します。

旧ケースは `scenarios.cpp` / `new_scenarios.cpp`、追加ケースは `v244_scenarios.cpp`、CSV集計は `verify_stats.py`。監査の基準は `baseline_functions.json`、`v242_safety_baseline.json`、`v243_safety_baseline.json` と厳密なフック除去を行う `v244_audit_helpers.py` です。

`verification/integration_results.json` / `source_audit.json` に13ソースのSHA-256、`json_results.json` にJSON55ケース、`stats_results.json` に集計20ケースと集計ツールのSHA-256を保存しています。`SHA256SUMS.txt` は配布全体の検査用です。検証で生成したC++/Linuxバイナリ、開発用途中ZIPは配布ZIPに含めません。
