# 実タスクshadow計測

省略OFF、confidence 0.90、Sol High/xHighを維持する。初期実コホートのEAレビュー/実装は保守的にxHigh必須とする。JEVは重要群を判断せず、売買・安全性・最終承認を任せない。ユーザー設定、既存CI、EAは変更しない。

## 独立タスクと欠測

登録単位は repository + request_id (`pr:11`等)。同じPRの反復、head更新、A/Bの2レビューを別件に数えない。origin=prospectiveかつkind=ea_review/ea_implementationだけを30件・目標50件に含める。架空fixture・過去ログの集計・開発補助変更は別群。PRレビューは新しく実行したレビューを数え、元の実装が今回行われたとは扱わない。

記録にはbase/head SHA、開始/完了UTC、モデル/推論、実行status、usageと元のusageフィールド、時間、context再取得/不足、再修正、テスト失敗、見逃し監査を含める。reported_reasoning_output_tokensはAPI/CLIが提供したときだけ値を持ち、可視回答の文字数と区別する。入力cache・出力reasoningは内数で二重加算しない。exact backend call数は取得不能ならnull。

レビューのtoken比較と実装を含む全タスクusageを分ける。両側のmodel/effortと計測が揃ったreview pairでのみ削減率を出す。context追加呼出やJEV・監査・計測制御のコストも別に記録する。元実装の再修正やテスト失敗を今回のレビューから推測しない。未取得はnull、coverageを必ず併記する。

false negative/criticalは後続の独立レビュー、再現テスト、修正後の検証等で根拠を確認してから監査済みにする。判定一致だけで正解ラベルを作らない。未監査はPENDINGで、見逃し0を意味しない。critical観測は削減比較の無効pairでも保全する。criticalを含む条件は原因分析・ルーティング改訂前に採用しない。

監査はA/Bそれぞれのfalse negative・critical見逃しと全体の件数を持つ。CHECKEDにするには全6件数の独立した根拠が必要で、PENDING中はすべてnull。比較ペアの監査coverageと全タスクの監査coverageも区別する。usageを取得できたUNKNOWN/失敗の数値は観測subtotalとして残し、未取得の試行数を示す。異なるPRの片側同士から削減率を作らない。

## CLI

Repository rootで実行する。全出力はgitignore済み `.workflow-eval/`。raw source、prompt、実取引ログ、秘密をcohort recordやGit/CI artifactに載せない。

```powershell
python -m tools.workflow_eval.cli decompose .workflow-eval/holdout-20260928T041611823390-rows.json
python -m tools.workflow_eval.cli cohort-record <safe-real-task-record.json>
python -m tools.workflow_eval.cli cohort-record <audited-same-task-record.json> --update-audit
python -m tools.workflow_eval.cli cohort-report
```

登録は単一writerで行う。監査更新は同じtask identity/source/resultsを維持し、以前の記録をローカルに保全する。記録済みcritical見逃しを減らせない。runnerが自動でタスクを作ったり、GitHubにマージしたり、EAを修正したりする機能はない。

既存capture/event/events-reportで全タスクの数値usage、test/rework phaseを収集し、対象taskのrecordへ対応付ける。数値の出所とSHAの一致は担当者が検証する。typed schemaは真偽の証明・署名ではない。

実レビューの呼出関数は `tools.workflow_eval.real_tasks.perform_review(task, evidence, effort='xhigh')`。入力は秘密・実口座ログを除いた文字列で、出力は判定と数値usageのみ。Codex CLIのread-only/ephemeral実行でユーザー設定を変更しない。JSON schemaはfinding数やreason長に上限を付けず、重要指摘や推論の切断を狙わない。初回計測後にstructured outputと900秒の待機上限、診断コードを追加した。schema表現・parserはoffline検証済みだが、この改訂wrapperの実API再計測はまだ行っていない。上限変更は推論レベルの変更ではない。

## 継続と採用条件

実際に承認されたタスクごとに計測する。週次の集計では追加証拠がない日にモデル比較を再実行せず、タスク数を増やさない。30件で中間報告、50件を目標に蓄積し、課題種類、重要群/低リスク群、欠測/監査coverage、A/B見逃し、再修正、context再取得、token・処理時間を示す。新しい改修仕様はユーザーの依頼から取得する。

このスレッドに週次のheartbeat「EA実タスクshadow集計」を設定した。新規記録・証拠がなければ集計のみ行い、他スレッドへの送信や自動的な仕様変更はしない。別タスクのusageがこのrecordへ自動注入されるわけではなく、実際の作業担当によるphase計測と記録の対応付けが必要。30〜50件の蓄積完了は今後の実作業と独立監査に依存する。

50件だけで最終保証もしない。必要仕様・安全性・コード品質・資金管理リスク・テスト品質・見逃し・再修正が悪化する条件を除外する。品質維持が未確認ならquality_preserving_reduction_percentはnull。候補提案には十分な実タスクと独立監査が必要で、実際の省略有効化は別途明示承認と実装を要する。

rollbackはCLI/定期集計を停止するかpolicy.mode=off、恒久撤回は開発補助のcommitをrevertしchecksumを更新する。既存EA/CI/settingsに変更はない。
