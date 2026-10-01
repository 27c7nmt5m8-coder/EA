# Workflow High-first policy

開発補助のactive policy version 5は `gpt-6.1-sol` / `high` を通常・mandatory・independent reviewの標準とします。protected / critical / EA / financial / order / safety、未知依存、allowlist外ではレビュー・決定論的検証が必須で、Jev最終承認とreview skipは禁止です。`review_skip_enabled=false`、`confidence_threshold=0.90` を維持します。src/とEA/Worker runtimeは変更しません。

effortの存在やrisk分類だけでは昇格しません。xHighは追加検証用で、次の明示的理由と具体的な公開可能な証拠を要求します。

| reason | 必要な証拠 |
| --- | --- |
| high_review_material_uncertainty | 実施済みSol Highレビューと残る重要な不確実性 |
| independent_high_review_disagreement | 独立Highレビュー間の重大な判断不一致 |
| unresolved_root_cause | 適切な調査後も原因不明である具体的な結果 |
| unexplained_deterministic_behavior | 決定論的チェックの説明不能な挙動 |
| explicit_project_xhigh_rule | xHighを要求するproject ruleのパスと該当条件 |

`route(facts, escalation={"reason": ..., "evidence": ...})` および `perform_review(task, evidence, "xhigh", escalation=...)` が明示追加レビューの入口です。metadata検証は証拠の真実性を証明しません。担当者は必要なHighレビュー・調査・テストを実施し、根拠を示す責任があります。失敗・未対応はUNAVAILABLEとして報告し、別モデルや低effortへのsilent fallbackはありません。

benchmarkの `run_case(..., comparison_effort="xhigh")` / `run_cases(..., comparison_effort="xhigh")` と `sol_review(..., "xhigh")` は明示的な実験用です。mandatory routingはHighのままで、結果にmodel/effortを保持します。benchmark比較にreview承認権限はありません。A/Bのmodelまたはeffortが異なるpairは比較集計から除外します。

GPT-6 Astraは、Solで不足した具体的証拠がある例外的に難しい設計・判断のみです。deterministic evidenceをAI effortより優先します。

旧 `gpt-6-sol` は記録parserと過去料金参照のみで受け付けます。historical recordはそのmodel/effortを保持し、`gpt-6.1-sol` と同一モデルへ書き換えません。旧料金は新モデルに適用しません。PR #18〜#20の測定値・レビュー記録・provenanceを変更せず、各実験branchの将来実行設定は本PRに取り込みません。統合時は新active policyと照合する必要があります。

変更がdeveloper toolingのみなので、native MQL5/MetaEditor・Strategy Tester・実口座・実AI/API通信は今回の検証対象外です。未実行をPASSとしません。全Python discovery、offline routing evaluation、既存 `tests/run_all.py` gateは実施します。
