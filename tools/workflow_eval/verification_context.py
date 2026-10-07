"""Lossless, artifact-backed verification transport; no gate or provider execution.

``runner_result`` is an explicit acquisition contract: the caller supplies a
structured record produced by its trusted runner, not an arbitrary user's PASS
claim. This module verifies consistency and availability, not authorship. A
manifest/hash alone never certifies PASS. Raw logs can contradict a runner
record but cannot establish successful execution or counts.
"""
import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

from .context import _path_name, _safe_evidence
from .serialization import canonical_json


FIELDS = ('source', 'tree', 'scope', 'command', 'platform', 'toolchain',
          'exit_code', 'status', 'passed', 'failed', 'warnings', 'ci_identity',
          'equivalence', 'recorded_at', 'protected', 'dependency')
CURRENT_FIELDS = ('source', 'tree', 'scope', 'command', 'platform', 'toolchain',
                  'equivalence', 'protected', 'dependency')
MANIFEST_FIELDS = set(FIELDS) | {'schema_version', 'evidence_kind', 'artifacts', 'missing_reasons'}
STATES = {'PASS', 'FAIL', 'BLOCKED', 'UNKNOWN', 'NOT_RUN', 'INCOMPLETE', 'DELEGATED_TO_CI'}


def _artifact_path(root, name):
    if not _path_name(name):
        raise ValueError('invalid_artifact_path')
    root = Path(root).resolve(strict=True)
    candidate = root
    for part in name.split('/'):
        candidate = candidate / part
        if candidate.is_symlink() or getattr(candidate, 'is_junction', lambda: False)():
            raise ValueError('unsafe_artifact_path')
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root) or resolved == root:
        raise ValueError('unsafe_artifact_path')
    return candidate


def _read(root, name):
    try:
        path = _artifact_path(root, name)
        raw = path.read_bytes()
    except OSError:
        return None, None, 'artifact_unavailable'
    # Decode strictly: replacement characters cannot stand in for original bytes.
    try:
        text = raw.decode('utf-8')
    except UnicodeError:
        return raw, None, 'artifact_not_utf8'
    _safe_evidence(text)
    return raw, text, None


def _record(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate_record_key')
            result[key] = value
        return result
    try:
        value = json.loads(text, object_pairs_hook=unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite_record')))
        canonical_json(value)
    except (ValueError, TypeError):
        return None
    if not isinstance(value, dict):
        return None
    _safe_evidence(value)
    return value


def _metadata(record):
    value = {name: None for name in FIELDS}
    if record is not None:
        for name in FIELDS:
            value[name] = copy.deepcopy(record.get(name))
        # Existing run_all records are retained as evidence, without inventing
        # tree, command, exit status, counts, toolchain or CI equivalence.
        if value['source'] is None:
            value['source'] = record.get('commit')
        if value['status'] is None:
            value['status'] = record.get('full_gate')
        if value['platform'] is None:
            value['platform'] = copy.deepcopy(record.get('environment'))
        if value['ci_identity'] is None:
            ci = record.get('ci_native')
            if isinstance(ci, dict) and ci.get('run_id') is not None:
                value['ci_identity'] = copy.deepcopy(ci)
    value['missing_reasons'] = {name: 'not_recorded_in_original' for name in FIELDS if value[name] is None}
    return value


def build_verification_manifest(artifact_root, record_path, *, log_paths=(), evidence_kind='runner_result'):
    """Read and screen original local artifacts, retaining their exact SHA-256.

    Paths are relative to the caller's artifact root. This API never overwrites
    originals or caches text. Missing values remain null with recorded reasons.
    Declared ``log_paths`` in the runner record establish required log scope;
    absent declarations disable manifest-only transport.
    """
    if evidence_kind not in ('runner_result', 'raw_log'):
        raise ValueError('invalid_verification_evidence_kind')
    if not isinstance(log_paths, (list, tuple)) or not all(isinstance(p, str) for p in log_paths):
        raise ValueError('invalid_artifact_paths')
    paths = [record_path, *log_paths]
    if len(paths) != len(set(paths)):
        raise ValueError('duplicate_artifact_path')
    artifacts = []
    record = None
    for index, name in enumerate(paths):
        raw, text, problem = _read(artifact_root, name)
        artifacts.append(dict(path=name, role='record' if index == 0 else 'log',
                              sha256=hashlib.sha256(raw).hexdigest() if raw is not None else None,
                              size_bytes=len(raw) if raw is not None else None,
                              unavailable_reason=problem))
        if index == 0 and evidence_kind == 'runner_result' and text is not None:
            record = _record(text)
    result = dict(schema_version=1, evidence_kind=evidence_kind, artifacts=artifacts, **_metadata(record))
    _safe_evidence(result)
    return result


def _sha(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{40}', value) is not None


def _nested_problems(value, source=None, tree=None):
    if isinstance(value, dict):
        if source is None:
            source = value.get('source', value.get('commit'))
        if tree is None:
            tree = value.get('tree')
        for name, item in value.items():
            expected = source if name in ('source', 'commit') else tree if name == 'tree' else None
            if expected is not None and canonical_json(item) != canonical_json(expected):
                yield 'contradictory_nested_source'
            if name in ('status', 'full_gate') and item != 'PASS':
                yield 'contradictory_nested_status'
            if name in ('unexplained', 'material_uncertainty', 'missing_evidence', 'blocked_judgment',
                        'stale', 'stale_evidence') and item is not False:
                yield 'unresolved_record_evidence'
            if name in ('exit_code', 'failed', 'missing_context_count') and (
                    type(item) is not int or item != 0):
                yield 'contradictory_nested_failure_or_missing_context'
            if name == 'passed' and (type(item) is not int or item < 0):
                yield 'invalid_nested_count'
            if name == 'warnings' and (not isinstance(item, list) or any(
                    not isinstance(w, dict) or w.get('material') is not False
                    or not isinstance(w.get('text'), str) for w in item)):
                yield 'material_or_unclassified_nested_warning'
            if name == 'missing_context_ids' and item != []:
                yield 'missing_record_context'
            if name == 'acquired' and item is not True:
                yield 'unacquired_record_evidence'
            if name == 'protected' and item is not False:
                yield 'protected_or_uncertain_record_scope'
            if name == 'dependency' and item != 'known':
                yield 'unknown_record_dependency'
            yield from _nested_problems(item, source, tree)
    elif isinstance(value, list):
        for item in value:
            yield from _nested_problems(item, source, tree)


def _log_problems(text, passed=None, failed=None):
    # Recognize the transport prefix used by GitHub Actions without modifying
    # the original artifact or interpreting successful log text as proof.
    text = re.sub(r'(?m)^\s*\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}'
                  r'(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\s+', '', text)
    if re.search(r'(?im)^\s*(?:FAIL(?:ED|URE)?|ERROR|BLOCKED|WARNING)\b', text):
        yield 'unexplained_log_diagnostic'
    if type(passed) is int and type(failed) is int:
        totals = re.findall(r'(?im)^\s*Ran (\d+) tests?\b', text)
        counts = re.findall(r'(?i)\b(passed|failed)\s*[:=]\s*(\d+)\b', text)
        if any(int(n) != passed + failed for n in totals) or any(
                int(n) != (passed if label.lower() == 'passed' else failed) for label, n in counts):
            yield 'log_count_mismatch'


def _result_reasons(record, metadata, logs):
    reasons = []
    if record is None:
        return ['missing_structured_runner_evidence']
    try:
        timestamp = metadata['recorded_at']
        if not isinstance(timestamp, str) or not timestamp.strip():
            raise ValueError('timestamp_missing')
        recorded = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        if recorded.tzinfo is None or recorded.utcoffset() is None:
            raise ValueError('timestamp_timezone_unknown')
    except (ValueError, TypeError, OverflowError):
        reasons.append('missing_or_invalid_record_timestamp')
    if metadata['protected'] is not False or metadata['dependency'] != 'known':
        reasons.append('protected_unknown_or_unclassified_scope')
    if metadata['status'] not in STATES or metadata['status'] != 'PASS':
        reasons.append('result_not_pass')
    if type(metadata['exit_code']) is not int or metadata['exit_code'] != 0:
        reasons.append('exit_status_not_success')
    passed, failed = metadata['passed'], metadata['failed']
    if type(passed) is not int or passed < 0 or type(failed) is not int or failed != 0:
        reasons.append('counts_missing_or_inconsistent')
    if not _sha(metadata['source']) or not _sha(metadata['tree']):
        reasons.append('invalid_record_identity')
    for name in CURRENT_FIELDS[2:]:
        if metadata[name] is None or metadata[name] in ('UNKNOWN', 'NOT_RUN', 'INCOMPLETE'):
            reasons.append('missing_or_unknown_' + name)
    scope = metadata['scope']
    command = metadata['command']
    if not ((isinstance(scope, str) and scope.strip()) or
            (isinstance(scope, list) and scope and all(_path_name(p) for p in scope)) or
            (isinstance(scope, dict) and scope)):
        reasons.append('invalid_scope')
    if not ((isinstance(command, str) and command.strip()) or
            (isinstance(command, list) and command and all(isinstance(p, str) and p for p in command))):
        reasons.append('invalid_command')
    for name in ('platform', 'toolchain'):
        value = metadata[name]
        if not ((isinstance(value, str) and value.strip() and value.upper() != 'UNKNOWN') or
                (isinstance(value, dict) and value)):
            reasons.append('invalid_' + name)
    if metadata['equivalence'] not in ('LOCAL_ONLY', 'EQUIVALENT'):
        reasons.append('unknown_equivalence')
    ci = metadata['ci_identity']
    if ci is not None and (not isinstance(ci, dict) or not ci or
                           ci.get('commit', ci.get('head_sha')) != metadata['source'] or
                           ci.get('status') != 'PASS'):
        reasons.append('invalid_or_contradictory_ci_identity')
    warnings = metadata['warnings']
    if not isinstance(warnings, list):
        reasons.append('warnings_unknown')
    elif any(not isinstance(w, dict) or w.get('material') is not False or
             not isinstance(w.get('text'), str) for w in warnings):
        reasons.append('material_or_unclassified_warning')
    gates = record.get('gates')
    if gates is not None and (not isinstance(gates, list) or not gates or any(g != 'PASS' for g in gates)):
        reasons.append('contradictory_gate_evidence')
    if record.get('full_gate', 'PASS') != 'PASS':
        reasons.append('contradictory_gate_evidence')
    if record.get('commit', metadata['source']) != metadata['source']:
        reasons.append('contradictory_source_evidence')
    reasons.extend(_nested_problems(record))
    # Diagnostic recognition is conservative and negative-only. No parsed log
    # string, including an OK line, can establish counts or PASS.
    for text in logs:
        reasons.extend(_log_problems(text, passed, failed))
    return reasons


def verification_transport(artifact_root, manifest, *, current=None, reviewer_request=False,
                           xhigh=False, blocked_judgment=False, unexplained=False):
    """Acquire originals before selecting manifest-only or complete expansion.

    ``current`` must supply the actual current source/tree and checked scope,
    command, platform, toolchain and equivalence. Unknown evidence uses originals;
    missing/nontext originals block. All expansion retains the supplied manifest.
    ``verified_pass`` concerns this exact runner check, never release/EA safety.
    """
    _safe_evidence(manifest)
    _safe_evidence(current)
    canonical_json(manifest)
    canonical_json(current)
    if (not isinstance(manifest, dict) or set(manifest) != MANIFEST_FIELDS or
            type(manifest['schema_version']) is not int or manifest['schema_version'] != 1 or
            manifest['evidence_kind'] not in ('runner_result', 'raw_log') or
            not isinstance(manifest['artifacts'], list) or not manifest['artifacts']):
        raise ValueError('invalid_verification_manifest')
    options = dict(reviewer_request=reviewer_request, xhigh=xhigh,
                   blocked_judgment=blocked_judgment, unexplained=unexplained)
    if any(type(v) is not bool for v in options.values()):
        raise ValueError('invalid_expansion_request')
    reasons = [name for name, requested in options.items() if requested]
    originals, observed, record, unavailable = [], [], None, False
    names = []
    for index, artifact in enumerate(manifest['artifacts']):
        if (not isinstance(artifact, dict) or set(artifact) !=
                {'path', 'role', 'sha256', 'size_bytes', 'unavailable_reason'} or
                artifact['role'] != ('record' if index == 0 else 'log')):
            raise ValueError('invalid_verification_artifact')
        name = artifact['path']
        if name in names:
            raise ValueError('duplicate_artifact_path')
        names.append(name)
        raw, text, problem = _read(artifact_root, name)
        if problem:
            unavailable = True
            reasons.append(problem)
        if text is not None:
            originals.append(dict(path=name, text=text))
        actual = dict(path=name, role=artifact['role'],
                      sha256=hashlib.sha256(raw).hexdigest() if raw is not None else None,
                      size_bytes=len(raw) if raw is not None else None, unavailable_reason=problem)
        observed.append(actual)
        if canonical_json(actual) != canonical_json(artifact):
            reasons.append('artifact_hash_mismatch')
        if index == 0 and text is not None and manifest['evidence_kind'] == 'runner_result':
            record = _record(text)
    metadata = _metadata(record)
    if any(canonical_json(manifest[name]) != canonical_json(metadata[name])
           for name in (*FIELDS, 'missing_reasons')):
        reasons.append('record_manifest_mismatch')
    if record is not None:
        declared = record.get('log_paths')
        if not isinstance(declared, list) or not all(_path_name(p) for p in declared) or len(set(declared)) != len(declared):
            reasons.append('original_log_scope_unknown')
        elif sorted(declared) != sorted(names[1:]):
            # Acquire omitted declared originals too. Missing manifest references
            # cannot certify original log completeness even if bytes exist.
            reasons.append('original_log_scope_mismatch')
            unavailable = True
            for name in declared:
                if name in names:
                    continue
                raw, text, problem = _read(artifact_root, name)
                if problem:
                    reasons.append(problem)
                if text is not None:
                    originals.append(dict(path=name, text=text))
    if not isinstance(current, dict) or not _sha(current.get('source')) or not _sha(current.get('tree')):
        reasons.append('current_identity_missing_or_invalid')
    else:
        for name in CURRENT_FIELDS:
            if name not in current or canonical_json(current[name]) != canonical_json(metadata[name]):
                reasons.append('current_' + name + '_mismatch')
    logs = [item['text'] for item in originals if item['path'] != names[0]]
    reasons += _result_reasons(record, metadata, logs)
    # Re-read after acquisition: changed bytes during validation invalidate reuse.
    for artifact in observed:
        raw, text, problem = _read(artifact_root, artifact['path'])
        if problem:
            reasons.append(problem)
            unavailable = True
        elif hashlib.sha256(raw).hexdigest() != artifact['sha256']:
            reasons.append('artifact_changed_during_acquisition')
            unavailable = True
    reasons = list(dict.fromkeys(reasons))
    return dict(manifest=copy.deepcopy(manifest),
                route='blocked' if unavailable else 'original' if reasons else 'manifest',
                verified_pass=not reasons and not unavailable, reasons=reasons,
                originals=originals if reasons or unavailable else [])
