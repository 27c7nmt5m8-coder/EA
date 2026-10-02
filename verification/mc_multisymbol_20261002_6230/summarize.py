"""Aggregate fresh, hash-verified diagnostic evidence; no native journals."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1]))
from tools import mc500k_batch as batch
from tools.analyze_mc_multisymbol import describe_case, require_export
from tools.mc_multisymbol_runner import validate_result_binding, verify_staged, build_cases


def summarize():
    manifest_file = ROOT / 'matrix/manifest_final.json'
    if not manifest_file.is_file():
        manifest_file = ROOT / 'matrix/manifest.json'
    manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
    environment = json.loads((ROOT / 'environment.json').read_text(encoding='utf-8'))
    if (environment['build'] != 6230 or len(manifest) != 12 or
        len({c['case'] for c in manifest}) != 12 or
        {(c['count'], c['mode'], c['load'], tuple(c['symbols'])) for c in manifest} !=
        {(c['count'], c['mode'], c['load'], tuple(c['symbols'])) for c in build_cases()} or
        any(c['engine_sha256'] != environment['engine_sha256'] for c in manifest)):
        raise ValueError('matrix or engine epoch mismatch')
    cases = []
    for frozen in manifest:
        directory = ROOT / 'native' / frozen['case']
        if not (directory / 'result.json').is_file():
            cases.append({'case': frozen['case'], 'status': 'NOT_RUN'})
            continue
        result = json.loads((directory / 'result.json').read_text(encoding='utf-8'))
        validate_result_binding(result, frozen)
        verify_staged(frozen)
        attempt = json.loads((directory / 'attempt.json').read_text(encoding='utf-8'))
        if (attempt['status'] != 'COLLECTABLE' or attempt['exit_code'] != 0 or
            any(attempt[k] != frozen[k] for k in ('case', 'mode', 'load')) or
            (directory / 'result.json').stat().st_mtime < attempt['started']):
            raise ValueError('result attempt or freshness mismatch')
        summary = describe_case(directory)
        callbacks = require_export(directory, result, '_callbacks.csv')
        summary['count'] = frozen['count']
        summary['status'] = 'PASS'
        summary['events'] = require_export(directory, result, '_events.csv')
        summary['management'] = require_export(directory, result, '_timing_summary.csv')
        summary['shadow_results'] = require_export(directory, result, '_multi_summary.csv')
        replay = require_export(directory, result, '_replay.csv')
        summary['native_completed_replay_rows_by_kind'] = {
            kind: sum(r['kind'] == kind and r['actual_compared'] == '1' for r in replay)
            for kind in ('ACTUAL', 'SHADOW', 'SELFTEST')
        }
        snapshots = require_export(directory, result, '_snapshots.csv')
        summary['service_by_symbol'] = {
            symbol: {
                kind: dict(callbacks=sum(r['symbol'] == symbol and r['kind'] == kind for r in callbacks),
                           operations=sum(int(r['operations']) for r in callbacks
                                          if r['symbol'] == symbol and r['kind'] == kind),
                           first_service_wait_ms=batch.percentiles(
                               (min(int(r['start_wall_us']) for r in callbacks
                                    if r['symbol'] == symbol and r['kind'] == kind and r['cycle'] == s['cycle'])
                                - int(s['start_wall_us'])) / 1000
                               for s in snapshots if s['symbol'] == symbol and s['kind'] == kind
                               and any(r['symbol'] == symbol and r['kind'] == kind and r['cycle'] == s['cycle']
                                       for r in callbacks)),
                           service_gap_ms=batch.percentiles(int(r['service_gap_us']) / 1000 for r in callbacks
                               if r['symbol'] == symbol and r['kind'] == kind and r['service_gap_known'] == '1'))
                for kind in ('ACTUAL', 'SHADOW')
            } for symbol in result['symbols']
        }
        summary['callbacks_ms'] = {
            kind: batch.percentiles(int(r['elapsed_us']) / 1000 for r in callbacks if r['kind'] == kind)
            for kind in ('ACTUAL', 'SHADOW')
        }
        summary['tick_counters'] = result['pipeline']
        summary['numeric_mismatches'] = result['scheduler']['mismatch']
        summary['shadow_overlap_s'] = result['shadow_overlap_s']
        summary['natural_shadow_overlap'] = result['natural_shadow_overlap']
        cases.append(summary)
    pairs = []
    complete = [c for c in cases if c['status'] == 'PASS']
    for n in (2, 3, 4):
        for mode in (0, 2):
            runs = [c for c in complete if c['count'] == n and c['mode'] == mode]
            if len(runs) != 2:
                continue
            normal = next(c for c in runs if c['load'] == 'NORMAL')
            loaded = next(c for c in runs if c['load'] == 'CPU_CONTENTION')
            pairs.append(dict(count=n, mode=mode, comparison='LOAD',
                              ticks_equal=normal['chart_processed_ticks'] == loaded['chart_processed_ticks'],
                              bars_equal=normal['symbol_bar_process_total'] == loaded['symbol_bar_process_total'],
                              funnel_equal=all(normal['symbols'][s]['funnel'] == loaded['symbols'][s]['funnel']
                                               for s in normal['symbols']),
                              trades_equal=normal['trades'] == loaded['trades']))
    numeric = []
    for n in (2, 3, 4):
        for load in ('NORMAL', 'CPU_CONTENTION'):
            runs = [c for c in complete if c['count'] == n and c['load'] == load]
            if len(runs) != 2:
                continue
            reference = next(c for c in runs if c['mode'] == 0)
            candidate = next(c for c in runs if c['mode'] == 2)
            for symbol in reference['symbols']:
                a = next(r for r in reference['shadow_results'] if r['symbol'] == symbol)
                b = next(r for r in candidate['shadow_results'] if r['symbol'] == symbol)
                fields = ('operations', 'risk_bits', 'allowed', 'rng', 'candidate', 'input_digest')
                numeric.append(dict(count=n, load=load, symbol=symbol,
                                    equal=all(a[k] == b[k] for k in fields)))
    payload = dict(build=6230, completed=len(complete), total=12, cases=cases, load_comparisons=pairs,
                   native_shadow_equivalence=numeric)
    encoded = json.dumps(payload, indent=2, ensure_ascii=True) + '\n'
    batch.PrivacyGuard().check(encoded)
    (ROOT / 'summary.json').write_text(encoded, encoding='utf-8')
    print(json.dumps(dict(completed=len(complete), total=12, load_comparisons=pairs)))


if __name__ == '__main__':
    summarize()
