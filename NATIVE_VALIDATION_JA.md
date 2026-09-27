# Application Controlを維持したnative検証

## 5-gateの定義

既存 `tests/run_all.py` の順序を維持する。MetaEditorは5-gateの外にある追加のrelease条件。

| Gate | 検証・実行方法（`python -X utf8 tests/` 以下） | 必要環境・依存 | correctnessとの関係 |
|---|---|---|---|
| 1 | `verify_v244.py`、582 assertions | Python＋x64 GCC C++17、native実行 | 本体・Worker・全headerを展開したmock。RNG、MC/DD、risk、注文保護、Tester診断等 |
| 2 | `verify_json_regression.py`、55 cases | Python＋x64 GCC C++17、native実行 | 実JSON parser、UTF-16、schema、応答状態。実API通信ではない |
| 3 | `verify_stats.py`、20 cases | Pythonのみ、Windows依存なし | CSV集計・独立数値fixture |
| 4 | `audit_source.py`、495 assertions | Pythonのみ、Windows依存なし | 製品ソースの静的契約 |
| 5 | `verify_lock_scope.py`、13 files | Pythonのみ、Windows依存なし | 既存baselineに対する厳密ソース照合 |

全gateはCI再現可能。ただしローカルでblockedになる1/2だけをdelegateする。
既存Ubuntuの全5-gate CIは補完検証として維持。Windows固有のMetaEditorはローカルに残す。
Strategy Tester診断のmock回帰はGate 1に含む。今回実市場バックテストは追加していない。

## 直接診断（2026-09-27）

CodeIntegrity/Operationalを読み取り、3077と3033の同一path・近接timestampを照合した。
3077のpolicyは `VerifiedAndReputableDesktop`、statusは `0xc0e90002`、要求署名level 2／検証level 1。
これはApplication Controlのenforcement拒否。3033単独では原因を断定しない。
[Microsoftのevent定義](https://learn.microsoft.com/en-us/windows/security/application-security/application-control/app-control-for-business/operations/event-id-explanations)参照。

| binary（ユーザー固有root省略） | 3077 UTC | event Flat SHA-256（通常のファイルSHA-256） | 現存との対応 |
|---|---|---|---|
| GCC `ucrt64/lib/gcc/x86_64-w64-mingw32/16.2.0/cc1plus.exe` | 2026-09-27 08:32:32.1786949 | `4df3595cccc0f75158adde105cf350cb8ff741c73c2ef2b03f7d671597969d83` | 一致、NotSigned、PE 8664/x64 |
| GCC `ucrt64/bin/g++.exe` | 2026-09-26 22:24:12.4624880 | `58efe82fa3ce35005f89d46fe439d7ee54e6889cb7db894019202da691a529a5` | 一致、NotSigned、PE 8664/x64 |
| indicator検証checkout `verification/integration.exe` | 2026-09-24 03:54:16.0188013 | `c54c01c5ee273e08a410587f0530e3642dcd31e06df94e578f794ea19c692a01` | 一致、NotSigned、PE 8664/x64 |
| 別checkout `verification/json_test.exe` | 2026-09-23 21:57:05.9917619 | `af504195535a4ddd035c91d95e0fad0d1abb19547b42e844eafa35c09556798f` | 現存は別hash。過去の拒否証拠のみ |

cc1plusの3033は同日08:32:32.0342219 UTC、integrationの3033は同日03:54:16.0144982 UTC。
親processはcc1plusがg++、生成exeがPython。対象はexe起動時の拒否で、これらの記録はDLL拒否ではない。
Win32 4551のシステムメッセージもApplication Control policyによるblockを示す。
ただし今回、既存integrationを一度起動した結果は `0xc0000135`（DLL不足）であり、
4551を新規再現したとは記載しない。現行GCCのハッシュ一致3077をpreflightの根拠とする。
`g++ --version` は現在実行可能で16.2.0 Rev4（MSYS2）だが、その成功はcc1plusの実行許可を意味しない。

## ABIとCIの等価性

旧Ubuntu CI単独は **PARTIALLY_EQUIVALENT**。Linux LP64の`long=8`とWindows LLP64の`long=4`が異なり、
旧mockの`datetime=long`もWindowsでは不十分だった。MQLのlong/datetimeは8 byte。
[MQL5型仕様](https://www.mql5.com/ja/docs/basis/types/integer/datetime)参照。

`native_adapter.py`は標準headerの後で、生成された製品/mock/scenarioの型tokenだけを
`int64_t/uint64_t/uint32_t`へ変換する。文字列・コメント・ネイティブ`long long`は維持。
製品ソース、既存fixture、expected value、MC/RNG数式は変更しない。

| 比較 | ローカル想定 | authoritative CI |
|---|---|---|
| OS / arch | Windows 11、x64 | Windows Server 2025 runner、x64 |
| compiler | MSYS2 UCRT64 GCC 16.2.0 Rev4 | MSYS2 UCRT64 GCC（実versionをartifact記録） |
| runtime / ABI | UCRT、MinGW-w64、LLP64 | 同じruntime/ABI family |
| native `long` / pointer | 4 / 8 byte | runtime reportで4 / 8を確認 |
| MQL `long` / `ulong` / `datetime` / `uint` | 8 / 8 / 8 / 4 | static_assert、64bit arithmetic、2040年UTC roundtrip |
| flags | `-std=c++17 -O1 -Wall -Wextra`（統合）、`-O2`（JSON） | 同じscripts・flags、追加defineなし |
| files / fixtures / command | exact HEADのsrc＋tests、既存fixture | clean exact HEAD checkout、同じ2 scripts |
| expected | 統合582/失敗0、JSON55/失敗0 | 同じassertions、ABI契約`mql64-v1`も必須 |

Windows CIの上記契約を満たすPASSは、これらのoffline deterministic試験の目的について
**EQUIVALENT**と扱う。OS buildや署名許可、実MT5/broker/API環境の完全一致を意味しない。
Ubuntuのみ、ABI不一致、Windows job未実行／失敗は代用不可。新toolchainでも契約を満たさない限り緑にしない。

## 実行と正式判定

GCCの既存installのbinを通常のprocess PATHに設定してから実行する（バイナリの移動・改名はしない）。
PythonのUTF-8 modeを使用する。preflightは既存3077最大256件と現在のcompiler/cc1plus/生成exeを
path suffix＋SHA-256で対応付ける。既知blockならnativeを起動せずBLOCKED、Python gateは続行。
ログ読取不能／一致なしはUNKNOWN。実行時4551/577/1260もBLOCKEDで、native再試行はしない。
それ以外のcompile/assertion/DLL不足はFAIL。古いblock記録は保守的な停止根拠であり、現在の許可状態の保証ではない。

```powershell
python -X utf8 tests/run_all.py
# BLOCKEDがあれば終了1、full INCOMPLETE。これだけでrelease PASSにはならない。

python -X utf8 tests/run_all.py --ci-run <push-run-id> `
  --metaeditor '<MetaEditor64.exeのpath>' --mql-include '<MQL5 root>'
```

集約はGitHub APIからrepository、branch、exact HEAD SHA、`.github/workflows/ci.yml`、
push/workflow_dispatch event、最新attempt、`native-windows` jobと必須steps、
SHA/attempt対応artifactの存在と有効期限を照合する。PR merge SHAや別HEADの成功は採用しない。
CI状態が取得できなければUNKNOWN。public repoはtoken不要、privateは環境変数GH_TOKEN等を利用可能だが表示・保存しない。

**必要条件**: cleanで実行中も変わらないcheckout ＋ Gate 3/4/5のローカルPASS ＋
Gate 1/2のローカルPASSまたはBLOCKEDに対応するexact HEAD Windows CI PASS ＋ 本体/Worker MetaEditor 0 errors/0 warnings ＋
指定base（既定origin/main）とのsrc/set差分なし。
authoritative releaseにはローカルnativeが実行可能な場合もexact HEAD Windows CI PASSを必須とする。
FAILはCIで上書きしない。BLOCKED、NOT_RUN、UNKNOWN、DELEGATED_TO_CIはPASSではない。
`--native-only`はCIで1/2だけを実行し、full/release PASSを出さない。

当回結果は `.validation/gate_result.json` と関連ログへ保存する。同梱verificationの過去記録は復元し、
未実行gateに過去結果を流用しない。MetaEditorは隔離コピーのみをcompileし、MT5起動・EX5配備を行わない。
CI artifactは30日保持。期限切れ時は同じHEADでCIを再実行する。ログ・JSONのみ保存しexeは公開しない。

Windows security、execution policy、trust storeは一切変更しない。
将来ローカルnativeを必須にするなら、既存policyが認めるtrusted code signingは検討候補だが、
署名だけで必ず許可されるわけではない。今回は署名基盤・証明書購入・trust追加は行わない。
