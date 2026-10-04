"""Hash-bound minimal/detailed startup comparison; wall-time causes stay bounded."""
import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from tools import mc500k_batch as batch
from tools import mc_multisymbol_runner as matrix
from tools.analyze_mc_multisymbol import describe_case, require_export
from tools.analyze_mc_affinity import comparison_fields
from tools.build_tester_startup_scan import analyze_spans, SafeDiagnosticParser
from tools.build_tester_timer_latency import analyze_timer_trace
from tools.build_tester_journal_io import analyze_io_trace
from tools.mc_isolated_contention import placement_signature, require_matching_placement, timer_population, tooling_hashes


def scan_subtree(rows,span_id):
    selected={span_id}
    # Validated span IDs are in creation order and each parent precedes its child.
    for r in sorted(rows,key=lambda r:r['span_id']):
        if r['parent_id'] in selected:selected.add(r['span_id'])
    return [r for r in rows if r['span_id'] in selected]


def validate_phase_roots(phases,roots):
    for phase,indices in (('STARTUP',range(1,5)),('WARMUP',range(5,101))):
        values=sorted(roots[i]['duration_us'] for i in indices)
        def quantile(p):
            at=(len(values)-1)*p;low=math.floor(at);high=math.ceil(at)
            return values[low]+(values[high]-values[low])*(at-low)
        expected=dict(count=len(values),total_us=sum(values),median_us=quantile(.5),p95_us=quantile(.95),p99_us=quantile(.99),max_us=max(values))
        # FileWrite serializes diagnostic doubles; this is not an MC tolerance.
        if any(not math.isclose(phases[phase][k],v,rel_tol=0,abs_tol=1e-6) for k,v in expected.items()):raise ValueError('phase/root statistics disagree')


def validate_observation_binding(case,result,attempt,observation):
    if (not observation.get('comparison_eligible') or observation.get('overhead_status')!='ACCEPTABLE'
        or result.get('status')!='PASS' or attempt.get('status')!='COLLECTABLE' or attempt.get('exit_code')!=0
        or attempt.get('diagnostic_tool_sha256')!=tooling_hashes()
        or attempt.get('profile_sha256')!=case['profile_sha256']
        or any(attempt.get(k)!=case[k] or result.get(k)!=case[k] for k in ('case','mode','load'))):
        raise ValueError('attempt/observer binding mismatch')


def inspect(base,case):
    base=Path(base);folder=base/'native'/case['case'];matrix.verify_staged(case)
    result=json.loads((folder/'result.json').read_text(encoding='utf-8'))
    attempt=json.loads((folder/'attempt.json').read_text(encoding='utf-8'))
    observation=json.loads((folder/'observation.json').read_text(encoding='utf-8'))
    matrix.validate_result_binding(result,case)
    validate_observation_binding(case,result,attempt,observation)
    described=describe_case(folder)
    sections=require_export(folder,result,'_timer_sections.csv')
    summaries=require_export(folder,result,'_timer_summary.csv')
    events=require_export(folder,result,'_events.csv')
    timer=analyze_timer_trace(sections,summaries)
    io=analyze_io_trace(require_export(folder,result,'_journal_io.csv'),require_export(folder,result,'_journal_sections.csv'),sections,summaries)
    frames={int(r['timer_id']):int(r['total_us']) for r in sections if r['stage']=='maintain'}
    out=dict(case=case['case'],variant=case['startup_variant'],mode=case['mode'],load=case['load'],
             native=described,placement=placement_signature(observation),warnings=result['warnings'],
             timer_population=timer_population(events,summaries),timer_attribution=timer,journal_io_attribution=io,
             retained_steady_max_us=max(v for k,v in frames.items() if k>100),
             source_result_sha256=matrix.sha256(folder/'result.json'),source_attempt_sha256=matrix.sha256(folder/'attempt.json'),
             source_observation_sha256=matrix.sha256(folder/'observation.json'),source_process_samples_sha256=matrix.sha256(folder/'process_samples.jsonl'),
             numerical_comparisons=int(result['scheduler']['comparisons']),numerical_mismatches=int(result['scheduler']['mismatch']))
    if case['startup_variant']=='detailed':
        def additional(suffix):
            source=batch.COMMON/(result['scheduler']['prefix']+suffix+'.csv')
            if not source.is_file() or source.stat().st_mtime<attempt['started']-1:raise ValueError('missing/stale startup export')
            raw=source.read_bytes();batch.PrivacyGuard().check(raw.decode('ascii'))
            target=folder/source.name
            if target.exists() and target.read_bytes()!=raw:raise ValueError('retained startup export changed')
            target.write_bytes(raw)
            with target.open(encoding='ascii',newline='') as f:rows=list(csv.DictReader(f))
            return rows,matrix.sha256(target)
        rows,trace_hash=additional('_startup_scan');population,pop_hash=additional('_startup_population')
        parsed=analyze_spans(rows)
        if parsed['timer_count']!=100 or {r['timer_id'] for r in parsed['roots']}!=set(range(101)):raise ValueError('missing first-100/init roots')
        root={r['timer_id']:r for r in parsed['roots']}
        if any(root[k]['duration_us']!=v for k,v in frames.items() if k<=100):raise ValueError('startup/Timer clocks disagree')
        expected={'phase','count','total_us','median_us','p95_us','p99_us','max_us'}
        if len(population)!=3 or {r['phase'] for r in population}!={'STARTUP','WARMUP','STEADY_STATE'} or any(set(r)!=expected for r in population):raise ValueError('unknown population schema')
        phase_stats={}
        for p in population:
            n=int(p['count']);total=int(p['total_us']);numbers={k:float(p[k]) for k in ('median_us','p95_us','p99_us','max_us')}
            if n<=0 or total<0 or any(not math.isfinite(v) or v<0 for v in numbers.values()) or not numbers['median_us']<=numbers['p95_us']<=numbers['p99_us']<=numbers['max_us'] or total<numbers['max_us']:raise ValueError('invalid population statistics')
            phase_stats[p['phase']]=dict(count=n,total_us=total,**numbers)
        overall=next(r for r in events if r['event']=='OnTimer')
        if sum(p['count'] for p in phase_stats.values())!=int(overall['count']) or sum(p['total_us'] for p in phase_stats.values())!=int(overall['total_us']) or max(p['max_us'] for p in phase_stats.values())!=float(overall['max_us']):raise ValueError('phase populations not conserved')
        if phase_stats['STARTUP']['count']!=4 or phase_stats['WARMUP']['count']!=96:raise ValueError('phase window mismatch')
        validate_phase_roots(phase_stats,root)
        if {r['symbol'] for r in parsed['spans'] if r['section']=='scan' and 1<=r['timer_id']<=4}!=set(case['symbols']):raise ValueError('first-four symbol coverage incomplete')
        maxima={};context_exclusive=defaultdict(int);children=defaultdict(list)
        for r in parsed['spans']:children[r['parent_id']].append(r)
        for r in parsed['spans']:
            context_exclusive[r['context']+':'+r['section']]+=r['duration_us']-sum(c['duration_us'] for c in children[r['span_id']])
        for symbol in case['symbols']:
            scan=next(r for r in parsed['spans'] if r['section']=='scan' and r['symbol']==symbol)
            subtree=scan_subtree(parsed['spans'],scan['span_id'])
            totals=defaultdict(int)
            scan_exclusive=defaultdict(int)
            for r in subtree:
                key=r['context']+':'+r['section'];totals[key]+=r['duration_us']
                scan_exclusive[key]+=r['duration_us']-sum(c['duration_us'] for c in children[r['span_id']])
            maxima[symbol]=dict(timer_id=scan['timer_id'],server_s=scan['server_s'],scan_us=scan['duration_us'],
                                timer_us=root[scan['timer_id']]['duration_us'],inclusive_section_us=dict(totals),exclusive_section_us=dict(scan_exclusive))
        handle_creates=[r for r in parsed['spans'] if r['section'].startswith('create_')]
        out.update(startup=dict(phase_population=phase_stats,first_symbol_scans=maxima,
                    first_access={s:next((dict(timer_id=r['timer_id'],symbol=r['symbol'],context=r['context'],duration_us=r['duration_us']) for r in parsed['spans'] if r['section']==s),None) for s in ('history','initial_risks','handle_access','series_time','copy_buffer','lines','observer','position')},
                    initialization_us=root[0]['duration_us'],spans=parsed['span_count'],
                    native_handle_create_calls=len(handle_creates),native_handle_create_us=sum(r['duration_us'] for r in handle_creates),
                    exclusive_context_us=dict(context_exclusive),trace_sha256=trace_hash,population_sha256=pop_hash,
                    queue_wait='UNKNOWN',os_scheduling='UNKNOWN',residual_interpretation='exclusive time includes instrumentation/bookkeeping and uninstrumented work; not pure CPU'))
    batch.PrivacyGuard().check(json.dumps(out))
    return out


def compare(minimal,detailed):
    cases=[]
    for base in (minimal,detailed):
        for c in json.loads((Path(base)/'matrix/manifest.json').read_text(encoding='utf-8')):cases.append(inspect(base,c))
    pairs=[]
    for mode in (0,2):
        a=next(c for c in cases if c['variant']=='minimal' and c['mode']==mode)
        b=next(c for c in cases if c['variant']=='detailed' and c['mode']==mode)
        require_matching_placement(a['placement'],b['placement'])
        equal=comparison_fields(a['native'])==comparison_fields(b['native'])
        pairs.append(dict(mode=mode,tick_bar_trade_funnel_equal=equal,diagnostic_intrusive='NOT_OBSERVED_IN_COUNTS' if equal else 'DIAGNOSTIC_INTRUSIVE',
                          minimal_timer=a['timer_population'],detailed_timer=b['timer_population'],timing_causality='unreplicated host wall-time comparison; not pure CPU overhead'))
    out=dict(cases=cases,pairs=pairs,root_cause_status='ON_TIMER_ROOT_CAUSE_PARTIAL',queue_wait='UNKNOWN',
             scheduler_status='NEEDS_MORE_TESTING',product_adoption=False,
             numerical_comparisons=sum(c['numerical_comparisons'] for c in cases),numerical_mismatches=sum(c['numerical_mismatches'] for c in cases))
    batch.PrivacyGuard().check(json.dumps(out));return out


if __name__=='__main__':
    p=SafeDiagnosticParser(description=__doc__);p.add_argument('minimal',type=Path);p.add_argument('detailed',type=Path);p.add_argument('--output',type=Path,required=True)
    try:
        a=p.parse_args()
        out=compare(a.minimal,a.detailed);batch.dump(a.output,out)
        print(json.dumps(dict(status=out['root_cause_status'],cases=len(out['cases']),pairs=[dict(mode=p['mode'],counts_equal=p['tick_bar_trade_funnel_equal']) for p in out['pairs']],comparisons=out['numerical_comparisons'],mismatches=out['numerical_mismatches'])))
    except Exception as e:print(json.dumps(dict(status='BLOCKED',exception=type(e).__name__)));raise SystemExit(1) from None
