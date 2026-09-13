# 開発ガイド

## 対象と構成

このリポジトリは MTFAutoTrader v2.44 の MQL5 ソース配布物です。

- `src/`: EA 本体、AI Worker、共通ヘッダー。13ファイルを一体として扱う。
- `tests/`: C++17 の MT5 モック、JSON 回帰、静的ソース監査、集計テスト。
- `tools/build_pattern_stats.py`: 取引ログから統計CSVを生成するオフラインツール。
- `verification/`: 配布時に記録した検証結果。ローカル実行で生成する一時C++やバイナリはコミットしない。
- `README_JA.md`: 利用・開発手順。`VALIDATION_JA.md`: 検証範囲と限界。`CHANGELOG.md`: v2.44 の変更履歴。

## 変更時の原則

v2.44 の取引挙動と互換性を保つ。特に次を意図せず変更しない。

- M1 エントリー、10パターン、最高 PatternScore の選択、反対方向競合の拒否、同一構造の再利用防止。
- 7時間足の重み `20/25/22/15/10/5/3`、Trend/MACD `70/30`、最終スコア `80/15/5`、`MinimumSignalScore=70`、方向一致の初期下限55%。
- 3つのリスクモード、総ポートフォリオリスク上限、Fintokei 保護、SLの構造アンカーと汎用 fallback、ロット・TP・コスト判定。
- 銘柄別状態、1銘柄1M1バーの発注制約、Magic/銘柄の所有判定、Netting/Hedging、未解決注文停止、口座ミューテックス。
- Worker プロトコル242、厳格JSON schema、AI期限・価格ドリフト・FailOpen条件。Workerから注文を出さない。
- 重要な安全状態の永続化と、分析ログ失敗を売買判断から分離する設計。CSV列、PositionIdentifier照合、初期リスクRの意味を維持する。

ソースを変更するときは本体だけでなく Worker、ヘッダー、入力、保存キー、ログ形式、移行処理への影響を確認する。秘密情報、APIキー、口座情報、実ログをソース、fixture、CIログ、artifactへ追加しない。AI通信のfixtureは架空値だけを使う。

## GitHub / Codex の標準開発フロー

GitHub の `main` を正本かつ安定版として扱う。Codex を含む自動修正では、ユーザーが明示的に別方式を指定しない限り、次の流れを標準とする。

1. 作業開始前に `main` の現行コード、`AGENTS.md`、関連ドキュメント、直近の変更を確認する。
2. 原則として `main` を直接変更せず、目的が分かる専用 branch を作る。例: `fix/v244-global-variable-lock`、`feat/v245-...`。
3. 変更範囲を必要最小限に限定し、ユーザーから明示されていない売買ロジック、スコア、SL/TP、リスク管理、注文処理を勝手に変更しない。
4. バグ修正では症状だけでなく根本原因を特定し、可能なら修正前に再現テストまたは回帰テストを追加する。Mock と実MQL5仕様の差が原因なら、Mock側も実仕様へ合わせる。
5. 既存テストを削除・弱体化せず、変更に対応するテストを追加して `python3 tests/run_all.py` を実行する。
6. 変更差分を確認し、意図しないファイル変更、保存キー、通信schema、Magic/所有範囲、Netting/Hedging、安全永続化への副作用がないかレビューする。
7. 修正 branch にコミットし、`main` 向け Pull Request を作る。PR本文には変更理由、変更ファイル、追加テスト、検証結果、未検証項目を明記する。
8. CIとレビュー結果を確認し、MetaEditor/MT5実機で確認が必要な項目を明確に残す。実機確認前に `main` へマージ済みと扱わない。
9. ユーザー実機で必要な確認が完了し、問題がなければPRをマージする。問題があれば同じbranch/PRで最小限の修正を続ける。

ZIPやチャット添付ファイルが提供された場合も、GitHub版との対応関係を確認し、可能ならGitHubを正本として差分管理する。GitHubへ反映できない場合だけ一時的にZIPベースで作業し、その状態を明記する。

## MetaEditor / 実機検証の扱い

- MQL5コードの最終基準はMetaEditorのネイティブコンパイルとする。目標は `0 errors / 0 warnings`。
- C++モック、静的解析、GitHub Actions、独自テストだけを根拠に「MetaEditorでコンパイル済み」「0 errors / 0 warnings」と断定しない。
- MetaEditor実機で未確認の場合は、報告に **「ネイティブコンパイル未実測」** と明記する。
- MetaEditorのwarningも原則放置せず、未初期化変数、暗黙変換、precision loss、配列境界、無効ハンドル、戻り値未確認、注文/ポジション関連を重点確認する。
- 警告修正では売買ロジックを不要に変更せず、安全な初期化、明示的型変換、戻り値確認など最小限の修正を優先する。
- 時間足変更、チャート変更、再起動、再接続など `OnDeinit()` → `OnInit()` を伴う実機挙動も検証対象とする。Global Variable、mutex、owner lock等のMockは実MQL5の再初期化 semantics と一致させる。

## 検証

Python 3 と g++ が必要。リポジトリ直下で全ゲートを実行する。

```bash
python3 tests/run_all.py
```

個別確認は次の順序と範囲で実行できる。

```bash
python3 tests/verify_v244.py
python3 tests/verify_json_regression.py
python3 tests/verify_stats.py
python3 tests/audit_source.py
```

`verify_v244.py` は実ソースを C++17 用に変換して MT5 モック上で検証する。これは MetaEditor のネイティブ MQL5 コンパイルではない。結果を報告するときは、C++モック、JSON回帰、静的監査、集計の件数を分け、未実施の MetaEditor コンパイル、MT5実機、実市場バックテスト、実AI/API通信、収益性を成功扱いしない。

テスト後に生成される `verification/integration`、`verification/*.cpp`、`verification/case.json`、`verification/initial.json`、`verification/json_test`、`__pycache__/` は作業生成物として除外する。履歴として同梱された検証レポートを更新する場合は、内容とソースSHAの整合を確認する。

配布対象を追加・変更したら、`SHA256SUMS.txt` 自身を除く追跡対象ファイルをパス順に並べて SHA-256 を更新する。
