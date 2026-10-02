"""MC event lifecycle accounting; market seconds and execution microseconds stay separate."""
import argparse
import csv
import json
from pathlib import Path

try:
    from .analyze_tester_bottlenecks import quantile
except ImportError:
    from analyze_tester_bottlenecks import quantile


def cycles_from_events(events):
    cycles={};last_seq=0
    for e in events:
        seq=int(e['seq']);cid=int(e['cycle']);kind=e['event']
        if seq<=last_seq:raise ValueError('event sequence must be strictly increasing')
        last_seq=seq
        if kind=='REQUEST':
            if cid in cycles:raise ValueError('duplicate cycle request')
            parent=cycles.get(int(e['parent']))
            cycles[cid]=dict(id=cid,parent=int(e['parent']),trigger=e['trigger'],request_s=int(e['server_s']),
                request_us=int(e['wall_us']),input_version=int(e['input_version']),state_version=int(e['state_version']),
                samples=int(e['samples']),same_input=bool(parent and parent['input_version']==int(e['input_version'])),
                same_state=bool(parent and parent['state_version']==int(e['state_version'])),
                status='requested',start_s=None,start_us=None,complete_s=None,complete_us=None,
                market_duration_s=None,wall_duration_ms=None,invalidated_s=None,request=e)
        elif kind in ('START','COMPLETE','CANCEL','CALCULATION_FAILED','INVALIDATE'):
            if cid not in cycles:raise ValueError('lifecycle event without request')
            c=cycles[cid]
            if kind=='START':
                if c['status']!='requested' or c['start_s'] is not None:raise ValueError('start after terminal event or duplicate start')
                c.update(status='computing',start_s=int(e['server_s']),start_us=int(e['wall_us']),start=e)
            elif kind=='INVALIDATE':c.update(invalidated_s=int(e['server_s']),invalidation_reason=e['trigger'],invalidation=e)
            else:
                if c['status'] not in ('requested','computing'):raise ValueError('duplicate terminal event')
                c.update(status={'COMPLETE':'completed','CANCEL':'cancelled','CALCULATION_FAILED':'failed'}[kind],terminal=e,
                         end_s=int(e['server_s']),end_us=int(e['wall_us']))
                if kind=='COMPLETE':
                    c.update(complete_s=int(e['server_s']),complete_us=int(e['wall_us']),
                             valid_from_s=int(e['server_s']),decision=e['trigger'])
                    if c['start_s'] is not None:
                        c['market_duration_s']=c['complete_s']-c['start_s']
                        c['wall_duration_ms']=(c['complete_us']-c['start_us'])/1000
                        if c['market_duration_s']<0 or c['wall_duration_ms']<0:raise ValueError('negative duration')
        elif kind=='RUN_END' and cid in cycles and cycles[cid]['status'] in ('requested','computing'):
            cycles[cid].update(status='censored',end_s=int(e['server_s']),end_us=int(e['wall_us']),terminal=e)
    return cycles


def classify_wait(cycle,*,first_s,last_s,expiry_s,entered):
    """Classify the observed wait, not a hypothetical benefit of changing policy."""
    trigger=cycle['trigger'];categories=[]
    if trigger=='INITIAL':categories.append('A')
    elif trigger=='HISTORY_CHANGED':categories.extend(['B','G'])
    elif trigger=='PERIODIC_EXPIRY':categories.append('G')
    elif trigger=='FORCED_SAME_INPUT':categories.append('D' if cycle.get('same_state') else 'C')
    else:categories.append('H')
    completed=cycle.get('complete_s')
    expired=not entered and completed is not None and completed>=expiry_s
    if expired:categories.append('E')
    if trigger=='FORCED_SAME_INPUT' and cycle.get('same_input') and cycle.get('same_state'):
        label='UNNECESSARY_RECALCULATION'
    elif expired:label='PERFORMANCE_LIMIT'
    elif entered:label='NORMAL_EXPECTED'
    else:label='INSUFFICIENT_EVIDENCE'
    return dict(classification=label,categories=categories,expired_before_completion=expired)


def completion_eligibility(cycle, identity, expiry_s):
    """An old observer snapshot is not evidence of eligibility at completion."""
    if cycle['status']!='completed':return None
    if cycle['complete_s']>=expiry_s:return False
    e=cycle['terminal']
    if e.get('eligible_timer')!=e.get('timer'):return None
    return e.get('eligible_id')==identity


def duration_stats(values):
    return dict(n=len(values),median=quantile(values,.5),p90=quantile(values,.9),
                p95=quantile(values,.95),max=max(values) if values else None)


def analyze(events,details):
    cycles=cycles_from_events(events)
    started=[c for c in cycles.values() if c['start_s'] is not None]
    completed=[c for c in started if c['status']=='completed']
    by_id={r['id']:r for r in details};opportunities=[]
    if len(by_id)!=len(details):raise ValueError('duplicate opportunity identity')
    for identity,r in by_id.items():
        eligible=[e for e in events if e['event']=='ELIGIBLE' and e['opp_id']==identity]
        if not eligible:continue
        waiting=[e for e in eligible if int(e['position_kind'])==0 and not int(e['ready']) and int(e['active'])]
        endings=[e for e in events if e['event']=='ELIGIBILITY_END' and e['opp_id']==identity]
        accepted=[e for e in events if e['event']=='ACCEPTED' and e['opp_id']==identity]
        first=min(int(e['server_s']) for e in eligible)
        last=max([int(e['server_s']) for e in eligible]+[int(e['last_eligible_s']) for e in endings])
        expiry=min(int(r['bar'])+60,max(int(e['server_s']) for e in endings)) if endings else int(r['bar'])+60
        references=[]
        for cid in sorted({int(e['cycle']) for e in waiting}):
            c=cycles[cid]
            valid=completion_eligibility(c,identity,expiry)
            references.append(dict(cycle=cid,completion_s=c['complete_s'],cycle_status=c['status'],
                eligible_at_completion=valid,classification=classify_wait(c,first_s=first,last_s=last,expiry_s=expiry,entered=bool(accepted))))
        # A cancelled/incomplete calculation cannot prove expiry before completion.
        expired=any(e['trigger']=='BAR_EXPIRED' for e in endings)
        denied=any(int(e['ready']) and not int(e['allowed']) and int(e['position_kind'])==0 for e in eligible)
        outcome='entered' if accepted else ('MC_rejected' if denied else ('expired' if waiting and expired else
                ('blocked_by_position' if not int(r['stage_mask'])&(1<<13) else 'other')))
        opportunities.append(dict(id=identity,bar=int(r['bar']),buy=int(r['buy']),first_eligible_s=first,
            last_eligible_s=last,lifetime_observed_s=last-first,expiry_upper_s=expiry,first_state=eligible[0],
            eligible_states=eligible,ends=endings,accepted=accepted,mc_wait_cycles=references,
            first_wait_s=min(int(e['server_s']) for e in waiting) if waiting else None,
            outcome=outcome))
    return dict(cycles=cycles,opportunities=opportunities,metrics=dict(request_count=len(cycles),
        calculation_count=len(started),completed_calculations=len(completed),
        completed_decisions=sum(c['status']=='completed' for c in cycles.values()),
        restart_count=sum(c['status']=='cancelled' for c in cycles.values()),
        recalculation_requests=max(0,len(cycles)-1),
        censored_count=sum(c['status']=='censored' for c in cycles.values()),
        failed_count=sum(c['status']=='failed' for c in cycles.values()),
        market_duration_s=duration_stats([c['market_duration_s'] for c in completed]),
        wall_elapsed_ms=duration_stats([c['wall_duration_ms'] for c in completed]),
        advance_execution_ms=duration_stats([int(c['terminal']['advance_us'])/1000 for c in completed]),
        waiting_opportunities=sum(bool(o['mc_wait_cycles']) for o in opportunities),
        waiting_not_entered=sum(bool(o['mc_wait_cycles']) and not o['accepted'] for o in opportunities),
        expired_before_completion=sum(any(x['classification']['expired_before_completion'] for x in o['mc_wait_cycles']) for o in opportunities)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('events',type=Path);parser.add_argument('details',type=Path)
    args=parser.parse_args()
    with args.events.open(encoding='ascii',newline='') as f:events=list(csv.DictReader(f))
    with args.details.open(encoding='ascii',newline='') as f:details=list(csv.DictReader(f))
    print(json.dumps(analyze(events,details),indent=2))
