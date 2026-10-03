"""Hash-bound read-only analysis of the frozen affinity-observed Tester matrix.

Raw native journals/HTML are never exported. Event arrival/queue delay cannot
be established by process polling and are explicitly UNKNOWN.
"""
import argparse
import csv
import json
from pathlib import Path

from tools import mc500k_batch as batch
from tools import mc_multisymbol_runner as matrix
from tools.analyze_mc_multisymbol import describe_case
from tools.build_tester_timer_latency import analyze_timer_trace
from tools.build_tester_journal_io import analyze_io_trace
from tools.mc_isolated_contention import placement_signature, require_matching_placement, tooling_hashes, timer_population


def comparison_fields(case):
    return {key:case[key] for key in ('chart_processed_ticks','symbol_bar_process_total','trades')} | {
        'symbols':{symbol:({key:value[key] for key in ('funnel','outcomes',
                                                      'order_acceptance','quote_samples','quote_advances')} |
                           {'mc_lifecycle':{k:v for k,v in value['mc_lifecycle'].items()
                                            if k not in ('market_duration_s','wall_elapsed_ms','advance_execution_ms')}})
                   for symbol,value in case['symbols'].items()}}


def analyze(evidence):
    evidence=Path(evidence)
    manifest=json.loads((evidence/'matrix/manifest.json').read_text(encoding='utf-8'))
    cases=[]
    for frozen in manifest:
        folder=evidence/'native'/frozen['case']
        if not (folder/'result.json').exists():
            continue
        result=json.loads((folder/'result.json').read_text(encoding='utf-8'))
        observation=json.loads((folder/'observation.json').read_text(encoding='utf-8'))
        attempt=json.loads((folder/'attempt.json').read_text(encoding='utf-8'))
        matrix.verify_staged(frozen)
        matrix.validate_result_binding(result,frozen)
        if (not observation.get('comparison_eligible') or attempt.get('status')!='COLLECTABLE' or
            attempt.get('exit_code')!=0 or attempt.get('diagnostic_tool_sha256')!=tooling_hashes()):
            raise ValueError('fresh eligible observation required')
        signature=placement_signature(observation)
        if frozen['load']=='CPU_CONTENTION':
            ready=attempt.get('load_ready',[])
            if (len(ready)!=6 or any(r.get('operations',0)<=0 or r.get('cpu_seconds',0)<=0 for r in ready) or
                attempt.get('load_ready_wall_perf_ns',0)>=attempt.get('terminal_launch_wall_perf_ns',0)):
                raise ValueError('load before launch not established')
        described=describe_case(folder)
        prefix=result['scheduler']['prefix']
        def rows(suffix):
            name=prefix+suffix+'.csv'
            if matrix.sha256(folder/name)!=result['exports'][name]:
                raise ValueError('export checksum mismatch')
            with (folder/name).open(encoding='ascii',newline='') as f:
                return list(csv.DictReader(f))
        sections=rows('_timer_sections')
        population=timer_population(rows('_events'),rows('_timer_summary'))
        if json.loads((folder/'timer_population.json').read_text(encoding='utf-8'))!=population:
            raise ValueError('timer population proof changed')
        longest=max(sections,key=lambda r:int(r['total_us']))
        tid=longest['timer_id']
        worst={suffix:[r for r in rows(suffix) if r['timer_id']==tid]
               for suffix in ('_timer_sections','_journal_sections','_journal_io')}
        cpu={}
        with (folder/'process_samples.jsonl').open(encoding='utf-8') as f:
            for line in f:
                for row in json.loads(line)['processes']:
                    if isinstance(row.get('cpu_one_core_pct'),(int,float)):
                        cpu.setdefault(row['role'],[]).append(row['cpu_one_core_pct'])
        cases.append(dict(count=frozen['count'],mode=frozen['mode'],load=frozen['load'],
                          case=described,placement=signature,observer=observation,
                          timer_population=population,
                          timer_attribution=analyze_timer_trace(sections,rows('_timer_summary')),
                          journal_io_attribution=analyze_io_trace(rows('_journal_io'),rows('_journal_sections'),sections,rows('_timer_summary')),
                          worst_timer=worst,cpu_one_core_pct={role:batch.percentiles(v) for role,v in cpu.items()},
                          warnings=result['warnings'],replay_comparisons=int(result['scheduler']['comparisons']),
                          replay_actual_rows=result['actual_replay_rows'],
                          source_result_sha256=matrix.sha256(folder/'result.json'),
                          source_observation_sha256=matrix.sha256(folder/'observation.json'),
                          source_attempt_sha256=matrix.sha256(folder/'attempt.json'),
                          source_process_samples_sha256=matrix.sha256(folder/'process_samples.jsonl')))
    pairs=[]
    for count in (2,3,4):
        for mode in (0,2):
            selected=[c for c in cases if c['count']==count and c['mode']==mode]
            if len(selected)==2:
                require_matching_placement(selected[0]['placement'],selected[1]['placement'])
                pairs.append(dict(count=count,mode=mode,
                                  tick_bar_trade_funnel_equal=comparison_fields(selected[0]['case'])==comparison_fields(selected[1]['case'])))
    output=dict(status='COMPLETE' if len(cases)==12 and len(pairs)==6 else 'INCOMPLETE',
                manifest_sha256=matrix.sha256(evidence/'matrix/manifest.json'),cases=cases,
                load_pairs=pairs,completed=len(cases),remaining=12-len(cases),
                queue_wait='UNKNOWN',unsampled_affinity_transients='UNKNOWN',api_caller='UNATTRIBUTED',
                live_broker_latency='UNKNOWN',product_adoption=False)
    batch.PrivacyGuard().check(json.dumps(output))
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        result=analyze(args.evidence)
        batch.dump(args.output,result)
        print(json.dumps({k:result[k] for k in ('status','completed','remaining','load_pairs')}))
    except Exception as error:
        print(json.dumps(dict(status='BLOCKED',exception=type(error).__name__)))
        raise SystemExit(1) from None
