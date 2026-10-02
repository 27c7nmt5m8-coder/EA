判定は **NEEDS_MORE_TESTING**。固定12条件をMT5 build 6230で完走した。通常負荷／CPU競合の全6組でTick・Bar処理数、Opportunity単位Funnel、Tradesが一致し、Runtime error／warningは全12件0。500kを製品採用していない。commit・push・PR・merge・Live取引は行っていない。

更新後の旧PID 22744は開始時刻・実行imageを含めた読み取り専用のプロセス照合で同一プロセス不在を確認した。所有外プロセスを終了・kill・再起動せず、GUI操作も行っていない。旧6182 pilotは別記録として保存し、6230集計から除外した。terminal/metaeditor/metatesterのversion 5.0.0.6230とSHA-256を固定し、実行前後にsource/set/EX5/engine hashesを照合した。最後の読み取り確認でもMT5/Tester/liveupdateプロセスは存在しなかった。残り条件0、再開作業にユーザー操作は不要だった。監視自動化は停止状態を維持する。

条件は2 Symbol=USDJPY/EURUSD、3 Symbol=さらにEURJPY、4 Symbol=さらにXAUUSD。各群でCurrent20k／fixed500k × NORMAL／CPU_CONTENTION。USDJPYチャートM1、2026-09-14〜09-19、real ticks、USD100,000、1:1000、AUTO、最適化・Forwardなし、既存High入力を固定した。元setは無変更。TesterコピーのScanMode/CustomSymbolsだけで銘柄群を指定した。XAUUSDもFX High入力2.60×0.40のため、XAU専用preset検証や性能・利益評価には使わない。

CPU_CONTENTIONは所有するterminal・verified Tester descendant・算術busy-loop workerを同一CPU affinity mask 1に固定した実CPU競合。sleep負荷ではない。NORMALとの差は単一core制限と競合workerの組合せであり、CPU使用率百分比は未測定。低速物理PCの代用としてPASS扱いしない。

同時heavyは同じEA/Testerプロセス・同じイベントループに独立した2/3/4 SHADOW contextを同時activeにする再現負荷。各contextは同じ30標本の合成入力、同じRNG・bootstrap・閾値で20,000,000演算を実行し、出力は製品判断・注文・履歴・Riskへ渡さない。並列実行ではない。自然な製品MC（ACTUAL）と合成負荷（SHADOW）は別集計。4 SymbolではUSDJPY/XAUUSDの自然heavy active区間が、完了snapshotだけの下限集計でCurrent18組、500k4組重なった（各負荷で再現）。EURUSD/EURJPYは自然heavyを開始していないため、自然な3/4 Symbol同時heavyは未再現。自然MCとSHADOWの重複は全件UNKNOWN。

以下の集計はNORMALのOpportunity単位。CPU_CONTENTIONのFunnel／Tradesも全件同値。同じ週の入れ子銘柄群を独立した市場サンプルとして合算しない。

| N | 方式 | Signal | Score | SL | Spread | Position前 | Position後 | MC ready | MC許可 | Risk pass | 要求 | 受理 | 拒否 | Trades | MC待ち | 有効性終了 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 20k | 142 | 98 | 96 | 72 | 72 | 50 | 47 | 47 | 47 | 47 | 47 | 0 | 47 | 3 | 3 |
| 2 | 500k | 141 | 97 | 95 | 71 | 71 | 49 | 48 | 48 | 48 | 48 | 48 | 0 | 48 | 1 | 1 |
| 3 | 20k | 221 | 143 | 141 | 112 | 112 | 81 | 78 | 77 | 77 | 77 | 77 | 0 | 77 | 3 | 3 |
| 3 | 500k | 220 | 142 | 140 | 111 | 111 | 80 | 79 | 78 | 78 | 78 | 78 | 0 | 78 | 1 | 1 |
| 4 | 20k | 295 | 198 | 196 | 167 | 167 | 124 | 119 | 118 | 118 | 118 | 117 | 1 | 117 | 5 | 5 |
| 4 | 500k | 294 | 197 | 195 | 166 | 166 | 122 | 121 | 120 | 120 | 120 | 119 | 1 | 119 | 2 | 1 |

Score reject=Signal−Score pass、Spread reject=spread_evaluated−spread_pass、Position reject=Position前−Position後。Risk failは全ケース0。EURJPYのcompleted-decision不許可1件はMC計算中とは分ける。4 Symbolの注文拒否1件はXAUUSD retcode10018 MARKET_CLOSEDで両方式・両負荷共通。CTrade bool=trueだけで受理に数えず、retcode10008/10009/10010とのANDで判定した。その他の説明不能な負荷間Funnel差0。詳細Symbol別Funnelはsummary.jsonに全件保存。

| N | 方式 | Symbol | Signal | Score | SL | Spread評価 | Spread pass | Position前 | Position後 | MC ready | MC許可 | 他Safety | Risk | 注文 | 受理 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 20k | USDJPY | 86 | 58 | 58 | 58 | 56 | 56 | 37 | 34 | 34 | 34 | 34 | 34 | 34 |
| 2 | 20k | EURUSD | 56 | 40 | 38 | 38 | 16 | 16 | 13 | 13 | 13 | 13 | 13 | 13 | 13 |
| 2 | 500k | USDJPY | 85 | 57 | 57 | 57 | 55 | 55 | 36 | 35 | 35 | 35 | 35 | 35 | 35 |
| 2 | 500k | EURUSD | 56 | 40 | 38 | 38 | 16 | 16 | 13 | 13 | 13 | 13 | 13 | 13 | 13 |
| 3 | 20k | USDJPY | 86 | 58 | 58 | 58 | 56 | 56 | 37 | 34 | 34 | 34 | 34 | 34 | 34 |
| 3 | 20k | EURUSD | 56 | 40 | 38 | 38 | 16 | 16 | 13 | 13 | 13 | 13 | 13 | 13 | 13 |
| 3 | 20k | EURJPY | 79 | 45 | 45 | 45 | 40 | 40 | 31 | 31 | 30 | 30 | 30 | 30 | 30 |
| 3 | 500k | USDJPY | 85 | 57 | 57 | 57 | 55 | 55 | 36 | 35 | 35 | 35 | 35 | 35 | 35 |
| 3 | 500k | EURUSD | 56 | 40 | 38 | 38 | 16 | 16 | 13 | 13 | 13 | 13 | 13 | 13 | 13 |
| 3 | 500k | EURJPY | 79 | 45 | 45 | 45 | 40 | 40 | 31 | 31 | 30 | 30 | 30 | 30 | 30 |
| 4 | 20k | USDJPY | 86 | 58 | 58 | 58 | 56 | 56 | 37 | 34 | 34 | 34 | 34 | 34 | 34 |
| 4 | 20k | EURUSD | 56 | 40 | 38 | 38 | 16 | 16 | 13 | 13 | 13 | 13 | 13 | 13 | 13 |
| 4 | 20k | EURJPY | 79 | 45 | 45 | 45 | 40 | 40 | 31 | 31 | 30 | 30 | 30 | 30 | 30 |
| 4 | 20k | XAUUSD | 74 | 55 | 55 | 55 | 55 | 55 | 43 | 41 | 41 | 41 | 41 | 41 | 40 |
| 4 | 500k | USDJPY | 85 | 57 | 57 | 57 | 55 | 55 | 36 | 35 | 35 | 35 | 35 | 35 | 35 |
| 4 | 500k | EURUSD | 56 | 40 | 38 | 38 | 16 | 16 | 13 | 13 | 13 | 13 | 13 | 13 | 13 |
| 4 | 500k | EURJPY | 79 | 45 | 45 | 45 | 40 | 40 | 31 | 31 | 30 | 30 | 30 | 30 | 30 |
| 4 | 500k | XAUUSD | 74 | 55 | 55 | 55 | 55 | 55 | 42 | 42 | 42 | 42 | 42 | 42 | 41 |

MC callbackの壁時計占有時間（ms）。OSのdescheduling待ちも含み、CPU実行時間ではない。ACTUALには完了・未完了cycle双方のcallbackを含む。中央値・p90・p95・p99・最大値を取得し、固定許容閾値を新設してPASS判定していない。
ACTUAL：

| N | 方式 | 負荷 | callback数 | median | p90 | p95 | p99 | max | 占有合計ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 20k | NORMAL | 26346 | 0.093 | 0.162 | 0.169 | 0.531 | 1.878 | 3383.188 |
| 2 | 20k | CPU_CONTENTION | 26346 | 0.091 | 0.151 | 0.155 | 1.03 | 5.527 | 3250.774 |
| 2 | 500k | NORMAL | 1843 | 3.04 | 4.264 | 4.969 | 5.437 | 6.334 | 5775.034 |
| 2 | 500k | CPU_CONTENTION | 1844 | 2.482 | 5.356 | 6.208 | 8.541 | 22.33 | 6012.531 |
| 3 | 20k | NORMAL | 26346 | 0.093 | 0.162 | 0.17 | 0.838 | 1.696 | 3360.955 |
| 3 | 20k | CPU_CONTENTION | 26346 | 0.092 | 0.152 | 0.156 | 1.029 | 4.142 | 3278.862 |
| 3 | 500k | NORMAL | 1846 | 2.735 | 4.149 | 4.963 | 5.339 | 12.347 | 5641.263 |
| 3 | 500k | CPU_CONTENTION | 1847 | 2.36 | 4.936 | 6.082 | 7.602 | 21.124 | 5884.969 |
| 4 | 20k | NORMAL | 49060 | 0.092 | 0.161 | 0.168 | 0.504 | 1.829 | 6032.47 |
| 4 | 20k | CPU_CONTENTION | 49060 | 0.091 | 0.15 | 0.153 | 1.023 | 5.568 | 5923.251 |
| 4 | 500k | NORMAL | 3124 | 2.808 | 4.128 | 4.963 | 5.339 | 9.525 | 9552.633 |
| 4 | 500k | CPU_CONTENTION | 3124 | 2.393 | 4.984 | 5.847 | 8.033 | 11.34 | 9838.252 |

SHADOW：

| N | 方式 | 負荷 | callback数 | median | p90 | p95 | p99 | max | 占有合計ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 20k | NORMAL | 2000 | 0.103 | 0.123 | 0.189 | 0.415 | 1.644 | 241.404 |
| 2 | 20k | CPU_CONTENTION | 2000 | 0.103 | 0.176 | 0.19 | 1.017 | 3.344 | 264.934 |
| 2 | 500k | NORMAL | 80 | 2.673 | 3.725 | 4.237 | 6.326 | 9.487 | 250.806 |
| 2 | 500k | CPU_CONTENTION | 80 | 3.482 | 7.102 | 7.802 | 8.683 | 8.817 | 327.083 |
| 3 | 20k | NORMAL | 3000 | 0.103 | 0.113 | 0.189 | 0.388 | 1.905 | 358.54 |
| 3 | 20k | CPU_CONTENTION | 3000 | 0.103 | 0.185 | 0.193 | 2.198 | 4.344 | 482.645 |
| 3 | 500k | NORMAL | 120 | 2.971 | 4.512 | 4.782 | 5.419 | 5.683 | 391.618 |
| 3 | 500k | CPU_CONTENTION | 121 | 3.066 | 6.95 | 7.857 | 8.344 | 9.857 | 472.69 |
| 4 | 20k | NORMAL | 4000 | 0.103 | 0.16 | 0.19 | 0.418 | 1.697 | 491.467 |
| 4 | 20k | CPU_CONTENTION | 4000 | 0.103 | 0.189 | 0.198 | 2.148 | 4.842 | 644.164 |
| 4 | 500k | NORMAL | 162 | 3.501 | 5.407 | 5.923 | 6.604 | 8.144 | 600.692 |
| 4 | 500k | CPU_CONTENTION | 163 | 3.847 | 6.659 | 7.951 | 9.031 | 9.57 | 708.812 |

MC生命周期はsnapshotのheavy start/completeと、明示されたCANCEL/RUN_ENDを分けた。未完了だけではcancelと数えない。以下はNORMAL。CPUでもstart/complete/cancel/censored件数、TimeCurrent差の中央値は一致した。TimeCurrent差は最後のquoteに基づく市場時刻差であり、Timerの正確な経過時計やwall-clockではない。SHADOWでは500k40〜43 callbackでもTimeCurrent差15秒となる。callback ordinalの開始／終了はobservations.jsonに残し、15秒をTimer40秒の代用にしない。Timer実経過の別時計はUNKNOWN。

| N | 方式 | Symbol | kind | 開始 | 完了 | cancel | 打切り | callback | 演算 | 市場median秒 | p95秒 | max秒 | callback占有合計ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 20k | USDJPY | ACTUAL | 19 | 17 | 2 | 0 | 26346 | 526920000 | 1499 | 1499 | 1499 | 3383.188 |
| 2 | 20k | USDJPY | SHADOW | 1 | 1 | 0 | 0 | 1000 | 20000000 | 995 | 995 | 995 | 120.341 |
| 2 | 20k | EURUSD | ACTUAL | 0 | 0 | 0 | 0 | 0 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | 0 |
| 2 | 20k | EURUSD | SHADOW | 1 | 1 | 0 | 0 | 1000 | 20000000 | 995 | 995 | 995 | 121.063 |
| 2 | 500k | USDJPY | ACTUAL | 35 | 34 | 0 | 1 | 1843 | 921500000 | 55 | 58 | 59 | 5775.034 |
| 2 | 500k | USDJPY | SHADOW | 1 | 1 | 0 | 0 | 40 | 20000000 | 15 | 15 | 15 | 122.567 |
| 2 | 500k | EURUSD | ACTUAL | 0 | 0 | 0 | 0 | 0 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | 0 |
| 2 | 500k | EURUSD | SHADOW | 1 | 1 | 0 | 0 | 40 | 20000000 | 15 | 15 | 15 | 128.239 |
| 3 | 20k | USDJPY | ACTUAL | 19 | 17 | 2 | 0 | 26346 | 526920000 | 1499 | 1499 | 1499 | 3360.955 |
| 3 | 20k | USDJPY | SHADOW | 1 | 1 | 0 | 0 | 1000 | 20000000 | 995 | 995 | 995 | 118.896 |
| 3 | 20k | EURUSD | ACTUAL | 0 | 0 | 0 | 0 | 0 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | 0 |
| 3 | 20k | EURUSD | SHADOW | 1 | 1 | 0 | 0 | 1000 | 20000000 | 995 | 995 | 995 | 119.728 |
| 3 | 20k | EURJPY | ACTUAL | 0 | 0 | 0 | 0 | 0 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | 0 |
| 3 | 20k | EURJPY | SHADOW | 1 | 1 | 0 | 0 | 1000 | 20000000 | 995 | 995 | 995 | 119.916 |
| 3 | 500k | USDJPY | ACTUAL | 35 | 34 | 0 | 1 | 1846 | 923000000 | 55 | 58 | 59 | 5641.263 |
| 3 | 500k | USDJPY | SHADOW | 1 | 1 | 0 | 0 | 40 | 20000000 | 15 | 15 | 15 | 128.126 |
| 3 | 500k | EURUSD | ACTUAL | 0 | 0 | 0 | 0 | 0 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | 0 |
| 3 | 500k | EURUSD | SHADOW | 1 | 1 | 0 | 0 | 40 | 20000000 | 15 | 15 | 15 | 134.745 |
| 3 | 500k | EURJPY | ACTUAL | 0 | 0 | 0 | 0 | 0 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | 0 |
| 3 | 500k | EURJPY | SHADOW | 1 | 1 | 0 | 0 | 40 | 20000000 | 15 | 15 | 15 | 128.747 |
| 4 | 20k | USDJPY | ACTUAL | 19 | 17 | 2 | 0 | 26346 | 526920000 | 1499 | 1499 | 1499 | 3171.087 |
| 4 | 20k | USDJPY | SHADOW | 1 | 1 | 0 | 0 | 1000 | 20000000 | 995 | 995 | 995 | 122.322 |
| 4 | 20k | EURUSD | ACTUAL | 0 | 0 | 0 | 0 | 0 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | 0 |
| 4 | 20k | EURUSD | SHADOW | 1 | 1 | 0 | 0 | 1000 | 20000000 | 995 | 995 | 995 | 123.623 |
| 4 | 20k | EURJPY | ACTUAL | 0 | 0 | 0 | 0 | 0 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | 0 |
| 4 | 20k | EURJPY | SHADOW | 1 | 1 | 0 | 0 | 1000 | 20000000 | 995 | 995 | 995 | 121.956 |
| 4 | 20k | XAUUSD | ACTUAL | 63 | 60 | 2 | 1 | 22714 | 454280000 | 199 | 899 | 899 | 2861.383 |
| 4 | 20k | XAUUSD | SHADOW | 1 | 1 | 0 | 0 | 1000 | 20000000 | 995 | 995 | 995 | 123.566 |
| 4 | 500k | USDJPY | ACTUAL | 35 | 34 | 0 | 1 | 1844 | 922000000 | 55 | 59 | 59 | 5711.508 |
| 4 | 500k | USDJPY | SHADOW | 1 | 1 | 0 | 0 | 40 | 20000000 | 15 | 15 | 15 | 154.128 |
| 4 | 500k | EURUSD | ACTUAL | 0 | 0 | 0 | 0 | 0 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | 0 |
| 4 | 500k | EURUSD | SHADOW | 1 | 1 | 0 | 0 | 40 | 20000000 | 15 | 15 | 15 | 148.602 |
| 4 | 500k | EURJPY | ACTUAL | 0 | 0 | 0 | 0 | 0 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | 0 |
| 4 | 500k | EURJPY | SHADOW | 1 | 1 | 0 | 0 | 40 | 20000000 | 15 | 15 | 15 | 154.159 |
| 4 | 500k | XAUUSD | ACTUAL | 74 | 74 | 0 | 0 | 1280 | 640000000 | 7 | 35 | 35 | 3841.125 |
| 4 | 500k | XAUUSD | SHADOW | 1 | 1 | 0 | 0 | 42 | 20000000 | 15 | 15 | 15 | 143.803 |

各完了cycleのoperation count分布、wall elapsed分布、Symbol別callback/service-gap/first-service-wait分布もsummary.jsonに保存。callback占有合計は未完了を含むため、完了cycleだけのwall elapsed分布と直接差し引かない。

SHADOWのstarvationは今回の範囲で観測されなかった。全Symbolが20m演算で完了し、20kでは各1,000 callback、500kでは各40〜43 callback。operation shareは均等、callback数の差はdeadline内に進んだ演算数の差で数値結果は完全一致。first-service waitと最大service gapを消さず報告する。自然heavyについてEURUSD/EURJPYのfairnessは評価不能。

| N | 方式 | 負荷 | Symbol | callback | 演算 | first wait max ms | service gap p95 ms | service gap max ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 20k | NORMAL | USDJPY | 1000 | 20000000 | 267.707 | 0.475 | 260.697 |
| 2 | 20k | NORMAL | EURUSD | 1000 | 20000000 | 267.807 | 0.483 | 260.695 |
| 2 | 20k | CPU_CONTENTION | USDJPY | 1000 | 20000000 | 273.083 | 0.518 | 267.547 |
| 2 | 20k | CPU_CONTENTION | EURUSD | 1000 | 20000000 | 273.183 | 0.561 | 267.538 |
| 2 | 500k | NORMAL | USDJPY | 40 | 20000000 | 250.382 | 6.288 | 248.051 |
| 2 | 500k | NORMAL | EURUSD | 40 | 20000000 | 252.928 | 5.191 | 248.045 |
| 2 | 500k | CPU_CONTENTION | USDJPY | 40 | 20000000 | 314.883 | 8.97 | 350.539 |
| 2 | 500k | CPU_CONTENTION | EURUSD | 40 | 20000000 | 317.456 | 7.973 | 348.703 |
| 3 | 20k | NORMAL | USDJPY | 1000 | 20000000 | 250.867 | 0.732 | 280.748 |
| 3 | 20k | NORMAL | EURUSD | 1000 | 20000000 | 250.97 | 0.813 | 280.75 |
| 3 | 20k | NORMAL | EURJPY | 1000 | 20000000 | 251.072 | 0.729 | 280.753 |
| 3 | 20k | CPU_CONTENTION | USDJPY | 1000 | 20000000 | 306.355 | 2.439 | 348.914 |
| 3 | 20k | CPU_CONTENTION | EURUSD | 1000 | 20000000 | 306.459 | 2.438 | 348.913 |
| 3 | 20k | CPU_CONTENTION | EURJPY | 1000 | 20000000 | 306.559 | 2.547 | 348.917 |
| 3 | 500k | NORMAL | USDJPY | 40 | 20000000 | 262.151 | 34.541 | 288.63 |
| 3 | 500k | NORMAL | EURUSD | 40 | 20000000 | 264.773 | 34.895 | 288.574 |
| 3 | 500k | NORMAL | EURJPY | 40 | 20000000 | 267.373 | 34.658 | 288.647 |
| 3 | 500k | CPU_CONTENTION | USDJPY | 40 | 20000000 | 347.531 | 43.528 | 341.211 |
| 3 | 500k | CPU_CONTENTION | EURUSD | 40 | 20000000 | 351.585 | 42.889 | 342.693 |
| 3 | 500k | CPU_CONTENTION | EURJPY | 41 | 20000000 | 359.842 | 28.403 | 342.77 |
| 4 | 20k | NORMAL | USDJPY | 1000 | 20000000 | 283.496 | 1.009 | 343.383 |
| 4 | 20k | NORMAL | EURUSD | 1000 | 20000000 | 283.596 | 1.112 | 343.469 |
| 4 | 20k | NORMAL | EURJPY | 1000 | 20000000 | 283.695 | 1.114 | 343.578 |
| 4 | 20k | NORMAL | XAUUSD | 1000 | 20000000 | 283.788 | 1.006 | 343.659 |
| 4 | 20k | CPU_CONTENTION | USDJPY | 1000 | 20000000 | 280.336 | 2.646 | 336.748 |
| 4 | 20k | CPU_CONTENTION | EURUSD | 1000 | 20000000 | 280.435 | 2.741 | 336.746 |
| 4 | 20k | CPU_CONTENTION | EURJPY | 1000 | 20000000 | 280.532 | 2.736 | 336.747 |
| 4 | 20k | CPU_CONTENTION | XAUUSD | 1000 | 20000000 | 280.63 | 2.788 | 336.746 |
| 4 | 500k | NORMAL | USDJPY | 40 | 20000000 | 271.674 | 249.018 | 274.454 |
| 4 | 500k | NORMAL | EURUSD | 40 | 20000000 | 276.391 | 248.801 | 278.312 |
| 4 | 500k | NORMAL | EURJPY | 40 | 20000000 | 280.386 | 248.765 | 281.751 |
| 4 | 500k | NORMAL | XAUUSD | 42 | 20000000 | 283.803 | 247.5 | 285.63 |
| 4 | 500k | CPU_CONTENTION | USDJPY | 40 | 20000000 | 292.35 | 302.496 | 317.933 |
| 4 | 500k | CPU_CONTENTION | EURUSD | 40 | 20000000 | 294.9 | 302.215 | 317.84 |
| 4 | 500k | CPU_CONTENTION | EURJPY | 43 | 20000000 | 297.475 | 288.618 | 319.805 |
| 4 | 500k | CPU_CONTENTION | XAUUSD | 40 | 20000000 | 300.077 | 303.4 | 319.746 |

chart input/processed tickは全12件584,990で一致。OnTimer回数も全件431,998で一致。Bar処理の全Symbol合計はN2=14,385、N3=21,583、N4=28,483で負荷／方式間一致。このBar合計をchartだけのBar数と混同しない。foreign SymbolはTimerのquote sample/advanceの観測であり、true input tick数・processed tick parity・全tickの重複/欠落はUNKNOWN。quote timestamp regressionは全Symbol0。queue depth／event arrival-to-handler delay／timer enqueue/drop数はUNKNOWN。

イベントは直列処理で、処理中・待機中の同種NewTick/Timerはqueueへ追加されない公式仕様。そのため今回のTester tick parityだけでLive queue待ち・event lossを否定しない。[OnTick公式仕様](https://www.mql5.com/en/docs/event_handlers/ontick)、[OnTimer公式仕様](https://www.mql5.com/en/docs/event_handlers/ontimer)。

OnTick・OnTimer全体・Position管理のwall-clock処理時間（ms）は以下。Position管理はSymbol横断・全呼出しの集計で、SL/TP、BE/trailing、close handling各内部操作の遅延・Symbol別queue待ちはUNKNOWN。現診断はPosition管理の個別spike時刻を持たず、MCと外れ値が同時刻だったかの直接裏付けもUNKNOWN。MC callbackだけの最大値とOnTimer全体最大値を混同しない。全12件でtiming measured_count=countを確認し、欠損0。

| N | 方式 | 負荷 | 処理 | median ms | p95 ms | p99 ms | max ms |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 20k | NORMAL | OnTick | 0.005 | 0.015 | 0.02 | 5.477 |
| 2 | 20k | NORMAL | OnTimer | 0.164 | 0.495 | 4.171 | 269.761 |
| 2 | 20k | NORMAL | ManagePositions | 0 | 0.001 | 0.002 | 0.235 |
| 2 | 20k | CPU_CONTENTION | OnTick | 0.005 | 0.01 | 0.016 | 9.146 |
| 2 | 20k | CPU_CONTENTION | OnTimer | 0.145 | 0.635 | 3.518 | 273.758 |
| 2 | 20k | CPU_CONTENTION | ManagePositions | 0 | 0.001 | 0.002 | 2.376 |
| 2 | 500k | NORMAL | OnTick | 0.005 | 0.015 | 0.021 | 8.257 |
| 2 | 500k | NORMAL | OnTimer | 0.163 | 0.554 | 4.344 | 255.937 |
| 2 | 500k | NORMAL | ManagePositions | 0 | 0.001 | 0.002 | 0.406 |
| 2 | 500k | CPU_CONTENTION | OnTick | 0.005 | 0.01 | 0.017 | 8.204 |
| 2 | 500k | CPU_CONTENTION | OnTimer | 0.144 | 1.134 | 3.663 | 350.954 |
| 2 | 500k | CPU_CONTENTION | ManagePositions | 0 | 0.001 | 0.002 | 8.161 |
| 3 | 20k | NORMAL | OnTick | 0.008 | 0.021 | 0.032 | 5.955 |
| 3 | 20k | NORMAL | OnTimer | 0.271 | 0.902 | 5.189 | 280.777 |
| 3 | 20k | NORMAL | ManagePositions | 0 | 0.002 | 0.003 | 0.194 |
| 3 | 20k | CPU_CONTENTION | OnTick | 0.007 | 0.017 | 0.024 | 9.736 |
| 3 | 20k | CPU_CONTENTION | OnTimer | 0.229 | 1.405 | 4.433 | 349.021 |
| 3 | 20k | CPU_CONTENTION | ManagePositions | 0 | 0.001 | 0.002 | 2.385 |
| 3 | 500k | NORMAL | OnTick | 0.007 | 0.021 | 0.031 | 6.754 |
| 3 | 500k | NORMAL | OnTimer | 0.252 | 1.114 | 5.232 | 291.119 |
| 3 | 500k | NORMAL | ManagePositions | 0 | 0.002 | 0.003 | 0.356 |
| 3 | 500k | CPU_CONTENTION | OnTick | 0.007 | 0.017 | 0.023 | 34.18 |
| 3 | 500k | CPU_CONTENTION | OnTimer | 0.223 | 1.463 | 4.707 | 363.961 |
| 3 | 500k | CPU_CONTENTION | ManagePositions | 0 | 0.001 | 0.002 | 3.058 |
| 4 | 20k | NORMAL | OnTick | 0.012 | 0.029 | 0.042 | 22.102 |
| 4 | 20k | NORMAL | OnTimer | 0.44 | 1.635 | 6.202 | 343.866 |
| 4 | 20k | NORMAL | ManagePositions | 0 | 0.002 | 0.003 | 0.321 |
| 4 | 20k | CPU_CONTENTION | OnTick | 0.009 | 0.022 | 0.031 | 34.119 |
| 4 | 20k | CPU_CONTENTION | OnTimer | 0.351 | 2.707 | 5.631 | 336.851 |
| 4 | 20k | CPU_CONTENTION | ManagePositions | 0 | 0.001 | 0.002 | 2.067 |
| 4 | 500k | NORMAL | OnTick | 0.013 | 0.03 | 0.042 | 8.849 |
| 4 | 500k | NORMAL | OnTimer | 0.416 | 2.677 | 6.098 | 290.178 |
| 4 | 500k | NORMAL | ManagePositions | 0 | 0.002 | 0.003 | 0.263 |
| 4 | 500k | CPU_CONTENTION | OnTick | 0.01 | 0.022 | 0.032 | 15.331 |
| 4 | 500k | CPU_CONTENTION | OnTimer | 0.347 | 2.912 | 5.955 | 323.162 |
| 4 | 500k | CPU_CONTENTION | ManagePositions | 0 | 0.001 | 0.002 | 3.304 |

同期ENTRY_SEND区間（要求開始→CTrade戻りまで）は観測可能。受理retcodeを確認した。candidate first観測→requestの市場秒差も保存したが、これはposition/MC待ちを含みenqueue latencyではない。Live broker latencyはUNKNOWN。Symbol別order区間分布はsummary.json。

| N | 方式 | 負荷 | 要求/受理/拒否 | order median ms | p95 ms | p99 ms | max ms | candidate→request max市場秒 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 20k | NORMAL | 47/47/0 | 0.055 | 0.135 | 0.23 | 0.257 | 0 |
| 2 | 20k | CPU_CONTENTION | 47/47/0 | 0.049 | 0.116 | 0.247 | 0.254 | 0 |
| 2 | 500k | NORMAL | 48/48/0 | 0.058 | 0.197 | 0.336 | 0.414 | 0 |
| 2 | 500k | CPU_CONTENTION | 48/48/0 | 0.049 | 0.1 | 0.159 | 0.2 | 0 |
| 3 | 20k | NORMAL | 77/77/0 | 0.06 | 0.111 | 0.186 | 0.226 | 0 |
| 3 | 20k | CPU_CONTENTION | 77/77/0 | 0.047 | 0.099 | 0.132 | 0.133 | 0 |
| 3 | 500k | NORMAL | 78/78/0 | 0.059 | 0.094 | 0.155 | 0.218 | 0 |
| 3 | 500k | CPU_CONTENTION | 78/78/0 | 0.05 | 0.084 | 0.275 | 0.637 | 0 |
| 4 | 20k | NORMAL | 118/117/1 | 0.054 | 0.091 | 0.16 | 0.239 | 49 |
| 4 | 20k | CPU_CONTENTION | 118/117/1 | 0.048 | 0.08 | 0.203 | 0.238 | 49 |
| 4 | 500k | NORMAL | 120/119/1 | 0.054 | 0.087 | 0.163 | 0.186 | 49 |
| 4 | 500k | CPU_CONTENTION | 120/119/1 | 0.046 | 0.077 | 0.163 | 0.605 | 49 |

取引系列差は両負荷で同じID・同じ理由となった。利益・勝率では候補を選んでいない。全Symbolの判断経路そのものが同値という主張ではない。

- USDJPY `551454E903239248` / `E2727DFD667685C8`：CurrentはScore/SL/Spread/Positionを通過した時点でMC active・not-ready、そのまま有効性終了。500kはMC ready/permittedで受理。MC_STATE_CHANGE。後者は先行取引でhistory/inputが変化しており、同input数値比較と別問題。
- USDJPY `0991CC99A1A62FFC`：Current受理、500kでは前段Opportunity自体が消える。before-Safety observerのRECEIPT guardが先行受理 `E2727DFD667685C8` をclaimantとして記録し、position_kind=1。observer記録（actual_seen=0）と製品RefreshCandidate/EntryPreflight/IsPatternAlreadyUsedのコードパスを合わせたEXPECTED_SEQUENCE_CHANGE。実Entryのguard実行ログとは扱わない。
- XAUUSD `9C848C02E3208A63` / `7BCF7599BA8B5D5A`：CurrentはPositionなしでMC待ちのまま有効性終了、500kはMC ready後受理。後者は候補から4市場秒後にready/受理。MC_STATE_CHANGE。
- XAUUSD `50433E0D3809F9E2`：Current受理、500kでは同OpportunityのELIGIBLE記録でposition_kind=1、MCはready/permitted。既存Positionによる拒否。POSITION_STATE_CHANGE。

追加2件−消失1件でUSDJPY純増1。4 SymbolではXAU追加2件−既存Positionで消失1件、さらに純増1。詳細時刻・input/state/history versionとguardはobservations.json。説明不能な系列差は見つからなかったが、診断外のLive経路は未証明。

500kのMC待ち有効性終了はN2/N3/N4・各負荷で1件、同一ID `B23D296093DA0BE1`。独立6Opportunityとは数えない。上流候補の観測幅59秒、Position解消後の待機観測幅8秒。寿命分布は同一週の繰返しなので、median/p10/p25/minはいずれも8秒（上流では59秒）。救済のためのchunk変更は行っていない。CurrentのN4有効性終了5件には、bar終了だけでなくXAUのNO_LONGER_ELIGIBLEも含む。
force dedupは無変更。forceの同期request call壁時計コストと、同input/state/fresh heavy repeatに属する非同期callback占有合計を分けた。後者は完了前cancelされた分も含む実観測の合計で、純CPU時間ではない。bootstrap再実行の増加は残っている別issue候補で、今回修正していない。

| N | 方式 | 負荷 | force | heavy | 即時 | 同input/state/fresh heavy | 同期call ms | 重複heavy callback占有ms | 重複演算 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 20k | NORMAL | 96 | 9 | 87 | 4 | 0.199 | 689.047 | 94920000 |
| 2 | 20k | CPU_CONTENTION | 96 | 9 | 87 | 4 | 0.18 | 538.703 | 94920000 |
| 2 | 500k | NORMAL | 98 | 11 | 87 | 5 | 0.537 | 807.855 | 132000000 |
| 2 | 500k | CPU_CONTENTION | 98 | 11 | 87 | 5 | 0.395 | 890.517 | 132000000 |
| 3 | 20k | NORMAL | 157 | 9 | 148 | 4 | 0.547 | 690.791 | 94920000 |
| 3 | 20k | CPU_CONTENTION | 157 | 9 | 148 | 4 | 0.542 | 526.71 | 94920000 |
| 3 | 500k | NORMAL | 159 | 11 | 148 | 5 | 0.282 | 854.902 | 132000000 |
| 3 | 500k | CPU_CONTENTION | 159 | 11 | 148 | 5 | 0.26 | 822.25 | 132000000 |
| 4 | 20k | NORMAL | 238 | 30 | 208 | 14 | 0.553 | 1063.431 | 152260000 |
| 4 | 20k | CPU_CONTENTION | 238 | 30 | 208 | 14 | 0.461 | 843.85 | 152260000 |
| 4 | 500k | NORMAL | 242 | 34 | 208 | 16 | 0.629 | 1480.721 | 222000000 |
| 4 | 500k | CPU_CONTENTION | 242 | 34 | 208 | 16 | 0.583 | 1349.2 | 222000000 |

数値同値性はsource-derived Current/500k replay 1,316比較、不一致0、許容差なし。うち実完了ACTUALとの照合1,148、実完了SHADOWとの照合72。比較行はcycleの独立数ではなくmode別の比較数。さらにnative SHADOWのCurrent/500k対応18組はRNG・input digest・sample selection/sequence・Risk bits・判定・candidate・operation countが完全一致。DD95はcandidate別bit signatureで照合。未完了ACTUALのreplay一致を実完了結果との比較に数えていない。SELFTESTも実完了数に含めない。

検証状態は次のとおり。同一HEADでもdirty診断差分を含まない既存CI成功を今回のfull PASSへ流用していない。

| 検証 | 状態 | 証拠/制約 |
| --- | --- | --- |
| MetaEditor 6230 | PASS | 製品EA/Worker、Tester20k/500k、4Symbol容量版とも0 errors / 0 warnings、fresh EX5をTesterでload |
| MetaEditor process exit | 1 | compile log0/0・fresh EX5と区別して記録 |
| 診断回帰 | PASS | 27 tests |
| Python syntax/static | PASS | 13 files（RAM compileのみ） |
| MC numerical | PASS | 1316比較0 mismatch、許容差なし |
| verify_v244.py | BLOCKED | Code Integrity cc1plus.exe: Event ID3077 / VerifiedAndReputableDesktop、同binary hash履歴preflight、launch未実施 |
| verify_json_regression.py | BLOCKED | 同上 |
| verify_stats.py | PASS | fresh gate_result.json |
| audit_source.py | PASS | fresh gate_result.json |
| verify_lock_scope.py | PASS | fresh gate_result.json |
| full 5-gate | INCOMPLETE | BLOCKED/BLOCKED/PASS/PASS/PASS |
| C++ MC deterministic | BLOCKED / NOT RUN | 診断worktree上の実行なし |
| 同一dirty診断diffのauthoritative CI | NOT RUN | commit/push禁止を維持 |
| Runtime error / warnings | PASS | 全12条件0 / 0、OnDeinit理由1 |
| canonical product scope | PASS | src13ファイルのHEAD bytes/hash不変、観測origin/mainとの製品diff0 |
| original set / MC math / Risk / Safety | PASS | 元High set hash不変、製品変更なし |
| privacy scan | PASS | 既知secret/口座識別子のUTF8/UTF16照合、770 files / matches0。全文PC・git履歴走査ではない |
| Forward / Live | NOT RUN | Live接続・実口座注文なし |
| queue / per-Symbol Position delay / broker live latency | UNKNOWN | 直接測定なし |

無効試行は保存した。N3 Current CPUとN4 Current CPUの起動時affinity driftはBLOCKEDとして除外し、別fresh出力名の同条件1回retryがPASS。N4の逸脱はTester agent起動前にowned terminal affinityが1→255となった直接記録があり、原因主体はUNKNOWN。repinしてPASSにしていない。N4旧診断のManagePositions3241875回に対する3m記録上限の欠損241875はFAILとして除外。生成されたmulti-only診断容量を12mへ増やし、4条件とも再compile・再実行した。元3m template/判定は無変更、2/3Symbol旧8結果はmeasured_count=countで欠損0を確認して再利用。群間で異なる診断binaryを同一binary比較と扱わない。

標準MT5原文journal/HTMLはrepositoryへコピーせず、fresh segmentをRAM内で読んでallowlisted非機密CSVと集計だけを保存した。MT5自身の既存原文ログ全体が無機密という主張はしない。秘密値を表示・診断artifactへ記録・commitしていない。既存MT5/Windowsセキュリティ設定、製品src/元set/MC数式/RNG/Risk/Safety/注文条件は変更していない。変更は未commitのTester専用生成器・runner・解析・回帰テスト・検証artifactのみ。

privacy再監査では保存artifactに加えて所有するstaged source/set/config/EX5/native HTMLをRAM内で走査した。現存するnative原ログ1本の今回offset以降も既知値一致0。ただし開始時offset一覧にあった原ログ2本は現在不在で、raw-log全体のcoverageはUNKNOWN。これらを削除・変更していない。各実行時のfresh journal判定とSHA付きCSVの保存証拠は維持するが、失われた原文の後日再確認は成功扱いしない。

READY条件を満たさない理由は、full5-gate未完走、自然な3/4Symbol同時heavy未再現、event到着→handler待ち・Symbol別Position管理spikeの直接証拠不足。OnTimer全体の最大255.937〜363.961msを無視して安全と断定しない。数値mismatchや観測可能なTick減少によるREJECT根拠はないが、未測定項目をPASSにせずNEEDS_MORE_TESTINGを維持する。

採用前のForward計画は、安全なTester/Demo隔離環境でSymbol別Position管理・BE/trailing/close・order request/accept・同期したevent到着referenceを測定し、real-time負荷でCurrent/500kを比較すること。低速実機、同時natural heavy、event coalescing、order処理外れ値、Risk/Safetyの状態遷移とqueue待ちを確認する。今回は計画のみでForwardを開始していない。

**次に1つだけ行う作業:** Windows securityを変更せず、同じ診断差分を対象にしたauthoritative CI/full5-gate証拠を成立させる手順を確立する。現時点のcommit/push禁止は維持する。

再現証拠: matrix/manifest_final.json、environment.json、native/*/attempt.json/result.json（各CSV SHA）、summary.json、observations.json、compile_results.json、compile_cap4_results.json、gate_result.json、finish_validation.json。集計scriptはsummarize.py / analyze_evidence.py。異常・UNKNOWNは原CSVへ戻って確認する。
