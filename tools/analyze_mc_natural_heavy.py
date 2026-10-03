"""ACTUAL MC lifecycle overlap, using one EA execution clock, never shadows."""
from collections import defaultdict
import math
from .analyze_mc_timeline import cycles_from_events


def natural_overlap(events, snapshots, symbols):
    symbols = tuple(symbols)
    if len(set(symbols)) != len(symbols) or len(symbols) not in (3, 4):
        raise ValueError('expected distinct three/four-symbol universe')
    grouped = defaultdict(list)
    last_seq, last_clock = 0, -1
    for event in events:
        seq, clock = int(event['seq']), int(event['wall_us'])
        if seq <= last_seq or clock < last_clock:
            raise ValueError('timeline must use one globally ordered execution clock')
        last_seq, last_clock = seq, clock
        if event['symbol'] not in symbols:
            raise ValueError('timeline symbol outside frozen universe')
        grouped[event['symbol']].append(event)
    captured = {}
    for row in snapshots:
        if row['kind'] in ('SHADOW', 'SELFTEST'):
            continue
        if row['kind'] != 'ACTUAL' or row['symbol'] not in symbols:
            raise ValueError('unknown snapshot kind or symbol')
        key = (row['symbol'], int(row['cycle']))
        if key in captured:
            raise ValueError('duplicate actual snapshot')
        captured[key] = row
    intervals = []
    started_keys = set()
    for symbol in symbols:
        cycles = cycles_from_events(grouped[symbol])
        for cid, cycle in cycles.items():
            if cycle['start_us'] is None:
                continue
            key = (symbol, cid); started_keys.add(key)
            row = captured.get(key)
            if row is None:
                raise ValueError('actual START without input snapshot')
            start, end = cycle['start_us'], cycle.get('end_us')
            if end is None or end <= start:
                raise ValueError('actual START lacks positive bounded lifecycle')
            request = cycle['request']
            for field in ('samples', 'input_digest', 'input_version', 'history_version'):
                if row[field] != request[field] or cycle['start'][field] != request[field]:
                    raise ValueError('actual lifecycle input/history mismatch')
            if (int(row['samples']) < 30 or not row['input_digest'] or
                not start <= int(row['start_wall_us']) <= end):
                raise ValueError('invalid natural heavy snapshot')
            rate, started_rate = float(request['win_rate']), float(cycle['start']['win_rate'])
            if not math.isfinite(rate) or not .40 <= rate <= 1 or started_rate != rate:
                raise ValueError('natural START contradicts frozen win-rate gate')
            completed = cycle['status'] == 'completed'
            if row['completed'] != str(int(completed)):
                raise ValueError('actual completion/snapshot mismatch')
            if completed and not int(row['start_wall_us']) <= int(row['end_wall_us']) <= end:
                raise ValueError('actual snapshot completion clock mismatch')
            # The result snapshot is captured before the later COMPLETE marker.
            # That observer tail cannot extend the active heavy calculation.
            active_end = int(row['end_wall_us']) if completed else end
            intervals.append(dict(symbol=symbol, cycle=cid, start_wall_us=start, end_wall_us=end,
                                  status=cycle['status'], input_digest=row['input_digest'],
                                  input_version=int(row['input_version']), history_version=int(row['history_version'])))
            intervals[-1]['lifecycle_end_wall_us'] = end
            intervals[-1]['end_wall_us'] = active_end
    if started_keys != set(captured):
        raise ValueError('actual snapshot without lifecycle START')
    boundaries = sorted({i[k] for i in intervals for k in ('start_wall_us', 'end_wall_us')})
    witnesses = []; maximum = 0
    cardinality = {str(n): dict(duration_us=0, witnesses=[]) for n in range(2, len(symbols)+1)}
    for left, right in zip(boundaries, boundaries[1:]):
        active = [i for i in intervals if i['start_wall_us'] <= left and i['end_wall_us'] >= right]
        unique = {i['symbol'] for i in active}
        if len(active) != len(unique):
            raise ValueError('overlapping actual cycles within one symbol')
        maximum = max(maximum, len(unique))
        if len(unique) >= 2:
            witness=dict(start_wall_us=left, end_wall_us=right, duration_us=right-left,
                         cycles=[dict(symbol=i['symbol'], cycle=i['cycle'], status=i['status']) for i in active])
            cardinality[str(len(unique))]['duration_us'] += right-left
            cardinality[str(len(unique))]['witnesses'].append(witness)
            if len(unique) == len(symbols):witnesses.append(witness)
    all_completed = [w for w in witnesses if all(i['status']=='completed' for i in w['cycles'])]
    return dict(clock='EA GetMicrosecondCount / wall microseconds', target_symbols=list(symbols),
                execution='one EA event loop; overlapping active cycles, interleaved callbacks; not parallel CPU threads',
                maximum_active_symbols=maximum, actual_intervals=intervals,
                target_overlap_us=sum(w['duration_us'] for w in witnesses), witnesses=witnesses,
                overlap_by_cardinality=cardinality,
                simultaneous_activity='OBSERVED' if witnesses else 'UNOBSERVED',
                completed_overlap='OBSERVED' if all_completed else 'PARTIAL' if witnesses else 'UNOBSERVED',
                queue_depth='UNKNOWN', broker_live_latency='UNKNOWN')
