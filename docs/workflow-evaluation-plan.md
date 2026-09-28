# 承認済み実装範囲

2026-09-28の承認条件を優先する。

- GPT-6 Sol Highを通常実装/レビュー、xHighを重要・複雑変更に維持する。
- EA本体・売買仕様・パラメータ・Worker・既存テスト・既存CI・Codex設定は変更しない。
- 開発補助CLI、数値/phase計測、Git差分context、JEV shadow adapter、paired集計、offline回帰を追加する。
- 実際の追加再レビュー省略を実装しない。shadow結果の評価前に有効化する経路を設けない。
- calibration10/holdout20は初期検証。品質同等の最終認定には使わない。
- 必須Sol規則、confidenceを保証にしない境界、critical見逃し時の不採用、OFFへのrollbackを維持する。

## 手順

1. 最適化前の既存数値ベースラインを保全し、既存7 unittestの成功を確認。
2. telemetry/phase schema、bundle/追加context、routing/HTTP境界を回帰テストから実装。
3. calibrationを実測。原因に基づく条件修正をRED→GREENで検証。
4. 条件を固定しholdoutを実測。tokens/時間/一致/見逃し/critical/欠落/エスカレーション/reworkの範囲を報告。
5. 既存source/CI/config/hash不変、全体ゲート、Sol xHighのfresh review、専用branch/PR/CIを確認。マージしない。

変更: tools/workflow_eval/*、tests/test_workflow_evaluation.py、架空fixture、運用/結果文書、.gitignore、SHA256SUMS.txt。
元計画のAGENTS/skill変更と限定pilotは今回の実装から除外する。現行指示やモデル設定を変更せず比較できるため。

レビュー重点: secretの外部送信/保存、欠損usageの0扱い、重要変更のcandidate化、context不足/古い証拠、calibration/holdoutや実測/架空の混同。

詳細運用: [workflow-evaluation.md](workflow-evaluation.md)。数値実測: [workflow-evaluation-results.md](workflow-evaluation-results.md)。
