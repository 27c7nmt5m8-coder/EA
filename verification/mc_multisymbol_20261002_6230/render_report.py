"""Render a factual Japanese report from hash-verified aggregates."""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parents[1]))
from tools.mc500k_batch import PrivacyGuard


def fmt(value):
    return 'UNKNOWN' if value is None else f'{value:.3f}'.rstrip('0').rstrip('.')


def table(lines, headers, rows):
    lines += ['', '| '+' | '.join(headers)+' |', '| '+' | '.join('---' for _ in headers)+' |']
    lines += ['| '+' | '.join(str(v) for v in row)+' |' for row in rows]
    lines += ['']


def main():
    s=json.loads((ROOT/'summary.json').read_text(encoding='utf-8'))
    observations=json.loads((ROOT/'observations.json').read_text(encoding='utf-8'))
    finish=json.loads((ROOT/'finish_validation.json').read_text(encoding='utf-8'))
    gate=json.loads((ROOT/'gate_result.json').read_text(encoding='utf-8'))
    if s['completed']!=12 or any(c['status']!='PASS' for c in s['cases']):
        raise ValueError('incomplete native matrix')
    lines=[
        '判定は **NEEDS_MORE_TESTING**。固定12条件をMT5 build 6230で完走した。通常負荷／CPU競合の全6組でTick・Bar処理数、Opportunity単位Funnel、Tradesが一致し、Runtime error／warningは全12件0。500kを製品採用していない。commit・push・PR・merge・Live取引は行っていない。',
        '',
        '更新後の旧PID 22744は開始時刻・実行imageを含めた読み取り専用のプロセス照合で同一プロセス不在を確認した。所有外プロセスを終了・kill・再起動せず、GUI操作も行っていない。旧6182 pilotは別記録として保存し、6230集計から除外した。terminal/metaeditor/metatesterのversion 5.0.0.6230とSHA-256を固定し、実行前後にsource/set/EX5/engine hashesを照合した。最後の読み取り確認でもMT5/Tester/liveupdateプロセスは存在しなかった。残り条件0、再開作業にユーザー操作は不要だった。監視自動化は停止状態を維持する。',
        '',
        '条件は2 Symbol=USDJPY/EURUSD、3 Symbol=さらにEURJPY、4 Symbol=さらにXAUUSD。各群でCurrent20k／fixed500k × NORMAL／CPU_CONTENTION。USDJPYチャートM1、2026-09-14〜09-19、real ticks、USD100,000、1:1000、AUTO、最適化・Forwardなし、既存High入力を固定した。元setは無変更。TesterコピーのScanMode/CustomSymbolsだけで銘柄群を指定した。XAUUSDもFX High入力2.60×0.40のため、XAU専用preset検証や性能・利益評価には使わない。',
        '',
        'CPU_CONTENTIONは所有するterminal・verified Tester descendant・算術busy-loop workerを同一CPU affinity mask 1に固定した実CPU競合。sleep負荷ではない。NORMALとの差は単一core制限と競合workerの組合せであり、CPU使用率百分比は未測定。低速物理PCの代用としてPASS扱いしない。',
        '',
        '同時heavyは同じEA/Testerプロセス・同じイベントループに独立した2/3/4 SHADOW contextを同時activeにする再現負荷。各contextは同じ30標本の合成入力、同じRNG・bootstrap・閾値で20,000,000演算を実行し、出力は製品判断・注文・履歴・Riskへ渡さない。並列実行ではない。自然な製品MC（ACTUAL）と合成負荷（SHADOW）は別集計。4 SymbolではUSDJPY/XAUUSDの自然heavy active区間が、完了snapshotだけの下限集計でCurrent18組、500k4組重なった（各負荷で再現）。EURUSD/EURJPYは自然heavyを開始していないため、自然な3/4 Symbol同時heavyは未再現。自然MCとSHADOWの重複は全件UNKNOWN。',
        '',
        '以下の集計はNORMALのOpportunity単位。CPU_CONTENTIONのFunnel／Tradesも全件同値。同じ週の入れ子銘柄群を独立した市場サンプルとして合算しない。']
    normal=[c for c in s['cases'] if c['load']=='NORMAL']
    rows=[]
    for c in normal:
        vals=list(c['symbols'].values())
        total=lambda key:sum(v['funnel'][key] for v in vals)
        rows.append([c['count'],'20k' if c['mode']==0 else '500k',total('signals'),total('score_pass'),total('valid_stop'),total('spread_pass'),
                     total('before_position_mc'),total('position_pass'),total('mc_ready'),total('mc_permitted'),
                     total('risk_pass'),total('order_request'),total('accepted'),total('rejected'),c['trades'],
                     sum(v['mc_lifecycle']['waiting_opportunities'] for v in vals),sum(v['mc_lifecycle']['expired_before_completion'] for v in vals)])
    table(lines,['N','方式','Signal','Score','SL','Spread','Position前','Position後','MC ready','MC許可','Risk pass','要求','受理','拒否','Trades','MC待ち','有効性終了'],rows)
    lines += ['Score reject=Signal−Score pass、Spread reject=spread_evaluated−spread_pass、Position reject=Position前−Position後。Risk failは全ケース0。EURJPYのcompleted-decision不許可1件はMC計算中とは分ける。4 Symbolの注文拒否1件はXAUUSD retcode10018 MARKET_CLOSEDで両方式・両負荷共通。CTrade bool=trueだけで受理に数えず、retcode10008/10009/10010とのANDで判定した。その他の説明不能な負荷間Funnel差0。詳細Symbol別Funnelはsummary.jsonに全件保存。']
    rows=[]
    for c in normal:
        for symbol,v in c['symbols'].items():
            f=v['funnel']
            rows.append([c['count'],'20k' if c['mode']==0 else '500k',symbol,f['signals'],f['score_pass'],f['valid_stop'],f['spread_evaluated'],f['spread_pass'],
                         f['before_position_mc'],f['position_pass'],f['mc_ready'],f['mc_permitted'],f['other_safety_pass'],f['risk_pass'],f['order_request'],f['accepted']])
    table(lines,['N','方式','Symbol','Signal','Score','SL','Spread評価','Spread pass','Position前','Position後','MC ready','MC許可','他Safety','Risk','注文','受理'],rows)
    lines += ['MC callbackの壁時計占有時間（ms）。OSのdescheduling待ちも含み、CPU実行時間ではない。ACTUALには完了・未完了cycle双方のcallbackを含む。中央値・p90・p95・p99・最大値を取得し、固定許容閾値を新設してPASS判定していない。']
    for kind in ('ACTUAL','SHADOW'):
        lines += [kind+'：']
        table(lines,['N','方式','負荷','callback数','median','p90','p95','p99','max','占有合計ms'],
            [[c['count'],'20k' if c['mode']==0 else '500k',c['load'],c['callbacks_ms'][kind]['n']]+
             [fmt(c['callbacks_ms'][kind][k]) for k in ('median','p90','p95','p99','maximum','total')] for c in s['cases']])
    lines += ['MC生命周期はsnapshotのheavy start/completeと、明示されたCANCEL/RUN_ENDを分けた。未完了だけではcancelと数えない。以下はNORMAL。CPUでもstart/complete/cancel/censored件数、TimeCurrent差の中央値は一致した。TimeCurrent差は最後のquoteに基づく市場時刻差であり、Timerの正確な経過時計やwall-clockではない。SHADOWでは500k40〜43 callbackでもTimeCurrent差15秒となる。callback ordinalの開始／終了はobservations.jsonに残し、15秒をTimer40秒の代用にしない。Timer実経過の別時計はUNKNOWN。']
    rows=[]
    for c in normal:
        for symbol,v in c['symbols'].items():
            for kind in ('ACTUAL','SHADOW'):
                m=v['mc'][kind]
                rows.append([c['count'],'20k' if c['mode']==0 else '500k',symbol,kind,m['started'],m['completed'],m['cancelled'],m['censored'],m['callbacks'],m['operations'],
                             fmt(m['market_s']['median']),fmt(m['market_s']['p95']),fmt(m['market_s']['maximum']),fmt(m['callback_elapsed_sum_ms'])])
    table(lines,['N','方式','Symbol','kind','開始','完了','cancel','打切り','callback','演算','市場median秒','p95秒','max秒','callback占有合計ms'],rows)
    lines += ['各完了cycleのoperation count分布、wall elapsed分布、Symbol別callback/service-gap/first-service-wait分布もsummary.jsonに保存。callback占有合計は未完了を含むため、完了cycleだけのwall elapsed分布と直接差し引かない。',
              '',
              'SHADOWのstarvationは今回の範囲で観測されなかった。全Symbolが20m演算で完了し、20kでは各1,000 callback、500kでは各40〜43 callback。operation shareは均等、callback数の差はdeadline内に進んだ演算数の差で数値結果は完全一致。first-service waitと最大service gapを消さず報告する。自然heavyについてEURUSD/EURJPYのfairnessは評価不能。']
    table(lines,['N','方式','負荷','Symbol','callback','演算','first wait max ms','service gap p95 ms','service gap max ms'],
        [[c['count'],'20k' if c['mode']==0 else '500k',c['load'],symbol,v['SHADOW']['callbacks'],v['SHADOW']['operations'],
          fmt(v['SHADOW']['first_service_wait_ms']['maximum']),fmt(v['SHADOW']['service_gap_ms']['p95']),fmt(v['SHADOW']['service_gap_ms']['maximum'])]
         for c in s['cases'] for symbol,v in c['service_by_symbol'].items()])
    lines += ['chart input/processed tickは全12件584,990で一致。OnTimer回数も全件431,998で一致。Bar処理の全Symbol合計はN2=14,385、N3=21,583、N4=28,483で負荷／方式間一致。このBar合計をchartだけのBar数と混同しない。foreign SymbolはTimerのquote sample/advanceの観測であり、true input tick数・processed tick parity・全tickの重複/欠落はUNKNOWN。quote timestamp regressionは全Symbol0。queue depth／event arrival-to-handler delay／timer enqueue/drop数はUNKNOWN。',
              '',
              'イベントは直列処理で、処理中・待機中の同種NewTick/Timerはqueueへ追加されない公式仕様。そのため今回のTester tick parityだけでLive queue待ち・event lossを否定しない。[OnTick公式仕様](https://www.mql5.com/en/docs/event_handlers/ontick)、[OnTimer公式仕様](https://www.mql5.com/en/docs/event_handlers/ontimer)。',
              '',
              'OnTick・OnTimer全体・Position管理のwall-clock処理時間（ms）は以下。Position管理はSymbol横断・全呼出しの集計で、SL/TP、BE/trailing、close handling各内部操作の遅延・Symbol別queue待ちはUNKNOWN。現診断はPosition管理の個別spike時刻を持たず、MCと外れ値が同時刻だったかの直接裏付けもUNKNOWN。MC callbackだけの最大値とOnTimer全体最大値を混同しない。全12件でtiming measured_count=countを確認し、欠損0。']
    rows=[]
    for c in s['cases']:
        for event in c['events']:
            rows.append([c['count'],'20k' if c['mode']==0 else '500k',c['load'],event['event']]+[fmt(float(event[k])/1000) for k in ('median_us','p95_us','p99_us','max_us')])
        event=next(r for r in c['management'] if r['event']=='ManagePositions')
        rows.append([c['count'],'20k' if c['mode']==0 else '500k',c['load'],'ManagePositions']+[fmt(float(event[k])/1000) for k in ('median_us','p95_us','p99_us','max_us')])
    table(lines,['N','方式','負荷','処理','median ms','p95 ms','p99 ms','max ms'],rows)
    lines += ['同期ENTRY_SEND区間（要求開始→CTrade戻りまで）は観測可能。受理retcodeを確認した。candidate first観測→requestの市場秒差も保存したが、これはposition/MC待ちを含みenqueue latencyではない。Live broker latencyはUNKNOWN。Symbol別order区間分布はsummary.json。']
    table(lines,['N','方式','負荷','要求/受理/拒否','order median ms','p95 ms','p99 ms','max ms','candidate→request max市場秒'],
        [[o['count'],'20k' if o['mode']==0 else '500k',o['load'],f"{o['order_calls']}/{o['accepted']}/{o['rejected']}"]+
         [fmt(o['order_call_wall_ms'][k]) for k in ('median','p95','p99','maximum')]+[fmt(o['candidate_to_request_market_s']['maximum'])] for o in observations['observations']])
    lines += ['取引系列差は両負荷で同じID・同じ理由となった。利益・勝率では候補を選んでいない。全Symbolの判断経路そのものが同値という主張ではない。',
              '',
              '- USDJPY `551454E903239248` / `E2727DFD667685C8`：CurrentはScore/SL/Spread/Positionを通過した時点でMC active・not-ready、そのまま有効性終了。500kはMC ready/permittedで受理。MC_STATE_CHANGE。後者は先行取引でhistory/inputが変化しており、同input数値比較と別問題。',
              '- USDJPY `0991CC99A1A62FFC`：Current受理、500kでは前段Opportunity自体が消える。before-Safety observerのRECEIPT guardが先行受理 `E2727DFD667685C8` をclaimantとして記録し、position_kind=1。observer記録（actual_seen=0）と製品RefreshCandidate/EntryPreflight/IsPatternAlreadyUsedのコードパスを合わせたEXPECTED_SEQUENCE_CHANGE。実Entryのguard実行ログとは扱わない。',
              '- XAUUSD `9C848C02E3208A63` / `7BCF7599BA8B5D5A`：CurrentはPositionなしでMC待ちのまま有効性終了、500kはMC ready後受理。後者は候補から4市場秒後にready/受理。MC_STATE_CHANGE。',
              '- XAUUSD `50433E0D3809F9E2`：Current受理、500kでは同OpportunityのELIGIBLE記録でposition_kind=1、MCはready/permitted。既存Positionによる拒否。POSITION_STATE_CHANGE。',
              '',
              '追加2件−消失1件でUSDJPY純増1。4 SymbolではXAU追加2件−既存Positionで消失1件、さらに純増1。詳細時刻・input/state/history versionとguardはobservations.json。説明不能な系列差は見つからなかったが、診断外のLive経路は未証明。',
              '',
              '500kのMC待ち有効性終了はN2/N3/N4・各負荷で1件、同一ID `B23D296093DA0BE1`。独立6Opportunityとは数えない。上流候補の観測幅59秒、Position解消後の待機観測幅8秒。寿命分布は同一週の繰返しなので、median/p10/p25/minはいずれも8秒（上流では59秒）。救済のためのchunk変更は行っていない。CurrentのN4有効性終了5件には、bar終了だけでなくXAUのNO_LONGER_ELIGIBLEも含む。']
    rows=[]
    for c in s['cases']:
        vals=list(c['symbols'].values())
        total=lambda key:sum(v[key] for v in vals)
        rows.append([c['count'],'20k' if c['mode']==0 else '500k',c['load'],total('force_requests'),total('heavy_force'),total('immediate_force'),total('duplicate_heavy'),fmt(total('force_wall_ms')),fmt(total('duplicate_heavy_callback_elapsed_sum_ms')),total('duplicate_heavy_operations')])
    lines += ['force dedupは無変更。forceの同期request call壁時計コストと、同input/state/fresh heavy repeatに属する非同期callback占有合計を分けた。後者は完了前cancelされた分も含む実観測の合計で、純CPU時間ではない。bootstrap再実行の増加は残っている別issue候補で、今回修正していない。']
    table(lines,['N','方式','負荷','force','heavy','即時','同input/state/fresh heavy','同期call ms','重複heavy callback占有ms','重複演算'],rows)
    lines += [f"数値同値性はsource-derived Current/500k replay {observations['numerical_replay_comparisons']:,}比較、不一致0、許容差なし。うち実完了ACTUALとの照合{observations['native_completed_result_comparisons_by_kind']['ACTUAL']:,}、実完了SHADOWとの照合{observations['native_completed_result_comparisons_by_kind']['SHADOW']}。比較行はcycleの独立数ではなくmode別の比較数。さらにnative SHADOWのCurrent/500k対応18組はRNG・input digest・sample selection/sequence・Risk bits・判定・candidate・operation countが完全一致。DD95はcandidate別bit signatureで照合。未完了ACTUALのreplay一致を実完了結果との比較に数えていない。SELFTESTも実完了数に含めない。",
              '',
              '検証状態は次のとおり。同一HEADでもdirty診断差分を含まない既存CI成功を今回のfull PASSへ流用していない。']
    table(lines,['検証','状態','証拠/制約'],[
        ['MetaEditor 6230','PASS','製品EA/Worker、Tester20k/500k、4Symbol容量版とも0 errors / 0 warnings、fresh EX5をTesterでload'],
        ['MetaEditor process exit','1','compile log0/0・fresh EX5と区別して記録'],
        ['診断回帰','PASS',str(finish['diagnostic_regression']['tests'])+' tests'],
        ['Python syntax/static','PASS',str(finish['static_syntax']['files'])+' files（RAM compileのみ）'],
        ['MC numerical','PASS','1316比較0 mismatch、許容差なし'],
        ['verify_v244.py','BLOCKED','Code Integrity cc1plus.exe: Event ID3077 / VerifiedAndReputableDesktop、同binary hash履歴preflight、launch未実施'],
        ['verify_json_regression.py','BLOCKED','同上'],
        ['verify_stats.py','PASS','fresh gate_result.json'],
        ['audit_source.py','PASS','fresh gate_result.json'],
        ['verify_lock_scope.py','PASS','fresh gate_result.json'],
        ['full 5-gate','INCOMPLETE','BLOCKED/BLOCKED/PASS/PASS/PASS'],
        ['C++ MC deterministic','BLOCKED / NOT RUN','診断worktree上の実行なし'],
        ['同一dirty診断diffのauthoritative CI','NOT RUN','commit/push禁止を維持'],
        ['Runtime error / warnings','PASS','全12条件0 / 0、OnDeinit理由1'],
        ['canonical product scope','PASS','src13ファイルのHEAD bytes/hash不変、観測origin/mainとの製品diff0'],
        ['original set / MC math / Risk / Safety','PASS','元High set hash不変、製品変更なし'],
        ['privacy scan','PASS',f"既知secret/口座識別子のUTF8/UTF16照合、{finish['privacy']['files_scanned']} files / matches0。全文PC・git履歴走査ではない"],
        ['Forward / Live','NOT RUN','Live接続・実口座注文なし'],
        ['queue / per-Symbol Position delay / broker live latency','UNKNOWN','直接測定なし']])
    lines += ['無効試行は保存した。N3 Current CPUとN4 Current CPUの起動時affinity driftはBLOCKEDとして除外し、別fresh出力名の同条件1回retryがPASS。N4の逸脱はTester agent起動前にowned terminal affinityが1→255となった直接記録があり、原因主体はUNKNOWN。repinしてPASSにしていない。N4旧診断のManagePositions3241875回に対する3m記録上限の欠損241875はFAILとして除外。生成されたmulti-only診断容量を12mへ増やし、4条件とも再compile・再実行した。元3m template/判定は無変更、2/3Symbol旧8結果はmeasured_count=countで欠損0を確認して再利用。群間で異なる診断binaryを同一binary比較と扱わない。',
              '',
              '標準MT5原文journal/HTMLはrepositoryへコピーせず、fresh segmentをRAM内で読んでallowlisted非機密CSVと集計だけを保存した。MT5自身の既存原文ログ全体が無機密という主張はしない。秘密値を表示・診断artifactへ記録・commitしていない。既存MT5/Windowsセキュリティ設定、製品src/元set/MC数式/RNG/Risk/Safety/注文条件は変更していない。変更は未commitのTester専用生成器・runner・解析・回帰テスト・検証artifactのみ。',
              '',
              f"privacy再監査では保存artifactに加えて所有するstaged source/set/config/EX5/native HTMLをRAM内で走査した。現存するnative原ログ{finish['privacy'].get('native_fresh_segments_inspected',0)}本の今回offset以降も既知値一致{finish['privacy'].get('native_known_value_matching_segments',0)}。ただし開始時offset一覧にあった原ログ{finish['privacy'].get('native_missing_offset_files',0)}本は現在不在で、raw-log全体のcoverageは{finish['privacy'].get('native_raw_log_coverage','UNKNOWN')}。これらを削除・変更していない。各実行時のfresh journal判定とSHA付きCSVの保存証拠は維持するが、失われた原文の後日再確認は成功扱いしない。",
              '',
              'READY条件を満たさない理由は、full5-gate未完走、自然な3/4Symbol同時heavy未再現、event到着→handler待ち・Symbol別Position管理spikeの直接証拠不足。OnTimer全体の最大255.937〜363.961msを無視して安全と断定しない。数値mismatchや観測可能なTick減少によるREJECT根拠はないが、未測定項目をPASSにせずNEEDS_MORE_TESTINGを維持する。',
              '',
              '採用前のForward計画は、安全なTester/Demo隔離環境でSymbol別Position管理・BE/trailing/close・order request/accept・同期したevent到着referenceを測定し、real-time負荷でCurrent/500kを比較すること。低速実機、同時natural heavy、event coalescing、order処理外れ値、Risk/Safetyの状態遷移とqueue待ちを確認する。今回は計画のみでForwardを開始していない。',
              '',
              '**次に1つだけ行う作業:** Windows securityを変更せず、同じ診断差分を対象にしたauthoritative CI/full5-gate証拠を成立させる手順を確立する。現時点のcommit/push禁止は維持する。',
              '',
              '再現証拠: matrix/manifest_final.json、environment.json、native/*/attempt.json/result.json（各CSV SHA）、summary.json、observations.json、compile_results.json、compile_cap4_results.json、gate_result.json、finish_validation.json。集計scriptはsummarize.py / analyze_evidence.py。異常・UNKNOWNは原CSVへ戻って確認する。'
    ]
    text='\n'.join(lines)+'\n'
    PrivacyGuard().check(text)
    (ROOT/'REPORT_JA.md').write_text(text,encoding='utf-8')
    print(json.dumps(dict(report='REPORT_JA.md',conditions=12,verdict='NEEDS_MORE_TESTING',bytes=len(text.encode('utf-8')))))


if __name__=='__main__':
    main()
