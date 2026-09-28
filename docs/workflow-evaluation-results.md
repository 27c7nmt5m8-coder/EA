# 初期A/B・JEV shadow計測結果

2026-09-28、架空の固定レビュー課題calibration10組＋holdout20組を実測した。Solによる実装タスクや市場・売買結果の比較ではない。省略機能は実装せず、両側でレビューを実行した。品質同等の最終認定は行わない。

## 実測

| 指標 | calibration 10組 | holdout 20組 |
|---|---:|---:|
| GPT-6入力削減率 | 6.1435% | 6.1431% |
| GPT-6出力削減率（負値=増加） | -20.2991% | -20.2952% |
| GPT-6総tokens削減率 | 6.0672% | 6.0547% |
| JEVを含む全provider総tokens削減率 | 3.8889% | 4.6668% |
| A GPT-6 input/output/total | 161633 / 468 / 162101 | 323291 / 1084 / 324375 |
| B GPT-6 input/output/total | 151703 / 563 / 152266 | 303431 / 1304 / 304735 |
| JEV総tokens | 3531 | 4502 |
| A Sol処理時間合計 | 83.205秒 | 184.122秒 |
| B Sol処理時間合計 | 80.100秒 | 176.869秒 |
| B Sol＋JEV処理時間合計 | 82.551秒 | 183.036秒 |
| JEV/Sol一致 | 7/8（87.5%） | 9/10（90%） |
| JEV比較coverage | 8/10 | 10/20 |
| raw JEV false negative（元fixtureラベルに対して） | 1 | 0 |
| shadow規則適用後のfalse negative | 0 | 0 |
| Sol false negative A/B | 0 / 0 | 0 / 0 |
| Sol判定と元ラベルの不一致 A/B | 1 / 1 | 2 / 1 |
| criticalルーティング見逃し | 対象なし | 0 / 5対象 |
| 初期context欠落件数 | 1 | 1 |
| 追加取得後の未解決欠落 | 0 | 0 |
| shadowエスカレーション率 | 90% | 85% |
| 実際のSolレビュー率 | 100% | 100% |
| 実際のレビュー省略 | 0 | 0 |
| 観測completed Sol turn A/B | 10 / 10 | 20 / 20 |
| 再修正 | 固定レビューfixtureでは0 | 固定レビューfixtureでは0 |
| 並列run wall時間（A+B+JEV） | 63.173秒 | 128.452秒 |

Sol High/xHighを両側で揃え、必要なtest/fingerprint/依存等の条件を架空事実として供給した。fixtureのPASSは実際のEAテストを実行したという意味ではない。課題はコード生成・修正を含まないので、実開発の再修正率やテスト失敗率の改善は未計測。厳密backend呼出回数も未取得。観測completed turnではSol呼出削減は0%。接続確認に別途Solを1回実行した。

全入力中の共通system contextもusageに含まれる。制御Aは課題に供給した無関係な文書contextを含み、現行運用が毎回全リポジトリを読むという仮定をしていない。ここでの約6%を現行EA開発の平均削減率として扱わない。

## 見逃し・不一致の扱い

calibration C06では「cached inputをinclusiveなinputへさらに加算する」という誤った説明を、JEVがcandidateと判定した。confidenceは0.75だったためshadow規則ではSolへ戻った。Sol両側はreviewと判定した。低confidenceの候補を自動通過させない境界が機能したが、JEV単独の正確性を保証しない。

calibration C09は英語のbeをBEと誤検出して過剰エスカレーションした。RED→GREEN回帰で小文字beとBreak Even/BE/stop loss/take profitを区別し、policy versionを1から2へ更新した。holdoutはversion2とconfidence0.90を固定して実施。閾値は下げていない。calibrationの元結果はversion1の測定として保全する。

holdout H07は元ラベルcandidateに対してSol両側がreview。要求にはinterfaceの境界値保持があるが、変更後説明はfractionのみでnonnegative条件の充足が明確でなく、元ラベルの妥当性に曖昧さが残る。ラベルを結果に合わせて書き換えず、要監査として記載する。この曖昧な1件を見逃し対象と評価する場合、raw JEV見逃しは追加で1件となる。JEV confidence0.46で実際のshadow規則はreviewに戻っている。

H11ではAがunknown、Bがreviewとなった。tool/parser変更のmandatory経路はどちらもSol xHighを要求している。reviewとunknownの意味差を品質改善と認定しない。重要5課題はすべて必須Solへ送られ、JEVには判断させていない。したがって「JEVがcriticalな欠陥を検出できた」という評価ではない。

## 費用・採用判断

Standard短contextの公式単価によるSol text-token相当額は、calibration A $0.098007 / B $0.070802、holdout A $0.201460 / B $0.190897。cached内訳を用いた参考換算であり、Codexの実請求額・実際のtierとは異なる。[Sol料金表](https://developers.openai.com/api/docs/models/gpt-6-sol)

測定JEVは全18試行でjev-1.13.0。[公式料金](https://docs.typesafe.ai/models)は入力$0.042/Mtokens、出力無料。入力calibration3227、holdout4122から参考費用は$0.000135534 / $0.000173124。Bに加えた参考相当額は$0.070937534 / $0.191070124。実請求額・割引・tierは未取得なのでレポートのactual all_provider_cost_usdはnullのままです。初期policyのaliasと回答versionは保全し、修正版の今後の実験ではversioned IDを固定します。

入力と総tokensは減ったが、出力は増えた。JEV込みの処理時間改善はcalibration約0.8%、holdout約0.6%で、小標本・単回測定・cache変動の範囲。shadow省略候補はcalibration1/10、holdout3/20だったが、実現したレビュー省略/呼出削減として報告しない。

結論はSHADOW_ONLY_INSUFFICIENT_FOR_ADOPTION。実際の省略を有効化しない。品質ラベル監査、実際の同等開発タスクでの前向きphase計測、追加の代表的sampleと安全レビューが必要。critical見逃しが今後1件でも発生した条件では、原因分析とrouting修正が先となる。

## 証拠・検証範囲

実使用量・時間・JEV回答・送信した最小state・Sol判断・一致/不一致・fingerprintは、ローカルgitignoreされた `.workflow-eval/` に保存した。公開するのはこの集計と架空fixtureのみ。共通contextはfixtureの共有領域へ移し、materialize後の全30ケースが元測定入力と同一であることを決定論的に照合した。重複保存を約207KBから約33KBへ削減した。

独立Sol xHighレビューとfixtureラベル監査を実施。H07以外の元ラベルは支持され、H20の複数module説明とmodule_count=1の不整合を今後のfixtureでは2へ修正した。測定済み行・旧入力・policy1/2のログは書き換えない。H20は元測定でも未知依存によりxHighだった。

レビューで見つかった7件は、送信facts/schemaと全payload検査、保護語句追加、index鮮度、削除context不足、usage欠損のnull扱い、A/B全側critical観測、Sol推論floor検証に修正した。追加の再現テストは修正前に失敗、修正後に成功を確認した。policy3はこれらの修正版であり、旧測定で再検証したとは主張しない。EA安全判定を語句検索だけで保証しない。

EA source13件、既存CI/既存tests、Codex configのSHA-256不変を確認。新offline回帰と既存unittest、既存offline routing fixtureを検証した。Windowsのdirectory symlink回帰1件は作成権限がなくローカルSKIPで、CIでは実行する。

全体gateは初回にg++がPATHに無くGate1/2がFAIL。既存UCRT64をprocess PATHへ指定して再実行し、Application ControlによるGate1/2=BLOCKED、Gate3/4/5=PASSを確認した。ローカル全体はINCOMPLETEであり、成功扱いしない。正式なexact-commit CI確認はPRの結果へ記録する。今回のMetaEditor/実機/市場/実AI売買通信は未実施。
