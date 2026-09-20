# v2.44 検証報告

## 2026-09-21：候補単位の最初の拒否理由を測定

PR #10をmainへマージした `bcb41c8f9f775b170154ecddebeb0f6624d947ca` から別branchで作業。製品変更はTester AUTO専用の読み取り専用診断で、売買条件・SL/TP・lot・risk・注文引数・input/defaultは変更していません。経路一覧、戻り値、status、計数定義は [ENTRY_DIAGNOSTICS_JA.md](ENTRY_DIAGNOSTICS_JA.md)、匿名の実測集計は [entry_diagnostics.json](verification/entry_diagnostics.json) を参照してください。

実機はPR #10と同じUSDJPY/M1、2026-06-01〜2026-09-01、real ticks、AUTO、OpenAI無効、COMBINED、MinimumSignalScore=70。inputファイルのバイト一致と実行EX5のhashを確認しました。前後とも **5,273,008 ticks / 94,267 bars / 100% real ticks / trades 0 / deals 0** です。

評価開始7,948,798回のうち、候補生成前のpattern_waitは7,881,602回。パターン選択後の候補評価67,196件はすべて最初の拒否で終了し、queue_passes・order_attempts・order_accepted・order_rejectedはいずれも0、診断欠落droppedも0でした。

| 最初の拒否理由 | 候補評価件数 | 全拒否67,196件に対する割合 | cost_or_stop_gate内の割合 |
|---|---:|---:|---:|
| ATR比spread上限 `spread_atr_limit` | 45,691 | 68.00% | 97.98% |
| 最終score不足 `score_below_threshold` | 20,565 | 30.60% | 対象外 |
| SLのStopsLevel/FreezeLevel距離 `sl_broker_gap` | 797 | 1.19% | 1.71% |
| fallback swingがentryの逆側 `swing_wrong_side` | 143 | 0.21% | 0.31% |

cost_or_stop_gate内は計46,631件。割合の丸めで合計に差が出る場合があります。固有パターン数や注文数ではなく、最終拒否後の再評価も別候補です。キュー内の再確認は重複候補にしません。

従来status遷移は **2,384回**で、PR #10の実測と同じ内訳でした（indicator_wait 0 / pattern_wait 1,106 / cost_or_stop_gate 798 / score_below_threshold 479 / weighted_agreement_or_opposition 0）。798回と46,631件は異なる母数です。新診断の理由別集計からstatus遷移を推定していません。

修正前の[Red CI](https://github.com/27c7nmt5m8-coder/EA/actions/runs/35536019568)では既存取引fixtureが通り、新規の集計出力欠落を検出。診断追加後の[CI](https://github.com/27c7nmt5m8-coder/EA/actions/runs/35536412172)はmock712 / JSON55 / CSV20 / 静的495 / 13ソース照合成功。その後、診断ON/OFFの注文引数一致と構造SL失敗後のfallback回復に関する追加検証を行っています。最終HEADの全体ゲート結果はPRの最新CIに対応付けます。既存baselineのhash・テストは維持しています。

MetaEditor 5.0.0.6182で本体・Workerとも **0 errors / 0 warnings**。対象ソースとEX5のSHA-256は [native_compile.json](verification/native_compile.json) に記録しています。過去日付の同梱検証結果は歴史的記録です。

0取引の直接経路は測定できましたが、閾値の適切さ、ブローカーのStopsLevel/FreezeLevelへの仕様上の対応、個々のfallback生成値が意図どおりかは未評価です。数値分布や構造SLからfallbackへ移る途中理由、pattern_waitの内部選択理由は今回の集計対象外です。売買結果に影響する修正や最適化は別途レビューが必要です。実ブローカー発注・実AI/API・実運用の再接続/再初期化/同時owner lockは **NOT_MEASURED**。今回の実機バックテストを実口座の安全性や収益性の保証とは扱いません。

## 2026-09-20：指標要求順序の修正

非ビジュアルの実機テスターで取引数0を再現し、診断statusが指標待機から進まないことを確認しました。権限・履歴・MC・未解決注文のgateではありません。`ReadIndicator` が `BarsCalculated` の未計算判定で戻るため、要求時に計算を開始する `CopyBuffer` へ到達しませんでした。MQL5公式仕様に合わせて呼び出し順序の1行だけを変更し、取得値の検証・7時間足すべての準備条件・売買仕様は維持しています。

mockの要求時計算で修正前に回帰テストが失敗し、修正後は全体ゲート582/55/20/495/13が成功しました。追加は初回読み取り・7時間足の準備・履歴不足・不正ハンドル・バー不足・EMPTY_VALUEの回帰確認です。MetaEditor 6182で本体・Workerとも0 errors / 0 warnings。最新ソースに対する結果は [native_compile.json](verification/native_compile.json) を参照してください。

実機比較も2026-06-01〜2026-09-01、USDJPY/M1・AUTO・OpenAI無効・実ティック・同一入力で完了しました。前後とも5,273,008ティック・94,267バーを処理し、指標待機は修正版で解消しました。ただし取引数は前後とも0です。修正版はパターン、スコア、価格・コスト・SL形状等の後段gateまで進んでおり、取引数0の全要因が解消したとは扱いません。個人ログを含まない集計と対象ソースSHAは [indicator_demand.json](verification/indicator_demand.json) に記録しています。診断件数はstatus遷移数で、独立した候補・拒否・取引数ではありません。次の調査は後段の複合gateの内訳確認であり、条件緩和は行いません。

以下は診断追加時点の記録です。既存の `integration_results.json`、`source_audit.json`、`validation_summary.json` 等は当時のソースSHAに対応する履歴として保持します。

実施日: 2026-09-13（オフライン診断検証）、2026-09-20（最新mainへの統合・ネイティブコンパイル）

**配布する実ソースの模擬実行573チェック（既存565＋Strategy Tester診断8）、JSON回帰55チェック、既存静的監査495チェック、CSV集計20チェック、13ソースの差分照合が通過しました。MetaEditor 5.0.0.6182で本体・Workerとも0 errors / 0 warningsを確認しました。診断版の実機Strategy Tester・実際のAI API通信は未実測で、EX5は同梱していません。**

件数には初期化、方向違い、倍率違い、同一試験内の複数確認を含みます。573件の独立した相場シナリオや、収益性の検証という意味ではありません。

## Strategy Tester診断ログの追加検証

Strategy Testerで取引数0が継続する場合に、売買条件を変更せず停止地点を特定できるよう、テスター時だけstatus変化を `[MT3 TESTER DIAG]` として出力します。同一statusの連続出力は抑制し、実運用ではこの診断を出力しません。診断には接続・売買許可、履歴、Monte Carlo状態、RiskMode、サンプル数、未解決注文、既存エクスポージャなどの読み取り専用状態を含めます。

追加8チェックで、テスターの拒否status記録、同一statusの重複抑制、次段階statusへの更新、実運用で診断状態が変化しないことを確認します。13ソース差分監査では診断用フィールド・初期化・診断関数・呼び出しだけを厳密に投影して既存配布ソースと比較します。

2026-09-20のネイティブ結果と対象13ソースのSHA-256は [native_compile.json](verification/native_compile.json) に記録しました。既存の `validation_summary.json` 等は2026-09-13時点の記録です。コンパイルは作業用コピーで行い、端末へ導入・実行していません。

取引数0の再現では、元の銘柄・期間・M1・AUTO・入力設定・費用条件を維持し、`[MT3 TESTER DIAG]` のstatus遷移と最初の拒否理由を確認します。権限・履歴・MC等を通過した場合は、パターン・スコア・方向一致・同一M1バー等の既存gateへ追跡します。このログはJournalSample時点の状態であり、全gateの通過履歴やカウンターではありません。原因不明の段階で条件を緩和しません。個人ログ・口座情報はGitHubへ掲載しません。

2026-09-20には既存の再現設定（2026-06-01〜2026-09-01、USDJPY/M1、AUTO、OpenAI無効、実ティック）を用いて隔離したMT5で再実行を試みました。認証情報を移さない環境では `tester not started because the account is not specified` によりEA実行前に終了したため、Strategy Tester結果は未実測です。次は口座設定済みのMT5のテスターで同条件を実行し、診断statusから停止gateを特定します。この環境制約をEA不具合や取引数0の再現成功として数えません。

## Strategy Tester接続判定の追加検証

`EntryPreflight()` は実運用では引き続き `TERMINAL_CONNECTED` を要求しますが、`MQL_TESTER` のときだけライブ接続要件を除外します。端末・MQL・口座の売買許可、未解決注文、総ポートフォリオリスクなど他の安全判定は維持します。

既存543チェックに22チェックを追加し、未接続テスターの適格候補が `OnInit → OnTimer` で模擬注文へ進むこと、未接続の実運用は注文しないこと、再接続後は進めること、テスターでも売買許可・総リスク・未解決注文の拒否が残ることを確認します。静的監査では接続式を厳密に旧式へ投影して既存ハッシュと比較し、他のEntryPreflight内容をマスクしません。

**この統合状態のMetaEditorネイティブコンパイルは2026-09-20に確認済みです。実機Strategy Testerバックテストは未実測です。**

## 今回の基点・不具合再現・修正範囲

今回の基点は添付 `MTFAutoTrader_3Mode_AI_v2_44_Package.zip` です。

```text
SHA-256: eac671507e4ba8b36a96a61fcb7af6b346242b54cf48bd7c83bdb7036a36d4c6
```

このZIPの `GlobalVariableTemp()` mockは既存変数でもtrueを返し、実機で発生した再初期化障害を隠していました。既存変数ならfalse／エラー4502を返すmockへ先に修正し、製品ソースを変更する前にSymbolState、チャート変更後の本体、注文mutex、Worker、Fintokeiの再取得失敗を個別に再現しました。厳密化したmockでは既存テスト一式も `symbol init` で失敗しました。修正前結果は `lock_regression_before.json` に保存しています。

4か所に存在確認ガードを加え、値0の既存ロックはCAS（`GlobalVariableSetOnCondition(key,1,0)`）で再取得、値1は拒否するようにしました。Checkと作成の間に他インスタンスが作成して作成処理が失敗する場合も、安全側に取得を拒否します。取得のためのDeleteや強制0書込みは追加していません。既存の解放処理も変更していません。

添付ZIPには前回の警告対策が未適用だったため、`UpdateAutoTrendLines()` の8変数の宣言時初期化を再反映しました。`verify_lock_scope.py` は、今回の4条件とこの8宣言だけを逆変換した全13ソースを、添付ZIPのSHA-256とバイト単位で照合します。変更ファイルはSymbolState・本体・Workerの3ファイル、残り10ソースはそのままです。売買ロジック・注文引数・スコア・SL・リスク計算・入力・バージョンは変更していません。過去の監査用ハッシュも更新せず、厳密に一致した今回の差分だけを監査時に戻しています。

## 今回追加したロック回帰

| 試験グループ | チェック数 | 確認内容 |
| --- | ---: | --- |
| mock仕様 | 3 | 新規0作成、既存0／1のfalse・4502、既存値維持 |
| SymbolState | 5 | Init→Shutdown→同一オブジェクト再Init、別オブジェクトで同一銘柄再Init |
| 本体の時間足変更 | 5 | 2銘柄のOnInit→OnDeinit(REASON_CHARTCHANGE)→OnInit、連続切替 |
| 注文実行mutex | 4 | Acquire→Release→再Acquire、再入拒否、値0の変数を保持 |
| Worker | 4 | Init→Deinit→再Init、owner・プロトコル・登録の復帰 |
| Fintokei | 4 | controllerと2銘柄の再初期化、終了後の値0保持 |
| 競合・非所有者の終了 | 13 | 4ロックの値1を保持する先行所有者に対する拒否、失敗側の終了で先行所有権・Worker稼働状態を壊さない |
| 取得失敗 | 5 | 各ロックの作成失敗、注文mutexのCAS失敗で所有フラグを立てない |
| 合計 | 43 | 既存500と合わせて543チェック |

`v244_lock_scenarios.cpp` は実際の製品関数をC++アダプター経由で呼びます。SymbolStateは独立した2オブジェクトを使用し、本体／Worker／実行mutexはインスタンスごとの所有フラグや状態配列を切り替え、端末Global Variableを共有する2インスタンス相当の条件で検証しています。実MT5の複数EAスレッドを並行実行した試験ではありません。修正後のグループ別結果は `lock_regression_after.json` に保存しています。

MetaEditor／MT5／Wineが利用できないため、**本体・Workerのネイティブ `0 errors / 0 warnings`、実際のチャート時間足切替、複数EAの実機競合は未実測**です。これらの最終確認はユーザー実機で行ってください。

## v2.44初回機能追加の基点・今回の検証環境

v2.44初回機能追加時の基点は `MTFAutoTrader_3Mode_AI_v2_43_Package(1).zip` です。

```text
SHA-256: 86d92447782e8bc72ce28264b2c8040c41b46040248948b234912ca4ea97e00a
```

初回開発時は元のv2.43で326チェックの通過を確認し、v2.44で174チェックを追加しました。今回は、その既存500（v2.42由来207＋v2.43追加119＋v2.44追加174）を削除せず、修正版に対してすべて再実行しました。共通resetにはmockエラー状態の初期化を追加しています。

Linux、Python 3、g++ C++17を使用しました。MT5/MetaEditor/Wineが利用できないため、本体・全include・Workerを展開してMQLの配列・UTF-16文字列・クラス参照等をC++へ適応し、MT5サービスを模擬して実ソースを実行しました。判定関数を別言語に複製したものだけを試験したわけではありません。

価格、指標、履歴、注文、SL変更、チャート、ファイル、イベント、HTTPは模擬実装です。C++アダプターのコンパイルエラーは0。短い複数文行のインデント、未使用引数・変数等の警告が31件あります。これはMetaEditorでのコンパイル結果ではありません。

## 結果

| 区分 | 結果 | 内容 |
| --- | --- | --- |
| 本体・Worker模擬実行 | 573 / 573 | 既存565＋Strategy Tester診断8 |
| JSON回帰 | 55 / 55 | 厳格JSON、UTF-16、Responses回答状態・schema |
| ソース監査 | 495 / 495 | 既存監査の継承、変更関数の限定、総リスク・SL・ログ監査 |
| オフラインCSV集計 | 20 / 20 | 独立した数値例、重複・不正・不明値・データセット分離 |
| 今回のソース差分照合 | 13 / 13 | 4ロック条件＋8宣言初期化＋テスター接続例外＋診断追加だけを厳密に逆変換して照合 |
| `_Symbol` 全検索 | 1か所 | 本体OnInitの設置先取得のみ |
| `_Point` / `_Digits` / `_Period` / `PERIOD_CURRENT` | 実行ソースに残存なし | 新モジュールも銘柄別参照 |
| ネイティブMQL5コンパイル | 本体・Workerとも0 errors / 0 warnings | MetaEditor 5.0.0.6182、EX5は配布対象外 |
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
- v2.43エンジン171関数のうち、初回v2.44で変更した11関数を除く160関数を照合。今回の `UpdateAutoTrendLines()` の8初期化だけを厳密に元へ戻すと、160関数のSHA-256が旧基準と一致する。今回のInitの存在確認ガードも旧版監査時だけ厳密に戻して照合する。
- v2.42由来162関数の比較も保持。そのうち6関数は追加された分析フックだけを厳密なテキスト一致で除去してから旧ハッシュへ照合し、元の保護計算・条件・注文引数の一致を確認。
- `MT3Types`、`MT3Scoring`、`MT3ReversalPatterns`、`MT3AIProtocol`、`MT3Json` はv2.43のモジュール全体と一致。既存inputの宣言・初期値をすべて保持し、新しいinputは総リスク2個＋EnableTradeLogの3個のみ。
- コントローラは既存の分析フックと今回の2ロック存在確認ガードを厳密に除いて旧版と比較。Workerは今回のowner存在確認ガードと表示バージョンを戻すと旧版と一致する。プロトコル242、request/response schema、状態キーsalt、Magic/銘柄・口座予約スコープは変更なし。
- 注文直前の総リスク再計算と鮮度再確認の順序、SLの外向き丸め、分析I/Oから注文承認へ戻り値を接続しないこと、重要保存失敗の発注停止を監査。
- 公式のOrderCalcProfit、Position/Deal properties、FileFindFirst/FileMove仕様を参照し、口座通貨計算・64bit識別子・FILE_COMMONの使用を確認。

比較は変更範囲の限定を確認するものです。旧版の未知の不具合やネイティブMQL固有の型規則、ブローカー固有仕様がないことを証明するものではありません。将来変更する場合、監査の除外範囲を雑に広げず、追加フックと試験内容を再レビューしてください。

## 実機で残る確認とv2.43比較

1. MetaEditorで本体とWorkerをコンパイルして `0 errors / 0 warnings` を確認する。複数銘柄でM1→M5→M15→M1等の時間足変更と再設置を行い、EAが残ることを確認する。FintokeiとWorkerも再初期化し、先行インスタンス稼働中の2つ目が拒否されることを確認する。
2. 同じブローカー・期間・銘柄・初期資金・費用・80/15/5等の入力で、v2.43とv2.44のAUTOをMT5テスター実行する。
3. Total Trades、Win Rate、Profit Factor、Expectancy、Max Drawdown、Average R、パターン別Win Rate/PF、Portfolio Risk拒否数、SLSource別成績を比較する。旧版にないパターンログは履歴だけから推定しない。
4. デモのNetting/Hedgingで実約定・部分約定・遅延履歴、複数銘柄同時候補、AI待ち中の保有増加、FILE_COMMONのロック・保存失敗と復帰、再接続・再起動を確認する。
5. 建値・トレーリング・DD決済の実ExitReasonとCSV、裁量UI、テーマ・水平線/トレンドラインを確認する。
6. AIの実認証・利用可能モデル・応答遅延と、Fintokei契約プランの実際の規則・参照値を確認する。今回それらの適合性・有効性を実通信で検証していない。

総リスク上限は新規追加の制限であり、ギャップでSL約定が保証されるものではありません。勝率やPFの向上は未測定です。

## 再現・配布結果

以下は継続開発時のテスト手順です。上記の件数・環境・実機確認リストは各修正時点の記録であり、文書変更を含む毎作業の必須試験ではありません。実行範囲・確認・PRの判断基準は [AGENTS.md](AGENTS.md#テスト実機検証) を参照してください。

リポジトリ直下で、変更箇所に直接関係する行から選び、影響範囲に応じて関連テストへ広げます。Python 3を使用し、`python3` がない環境ではPython 3の `python` または実行ファイルのパスに読み替えます。

| 変更・確認対象 | コマンド | 依存環境・範囲 |
| --- | --- | --- |
| ロック・再初期化の特定箇所 | `python3 tests/verify_v244.py symbol` | Python 3＋g++（C++17）。グループ名は下記参照 |
| EA本体・Worker・共有ヘッダー、テスター接続判定 | `python3 tests/verify_v244.py` | Python 3＋g++。実ソースをC++17に変換した全mock試験 |
| JSON・Worker通信schema | `python3 tests/verify_json_regression.py` | Python 3＋g++。JSON回帰。通信経路への影響は全mock試験も確認 |
| CSV集計ツール | `python3 tests/verify_stats.py` | Python 3のみ。独立した数値fixtureによる集計確認 |
| ソース構造・既存安全仕様の保持 | `python3 tests/audit_source.py` | Python 3のみ。静的監査 |
| 承認済み修正以外のソース差分 | `python3 tests/verify_lock_scope.py` | Python 3のみ。13ソースの厳密な差分照合 |

全体検証は次を使います。GitHub ActionsもUbuntu、Python 3.11、g++で同じ5ゲートを実行します。ローカルにg++がなければPythonのみの3ゲートを実施し、C++依存の2ゲートはCI等で確認します。`run_all.py` は最初の失敗で終了するため、後続ゲートを合格と解釈しないでください。

```bash
python3 tests/run_all.py
```

旧 `verify_v242.py` / `verify_v243.py` は `verify_v244.py` への互換エントリーです。同じ試験を重複実行する必要はありません。ロックのグループ指定は mock / symbol / chartchange / execution / worker / fintokei / contention / failure のみ対応し、指定時は全件結果のJSONを上書きしません。Strategy Tester接続判定はグループ指定では実行されないため、引数なしの全mock試験で確認します。

`verify_lock_scope.py` は4ロック条件・8宣言初期化・テスター接続式1か所・診断用フィールド/初期化/関数/呼び出し・指標要求順序1か所だけを厳密に逆変換し、元ZIPの全ソースと比較します。意図した製品変更でもこの固定基準は失敗し得ます。失敗を隠すために基準ハッシュや除外範囲を広げず、明示的に承認された仕様変更に必要な基準更新だけを理由・回帰テストとともにレビューします。

旧ケースは `scenarios.cpp` / `new_scenarios.cpp` / `v244_scenarios.cpp`、今回の追加ケースは `v244_lock_scenarios.cpp`、CSV集計は `verify_stats.py`。監査の基準は `baseline_functions.json`、`v242_safety_baseline.json`、`v243_safety_baseline.json` と厳密な差分投影を行う `v244_audit_helpers.py` です。添付ZIPの全13ソースの基準は `v244_lock_fix_baseline.json` に保持しています。

`verification/integration_results.json` / `source_audit.json` に13ソースのSHA-256、`json_results.json` にJSON55ケース、`stats_results.json` に集計20ケースと集計ツールのSHA-256を保存しています。`SHA256SUMS.txt` は配布全体の検査用です。検証で生成したC++/Linuxバイナリ、開発用途中ZIPは配布ZIPに含めません。
