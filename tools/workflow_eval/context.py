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
            content = path.read_bytes().decode('utf-8')
        except UnicodeError:
            unknown.append(name)
            continue
        if SENSITIVE.search(content):
            raise ValueError('sensitive_context')
        blocks.append(dict(path=name, sha256=digest(path.read_bytes()), text=content,
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
                expansion_required=unknown, protected=bool(PROTECTED.search(task + patch + '\n'.join(b['text'] for b in blocks))),
                status_porcelain=git(root, 'status', '--porcelain=v1', '-z').decode('utf-8'))


def is_current(root, bundle):
    return (git(root, 'rev-parse', 'HEAD').decode().strip() == bundle['head']
            and fingerprint(root) == bundle['fingerprint'])


def _verification_digest(verification):
    if verification is None:
        return None
    if not isinstance(verification, dict):
        raise ValueError('invalid_verification')
    raw = json.dumps(verification, ensure_ascii=False, sort_keys=True,
                     separators=(',', ':'), allow_nan=False)
    from .triage import SENSITIVE
    if SENSITIVE.search(raw):
        raise ValueError('sensitive_verification')
    summary = {}
    for key in ('status', 'full_gate', 'authoritative_release', 'commit', 'branch',
                'dirty', 'product_scope'):
        value = verification.get(key)
        if value is None or type(value) in (str, bool, int, float):
            if key in verification:
                summary[key] = value
    gates = verification.get('gates')
    if isinstance(gates, list) and all(type(v) in (str, bool, int, float) or v is None for v in gates):
        summary['gates'] = gates
    for key in ('ci_native', 'metaeditor', 'preflight'):
        value = verification.get(key)
        if not isinstance(value, dict):
            continue
        picked = {name: value[name] for name in ('status', 'equivalence', 'commit', 'branch')
                  if name in value and (value[name] is None or type(value[name]) in (str, bool, int, float))}
        if picked:
            summary[key] = picked
    return dict(sha256=digest(raw.encode('utf-8')), summary=summary)


def _prior_block_hashes(prior):
    if prior is None:
        return {}
    if not isinstance(prior, dict) or prior.get('schema_version') != 1:
        raise ValueError('invalid_prior_packet')
    result = {}
    for block in prior.get('blocks', []):
        if (not isinstance(block, dict) or not isinstance(block.get('path'), str)
                or not re.fullmatch(r'[0-9a-f]{64}', str(block.get('sha256', '')))):
            raise ValueError('invalid_prior_packet')
        result[block['path']] = block['sha256']
    return result


def build_context_packet(bundle, prior=None, verification=None):
    """Create a content-addressed agent/reviewer packet.

    Exact-hash reuse is deliberately narrow: only unchanged related context may
    be replaced by a handle, and never when the task is protected, dependency
    scope is unknown, or source expansion is already required. Changed files
    always retain full text. Reused handles are expandable with
    expand_context_packet; this is transport compression, never review evidence.
    """
    required = {'schema_version', 'base', 'head', 'fingerprint', 'index_sha256',
                'changed_paths', 'changed_lines', 'patch', 'blocks', 'task',
                'dependency', 'expansion_required', 'protected', 'status_porcelain'}
    if not isinstance(bundle, dict) or not required.issubset(bundle):
        raise ValueError('invalid_bundle')
    prior_hashes = _prior_block_hashes(prior)
    reuse_enabled = (bundle['dependency'] == 'known' and not bundle['protected']
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
                     and prior_hashes.get(path) == source['sha256'])
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
                reuse_policy='exact_sha_unchanged_related_known_unprotected_only',
                reused_paths=sorted(reused), fresh_context_requires_expansion=bool(reused), blocks=blocks,
                verification=_verification_digest(verification))


def expand_context_packet(packet, bundle, paths=None):
    """Restore exact text for selected reused handles from the current bundle."""
    if (not isinstance(packet, dict) or packet.get('schema_version') != 1
            or not isinstance(bundle, dict)
            or any(packet.get(k) != bundle.get(k) for k in ('base', 'head', 'fingerprint', 'index_sha256'))):
        raise ValueError('packet_bundle_mismatch')
    sources = {b['path']: b for b in bundle.get('blocks', []) if isinstance(b, dict) and 'path' in b}
    reused = set(packet.get('reused_paths', []))
    targets = reused if paths is None else set(paths)
    if not targets.issubset(reused):
        raise ValueError('invalid_expansion_path')
    result = dict(packet)
    result['blocks'] = []
    for block in packet.get('blocks', []):
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
        key = digest(text.encode('utf-8'))
        if key in seen:
            continue
        seen.add(key)
        texts.append(text)
    return dict(text='\n\n'.join(texts), missing_context=sorted(set(missing)))


def expand_context(task):
    initial = select_context(task)
    expanded = dict(task, selected_context_ids=list(dict.fromkeys(
        task['selected_context_ids'] + task['required_context_ids'])))
    result = select_context(expanded)
    result['initial_missing_context'] = initial['missing_context']
    return result
