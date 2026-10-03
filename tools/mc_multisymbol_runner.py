"""Frozen test-only multi-symbol matrix; no native execution on import."""
import hashlib
from collections import Counter, defaultdict
import csv
import io
import json
from pathlib import Path
import re
import shutil
import argparse
import os
import subprocess
import sys
import time

try:
    from . import mc500k_batch as batch
except ImportError:
    import mc500k_batch as batch
try:
    from . import mc500k_stress as stress
except ImportError:
    import mc500k_stress as stress

CASE_SYMBOLS = {
    2: ('USDJPY', 'EURUSD'),
    3: ('USDJPY', 'EURUSD', 'EURJPY'),
    4: ('USDJPY', 'EURUSD', 'EURJPY', 'XAUUSD'),
}
MODES = (0, 2)
LOADS = ('NORMAL', 'CPU_CONTENTION')
MARKET_WINDOWS = {
    'SEPTEMBER_BASELINE': ('2026.09.14', '2026.09.19'),
    'JUNE_NATURAL': ('2026.06.01', '2026.06.13'),
}


def build_cases():
    return [dict(count=n, symbols=symbols, mode=mode, load=load)
            for n, symbols in CASE_SYMBOLS.items() for mode in MODES for load in LOADS]


def selection_copy(original: str, symbols: tuple[str, ...]) -> str:
    """Alter only the Tester copy's universe selection; preserve all other lines."""
    if symbols not in CASE_SYMBOLS.values():
        raise ValueError('unsupported or duplicate symbol group')
    lines = original.splitlines(keepends=True)
    fields = [line.partition('=')[0] for line in lines if '=' in line]
    if fields.count('ScanMode') != 1 or fields.count('CustomSymbols') != 1:
        raise ValueError('missing/duplicate selection field')
    result = []
    for line in lines:
        key, sep, value = line.partition('=')
        ending = '\r\n' if line.endswith('\r\n') else '\n' if line.endswith('\n') else ''
        if key == 'ScanMode':
            if not value.removesuffix(ending).startswith('0||'):
                raise ValueError('unexpected original ScanMode')
            rest = value.removesuffix(ending).split('||', 1)[1]
            line = 'ScanMode=2||' + rest + ending
        elif key == 'CustomSymbols':
            if value.removesuffix(ending):
                raise ValueError('original CustomSymbols nonempty')
            line = 'CustomSymbols=' + ','.join(symbols) + ending
        result.append(line)
    return ''.join(result)


def frozen_config(original: str, expert: str, parameters: str, report: str,
                  *, market_window: str = 'SEPTEMBER_BASELINE') -> str:
    """Allow only three destination names; retain the reference market contract."""
    old = batch.tester_config(original, expert, report)
    values = dict(line.split('=', 1) for line in old.splitlines() if '=' in line)
    if (market_window not in MARKET_WINDOWS or values['Symbol'] != 'USDJPY' or
        (values['FromDate'], values['ToDate']) != MARKET_WINDOWS[market_window]):
        raise ValueError('reference market period differs')
    if '\\' in parameters or '/' in parameters or parameters in ('', '.', '..'):
        raise ValueError('unsafe Tester parameters name')
    lines = old.splitlines()
    lines = ['ExpertParameters=' + parameters if line.startswith('ExpertParameters=') else line for line in lines]
    if sum(line.startswith('ExpertParameters=') for line in lines) != 1:
        raise ValueError('parameters field missing')
    return '\n'.join(lines) + '\n'


def expected_export_prefix(case: dict) -> str:
    """Bind actual export dates to the hash-verified, explicitly frozen window."""
    path = Path(case['config'])
    if sha256(path) != case['config_sha256']:
        raise ValueError('Tester config changed')
    window = case.get('market_window', 'SEPTEMBER_BASELINE')
    text = path.read_text(encoding='utf-8')
    frozen_config(text, 'validated\\EA.ex5', 'validated.set', 'validated', market_window=window)
    if case['mode'] not in MODES:
        raise ValueError('unsupported scheduler mode')
    return f"CodexMCV{case['mode']}_20260927_USDJPY_{MARKET_WINDOWS[window][0]}_A2.60_S0.40"


def validate_case_contract(case: dict) -> None:
    """Reject metadata drift before any launch, affinity work or result reuse."""
    window = case.get('market_window', 'SEPTEMBER_BASELINE')
    count = case['count']
    if (window not in MARKET_WINDOWS or count not in CASE_SYMBOLS or
        tuple(case['symbols']) != CASE_SYMBOLS[count] or case['mode'] not in MODES or
        case['load'] not in LOADS):
        raise ValueError('unsupported frozen case contract')
    if window == 'JUNE_NATURAL' and (count not in (3, 4) or case['load'] != 'NORMAL'):
        raise ValueError('June diagnostic permits only N3/N4 NORMAL')


def validate_case_evidence(evidence: dict, symbols: tuple[str, ...]) -> None:
    """A partial/unqualified observation is not a passed multi-symbol case."""
    if set(evidence['symbols']) != set(symbols):
        raise ValueError('missing or extra symbol evidence')
    if evidence['simultaneous_shadow_active'] < 2:
        raise ValueError('shadow jobs did not overlap')
    if evidence['queue_depth'] != 'UNKNOWN':
        raise ValueError('unobservable queue depth must remain unknown')
    if evidence['runtime_errors'] or evidence['numerical_mismatches']:
        raise ValueError('runtime or numerical failure')
    if any(row['shadow_callbacks'] < 1 or row['quote_samples'] < 1 for row in evidence['symbols'].values()):
        raise ValueError('symbol observation missing')


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_matrix(original_set: Path, original_config: str, bundles: dict,
                   native_root: Path, evidence_root: Path, expected_set_sha256: str | None = None,
                   namespace: str = 'CodexMCMulti20260928', engine_sha256: dict | None = None,
                   counts: tuple = (2, 3, 4), loads: tuple = LOADS,
                   market_window: str = 'SEPTEMBER_BASELINE') -> list[dict]:
    """Stage only Tester artifacts; freeze hashes for every subsequent native run."""
    original_set, native_root, evidence_root = map(Path, (original_set, native_root, evidence_root))
    if not re.fullmatch(r'CodexMCMulti[A-Za-z0-9_]+', namespace):
        raise ValueError('unsafe matrix namespace')
    if not counts or len(set(counts)) != len(counts) or not set(counts).issubset(CASE_SYMBOLS):
        raise ValueError('unsupported matrix symbol counts')
    if not loads or len(set(loads)) != len(loads) or not set(loads).issubset(LOADS):
        raise ValueError('unsupported matrix loads')
    if market_window == 'JUNE_NATURAL' and (counts != (3, 4) or loads != ('NORMAL',)):
        raise ValueError('June diagnostic is bounded to four NORMAL conditions')
    frozen_config(original_config, 'validated\\EA.ex5', 'validated.set', 'validated', market_window=market_window)
    engine_sha256 = dict(engine_sha256 or {})
    verify_engine({'engine_sha256': engine_sha256})
    digest = sha256(original_set)
    if expected_set_sha256 is not None and digest != expected_set_sha256:
        raise ValueError('original set hash changed')
    raw = original_set.read_bytes()
    if not raw.startswith(b'\xff\xfe'):
        raise ValueError('expected original UTF-16LE Tester set')
    original = raw.decode('utf-16')
    if set(bundles) != {0, 2}:
        raise ValueError('current/fixed500k bundles required')
    if evidence_root.exists():
        raise ValueError('evidence destination already exists')
    source_maps = {}
    expert_names = {}
    for mode, bundle in bundles.items():
        bundle = Path(bundle)
        mains = [p for p in bundle.glob('*.mq5') if (bundle / (p.stem + '.ex5')).is_file()]
        if len(mains) != 1:
            raise ValueError('compiled Tester bundle missing or ambiguous')
        source_maps[mode] = {p.name: sha256(p) for p in bundle.iterdir() if p.suffix in ('.mq5', '.mqh')}
        expert_names[mode] = mains[0].stem + '.ex5'
        header = bundle / 'TesterMCSchedulerDiag.mqh'
        if header.is_file() and f'#define MCS_MODE {mode}' not in header.read_text(encoding='utf-8-sig'):
            raise ValueError('bundle mode does not match case')
    manifest = []
    for case in build_cases():
        if case['count'] not in counts or case['load'] not in loads:
            continue
        count, mode, load, symbols = (case[k] for k in ('count', 'mode', 'load', 'symbols'))
        stem = f'{namespace}_N{count}_M{mode}_{load}'
        folder = f'{namespace}_M{mode}'
        expert = folder + '\\' + expert_names[mode]
        staged_set = native_root / 'Profiles' / 'Tester' / (stem + '.set')
        config = native_root / 'Profiles' / 'Tester' / (stem + '.ini')
        report = native_root.parent / (stem + '.htm')
        if staged_set.exists() or config.exists() or report.exists():
            raise ValueError('Tester destination exists; refusing overwrite')
        selected = selection_copy(original, symbols)
        prepared = frozen_config(original_config, expert, staged_set.name, stem, market_window=market_window)
        manifest.append(dict(case=stem, count=count, mode=mode, load=load, symbols=list(symbols),
                             expert=expert, config=str(config), report=str(report), set_path=str(staged_set),
                             original_set_sha256=digest, selected_set_sha256=hashlib.sha256(selected.encode('utf-16')).hexdigest(),
                             source_sha256=source_maps[mode], binary_sha256=sha256(Path(bundles[mode]) / expert_names[mode]),
                             config_sha256=hashlib.sha256(prepared.encode('utf-8')).hexdigest(),
                             engine_sha256=engine_sha256, market_window=market_window))
    # All destinations were checked before the first write. These remain local
    # Tester copies; no product source, original set, or repository config changes.
    for mode, bundle in bundles.items():
        destination = native_root / 'Experts' / f'{namespace}_M{mode}'
        if destination.exists():
            raise ValueError('Tester Expert bundle destination exists')
        shutil.copytree(bundle, destination)
    (native_root / 'Profiles' / 'Tester').mkdir(parents=True, exist_ok=True)
    for entry in manifest:
        selected = selection_copy(original, tuple(entry['symbols']))
        Path(entry['set_path']).write_bytes(selected.encode('utf-16'))
        Path(entry['config']).write_bytes(
            frozen_config(original_config, entry['expert'], Path(entry['set_path']).name, entry['case'],
                          market_window=market_window).encode('utf-8'))
    evidence_root.mkdir(parents=True)
    (evidence_root / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
    return manifest


def verify_engine(case: dict) -> None:
    for name, expected in case.get('engine_sha256', {}).items():
        if sha256(Path(name)) != expected:
            raise ValueError('frozen MT5 engine changed')


def validate_result_binding(result: dict, case: dict) -> None:
    if result.get('status') != 'PASS' or any(result.get(k) != case[k]
                                           for k in ('case', 'mode', 'load', 'symbols')):
        raise ValueError('result does not match frozen case identity')
    if result.get('market_window', 'SEPTEMBER_BASELINE') != case.get('market_window', 'SEPTEMBER_BASELINE'):
        raise ValueError('result market window differs')


def verify_staged(case: dict) -> None:
    validate_case_contract(case)
    verify_engine(case)
    if sha256(Path(case['config'])) != case['config_sha256']:
        raise ValueError('Tester config changed')
    expected_export_prefix(case)
    if sha256(Path(case['set_path'])) != case['selected_set_sha256']:
        raise ValueError('Tester set changed')
    bundle = batch.ROOT / 'MQL5' / 'Experts' / case['expert'].split('\\', 1)[0]
    binary = bundle / case['expert'].split('\\', 1)[1]
    if sha256(binary) != case['binary_sha256']:
        raise ValueError('Tester binary changed')
    for name, expected in case['source_sha256'].items():
        if sha256(bundle / name) != expected:
            raise ValueError('Tester source changed')


def save_affinity_evidence(destination: Path, monitor, primary_error=None) -> None:
    try:
        evidence = monitor.evidence() if monitor is not None else dict(
            status='UNKNOWN', reason='startup failed before monitor available', mask='UNKNOWN')
        batch.dump(destination / 'affinity.json', evidence)
    except Exception as error:
        if primary_error is None:
            raise
        primary_error.add_note('affinity evidence save failed: ' + type(error).__name__)


def run_native_case(case: dict, evidence_root: Path, cpu: int = 0,
                    timeout: int = 1800) -> dict:
    """Launch a single owned Tester; stdout/journal contents never enter output."""
    verify_staged(case)
    if timeout <= 0 or timeout > stress.MAX_SECONDS or not 0 <= cpu < 64:
        raise ValueError('invalid bounded native run')
    api = stress.WindowsProcesses()
    if api.snapshot():
        raise ValueError('unowned terminal or tester process present')
    destination = Path(evidence_root) / case['case']
    destination.mkdir(parents=True, exist_ok=False)
    offsets = {str(p): p.stat().st_size for p in batch.LOGROOT.glob('*.log')}
    start = time.time()
    monotonic = time.monotonic()
    attempt = dict(case=case['case'], mode=case['mode'], load=case['load'], started=start,
                   offsets=offsets, status='RUNNING', timeout_seconds=timeout)
    batch.dump(destination / 'attempt.json', attempt)
    monitor = None
    worker = None
    primary_error = None
    try:
        with stress.OwnedChildren() as owned:
            terminal = owned.add(subprocess.Popen(
                [str(batch.TERMINAL), '/profile:' + batch.PROFILE, '/config:' + case['config']],
                startupinfo=stress.hidden_startup(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
            if case['load'] == 'CPU_CONTENTION':
                root = api.read(terminal.pid)
                if stress.image_key(root.image) != stress.image_key(str(batch.TERMINAL)):
                    raise ValueError('terminal image mismatch')
                monitor = stress.AffinityMonitor(api, root, cpu, monotonic)
                runner = api.read(os.getpid())
                worker = owned.add(subprocess.Popen(
                    [sys.executable, str(Path(stress.__file__).resolve()), '--busy-worker', str(cpu), str(timeout),
                     str(os.getpid()), str(runner.born)], startupinfo=stress.hidden_startup(),
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
                worker_identity = api.read(worker.pid)
                if stress.image_key(worker_identity.image) != stress.image_key(sys.executable):
                    raise ValueError('worker image mismatch')
                monitor.observe(worker_identity, 'owned_contention_worker', pin=True)
            while terminal.poll() is None:
                if time.monotonic() - monotonic > timeout:
                    raise TimeoutError('owned Tester timeout')
                if monitor is not None:
                    if worker.poll() is not None:
                        raise RuntimeError('contention worker exited')
                    monitor.observe(api.read(worker.pid), 'owned_contention_worker')
                    monitor.sample()
                time.sleep(stress.POLL_SECONDS)
            exit_code = terminal.wait(timeout=1)
            if monitor is not None:
                monitor.sample()
                if monitor.evidence()['status'] != 'PASS':
                    raise ValueError('contention attribution incomplete')
    except BaseException as error:
        primary_error = error
        raise
    finally:
        if case['load'] == 'CPU_CONTENTION':
            save_affinity_evidence(destination, monitor, primary_error)
    attempt.update(status='COLLECTABLE', exit_code=exit_code, elapsed_seconds=time.monotonic() - monotonic)
    batch.dump(destination / 'attempt.json', attempt)
    return attempt


def strict_diagnostic_row(row: dict, expected_symbol: str | None = None) -> None:
    if expected_symbol is not None and row.get('symbol') != expected_symbol:
        raise ValueError('symbol-qualified row mismatch')
    if any(value is None for value in row.values()):
        raise ValueError('incomplete diagnostic row')


def validate_replay_rows(replay: list[dict], expected_count: int) -> int:
    """Require exact 20k/500k pairs for each symbol/kind/cycle snapshot."""
    if len(replay) != expected_count or len(replay) % 2:
        raise ValueError('replay row coverage mismatch')
    pairs = defaultdict(dict)
    for row in replay:
        if (row['equal_reference'] != '1' or row['actual_equal'] != '1' or row['sequence_exact'] != '1' or
            row['sequence_errors'] != '0' or row['sequence_draws'] != row['operations'] or
            row['mode'] not in ('0', '2')):
            raise ValueError('numeric replay mismatch')
        key = (row['symbol'], row['kind'], row['cycle'])
        if row['mode'] in pairs[key]:
            raise ValueError('duplicate replay mode')
        pairs[key][row['mode']] = row
    if any(set(pair) != {'0', '2'} for pair in pairs.values()):
        raise ValueError('incomplete replay pair')
    exact = ('samples', 'input_digest', 'operations', 'risk_bits', 'allowed', 'rng', 'candidate')
    if any(any(pair['0'][field] != pair['2'][field] for field in exact) for pair in pairs.values()):
        raise ValueError('20k/500k result differs')
    return sum(int(row['actual_compared']) for row in replay)


def collect_native_case(case: dict, evidence_root: Path) -> dict:
    """Read fresh native evidence in RAM, exporting only allowlisted CSVs/aggregates."""
    verify_staged(case)
    destination = Path(evidence_root) / case['case']
    attempt = json.loads((destination / 'attempt.json').read_text(encoding='utf-8'))
    if attempt['status'] != 'COLLECTABLE' or attempt['exit_code'] != 0 or attempt['case'] != case['case']:
        raise ValueError('Tester did not complete normally')
    privacy = batch.PrivacyGuard()
    journal = ''
    for file in batch.LOGROOT.glob('*.log'):
        with file.open('rb') as stream:
            stream.seek(attempt['offsets'].get(str(file), 2))
            journal += stream.read().decode('utf-16-le')
    if case['expert'].replace('\\', '\\') not in journal or 'Test passed in' not in journal:
        raise ValueError('fresh completed native Tester journal absent')
    wanted = ('TESTER_PIPELINE_SUMMARY', 'TESTER_MC_MULTI', 'TESTER_MC_SCHEDULER',
              'TESTER_MC_VALIDATION', 'TESTER_BOTTLENECK_SUMMARY',
              'TESTER_MC_TIMELINE_EXPORT', 'TESTER_BOTTLENECK_EXPORT')
    markers = {}
    for name in wanted:
        found = [line[line.index(name + ' '):].strip() for line in journal.splitlines() if name + ' ' in line]
        if len(found) != 1:
            raise ValueError('missing/duplicate fresh diagnostic marker ' + name)
        privacy.check(found[0])
        if not re.match(r'^' + name + r' (?:PASS|FAIL|UNKNOWN|OK|[a-z_]+=)', found[0]):
            raise ValueError('malformed diagnostic marker')
        if found[0].startswith(name + ' FAIL') or found[0].startswith(name + ' UNKNOWN'):
            raise ValueError('native diagnostic did not pass')
        markers[name] = batch.fields(found[0])
    pipeline = markers['TESTER_PIPELINE_SUMMARY']
    multi = markers['TESTER_MC_MULTI']
    mc = markers['TESTER_MC_SCHEDULER']
    validation = markers['TESTER_MC_VALIDATION']
    if (int(pipeline['deinit_reason']) != 1 or int(multi['symbols']) != case['count'] or
        int(multi['shadow_completed']) != case['count'] or int(multi['unknown']) or
        int(multi['replay_mismatch']) or int(mc['mode']) != case['mode'] or
        int(mc['mismatch']) or int(mc['unknown']) or int(validation['unknown'])):
        raise ValueError('native diagnostic counters inconsistent')
    prefix = mc['prefix']
    if prefix != expected_export_prefix(case):
        raise ValueError('case prefix/inputs mismatch')
    bundle = batch.ROOT / 'MQL5' / 'Experts' / case['expert'].split('\\')[0]
    schemas, _, suffixes = batch.schema_contract(bundle)
    filenames = {prefix + suffix + '.csv' for suffix in suffixes}
    filenames.update((markers['TESTER_MC_TIMELINE_EXPORT']['file'],
                      markers['TESTER_BOTTLENECK_EXPORT']['file']))
    if any(Path(name).name != name for name in filenames):
        raise ValueError('unsafe export filename')
    exports = {}
    for name in sorted(filenames):
        file = batch.COMMON / name
        if not file.is_file() or file.stat().st_mtime < attempt['started'] - 1:
            raise ValueError('missing/stale native export')
        raw = file.read_text(encoding='ascii')
        privacy.check(raw)
        reader = csv.reader(io.StringIO(raw))
        header = tuple(next(reader, ()))
        if header not in schemas:
            raise ValueError('unknown diagnostic CSV schema')
        exports[name] = batch.strict_rows(raw)
    def rows(suffix):
        name = prefix + suffix + '.csv'
        if name not in exports:
            raise ValueError('required CSV absent')
        return exports[name]
    summaries = rows('_multi_summary')
    callbacks = rows('_callbacks')
    snapshots = rows('_snapshots')
    replay = rows('_replay')
    if len(summaries) != case['count'] or {r['symbol'] for r in summaries} != set(case['symbols']):
        raise ValueError('symbol summary coverage mismatch')
    symbol_rows = {}
    for row in summaries:
        symbol = row['symbol']
        strict_diagnostic_row(row, symbol)
        if (row['kind'] != 'SHADOW' or row['completed'] != '1' or row['status'] != 'PASS' or
            int(row['operations']) <= 0 or int(row['callbacks']) <= 0 or
            int(row['quote_samples']) <= 0 or row['input_arrivals'] != 'UNKNOWN' or
            row['queue_depth'] != 'UNKNOWN' or row['broker_latency'] != 'UNKNOWN'):
            raise ValueError('shadow symbol/unknown evidence incomplete')
        actual_callbacks = [r for r in callbacks if r['symbol'] == symbol and r['kind'] == 'SHADOW']
        if len(actual_callbacks) != int(row['callbacks']):
            raise ValueError('symbol callback count mismatch')
        snap = [r for r in snapshots if r['symbol'] == symbol and r['kind'] == 'SHADOW' and r['cycle'] == '1']
        if len(snap) != 1 or snap[0]['completed'] != '1' or snap[0]['operations'] != row['operations']:
            raise ValueError('shadow snapshot mismatch')
        symbol_rows[symbol] = dict(shadow_callbacks=len(actual_callbacks), quote_samples=int(row['quote_samples']),
                                   quote_advances=int(row['quote_advances']), bar_samples=int(row['bar_samples']),
                                   operations=int(row['operations']), duration_us=int(row['duration_us']))
    actual_replay_rows = validate_replay_rows(replay, int(mc['comparisons']))
    errors = sum(any(term in line.lower() for term in ('array out of range','zero divide','critical runtime error',
                   'initialization failed','cannot load expert')) for line in journal.splitlines())
    warnings = sum(bool(re.search(r'\bwarning\b', line, re.I)) for line in journal.splitlines())
    if errors or warnings:
        raise ValueError('runtime error or warning')
    report = Path(case['report'])
    if not report.is_file() or report.stat().st_mtime < attempt['started'] - 1:
        raise ValueError('fresh native report absent')
    report_metrics = batch.report_metrics(report)
    if report_metrics['history_quality'] != 100:
        raise ValueError('history quality degraded')
    evidence = dict(symbols=symbol_rows, simultaneous_shadow_active=case['count'],
                    queue_depth='UNKNOWN', runtime_errors=errors, numerical_mismatches=0)
    validate_case_evidence(evidence, tuple(case['symbols']))
    for name in exports:
        shutil.copyfile(batch.COMMON / name, destination / name)
    result = dict(status='PASS', case=case['case'], mode=case['mode'], load=case['load'],
                  market_window=case.get('market_window', 'SEPTEMBER_BASELINE'),
                  symbols=case['symbols'], deinit_reason=int(pipeline['deinit_reason']),
                  shadow_overlap_s=float(multi['shadow_overlap_s']),
                  natural_shadow_overlap=multi['natural_shadow_overlap'],
                  report_metrics=report_metrics, symbol_rows=symbol_rows,
                  replay_rows=len(replay), actual_replay_rows=actual_replay_rows,
                  runtime_errors=errors, warnings=warnings, scheduler=mc, validation=validation,
                  pipeline=pipeline, exports={name: sha256(destination / name) for name in exports})
    privacy.check(json.dumps(result, ensure_ascii=True))
    batch.dump(destination / 'result.json', result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-case')
    parser.add_argument('--collect-case')
    parser.add_argument('--run-matrix', action='store_true')
    parser.add_argument('--max-new', type=int, default=12)
    parser.add_argument('--cpu', type=int, default=0)
    parser.add_argument('--manifest', type=Path, default=Path(__file__).resolve().parents[1] /
                        'verification/mc_multisymbol_20260928/matrix/manifest.json')
    parser.add_argument('--evidence-root', type=Path, default=Path(__file__).resolve().parents[1] /
                        'verification/mc_multisymbol_20260928/native')
    args = parser.parse_args()
    if sum(bool(x) for x in (args.run_case, args.collect_case, args.run_matrix)) != 1:
        parser.error('specify exactly one native action')
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    root = args.evidence_root
    for case in manifest:
        validate_case_contract(case)
        verify_engine(case)
    if args.run_matrix:
        if not 1 <= args.max_new <= 12:
            raise ValueError('invalid matrix bound')
        newly_run = 0
        for case in manifest:
            out = root / case['case']
            if (out / 'result.json').is_file():
                result = json.loads((out / 'result.json').read_text(encoding='utf-8'))
                validate_result_binding(result, case)
                if any(sha256(out / name) != digest for name, digest in result['exports'].items()):
                    raise ValueError('prior case evidence changed')
                continue
            if not (out / 'attempt.json').is_file():
                if newly_run >= args.max_new:
                    break
                try:
                    with batch.RunnerLock():
                        run_native_case(case, root, args.cpu)
                except Exception as error:
                    if (out / 'attempt.json').is_file():
                        failed = json.loads((out / 'attempt.json').read_text(encoding='utf-8'))
                        failed['status'] = 'BLOCKED'
                        failed['failure_type'] = type(error).__name__
                        batch.dump(out / 'attempt.json', failed)
                    raise
                newly_run += 1
            result = collect_native_case(case, root)
            print(json.dumps(dict(case=result['case'], mode=result['mode'], load=result['load'],
                                  status=result['status'], runtime_errors=result['runtime_errors'],
                                  replay_rows=result['replay_rows'])), flush=True)
        print(json.dumps(dict(matrix_new_runs=newly_run, completed=sum(
            (root / c['case'] / 'result.json').is_file() for c in manifest), total=len(manifest))), flush=True)
        return
    matching = [c for c in manifest if c['case'] == (args.run_case or args.collect_case)]
    if len(matching) != 1:
        raise ValueError('case not present in frozen manifest')
    if args.run_case:
        with batch.RunnerLock():
            attempt = run_native_case(matching[0], root, args.cpu)
        print(json.dumps({k: attempt[k] for k in ('case', 'load', 'mode', 'exit_code', 'elapsed_seconds', 'status')}))
    else:
        result = collect_native_case(matching[0], root)
        print(json.dumps({k: result[k] for k in ('case', 'mode', 'load', 'status', 'replay_rows', 'runtime_errors', 'warnings')}))


if __name__ == '__main__':
    main()
