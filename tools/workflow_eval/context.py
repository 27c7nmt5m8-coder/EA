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
        if path.is_file():
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
    if untracked_names & set(unknown): changed_lines = None
    return dict(schema_version=3, base=base_sha, head=head, fingerprint=fingerprint(root),
                index_sha256=digest(git(root, 'ls-files', '--stage', '-z')),
                changed_paths=paths, changed_lines=changed_lines, patch=patch, blocks=blocks, task=task,
                dependency='unknown' if unknown or any(not p.startswith('docs/') for p in paths) else 'known',
                expansion_required=unknown, protected=bool(PROTECTED.search(task + patch + '\n'.join(b['text'] for b in blocks))),
                status_porcelain=git(root, 'status', '--porcelain=v1', '-z').decode('utf-8'))


def is_current(root, bundle):
    return (git(root, 'rev-parse', 'HEAD').decode().strip() == bundle['head']
            and fingerprint(root) == bundle['fingerprint'])


def select_context(task):
    blocks = {b['id']: b['text'] for b in task['context_blocks']}
    if len(blocks) != len(task['context_blocks']):
        raise ValueError('duplicate_context_id')
    selected = task['selected_context_ids']
    missing = sorted(set(task['required_context_ids']) - (set(selected) & set(blocks)))
    missing += sorted(set(selected) - set(blocks))
    return dict(text='\n\n'.join(blocks[x] for x in selected if x in blocks), missing_context=sorted(set(missing)))


def expand_context(task):
    initial = select_context(task)
    expanded = dict(task, selected_context_ids=list(dict.fromkeys(
        task['selected_context_ids'] + task['required_context_ids'])))
    result = select_context(expanded)
    result['initial_missing_context'] = initial['missing_context']
    return result
