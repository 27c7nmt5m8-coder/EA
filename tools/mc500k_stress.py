"""Scoped, opt-in stress collection after the fresh 28-case matrix is complete.

No native run occurs without --run. Only the launched terminal, its verified
Tester descendants, and one optional owned Python worker receive affinity changes.
Process command lines, accounts, journals and environment values are not exported.
Toolhelp parent IDs are corroborated by image paths and creation times because IDs
can be reused: https://devblogs.microsoft.com/oldnewthing/20150403-00/?p=44313
"""
import argparse
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime
import json
import math
import ntpath
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

try:
    from . import mc500k_batch as batch
except ImportError:
    import mc500k_batch as batch


LABELS = ('single_core', 'contended_core')
TESTERS = {'metatester64.exe', 'metatester.exe'}
NATIVE_NAMES = TESTERS | {'terminal64.exe', 'terminal.exe'}
MAX_SECONDS = 1800
POLL_SECONDS = .1
EXIT_CONFIRMATION_MS = 1000


def require(ok, code):
    if not ok:
        raise batch.BatchFailure(code)


def safe_component(value):
    require(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]+', value),
            'unsafe stress component')
    return value


def verify_files(case):
    for key in ('config', 'set_path', 'binary'):
        hash_key = {'config': 'config_sha256', 'set_path': 'set_sha256', 'binary': 'binary_sha256'}[key]
        require(batch.sha(case[key]) == case[hash_key], 'baseline artifact changed')
    for name, digest in case['source_hashes'].items():
        require(Path(name).name == name, 'invalid baseline source name')
        require(batch.sha(Path(case['binary']).parent / name) == digest, 'baseline source changed')


def select_cases(manifest, baseline, count=1):
    """One heavy-MC pair: tick density first, then fixed500k callback time."""
    require(count == 1 and len(manifest) == 56, 'expected complete original matrix and one stress pair')
    pairs = {}
    densities = {}
    heavy = {}
    exposure = {}
    for case in manifest:
        identity = safe_component(case['case'])
        mode = case['mode']
        require(mode in (0, 2) and mode not in pairs.setdefault(identity, {}), 'invalid matrix pair')
        out = Path(baseline) / identity / ('current' if mode == 0 else 'fixed500k')
        require(batch.resume_valid(case, out), 'normal matrix incomplete')
        result = json.loads((out / 'result.json').read_text(encoding='utf-8'))
        ticks = result['report_metrics']['ticks']
        require(isinstance(ticks, int) and ticks > 0 and result['report_metrics']['history_quality'] == 100,
                'invalid normal tick evidence')
        seconds = (datetime.strptime(case['end'], '%Y.%m.%d') -
                   datetime.strptime(case['start'], '%Y.%m.%d')).total_seconds()
        require(seconds > 0, 'invalid normal case duration')
        metrics = result.get('timeline', {}).get('metrics', {})
        started = metrics.get('calculation_count')
        completed = metrics.get('completed_calculations')
        require(type(started) is int and type(completed) is int and 0 <= completed <= started,
                'invalid heavy MC evidence')
        heavy.setdefault(identity, {})[mode] = started > 0 and completed > 0
        if mode == 2:
            total = result.get('callback_us', {}).get('total')
            require(type(total) in (int, float) and math.isfinite(total) and total >= 0,
                    'invalid MC callback exposure')
            exposure[identity] = total
        pairs[identity][mode] = case
        if mode == 0:
            densities[identity] = ticks / seconds
    require(len(pairs) == 28 and all(set(p) == {0, 2} for p in pairs.values()), 'incomplete matrix pairs')
    for pair in pairs.values():
        require(all(pair[0].get(k) == pair[2].get(k)
                    for k in ('symbol', 'start', 'end', 'set_sha256', 'max_atr', 'max_sl')),
                'normal pair conditions mismatch')
    eligible = [key for key in pairs if all(heavy[key].values())]
    require(bool(eligible), 'no completed heavy MC pair')
    chosen = sorted(eligible, key=lambda key: (-densities[key], -exposure[key], key))[:1]
    return [pairs[key][mode] for key in chosen for mode in (0, 2)]


def prepare_case(case, label, attempt):
    require(label in LABELS, 'invalid stress label')
    safe_component(attempt)
    safe_component(case['case'])
    require(case['mode'] in (0, 2), 'invalid stress mode')
    verify_files(case)
    before_text = batch.read_text(case['config'])
    before = dict(line.split('=', 1) for line in before_text.splitlines() if '=' in line)
    report = f"CodexMCStress_{label}_{case['case']}_{case['mode']}_{attempt}"
    config = Path(case['config']).with_name(report + '.ini')
    report_path = batch.ROOT / (report + '.htm')
    require(not config.exists() and not report_path.exists(), 'stress names already exist')
    text = batch.tester_config(before_text, before['Expert'], report)
    after = dict(line.split('=', 1) for line in text.splitlines() if '=' in line)
    require({k: v for k, v in after.items() if k != 'Report'} ==
            {k: v for k, v in before.items() if k != 'Report'}, 'stress condition drift')
    with config.open('x', encoding='utf-8') as stream:
        stream.write(text)
    return dict(case, config=str(config), config_sha256=batch.sha(config), report=str(report_path),
                baseline_config_sha256=case['config_sha256'], stress_label=label, attempt_id=attempt)


@dataclass(frozen=True)
class Process:
    pid: int
    parent: int
    born: int
    image: str
    affinity: int


def image_key(image):
    return ntpath.normcase(ntpath.normpath(image))


def owned_descendants(root, snapshot, known=()):
    """Enroll through live verified parents; observe known children by identity."""
    current = {p.pid: p for p in snapshot}
    require(len(current) == len(snapshot), 'duplicate process identity')
    ancestors = {root.pid: root, **{p.pid: p for p in known}}
    for pid, prior in ancestors.items():
        if pid in current:
            require(current[pid].born == prior.born and image_key(current[pid].image) == image_key(prior.image),
                    'process identity changed')
    testers = [p for p in snapshot if ntpath.basename(p.image).lower() in TESTERS]
    # Known children have already been attributed and their current creation time
    # and image were revalidated above. Their parents may have exited meanwhile.
    owned = [p for p in testers if p.pid in ancestors and p.pid != root.pid]
    pending = [p for p in testers if p not in owned]
    while pending:
        progress = False
        for process in pending[:]:
            parent = ancestors.get(process.parent)
            if parent is None:
                continue
            # A remembered ancestor alone is not ownership evidence: its PID
            # may now belong to a nonnative process omitted by the snapshot.
            live_parent = current.get(parent.pid)
            require(live_parent is not None and live_parent.born == parent.born and
                    image_key(live_parent.image) == image_key(parent.image),
                    'live parent identity unavailable')
            require(process.born >= parent.born and process.born >= root.born,
                    'agent predates owned ancestor')
            require(image_key(ntpath.dirname(process.image)) == image_key(ntpath.dirname(root.image)),
                    'agent image outside terminal installation')
            ancestors[process.pid] = process
            owned.append(process)
            pending.remove(process)
            progress = True
        require(progress or not pending, 'agent ownership unknown')
    return owned


class OwnedChildren:
    """Only Popen objects created by this invocation can enter this cleanup list."""
    def __init__(self):
        self.children = []

    def __enter__(self):
        return self

    def add(self, process):
        self.children.append(process)
        return process

    def __exit__(self, *_):
        failed = False
        for process in reversed(self.children):
            try:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                failed = True
        require(not failed, 'owned process cleanup incomplete')


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
                ('th32ProcessID', wintypes.DWORD), ('th32DefaultHeapID', ctypes.c_size_t),
                ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
                ('th32ParentProcessID', wintypes.DWORD), ('pcPriClassBase', wintypes.LONG),
                ('dwFlags', wintypes.DWORD), ('szExeFile', wintypes.WCHAR * 260)]


class ObservedProcessExit(batch.BatchFailure):
    """Only raised after the open process handle signals process termination."""
    def __init__(self, pid, parent):
        super().__init__('process exited during identity query')
        self.evidence = dict(pid=pid, parent_pid=parent, phase='identity_query',
                             proof=f'WaitForSingleObject(handle,{EXIT_CONFIRMATION_MS})==WAIT_OBJECT_0',
                             confirmation_wait_limit_ms=EXIT_CONFIRMATION_MS,
                             ownership='not_asserted', observed_monotonic=time.monotonic())


class WindowsProcesses:
    """Read scoped identities; set affinity only after reopening and rechecking identity."""
    def __init__(self):
        require(os.name == 'nt', 'Windows affinity unavailable')
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.exited_observations = []
        declarations = {
            'OpenProcess': ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
            'CloseHandle': ([wintypes.HANDLE], wintypes.BOOL),
            'WaitForSingleObject': ([wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
            'GetProcessTimes': ([wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4, wintypes.BOOL),
            'QueryFullProcessImageNameW': ([wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                          ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
            'GetProcessAffinityMask': ([wintypes.HANDLE, ctypes.POINTER(ctypes.c_size_t),
                                       ctypes.POINTER(ctypes.c_size_t)], wintypes.BOOL),
            'SetProcessAffinityMask': ([wintypes.HANDLE, ctypes.c_size_t], wintypes.BOOL),
            'CreateToolhelp32Snapshot': ([wintypes.DWORD, wintypes.DWORD], wintypes.HANDLE),
            'Process32FirstW': ([wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)], wintypes.BOOL),
            'Process32NextW': ([wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)], wintypes.BOOL),
            'GetActiveProcessorGroupCount': ([], wintypes.WORD),
        }
        for name, (args, result) in declarations.items():
            function = getattr(self.kernel, name)
            function.argtypes, function.restype = args, result
        require(self.kernel.GetActiveProcessorGroupCount() == 1, 'multiple processor groups unsupported')

    def _open(self, pid, mutate=False):
        # SYNCHRONIZE permits a bounded wait on this exact handle. Without
        # that proof, an identity-query failure must remain blocking.
        handle = self.kernel.OpenProcess(0x1000 | 0x100000 | (0x0200 if mutate else 0), False, pid)
        require(bool(handle), 'process identity unavailable')
        return handle

    def _read(self, handle, pid, parent):
        times = [wintypes.FILETIME() for _ in range(4)]
        require(self.kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)), 'process creation unavailable')
        size = wintypes.DWORD(32768)
        image = ctypes.create_unicode_buffer(size.value)
        require(self.kernel.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(size)), 'process image unavailable')
        mask, system = ctypes.c_size_t(), ctypes.c_size_t()
        require(self.kernel.GetProcessAffinityMask(handle, ctypes.byref(mask), ctypes.byref(system)),
                'process affinity unavailable')
        return Process(pid, parent, (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime,
                       image.value, mask.value)

    def read(self, pid, parent=0):
        handle = self._open(pid)
        try:
            try:
                return self._read(handle, pid, parent)
            except batch.BatchFailure:
                # Image teardown can precede the process termination signal.
                # Wait at most one second on the same handle; never repin it.
                # WAIT_TIMEOUT, WAIT_FAILED, or any unexpected result does not
                # prove termination. Preserve the original query failure.
                if self.kernel.WaitForSingleObject(handle, EXIT_CONFIRMATION_MS) == 0:
                    raise ObservedProcessExit(pid, parent) from None
                raise
        finally:
            self.kernel.CloseHandle(handle)

    def pin(self, expected, mask):
        handle = self._open(expected.pid, mutate=True)
        try:
            actual = self._read(handle, expected.pid, expected.parent)
            require(actual.born == expected.born and image_key(actual.image) == image_key(expected.image),
                    'process identity changed before affinity')
            require(mask > 0 and mask & (mask - 1) == 0 and actual.affinity & mask,
                    'requested CPU outside current process affinity')
            require(self.kernel.SetProcessAffinityMask(handle, mask), 'scoped affinity failed')
            observed = self._read(handle, expected.pid, expected.parent).affinity
            require(observed == mask, 'scoped affinity unverified')
            return observed
        finally:
            self.kernel.CloseHandle(handle)

    def snapshot(self):
        handle = self.kernel.CreateToolhelp32Snapshot(2, 0)
        require(handle not in (None, ctypes.c_void_p(-1).value), 'process snapshot unavailable')
        result = []
        try:
            entry = PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(entry)
            ok = self.kernel.Process32FirstW(handle, ctypes.byref(entry))
            while ok:
                if entry.szExeFile.lower() in NATIVE_NAMES:
                    try:
                        result.append(self.read(entry.th32ProcessID, entry.th32ParentProcessID))
                    except ObservedProcessExit as exited:
                        # The handle proved termination. Omit the dead entry;
                        # never infer identity/ownership or mutate affinity.
                        self.exited_observations.append(exited.evidence)
                ok = self.kernel.Process32NextW(handle, ctypes.byref(entry))
            require(ctypes.get_last_error() == 18, 'incomplete process snapshot')
            return result
        finally:
            self.kernel.CloseHandle(handle)


class AffinityMonitor:
    def __init__(self, api, root, cpu, started):
        self.api, self.root, self.mask, self.started = api, root, 1 << cpu, started
        self.known = {}
        self.records = {}
        self.affinity_drift = []
        self.observe(root, 'owned_terminal', pin=True)

    def observe(self, process, role, pin=False):
        key = (process.pid, process.born)
        now = time.monotonic() - self.started
        if pin:
            observed = self.api.pin(process, self.mask)
        else:
            observed = process.affinity
        if observed != self.mask:
            self.affinity_drift.append(dict(pid=process.pid,role=role,expected_mask=self.mask,
                                            observed_mask=observed,observed_seconds=now))
            raise batch.BatchFailure('observed affinity drift')
        if key not in self.records:
            self.records[key] = dict(pid=process.pid, role=role, first_seen_seconds=now,
                                     initial_mask=process.affinity, observed_mask=observed,
                                     samples=0, last_seen_seconds=now)
        self.records[key]['samples'] += 1
        self.records[key]['last_seen_seconds'] = now

    def sample(self):
        snapshot = self.api.snapshot()
        require(not any(ntpath.basename(p.image).lower() in {'terminal64.exe', 'terminal.exe'} and
                        (p.pid != self.root.pid or p.born != self.root.born) for p in snapshot),
                'unowned terminal appeared')
        descendants = owned_descendants(self.root, snapshot, self.known.values())
        for process in snapshot:
            if process.pid == self.root.pid:
                self.observe(process, 'owned_terminal')
        for process in descendants:
            first = process.pid not in self.known
            self.observe(process, 'verified_tester_descendant', pin=first)
            self.known[process.pid] = process

    def evidence(self):
        return dict(status='BLOCKED' if self.affinity_drift else 'PASS' if self.known else 'UNKNOWN', mask=self.mask,
                    attribution='parent PID plus creation time and installation image; rechecked before mutation',
                    processes=list(self.records.values()), sampled_agents=len(self.known),
                    affinity_drift=list(self.affinity_drift),
                    confirmed_exits=[{k: v for k, v in event.items() if k != 'observed_monotonic'} |
                                     dict(observed_seconds=event['observed_monotonic'] - self.started)
                                     for event in getattr(self.api, 'exited_observations', [])],
                    sampling_interval_seconds=POLL_SECONDS,
                    unsampled_startup_affinity='UNKNOWN', live_queue_latency='UNKNOWN',
                    actual_multisymbol='NOT_RUN: cycle identity collision constraint')


def hidden_startup():
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    return startup


def busy_worker(cpu, seconds, owner_pid, owner_born):
    """Bounded process-local load; exits when the creating runner disappears."""
    require(0 <= cpu < 64 and 0 < seconds <= MAX_SECONDS, 'invalid worker bounds')
    api = WindowsProcesses()
    own = api.read(os.getpid())
    api.pin(own, 1 << cpu)
    deadline = time.monotonic() + seconds
    value = 1
    while time.monotonic() < deadline:
        owner = api.read(owner_pid)
        if owner.born != owner_born:
            return
        checkpoint = min(deadline, time.monotonic() + .25)
        while time.monotonic() < checkpoint:
            value = (value * 1664525 + 1013904223) & 0xffffffff


def run_one(case, label, cpu, privacy, api=None, timeout=MAX_SECONDS):
    require(label in LABELS and 0 <= cpu < 64 and 0 < timeout <= MAX_SECONDS, 'invalid stress bounds')
    verify_files(case)
    api = api or WindowsProcesses()
    require(not api.snapshot(), 'existing terminal or tester ownership unknown')
    out = batch.DEST / 'stress' / label / safe_component(case['case']) / ('current' if case['mode'] == 0 else 'fixed500k')
    require(not out.exists(), 'stress attempt already exists; inspect recovery evidence')
    out.mkdir(parents=True)
    native_case = None
    monitor = None
    worker = None
    started = time.time()
    monotonic_start = time.monotonic()
    stage = 'prepare'
    try:
        native_case = prepare_case(case, label, uuid.uuid4().hex[:12])
        privacy.check(batch.read_text(native_case['config']))
        privacy.check(batch.read_text(native_case['set_path']))
        offsets = {str(p): p.stat().st_size for p in batch.LOGROOT.glob('*.log')}
        attempt = dict(case=native_case, label=label, cpu=cpu, started=started, offsets=offsets,
                       timeout_seconds=timeout, status='RUNNING')
        batch.dump(out / 'attempt.json', attempt)
        with OwnedChildren() as owned:
            stage = 'launch'
            terminal = owned.add(subprocess.Popen(
                [str(batch.TERMINAL), '/profile:' + batch.PROFILE, '/config:' + native_case['config']],
                startupinfo=hidden_startup(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
            root = api.read(terminal.pid)
            require(image_key(root.image) == image_key(str(batch.TERMINAL)), 'launched terminal identity mismatch')
            monitor = AffinityMonitor(api, root, cpu, monotonic_start)
            if label == 'contended_core':
                runner = api.read(os.getpid())
                worker = owned.add(subprocess.Popen(
                    [sys.executable, str(Path(__file__).resolve()), '--busy-worker', str(cpu), str(timeout),
                     str(os.getpid()), str(runner.born)], startupinfo=hidden_startup(),
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
                worker_identity = api.read(worker.pid)
                require(image_key(worker_identity.image) == image_key(sys.executable), 'worker image mismatch')
                monitor.observe(worker_identity, 'owned_contention_worker', pin=True)
            stage = 'sample'
            while terminal.poll() is None:
                require(time.monotonic() - monotonic_start < timeout, 'owned stress timeout')
                if worker is not None:
                    require(worker.poll() is None, 'contention worker exited early')
                    monitor.observe(api.read(worker.pid), 'owned_contention_worker')
                monitor.sample()
                time.sleep(POLL_SECONDS)
            monitor.sample()
            code = terminal.wait(timeout=1)
            attempt.update(exit_code=code, elapsed=time.monotonic() - monotonic_start, status='COLLECTABLE')
            batch.dump(out / 'attempt.json', attempt)
            evidence = monitor.evidence()
            batch.dump(out / 'affinity.json', evidence)
            require(evidence['status'] == 'PASS', 'tester agent ownership unobserved')
        # Worker and launched terminal are now stopped. Tester descendant handles
        # are never terminated; an idle surviving agent blocks the next run.
        stage = 'collect'
        result = batch.collect(native_case, out, started, offsets, code, attempt['elapsed'], privacy)
        result['stress'] = dict(label=label, cpu=cpu, affinity_sha256=batch.sha(out / 'affinity.json'),
                                normal_case=case, live_queue_latency='UNKNOWN', actual_multisymbol='NOT_RUN')
        privacy.check(json.dumps(result, ensure_ascii=True))
        batch.dump(out / 'result.json', result)
        return result
    except BaseException as error:
        if monitor is not None:
            evidence = monitor.evidence()
            evidence['status'] = 'UNKNOWN'
            batch.dump(out / 'affinity.json', evidence)
        failure = dict(status='BLOCKED', stage=stage, exception=type(error).__name__,
                       code=str(error) if isinstance(error, batch.BatchFailure) else 'UNCLASSIFIED',
                       elapsed=time.monotonic() - monotonic_start, label=label, case=case['case'], mode=case['mode'])
        batch.dump(out / 'failure.json', failure)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--count', type=int, default=1)
    parser.add_argument('--cpu', type=int, default=0)
    parser.add_argument('--label', choices=LABELS, action='append')
    parser.add_argument('--busy-worker', nargs=4, type=int, metavar=('CPU', 'SECONDS', 'OWNER', 'BIRTH'))
    args = parser.parse_args()
    if args.busy_worker:
        busy_worker(*args.busy_worker)
        return
    manifest = json.loads((batch.DEST / 'manifest.json').read_text(encoding='utf-8'))
    with batch.RunnerLock():
        chosen = select_cases(manifest, batch.DEST, args.count)
        print(json.dumps(dict(status='SELECTED', cases=[dict(case=c['case'], mode=c['mode']) for c in chosen])))
        if args.run:
            privacy = batch.PrivacyGuard()
            for label in dict.fromkeys(args.label or LABELS):
                for case in chosen:
                    result = run_one(case, label, args.cpu, privacy)
                    print(json.dumps(dict(status=result['status'], label=label,
                                          case=case['case'], mode=case['mode'])), flush=True)


if __name__ == '__main__':
    try:
        main()
    except (Exception, KeyboardInterrupt) as error:
        print(json.dumps(dict(status='BLOCKED', exception=type(error).__name__,
                              code=str(error) if isinstance(error, batch.BatchFailure) else 'UNCLASSIFIED')), flush=True)
        sys.exit(1)
