# Tester AUTOのエントリー拒否診断

基点: PR #10をマージしたmain `bcb41c8f9f775b170154ecddebeb0f6624d947ca`。
PR #10は指標要求順序の修正であり、0取引全体の解決ではない。本診断も条件緩和・最適化を行わない。

## 測定単位

- **status transition count**: 従来の `[MT3 TESTER DIAG]` が観測したstatus文字列の変化。同じ分類内のスコア文字列変化も含む。候補数ではない。
- **evaluations**: `RefreshCandidate()` の評価開始回数。候補生成前のpreflight、指標待機、パターン待機を含む。
- **entry candidate count / candidates**: AUTOの `SelectReversalPattern()` 成功後に評価する候補数。キュー内の同一M1バーの再確認は同じ候補IDを使う。最終拒否後の次の評価は新IDとするため、固有パターン数・固有M1バー数ではない。
- **rejection count / rejections**: その候補評価の最初の最終拒否を1回だけ数える。後から別の理由で上書き・加算しない。候補生成前の拒否は `pre_candidate/` に別集計する。
- **queue_passes**: ローカル評価を通ってキューへ入った候補数。再確認は重複加算しない。候補が通った後、発注前の再確認で拒否されることはある。
- **order attempt count / order_attempts**: 実際に `trade.Buy/Sell` を呼んだ回数。DispatchCandidateの呼び出し回数でも永続化したattempt.barの件数でもない。
- **order_accepted / order_rejected**: CTradeのbool結果と既存のDONE / DONE_PARTIAL / PLACED判定による発注応答数。acceptedは約定成功数ではない。特にPLACEDは受理のみで、後続照合を要する。
- **trade count / deal count**: MT5 Strategy TesterレポートのTotal Trades / Total Deals。上記カウンターから推定しない。

診断は `MQL_TESTER && ExecutionMode==EXECUTION_AUTO` のみ。新input・保存キー・ファイル・CSV列はない。実運用、MANUAL、AI/HYBRIDの候補集計は対象外で、既存のテスター制限も変更しない。

`[MT3 ENTRY SUMMARY]` はShutdown時の累計、`[MT3 ENTRY REASON]` は `candidate|pre_candidate / stage / first_reason` ごとの累計。`[MT3 ENTRY FIRST]` は各分類の初回例のみ、`[MT3 ENTRY ORDER]` は候補ID付きの発注と応答。大量の候補ログを出さず、候補IDはシンボル内・SymbolState生存期間内の連番とする。再初期化を跨ぐ集計ではrun/instanceを分け、同じ累計出力を重ねて足さない。

`dropped` が0でない場合は診断用配列の確保失敗があり、理由別集計を完全とは扱わない。診断失敗で発注を承認・拒否しない。異常終了でShutdownが呼ばれなければ最終集計は未取得とする。

## cost_or_stop_gateに到達する実経路

`src/MT3SymbolState.mqh::RefreshCandidate()` はpreflight、M1制約、7時間足準備、パターン選択、方向・既使用判定、最終scoreを通過した後、以下を左から短絡評価する。

`SymbolDirectionAllowed → FreshQuote → BuildEntryStops → SpreadOK → PatternEntryLocationOK`

どれかがfalseなら、戻り値は従来どおりfalse、statusも **Quote / relative cost / stop geometry blocks entry** のまま。下表の診断は、そのfalseを生んだ既存の最初の条件を記録する。成功したfallbackの途中失敗は候補拒否に数えない。

| ファイル・関数 | 既存の拒否条件 → 詳細理由 | 戻り値 | 段階・位置づけ |
|---|---|---|---|
| MT3SymbolState.mqh / SymbolDirectionAllowed（呼出側） | FULLでも要求方向のLONGONLY/SHORTONLYでもない → `symbol_direction` | false | キュー前・銘柄売買権限 |
| 同 / FreshQuote | SymbolInfoTick失敗 → `quote_unavailable`、非数bid/askまたはbid<=0 → `invalid_bid` / `invalid_ask`、ask<bid → `invalid_bid_ask` | false | キュー前・価格の安全確認 |
| 同 / FreshQuote | time_msc<=0 → `quote_timestamp_missing`、serverMs<=0 → `server_time_missing`、serverMs+1000超の未来quote → `quote_from_future`、ageLimit超 → `quote_stale` | false | キュー前・価格鮮度の安全確認 |
| 同 / BuildStops | swing探索失敗 → `swing_not_found`、iLowest/iHighestのshift<1 → `swing_index_missing` | false | SL fallback・既存の構造SL仕様 |
| 同 / BuildStops | swing価格<=0 → `swing_price_invalid`、買いでprice>=entry／売りでprice<=entry → `swing_wrong_side` | false | SL fallback・構造位置の仕様／安全確認 |
| 同 / BuildStops | 買いTP<bid+minDistance／売りTP>ask-minDistance → `tp_broker_gap`、最終sl<=0／tp<=0 → `invalid_sl` / `invalid_tp` | false | SL fallback・既存生成結果の検証 |
| MT3PatternStops.mqh / EntryStopsValid | tick size<=0 → `tick_size_invalid`、非数または非正のSL/TP → `invalid_sl` / `invalid_tp`、bid<=0／ask<bid → `invalid_bid` / `invalid_bid_ask` | false | 構造SLまたはfallback後・安全確認 |
| 同 / EntryStopsValid | SL/TPがtick刻みに整列しない（既存許容差1e-6）→ `sl_tick_alignment` / `tp_tick_alignment` | false | ブローカー価格刻み |
| 同 / EntryStopsValid | SLがentryの正しい側にない → `sl_wrong_side` | false | SL側の仕様／安全確認 |
| 同 / EntryStopsValid | SLまたはTPが既存gapを満たさない → `sl_broker_gap` / `tp_broker_gap`。gap = max(StopsLevel, FreezeLevel) * point + tick、eps = tick * 1e-8。元の買い／売り別bid/ask基準を維持 | false | ブローカー距離の安全確認 |
| MT3SymbolState.mqh / SpreadOK | ATR<=0 → `spread_atr_unavailable`、spread<0 → `invalid_spread` | false | コスト計算の前提 |
| 同 / SpreadOK | spread > ATR*MaxSpreadATR+tick余裕 → `spread_atr_limit`、有効なMaxSpreadPoints超 → `spread_points_limit` | false | 既存コスト仕様 |
| 同 / SpreadOK | sl>0のときdistance<=0 → `sl_distance_zero`、spread > distance*MaxSpreadSL+tick余裕 → `spread_sl_limit` | false | SL距離に対する既存コスト仕様 |
| MT3ReversalPatterns.mqh / PatternEntryLocationOK | 新規反転パターンに限り、!valid → `pattern_invalid`、triggerTime不一致 → `pattern_bar_stale`、buySignal不一致 → `pattern_direction_mismatch` | false | パターン／確定M1の仕様 |
| 同 / PatternEntryLocationOK | ATR<=0 → `pattern_atr_unavailable`、referencePrice<=0 → `pattern_reference_invalid` | false | パターン価格の前提 |
| 同 / PatternEntryLocationOK | entryがreferencePriceの正しい側にない → `pattern_entry_wrong_side` | false | 既存ブレイク条件 |
| 同 / PatternEntryLocationOK | failed breakoutでreferencePriceから0.35*ATR+tick余裕を超える → `failed_breakout_price_drift` | false | 既存追い掛け価格制限 |

FreshQuoteの単調時計による受信鮮度条件は実運用のみであり、Tester専用診断へ架空の観測件数を追加しない。

### 構造SLからfallbackへの経路

`MT3PatternStops.mqh::PatternStopAnchor()` は無効パターン、方向不一致、ピボット欠落、未対応type、非数/非正anchorでfalseを返す。その理由は既存fallback文字列に残り、直接の候補拒否ではない。

`BuildEntryStops()` は上記に加え、ATR/buffer不足、anchorの逆側、EntryStopsValidの失敗、SLがanchor外側でない場合にも既存のgeneric swing fallbackを試す。途中の診断理由を復元してから `BuildStops → EntryStopsValid` を評価し、この最終失敗だけを記録する。SLを広げる／fallbackを削るなどの変更はしない。

## cost_or_stop_gateの外側

以下を798回の大分類へ混ぜない。元のstatus、戻り値、順序は維持する。下表は追加診断の対応範囲で、全ブローカーretcodeの意味を推測して細分化しない。

| ファイル・関数 | 拒否経路と診断 | 既存status／戻り値 | 段階・位置づけ |
|---|---|---|---|
| MT3SymbolState.mqh / EntryPreflight | universe、実行mode、account/symbol unresolved、既存exposure、権限、履歴、MC、リスク上限をそれぞれ区別 | 既存の各専用status、false | 候補前または発注再確認・仕様／安全装置 |
| 同 / RefreshCandidate | `bar_or_ai_lock`、`indicator_wait`、`pattern_wait` | status維持または従来専用status、false | 候補生成前。pattern_waitは未検出のほか、既存選択関数の方向競合・適格性拒否等も含む |
| 同 / RefreshCandidate | `pattern_consumed`、`weighted_agreement_or_opposition`、`entry_direction`、`score_below_threshold`、`snapshot_changed` | status維持または従来専用status、false | 選択後・売買仕様／スナップショット安全確認 |
| 同 / ExecuteEntry | `execution_lock` | Account execution busy、false | mutex取得。owner lockのInit拒否は候補生成前で従来ログを使用 |
| 同 / ExecuteEntryLocked | direction、pattern既使用、preflight、M1重複、quote、AI鮮度、spread/location、risk、stop、portfolio、lot、OrderCheck、準備中価格変化、永続化、送信直前再確認、注文結果 | 従来status／false。理由が下位関数で確定していればそちらを保持 | キュー後・発注安全確認。複合条件は新たに再計算せず、既存構造で確定できる粒度のみ |
| 同 / CalculateLotByRisk・NormalizeVolume | risk<=0、broker最小lot不正、exit不正、OrderCalcProfit失敗、lossPerLot<=0、lot step不正／最小未満／丸めで要求超、OrderCalcMargin失敗、margin縮小後最小lot未満 | 0、上位ではLot below minimum or insufficient margin／false | サイジング・資金管理。`insufficient_margin_min_lot` は既存margin縮小の結果が0の場合のみ |
| MT3PatternStops.mqh / CheckPortfolioEntry | `portfolio_unknown`、`planned_risk_unknown`、`portfolio_risk_limit` | PORTFOLIO RISK REJECT:既存理由、false | 発注前およびmutex内再確認・安全装置 |

lot>maxは既存NormalizeVolumeで上限へ丸められ、独立した拒否ではない。RR不正は起動時ValidateInputsの領域で、この候補経路に独立したinvalid_rr判定はない。委託手数料は既存のrisk sizingに入るが、独立したcost_filter_rejectという条件はない。存在しない分類を追加しない。

## 変更範囲と検証

製品コードはMT3SymbolState.mqh、MT3PatternStops.mqh、MT3ReversalPatterns.mqhの診断状態、結果をそのまま返す観測関数、既存分岐への観測呼び出しのみ。SL/TP、score、pattern、lot、risk、注文引数、callの短絡順序、閾値、input/defaultは維持する。Worker・JSON・CSV契約は変更しない。

`tests/entry_diagnostic_projection.json` に逆変換前後を全文で明記し、各hunkが1回だけ存在することを検査する。これを逆順に投影した後も、既存の静的495件・13ソースの旧ハッシュ照合を継続する。baselineは更新しない。任意の診断名を正規表現で消して許可する方式にはしない。

回帰テストは実製品の各gateを呼び、主要理由、最初の拒否の保持、二重加算防止、キュー再確認、fallback回復、診断ON/OFFの注文パラメータ一致、従来status、permission・MC・portfolio・unresolved・mutexの拒否を確認する。修正前CIは集計出力欠落で失敗した。最新の実測結果と未実測事項はVALIDATION_JA.mdおよびverificationの匿名集計を参照する。
