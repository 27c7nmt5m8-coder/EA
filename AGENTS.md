# 開発ガイド

MTFAutoTraderのMQL5配布物。`src/` の本体・Worker・全ヘッダーを一体として扱う。製品仕様・versionは [README_JA.md](README_JA.md)、検証手順・限界は [VALIDATION_JA.md](VALIDATION_JA.md#再現配布結果)、履歴は [CHANGELOG.md](CHANGELOG.md) を参照する。

## 判断・Context

- システム・開発者指示と実行権限の範囲内で「現在の明示依頼 → EA固有の安全・品質ルール → Skill等の一般手順」を優先する。依頼範囲や安全機構の変更許可を推測しない。軽微な不明点は証拠に基づく最小変更で進め、仮定を報告する。許可済み作業の再確認は不要。
- 未承認の売買仕様変更、破壊的変更、重大な結果を分ける未解決の選択は確認し、独立した調査は続ける。範囲外の重大不具合は勝手に直さず報告する。指示による停止・確認・逸脱はファイルパスと該当ルールを引用し、環境・権限不足と区別する。
- 調査順序は「変更対象 → git diff / 検索 → 関連関数・節 → 関連履歴 → 必要な依存先」。毎回のRepository全文・全docs・全Skill・全履歴の読み直しは禁止。必要な時だけ広げ、必要な確認は省略しない。
- 非自明な作業で同じ文脈をsubagent / reviewerへ渡す場合は、可能なら `tools.workflow_eval.context` のcontent-addressed packetを使う。変更ファイルは本文を保持し、exact SHAが一致する未変更の関連文脈だけをhandle化する。protected、unknown dependency、未解決のexpansionでは再利用を無効化し、handleの中身が判断に必要・不確実なら必ず展開する。これはcontext転送の圧縮だけであり、レビュー・検証・モデル能力を置き換えない。
- 現在のRepository / Git状態を正本とし、古いPR番号・SHA・過去チャットのversionを基準にしない。一時的なPR・SHA・診断状況は本書へ残さない。重複・古い指示は既存表現へ統合し、安全ルールは削らない。

## EA固有の保護

- 明示依頼なしにEA売買仕様・互換性を変更しない。READMEのEntry・パターン選択/競合/再利用防止、Score、SL/TP・lot・コスト、注文/決済、インジケーター・UI・入力、Worker通信schema/期限/価格ドリフト/FailOpen、状態・保存キー・ログ/CSV仕様を維持する。Workerから注文を出さない。
- Risk / Safety機構を弱めない。Monte Carlo・総ポートフォリオリスク・Fintokei保護、銘柄/口座の状態分離・所有判定・発注制約・未解決注文停止・mutex、安全状態の永続化、分析ログ失敗と売買判断の分離、PositionIdentifier照合・初期リスクRを保護する。詳細値・条件はREADMEを参照する。
- ソース変更では本体・Worker・全ヘッダー・入力・保存キー・ログ・移行処理への影響を確認する。MQL5実仕様をmockより優先し、不整合はmock側を修正する。テストのためだけに製品仕様を変えない。
- 実口座への注文は禁止。秘密情報・APIキー・口座情報・実ログをソース、fixture、CIログ、artifact等へ保存・掲載しない。通信fixtureには架空値を使う。

## Skill

- 適合する作業でのみSkillを使い、一般的な計画承認・毎回の全テストを上位の依頼へ追加しない。
- 非自明な開発でモデル選択・昇格が有益なら [model-orchestrator](.agents/skills/model-orchestrator/SKILL.md) を使う。決定論的な確認・検証を優先し、能力・正確性・EA安全性・必要な検証を損なわない最低限十分なモデルと推論レベルを選ぶ。
- TypeSafeAI / Jevの詳細は [typesafe-ai](.agents/skills/typesafe-ai/SKILL.md) に委ねる。決定論的確認後も限定的な意味判断が有益な場合だけ使い、利用不能時は通常経路へ戻す。`TYPESAFE_API_KEY` を表示・保存しない。EA固有の売買仕様・安全機構・Risk管理・Git/検証ルールを上書きしない。Jevは軽量分類・関連候補整理・ログ分類等の補助に限定し、売買方向、Entry条件、Score、SL/TP、lot、Monte Carlo、Risk、Fintokei保護、安全装置の判断・変更を任せない。

## 開発・Git・レビュー

### モデルと役割

- root / orchestrator / integrate / verifyは `gpt-6.1-sol / high`。単純な作業は直接処理し、並列化・独立調査/レビュー・専門分担に具体的な利点がある場合だけ委任する。統合時は実diff・依存関係・テスト・CI・モデル割当を確認する。
- subagentを使う場合は、正確性に必要な履歴がない限りfull-history forkを既定にしない。task、実diff、関連する変更本文、必要な仕様、verification digest、未解決事項を小さいpacketとして渡し、未変更の既知文脈はexact-hash handleで参照する。新しい独立contextのagent / reviewerがhandleの元本文を保持していない場合は、そのhandleを送信前に必ず展開する。必要情報の追加取得は許可し、context節約を理由に調査範囲やmandatory reviewを狭めない。
- workerは通常 `gpt-6.1-sol / medium`。複数モジュール、注文・資金・lot・SL/TP/BE/trailing・Monte Carlo・Risk/Safety、並行性・状態管理、原因不明のbug、architecture、orchestration・JEV/JEVGrep連携ではHighを選ぶ。
- explorer / researcherは通常 `gpt-6-luna / high`、read-only。複雑な依存調査・保護領域の深い探索・複数仕様の比較では `gpt-6.1-sol / medium`。既存の適切なagentを再利用し、同じ役割を重複作成しない。
- reviewerは独立contextの `gpt-6.1-sol / high`、read-only。mandatory reviewは省略不可という意味で、protected / high-riskだけでxHighへ上げない。deterministic verification後にHighを実施し、未解決のmaterial uncertainty・重大なレビュー不一致・未解明のroot cause・説明不能な検証挙動・明示的project ruleがある場合のみ、理由と証拠を付けて追加xHighへ昇格する。
- AstraはSolで能力不足が実証された非常に難しい独立レビューだけ。必要性・確認範囲・コスト増の理由を先に報告し、明示承認後に使用する。自動routing・fallbackは禁止。
- [.codex/config.toml](.codex/config.toml)はrootと未指定subagentのSol High既定値。役割別のmodel / effortは対応するspawn指定で明示する。`fork_turns`はcontext伝播の制御でありモデル切替ではない。全履歴forkでは親設定を継承する。指定が利用不能なら停止して報告し、旧Solや別モデル・effortへsilent fallbackしない。
- 新規Sol実行は `gpt-6.1-sol` のみ。旧IDは履歴・provenance・過去料金・互換/negative testに限定する。Jev confidence `0.90`、review skip禁止、EA保護、既存deterministic verificationを維持する。

1. 最新GitHub main・git status・適用指示・関連履歴を確認し、mainを直接変更せず専用branchで作業する。既存の作業変更を保全する。関連open PRの変更・競合を確認して重複実装を避ける。ZIP等でmainとの対応が不明なら反映の制約を明記する。
2. 無関係な機能削除・大規模リファクタリングを混ぜない。バグは根本原因を調べ、可能なら修正前に再現・回帰テストを追加する。既存テストは削除・弱体化しない。
3. 差分と保護への副作用をセルフレビューし、branchにコミットしてmain向けPRを作り、CI・レビュー結果を確認する。ユーザーの明示許可なしにmainへマージしない。許可時もCI・レビュー・必要な実機確認を満たす。PR作成はマージ・実口座導入の許可ではない。

## テスト・実機検証

- 「直接関連 → 関連 → 必要なintegration → PR完成前の全体ゲート」の順に広げる。文書のみはリンク・コマンド・diff・チェックサムを確認し、形式的なランタイム回帰テスト追加は不要。PR完成前・マージ前は `python3 tests/run_all.py` を確認する。同一commit・同一diff・同一前提の信頼できる成功結果は再利用可能。変更時は再検証し、全体ゲート未完了のPRはdraftにする。
- MQL5変更では利用可能なネイティブコンパイルと関連実機確認を優先する。詳細手順・失敗の切り分け・生成物の扱いはVALIDATIONに従う。必要な安全確認・レビュー・回帰確認を省かず、未実測事項を明示する。未実行を合格や実装の失敗と数えず、mock/静的検証をネイティブ・実機・市場バックテスト・実AI/API通信・収益性の成功と混同しない。
- 報告は理由・範囲・件数・失敗・重要警告・未検証を要約し、詳細ログは必要箇所だけ確認する。同梱の `verification/` は過去の記録であり、更新時は実行結果と対象ソースSHAを対応させる。

配布変更時は `SHA256SUMS.txt` 自身を除く追跡対象ファイルのSHA-256をパス順に更新する。生成物はコミットせず、意図した配布ファイルだけを含める。
