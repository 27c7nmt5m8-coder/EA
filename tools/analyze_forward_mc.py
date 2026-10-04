"""Read an allowlisted observer CSV locally; never read terminal/account files."""
import argparse
from collections import Counter
import csv
import json
import re

FIELDS='seq event symbol cycle start_wall_us end_wall_us server_s utc_s count max_us total_us reason ready allowed_or_success value_bits rng active_symbols arrival_us queue_depth observer_unknown'.split()
SYMBOLS={'USDJPY','EURUSD','EURJPY','XAUUSD'}
EVENTS=set('MC_REQUEST MC_FORCE_REQUEST MC_PRIOR_RESULT MC_START MC_INPUT MC_INPUT_VERSION MC_DD95 MC_COMPLETE MC_CANCEL_FORCE MC_IMMEDIATE_DECISION MC_PREPARATION_FAILED MC_CYCLE_CALLBACKS MC_CYCLE_OPERATIONS HISTORY_REFRESH MC_PREFLIGHT_WAIT_BAR MC_WAIT_WINDOW_END BAR CANDIDATE ORDER_RESULT POSITION_CLOSE_RESULT POSITION_MODIFY_RESULT TRADE_TRANSACTION DEAL_PRICE DEAL_VOLUME TRADE_REQUEST_RESULT INIT DEINIT DURATION_OUTLIER DURATION_TOTAL DURATION_HIST POSITION_SAMPLE PROGRESSION'.split())


def invalid():
    raise ValueError('invalid observer evidence; private source review required')


def read_rows(stream):
    reader=csv.DictReader(stream)
    if reader.fieldnames!=FIELDS:invalid()
    return list(reader)


def analyze(rows):
    active={};counts=Counter();last_seq=0;unknown=0;anomalies=0;overlaps=[];maximum=0;previous=None
    totals={};hist={};cycles=[];orders=[];symbols=Counter();requests=set();seen_starts=set()
    for row in rows:
        if set(row)!=set(FIELDS) or row['event'] not in EVENTS or row['symbol'] not in SYMBOLS:invalid()
        if row['arrival_us']!='UNKNOWN' or row['queue_depth']!='UNKNOWN':invalid()
        values={}
        for key in FIELDS:
            if key in ('event','symbol','arrival_us','queue_depth','value_bits'):continue
            value=row[key]
            if key in ('ready','allowed_or_success') and value.lower() in ('true','false'):value=str(int(value.lower()=='true'))
            if not re.fullmatch(r'-?\d{1,20}',value):invalid()
            values[key]=int(value)
            if key!='reason' and not 0<=values[key]<2**64:invalid()
        if not re.fullmatch(r'[0-9A-Fa-f]{1,16}',row['value_bits']):invalid()
        if values['seq']!=last_seq+1 or values['end_wall_us']<values['start_wall_us'] or values['active_symbols']>4:invalid()
        if values['ready'] not in (0,1) or values['allowed_or_success'] not in (0,1):invalid()
        last_seq=values['seq'];unknown=max(unknown,values['observer_unknown'])
        event,symbol,cycle=row['event'],row['symbol'],values['cycle'];key=(symbol,cycle)
        counts[event]+=1;symbols[symbol]+=1
        if event=='MC_REQUEST':
            if key in requests:anomalies+=1
            requests.add(key)
        if event in ('MC_START','MC_COMPLETE','MC_CANCEL_FORCE'):
            now=values['end_wall_us']
            if previous is not None and now<previous:invalid()
            if previous is not None and len(active)>=2 and now>previous:
                overlaps.append({'symbols':sorted(active),'cycle_ids':{s:state[0] for s,state in active.items()},
                                 'start_wall_us':previous,'end_wall_us':now,'duration_us':now-previous})
            previous=now
            if event=='MC_START':
                if key not in requests or symbol in active or key in seen_starts:anomalies+=1
                seen_starts.add(key);active[symbol]=(cycle,now,values['server_s'])
                if values['active_symbols']!=len(active):anomalies+=1
            else:
                if values['active_symbols']!=len(active):anomalies+=1
                start=active.pop(symbol,None)
                if start is None or start[0]!=cycle:anomalies+=1
                else:cycles.append({'symbol':symbol,'cycle':cycle,'outcome':event,'wall_elapsed_us':now-start[1],
                                   'server_elapsed_s':values['server_s']-start[2],'ready':bool(values['ready']),
                                   'permitted':bool(values['allowed_or_success']),'risk_bits':row['value_bits'],'rng':values['rng']})
            maximum=max(maximum,len(active))
        if event=='DURATION_TOTAL':
            if not 0<=values['reason']<5:invalid()
            totals[f'{symbol}:{values["reason"]}']={k:values[k] for k in ('count','max_us','total_us')}
        if event=='DURATION_HIST':
            if not 0<=values['reason']<5:invalid()
            hist[f'{symbol}:{values["reason"]}:{values["max_us"]}']=values['count']
        if event in ('ORDER_RESULT','POSITION_CLOSE_RESULT','POSITION_MODIFY_RESULT'):
            orders.append({'symbol':symbol,'path':event,'retcode':values['reason'],'call_success':bool(values['allowed_or_success']),
                           'wall_elapsed_us':values['end_wall_us']-values['start_wall_us']})
    completed={(c['symbol'],c['cycle']) for c in cycles if c['outcome']=='MC_COMPLETE'}
    broken=unknown or anomalies or counts['MC_PREPARATION_FAILED']
    coverage={}
    for n in (2,3,4):
        complete=any(len(o['symbols'])>=n and all((s,c) in completed for s,c in o['cycle_ids'].items()) for o in overlaps)
        coverage[f'{n}_symbol']='INVALID' if broken else 'OBSERVED_COMPLETE' if complete else 'PARTIAL' if maximum>=n else 'UNOBSERVED'
    return {'status':'INCOMPLETE' if not rows or broken or active else 'RECORDED_NOT_ACCEPTED',
            'row_count':len(rows),'observer_unknown':unknown,'lifecycle_anomalies':anomalies,'event_counts':dict(counts),
            'observed_symbols':sorted(symbols),'actual_max_overlap':maximum,'overlap_intervals':overlaps,'cycles':cycles,
            'completed_cycles':counts['MC_COMPLETE'],'open_cycles':len(active),
            'coverage':coverage,
            'duration_totals':totals,'duration_histogram_cumulative':hist,'exact_percentiles':'UNKNOWN_BUCKET_BOUNDS_ONLY',
            'orders':orders,'mc_wait_bar_observations':counts['MC_PREFLIGHT_WAIT_BAR'],
            'eligible_opportunity_expiry':'UNKNOWN','queue_wait':'UNKNOWN','queue_depth':'UNKNOWN',
            'position_arrival_delay':'UNKNOWN','input_tick_loss':'UNKNOWN_WITHOUT_INDEPENDENT_FEED',
            'numerical_equivalence':'NOT_RUN','forward_acceptance':'NOT_DECIDED'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('observer_csv')
    args=parser.parse_args()
    try:
        with open(args.observer_csv,encoding='ascii',newline='') as stream:result=analyze(read_rows(stream))
    except (OSError,UnicodeError,ValueError,AttributeError,TypeError):
        parser.exit(1,'UNKNOWN: invalid or unavailable observer evidence; private review required\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
