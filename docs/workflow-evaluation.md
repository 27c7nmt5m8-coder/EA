# 開発ワークフロー計測・差分context・JEV shadow

このツールは開発補助専用です。EA本体、売買処理、Worker、パラメータ、既存CI、Codex設定を変更しません。実際のレビュー省略は実装していません。policyのreview_skip_enabledをtrueにするとエラーになります。

## 実行

Repository rootからPython 3.11以上で実行します。外部SDKは不要です。

```powershell
python -m tools.workflow_eval.cli --help
python -m tools.workflow_eval.cli capture <local-Codex-session.jsonl> --name baseline.json
python -m tools.workflow_eval.cli event <numeric-phase-event.json>
python -m tools.workflow_eval.cli events-report .workflow-eval/events.jsonl
python -m tools.workflow_eval.cli bundle --base origin/main --task-file <task.txt> --related <relevant-file>
python -m tools.workflow_eval.cli triage .workflow-eval/bundle.json --test-evidence <test-evidence.json>
python -m tools.workflow_eval.cli report <paired-rows.json>
```

`capture`はローカルsessionから数値だけを抽出します。会話・tool output・秘密を保存しません。単独完了turn、継承contextなし、単一Sol、累積counter整合が確認できた場合だけtask_usageを出します。不明な累積値はsession_cumulativeと区別し、厳密なbackend呼出回数はnullです。途中モデル変更・counter reset・欠損を成功として扱いません。

phaseイベントはtask_id / pair_id / arm / phase / eventを必須とし、round、elapsed_seconds、failed_cases、PASS/FAIL/BLOCKED/UNKNOWNを明示します。review/reworkを文章から推測しません。同じphaseの複数roundには別のround番号を与えます。未記録の作業を「なかった」と証明するものではありません。

```json
{"task_id":"example","pair_id":"pair01","arm":"A","phase":"additional_review","event":"end","round":1,"status":"PASS","elapsed_seconds":12.5}
```

bundleはbase/head、dirty差分、staged/unstaged/untracked、renameの両側、削除、関連ファイルの全文/interface/include、fingerprintを記録します。巨大contextを黙って切り捨てません。コード依存はUNKNOWNを維持し、include情報だけで依存が完全と主張しません。必要な仕様・呼出先/元は--relatedで追加します。機械的な依存候補に意味的な関係を含める判断はSolが行います。安全なbundleを作れない場合は通常のSol調査へ戻ります。

triageのtest-evidenceは `{"status":"PASS","fingerprint":"bundleのfingerprint"}` の形式です。テストrunnerの証拠と現在bundleが一致する場合だけ既知PASSとして扱います。このwrapperは証拠を署名・認証するものではなく、入力を作った担当者は実際に必要なテストを行う責任があります。古い証拠、UNKNOWN/BLOCKED/FAIL、未知依存、複数moduleは必須Solです。

全生成物はgitignoreされた `.workflow-eval/` に置きます。生のログ・bundle・外部requestをGit/CI artifactへ載せないでください。外部送信は明示された--live-jevだけです。TYPESAFE_API_KEYは環境変数から読み、出力しません。redaction不可、timeout、401/429等、schema不正時はSolへ戻し、retryは行いません。redirectは拒否します。

## A/Bとshadow実測

```powershell
python -m tools.workflow_eval.cli benchmark --split calibration --live-jev --workers 3
python -m tools.workflow_eval.cli benchmark --split holdout --live-jev --workers 3
```

benchmarkは明示実行時だけCodex CLIを起動します。Codexの既存認証を使い、ユーザーconfigを読み込まず、各子プロセスでGPT-6.1 Sol Highを標準指定します。明示的なbenchmark比較のみxHighを指定できます。設定ファイルは書き換えません。read-only/ephemeralで架空の固定レビュー課題だけを渡します。回答でtool実行や複数completed turnを検出した場合は無効とします。120秒timeout、同時実行は最大3件です。毎回fresh contextを使用し、A/B順序を入れ替えます。

Aは課題に供給されたcontext、Bは関連contextです。Aを「現行運用が毎回全リポジトリを読む」と仮定していません。fixtureには無関係な文書contextも含まれており、これを除ける場合の制御実験です。実際のEA開発の平均削減率へ一般化できません。

calibration10組、holdout20組は手ラベル付きの架空レビュー課題です。重要群はルーティング確認専用で、EAコードを生成・変更・実行しません。JEVは重要群を判定しません。必要contextを欠かした初期選択は追加取得してからSolへ渡し、初期欠落件数と未解決欠落を区別します。calibrationで条件を調整した場合、その後のholdoutでは固定します。

両armでSolレビューを実行します。JEVのcandidateは反実仮想の省略候補であり、actual_routeは常にreview、actual_review_skippedは常にfalseです。最初の実装・セルフレビュー、安全レビュー、テスト、PR運用を省略しません。modeはoffまたはshadowのみです。

重要ロジック、資金管理、注文、SL/TP/BE/Trailing、安全装置、複数module、未知依存を含め、src全変更、既存CI、テスト基準やmock変更等はレビューと決定論的検証が必須です。通常・mandatoryともGPT-6.1 Sol Highが標準で、重要群だけを理由にxHighへ自動昇格しません。Jevによる最終承認・レビュー省略はできません。xHigh追加レビューはHigh後のmaterial uncertainty、独立High間の重大不一致、適切な調査後の未解明原因、説明不能な決定論的挙動、明示project ruleの具体的証拠がある場合に限ります。初期candidate範囲はdocs/dev-*.mdの既知低リスク変更だけです。閾値0.90は分布由来confidenceへの条件であり、安全性・正解率保証ではありません。判定者は必要なcontext不足や重要な意味がないか別途確認します。

fingerprintはworking filesとindexのmode/blob/stageを含みます。削除・rename元など現在の全文を取得できないpathはexpansion_requiredとUNKNOWN依存にし、必須Solへ戻します。triageのevidenceにはdiffも含めます。benchmarkではfactsのschemaと、実際に送信する全payloadを呼び出し前に検査します。

## 結果の読み方

- GPT-6 input/output/total削減率は同じ有効pairだけから算出します。負値は増加です。reasoningはoutput、cachedはinputの内数です。
- 時間はarmごとのSolプロセス経過時間合計とB＋JEV時間、並列runのwall時間を区別します。開発全体時間ではありません。
- JEVとSolの一致率は有効JEV回答と同じ課題のB判定の比較。coverage/分母を必ず示します。
- raw JEV false negative、閾値・mandatory適用後のshadow false negative、Sol false negativeを分けます。criticalは件数と評価範囲を示します。
- criticalなSol/shadow見逃しが1件でもあればBLOCKED_CRITICAL_MISS。原因分析・条件修正が必要です。このreleaseには省略を有効にする経路がありません。
- critical観測はA/B両側、raw JEV、shadowを検査し、相手armの通信失敗やusage欠損で消しません。削減率の有効pairには同一Solモデル・同一HighまたはxHigh effortを要求します。mandatory Highも正規ルートです。model/effort別のreview_provenanceを保持し、旧モデル読込互換を実行fallbackにしません。
- 固定レビューfixtureのrework=0はコード修正を行わなかったことだけを表します。実開発の再修正はphaseイベントで計測します。
- usageが取れない通信の費用を0とみなしません。JEV/actual tier価格不明時の全費用は未計測です。cached内訳を無視して総tokensだけから費用を推定しません。
- JEV試行のusageが欠損した場合、completeなJEV総tokens・全provider合計・削減率はnullです。既知分はjev_known_token_subtotal、欠損件数はjev_usage_missing_attemptsとして分けます。
- 20組のholdout、一致率、mock成功だけで「品質低下なし」を最終認定しません。quality_certifiedとreview_skip_enabledは常にfalseです。

## 検証・rollback

```powershell
python -m unittest discover -s tests -p 'test_*.py'
python .agents/skills/model-orchestrator/scripts/evaluate_routing.py
python tests/run_all.py
```

既存ゲートとCIはそのままです。BLOCKEDはPASSではなく、native環境不足は実装のfailureと分離します。必要なexact-commit CI確認はNATIVE_VALIDATION_JA.mdに従います。source不変なのでこの変更による売買挙動の試験とは扱いません。

rollbackはpolicy.modeをoffにするかCLIを使わないだけで現行運用に戻れます。恒久撤回は開発補助のcommitをrevertしchecksumを更新します。EA・CI・Codex設定のrollback作業は発生しません。共有branch/mainへマージするには別途許可が必要です。

API契約: https://docs.typesafe.ai/api
confidence: https://docs.typesafe.ai/confidence

## Active policyと履歴

policy version 5の今後の実行は `gpt-6.1-sol` / Highです。旧モデルや過去のxHigh測定・PRレビュー・provenanceは書き換えません。旧policyでの計画・測定結果は実施時の履歴です。履歴価格は `historical_sol_standard_short_context_rates` としてのみ残し、新モデルの料金は未検証のため集計でunknownを維持します。詳細と明示追加レビューのAPIは [High-first policy](workflow-high-first.md) を参照してください。
