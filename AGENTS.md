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
