# 開発ガイド

MTFAutoTraderのMQL5配布物。`src/` の本体・Worker・全ヘッダーを一体として扱う。製品仕様・versionは [README_JA.md](README_JA.md)、検証手順・限界は [VALIDATION_JA.md](VALIDATION_JA.md#再現配布結果)、履歴は [CHANGELOG.md](CHANGELOG.md)。

<!-- canonical-rules: agents version=phase2a-1 -->

この文書の必須ルール本文は [.agents/rules/canonical.json](.agents/rules/canonical.json) の `consumers.agents` が指す全ID。作業前に全本文を解決して読む。ID・hashだけでは本文取得に代えない。新しいagent / reviewerにも必要全文を展開する。`tools.workflow_eval.rules.expand_document_rules` はversion・hash・全参照・循環を検証し、一度ずつ本文を返す。参照切れ・不一致・読み込み不能は停止して取得/修復し、ルールがないと解釈しない。これは参照の正本化のみで、dependency選択・changed file全文・レビュー・検証を変更しない。

役割の要約（詳細条件は正本）: root / orchestrator / integrate / verifyは `gpt-6.1-sol / high`。workerは通常 `gpt-6.1-sol / medium`。explorer / researcherは `gpt-6.1-sol / medium`。reviewerは独立contextの `gpt-6.1-sol / high`。

非自明な開発でモデル選択・昇格が有益なら [model-orchestrator](.agents/skills/model-orchestrator/SKILL.md)、TypeSafeAI / JevのAPI・primitiveは [typesafe-ai](.agents/skills/typesafe-ai/SKILL.md) を使う。正本はglobal rules、Skillは固有の操作手順を保持する。過去のbaselineと意味対応は [semantic-coverage.json](.agents/rules/semantic-coverage.json)（監査用。recipientの必須contextを代替しない）。
