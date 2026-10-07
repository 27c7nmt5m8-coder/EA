"""Hash-bound static dependency candidates, for shadow comparison only.

This is a bounded parser, not proof of dependency absence. Python imports,
unambiguous direct calls and literal tracked file references are candidates.
MQL includes are metadata only. Unsupported/ambiguous/protected evidence requires
ordinary exploration. Source bodies and credentials are never stored in an index.
"""
import ast
import builtins
import copy
import hashlib
from pathlib import Path, PurePosixPath
import platform
import re
import sys
import time

from .context import _path_name, _safe_evidence, digest, fingerprint, git
from .serialization import canonical_hash, canonical_json
from .triage import PROTECTED


INDEX_VERSION = 'shadow-dependency-v1'
PARSER_SHA256 = digest(Path(__file__).read_bytes())
INDEX_FIELDS = {'schema_version', 'index_version', 'identity', 'scope_paths', 'nodes',
                'edges', 'unresolved', 'canonical_sha256', 'build_metrics'}
LEGACY_FIELDS = {'schema_version', 'paths', 'material_paths', 'acquired', 'independent',
                 'source', 'tree', 'fingerprint', 'dependency_hashes', 'provenance'}


def _hash(index):
    # Timing is observational telemetry, not dependency identity or authority.
    return canonical_hash({k: v for k, v in index.items() if k not in ('canonical_sha256', 'build_metrics')})


def _tracked(root):
    return sorted(raw.decode('utf-8') for raw in git(root, 'ls-files', '-z').split(b'\0') if raw)


def _file(root, name):
    if not _path_name(name):
        raise ValueError('invalid_dependency_path')
    root = Path(root).resolve(strict=True)
    target = root
    for part in name.split('/'):
        target = target / part
        if target.is_symlink() or getattr(target, 'is_junction', lambda: False)():
            raise ValueError('unsafe_dependency_path')
    if not target.resolve().is_relative_to(root) or not target.is_file():
        raise ValueError('missing_dependency_path')
    _safe_evidence(name)
    return target


def _identity(root):
    if digest(Path(__file__).read_bytes()) != PARSER_SHA256:
        raise ValueError('dependency_parser_source_changed')
    return dict(repository_id=digest(git(root, 'rev-parse', '--path-format=absolute', '--git-common-dir').strip()),
                source=git(root, 'rev-parse', 'HEAD').decode().strip(),
                tree=git(root, 'rev-parse', 'HEAD^{tree}').decode().strip(),
                fingerprint=fingerprint(root), index_sha256=digest(git(root, 'ls-files', '--stage', '-z')),
                parser_runtime=dict(implementation=platform.python_implementation(), version=list(sys.version_info[:3])),
                parser_sha256=PARSER_SHA256)


def _paths(paths, tracked):
    if (not isinstance(paths, list) or not paths or not all(_path_name(p) for p in paths) or
            len(paths) != len(set(paths)) or not set(paths).issubset(tracked)):
        raise ValueError('invalid_or_untracked_dependency_scope')
    _safe_evidence(paths)
    return sorted(paths)


def _module(path):
    parts = list(PurePosixPath(path).with_suffix('').parts)
    if parts[-1] == '__init__':
        parts.pop()
    return '.'.join(parts) if parts and all(part.isidentifier() for part in parts) else None


def _name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _name(node.value)
        return owner + '.' + node.attr if owner else None
    return None


def build_dependency_index(root, paths):
    """Index explicit tracked scope and proven local candidate edges transitively.

    Canonical SHA binds semantic facts, Git/worktree identity and parser version.
    Build timing/tokens are a separate observational envelope. Every unknown is
    recorded, including external imports and data/MQL semantic limitations.
    """
    started = time.perf_counter()
    tracked = set(_tracked(root))
    scope = _paths(paths, tracked)
    identity = _identity(root)
    modules = {}
    for path in sorted(tracked):
        if path.endswith('.py') and _module(path):
            modules.setdefault(_module(path), []).append(path)
    nodes, parsed, unresolved, edges = {}, {}, [], []
    queue = []

    def unknown(path, reason, symbol=None):
        value = dict(source_path=path, reason=reason, symbol=symbol)
        _safe_evidence(value)
        if value not in unresolved:
            unresolved.append(value)

    def load(path):
        if path in nodes:
            return parsed[path]
        if path not in tracked:
            raise ValueError('untracked_dependency_path')
        raw = _file(root, path).read_bytes()
        language = 'python' if path.endswith('.py') else 'mql' if path.endswith(('.mq5', '.mqh')) else 'data'
        node = dict(path=path, sha256=digest(raw), size_bytes=len(raw), language=language,
                    public_interfaces=[], coverage='static_candidates_only', protected=path.startswith('src/') or path.endswith('.set'))
        nodes[path] = node
        parsed[path] = dict(tree=None, definitions={}, text=None)
        queue.append(path)
        try:
            text = raw.decode('utf-8')
        except UnicodeError:
            unknown(path, 'unsupported_encoding')
            return parsed[path]
        _safe_evidence(text)
        parsed[path]['text'] = text  # Ephemeral parser input, never returned/stored.
        words = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', text.replace('_', ' '))
        node['protected'] = node['protected'] or bool(PROTECTED.search(words))
        if node['protected']:
            unknown(path, 'protected_logic')
        if re.search(r'(?im)generated (?:file|code)|automatically generated|do not edit', '\n'.join(text.splitlines()[:16])):
            unknown(path, 'generated_code')
            return parsed[path]
        if language != 'python':
            unknown(path, 'mql_semantics_not_parsed' if language == 'mql' else 'unsupported_data_semantics')
            return parsed[path]
        try:
            tree = ast.parse(text, filename=path)
        except (SyntaxError, ValueError, RecursionError):
            unknown(path, 'parse_failure')
            return parsed[path]
        parsed[path]['tree'] = tree
        for statement in tree.body:
            names, kind = [], None
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names = [statement.name]
                kind = 'class' if isinstance(statement, ast.ClassDef) else 'function'
                if statement.decorator_list:
                    unknown(path, 'runtime_decorator', statement.name)
            elif isinstance(statement, (ast.Assign, ast.AnnAssign)):
                targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                names = [target.id for target in targets if isinstance(target, ast.Name)]
                kind = 'assignment'
            for name in names:
                parsed[path]['definitions'][name] = kind
                if not name.startswith('_'):
                    identifier = (_module(path) or path) + '.' + name
                    node['public_interfaces'].append(dict(symbol=name, kind=kind, identifier=identifier))
        _safe_evidence(node)
        return parsed[path]

    def edge(source, dependency, relation, symbol, interface=None):
        load(dependency)
        value = dict(schema_version=1, source_path=source, source_sha256=nodes[source]['sha256'],
                     dependency_path=dependency, dependency_sha256=nodes[dependency]['sha256'],
                     relation_type=relation, symbol=symbol, interface_identifier=interface)
        _safe_evidence(value)
        if value not in edges:
            edges.append(value)

    def resolve(source, module):
        candidates = set(modules.get(module, []))
        # Script-directory imports can differ from repository-root imports.
        parent = PurePosixPath(source).parent.as_posix().replace('/', '.')
        if '.' not in module and parent != '.':
            candidates.update(modules.get(parent + '.' + module, []))
        if len(candidates) != 1:
            unknown(source, 'ambiguous_import' if candidates else 'unresolved_import', module)
            return None
        dependency = next(iter(candidates))
        edge(source, dependency, 'python_import', module)
        if source.startswith('tests/') and not dependency.startswith('tests/'):
            edge(source, dependency, 'test_source', module)
        parts = module.split('.')
        for length in range(1, len(parts)):
            prefix = '.'.join(parts[:length])
            package = '/'.join(parts[:length]) + '/__init__.py'
            if len(modules.get(prefix, [])) > 1:
                unknown(source, 'ambiguous_import', prefix)
            if package in tracked:
                edge(source, package, 'package_initializer', prefix)
            else:
                unknown(source, 'namespace_package_scope', prefix)
        return dependency

    def reference(source, literal, relation):
        if not _path_name(literal):
            unknown(source, 'unsupported_file_reference')
            return
        candidates = {literal, (PurePosixPath(source).parent / literal).as_posix()} & tracked
        if len(candidates) != 1:
            unknown(source, 'ambiguous_file_reference' if candidates else 'unresolved_file_reference', literal)
            return
        edge(source, next(iter(candidates)), relation, literal)

    for path in scope:
        load(path)
    cursor = 0
    while cursor < len(queue):
        path = queue[cursor]
        cursor += 1
        info = parsed[path]
        if nodes[path]['language'] == 'mql' and info['text'] is not None:
            clean = re.sub(r'/\*.*?\*/|//[^\n]*', '', info['text'], flags=re.S)
            for line in clean.splitlines():
                if re.match(r'\s*#\s*(?:define|if|ifdef|ifndef|elif|else|endif|undef)\b', line):
                    unknown(path, 'unknown_macro')
                if re.match(r'\s*#\s*include\b', line):
                    include = re.fullmatch(r'\s*#\s*include\s+"([^"\n]+)"\s*', line)
                    if include and _path_name(include[1]):
                        dependency = (PurePosixPath(path).parent / include[1]).as_posix()
                        if dependency in tracked:
                            edge(path, dependency, 'mql_include', include[1])
                        else:
                            unknown(path, 'unresolved_include', include[1])
                    else:
                        unknown(path, 'ambiguous_include' if '<' in line else 'unknown_macro')
            continue
        tree = info['tree']
        if tree is None:
            continue
        bindings = {}
        top = {id(statement) for statement in tree.body}
        for statement in ast.walk(tree):
            if not isinstance(statement, (ast.Import, ast.ImportFrom)):
                continue
            if id(statement) not in top:
                unknown(path, 'conditional_import')
            if isinstance(statement, ast.Import):
                for alias in statement.names:
                    dependency = resolve(path, alias.name)
                    if dependency:
                        bound = alias.asname or alias.name.split('.')[0]
                        bindings[bound] = dict(path=dependency, kind='module', module=alias.name if alias.asname else alias.name.split('.')[0])
            else:
                package = _module(path).split('.')[:-1] if _module(path) else []
                if PurePosixPath(path).name == '__init__.py':
                    package = _module(path).split('.') if _module(path) else []
                if statement.level:
                    if statement.level > len(package):
                        unknown(path, 'unresolved_import')
                        continue
                    package = package[:len(package) - statement.level + 1]
                else:
                    package = []
                base = '.'.join(package + ([statement.module] if statement.module else []))
                for alias in statement.names:
                    module = base + ('.' if base else '') + alias.name if statement.module is None else base
                    dependency = resolve(path, module)
                    if alias.name == '*':
                        unknown(path, 'wildcard_import')
                    elif dependency:
                        kind = 'module' if statement.module is None else load(dependency)['definitions'].get(alias.name)
                        if kind is None and modules.get(module + '.' + alias.name):
                            module += '.' + alias.name
                            dependency = resolve(path, module)
                            kind = 'module' if dependency else None
                        if kind is None:
                            unknown(path, 'unresolved_symbol', alias.name)
                        else:
                            bindings[alias.asname or alias.name] = dict(path=dependency, kind=kind, module=module, symbol=alias.name)
                            edge(path, dependency, 'symbol_reference', alias.name, module + '.' + alias.name)
        parameters = {n.arg for n in ast.walk(tree) if isinstance(n, ast.arg)}
        stored = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        shadowed = set(bindings) & (parameters | stored | set(info['definitions']))
        for name in sorted(shadowed):
            unknown(path, 'shadowed_or_rebound_import', name)
            del bindings[name]
        for interface in nodes[path]['public_interfaces']:
            edge(path, path, 'public_interface', interface['symbol'], interface['identifier'])
        known_names = set(info['definitions']) | set(bindings) | set(dir(builtins)) | {'__file__', '__name__', '__package__'}
        known_names.update(n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store))
        known_names.update(n.arg for n in ast.walk(tree) if isinstance(n, ast.arg))
        for statement in ast.walk(tree):
            if isinstance(statement, ast.Name) and isinstance(statement.ctx, ast.Load) and statement.id not in known_names:
                unknown(path, 'unresolved_symbol', statement.id)
            if isinstance(statement, (ast.Match, ast.Lambda, ast.NamedExpr, ast.Try, ast.With, ast.AsyncWith)):
                unknown(path, 'unsupported_syntax')
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)) and statement.name in ('__getattr__', '__getattribute__', '__dir__'):
                unknown(path, 'reflection', statement.name)
            if isinstance(statement, ast.Attribute):
                name = _name(statement)
                first = name.split('.')[0] if name else None
                if first not in bindings or bindings[first]['kind'] != 'module':
                    unknown(path, 'unresolved_attribute', name)
            if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                names = [target.id for target in targets if isinstance(target, ast.Name)]
                if any(re.search(r'(?:CONFIG|PATH|FILE)$', name, re.I) for name in names):
                    if isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, str):
                        reference(path, statement.value.value, 'configuration_reference')
                    else:
                        unknown(path, 'indirect_configuration')
            if not isinstance(statement, ast.Call):
                continue
            called = _name(statement.func)
            if called is None:
                unknown(path, 'indirect_call')
                continue
            final = called.rsplit('.', 1)[-1]
            binding = bindings.get(called)
            origin = ((binding.get('module', '') + '.' + binding.get('symbol', '')) if binding else called)
            if called.split('.')[0] in shadowed or called in parameters:
                unknown(path, 'indirect_call', called)
                continue
            if final == '__import__' or final == 'import_module' or origin.endswith('.import_module'):
                unknown(path, 'dynamic_import', called)
                continue
            if final in ('getattr', 'setattr', 'delattr', 'vars', 'globals', 'locals', 'eval', 'exec'):
                unknown(path, 'reflection', called)
                continue
            if final in ('Path', 'open'):
                if statement.args and isinstance(statement.args[0], ast.Constant) and isinstance(statement.args[0].value, str):
                    reference(path, statement.args[0].value, 'file_reference')
                else:
                    unknown(path, 'indirect_file_reference')
                continue
            if binding and binding['kind'] in ('function', 'class'):
                edge(path, binding['path'], 'direct_call', binding.get('symbol', called), origin)
            elif info['definitions'].get(called) in ('function', 'class'):
                edge(path, path, 'direct_call', called, (_module(path) or path) + '.' + called)
            elif '.' in called and called.split('.')[0] in bindings:
                owner, symbol = called.rsplit('.', 1)
                first, *suffix = owner.split('.')
                bound = bindings[first]
                module = bound['module'] + ('.' + '.'.join(suffix) if suffix else '')
                dependency = resolve(path, module)
                if dependency and load(dependency)['definitions'].get(symbol) in ('function', 'class'):
                    edge(path, dependency, 'direct_call', symbol, module + '.' + symbol)
                else:
                    unknown(path, 'unresolved_symbol', called)
            elif called in info['definitions'] or called not in ('print', 'len', 'range', 'str', 'int', 'float', 'bool', 'list', 'dict', 'set', 'tuple', 'sum', 'min', 'max', 'abs', 'enumerate', 'zip'):
                unknown(path, 'unresolved_symbol', called)
    if any(digest(_file(root, path).read_bytes()) != node['sha256'] for path, node in nodes.items()) or identity != _identity(root):
        raise ValueError('repository_changed_during_index_build')
    result = dict(schema_version=1, index_version=INDEX_VERSION, identity=identity, scope_paths=scope,
                  nodes=[nodes[name] for name in sorted(nodes)], edges=sorted(edges, key=canonical_json),
                  unresolved=sorted(unresolved, key=canonical_json), build_metrics=dict(
                    build_time_seconds=time.perf_counter() - started, input_tokens=None,
                    missing_reasons={'input_tokens': 'not_observable'}))
    _safe_evidence(result)
    result['canonical_sha256'] = _hash(result)
    return result


def validate_dependency_index(root, index):
    """Verify exact semantic facts, original source freshness and safe paths."""
    _safe_evidence(index)
    canonical_json(index)
    if (not isinstance(index, dict) or set(index) != INDEX_FIELDS or type(index['schema_version']) is not int or
            index['schema_version'] != 1 or index['index_version'] != INDEX_VERSION or index['canonical_sha256'] != _hash(index)):
        raise ValueError('corrupt_dependency_index')
    metrics = index['build_metrics']
    if (not isinstance(metrics, dict) or set(metrics) != {'build_time_seconds', 'input_tokens', 'missing_reasons'} or
            type(metrics['build_time_seconds']) not in (int, float) or metrics['build_time_seconds'] < 0 or
            metrics['input_tokens'] is not None or metrics['missing_reasons'] != {'input_tokens': 'not_observable'}):
        raise ValueError('invalid_dependency_metrics')
    if index['identity'] != _identity(root):
        raise ValueError('stale_dependency_index')
    rebuilt = build_dependency_index(root, index['scope_paths'])
    if _hash(rebuilt) != index['canonical_sha256']:
        raise ValueError('dependency_index_semantic_mismatch')
    return index


def _legacy(root, legacy, identity):
    """Caller acquisition/independence assertions are workflow provenance only."""
    _safe_evidence(legacy)
    canonical_json(legacy)
    if (not isinstance(legacy, dict) or set(legacy) != LEGACY_FIELDS or type(legacy['schema_version']) is not int or
            legacy['schema_version'] != 1 or legacy['acquired'] is not True or legacy['independent'] is not True or
            not isinstance(legacy['provenance'], dict) or not legacy['provenance'] or
            any(legacy[name] != identity[name] for name in ('source', 'tree', 'fingerprint'))):
        return None
    tracked = set(_tracked(root))
    paths, material = legacy['paths'], legacy['material_paths']
    if (not isinstance(paths, list) or not all(_path_name(p) for p in paths) or len(set(paths)) != len(paths) or
            not set(paths).issubset(tracked) or not isinstance(material, list) or not all(_path_name(p) for p in material) or
            len(set(material)) != len(material) or not set(material).issubset(paths) or
            not isinstance(legacy['dependency_hashes'], dict) or set(legacy['dependency_hashes']) != set(paths)):
        return None
    for path in paths:
        try:
            actual = digest(_file(root, path).read_bytes())
        except (OSError, ValueError):
            return None
        if legacy['dependency_hashes'][path] != actual:
            return None
    return legacy


def _empty_comparison(reason):
    return dict(true_positive_paths=None, false_positive_paths=None, false_negative_paths=None,
                true_positive_count=None, false_positive_count=None, false_negative_count=None,
                material_false_negative_count=None, missing_reasons={'legacy_evidence': reason})


def compare_dependency_shadow(root, index, roots, *, legacy=None, task='', protected=False, dependency='known'):
    """Compare candidates against independently acquired legacy evidence only.

    Production/context selection remains the legacy full route in every case.
    Provenance assertions cannot prove that a human/runner independently searched.
    No absence proof, token estimate, model execution or promotion is inferred.
    """
    _safe_evidence({'task': task, 'legacy': legacy})
    if not isinstance(task, str) or type(protected) is not bool or dependency not in ('known', 'unknown'):
        raise ValueError('invalid_dependency_shadow_classification')
    result = dict(schema_version=1, actual_route='legacy_full', production_adoption=False, changed_files_full=True,
                  promotion_blocked=True, promotion_reasons=['shadow_only'], fallback=False, fallback_reasons=[],
                  candidate_paths=None, unresolved=None, unresolved_count=None, selected_bytes=None,
                  input_tokens=None, missing_reasons={'input_tokens': 'not_observable'},
                  build_time_seconds=None, comparison=_empty_comparison('index_unavailable'),
                  legacy_provenance_contract='caller assertion does not prove independent exploration')
    try:
        validate_dependency_index(root, index)
    except (OSError, ValueError, KeyError, TypeError):
        result.update(fallback=True, fallback_reasons=['index_invalid_or_stale'])
        result['missing_reasons'].update(selected_bytes='index_unavailable', build_time_seconds='index_unavailable')
        return result
    nodes = {node['path']: node for node in index['nodes']}
    selected = _paths(roots, set(nodes))
    reachable, pending = set(selected), list(selected)
    while pending:
        source = pending.pop()
        for edge in index['edges']:
            target = edge['dependency_path']
            if edge['source_path'] == source and target not in reachable:
                reachable.add(target)
                pending.append(target)
    candidates = sorted(reachable - set(selected))
    unresolved = [u for u in index['unresolved'] if u['source_path'] in reachable]
    reasons = {u['reason'] for u in unresolved}
    if protected or PROTECTED.search(task) or any(nodes[path]['protected'] for path in reachable):
        reasons.add('protected_or_uncertain_scope')
    if dependency != 'known':
        reasons.add('unknown_dependency')
    result.update(candidate_paths=candidates, unresolved=unresolved, unresolved_count=len(unresolved),
                  selected_bytes=sum(nodes[path]['size_bytes'] for path in candidates),
                  build_time_seconds=index['build_metrics']['build_time_seconds'])
    evidence = _legacy(root, legacy, index['identity'])
    if evidence is None:
        reasons.add('legacy_evidence_unknown_or_stale')
        result['comparison'] = _empty_comparison('independent_acquired_current_hashed_legacy_required')
    else:
        candidate_set, legacy_set = set(candidates), set(evidence['paths'])
        true, false, missed = sorted(candidate_set & legacy_set), sorted(candidate_set - legacy_set), sorted(legacy_set - candidate_set)
        material = set(missed) & set(evidence['material_paths'])
        result['comparison'] = dict(true_positive_paths=true, false_positive_paths=false, false_negative_paths=missed,
            true_positive_count=len(true), false_positive_count=len(false), false_negative_count=len(missed),
            material_false_negative_count=len(material), missing_reasons={})
        if missed:
            reasons.add('false_negative')
        if material:
            reasons.add('material_false_negative')
            result['promotion_reasons'].append('material_false_negative')
    result['fallback_reasons'] = sorted(reasons)
    result['fallback'] = bool(reasons)
    if _identity(root) != index['identity']:
        result.update(fallback=True, fallback_reasons=['repository_changed_during_shadow'],
                      candidate_paths=None, unresolved=None, unresolved_count=None, selected_bytes=None,
                      comparison=_empty_comparison('repository_changed_during_shadow'))
        result['missing_reasons']['selected_bytes'] = 'repository_changed_during_shadow'
    _safe_evidence(result)
    return result
