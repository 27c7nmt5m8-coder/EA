"""Opt-in Tester-only comparison with query-only affinity observation.

Separate test profile/namespace, no pinning/priority/OS changes. CPU workers
inherit all scheduling settings and stop cooperatively. A polluted observation
is excluded, never repaired by changing the environment.
"""
import argparse
import csv
import json
import math
import os
import re
from pathlib import Path
import subprocess
import sys
import time

from tools import mc500k_batch as batch
from tools import mc_multisymbol_runner as matrix
from tools.mc_affinity_observer import WindowsReadOnly, Observer, POLL_SECONDS, overhead_status, NATIVE_NAMES, known_placement
from tools.build_tester_journal_io import build

WORKERS = 6  # 6 independent busy processes on observed 8 logical CPUs; no CPU pin.
MAX_SECONDS = 1800
PROFILE = 'CodexTesterAffinity_20261004'
SAFE_FAILURE_CODES = frozenset({
    'OBSERVER_OVERHEAD_TOO_HIGH', 'UNKNOWN',
    'NEEDS_USER_ACTION: pre-existing native/update process',
    'NEEDS_USER_ACTION: native/update process exists before launch',
    'NEEDS_USER_ACTION: Tester still running at bounded deadline',
    'ISOLATION_NOT_ESTABLISHED: startup observation contaminated',
    'ISOLATION_NOT_ESTABLISHED: contaminated/changed/unknown observation',
    'owned worker ended prematurely', 'terminal identity/owner mismatch',
    'launched terminal already absent', 'worker creation not observed',
    'worker ownership not proven', 'dedicated profile changed immediately before launch',
    'frozen dedicated profile changed', 'case/evidence manifest mismatch',
    'CLI/evidence manifests differ', 'frozen case absent/ambiguous',
    'observer overhead/collection prevents comparison',
    'NORMAL frozen manifest required', 'NORMAL identity not in frozen manifest',
    'NORMAL observer-only pair must pass before CPU load',
    'NORMAL export changed', 'NORMAL population proof changed',
    'timer population absent/ambiguous', 'timer population incomplete',
    'timer population contradiction', 'PRIVATE_METADATA_REJECTED',
    'comparison placement differs', 'comparison placement unknown',
    'worker readiness not proven', 'worker readiness timeout', 'NORMAL attempt binding changed',
})


def safe_error_code(error):
    # A parser ValueError can include its input, even with a benign type/name.
    # Only authored, exact failure codes may leave this process.
    message = str(error)
    return message if message in SAFE_FAILURE_CODES else 'UNCLASSIFIED'


def timer_population(events, summaries):
    rows = [r for r in events if r.get('event') == 'OnTimer']
    overall = [r for r in summaries if r.get('stage') == 'OnTimer']
    if len(rows) != 1 or len(overall) != 1:
        raise ValueError('timer population absent/ambiguous')
    try:
        row = {k: float(rows[0][k]) for k in ('count','total_us','median_us','p95_us','p99_us','max_us')}
        expected = {k: int(overall[0][k]) for k in ('count','total_us','max_us','unknown')}
    except (ValueError, KeyError, TypeError):
        raise ValueError('timer population incomplete') from None
    if (any(not math.isfinite(v) or v < 0 for v in row.values()) or row['count'] <= 0 or
        row['count'] != int(row['count']) or expected['unknown'] or
        any(row[k] != expected[k] for k in ('count','total_us','max_us')) or
        not row['median_us'] <= row['p95_us'] <= row['p99_us'] <= row['max_us']):
        raise ValueError('timer population contradiction')
    return dict(row, count=int(row['count']), source='ALL_CALLBACKS', event_arrival_delay='UNKNOWN')


def placement_signature(observed):
    signature = {}
    workers = []
    for row in observed.get('processes',[]):
        role = row['role']
        if role == 'owned_descendant' and row['name'].lower() != 'metatester64.exe':
            continue
        if role not in ('controller','owned_terminal','owned_descendant','owned_load_generator'):
            continue
        first,last = row.get('initial_placement'),row.get('final_placement')
        if not isinstance(first,dict) or first != last:
            raise ValueError('comparison placement unknown')
        if not known_placement(first):
            raise ValueError('comparison placement unknown')
        if role == 'owned_load_generator':
            workers.append(first)
        elif role in signature:
            raise ValueError('comparison placement unknown')
        else:
            signature[role]=first
    if set(signature) != {'controller','owned_terminal','owned_descendant'}:
        raise ValueError('comparison placement unknown')
    if any(w != signature['controller'] for w in workers):
        raise ValueError('comparison placement differs')
    return signature


def require_matching_placement(left,right):
    if left != right:
        raise ValueError('comparison placement differs')


def read_worker_ready(path,pid,born,owner_pid,owner_born):
    row=json.loads(Path(path).read_text(encoding='utf-8'))
    if (any(row.get(k)!=v for k,v in dict(pid=pid,born=born,owner_pid=owner_pid,owner_born=owner_born).items()) or
        type(row.get('operations')) is not int or row['operations']<=0 or
        not isinstance(row.get('cpu_seconds'),(int,float)) or not math.isfinite(row['cpu_seconds']) or row['cpu_seconds']<=0):
        raise ValueError('worker readiness not proven')
    return row


def require_normal_pair(evidence, count):
    manifest_path = Path(evidence).parent / 'matrix' / 'manifest.json'
    if not manifest_path.is_file():
        raise ValueError('NORMAL frozen manifest required')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    selected = []
    for folder in Path(evidence).glob(f'*_N{count}_M*_NORMAL'):
        if not (folder / 'observation.json').is_file() or not (folder / 'result.json').is_file():
            continue
        observed = json.loads((folder / 'observation.json').read_text(encoding='utf-8'))
        result = json.loads((folder / 'result.json').read_text(encoding='utf-8'))
        attempt = json.loads((folder / 'attempt.json').read_text(encoding='utf-8'))
        population_path = folder / 'timer_population.json'
        if not population_path.is_file():
            continue
        expected = [c for c in manifest if c['case'] == folder.name and c['count'] == count and c['load'] == 'NORMAL']
        if len(expected) != 1:
            raise ValueError('NORMAL identity not in frozen manifest')
        matrix.verify_staged(expected[0])
        matrix.validate_result_binding(result, expected[0])
        for name,digest in result['exports'].items():
            if matrix.sha256(folder / name) != digest:
                raise ValueError('NORMAL export changed')
        prefix = result['scheduler']['prefix']
        def read_rows(suffix):
            with (folder / (prefix + suffix + '.csv')).open(encoding='ascii',newline='') as f:
                return list(csv.DictReader(f))
        if json.loads(population_path.read_text(encoding='utf-8')) != timer_population(read_rows('_events'),read_rows('_timer_summary')):
            raise ValueError('NORMAL population proof changed')
        if (observed.get('comparison_eligible') and observed.get('overhead_status') == 'ACCEPTABLE' and
                result.get('status') == 'PASS' and result.get('load') == 'NORMAL' and
                attempt.get('diagnostic_tool_sha256') == tooling_hashes()):
            if (attempt.get('case') != expected[0]['case'] or attempt.get('mode') != result['mode'] or
                attempt.get('load') != 'NORMAL' or attempt.get('status') != 'COLLECTABLE' or
                attempt.get('exit_code') != 0 or attempt.get('profile_sha256') != expected[0]['profile_sha256']):
                raise ValueError('NORMAL attempt binding changed')
            selected.append((result['mode'],placement_signature(observed)))
    if sorted(m for m,_ in selected) != [0, 2]:
        raise ValueError('NORMAL observer-only pair must pass before CPU load')
    require_matching_placement(selected[0][1],selected[1][1])
    return selected[0][1]


def tooling_hashes():
    return {name:matrix.sha256(Path(__file__).with_name(name)) for name in ('mc_affinity_observer.py','mc_isolated_contention.py')}


def safe_summary(summary, privacy):
    try:
        privacy.check(json.dumps(summary))
        return summary
    except batch.BatchFailure:
        return dict(comparison_eligible=False,status='BLOCKED',reason='PRIVATE_METADATA_REJECTED')


def stop_workers(workers, stop):
    Path(stop).touch(exist_ok=False)
    status, reason = 'PASS', None
    for worker in workers:
        try:
            if worker.wait(timeout=5) != 0 and status != 'NEEDS_USER_ACTION':
                status, reason = 'BLOCKED', 'owned worker failed during cooperative shutdown'
        except subprocess.TimeoutExpired:
            status, reason = 'NEEDS_USER_ACTION', 'owned worker cooperative shutdown incomplete'
    return status, reason


def profile_state(profile):
    profile = Path(profile)
    charts = list(profile.glob('*.chr'))
    if len(charts) != 4 or any(re.search(r'<\s*expert\b',batch.read_text(p),re.I) for p in charts):
        raise ValueError('NEEDS_USER_ACTION: dedicated profile is not EA-free')
    paths = [p for p in profile.iterdir() if p.is_file()]
    if any(p.name not in {'chart01.chr','chart02.chr','chart03.chr','chart04.chr','order.wnd'} for p in paths):
        raise ValueError('dedicated profile contains unknown files')
    return {p.name:matrix.sha256(p) for p in sorted(paths)}


def preflight_observer(api, privacy):
    beginning, cpu, wall, polls = time.perf_counter(), 0.0, 0.0, 0
    while time.perf_counter() - beginning < 10:
        c,w = time.process_time(),time.perf_counter()
        rows = api.snapshot({os.getpid()})
        if any(r['name'].lower() in NATIVE_NAMES or 'liveupdate' in r['image'].lower() for r in rows):
            raise ValueError('NEEDS_USER_ACTION: native/update process exists before launch')
        privacy.check(json.dumps(rows))
        cpu += time.process_time() - c
        wall += time.perf_counter() - w
        polls += 1
        time.sleep(POLL_SECONDS)
    elapsed = time.perf_counter() - beginning
    status = overhead_status(cpu, elapsed)
    if status != 'ACCEPTABLE':
        raise ValueError(status)
    return dict(status=status,cpu_seconds=cpu,wall_seconds=wall,elapsed_seconds=elapsed,polls=polls)


def hidden_startup():
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    info.wShowWindow = 0
    return info


def busy_worker(stop, seconds, owner_pid, owner_born, ready=None):
    if not 0 < seconds <= MAX_SECONDS:
        raise ValueError('worker duration out of bounds')
    api = WindowsReadOnly()
    own=api.read(api.entries()[os.getpid()])
    cpu_beginning=time.process_time()
    deadline, value, operations = time.monotonic() + seconds, 1, 0
    announced=False
    while time.monotonic() < deadline and not Path(stop).exists():
        entries = api.entries()
        if owner_pid not in entries:
            break
        row = api.read(entries[owner_pid])
        if row['born'] != owner_born:
            break
        checkpoint = min(deadline, time.monotonic() + .25)
        # Deterministic integer workload. Wall-time only controls its duration.
        while time.monotonic() < checkpoint:
            for _ in range(1000):
                value = (value * 1664525 + 1013904223) & 0xffffffff
            operations += 1000
        if ready is not None and not announced and operations>0 and time.process_time()>cpu_beginning:
            batch.dump(Path(ready),dict(pid=os.getpid(),born=own['born'],owner_pid=owner_pid,
                       owner_born=owner_born,operations=operations,cpu_seconds=time.process_time()-cpu_beginning))
            announced=True
    return operations


def run_case(case, evidence_root):
    matrix.verify_staged(case)
    evidence_root = Path(evidence_root)
    bound_manifest = json.loads((evidence_root.parent / 'matrix' / 'manifest.json').read_text(encoding='utf-8'))
    if case not in bound_manifest:
        raise ValueError('case/evidence manifest mismatch')
    profile = batch.ROOT / 'MQL5/Profiles/Charts' / PROFILE
    current_profile = profile_state(profile)
    if case.get('profile_sha256') != current_profile:
        raise ValueError('frozen dedicated profile changed')
    expected_placement = require_normal_pair(evidence_root,case['count']) if case['load']=='CPU_CONTENTION' else None
    privacy = batch.PrivacyGuard()
    api = WindowsReadOnly(privacy.values)
    preflight = preflight_observer(api, privacy)
    initial = api.snapshot({os.getpid()})
    if any(r['name'].lower() in NATIVE_NAMES or 'liveupdate' in r['image'].lower() for r in initial):
        raise ValueError('NEEDS_USER_ACTION: pre-existing native/update process')
    own = next(r for r in initial if r['pid'] == os.getpid())
    roles = {(r['pid'],r['born']): 'controller' if r['pid'] == os.getpid() else 'lineage_ancestor' for r in initial}
    observer = Observer(roles)
    destination = evidence_root / case['case']
    destination.mkdir(parents=True, exist_ok=False)
    stop = destination / 'worker.stop'
    started, beginning = time.time(), time.perf_counter()
    offsets = {str(p): p.stat().st_size for p in batch.LOGROOT.glob('*.log')}
    attempt = dict(case=case['case'], mode=case['mode'], load=case['load'], started=started,
                   offsets=offsets, status='RUNNING', timeout_seconds=MAX_SECONDS,
                   diagnostic_tool_sha256=tooling_hashes(),observer_preflight=preflight,
                   profile_sha256=current_profile)
    batch.dump(destination / 'attempt.json', attempt)
    workers, terminal, sampled_cpu, sampled_wall, poll_count = [], None, 0.0, 0.0, 0
    tracked = {os.getpid()}
    error = None
    measurement_end = None
    try:
        observer.sample(initial, 0)
        def startup_sample(first_read):
            nonlocal sampled_cpu,sampled_wall,poll_count
            cpu_start,wall_start = time.process_time(),time.perf_counter()
            rows = api.snapshot(tracked)
            rows = [r for r in rows if r['pid'] != first_read['pid']] + [first_read]
            snapshot = observer.sample(rows,time.perf_counter()-beginning)
            payload = json.dumps(dict(wall_unix_ns=time.time_ns(),wall_perf_ns=time.perf_counter_ns(),
                                      elapsed_s=time.perf_counter()-beginning,processes=snapshot))
            privacy.check(payload)
            with (destination / 'startup_samples.jsonl').open('a',encoding='utf-8') as stream:
                stream.write(payload+'\n')
            sampled_cpu += time.process_time()-cpu_start
            sampled_wall += time.perf_counter()-wall_start
            poll_count += 1
            state = observer.summary()
            if state['changes'] or state['unknown_identities'] or state['contamination']:
                raise ValueError('ISOLATION_NOT_ESTABLISHED: startup observation contaminated')
        if case['load'] == 'CPU_CONTENTION':
            ready_bindings=[]
            for index in range(WORKERS):
                ready=destination/f'worker_ready_{index}.json'
                worker = subprocess.Popen([sys.executable, '-m', 'tools.mc_isolated_contention', '--worker', str(stop),
                                           str(MAX_SECONDS), str(os.getpid()), str(own['born']),str(ready)],
                                          startupinfo=hidden_startup(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                workers.append(worker)
                tracked.add(worker.pid)
                entry = api.entries().get(worker.pid)
                if entry is None:
                    raise ValueError('worker creation not observed')
                row = api.read(entry)
                if row['owner'] != 'SAME_USER' or row['parent'] != os.getpid():
                    raise ValueError('worker ownership not proven')
                observer.register((row['pid'],row['born']), 'owned_load_generator')
                startup_sample(row)
                ready_bindings.append((ready,row['pid'],row['born']))
            ready_deadline=time.perf_counter()+30
            while not all(p.is_file() for p,_,_ in ready_bindings):
                if any(w.poll() is not None for w in workers):
                    raise ValueError('owned worker ended prematurely')
                if time.perf_counter()>ready_deadline:
                    raise ValueError('worker readiness timeout')
                startup_sample(api.read(api.entries()[os.getpid()]))
                time.sleep(POLL_SECONDS)
            attempt['load_ready']=[read_worker_ready(p,pid,born,os.getpid(),own['born']) for p,pid,born in ready_bindings]
            attempt['load_ready_wall_perf_ns']=time.perf_counter_ns()
            attempt['load_ready_wall_unix_ns']=time.time_ns()
            batch.dump(destination/'attempt.json',attempt)
        if profile_state(profile) != current_profile:
            raise ValueError('dedicated profile changed immediately before launch')
        startup_sample(api.read(api.entries()[os.getpid()]))
        terminal = subprocess.Popen([str(batch.TERMINAL), '/profile:' + PROFILE, '/config:' + case['config']],
                                    startupinfo=hidden_startup(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        attempt['terminal_launch_wall_perf_ns']=time.perf_counter_ns()
        entries = api.entries()
        if terminal.pid not in entries:
            raise ValueError('launched terminal already absent')
        root = api.read(entries[terminal.pid])
        if root['image'].lower() != str(batch.TERMINAL).lower() or root['owner'] != 'SAME_USER':
            raise ValueError('terminal identity/owner mismatch')
        observer.register((root['pid'],root['born']), 'owned_terminal')
        tracked.add(terminal.pid)
        startup_sample(root)
        with (destination / 'process_samples.jsonl').open('x', encoding='utf-8') as stream:
            while True:
                cpu_start, wall_start = time.process_time(), time.perf_counter()
                rows = api.snapshot(tracked)
                sample = observer.sample(rows, time.perf_counter() - beginning)
                tracked.update(k[0] for k, role in observer.roles.items() if role != 'lineage_ancestor')
                payload = json.dumps(dict(wall_unix_ns=time.time_ns(), wall_perf_ns=time.perf_counter_ns(),
                                          elapsed_s=time.perf_counter() - beginning, processes=sample), ensure_ascii=True)
                privacy.check(payload)
                stream.write(payload + '\n')
                sampled_cpu += time.process_time() - cpu_start
                sampled_wall += time.perf_counter() - wall_start
                poll_count += 1
                state = observer.summary()
                if state['changes'] or state['unknown_identities'] or state['contamination']:
                    raise ValueError('ISOLATION_NOT_ESTABLISHED: contaminated/changed/unknown observation')
                if any(w.poll() is not None for w in workers):
                    raise ValueError('owned worker ended prematurely')
                if terminal.poll() is not None:
                    break
                if time.perf_counter() - beginning >= MAX_SECONDS:
                    raise TimeoutError('NEEDS_USER_ACTION: Tester still running at bounded deadline')
                time.sleep(POLL_SECONDS)
        attempt.update(status='COLLECTABLE', exit_code=terminal.wait(timeout=1),
                       elapsed_seconds=time.perf_counter() - beginning)
        measurement_end = time.perf_counter()
    except BaseException as failure:
        error = failure
        attempt.update(status='BLOCKED', exception=type(failure).__name__,
                       reason=safe_error_code(failure))
    finally:
        if measurement_end is None:
            measurement_end = time.perf_counter()
        shutdown_status, shutdown_reason = stop_workers(workers, stop)
        if shutdown_status != 'PASS':
            attempt.update(status=shutdown_status, reason=shutdown_reason)
        elapsed = time.perf_counter() - beginning
        measured_elapsed = measurement_end - beginning
        summary = observer.summary(completed=attempt['status'] == 'COLLECTABLE')
        summary.update(observer_cpu_seconds=sampled_cpu, observer_wall_seconds=sampled_wall,
                       run_elapsed_seconds=elapsed, poll_count=poll_count,
                       acquisition_seconds=measured_elapsed,shutdown_seconds=elapsed-measured_elapsed,
                       overhead_status=overhead_status(sampled_cpu, measured_elapsed),
                       cpu_fraction_one_core=sampled_cpu / measured_elapsed if measured_elapsed else 'UNKNOWN',
                       load_workers=len(workers), affinity_mutations=0, priority_mutations=0,
                       ownership_method='Popen PID + live parent + creation time + same-user token',
                       current_terminal_running=terminal is not None and terminal.poll() is None)
        summary['comparison_eligible'] &= summary['overhead_status'] == 'ACCEPTABLE' and attempt['status'] == 'COLLECTABLE'
        if summary['comparison_eligible']:
            try:
                signature=placement_signature(summary)
                if expected_placement is not None:
                    require_matching_placement(expected_placement,signature)
                summary['placement_signature']=signature
            except ValueError:
                summary.update(comparison_eligible=False,placement_comparison='UNKNOWN_OR_DIFFERENT')
        summary = safe_summary(summary, privacy)
        if summary.get('reason') == 'PRIVATE_METADATA_REJECTED':
            attempt.update(status='BLOCKED',reason='PRIVATE_METADATA_REJECTED')
        batch.dump(destination / 'observation.json', summary)
        batch.dump(destination / 'attempt.json', attempt)
    if error:
        raise error
    if not summary['comparison_eligible']:
        raise ValueError('observer overhead/collection prevents comparison')
    result = matrix.collect_native_case(case, evidence_root)
    prefix = result['scheduler']['prefix']
    def rows(suffix):
        with (destination / (prefix + suffix + '.csv')).open(encoding='ascii', newline='') as f:
            return list(csv.DictReader(f))
    population = timer_population(rows('_events'), rows('_timer_summary'))
    batch.dump(destination / 'timer_population.json', population)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', nargs=5)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--evidence', type=Path)
    parser.add_argument('--count', type=int, choices=(2,3,4))
    parser.add_argument('--mode', type=int, choices=(0,2))
    parser.add_argument('--load', choices=matrix.LOADS)
    args = parser.parse_args()
    if args.worker:
        stop, seconds, owner_pid, owner_born, ready = args.worker
        busy_worker(stop, int(seconds), int(owner_pid), int(owner_born),ready)
        return
    if not args.manifest or not args.evidence or args.count is None or args.mode is None or not args.load:
        parser.error('explicit frozen manifest/evidence/case required')
    cases = json.loads(args.manifest.read_text(encoding='utf-8'))
    if cases != json.loads((args.evidence.parent / 'matrix' / 'manifest.json').read_text(encoding='utf-8')):
        raise ValueError('CLI/evidence manifests differ')
    case = [c for c in cases if (c['count'],c['mode'],c['load']) == (args.count,args.mode,args.load)]
    if len(case) != 1:
        raise ValueError('frozen case absent/ambiguous')
    with batch.RunnerLock():
        result = run_case(case[0], args.evidence)
    print(json.dumps(dict(status=result['status'], case=result['case'], runtime=result['runtime_errors'], warnings=result['warnings'])))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps(dict(status='BLOCKED', exception=type(error).__name__,
                              reason=safe_error_code(error))))
        sys.exit(1)
