# 実EA開発由来 Semantic Regression shadow pilot

PR #18の未マージbranch `feat/jev-experimental-benchmarks`、head
`ca2f7da9d65cf68433fd7d791e6dafe16ea3c1f1` を基点にした独立stacked PRです。
製品の変更ではなく、既存のtyped choice検証・numeric telemetryを再利用します。

## 固定fixtureと一次資料

`tests/fixtures/workflow_semantic_real_cases.json` は19の異なる契約です。
PR #11から4、#12から5、#17から6、#18から4件。
回帰15、非回帰control 4。Critical 6、Important 13、Minor 0。
PR #11/#12は未マージであり、その製品差分は取り込んでいません。

各caseに元PRのhead、source file SHA-256、実在するtest/spec anchor、
permalink、契約・適合baseline・candidate・expected result・根拠を記録します。
provenance manifestはcase全体のfingerprintを固定し、oracle変更を検出します。
expected resultは確認済みの仕様／テストから作成者が固定したもので、新たな人間の
盲検ラベル付けを行ったという意味ではありません。独立レビューで出典と対応を確認します。

Fintokei UI副作用のcaseはPR #12のRed commit
`aa5a4a1327d6d7e5be435abecc9eedcfb6a1db1e` と修正
`f19614d3a78259f27ee05ca1334c4ae9115a63d9`、対応CI失敗／成功を根拠にします。
レビュー本文そのものはGitHub review submissionsから取得できず、PR本文・検証記録と
実テスト／修正から確認しています。新しい不具合を想像したoracleではありません。

provider payloadは `requirement / baseline / candidate / evidence` の4フィールド。
ID、PR番号、severity、expected result、rationale、レビュー結論は送りません。
全文source・秘密・private traceは送りません。答えを直接指定する表現を拒否します。
契約そのものを与えるため、未知の要件を発見する能力を測る実験ではありません。

通常offline CIでは未マージPRのGit objectがない場合、commit済みの一次確認manifestを
検証します。自動fetchはしません。live時は実Git objectのfile hashとanchor照合を必須にし、
不足時は停止します。source headは歴史的出典であり、最新headに自動置換しません。

## 実行

```text
python -m tools.workflow_eval.cli semantic-real
python -m tools.workflow_eval.cli semantic-real --live
python -m tools.workflow_eval.cli semantic-real --rows .workflow-eval/semantic-real-<run>-rows.json
```

live前にtrackedでcleanなfixture／manifestを要求します。
新規Aは `gpt-6.1-sol / xhigh`、BはpolicyのJev modelによる直接typed choice評価。
A/Bは同一case・payload・base・fixture fingerprintを共有します。
これはSol対Jevの分類比較であり、Bで後段Solを実行するtrace/retrieval pipelineではありません。
Sol model/effortはCLI要求値を確認しますが、CLI JSONがbackendのeffective model/effortを
公開しない場合、それを実測済みとは主張しません。違うmodel/effortの観測は比較から除外します。

`.workflow-eval/semantic-real-<run>-*` にmetadataのみを排他的新規作成します。
raw prompt／provider response／traceは保存しません。過去結果を上書きしません。
各case終了時にmetadataを保存し、再集計ではproviderを呼びません。
credential欠測はUNAVAILABLE、API/CLI失敗は成功に変換しません。
default offlineは未測定を保存するだけでmockをliveに見せません。

## 集計

- **品質**：最初のcurrent試行をcase単位のTP/TN/FP/FNへ採用します。unknownは二値行列から
  分離し、未測定も別に記載。recall/specificity/precision/accuracyは実際の分子・分母を保持。
  全case数、severity、回帰／controlの母数も保持します。
- **安全観測**：全current試行のJev `no_regression / unknown` を監査します。
  Critical回帰のmissが一つでもあれば実験のみ `BLOCKED_CRITICAL_MISS`。
  retry成功・Sol検出・pair除外でも消しません。Important missもcase IDを列挙。
  未実行はmiss 0による合格にせず、監査coverage不足として扱います。
- **confidence**：数値検証後、mean、coverage、0.90未満件数を報告。
  accuracyはモデルの分類自体を測る値であり、confidenceで自動承認しません。
- **token**：各providerのinput/output/totalと取得済みsubtotal、試行coverage。
  retryを含む全current試行を一度ずつ課金観測へ加算し、case数には加算しません。
  combinedは実験のA+B消費合計。全case／全試行usageが揃わなければnull。
- **費用**：現行model・provider単価の根拠がなければnull。historical Sol単価を流用しません。
- **時間**：provider処理時間の和とrunのwall timeを分離。欠測はnull＋理由。
- **context retrieval / rework / test failure**：固定contextの分類実験では実開発工程を
  実行しないため未測定。ゼロにしません。
- **coverage**：欠測case、usage取得試行数、unknown、unavailable／malformedの理由。
  stale fixture/base/payload結果は現在集計から除外し、除外件数を明記します。

## 制約と非変更領域

synthetic20件、Trace、Jevgrep、過去UNAVAILABLE、policy、30/50 real-task cohortを
変更・再実行・混合集計しません。このcohortは実PR由来の固定mutationで、実タスク件数ではありません。
EA本体／src／売買・Risk・安全・Workerの変更はありません。
review_skip_enabled=false、confidence_threshold=0.90、protected/unknownのxhighを維持。
shadow-onlyでありEA品質保証、レビュー代替、Jev最終承認、CI必須gate、常用化、merge制御に
使いません。pilot成功だけで採用しません。rollbackはこのstacked PRを閉じる／評価差分をrevert。

実測結果と独立レビューはPR本文にも記載します。MetaEditorは今回のsemantic検証の必須条件に
追加しませんが、製品release gateの未実行状態は正確に区別します。
