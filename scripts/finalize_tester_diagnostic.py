from pathlib import Path
import hashlib
import json
import subprocess

p=Path("CHANGELOG.md");s=p.read_text()
section='''## 2026-09-13：Strategy Tester診断ログを追加（売買挙動は変更しない）

- Strategy Tester時だけ、`g_status` が変化したときに `[MT3 TESTER DIAG]` を1行出力する診断を追加。実運用では出力しない。
- 診断行には銘柄、現在status、scan/universe、接続・売買許可、履歴、Monte Carlo ready/allowed、RiskMode、サンプル数、MC上限、口座/銘柄の未解決注文、既存エクスポージャ状態を含める。
- 同じstatusの連続出力は抑制し、`EnableTradeLog=false` でもテスター診断は有効。注文可否、スコア、SL/TP、ロット、リスク計算、保存キー、AI protocolは変更しない。
- 診断回帰8チェックを追加し、統合模擬実行は573 / 573。既存JSON 55、静的監査495、CSV20、13ソース差分監査も通過。
- **MetaEditorネイティブコンパイルと、この診断版を使った実機Strategy Tester再実行は未実測。**

'''
marker="## 2026-09-13：Strategy Testerのライブ接続必須条件を修正"
if s.count(marker)!=1: raise SystemExit("CHANGELOG marker mismatch")
p.write_text(s.replace(marker,section+marker,1))

p=Path("VALIDATION_JA.md");s=p.read_text()
old="**配布する実ソースの模擬実行565チェック（既存500＋ロック43＋Strategy Tester接続22）、JSON回帰55チェック、既存静的監査495チェック、CSV集計20チェック、13ソースの差分照合が通過しました。ネイティブコンパイル未実測です。修正後の実機Strategy Tester・実際のAI API通信も未実測で、EX5は同梱していません。**"
new="**配布する実ソースの模擬実行573チェック（既存565＋Strategy Tester診断8）、JSON回帰55チェック、既存静的監査495チェック、CSV集計20チェック、13ソースの差分照合が通過しました。ネイティブコンパイル未実測です。診断版の実機Strategy Tester・実際のAI API通信も未実測で、EX5は同梱していません。**"
if s.count(old)!=1: raise SystemExit("VALIDATION summary mismatch")
s=s.replace(old,new,1).replace("565件の独立した相場シナリオや、収益性の検証という意味ではありません。","573件の独立した相場シナリオや、収益性の検証という意味ではありません。",1)
section='''## Strategy Tester診断ログの追加検証

Strategy Testerで取引数0が継続する場合に、売買条件を変更せず停止地点を特定できるよう、テスター時だけstatus変化を `[MT3 TESTER DIAG]` として出力します。同一statusの連続出力は抑制し、実運用ではこの診断を出力しません。診断には接続・売買許可、履歴、Monte Carlo状態、RiskMode、サンプル数、未解決注文、既存エクスポージャなどの読み取り専用状態を含めます。

追加8チェックで、テスターの拒否status記録、同一statusの重複抑制、次段階statusへの更新、実運用で診断状態が変化しないことを確認します。13ソース差分監査では診断用フィールド・初期化・診断関数・呼び出しだけを厳密に投影して既存配布ソースと比較します。

'''
marker="## Strategy Tester接続判定の追加検証"
if s.count(marker)!=1: raise SystemExit("VALIDATION section mismatch")
s=s.replace(marker,section+marker,1)
oldrow="| 本体・Worker模擬実行 | 565 / 565 | 既存500＋ロック43＋Strategy Tester接続22 |";newrow="| 本体・Worker模擬実行 | 573 / 573 | 既存565＋Strategy Tester診断8 |"
if s.count(oldrow)!=1: raise SystemExit("VALIDATION row mismatch")
p.write_text(s.replace(oldrow,newrow,1))

p=Path("verification/validation_summary.json");d=json.loads(p.read_text());d["checks"]["integration_results.json"]={"passed":573,"failed":0};d["revision"]="v2.44 lock reinitialization + Strategy Tester connection fix + tester-only status diagnostics; version unchanged";d["strategy_tester_status_diagnostics"]={"passed":8,"failed":0,"included_in_integration_total":True,"native_mt5_backtest":"NOT_MEASURED"};p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n")

files=[x for x in subprocess.check_output(["git","ls-files"],text=True).splitlines() if x!="SHA256SUMS.txt" and Path(x).is_file()]
Path("SHA256SUMS.txt").write_text("\n".join(f"{hashlib.sha256(Path(x).read_bytes()).hexdigest()}  {x}" for x in sorted(files))+"\n")
for line in Path("SHA256SUMS.txt").read_text().splitlines():
 h,x=line.split("  ",1)
 if hashlib.sha256(Path(x).read_bytes()).hexdigest()!=h: raise SystemExit("SHA256 mismatch: "+x)
print("SHA256SUMS verified")
