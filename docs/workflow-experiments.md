# Jev追加検証: 7 / 8 / 9

この文書は開発ワークフローの **shadow experiment** を定義する。EA本体、Worker、売買判断、Risk/Safety判定、レビューの最終承認、GitHub mergeの判断には使用しない。既存の [30/50件の実タスクcohort](workflow-real-shadow.md) と独立したfixture、実行結果、分母を持つ。`cohort-record` と `.workflow-eval/real-tasks.json` へ、以下のpilotや再実行を登録しない。

## 実験の共通条件

- A/Bは同一task ID、同一base SHA、同一Sol modelとeffortを一組とする。片側の失敗、provenance不一致、古いbaseの結果を成功ペアに含めない。再実行やarmを新しいtaskとして数えない。
- `review_skip_enabled=false`、`confidence_threshold=0.90`、protected / critical / unknown dependencyのSol xHigh必須を維持する。Jevのラベルや検索結果はSolへ渡す候補情報であり、承認ではない。
- fixtureは架空の安全な内容だけを追跡する。実trace全文、prompt、秘密、APIキー、口座情報、実取引ログを結果JSON、Git、CI artifactに保存しない。外部送信は明示的なlive指定の時だけ行う。
- 欠測は `null` と理由およびcoverageで示す。API/CLI timeout、非0終了、usage欠落、OS非対応を成功や0費用として扱わない。品質の分母とtoken比較の有効ペア数を分ける。
- pilotの件数は採用条件ではない。critical miss、protected領域の必須file漏れ、Aより悪い品質、未測定の費用・品質は個別に報告する。

## 実行方法

Repository rootからPython 3.11以上で実行する。通常実行はofflineで、fixtureと分離した結果ファイルを作るだけである。`--live` は追跡済み・未変更の専用fixtureに限り、現在の `origin/main` とfixtureのbase SHAが一致した場合だけ外部呼出しを許す。プロバイダー料金が発生し得るため、pilotのlive実行は個別に明示して行う。

```powershell
python -m tools.workflow_eval.cli trace-benchmark
python -m tools.workflow_eval.cli semantic-regression
python -m tools.workflow_eval.cli jevgrep-benchmark
python -m tools.workflow_eval.cli experimental-report --trace-rows .workflow-eval/<trace-rows.json> --semantic-rows .workflow-eval/<semantic-rows.json> --jevgrep-rows .workflow-eval/<jevgrep-rows.json>
```

Traceのlive A/Bは `trace-benchmark --live`、意味回帰のlive比較は `semantic-regression --live`。Jevgrepは通常探索のA-arm metadataを `--a-observations` で渡し、`--source-allowlist` に送信を認めた `src/*.mqh` / `src/*.mq5` のJSON配列を指定してから `jevgrep-benchmark --live` を実行する。このliveコマンドは**検索部分だけ**を実行し、結果を `RETRIEVAL_ONLY` として記録する。Windows nativeでは `UNAVAILABLE / unsupported_environment` になる。Solのtask successやtokenがない段階では完全なA/Bと数えない。

後段のSol測定を対応付けるには、liveで得た `jevgrep-*-rows.json` のSHA-256をB観測の `discovery_rows_sha256` に記録する。B観測には同じtask ID・base SHA・`gpt-6-sol` / `xhigh`、`sol_status=OK`、task success、Sol usage、時間、追加探索、再作業、test failureなど実測metadataを入れる。A観測も同じtask/base/model/effortで別に取得する。次に `jevgrep-benchmark --discovery-rows <live-rows.json> --a-observations <a.json> --b-observations <b.json> --source-allowlist <approved-paths.json>` を実行する。この処理はBの検索結果と後段のSol数値を、元の検索結果ファイルのdigest・source fingerprint・cache bypassに結び付ける。観測値は独立監査した記録に限り、JSON自体はprovider実行の暗号学的証明ではない。別途 `--a-observations` と `--b-observations` だけのoffline評価もできるが、Bの成功ペアには同じallowlistのsource fingerprintとcache bypassが必要である。すべての出力はgitignoreされた `.workflow-eval/` の専用prefixであり、既存の `real-tasks.json` は更新しない。

## 7. Agent Trace Evaluation

約10件のsynthetic/redacted trace fixtureで、Aは必要なtraceをSolが直接評価し、BはJevがsegmentを `progress`、`repetition`、`context_missing`、`rework`、`blocked`、`completed`、`unknown` に分類した後、関連segmentだけを同じSolへ渡す。Jev回答はlabel、0〜1のconfidence、根拠segment IDを検証する。保存するのはID、ラベル、usage、時間、expected label、判定などのmetadataだけである。

Sol入出力・合計tokens、Jev tokens、両者合計、時間、ラベル正確度、false positive/negative、必要contextやblockedの見逃し、repetition検出、追加context取得、rework、test failure、critical/important missを別々に測る。Solの最終レビューは両armで必要であり、Jevで省略しない。

## 8. Semantic Regression Testing

既存の [workflow evaluation](workflow-evaluation.md) のfixture形式と評価概念を再利用するが、過去の `workflow_eval_cases.json` は変更しない。専用の人間固定ラベルを持つ20件以上のmutation fixtureを使う。必要context欠落、単位・数値、`null` / unavailable、古いevidence、要求の一部欠落、安全文言の弱体化、protected挙動、曖昧な要求、矛盾するevidence、無関係なcontextを含む。

検出・見逃し、false positive/negative、critical/important miss、confidence、Sol/Jev一致、各token、時間を計測する。critical semantic regressionをJevが見逃した結果は実験レポートで `BLOCKED` とする。この状態はEAの操作、既存CIのrelease gate、GitHub mergeを自動制御しない。

## 9. Jevgrep Benchmark

[Jevgrep公式repository](https://github.com/dzhng/jevgrep) のCLIを任意の明示的live pilotで使う。観測時の `@dzhng/jevgrep 0.4.4` を記録するが、実行時には実際のCLI versionを記録する。Node.js 22以上、macOS/Linuxが公式対応であり、Windows nativeは `UNAVAILABLE / unsupported_environment` とする。通常のoffline testやCIは `jg` をglobal installせず、fake executableを使用する。`jg skill` は実行せず、Codexの常用Skillにも登録しない。

Aは通常の`git diff`、直接read、`rg`等から探索を始める。BはJevgrepから探索を始める。既知symbol/pathのexact lookupと、コードの役割から探すsemantic discoveryを別集計する。各caseに人間固定のmust-find filesとrelevant filesを置く。Fintokei、entry rejection、Monte Carlo、BE/Trailing、Worker通信境界など保護領域は**検索結果だけ**を評価し、製品コードは変更しない。

Jevgrepは検索対象sourceを外部providerへ送信する。既存ignoreを安全保証とせず、live実行前に明示した配布可能なfile allowlistから一時rootを作り、pathと内容を検査する。秘密やprivate logが疑われる場合は送信を拒否する。結果にはsource本文やCLI stdoutを保存しない。

成功率、must-find recall、relevant-file precision/recall、余分なfile read、source/context bytes、Sol入出力・合計tokens、Jevgrep/Jev tokens、合計tokens、時間、追加検索/context取得、rework、test failure、important/critical file漏れを測る。provider usageや単価の根拠がない費用は `null` とする。[公式の10件Python SWE-bench比較](https://github.com/dzhng/jevgrep#what-we-measured) の削減率をEAへ外挿しない。MQL5は同CLIのPython/TypeScript向けstructural parsingとは条件が異なり、pilotから一般化しない。

## 結果の読み方とrollback

`experimental-report` は必ず、(1)品質、(2)token、(3)費用、(4)時間、(5)context retrieval、(6)rework/test failure、(7)coverage / missing data、(8)limitationsを分けて出力する。各実験のpilot statusを別々に示す。critical missが0件でも、品質coverageが欠ける場合は品質維持を認定しない。

固定fixtureのID全体を分母にし、未実行・比較不能ケースをcoverageへ示す。fixtureのdigestが変わった古い結果は現在の結果として集計しない。Jevgrep検索後のSolが失敗・未実行でも他ケースの集計は継続する。そのケースはA/B比較から除外し、検索自体のstatusとSolのstatusを別に記録する。取得済みのusage・file漏れは残し、critical file漏れのBLOCKEDを消さない。

停止するにはlive flagを使わず実行を止める。実装を撤回する場合は本PRの開発補助コード・fixture・文書をrevertしてchecksumを更新する。既存EA、CI、30/50 cohortには移行処理はない。
