"""Hash-bound canonical rules; expand required full text, never infer absent policy.

Coverage is an audit inventory, not evidence of machine-proved language equivalence.
No dependency/context selection or active model execution occurs in this module.
"""
import copy
import hashlib
import json
from pathlib import Path
import re

from .serialization import canonical_hash
from .context import local_path, _safe_evidence

CATALOG_PATH = '.agents/rules/canonical.json'
COVERAGE_PATH = '.agents/rules/semantic-coverage.json'
RULES_VERSION = 'phase2a-1'
RULE_MARKER_PREFIX = '<!-- canonical-rules: '
CATALOG_SHA256 = '0eeac45a4f0e74f097b6da9aef6282c8ff9dfa54f58b553830d2eec1a80853c6'
COVERAGE_SHA256 = '20e661ae047179973f6f2a33f7d3ea5b199efa103fdd212eb4cc6be2343bc3cf'
REVIEW_SKIP_ENABLED = False
JEV_CONFIDENCE_THRESHOLD = 0.90
SAFETY_RULE_IDS = ('RULE_EA_SPECIFICATION', 'RULE_PROTECTED_FAIL_CLOSED',
                   'RULE_NO_LIVE_ORDER', 'RULE_SECURITY',
                   'RULE_UNKNOWN_DEPENDENCY_FAIL_CLOSED', 'RULE_CONTEXT_FULL')
PROTECTED_RULE_IDS = SAFETY_RULE_IDS
MODEL_RULE_IDS = ('RULE_MODEL_ROLES', 'RULE_MODEL_ROUTING',
                  'RULE_NO_SILENT_FALLBACK', 'RULE_SPAWN_HOST',
                  'RULE_XHIGH_ESCALATION', 'RULE_ASTRA_APPROVAL')
REVIEW_RULE_IDS = ('RULE_REVIEW_INDEPENDENT', 'RULE_VERIFICATION_EVIDENCE',
                   'RULE_VERIFICATION_GATES')
GLOBAL_RULE_IDS = ('RULE_AUTHORITY', 'RULE_EVIDENCE_FIRST') + SAFETY_RULE_IDS + (
    'RULE_VERIFICATION_EVIDENCE',) + MODEL_RULE_IDS[:4] + (
    'RULE_REVIEW_INDEPENDENT',) + MODEL_RULE_IDS[4:] + (
    'RULE_JEV_BOUNDARIES', 'RULE_JEV_SHADOW', 'RULE_GIT_SAFETY',
    'RULE_VERIFICATION_GATES', 'RULE_COMPLETION_AND_STOP')
ALL_RULE_IDS = GLOBAL_RULE_IDS + (
    'RULE_SPAWN_EVIDENCE', 'RULE_SPAWN_DEPENDENCY', 'RULE_SPAWN_VERIFICATION',
    'RULE_SPAWN_REVIEW_AND_ORDER', 'RULE_SPAWN_METADATA',
    'RULE_SPAWN_REVIEWER', 'RULE_SPAWN_READ_ONLY')
DOCUMENT_PATHS = {'agents': 'AGENTS.md',
    'model-orchestrator': '.agents/skills/model-orchestrator/SKILL.md',
    'typesafe-ai': '.agents/skills/typesafe-ai/SKILL.md'}


def _sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _object_hash(data):
    return canonical_hash({k: v for k, v in data.items() if k != 'canonical_sha256'})


def _read_json(root, relative):
    try:
        text = local_path(root, relative).read_text(encoding='utf-8')
        _safe_evidence(text)
        return json.loads(text, object_pairs_hook=_unique_keys)
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('canonical_rule_source_unavailable_or_invalid') from exc


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('canonical_rule_duplicate_key')
        result[key] = value
    return result


def load_catalog(root):
    """Validate entire rule graph, consumer coverage, exact version/body/catalog hash."""
    data = _read_json(root, CATALOG_PATH)
    if (not isinstance(data, dict) or set(data) != {
            'schema_version', 'rule_version', 'rules', 'consumers', 'canonical_sha256'}
            or type(data['schema_version']) is not int or data['schema_version'] != 1
            or data['rule_version'] != RULES_VERSION
            or not isinstance(data['rules'], dict)
            or not isinstance(data['consumers'], dict)):
        raise ValueError('canonical_rule_schema_or_version_mismatch')
    rules = data['rules']
    if set(rules) != set(ALL_RULE_IDS):
        raise ValueError('canonical_rule_missing_or_unknown')
    for key, entry in rules.items():
        if (not isinstance(entry, dict) or set(entry) != {
                'id', 'body', 'body_sha256', 'requires'} or entry['id'] != key
                or not isinstance(entry['body'], str) or not entry['body'].strip()
                or entry['body_sha256'] != _sha(entry['body'])
                or not isinstance(entry['requires'], list)
                or any(not isinstance(ref, str) or ref not in rules for ref in entry['requires'])
                or len(entry['requires']) != len(set(entry['requires']))):
            raise ValueError('canonical_rule_body_hash_or_reference_invalid')
    visiting, visited = set(), set()
    def visit(key):
        if key in visiting:
            raise ValueError('canonical_rule_circular_reference')
        if key not in visited:
            visiting.add(key)
            for ref in rules[key]['requires']:
                visit(ref)
            visiting.remove(key)
            visited.add(key)
    for key in rules:
        visit(key)
    expected_consumers = {'agents', 'model-orchestrator', 'typesafe-ai',
                         'spawn-common', 'spawn-reviewer', 'spawn-read-only'}
    if set(data['consumers']) != expected_consumers:
        raise ValueError('canonical_rule_unknown_or_missing_consumer')
    for name, selected in data['consumers'].items():
        if (not isinstance(selected, list) or not selected
                or any(not isinstance(ref, str) or ref not in rules for ref in selected)
                or len(selected) != len(set(selected))):
            raise ValueError('canonical_rule_consumer_reference_invalid')
        if name in ('agents', 'model-orchestrator') and set(selected) != set(GLOBAL_RULE_IDS):
            raise ValueError('canonical_rule_required_semantics_missing')
    if data['canonical_sha256'] != _object_hash(data) or data['canonical_sha256'] != CATALOG_SHA256:
        raise ValueError('canonical_rule_catalog_hash_mismatch')
    return data


def authority_paths(root):
    """All active canonical body authority files (coverage is audit-only)."""
    load_catalog(root)
    return (CATALOG_PATH,)


def required_rule_ids(root, consumer):
    data = load_catalog(root)
    if not isinstance(consumer, str) or consumer not in data['consumers']:
        raise ValueError('canonical_rule_unknown_consumer')
    return tuple(data['consumers'][consumer])


def resolve_rules(root, rule_ids):
    """Dependency-first ordered set of complete bodies; unknown IDs fail closed."""
    data = load_catalog(root)
    if not isinstance(rule_ids, (tuple, list)) or not rule_ids:
        raise ValueError('canonical_rule_explicit_required_ids')
    if any(not isinstance(key, str) or key not in data['rules'] for key in rule_ids):
        raise ValueError('canonical_rule_unknown_id')
    result, seen = [], set()
    def add(key):
        if key not in seen:
            for ref in data['rules'][key]['requires']:
                add(ref)
            seen.add(key)
            result.append(copy.deepcopy(data['rules'][key]))
    for key in rule_ids:
        add(key)
    return result


def instruction_texts(root, rule_ids):
    return [entry['body'] for entry in resolve_rules(root, rule_ids)]


def expand_document_rules(root, document, consumer):
    """Expand marked authority for fresh recipients, retaining document-specific text."""
    if (not isinstance(document, str) or not isinstance(consumer, str)
            or consumer not in DOCUMENT_PATHS):
        raise ValueError('canonical_rule_invalid_document')
    _safe_evidence(document)
    marker = f'{RULE_MARKER_PREFIX}{consumer} version={RULES_VERSION} -->'
    if document.count(RULE_MARKER_PREFIX) != 1 or document.count(marker) != 1:
        raise ValueError('canonical_rule_document_reference_missing_or_invalid')
    selected = resolve_rules(root, required_rule_ids(root, consumer))
    additions = []
    for entry in selected:
        count = document.count(entry['body'])
        if count > 1:
            raise ValueError('canonical_rule_body_repeated_in_document')
        if not count:
            additions.append(f"[{entry['id']}]\n{entry['body']}")
    text = document.rstrip() + ('\n\n' + '\n\n'.join(additions) if additions else '') + '\n'
    return dict(text=text, included_rule_ids=[e['id'] for e in selected],
                catalog_sha256=CATALOG_SHA256, rule_version=RULES_VERSION)


def _baseline_chunks(path, text):
    if path == 'AGENTS.md':
        return [m for m in re.finditer(r'[^\n]+', text) if m.group().strip()]
    return list(re.finditer(r'[^\r\n]+(?:\r?\n(?!\r?\n)[^\r\n]+)*', text))


def validate_semantic_coverage(root):
    """Audit exact baseline inventory and full expected targets; not AI equivalence."""
    catalog = load_catalog(root)
    data = _read_json(root, COVERAGE_PATH)
    if (not isinstance(data, dict) or data.get('schema_version') != 1
            or data.get('rule_version') != RULES_VERSION
            or data.get('catalog_sha256') != catalog['canonical_sha256']
            or data.get('canonical_sha256') != _object_hash(data)
            or data.get('canonical_sha256') != COVERAGE_SHA256
            or set(data.get('sources', {})) != set(DOCUMENT_PATHS.values())
            or data.get('unmapped_clause_ids') != []):
        raise ValueError('canonical_rule_coverage_hash_or_schema_mismatch')
    expected = {}
    for path, source in data['sources'].items():
        if source.get('source_sha256') != _sha(source.get('baseline_text', '')):
            raise ValueError('canonical_rule_baseline_source_hash_mismatch')
        for index, chunk in enumerate(_baseline_chunks(path, source['baseline_text'])):
            expected[f'{path}:{index}'] = (path, chunk.start(), chunk.end(), chunk.group())
    if (not isinstance(data.get('clauses'), list)
            or len(data['clauses']) != len(expected)
            or {c.get('id') for c in data['clauses']} != set(expected)):
        raise ValueError('canonical_rule_baseline_clause_omission')
    result = copy.deepcopy(data)
    for clause in result['clauses']:
        path, start, end, body = expected[clause['id']]
        if (clause.get('source_path'), clause.get('start'), clause.get('end')) != (path, start, end):
            raise ValueError('canonical_rule_baseline_clause_mismatch')
        if clause['baseline_sha256'] != _sha(body):
            raise ValueError('canonical_rule_baseline_clause_hash_mismatch')
        if clause['target_kind'] == 'canonical_rules':
            ids = clause['rule_ids']
            if not ids or any(k not in catalog['rules'] for k in ids):
                raise ValueError('canonical_rule_coverage_reference_missing')
            target = '\n\n'.join(catalog['rules'][k]['body'] for k in ids)
        elif clause['target_kind'] == 'document' and not clause['rule_ids']:
            try:
                document = local_path(root, path).read_text(encoding='utf-8')
                _safe_evidence(document)
            except (OSError, UnicodeError) as exc:
                raise ValueError('canonical_rule_coverage_document_missing') from exc
            first, last = clause.get('target_start'), clause.get('target_end')
            if (type(first) is not int or type(last) is not int
                    or not 0 <= first < last <= len(document)):
                raise ValueError('canonical_rule_target_range_invalid')
            target = document[first:last]
        else:
            raise ValueError('canonical_rule_target_kind_invalid')
        if _sha(target) != clause['target_sha256']:
            raise ValueError('canonical_rule_semantic_target_changed')
        clause['baseline_body'] = body
        clause['target_body'] = target
    return result


def measure_rule_bytes(root):
    """Actual UTF-8 text bytes; tokens are unavailable, never inferred as observed."""
    coverage = validate_semantic_coverage(root)
    all_ids = []
    metrics = {}
    for consumer, path in DOCUMENT_PATHS.items():
        document = local_path(root, path).read_text(encoding='utf-8')
        expanded = expand_document_rules(root, document, consumer)
        baseline = coverage['sources'][path]['baseline_text']
        metrics[consumer.replace('-', '_') + '_raw_bytes'] = len(document.encode('utf-8'))
        metrics[consumer.replace('-', '_') + '_baseline_bytes'] = len(baseline.encode('utf-8'))
        metrics[consumer.replace('-', '_') + '_expanded_bytes'] = len(expanded['text'].encode('utf-8'))
        all_ids.extend(required_rule_ids(root, consumer))
    metrics['deduplicated_rule_bytes'] = sum(len(x['body'].encode('utf-8')) for x in resolve_rules(root, all_ids))
    metrics['observed_token_count'] = None
    metrics['token_missing_reason'] = 'No provider token usage measured by rule inventory.'
    metrics['catalog_file_bytes'] = local_path(root, CATALOG_PATH).stat().st_size
    metrics['coverage_file_bytes'] = local_path(root, COVERAGE_PATH).stat().st_size
    return metrics
