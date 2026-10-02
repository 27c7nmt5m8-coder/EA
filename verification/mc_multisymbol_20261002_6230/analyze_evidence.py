"""Extra analysis of frozen, allowlisted exports; never reads native journals."""
import json
import sys
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1]))
from tools import mc500k_batch as batch
from tools.analyze_mc_multisymbol import require_export, exact_export, order_accepted
from tools.analyze_mc_timeline import analyze as timeline_analyze


def overlap(a, b, first, last):
    return max(0, min(int(a[last]), int(b[last])) - max(int(a[first]), int(b[first])))


def main():
    summary = json.loads((ROOT / 'summary.json').read_text(encoding='utf-8'))
    manifest = json.loads((ROOT / 'matrix/manifest_final.json').read_text(encoding='utf-8'))
    if summary['completed'] != 12:
        raise ValueError('incomplete matrix')
    raw = {}
    observations = []
    for frozen in manifest:
        directory = ROOT / 'native' / frozen['case']
        result = json.loads((directory / 'result.json').read_text(encoding='utf-8'))
        prefix = result['scheduler']['prefix']
        data = dict(
            snapshots=require_export(directory, result, '_snapshots.csv'),
            callbacks=require_export(directory, result, '_callbacks.csv'),
            timings=require_export(directory, result, '_timings.csv'),
            guards=require_export(directory, result, '_guards.csv'),
            requests=require_export(directory, result, '_requests.csv'),
            details=exact_export(directory, result, prefix.replace('20260927_', '20260927Detail_') + '.csv'),
            timeline=exact_export(directory, result, prefix + '.csv'))
        raw[(frozen['count'], frozen['mode'], frozen['load'])] = data
        case = next(c for c in summary['cases'] if c['case'] == frozen['case'])
        completed_actual = [s for s in data['snapshots'] if s['kind'] == 'ACTUAL' and s['completed'] == '1']
        natural_pairs = []
        for i, a in enumerate(completed_actual):
            for b in completed_actual[i+1:]:
                if a['symbol'] == b['symbol']:
                    continue
                seconds = overlap(a, b, 'server_start_s', 'server_end_s')
                micros = overlap(a, b, 'start_wall_us', 'end_wall_us')
                if seconds > 0 and micros > 0:
                    natural_pairs.append(dict(symbols=[a['symbol'], b['symbol']], cycles=[a['cycle'], b['cycle']],
                                              active_market_overlap_s=seconds, active_wall_overlap_ms=micros/1000))
        orders = [t for t in data['timings'] if t['event'] == 'ENTRY_SEND']
        accepted = [t for t in orders if order_accepted(t)]
        if len(accepted) != case['trades']:
            raise ValueError('accepted order/trade mismatch')
        symbol_timeline = {
            s: timeline_analyze([e for e in data['timeline'] if e['symbol'] == s],
                               [d for d in data['details'] if d['symbol'] == s])
            for s in frozen['symbols']}
        expiries = [dict(symbol=s, id=o['id'], first_wait_s=o['first_wait_s'],
                        observed_eligible_s=o['lifetime_observed_s'],
                        observed_post_position_wait_s=o['last_eligible_s']-o['first_wait_s'])
                    for s, t in symbol_timeline.items() for o in t['opportunities']
                    if any(r['classification']['expired_before_completion'] for r in o['mc_wait_cycles'])]
        details_by_id = {d['id']: d for d in data['details']}
        candidate_to_request = [int(t['server_start_s'])-int(details_by_id[t['opp_id']]['candidate_first'])
                                for t in orders if t['opp_id'] in details_by_id
                                and int(details_by_id[t['opp_id']]['candidate_first']) > 0]
        shadow_timer_spans = {}
        for symbol in frozen['symbols']:
            served = [c for c in data['callbacks'] if c['symbol']==symbol and c['kind']=='SHADOW']
            shadow_timer_spans[symbol]=dict(first_timer=int(served[0]['timer']),last_timer=int(served[-1]['timer']),
                                          first_last_timer_ordinal_span=int(served[-1]['timer'])-int(served[0]['timer']),
                                          clock='callback ordinal, not server or wall-clock seconds')
        observations.append(dict(case=frozen['case'], count=frozen['count'], mode=frozen['mode'], load=frozen['load'],
            completed_natural_active_overlap=natural_pairs,
            completed_natural_active_overlap_scope='lower bound from completed snapshots, not parallel execution',
            shadow_overlap_s=case['shadow_overlap_s'], natural_shadow_overlap=case['natural_shadow_overlap'],
            shadow_timer_spans=shadow_timer_spans,
            order_calls=len(orders), accepted=len(accepted), rejected=len(orders)-len(accepted),
            order_retcode_counts=dict(Counter(t['retcode'] for t in orders)),
            order_call_wall_ms=batch.percentiles(int(t['elapsed_us'])/1000 for t in orders),
            candidate_to_request_market_s=batch.percentiles(candidate_to_request),
            candidate_to_request_scope='first observed pre-position candidate to request; not enqueue latency',
            expired_while_waiting=expiries,
            lifetime_observed_s=batch.percentiles(o['observed_eligible_s'] for o in expiries),
            post_position_wait_observed_s=batch.percentiles(o['observed_post_position_wait_s'] for o in expiries),
            queue_depth='UNKNOWN', handler_enqueue_latency='UNKNOWN',
            per_symbol_position_management_latency='UNKNOWN', position_mc_spike_attribution='UNKNOWN',
            broker_live_latency='UNKNOWN'))
    differences = []
    for n in (2, 3, 4):
        for load in ('NORMAL', 'CPU_CONTENTION'):
            a, b = raw[(n, 0, load)], raw[(n, 2, load)]
            da = {d['id']: d for d in a['details']}
            db = {d['id']: d for d in b['details']}
            # Do not infer causality solely from an aggregate difference.
            accepted_a = {t['opp_id'] for t in a['timings'] if t['event']=='ENTRY_SEND' and order_accepted(t)}
            accepted_b = {t['opp_id'] for t in b['timings'] if t['event']=='ENTRY_SEND' and order_accepted(t)}
            diffs = []
            for identity in sorted((set(da) ^ set(db)) | (accepted_a ^ accepted_b)):
                destination = b if identity in da else a
                old, new = da.get(identity), db.get(identity)
                guards = [g for g in destination['guards'] if g['opp_id']==identity]
                timeline_a = [e for e in a['timeline'] if e['opp_id']==identity and e['event'] in ('ELIGIBLE','ELIGIBILITY_END','ACCEPTED')]
                timeline_b = [e for e in b['timeline'] if e['opp_id']==identity and e['event'] in ('ELIGIBLE','ELIGIBILITY_END','ACCEPTED')]
                keep = ('event','server_s','trigger','cycle','history_version','input_version','state_version','ready','allowed','active','position_kind','score')
                classification = 'INSUFFICIENT_EVIDENCE'
                evidence_note = 'No direct causal classification.'
                if identity in accepted_b and identity not in accepted_a and any(
                        e['event']=='ELIGIBLE' and e['position_kind']=='0' and e['active']=='1' and e['ready']=='0'
                        for e in timeline_a) and any(e['event']=='ACCEPTED' and e['ready']=='1' and e['allowed']=='1'
                                                  for e in timeline_b):
                    classification = 'MC_STATE_CHANGE'
                    evidence_note = 'Current eligible without position while MC active; fixed500k ready/permitted and accepted.'
                elif identity in accepted_a and identity not in accepted_b and any(
                        e['event']=='ELIGIBLE' and e['position_kind']!='0' for e in timeline_b):
                    classification = 'POSITION_STATE_CHANGE'
                    evidence_note = 'fixed500k explicit eligible event observes an existing position.'
                elif old and not new and any(g['reason']=='RECEIPT' and g['prior_claimant_id'] in accepted_b
                                              for g in guards):
                    classification = 'EXPECTED_SEQUENCE_CHANGE'
                    evidence_note = 'Before-Safety observer sees receipt consumed by earlier fixed500k accepted opportunity; actual_seen flag retained.'
                diffs.append(dict(id=identity, symbol=(old or new)['symbol'],
                                  current_detail=old, fixed500k_detail=new,
                                  current_accepted=identity in accepted_a, fixed500k_accepted=identity in accepted_b,
                                  destination_guards=guards,
                                  current_timeline=[{k:e[k] for k in keep} for e in timeline_a],
                                  fixed500k_timeline=[{k:e[k] for k in keep} for e in timeline_b],
                                  classification=classification, evidence_note=evidence_note))
            differences.append(dict(count=n, load=load, current_only_ids=sorted(set(da)-set(db)),
                                    fixed500k_only_ids=sorted(set(db)-set(da)),
                                    current_only_accepted=sorted(accepted_a-accepted_b),
                                    fixed500k_only_accepted=sorted(accepted_b-accepted_a), evidence=diffs))
    payload = dict(build=6230, observations=observations, sequence_differences=differences,
                   numerical_replay_comparisons=sum(c['replay_rows'] for c in summary['cases']),
                   native_completed_result_comparisons_by_kind={k:sum(c['native_completed_replay_rows_by_kind'][k]
                       for c in summary['cases']) for k in ('ACTUAL','SHADOW','SELFTEST')},
                   native_shadow_pair_comparisons=len(summary['native_shadow_equivalence']),
                   native_shadow_pair_mismatch=sum(not r['equal'] for r in summary['native_shadow_equivalence']))
    text=json.dumps(payload, indent=2, ensure_ascii=True)+'\n'
    batch.PrivacyGuard().check(text)
    (ROOT/'observations.json').write_text(text, encoding='utf-8')
    print(json.dumps(dict(completed=len(observations), comparisons=payload['numerical_replay_comparisons'],
                         native_by_kind=payload['native_completed_result_comparisons_by_kind'],
                         accepted_differences=[{k:d[k] for k in ('count','load','current_only_accepted','fixed500k_only_accepted')}
                                               for d in differences])))


if __name__=='__main__':
    main()
