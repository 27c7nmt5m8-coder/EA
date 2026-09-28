# PR17最終確認と初期測定の分解

2026-09-28時点のPR17 headは120d251b41196eefa269b76c2e5d63f6a59c63ae、mainは9f9c55379eb9298035b90d210d0158ac02cbe058。src、既存CI、AGENTS/Skill、製品仕様、既存testsは変更なし。EA13ソースを含む既存39ファイルとCodex configの保存済みSHA-256に一致した。PR17のpush/PR CI両方のLinux/Windows成功、同一commitの全体offline PASSを再確認した。MetaEditor/実機releaseは未検証。mainはマージしない。

## 出力20.30%増加

holdoutの出力は1084→1304、差220、1件平均54.2→65.2（+11）。High群265→351（+86）、xHigh群819→953（+134）。calibrationも468→563（+95）。Bだけ推論effortを上げたことが原因ではなく、両側で一致している。

回答は既にrouteだけのJSONで、説明文を長くする指示はない。[公式token定義](https://developers.openai.com/api/docs/guides/token-counting)ではreported outputは可視本文以外の生成も含む。元のCodex CLI usageでは可視/内部生成を十分に分解できず、normalizationのreasoning=0は未提供フィールドの既定値であり「内部生成なし」の証拠ではない。

context短縮による推論量変化、単回生成の変動、prompt/data配置の影響は仮説。主因を断定しない。必要context不足を追加取得した後の未解決欠落は0だったが、これも生成量の因果説明ではない。実タスクでは元usageフィールド、提供されたreasoning値、可視JSON文字数、判定・finding・context要求を記録する。

effortを下げたり、max outputで推論/重要指摘を切ったりしない。重複した状況説明・既知PASSの再説明を回答schemaから除き、実レビューはverdict/findings/missing_contextだけにする。[verbosityの公式説明](https://developers.openai.com/api/docs/guides/deployment-checklist)は出力形式の調整とreasoning effortを区別する。短い定型JSONだった初期試験にverbosity変更だけで同じ効果があるとは主張しない。現段階で品質維持の出力削減率は未確定。

## 全provider削減4.67%の算式

| 要素 | tokens | A総324375に対する寄与 |
|---|---:|---:|
| input除去 | 19860 | +6.12254ポイント |
| output増加 | 220 | -0.06782ポイント |
| JEV追加 | 4502（input4122/output380） | -1.38790ポイント |
| 最終削減 | 15138 | 4.66682% |

inputの6.1431%はA input323291が分母。総tokensの寄与とは分母が異なる。主要な相殺は出力増加よりJEV追加で、JEV込み処理時間改善も約0.6%。JEVの金額は出力無料の入力単価から小さいため、tokens/時間/費用を同じ尺度にしない。

85%は必須Sol10/20＋残る10件のshadowエスカレーション7/10。7件はreview判定4（H03/H04/H06/H10）とcandidateでもconfidence不足3（H05=.77/H07=.46/H09=.89）。候補3はH01=.94/H02=.92/H08=.90。低リスク群内のエスカレーション率は70%。全20件をSolでレビューしたので85%はcounterfactualで、4.67%を生んだのはレビュー省略ではない。

残る必須50%をconfidenceで迂回しない。低リスクでも要件未達・曖昧さを解消する必要がある。関連interface/境界条件を明示し、JEV stateの対象・変更前後・要件を整理する条件を今後の実タスクで試す。閾値0.90は下げない。決定論的に明白なPASS/FAILではJEVを呼ばず通常Solへ進める候補は、不要なJEV処理だけを減らす。重要群の判断はJEVへ移さない。

品質を保持した実タスク削減率は、必要サンプル・独立監査が揃うまで未確定。架空20件から現行EA開発全体の率を推定しない。

## 実PRレビューの初回観測

ユーザーの追加許可に従い、PR11とPR12を各1件の新しいレビュー作業として登録した。元の実装やその再修正を今回実施したとは扱わない。対象headはPR11 `56f4805e57c48cc611a87174ea2abecc5950a044`、PR12 `2f8e6e6bd1290873b0bfcec027363488760684f2`。両PRとも重要群のため全armでSol xHigh、JEV呼出なし、省略なし。

Aはdiff・変更ファイル全文・直接関連ソース/README、Bも必要ソース・依存・README・全diffを維持し、関連性の低い履歴/保存済み検証JSONの全文を省いた。公開Actionsの `actions/...@vX` 表記は秘密検出の誤一致を避けて両側とも `actions/... (public version vX)` と表現した。元のEA/CIは編集していない。PR11はA→B、PR12はB→Aで実行した。

| 実タスク/arm | status・判定 | input | output | total | 秒 |
|---|---|---:|---:|---:|---:|
| PR11 A | UNKNOWN、判定取得不可 | 202130 | 6657 | 208787 | 207.074 |
| PR11 B | UNAVAILABLE | 未取得 | 未取得 | 未取得 | 300.038 |
| PR12 A | UNAVAILABLE | 未取得 | 未取得 | 未取得 | 300.048 |
| PR12 B | OK、verdict=unknown | 168226 | 8574 | 176800 | 263.570 |

4回試行、観測完了turnは2、正確なbackend call数は不明。有効A/Bペア0件、独立依頼記録2件、監査完了0件。UNAVAILABLE2回は初回wrapperの300秒相当で終了したが、保存済み計測に診断コードがないため正確な理由は断定できない。PR11 AのUNKNOWNの原因も区別不能。既知tokens subtotalは385587、未取得2試行を含む総量・料金は不明。A時間subtotal507.121秒、B563.608秒は異なる成功/失敗を含み、性能比較の根拠にしない。計測制御・追加証拠確認のusage/時間も未計測で、全タスク削減率は不明。

PR12 Bのreported reasoningは8251/8574 output、可視JSONは1403文字。PR11 Aは6214/6657で可視文字数未取得。大部分がreasoningの内数であり、可視回答の圧縮だけで出力を大幅削減できる根拠はない。この別タスク2件から初期holdoutの20.30%増加の原因を逆算もしない。

PR12 Bはテストcoverageのimportant指摘1件、minor1件、不足context要求4件を返した。静的な追跡では、Fintokei有効化がsetup後でday guardに触れること、trend fixtureはM1を供給する一方でLineTimeframeの既定値がM15であることを確認した。実行での再現・網羅的監査は未完了なので、確定した製品不具合やfalse negativeのラベルにはしない。EAを修正しない。

要求されたCI run35557540186のjob結果とログを追加確認し、checkout SHAがPR12 headと一致、offline-validation成功、753シナリオ/55 JSON/20 stats/495静的assertions等の成功記録を確認した。この後続取得1件は初回A/B入力へ戻して再評価していないため、初回のcontext再取得0件と区別する。native compiler生ログのprovenanceとMT5 UI/Strategy Testerの実測証拠は未確認で、4要求すべてが解決したとは扱わない。初回の必要context欠落要求はPR12で4件、PR11は判定取得不可のため不明。

今回のshadowエスカレーション率は2/2=100%、JEV一致率は対象0件で未定義。再修正・テスト失敗・A/B false negative・critical見逃しは未取得/未監査でnull。「critical見逃しなし」とは報告しない。context再取得率0%は初回呼出内で追加取得しなかったという観測であり、contextが十分だったことを意味しない。

structured output・診断コード・待機上限の改善を今後の実作業に使用する。同じPRの無条件再実行で費用や件数を増やさない。最低30件・目標50件には未達で、品質を維持した実タスクのinput/output/総tokens削減率はすべて未確定。週次集計と承認された実作業ごとの記録を継続する。

## 補助ツールの追加検証

追加実装の独立Sol xHighレビューでimportant 5件を受領した。EA recordのmandatory flag迂回、nested usage/provenanceへの生文字列混入、無効pairでの既知usage消失、成功/attempt数/欠測時間の矛盾、A/B別監査の不足を修正した。各問題は修正前の回帰失敗と修正後の成功を確認した。minorのchecksum更新も実施する。実験のconfidenceは0.90のまま、validatorによるより保守的な閾値の許容を節約目的には使わない。

全unittestは58件、57成功、Windows directory symlink権限による1件SKIP。新規実タスク契約テストは21件すべて成功。protected既存39ファイルとCodex configの保存SHA-256は再照合で差異なし。既存全体gateのローカル再実行はGate1/2がApplication ControlでBLOCKED、Gate3/4/5はPASS。更新commitの正式CI確認はPR17へ記録する。MetaEditor/実MT5/市場/実AI売買通信は今回実施していない。

## マージ前の最終Sol xHighレビュー

追加の独立最終レビューでCriticalはなく、important 5件とminor 1件を確認した。重要事項は失敗判定での既知usage消失、実EA runnerの呼出前xHigh強制、untracked追加の保護/変更量分類、cache未取得での費用計算、無効A/Bペアの分解集計。minorはrepository名の大小文字違いによる重複登録だった。

policy4でこれらを修正し、12件のoffline境界回帰を追加した。実EA runnerは非xHighを呼出前に拒否する。未追跡ファイルも本文を保護対象検出と変更行数へ含め、旧bundleの分類不足は必須レビューへ戻す。正常な数値usageは判定失敗/非ゼロ終了/timeoutでも保持し、未提供のcache/reasoningは0を生成せず欠測を保つ。分解はreportと同じ適格性判定を共有する。既存EAテストは変更せず、PR内の新規算式テストには同じ適格性を満たすprovenanceを補った。

全unittest70件、69成功、ローカルWindows symlink権限による1件SKIP。初期の保存済み行をAPI再呼出なしで再集計し、calibration10/holdout20の適格ペアとtoken分解は一致した。旧行に元のcache提供フィールドが残っていないため、今回の再集計で参考費用はnullとなる。先に掲載した相当額は当時の参考計算として保全し、取得根拠の十分な現在の費用認定とは扱わない。元の実測ログを書き換えたり、未知費用を0にしたりしない。

レビュー省略OFF、confidence0.90、重要・未知依存のSol xHigh必須は維持する。30件は結果報告のみ、50件は一次評価と根拠が揃った低リスク試験条件の提案までとし、有効化しない。出力長や指摘件数を機械的に制限せず原因分析を続ける。修正差分の同じSol xHighレビュアーによる確認と正確な更新commitのCI結果を、マージ前にPR17へ記録する。
