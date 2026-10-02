"""Deterministic summaries of the allowlisted Tester bottleneck export.

An opportunity is symbol + M1 bar + canonical pattern identity + direction.
Stage flags mean ever passed within that opportunity, not tick/call counts.
Both first and maximum scores are reported; maximum determines never-passed
Score rejection. Histograms use half-open intervals and include values <60.
No thresholds, trading settings or Monte Carlo calculations are changed.
"""
import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path
import re

STAGES=('signals','score_pass','valid_stop','spread_evaluated','spread_pass',
        'before_position_mc','other_safety_pass','risk_reached','risk_pass',
        'risk_fail','order_request','accepted','rejected','position_pass',
        'mc_ready','mc_permitted')
POSITION=('same_symbol','same_direction','opposite_direction','netting','hedging',
          'single_position_policy','pending','unresolved','owned','foreign','other')
MC=('initialization','calculation_incomplete','history_state_unavailable',
    'sequence_unavailable','insufficient_samples_baseline_allowed',
    'baseline_risk_denied','minimum_win_rate_denied','completed_boundary_denied',
    'completed_permitted','other_not_ready','other_denied','bypass')


def has(row,stage):
    return bool(int(row['stage_mask'])&(1<<stage))


def validate_rows(rows):
    ids=set()
    for r in rows:
        try:
            if not r['id'] or r['id'] in ids:raise ValueError('duplicate/missing opportunity ID')
            ids.add(r['id'])
            values=[float(r[k]) for k in ('score_first','score_min','score_max','threshold')]
            first,minimum,maximum,threshold=values
            if not all(map(math.isfinite,values)):raise ValueError('nonfinite score/threshold')
            if r['score_seen']!='1' or r['score_invalid']!='0':raise ValueError('missing/invalid score')
            if not 0<=minimum<=first<=maximum<=100 or not 0<=threshold<=100:
                raise ValueError('inconsistent score range/scale')
            if not has(r,0) or has(r,1)!=(maximum>=threshold):raise ValueError('score-stage mismatch')
            if int(r['stage_mask'])<0 or int(r['stage_mask'])>>len(STAGES):raise ValueError('unknown stage bits')
        except (KeyError,TypeError,OverflowError) as e:
            raise ValueError('incomplete/invalid diagnostic row') from e
    return rows


def quantile(values,q):
    if not values:return None
    ordered=sorted(values);index=(len(ordered)-1)*q;lo=math.floor(index);hi=math.ceil(index)
    return ordered[lo]+(ordered[hi]-ordered[lo])*(index-lo)


def distribution(values):
    bins=dict.fromkeys(('below60','60_65','65_70','70_75','75_80','80_plus'),0)
    for v in values:
        key=next((name for top,name in zip((60,65,70,75,80),bins) if v<top),'80_plus')
        bins[key]+=1
    return dict(n=len(values),min=min(values) if values else None,
                p10=quantile(values,.1),p25=quantile(values,.25),median=quantile(values,.5),
                p75=quantile(values,.75),p90=quantile(values,.9),max=max(values) if values else None,bins=bins)


def score_summary(rows):
    validate_rows(rows)
    return dict(first=distribution([float(r['score_first']) for r in rows]),
                maximum=distribution([float(r['score_max']) for r in rows]),
                initially_below_threshold=sum(float(r['score_first'])<float(r['threshold']) for r in rows),
                ever_below_threshold=sum(float(r['score_min'])<float(r['threshold']) for r in rows),
                below_threshold_only=sum(not has(r,1) for r in rows),
                changed_within_opportunity=sum(float(r['score_min'])!=float(r['score_max']) for r in rows))


def compare_candidates(left,right):
    validate_rows(left);validate_rows(right)
    a={r['id']:r for r in left if has(r,5)};b={r['id']:r for r in right if has(r,5)}
    common=a.keys()&b.keys()
    return dict(net_candidate_change=len(b)-len(a),
                added_ids=sorted(b.keys()-a.keys()),removed_ids=sorted(a.keys()-b.keys()),
                common_ids=sorted(common),
                common_accepted_to_unaccepted=sorted(i for i in common if has(a[i],11) and not has(b[i],11)),
                common_unaccepted_to_accepted=sorted(i for i in common if not has(a[i],11) and has(b[i],11)),
                net_accepted_change=sum(has(r,11) for r in b.values())-sum(has(r,11) for r in a.values()))


def position_reason(row):
    mask=int(row['last_position_mask'])
    if mask&(1<<7):return 'unresolved_order'
    if mask&(1<<6):return 'pending_order'
    if mask&1:
        policy='netting_same_symbol' if mask&(1<<3) else 'hedging_single_position'
        direction='same_direction' if mask&(1<<1) else 'opposite_direction'
        ownership='owned' if mask&(1<<8) else 'foreign'
        return '/'.join((policy,direction,ownership))
    return 'other_position_or_prior_preflight'


def outcome(row,reason_names):
    if has(row,11):return 'accepted'
    if not has(row,5):return reason_names.get(int(row['terminal_reason']),'unknown_upstream')
    if not has(row,13):return 'position/'+position_reason(row)
    if not has(row,15):
        if has(row,14):
            reasons=[MC[i] for i in (5,6,7,10) if int(row['mc_block_mask'])&(1<<i)]
            return 'MC/'+('+'.join(reasons) if reasons else 'unknown_completed_denial')
        return 'MC/'+MC[int(row['last_mc_reason'])]
    return reason_names.get(int(row['terminal_reason']),'unknown_post_mc')


def analyze_rows(rows,reason_names):
    validate_rows(rows)
    for r in rows:
        for field,n in [('position_mask',len(POSITION)),('last_position_mask',len(POSITION)),
                        ('mc_mask',len(MC)),('mc_block_mask',len(MC))]:
            if int(r[field])<0 or int(r[field])>>n:raise ValueError('unknown reason bits')
        if not 0<=int(r['last_mc_reason'])<len(MC):raise ValueError('unknown MC reason')
        # Every downstream milestone must have actually reached its parent.
        for child,parent in ((1,0),(2,1),(3,2),(4,3),(5,4),(13,5),(14,13),(15,14),(6,15),(7,6),(8,7),(10,8),(11,10),(12,10)):
            if has(r,child) and not has(r,parent):raise ValueError(f'inconsistent funnel {child}/{parent}')
    positions=[r for r in rows if has(r,5) and not has(r,13)]
    mc=[r for r in rows if has(r,13) and not has(r,15)]
    return dict(funnel={k:sum(has(r,i) for r in rows) for i,k in enumerate(STAGES)},score=score_summary(rows),
                position_blocked=len(positions),position_reasons=dict(Counter(position_reason(r) for r in positions)),
                position_axes={name:sum(bool(int(r['last_position_mask'])&(1<<i)) for r in positions) for i,name in enumerate(POSITION)},
                position_ever_blocked=sum(bool(int(r['position_mask'])) for r in rows if has(r,5)),
                mc_blocked=len(mc),mc_not_ready=sum(not has(r,14) for r in mc),mc_decided_denial=sum(has(r,14) for r in mc),
                mc_completed_simulation_denial=sum(bool(int(r['mc_block_mask'])&(1<<7)) for r in mc),
                mc_reasons=dict(Counter(outcome(r,reason_names) for r in mc)),
                mc_ever_states={name:sum(bool(int(r['mc_mask'])&(1<<i)) for r in rows) for i,name in enumerate(MC)},
                mc_blocked_snapshots=[{k:r[k] for k in ('id','bar','buy','mc_ready','mc_allowed','mc_active','history_ok','history_dirty','samples','returns_count','bootstrap_count','mc_run','mc_trade','mc_candidate','win_rate','mc_risk','dd_seen','dd','dd_limit','mc_elapsed_max','candidate_first','candidate_last')} for r in mc],
                outcomes=dict(Counter(outcome(r,reason_names) for r in rows)),
                post_mc_blocked=sum(has(r,15) and not has(r,11) for r in rows))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv',type=Path)
    parser.add_argument('--compare',type=Path,help='A second candidate CSV from the same symbol and period')
    args=parser.parse_args()
    with args.csv.open(encoding='ascii',newline='') as f:rows=list(csv.DictReader(f))
    text=Path(__file__).with_name('TesterPipelineDiag.mqh').read_text(encoding='utf-8')
    enum=text.split('enum TesterPipelineCounter',1)[1].split('};',1)[0]
    names=dict(enumerate(re.findall(r'\bTP_[A-Z_]+\b',enum)))
    result=analyze_rows(rows,names)
    if args.compare:
        with args.compare.open(encoding='ascii',newline='') as f:other=list(csv.DictReader(f))
        result['comparison']=compare_candidates(rows,other)
        result['compared_analysis']=analyze_rows(other,names)
    print(json.dumps(result,indent=2))
