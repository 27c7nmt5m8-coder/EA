# 実EA開発由来 Semantic Regression shadow pilot

この文書の実測履歴は当初、PR #18の未マージbranch `feat/jev-experimental-benchmarks`、
head `ca2f7da9d65cf68433fd7d791e6dafe16ea3c1f1` を基点にしたstacked PRで取得しました。
PR #23でtoolingをpost-#21 mainへ統合した後は、その旧branch祖先関係を新規実行条件にはしません。
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

live前にtrackedでcleanなfixture／manifestを要求します。fixture内のsource PR SHAは
歴史provenanceであり、現在の実行headがその旧stackの子孫であることは要求しません。
新規runのbaseは現在のorigin/mainを使い、historical rowsの再集計ではrowに記録済みのbaseを保持します。
統合後の新規Aは `gpt-6.1-sol / high`、BはpolicyのJev modelによる直接typed choice評価。
xHighはHighレビュー後に具体的な未解決証拠が残った場合だけ追加レビューとして使用します。
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
  新規測定にはattempt IDを付け、同一IDの再読込は二重加算せず、同じIDの矛盾は拒否。
  凍結済み旧形式はrow全体hashで完全コピーを除外します。旧形式には独立した試行IDが
  ないため、同一内容の独立実行とコピーを区別できない限界を明記します。
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
review_skip_enabled=false、confidence_threshold=0.90を維持。2026-09-30の実測は当時のxHigh policyによる履歴であり、統合後の新規live実行はHigh-firstに従う。
shadow-onlyでありEA品質保証、レビュー代替、Jev最終承認、CI必須gate、常用化、merge制御に
使いません。pilot成功だけで採用しません。rollbackは統合PR #23を閉じる／評価差分をrevert。旧stacked PR群はhistorical provenanceとして保持します。

実測結果と独立レビューはPR本文にも記載します。MetaEditorは今回のsemantic検証の必須条件に
追加しませんが、製品release gateの未実行状態は正確に区別します。

## 2026-09-30 live結果

19 unique cases、38 provider calls、retry 0。credentialの存在確認後に実行しました。
run `semantic-real-20260930T140036994472`。fixture SHA-256
`0cf1b672be68ab83188cbed89b2e33ebce1e0ed8ee118e4bf39c70388844a2e0` を
live前のlocal commit `6c07b19` で凍結。GitHubへ公開したcommitはメタデータが異なりますが、
その初期tree `b6031662e5eed3022425f116a6a90a4532431d78` は実行treeと一致します。
以後fixture／oracleは編集していません。safe metadataはgitignoreされたローカル専用prefixへ
保存し、GitやCI artifactへraw traceを追加していません。

### 1. 品質

| 指標 | Sol A | Jev B |
| --- | ---: | ---: |
| TP / TN / FP / FN | 15 / 3 / 0 / 0 | 15 / 4 / 0 / 0 |
| binary scored / 全case | 18 / 19 | 19 / 19 |
| unknown / unavailable | 1 / 0 | 0 / 0 |
| recall | 15/15 | 15/15 |
| specificity | 3/3 | 4/4 |
| precision | 15/15 | 15/15 |
| accuracy（二値判定のみ） | 18/18 | 19/19 |
| confidence mean（19件） | 0.989737 | 0.952632 |
| confidence < 0.90 | 0 | 2 |

Critical Jev miss **0、監査5/5回帰**。Important miss **0、監査10/10回帰**、個別missなし。
Critical総caseは6件で、残り1件はnon-regression controlです。
agreementは二値同士18/18、全caseで同一choiceは18/19。
ER003（診断観測control）はSol unknown、Jev no_regression/confidence 0.54。
ER013（retry identity control）はJev no_regression/confidence 0.66。
0.90未満を自動承認へ使いません。raw accuracyをconfidence適格率と混同しません。
全caseの二値比較が揃わないため現行集計verdictは **UNMEASURED**
（live未実行の意味ではなく、全比較の成立条件不足）です。
tokenだけで成功／品質維持／採用を宣言しません。

### 2. Token

| provider | input | output | total | usage coverage |
| --- | ---: | ---: | ---: | ---: |
| Sol | 298,930 | 2,914 | 301,844 | 19/19 |
| Jev | 9,499 | 916 | 10,415 | 19/19 |
| 実験のA+B合計 | — | — | 312,259 | 38/38 |

Solは各caseを新しいCLI contextで実行しており、共通CLI prefixとcached input233,088を含む
reported input tokensです。実開発全体の削減率として外挿しません。
combinedは両方式を測るために消費した総量であり、Jev-onlyの本番workflowコストではありません。

### 3. 費用

null。GPT-6.1とprovider双方の今回適用される単価／請求根拠を揃えていません。
historical Sol価格の転用や0円推定はしていません。

### 4. 時間

Sol処理時間和304.503643秒、Jev処理時間和10.371709秒（各19/19）。
serial run wall time315.364526秒。起動・共通contextの差を含みます。

### 5. Context retrieval

null／未観測。固定4フィールド分類でrepository discoveryを実施していません。

### 6. Rework / test failure

null／未観測。開発タスクを実行した評価ではありません。offline評価コードのテスト結果は
pilotの開発test failureと分離して報告します。

### 7. Coverage / missing data

case19/19、回答38/38、usage38/38、時間38/38。malformed／provider unavailable 0。
Sol unknown 1、Jev低confidence control 2、費用と開発工程指標は欠測。
CLI backendのeffective model/effortはイベントに公開されず、要求値の証拠を保存しています。
既存測定JSON65ファイルはhash不変、ローカルreal-tasks.jsonは不在で新規作成していません。
外部にある30/50 cohort内容を新たに監査したという意味ではありません。

### 8. Limitations

小規模で作成者固定の要約mutationです。契約と適合baselineを与えるため、実PRの未知の
要求を探索するレビューより狭い問題です。confidenceの校正や新しい人間の盲検ラベル、
実開発での再作業／品質維持は未検証。EA品質や安全性の保証、レビュー省略、常用化の
根拠にしません。synthetic／Trace／Jevgrep／real-task cohortは再実行・混合集計していません。

独立レビューで「同じrowのコピーがtoken二重加算になる」Importantを検出しました。
回帰テストで30→15 tokensとなることをRed→Green確認し、attempt ID・旧形式完全コピー
検知・同一ID矛盾拒否を追加。原19件には重複がなく、fixtureもlive結果も編集せず、
同じ記録を再集計して全品質・token・時間が変わらないことを確認済みです。

## 評価コードの検証・独立レビュー

focused offline test22件、全Python unittest183件成功（skip1）。
初期公開treeの[push CI 36726547333](https://github.com/27c7nmt5m8-coder/EA/actions/runs/36726547333)
はLinux offline-validation／native-windows成功。修正後の最終head CIはPR本文で確認します。
ローカルtests/run_all.pyは既存Windows g++を指定するとGates1/2がApplication Controlで
BLOCKED、Gates3/4/5はPASS。最初のtoolchain未検出による失敗と区別しています。
MetaEditorは未実行で、Authoritative releaseは今回のsemantic検証の完了と区別します。

GPT-6.1 Sol xhighの独立レビューでImportant1件を修正し、修正差分を再レビュー。
未解決Critical0／Important0／Minor0。レビュアー自身も22テスト、一次資料hash、
集計再現、fixture／65履歴の不変、Critical miss保持、重複加算修正を確認しました。
レビュー用agentの初回capacityエラーは同じmodel/effortで再試行し、代替modelは使いませんでした。
