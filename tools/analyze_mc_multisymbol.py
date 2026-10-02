"""Summarize allowlisted multi-symbol Tester exports without raw journals."""
from collections import Counter
import csv
import json
from pathlib import Path

try:
    from . import mc500k_batch as batch
    from .analyze_mc_timeline import analyze as timeline_analyze
except ImportError:
    import mc500k_batch as batch
    from analyze_mc_timeline import analyze as timeline_analyze


def rows(path):
    with Path(path).open(encoding='ascii', newline='') as stream:
        return list(csv.DictReader(stream))


def order_accepted(row):
    return row['success'] == '1' and row['retcode'] in ('10008', '10009', '10010')


def snapshot_lifecycle_counts(kind, snapshots, cycles):
    """Never infer cancellation from absence of a completed snapshot."""
    return dict(
        unfinished=sum(r['completed'] != '1' for r in snapshots),
        cancelled=sum(kind == 'ACTUAL' and cycles.get(int(r['cycle']), {}).get('status') == 'cancelled'
                      for r in snapshots),
        censored=sum(kind == 'ACTUAL' and cycles.get(int(r['cycle']), {}).get('status') == 'censored'
                     for r in snapshots))


def require_export(directory, result, suffix):
    found = [n for n in result['exports'] if n.endswith(suffix)]
    if len(found) != 1:
        raise ValueError('missing/duplicate required export')
    path = Path(directory) / found[0]
    if batch.sha(path) != result['exports'][found[0]]:
        raise ValueError('export checksum mismatch')
    return rows(path)


def exact_export(directory, result, name):
    if name not in result['exports']:
        raise ValueError('required exact export absent')
    path = Path(directory) / name
    if batch.sha(path) != result['exports'][name]:
        raise ValueError('export checksum mismatch')
    return rows(path)


def describe_case(directory):
    directory = Path(directory)
    result = json.loads((directory / 'result.json').read_text(encoding='utf-8'))
    if result['status'] != 'PASS':
        raise ValueError('case not passed')
    callbacks = require_export(directory, result, '_callbacks.csv')
    snapshots = require_export(directory, result, '_snapshots.csv')
    requests = require_export(directory, result, '_requests.csv')
    timings = require_export(directory, result, '_timings.csv')
    prefix = result['scheduler']['prefix']
    details = exact_export(directory, result, prefix.replace('20260927_', '20260927Detail_') + '.csv')
    events = exact_export(directory, result, prefix + '.csv')
    if int(result['pipeline']['ticks']) != result['report_metrics']['ticks']:
        raise ValueError('chart processed tick count differs from Tester report')
    symbols = {}
    for symbol in result['symbols']:
        d = [r for r in details if r['symbol'] == symbol]
        e = [r for r in events if r['symbol'] == symbol]
        funnel = batch.analyze_rows(d, batch.reason_names())
        timeline = timeline_analyze(e, d)
        c = [r for r in callbacks if r['symbol'] == symbol]
        s = [r for r in snapshots if r['symbol'] == symbol]
        req = [r for r in requests if r['symbol'] == symbol]
        order = [r for r in timings if r['symbol'] == symbol and r['event'] == 'ENTRY_SEND']
        by_kind = {}
        for kind in ('ACTUAL', 'SHADOW'):
            ck = [r for r in c if r['kind'] == kind]
            sk = [r for r in s if r['kind'] == kind]
            finished = [r for r in sk if r['completed'] == '1']
            # Unfinished snapshots may be censored at run end; they are not
            # evidence of cancellation. Only explicit lifecycle events count.
            lifecycle_counts = snapshot_lifecycle_counts(kind, sk, timeline['cycles'])
            by_kind[kind] = dict(started=len(sk), completed=len(finished),
                                 **lifecycle_counts, callbacks=len(ck),
                                 operations=sum(int(r['operations']) for r in ck),
                                 callback_elapsed_sum_ms=sum(int(r['elapsed_us']) for r in ck)/1000,
                                 operations_per_completed_cycle=batch.percentiles(int(r['operations']) for r in finished),
                                 callback_ms=batch.percentiles(int(r['elapsed_us']) / 1000 for r in ck),
                                 market_s=batch.percentiles(int(r['server_end_s']) - int(r['server_start_s'])
                                                            for r in finished),
                                 wall_elapsed_ms=batch.percentiles(int(r['duration_us']) / 1000 for r in finished))
        force = [r for r in req if r['force'] == '1']
        heavy_force = [r for r in force if r['heavy_start'] == '1']
        duplicate_heavy = [r for r in heavy_force if all(r[k] == '1' for k in ('same_input','same_state','fresh'))]
        duplicate_cycles = {r['cycle_after'] for r in duplicate_heavy}
        duplicate_callbacks = [r for r in c if r['kind'] == 'ACTUAL' and r['cycle'] in duplicate_cycles]
        symbols[symbol] = dict(funnel=funnel['funnel'], outcomes=funnel['outcomes'],
                               mc=by_kind, mc_lifecycle=timeline['metrics'],
                               force_requests=len(force), heavy_force=len(heavy_force),
                               duplicate_heavy=len(duplicate_heavy),
                               immediate_force=len(force) - len(heavy_force),
                               force_wall_ms=sum(int(r['elapsed_us']) for r in force)/1000,
                               duplicate_heavy_callback_elapsed_sum_ms=sum(int(r['elapsed_us']) for r in duplicate_callbacks)/1000,
                               duplicate_heavy_callbacks=len(duplicate_callbacks),
                               duplicate_heavy_operations=sum(int(r['operations']) for r in duplicate_callbacks),
                               order_calls=len(order),
                               order_send_ms=batch.percentiles(int(r['elapsed_us'])/1000 for r in order),
                               order_acceptance=sum(order_accepted(r) for r in order),
                               order_raw_call_success=sum(r['success']=='1' for r in order),
                               order_retcode_counts=dict(Counter(r['retcode'] for r in order)),
                               quote_samples=result['symbol_rows'][symbol]['quote_samples'],
                               quote_advances=result['symbol_rows'][symbol]['quote_advances'])
    return dict(case=result['case'], mode=result['mode'], load=result['load'], symbols=symbols,
                chart_processed_ticks=result['report_metrics']['ticks'],
                symbol_bar_process_total=int(result['pipeline']['new_bars']),
                chart_input_ticks=result['report_metrics']['ticks'],
                foreign_input_ticks='UNKNOWN',
                position_manage_by_symbol='UNKNOWN', order_live_broker_latency='UNKNOWN',
                queue_depth='UNKNOWN', runtime_errors=result['runtime_errors'],
                trades=result['report_metrics']['trades'], replay_rows=result['replay_rows'])


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    print(json.dumps(describe_case(args.directory), ensure_ascii=True, indent=2))
