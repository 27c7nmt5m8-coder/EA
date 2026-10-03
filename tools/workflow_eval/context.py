"""Read-only Git evidence and explicit context selection, without silent truncation."""
import hashlib
import json
from pathlib import Path
import re
import subprocess


def digest(value):
    return hashlib.sha256(value).hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.DEVNULL)


def local_path(root, name):
    root = Path(root).resolve()
    path = (root / name).resolve()
    if path == root or not path.is_relative_to(root):
        raise ValueError('path_outside_repository')
    return path


def fingerprint(root):
    names = git(root, 'ls-files', '-z') + git(root, 'ls-files', '--others', '--exclude-standard', '-z')
    hashes = {}
    for raw in names.split(b'\0'):
        if not raw:
            continue
        name = raw.decode('utf-8')
        if name.startswith(('.workflow-eval/', '.validation/')):
            continue
        path = local_path(root, name)
        hashes[name] = digest(path.read_bytes()) if path.is_file() else None
    return digest(json.dumps(hashes, sort_keys=True).encode('utf-8') + b'\0INDEX\0'
                  + git(root, 'ls-files', '--stage', '-z'))


def build_bundle(root, base, related, task):
    root = Path(root).resolve()
    if base.startswith('-'):
        raise ValueError('invalid_base')
    base_sha = git(root, 'rev-parse', '--verify', base + '^{commit}').decode().strip()
    head = git(root, 'rev-parse', 'HEAD').decode().strip()
    records = git(root, 'diff', '--name-status', '-z', '--find-renames', base_sha, '--').split(b'\0')
    changed_names = []
    index = 0
    while index < len(records) and records[index]:
        status = records[index]
        count = 2 if status.startswith((b'R', b'C')) else 1
        changed_names.extend(records[index+1:index+1+count])
        index += 1 + count
    changed = b'\0'.join(changed_names) + b'\0'
    untracked = git(root, 'ls-files', '--others', '--exclude-standard', '-z')
    untracked_names = {v.decode('utf-8') for v in untracked.split(b'\0') if v
                       and not v.startswith((b'.workflow-eval/', b'.validation/'))}
    paths = sorted({v.decode('utf-8') for v in (changed + untracked).split(b'\0') if v
                    and not v.startswith((b'.workflow-eval/', b'.validation/'))})
    patch = git(root, 'diff', '--no-ext-diff', '--no-textconv', '--binary', base_sha, '--').decode('utf-8', errors='replace')
    from .triage import SENSITIVE, PROTECTED
    blocks = []
    unknown = []
    for name in sorted(set(paths + list(related))):
        path = local_path(root, name)
        if not path.is_file():
            unknown.append(name)
            continue
        try:
            raw = path.read_bytes()
            content = raw.decode('utf-8')
        except UnicodeError:
            unknown.append(name)
            continue
        if SENSITIVE.search(content):
            raise ValueError('sensitive_context')
        blocks.append(dict(path=name, sha256=digest(raw), text=content,
                           includes=re.findall(r'^\s*#include\s*["<]([^">]+)', content, re.M),
                           interface_lines=[line for line in content.splitlines()
                                            if re.match(r'\s*(input |enum |class |struct )', line)]))
    if SENSITIVE.search(task) or SENSITIVE.search(patch):
        raise ValueError('sensitive_context')
    changed_lines = sum(line.startswith(('+', '-')) and not line.startswith(('+++', '---')) for line in patch.splitlines())
    changed_lines += sum(len(b['text'].splitlines()) for b in blocks if b['path'] in untracked_names)
    if untracked_names & set(unknown):
        changed_lines = None
    return dict(schema_version=3, base=base_sha, head=head, fingerprint=fingerprint(root),
                index_sha256=digest(git(root, 'ls-files', '--stage', '-z')),
                changed_paths=paths, changed_lines=changed_lines, patch=patch, blocks=blocks, task=task,
                dependency='unknown' if unknown or any(not p.startswith('docs/') for p in paths) else 'known',
                expansion_required=unknown,
                protected=bool(PROTECTED.search('\n'.join([task, patch] + [b['text'] for b in blocks]))),
                status_porcelain=git(root, 'status', '--porcelain=v1', '-z', '--', '.',
                                     ':(exclude).workflow-eval', ':(exclude).validation').decode('utf-8'))


def is_current(root, bundle):
    return (git(root, 'rev-parse', 'HEAD').decode().strip() == bundle['head']
            and fingerprint(root) == bundle['fingerprint'])


COMMON_FIELDS = {'base', 'head', 'fingerprint', 'index_sha256', 'changed_paths',
                 'changed_lines', 'patch', 'task', 'dependency', 'expansion_required',
                 'protected', 'status_porcelain'}
BUNDLE_FIELDS = COMMON_FIELDS | {'schema_version', 'blocks'}
PACKET_FIELDS = COMMON_FIELDS | {'schema_version', 'source_bundle_schema', 'blocks',
                               'reuse_policy', 'reused_paths',
                               'fresh_context_requires_expansion', 'verification'}
REUSE_POLICY = 'exact_sha_unchanged_related_known_unprotected_only'
VERIFY_SCALARS = {'status', 'full_gate', 'authoritative_release', 'commit', 'branch', 'dirty', 'product_scope'}
VERIFY_NESTED = {'ci_native', 'metaeditor', 'preflight'}
VERIFY_DETAIL_FIELDS = {'status', 'equivalence', 'commit', 'branch', 'reason'}
VERIFY_STATES = {'PASS', 'FAIL', 'BLOCKED', 'UNKNOWN', 'NOT_RUN', 'INCOMPLETE', 'DELEGATED_TO_CI'}


def _safe_evidence(value):
    """Inspect JSON keys and decoded values, not quote-dependent JSON regexes."""
    from .triage import SENSITIVE
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or re.fullmatch(r'(?i)(token|authorization|bearer)', key) or re.search(
                    r'(?i)(password|secret|credential|api[_ -]?key|access[_ -]?token|'
                    r'account[_ -]?(?:id|number|balance))', key):
                raise ValueError('sensitive_evidence')
            _safe_evidence(item)
    elif isinstance(value, list):
        for item in value:
            _safe_evidence(item)
    elif isinstance(value, str):
        if SENSITIVE.search(value) or re.search(
                r'''(?i)(password|secret|credential|api[_ -]?key|access[_ -]?token|account[_ -]?(?:id|number|balance))["']?\s*[:=]''', value):
            raise ValueError('sensitive_evidence')
        if value.lstrip().startswith(('{', '[')):
            try:
                decoded = json.loads(value)
            except ValueError:
                pass
            else:
                _safe_evidence(decoded)


def _strings(value):
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def _path_name(name):
    return (isinstance(name, str) and bool(name) and not name.startswith('/')
            and not re.search(r'[\\:\x00-\x1f]', name)
            and all(part not in ('', '.', '..') for part in name.split('/')))


def _metadata(value, schema):
    if (not isinstance(value, dict) or type(value.get('schema_version')) is not int
            or value['schema_version'] != schema):
        raise ValueError('invalid_context_schema')
    for key, length in [('base', 40), ('head', 40), ('fingerprint', 64), ('index_sha256', 64)]:
        if not isinstance(value.get(key), str) or not re.fullmatch(r'[0-9a-f]{%d}' % length, value[key]):
            raise ValueError('invalid_context_identity')
    for key in ('changed_paths', 'expansion_required'):
        paths = value.get(key)
        if not _strings(paths) or len(paths) != len(set(paths)) or not all(_path_name(p) for p in paths):
            raise ValueError('invalid_context_paths')
    if (value.get('dependency') not in ('known', 'unknown')
            or type(value.get('protected')) is not bool
            or not all(isinstance(value.get(k), str) for k in ('task', 'patch', 'status_porcelain'))
            or not isinstance(value.get('blocks'), list)):
        raise ValueError('invalid_context_metadata')
    lines = value.get('changed_lines')
    if lines is not None and (type(lines) is not int or lines < 0):
        raise ValueError('invalid_context_size')
    if value['dependency'] == 'known' and (value['expansion_required'] or
                                         any(not p.startswith('docs/') for p in value['changed_paths'])):
        raise ValueError('invalid_dependency_claim')
    _safe_evidence({k: value[k] for k in COMMON_FIELDS})


def _block(block, full):
    fields = {'path', 'sha256', 'includes', 'interface_lines'}
    if (not isinstance(block, dict) or not _path_name(block.get('path'))
            or not isinstance(block.get('sha256'), str)
            or not re.fullmatch(r'[0-9a-f]{64}', block['sha256'])
            or not _strings(block.get('includes')) or not _strings(block.get('interface_lines'))):
        raise ValueError('invalid_context_block')
    if full:
        text = block.get('text')
        if not isinstance(text, str) or digest(text.encode('utf-8')) != block['sha256']:
            raise ValueError('context_body_hash_mismatch')
        if (block['includes'] != re.findall(r'^\s*#include\s*["<]([^">]+)', text, re.M)
                or block['interface_lines'] != [line for line in text.splitlines()
                                               if re.match(r'\s*(input |enum |class |struct )', line)]):
            raise ValueError('context_body_metadata_mismatch')
        fields.add('text')
    return fields


def _validate_bundle(bundle, root=None):
    if not isinstance(bundle, dict) or set(bundle) != BUNDLE_FIELDS:
        raise ValueError('invalid_bundle')
    _metadata(bundle, 3)
    _safe_evidence(bundle['blocks'])
    names = []
    for block in bundle['blocks']:
        if set(block) != _block(block, True):
            raise ValueError('invalid_bundle_block')
        names.append(block['path'])
    if (len(names) != len(set(names)) or
            not set(bundle['changed_paths']).issubset(set(names) | set(bundle['expansion_required']))):
        raise ValueError('missing_or_duplicate_context')
    from .triage import PROTECTED
    if (not bundle['protected'] and PROTECTED.search(
            '\n'.join([bundle['task'], bundle['patch']] + [b['text'] for b in bundle['blocks']]))):
        raise ValueError('invalid_protected_claim')
    if root is not None:
        if not is_current(root, bundle):
            raise ValueError('stale_bundle')
        # Current identity alone does not prove changed paths/scope/body claims.
        related = names + bundle['expansion_required']
        actual = build_bundle(root, bundle['base'], related, bundle['task'])
        if actual != bundle or not is_current(root, actual):
            raise ValueError('bundle_repository_mismatch')


def _validate_packet(packet):
    if not isinstance(packet, dict) or set(packet) != PACKET_FIELDS:
        raise ValueError('invalid_packet')
    _metadata(packet, 1)
    if (type(packet['source_bundle_schema']) is not int or packet['source_bundle_schema'] != 3
            or packet['reuse_policy'] != REUSE_POLICY):
        raise ValueError('invalid_packet_policy')
    names, reused = [], []
    for block in packet['blocks']:
        if not isinstance(block, dict) or block.get('content_mode') not in ('full', 'reused_exact'):
            raise ValueError('invalid_packet_block')
        full = block['content_mode'] == 'full'
        fields = _block(block, full) | {'content_mode'}
        if not full:
            fields.add('content_handle')
            if block.get('content_handle') != f"{block['path']}@sha256:{block['sha256']}":
                raise ValueError('invalid_content_handle')
            reused.append(block['path'])
        if set(block) != fields:
            raise ValueError('invalid_packet_block')
        # Validated path@sha256 handles contain '@', which is not an email.
        _safe_evidence({k: v for k, v in block.items() if k != 'content_handle'})
        names.append(block['path'])
    if (len(names) != len(set(names)) or packet['reused_paths'] != sorted(reused)
            or type(packet['fresh_context_requires_expansion']) is not bool
            or packet['fresh_context_requires_expansion'] != bool(reused)
            or not set(packet['changed_paths']).issubset(set(names) | set(packet['expansion_required']))
            or (reused and (packet['protected'] or packet['dependency'] != 'known'
                            or packet['expansion_required'] or set(reused) & set(packet['changed_paths'])))):
        raise ValueError('invalid_packet_reuse')
    verification = packet['verification']
    _safe_evidence(verification)
    if verification is not None and (
            not isinstance(verification, dict) or set(verification) != {'sha256', 'summary', 'requires_full_evidence'}
            or not isinstance(verification.get('sha256'), str)
            or not re.fullmatch(r'[0-9a-f]{64}', verification['sha256'])
            or not isinstance(verification.get('summary'), dict)
            or verification['requires_full_evidence'] is not True):
        raise ValueError('invalid_verification_digest')
    if verification is not None:
        _validate_verification_summary(verification['summary'])


def _validate_verification_summary(summary):
    if not isinstance(summary, dict) or not set(summary).issubset(VERIFY_SCALARS | VERIFY_NESTED | {'gates'}):
        raise ValueError('invalid_verification_summary')
    for key, value in summary.items():
        if key in VERIFY_NESTED:
            if not isinstance(value, dict) or not set(value).issubset(VERIFY_DETAIL_FIELDS):
                raise ValueError('invalid_verification_summary')
            for field, item in value.items():
                if item is not None and not isinstance(item, str):
                    raise ValueError('invalid_verification_summary')
                if field == 'status' and item not in VERIFY_STATES:
                    raise ValueError('invalid_verification_summary')
                if field == 'equivalence' and item not in ('EQUIVALENT', 'UNKNOWN'):
                    raise ValueError('invalid_verification_summary')
        elif key == 'gates':
            if not _strings(value) or any(v not in VERIFY_STATES for v in value):
                raise ValueError('invalid_verification_summary')
        elif key == 'dirty':
            if type(value) is not bool:
                raise ValueError('invalid_verification_summary')
        elif key in ('status', 'full_gate', 'authoritative_release', 'product_scope'):
            if not isinstance(value, str) or value not in VERIFY_STATES:
                raise ValueError('invalid_verification_summary')
        elif value is not None and not isinstance(value, str):
            raise ValueError('invalid_verification_summary')
    _safe_evidence(summary)


def _verification_digest(verification):
    if verification is None:
        return None
    if not isinstance(verification, dict):
        raise ValueError('invalid_verification')
    raw = json.dumps(verification, ensure_ascii=False, sort_keys=True,
                     separators=(',', ':'), allow_nan=False)
    _safe_evidence(verification)
    summary = {}
    for key in VERIFY_SCALARS | {'gates'}:
        if key in verification:
            summary[key] = verification[key]
    for key in VERIFY_NESTED:
        if key not in verification:
            continue
        value = verification[key]
        if not isinstance(value, dict):
            raise ValueError('invalid_verification')
        picked = {name: value[name] for name in VERIFY_DETAIL_FIELDS if name in value}
        if picked:
            summary[key] = picked
    _validate_verification_summary(summary)
    # The digest identifies an external record; it cannot prove its claims.
    return dict(sha256=digest(raw.encode('utf-8')), summary=summary, requires_full_evidence=True)


def _prior_block_texts(prior):
    if prior is None:
        return {}
    _validate_packet(prior)
    return {block['path']: block['text'] for block in prior['blocks'] if block['content_mode'] == 'full'}


def build_context_packet(bundle, prior=None, verification=None, *, root=None, recipient_has_content=False):
    """Create a content-addressed agent/reviewer packet.

    Exact-hash reuse is deliberately narrow: only unchanged related context may
    be replaced by a handle, and never when the task is protected, dependency
    scope is unknown, or source expansion is already required. Changed files
    always retain full text. Fresh recipients receive full text by default.
    Handle output requires a current repository and an explicit caller assertion
    that this recipient already retains the prior full text. Prior handles alone
    are insufficient. No digest substitutes for review or validation evidence.
    """
    _validate_bundle(bundle, root)
    if type(recipient_has_content) is not bool or (recipient_has_content and root is None):
        raise ValueError('retained_context_requires_current_repository')
    prior_texts = _prior_block_texts(prior)
    reuse_enabled = (recipient_has_content and bundle['dependency'] == 'known' and not bundle['protected']
                     and not bundle['expansion_required'])
    changed = set(bundle['changed_paths'])
    blocks = []
    reused = []
    for source in bundle['blocks']:
        if (not isinstance(source, dict) or not isinstance(source.get('path'), str)
                or not re.fullmatch(r'[0-9a-f]{64}', str(source.get('sha256', '')))
                or not isinstance(source.get('text'), str)):
            raise ValueError('invalid_bundle_block')
        path = source['path']
        record = dict(path=path, sha256=source['sha256'],
                      includes=list(source.get('includes', [])),
                      interface_lines=list(source.get('interface_lines', [])))
        can_reuse = (reuse_enabled and path not in changed
                     and prior_texts.get(path) == source['text'])
        if can_reuse:
            record.update(content_mode='reused_exact',
                          content_handle=f"{path}@sha256:{source['sha256']}")
            reused.append(path)
        else:
            record.update(content_mode='full', text=source['text'])
        blocks.append(record)
    return dict(schema_version=1, source_bundle_schema=bundle['schema_version'],
                base=bundle['base'], head=bundle['head'], fingerprint=bundle['fingerprint'],
                index_sha256=bundle['index_sha256'], task=bundle['task'], patch=bundle['patch'],
                changed_paths=list(bundle['changed_paths']), changed_lines=bundle['changed_lines'],
                dependency=bundle['dependency'], protected=bundle['protected'],
                status_porcelain=bundle['status_porcelain'],
                expansion_required=list(bundle['expansion_required']),
                reuse_policy=REUSE_POLICY,
                reused_paths=sorted(reused), fresh_context_requires_expansion=bool(reused), blocks=blocks,
                verification=_verification_digest(verification))


def expand_context_packet(packet, bundle, paths=None, *, root=None):
    """Restore exact text for selected reused handles from the current bundle."""
    _validate_packet(packet)
    _validate_bundle(bundle, root)
    if any(packet[k] != bundle[k] for k in COMMON_FIELDS):
        raise ValueError('packet_bundle_mismatch')
    sources = {b['path']: b for b in bundle['blocks']}
    if set(sources) != {b['path'] for b in packet['blocks']}:
        raise ValueError('packet_bundle_mismatch')
    reused = set(packet['reused_paths'])
    if reused and root is None:
        raise ValueError('expansion_requires_current_repository')
    if paths is not None and not _strings(paths):
        raise ValueError('invalid_expansion_path')
    targets = reused if paths is None else set(paths)
    if not targets.issubset(reused):
        raise ValueError('invalid_expansion_path')
    result = dict(packet)
    result['blocks'] = []
    for block in packet.get('blocks', []):
        source = sources[block['path']]
        if (any(source[k] != block[k] for k in ('sha256', 'includes', 'interface_lines'))
                or (block['content_mode'] == 'full' and source['text'] != block['text'])):
            raise ValueError('reused_content_mismatch')
        record = dict(block)
        if block.get('path') in targets and block.get('content_mode') == 'reused_exact':
            source = sources.get(block['path'])
            if (source is None or source.get('sha256') != block.get('sha256')
                    or not isinstance(source.get('text'), str)):
                raise ValueError('reused_content_mismatch')
            record.pop('content_handle', None)
            record.update(content_mode='full', text=source['text'])
        result['blocks'].append(record)
    result['reused_paths'] = sorted(reused - targets)
    result['fresh_context_requires_expansion'] = bool(result['reused_paths'])
    return result


def select_context(task):
    blocks = {b['id']: b['text'] for b in task['context_blocks']}
    if len(blocks) != len(task['context_blocks']):
        raise ValueError('duplicate_context_id')
    selected = task['selected_context_ids']
    missing = sorted(set(task['required_context_ids']) - (set(selected) & set(blocks)))
    missing += sorted(set(selected) - set(blocks))
    texts = []
    seen = set()
    for context_id in selected:
        if context_id not in blocks:
            continue
        text = blocks[context_id]
        # Different IDs can identify distinct sources even with identical text.
        if context_id in seen:
            continue
        seen.add(context_id)
        texts.append(text)
    return dict(text='\n\n'.join(texts), missing_context=sorted(set(missing)))


def expand_context(task):
    initial = select_context(task)
    expanded = dict(task, selected_context_ids=list(dict.fromkeys(
        task['selected_context_ids'] + task['required_context_ids'])))
    result = select_context(expanded)
    result['initial_missing_context'] = initial['missing_context']
    return result
