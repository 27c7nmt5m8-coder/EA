# Jev Context Relevance Filtering 試験報告（2026-09-27）

判定は **REJECT（今回計測した方式の採用を見送る）**。3種の限定Replayでは主モデルのtokenは1,623減ったが、Jevの5,806 tokenを加えるとtotalが4,183（2.33%）増えた。短い文書変更はContextを削減できず、時間も増加した。閾値を削減率目的で調整していない。

これは既存の匿名化済み検証記録を使う**後ろ向きの証拠Replay pilot**であり、過去の長時間Codexタスクを最初から最後まで再実行したものではない。全ツール・検証判断を含む通常タスクでの能力維持、再調査、総費用の改善は **未立証**。この結果をJev一般の有用性の否定や本番導入の許可に拡張しない。

## 1. 現在のContext管理構造とPhase 0

- 作業開始時は `docs/model-orchestrator`、HEAD `c578ef6b14cc51cc1eda822514ab5fdfc6c5aa8f`、変更なし。fetchしたmainは `f504c3988e5715baaf14647b4e5109e6c67c4222`。両者の配布内容のdiffは0だった。
- 専用の管理worktreeと `trial/jev-context-compaction` を作成。製品branchとmainを変更せず、開いていた関連PRとの重複も確認した。
- Model OrchestratorはSkillによる調査順・モデル選択・Risk floor・任意Jev・fail-openの方針。既存の `evaluate_routing.py` は11件のオフラインfixture評価であり、live routerではない。
- TypeSafeAI Skillは現行API参照先を持つ。リポジトリには既存のlive Jev client、SDK依存、自動Context hook、一般的なdeterministic圧縮プログラムはなかった。既存の短い出力保持、長い成功出力だけの決定論的圧縮方針を再利用し、本番用の重複実装は追加していない。
- Codex側の履歴・自動compactionと、EA自身の分析/Testerログは別物。調査したローカルEA履歴1本には1,290件の `token_count` と11件の `compacted` があった。取得可能なusage fieldはinput、cached input、cache write input、output、reasoning output、total。過去チャット原文はfixture・Git・Jevへ転記していない。
- この履歴の累計usageから反実仮想Bを推測できない。Codex内部の実Context占有量、非公開のcontext構成は **UNKNOWN**。sessionファイルのbyte数をLLM tokenと見なしていない。

## 2. Jevを入れた箇所

`tools/context_trial/` に独立harnessを追加した。Jevは `core.py` の関連度Choice/Scoreだけを担当する。APIは既存TypeSafeAI Skillが指定する [公式HTTP API](https://docs.typesafe.ai/api)、[Choice](https://docs.typesafe.ai/primitives/choice)、[reranking](https://docs.typesafe.ai/cookbooks/rerank_typesafe) を確認して使用した。endpointやSDKを推測していない。

生成は原因解析がGPT-6 Sol/high、集計がGPT-6 Luna/medium、短文変更がGPT-6 Luna/low。利用可能なモデルと推論levelをローカルで確認し、A/Bで固定した。Jevがモデルを選択・変更することはない。

## 3. PINNED設計

型付きmetadataにより、目的、確定仕様、禁止、完了条件、Safety、Git状態、確定原因、baseline、OOS、重要Tester/compiler/regression、未解決、未検証、ユーザー保持指定、直接作業コードを自動PINNEDする。failed hypothesisも保守的に保持する。依存先とその推移的依存、未知の型・状態もPINNED。PINNEDをJevへ送る経路はない。

今回は事前に精査したcorpus用の型付けである。任意の会話の文章から仕様・安全制約を自動認識するingestorは作っておらず、そのような入力への安全性を主張しない。

## 4. deterministic filterとの役割分担

PINNED分離 → 同型の完全重複をARCHIVE → 保持済みの完全な成功summaryへの明示依存がある大きな成功logだけARCHIVE → 残る曖昧なentryだけJev、の順。

今回のcorpusには圧縮条件に該当する成功log・重複はなかった。大きな静的監査結果も重要なregressionとして保持した。数値集計、Git・hash照合、test/compiler結果、監査gateは通常コードが担当。Jevには判断させていない。

## 5. Shadow結果

| タスク型 | entry | PINNED | ACTIVE | ARCHIVE | DROP候補 | Jev calls |
|---|---:|---:|---:|---:|---:|---:|
| 原因解析 | 12 | 9 | 2 | 0 | 1 | 3 |
| 大量検証記録・Tester集計 | 12 | 9 | 2 | 0 | 1 | 3 |
| 短い文書変更 | 8 | 5 | 3 | 0 | 0 | 3 |

合計32 entry（タスク間の同じ原文は別観測）、PINNED 23。対象外ライセンスが原因解析と集計でDROP候補となった。file table・packaging等の7判定はconfidence不足で保持。実応答modelは `jev-1.13.0`。confidence 0.8を事前固定し、Scoreは記録だけに使った。原文はすべて保持した。

## 6. False-drop audit

全32件に分類とは独立した必要性labelを設定し、hash・entry coverage・pin保持を確認。DROP候補2件の原文は第三者libraryのライセンスであり、今回の解析/文書作成の根拠ではなかった。必要な仕様・Safety・原因・baseline・回帰・未検証情報はPINNEDで残った。

事前critical 0、noncritical 0。Replay後もAの引用とBの復元要求を照合し、critical 0。原文は削除・書き換えなし。ただし人手で選んだ小corpusであり、任意の実タスクでfalse dropが0になる証明ではない。過去の長いfailed-hypothesis列を網羅した監査は未実施。

## 7. A/B 3タスクとContext量

Aは既存のdeterministic方針だけ、BはそれにJev判定を加えた選択ビュー。全タスクのShadow監査を通過してからReplayした。両armで同じ入力・stage・Git blob基点・モデル/levelを使用した。

| タスク | Replayの内容 | stages/arm | initial bytes | A保持bytes | B保持bytes | 削減 |
|---|---|---:|---:|---:|---:|---:|
| 原因解析 | 指標要求順序の因果→同一条件Tester比較→検証限界 | 3 | 26,884 | 26,884 | 25,795 | 4.05% |
| 大量記録 | 約67KBの静的監査を含む検証記録→遷移分母・検証環境の区別 | 2 | 86,278 | 86,278 | 85,189 | 1.26% |
| 短い変更 | 日本語の検証メモを診断用成果物として生成 | 1 | 15,294 | 15,294 | 15,294 | 0% |

bytesは元entry本文のUTF-8量であり、wrapper・archive catalog・system promptを除く。全原文はGit blobのexact span。Bの原文は要約で置換していない。実tokenにはwrapper等も含まれる。

原因解析は過去の複数段階の証拠を再解釈する限定版で、未知のroot causeを数時間かけて発見するタスクの完全Replayではない。集計は匿名aggregate/監査記録であり実口座raw logではない。短い変更は独立文書の生成で、EA製品条件を変更していない。

## 8. Total token差

| タスク | A root input | B root input | A root output | B root output | A total | B total（Jev含む） | B−A |
|---|---:|---:|---:|---:|---:|---:|---:|
| 原因解析 | 76,549 | 75,603 | 926 | 693 | 77,475 | 78,228 | +753 |
| 大量記録 | 81,226 | 80,741 | 344 | 382 | 81,570 | 83,072 | +1,502 |
| 短い変更 | 20,389 | 20,389 | 183 | 186 | 20,572 | 22,500 | +1,928 |
| 合計 | 178,164 | 176,733 | 1,453 | 1,261 | **179,617** | **183,800** | **+4,183** |

CLIの `turn.completed.usage` とJevの `usage` を使用。本文byteからtokenを推定していない。主モデルのみなら179,617→177,994（−1,623）だが、Jevの5,806を含めると2.33%増加。今回の前処理・harness作成・外側チャット・独立コードレビューはarm外の実験構築費であり、この表に含めていない。これらを含む全プロジェクト費用はUNKNOWN。

## 9. Wall-clock差

| タスク | A秒 | B秒（filter含む） | B−A秒 |
|---|---:|---:|---:|
| 原因解析 | 46.53 | 34.95 | −11.58 |
| 大量記録 | 23.59 | 16.41 | −7.18 |
| 短い変更 | 7.34 | 7.77 | +0.43 |
| 合計 | **77.46** | **59.13** | **−18.33** |

3タスク各1pair。原因解析/短文はA→B、集計はB→A。繰り返し・信頼区間なし。キャッシュ条件・混雑・生成文量を制御しておらず、時間短縮をJevの因果効果と断定できない。

## 10. Jev call / cost

| タスク | calls | input | output | 合計 | filter秒 | 金額 |
|---|---:|---:|---:|---:|---:|---|
| 原因解析 | 3 | 1,721 | 211 | 1,932 | 1.013 | UNKNOWN |
| 大量記録 | 3 | 1,736 | 213 | 1,949 | 0.701 | UNKNOWN |
| 短い変更 | 3 | 1,715 | 210 | 1,925 | 0.748 | UNKNOWN |
| 合計 | **9** | **5,172** | **634** | **5,806** | **2.462** | **UNKNOWN** |

応答に課金額がなく、請求情報も取得していない。root model costもUNKNOWN。cached tokenの内訳は初回計測で保存していないためUNKNOWNであり、金額や速度の推測に使わない。

## 11. 再調査・再読込への影響

両armともnative tool calls 0、明示的file read/reread 0、retry 0、archive restore 0。これらは**事前供給型Replay protocol内だけ**の値。通常の自律Codex作業のファイル読込数を0と主張していない。corpus作成時のGit読み取りはarm共通の準備として除外した。

各stageは新しいCLIセッションへ原文と前stageの応答を再供給する。その重複入力tokenはすべて計上した。再調査回数・隠れた内部アクセスはUNKNOWN。ARCHIVE復元が実測で起きなかったため、復元によるコスト増の評価はoffline regressionだけである。

## 12. 品質差・検証能力

12 stage・50 structured fact assertionsは全一致。2,384総遷移に対する内訳2,383の不足1件、状態遷移とentry試行の分母の違い、mock 573と後日の582、過去のnative compileと今回未実行、取引0の残存を保持した。

全12回答の本文を元証拠と照合した。重大な事実矛盾やBでの重要情報損失は見つからなかった。ただし集計Aのstage 2は、質問に含めたstatic auditの説明を省略しており、**Aの本文完全性はPARTIAL**。Bはその説明を含んだ。短文は両armとも要求する日本語文書を生成した。品質評価はblindでも独立したhuman reviewでもない。

初回harnessはfact合格を `final_correctness=PASS` と表示していた。独立Sol/highレビューで「本文空欄でも合格し得る」と判明し、回帰テストで再現後、fact判定と本文レビュー待ちを分離した。初回のraw結果は書き換えず、別の本文監査記録を作成した。現在のharnessは自動的に総合PASSを付けない。

同じレビューで、不正なmodel metadataを持つAPI応答の例外後にDROP判定が残る問題も再現・修正した。実測9応答はすべて正常な `jev-1.13.0` で、この不具合の条件には該当しなかった。両修正は判定threshold、prompt、実測値を変更していない。

製品コード未変更なので新規Strategy Tester・native MQL compileは実施していない。過去の成功を今回の成功と数えていない。Replay子プロセスではnative toolsを無効にしており、通常タスクのcompiler/test選択・実行能力を保てるかは未検証。

## 13. Security / Privacyとharness検証

- Jev stateは短いgoal、entry type、手で精査した320文字以内のdescription、state relation、dependency boolだけ。原文、source code、repository全体、raw log、session history、個人情報、秘密値を送信していない。
- APIキーは環境からメモリ内で使用し、出力・保存・ログ・fixture化なし。子Replay環境からcredential系環境変数を除いた。HTTP redirectを拒否し、例外本文を保存しない。
- 実キーの完全一致scan（値の表示なし）とsecret-like pattern確認を実施。報告には匿名集計だけを掲載し、original context・生成log/binaryはGit対象外。
- 関連unittest **19/19**、既存routing fixture **11/11**、Python AST parse **5 files**。bypass無通信、timeout/不正応答/低信頼/401/422/429/529/通信失敗の保持、redirect拒否、PINNED全種・依存、原文不変、false drop gate、実usage/UNKNOWN、archive復元費用、本文未レビューの非PASSを確認した。API障害はoffline simulationであり、本番障害試験ではない。
- 既存Python gateはCSV **20**、static **495**、厳密source照合 **13** 成功。
- ローカル `tests/run_all.py` は最初にcp932 decodeで停止。UTF-8設定で解決して再実行したが、g++からcc1plusを起動できず停止した。存在するcc1plusを直接起動して **WinError 4551** を確認。したがってローカル全体gateとC++依存2gateは**未完走**であり、後続成功を推定しない。Code Integrity / Smart App Control / Defenderは変更していない。
- 専用offline CIはAPIを呼ばず、既存CIを改変しない。GitHub CIの最終状態はPRの対象commitで確認する。draftを保ち、mainへmergeしない。

## 14. Adoption判定

**REJECT**。今回の3種すべてでtotal LLM tokenが増加し、短文では時間も増加したため。byte削減や主モデル単体のtoken削減を採用根拠としない。full autonomous task全体に関する比較証拠は不足しているが、この限定pilotの数値を採用側へ解釈する根拠もない。

## 15. 採用するtask type

現時点では**なし**。長い診断や大量ログへのADOPT_PARTIALLYも根拠不足。

## 16. 採用しないtask type

短い修正/文書変更、今回型の原因解析・検証記録解析。本試験を根拠とするEA売買・Risk/Safety・注文・検証判断への導入は対象外。既存の `bypass jev`、Model Orchestrator、Risk floor、AGENTS、Skillsは維持。

## 17. 本番hook導入前に残る検証

1. 安全に切り出した実際の長時間sessionを、cutoff時点以降の情報を混ぜずに再現する。confirmed root causeを最初から与える本pilotのhindsight biasを除く。
2. 同一snapshot・同一ツール環境で、自由な調査/ファイル再読込/失敗仮説/実test実行/途中Context変更を含む完了までの対照試験を繰り返す。今回の12回のevidence-only inferenceを完全タスクReplayと混同しない。
3. ARCHIVE復元が必要な長い因果依存、baseline/OOS/regression、未解決/未検証、安全制約の保持と、critical false dropを独立に監査する。
4. seed/order/cache/負荷・課金usage・全child/再試行/復元のtotal費用と分散を測る。setup費も含む償却効果を別計測する。
5. 任意sessionを扱う場合は、型付け・redaction・PINNED検出の見逃しを検証する。正規表現だけでPrivacy保証をしない。
6. Windowsの許可されたtoolchainで未完走gateを確認し、実務で検証能力を落とさない。保護設定の回避を解決策にしない。
7. 上記で効果を立証しても、別の明示承認なしに本番hook、自動削除、main mergeを導入しない。

実行方法・metric定義は [harness README](../tools/context_trial/README.md)、試験計画は [plan](superpowers/plans/2026-09-27-jev-context-trial.md)。ローカルoriginals/results/narrative-reviewは元のまま保持し、配布には含めない。

保存したrun-01のSHA-256（原文や回答をGitへ複製せず照合するためのfingerprint）:

| 記録 | SHA-256 |
|---|---|
| originals.json | `ee4283d2b92a88f9a4abc0f2ae391ea1f92832f07ec86fe5f796ce51f05eab97` |
| results.json | `3c93f5dc8970e53153648c17a2fd2519cde9d0cd873919b07538b21426707f04` |
| narrative-review.json | `842dfeab98a2a6c54b9deec79e844d5778eaac1b65fe330c1f6a9cb68be203ab` |
