"""Read-only Windows process observation. No setting/termination API is exposed.

Polling establishes intervals, not exact change/exit instants or API callers.
Command arguments are deny-by-default; credentials never enter exported rows.
"""
import ctypes
from ctypes import wintypes as W
import hashlib
import math
import ntpath
import os
import re
import time

NATIVE_NAMES = {'terminal64.exe', 'terminal.exe', 'metatester64.exe', 'metatester.exe',
                'metaeditor64.exe', 'liveupdate.exe'}
POLL_SECONDS = 1.0  # Read-only preflight at 250ms consumed >2% of one core.
# Observation must consume <2% of one core over the measured run. This is an
# instrumentation acceptance budget, not an EA event-latency safety threshold.
OBSERVER_CPU_FRACTION = .02


def redact_command(text, secrets=()):
    if not isinstance(text, str):
        return 'UNKNOWN'
    for secret in sorted((s for s in secrets if s), key=len, reverse=True):
        text = text.replace(secret, '[REDACTED]')
    # Never retain unknown arguments, even if a credential has an unknown name.
    tokens = re.findall(r'"[^"]*"|\S+', text)
    safe = []
    for index, token in enumerate(tokens):
        value = token.strip('"')
        if index == 0 and ntpath.basename(value).lower() in NATIVE_NAMES | {'python.exe','pwsh.exe','powershell.exe','codex.exe','chatgpt.exe','explorer.exe'}:
            safe.append(token)
        elif re.fullmatch(r'/profile:CodexTester(?:Pipeline|Affinity)_[0-9]{8}',value):
            safe.append(token)
        elif value.lower().startswith('/config:') and re.fullmatch(r'CodexMCMulti[A-Za-z0-9_]+\.ini', ntpath.basename(value[8:])):
            safe.append('/config:' + ntpath.basename(value[8:]))
        else:
            safe.append('[REDACTED_ARGUMENT]')
    return ' '.join(safe)


def overhead_status(cpu_seconds, elapsed_seconds):
    if not math.isfinite(elapsed_seconds) or not math.isfinite(cpu_seconds) or elapsed_seconds <= 0 or cpu_seconds < 0:
        return 'UNKNOWN'
    return 'ACCEPTABLE' if cpu_seconds / elapsed_seconds < OBSERVER_CPU_FRACTION else 'OBSERVER_OVERHEAD_TOO_HIGH'


def known_placement(row):
    return (type(row.get('affinity')) is int and row['affinity']>0 and
            type(row.get('priority')) is int and row['priority']>0 and
            all(isinstance(row.get(f),list) and all(type(v) is int and v>=0 for v in row[f])
                for f in ('groups','cpu_sets')) and bool(row['groups']))


class Observer:
    """Pure identity/lineage state machine, independent of OS access."""
    def __init__(self, roles):
        self.roles = dict(roles)
        self.required = {key for key,role in roles.items() if role != 'lineage_ancestor'}
        self.last, self.records = {}, {}
        self.events, self.changes, self.contamination = [], [], []
        self.seen = set()
        self.absent = set()
        self.unknown = []

    def register(self, key, role):
        self.roles[key] = role
        if role != 'lineage_ancestor':
            self.required.add(key)

    def sample(self, rows, seconds):
        by_pid = {row['pid']: row for row in rows}
        if len(by_pid) != len(rows):
            raise ValueError('duplicate PID snapshot')
        current = {(r['pid'], r['born']): r for r in rows}
        for key, prior in self.last.items():
            if key not in current:
                self.absent.add(key)
                self.events.append(dict(kind='PROCESS_ABSENT', pid=key[0], born=key[1],
                                        after_sample_s=prior['observed_s'], observed_s=seconds,
                                        exact_exit_time='UNKNOWN'))
        # Establish descendants only through the parent's live, exact identity.
        pending = list(rows)
        for _ in range(len(rows)):
            progress = False
            for row in pending[:]:
                key = row['pid'], row['born']
                parent = by_pid.get(row['parent'])
                if key in self.roles:
                    pending.remove(row)
                elif (parent and (parent['pid'], parent['born']) in self.roles and
                      self.roles[(parent['pid'], parent['born'])] != 'lineage_ancestor' and
                      isinstance(row['born'], int) and isinstance(parent['born'], int) and
                      row['born'] >= parent['born'] and row.get('owner') == 'SAME_USER'):
                    self.roles[key] = 'owned_editor_auxiliary' if row['name'].lower() == 'metaeditor64.exe' and ntpath.dirname(row.get('image','')).lower() == ntpath.dirname(parent.get('image','')).lower() else 'owned_descendant'
                    pending.remove(row)
                    progress = True
            if not progress:
                break
        for key, row in current.items():
            if key in self.absent and key in self.required and key not in self.unknown:
                self.unknown.append(key)
            native = row['name'].lower() in NATIVE_NAMES
            updater = 'liveupdate' in row.get('image', '').lower() or 'liveupdate' in row['name'].lower()
            parent = by_pid.get(row['parent'])
            child = parent and (parent['pid'],parent['born']) in self.roles and self.roles[(parent['pid'],parent['born'])] != 'lineage_ancestor'
            foreign_child = child and row.get('owner') != 'SAME_USER'
            if updater or (native and key not in self.roles) or foreign_child:
                event = dict(pid=row['pid'], born=row['born'], reason='UPDATER' if updater else 'FOREIGN_OR_UNKNOWN_CHILD' if foreign_child else 'UNOWNED_NATIVE', observed_s=seconds)
                if not any(e['pid'] == row['pid'] and e['born'] == row['born'] for e in self.contamination):
                    self.contamination.append(event)
            if key not in self.roles and not native and not updater and not foreign_child:
                continue
            role = self.roles.get(key, 'UNOWNED')
            prior = self.last.get(key)
            clean = dict(row, role=role, observed_s=seconds, cpu_one_core_pct='UNKNOWN')
            if prior and seconds > prior['observed_s'] and isinstance(row.get('cpu_100ns'), int) and isinstance(prior.get('cpu_100ns'), int):
                delta = row['cpu_100ns'] - prior['cpu_100ns']
                if delta >= 0:
                    clean['cpu_one_core_pct'] = delta / 100000 / (seconds - prior['observed_s'])
            essential = role != 'lineage_ancestor'
            if essential and (not known_placement(row) or row.get('owner') != 'SAME_USER' or row.get('image','UNKNOWN') == 'UNKNOWN'):
                if key not in self.unknown:
                    self.unknown.append(key)
            if prior and essential and type(prior['affinity']) is int and type(row['affinity']) is int and prior['affinity'] != row['affinity']:
                self.changes.append(dict(pid=row['pid'], born=row['born'], role=role,
                                         before=prior['affinity'], after=row['affinity'],
                                         after_sample_s=prior['observed_s'], observed_s=seconds,
                                         attribution='UNATTRIBUTED'))
            for field in ('groups','cpu_sets','priority'):
                if prior and essential and prior.get(field) != 'UNKNOWN' and row.get(field) != 'UNKNOWN' and prior.get(field) != row.get(field):
                    self.changes.append(dict(pid=row['pid'],born=row['born'],role=role,field=field,
                                             before=prior.get(field),after=row.get(field),
                                             after_sample_s=prior['observed_s'],observed_s=seconds,attribution='UNATTRIBUTED'))
            if key not in self.records:
                self.records[key] = dict(pid=row['pid'], born=row['born'], parent=row['parent'],
                                         role=role, name=row['name'], image=row.get('image', 'UNKNOWN'),
                                         owner=row.get('owner', 'UNKNOWN'), command=row.get('command', 'UNKNOWN'),
                                         first_seen_s=seconds, initial_affinity=row['affinity'], samples=0,
                                         initial_placement={f:row.get(f,'UNKNOWN') for f in ('affinity','groups','cpu_sets','priority')})
            self.records[key].update(last_seen_s=seconds, final_affinity=row['affinity'],
                                     final_placement={f:row.get(f,'UNKNOWN') for f in ('affinity','groups','cpu_sets','priority')},
                                     samples=self.records[key]['samples'] + 1)
            self.last[key] = clean
            self.seen.add(key)
        self.last = {k: v for k, v in self.last.items() if k in current}
        return list(self.last.values())

    def summary(self, completed=False):
        essential = [r for r in self.records.values() if r['role'] not in ('lineage_ancestor','owned_editor_auxiliary')]
        covered = all(key in self.seen for key in self.required) and all(r['samples'] >= 2 and r['last_seen_s'] > r['first_seen_s'] for r in essential)
        active = all(key in self.last for key in self.required)
        stable = bool(essential) and covered and (active or completed) and not self.changes and not self.unknown
        return dict(affinity_status='AFFINITY_STABLE' if stable else 'UNATTRIBUTED' if self.changes else 'UNKNOWN',
                    comparison_eligible=stable and not self.contamination,
                    changes=self.changes, contamination=self.contamination, unknown_identities=self.unknown,
                    processes=list(self.records.values()), events=self.events,
                    auxiliary_interval_coverage='UNKNOWN_FOR_SHORT_LIVED_PROCESSES',
                    poll_seconds=POLL_SECONDS, unsampled_transient_changes='UNKNOWN',
                    api_caller='UNATTRIBUTED', queue_depth='UNKNOWN')


class Entry(ctypes.Structure):
    _fields_ = [('size', W.DWORD), ('usage', W.DWORD), ('pid', W.DWORD),
                ('heap', ctypes.c_size_t), ('module', W.DWORD), ('threads', W.DWORD),
                ('parent', W.DWORD), ('priority', W.LONG), ('flags', W.DWORD), ('name', W.WCHAR * 260)]


class UnicodeString(ctypes.Structure):
    _fields_ = [('length', W.USHORT), ('maximum', W.USHORT), ('buffer', ctypes.c_void_p)]


class WindowsReadOnly:
    """Toolhelp + query-only handles. Inaccessible optional fields stay UNKNOWN."""
    def __init__(self, secrets=()):
        if os.name != 'nt':
            raise OSError('Windows observation unavailable')
        self.k = ctypes.WinDLL('kernel32', use_last_error=True)
        self.a = ctypes.WinDLL('advapi32', use_last_error=True)
        self.n = ctypes.WinDLL('ntdll', use_last_error=True)
        declarations = {
            'OpenProcess': ([W.DWORD, W.BOOL, W.DWORD], W.HANDLE),
            'CloseHandle': ([W.HANDLE], W.BOOL),
            'CreateToolhelp32Snapshot': ([W.DWORD, W.DWORD], W.HANDLE),
            'Process32FirstW': ([W.HANDLE, ctypes.POINTER(Entry)], W.BOOL),
            'Process32NextW': ([W.HANDLE, ctypes.POINTER(Entry)], W.BOOL),
            'GetProcessTimes': ([W.HANDLE] + [ctypes.POINTER(W.FILETIME)] * 4, W.BOOL),
            'QueryFullProcessImageNameW': ([W.HANDLE, W.DWORD, W.LPWSTR, ctypes.POINTER(W.DWORD)], W.BOOL),
            'GetProcessAffinityMask': ([W.HANDLE, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)], W.BOOL),
            'GetPriorityClass': ([W.HANDLE], W.DWORD),
            'GetProcessGroupAffinity': ([W.HANDLE, ctypes.POINTER(W.USHORT), ctypes.POINTER(W.USHORT)], W.BOOL),
            'GetProcessDefaultCpuSets': ([W.HANDLE, ctypes.POINTER(W.ULONG), W.ULONG, ctypes.POINTER(W.ULONG)], W.BOOL),
            'GetActiveProcessorGroupCount': ([], W.WORD),
        }
        for name, (args, result) in declarations.items():
            fn = getattr(self.k, name)
            fn.argtypes, fn.restype = args, result
        self.a.OpenProcessToken.argtypes = [W.HANDLE, W.DWORD, ctypes.POINTER(W.HANDLE)]
        self.a.OpenProcessToken.restype = W.BOOL
        self.a.GetTokenInformation.argtypes = [W.HANDLE, ctypes.c_int, ctypes.c_void_p, W.DWORD, ctypes.POINTER(W.DWORD)]
        self.a.GetTokenInformation.restype = W.BOOL
        self.a.GetLengthSid.argtypes, self.a.GetLengthSid.restype = [ctypes.c_void_p], W.DWORD
        self.n.NtQueryInformationProcess.argtypes = [W.HANDLE, ctypes.c_int, ctypes.c_void_p, W.ULONG, ctypes.POINTER(W.ULONG)]
        self.n.NtQueryInformationProcess.restype = W.LONG
        self.secrets = tuple(secrets)
        self.cache = {}
        h = self.k.OpenProcess(0x1000, False, os.getpid())
        if not h:
            raise OSError('observer query handle unavailable')
        try:
            self.own_sid = self.sid(h)
        finally:
            self.k.CloseHandle(h)
        if self.own_sid is None:
            raise OSError('observer owner unavailable')

    def sid(self, handle):
        token, size = W.HANDLE(), W.DWORD()
        if not self.a.OpenProcessToken(handle, 8, ctypes.byref(token)):
            return None
        try:
            self.a.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
            if not 0 < size.value < 65536:
                return None
            buf = ctypes.create_string_buffer(size.value)
            if not self.a.GetTokenInformation(token, 1, buf, size, ctypes.byref(size)):
                return None
            pointer = ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p))[0]
            length = self.a.GetLengthSid(pointer)
            return hashlib.sha256(ctypes.string_at(pointer, length)).digest() if 0 < length < 1024 else None
        finally:
            self.k.CloseHandle(token)

    def command(self, handle):
        # Optional native query; OS version/access failure does not become a
        # fabricated command. Pointer is validated inside the returned buffer.
        size = W.ULONG()
        self.n.NtQueryInformationProcess(handle, 60, None, 0, ctypes.byref(size))
        if not ctypes.sizeof(UnicodeString) <= size.value <= 131072:
            return 'UNKNOWN'
        buf = ctypes.create_string_buffer(size.value)
        if self.n.NtQueryInformationProcess(handle, 60, buf, size, ctypes.byref(size)) < 0:
            return 'UNKNOWN'
        value = ctypes.cast(buf, ctypes.POINTER(UnicodeString)).contents
        start, end = ctypes.addressof(buf), ctypes.addressof(buf) + len(buf)
        if not value.buffer or value.length % 2 or not start <= value.buffer <= end - value.length:
            return 'UNKNOWN'
        raw = ctypes.string_at(value.buffer, value.length).decode('utf-16-le')
        return redact_command(raw, self.secrets)

    def entries(self):
        h = self.k.CreateToolhelp32Snapshot(2, 0)
        if h in (None, ctypes.c_void_p(-1).value):
            raise OSError('process snapshot unavailable')
        rows = {}
        try:
            entry = Entry()
            entry.size = ctypes.sizeof(entry)
            ok = self.k.Process32FirstW(h, ctypes.byref(entry))
            while ok:
                rows[entry.pid] = dict(pid=entry.pid, parent=entry.parent, threads=entry.threads, name=entry.name)
                ok = self.k.Process32NextW(h, ctypes.byref(entry))
            if ctypes.get_last_error() != 18:
                raise OSError('incomplete snapshot')
            return rows
        finally:
            self.k.CloseHandle(h)

    def read(self, entry):
        row = dict(entry, born='UNKNOWN', affinity='UNKNOWN', owner='UNKNOWN', image='UNKNOWN',
                   groups='UNKNOWN', cpu_sets='UNKNOWN', cpu_100ns='UNKNOWN', priority='UNKNOWN', command='UNKNOWN')
        handle = self.k.OpenProcess(0x1000, False, entry['pid'])
        if not handle:
            return row
        try:
            times = [W.FILETIME() for _ in range(4)]
            if not self.k.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
                return row
            to_int = lambda t: (t.dwHighDateTime << 32) | t.dwLowDateTime
            row['born'], row['cpu_100ns'] = to_int(times[0]), to_int(times[2]) + to_int(times[3])
            # Reconcile the live handle with Toolhelp's PPID. Native class 0 is
            # query-only; 6 pointer-width fields represent PROCESS_BASIC_INFORMATION.
            basic = (ctypes.c_size_t * 6)()
            returned = W.ULONG()
            if self.n.NtQueryInformationProcess(handle,0,basic,ctypes.sizeof(basic),ctypes.byref(returned)) < 0 or basic[4] != entry['pid'] or basic[5] != entry['parent']:
                row['identity_status'] = 'UNKNOWN'
                return row
            row['identity_status'] = 'HANDLE_PARENT_VERIFIED'
            mask, system = ctypes.c_size_t(), ctypes.c_size_t()
            if self.k.GetProcessAffinityMask(handle, ctypes.byref(mask), ctypes.byref(system)):
                row['affinity'] = mask.value
            count = W.USHORT(64)
            groups = (W.USHORT * 64)()
            if self.k.GetProcessGroupAffinity(handle, ctypes.byref(count), groups):
                row['groups'] = list(groups[:count.value])
            sets, required = (W.ULONG * 1024)(), W.ULONG()
            if self.k.GetProcessDefaultCpuSets(handle, sets, 1024, ctypes.byref(required)):
                row['cpu_sets'] = list(sets[:required.value])
            row['priority'] = self.k.GetPriorityClass(handle) or 'UNKNOWN'
            key = entry['pid'], row['born']
            if key not in self.cache:
                size, path = W.DWORD(32768), ctypes.create_unicode_buffer(32768)
                image = path.value if self.k.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)) else 'UNKNOWN'
                if image != 'UNKNOWN' and ntpath.basename(image).lower() != entry['name'].lower():
                    row['identity_status'] = 'UNKNOWN'
                    return row
                sid = self.sid(handle)
                self.cache[key] = dict(image=image, owner='UNKNOWN' if sid is None else 'SAME_USER' if sid == self.own_sid else 'OTHER_USER',
                                       command=self.command(handle))
            row.update(self.cache[key])
            return row
        finally:
            self.k.CloseHandle(handle)

    def snapshot(self, tracked_pids):
        entries = self.entries()
        descendants = set(tracked_pids) & entries.keys()
        while True:
            before = set(descendants)
            descendants.update(pid for pid,row in entries.items() if row['parent'] in descendants)
            if before == descendants:
                break
        chosen = set(descendants)
        chosen.update(pid for pid, row in entries.items() if row['name'].lower() in NATIVE_NAMES or 'liveupdate' in row['name'].lower())
        # Both lineage ancestors and descendants; no broad command-line export.
        while True:
            before = set(chosen)
            chosen.update(row['parent'] for pid, row in entries.items() if pid in chosen and row['parent'] in entries)
            if chosen == before:
                break
        return [self.read(entries[pid]) for pid in sorted(chosen)]
