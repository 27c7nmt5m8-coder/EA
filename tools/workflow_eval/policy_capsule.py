"""Deterministic policy-capsule shadow comparison; production keeps full policy.

The capsule is a measurement, never an approval or context/dependency selector.
Canonical authority must be available and valid before full policy is usable.
Candidate omissions are checked against a separate literal baseline contract.
"""
import copy
from dataclasses import asdict, dataclass, fields
import json
import math
from pathlib import Path
import re
import subprocess
import tomllib

from . import context, rules
from .serialization import canonical_hash

SCHEMA_VERSION = 1
CAPSULE_VERSION = 'phase2a-shadow-1'
PRODUCTION_ADOPTION = False
DEFAULT_AUTHORITY_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = '.codex/config.toml'
WORKFLOW_POLICY_PATH = 'tools/workflow_eval/policy.json'
WORKFLOW_POLICY_VERSION = 5


@dataclass(frozen=True)
class CapsuleInput:
    role: str
    task_type: str
    changed_paths: tuple[str, ...]
    protected: bool | None
    dependency: str
    repository_area: str
    operation_type: str
    review_mode: str


# Baseline oracle: deliberately literal, not composed from the candidate selector
# or derived by filtering its selected result. Changes need independent review.
BASELINE_FULL_REQUIRED = (
    'RULE_AUTHORITY', 'RULE_EVIDENCE_FIRST', 'RULE_EA_SPECIFICATION',
    'RULE_PROTECTED_FAIL_CLOSED', 'RULE_NO_LIVE_ORDER', 'RULE_SECURITY',
    'RULE_UNKNOWN_DEPENDENCY_FAIL_CLOSED', 'RULE_CONTEXT_FULL',
    'RULE_VERIFICATION_EVIDENCE', 'RULE_MODEL_ROLES', 'RULE_MODEL_ROUTING',
    'RULE_NO_SILENT_FALLBACK', 'RULE_SPAWN_HOST', 'RULE_REVIEW_INDEPENDENT',
    'RULE_XHIGH_ESCALATION', 'RULE_ASTRA_APPROVAL', 'RULE_JEV_BOUNDARIES',
    'RULE_JEV_SHADOW', 'RULE_GIT_SAFETY', 'RULE_VERIFICATION_GATES',
    'RULE_COMPLETION_AND_STOP')
BASELINE_ROUTINE_DOCUMENTATION_REQUIRED = (
    'RULE_AUTHORITY', 'RULE_EVIDENCE_FIRST', 'RULE_EA_SPECIFICATION',
    'RULE_PROTECTED_FAIL_CLOSED', 'RULE_NO_LIVE_ORDER', 'RULE_SECURITY',
    'RULE_UNKNOWN_DEPENDENCY_FAIL_CLOSED', 'RULE_CONTEXT_FULL',
    'RULE_VERIFICATION_EVIDENCE', 'RULE_MODEL_ROLES', 'RULE_MODEL_ROUTING',
    'RULE_NO_SILENT_FALLBACK', 'RULE_SPAWN_HOST', 'RULE_REVIEW_INDEPENDENT',
    'RULE_XHIGH_ESCALATION', 'RULE_ASTRA_APPROVAL', 'RULE_JEV_BOUNDARIES',
    'RULE_GIT_SAFETY', 'RULE_VERIFICATION_GATES', 'RULE_COMPLETION_AND_STOP')
EXPECTED_REQUIRED_BY_PROFILE = {
    'routine_documentation': BASELINE_ROUTINE_DOCUMENTATION_REQUIRED,
    'reviewer': BASELINE_FULL_REQUIRED,
    'protected': BASELINE_FULL_REQUIRED,
    'full': BASELINE_FULL_REQUIRED,
}
# Independent coverage sets include all capability/safety boundaries even in a
# routine candidate. No role may omit review, context or verification authority.
COVERAGE_REQUIRED = {
    'protected': ('RULE_EA_SPECIFICATION', 'RULE_PROTECTED_FAIL_CLOSED',
                  'RULE_NO_LIVE_ORDER', 'RULE_UNKNOWN_DEPENDENCY_FAIL_CLOSED',
                  'RULE_CONTEXT_FULL'),
    'reviewer': ('RULE_REVIEW_INDEPENDENT', 'RULE_MODEL_ROLES',
                 'RULE_CONTEXT_FULL', 'RULE_VERIFICATION_EVIDENCE',
                 'RULE_VERIFICATION_GATES'),
    'model_routing': ('RULE_MODEL_ROLES', 'RULE_MODEL_ROUTING',
                      'RULE_NO_SILENT_FALLBACK', 'RULE_SPAWN_HOST',
                      'RULE_XHIGH_ESCALATION', 'RULE_ASTRA_APPROVAL'),
    'security': ('RULE_SECURITY', 'RULE_NO_LIVE_ORDER', 'RULE_GIT_SAFETY'),
}
ROLES = {'root', 'orchestrator', 'integrate', 'verify', 'worker',
         'reviewer', 'explorer', 'researcher'}
TASK_TYPES = {'routine', 'complex', 'documentation', 'review', 'verification',
              'integration', 'exploration', 'research', 'orchestration'}
OPERATIONS = {'inspect', 'implement', 'verify', 'review', 'integrate', 'document'}
AREAS = {'documentation', 'ea', 'workflow', 'policy', 'mixed'}
REVIEW_MODES = {'none', 'independent', 'mandatory_independent'}


def _inputs(value):
    if isinstance(value, dict):
        if set(value) != {field.name for field in fields(CapsuleInput)}:
            raise ValueError('input_parsing_error')
        value = CapsuleInput(**value)
    if not isinstance(value, CapsuleInput):
        raise ValueError('input_parsing_error')
    string_names = ('role', 'task_type', 'dependency', 'repository_area',
                    'operation_type', 'review_mode')
    if (any(not isinstance(getattr(value, name), str) for name in string_names)
            or not isinstance(value.changed_paths, (tuple, list))
            or any(not context._path_name(path) for path in value.changed_paths)
            or len(value.changed_paths) != len(set(value.changed_paths))
            or value.protected is not None and type(value.protected) is not bool):
        raise ValueError('input_parsing_error')
    clean = asdict(value)
    clean['changed_paths'] = sorted(value.changed_paths)
    context._safe_evidence(clean)
    return CapsuleInput(**{**clean, 'changed_paths': tuple(clean['changed_paths'])})


def _path_area(path):
    # Areas identify existing explicit repository surfaces; they do not prove
    # dependency completeness or select files. Unknown paths always fall back.
    if path.startswith('docs/') or path in {
            'README_JA.md', 'VALIDATION_JA.md', 'CHANGELOG.md', 'SHA256SUMS.txt'}:
        return 'documentation'
    if path.startswith('src/'):
        return 'ea'
    if path.startswith(('tools/', 'tests/', '.github/')):
        return 'workflow'
    if path == 'AGENTS.md' or path.startswith(('.agents/', '.codex/')):
        return 'policy'
    return None


def _issues(inputs, bundle):
    issues = []
    checks = [('role', ROLES, 'unknown_role'),
              ('task_type', TASK_TYPES, 'unknown_classification'),
              ('repository_area', AREAS, 'unknown_repository_area'),
              ('operation_type', OPERATIONS, 'unknown_operation_type'),
              ('review_mode', REVIEW_MODES, 'unknown_review_mode')]
    for field, allowed, reason in checks:
        if getattr(inputs, field) not in allowed:
            issues.append(reason)
    if inputs.protected is None:
        issues.append('protected_uncertainty')
    elif inputs.protected != bundle['protected']:
        issues.append('protected_claim_mismatch')
    if inputs.dependency != 'known' or bundle['dependency'] != 'known':
        issues.append('unknown_dependency')
    if inputs.dependency != bundle['dependency']:
        issues.append('dependency_claim_mismatch')
    if list(inputs.changed_paths) != sorted(bundle['changed_paths']):
        issues.append('changed_paths_mismatch')
    actual_areas = {_path_area(path) for path in bundle['changed_paths']}
    if None in actual_areas:
        issues.append('unknown_path')
    if not actual_areas:
        issues.append('changed_paths_required')
    elif None not in actual_areas:
        actual_area = next(iter(actual_areas)) if len(actual_areas) == 1 else 'mixed'
        if inputs.repository_area != actual_area:
            issues.append('repository_area_mismatch')
        if actual_area in ('ea', 'policy', 'mixed'):
            issues.append('protected_area_requires_full_policy')
    if bundle['protected']:
        issues.append('protected_task_requires_full_policy')
    if bundle['expansion_required']:
        issues.append('missing_context')
    relevant_text = '\n'.join([bundle['task'], bundle['patch']] +
                              [block['text'] for block in bundle['blocks']])
    if re.search(r'(?i)\b(?:Jev|JEVGrep|TypeSafe)\b', relevant_text):
        issues.append('jev_scope_requires_full_policy')
    if inputs.role == 'reviewer' and (
            inputs.operation_type != 'review' or inputs.task_type != 'review'
            or inputs.review_mode not in ('independent', 'mandatory_independent')):
        issues.append('reviewer_contract_mismatch')
    if inputs.operation_type == 'review' and inputs.review_mode == 'none':
        issues.append('review_mode_required')
    role_operations = {'explorer': {'inspect'}, 'researcher': {'inspect'},
                       'verify': {'inspect', 'verify'},
                       'integrate': {'inspect', 'integrate'}}
    if (inputs.role in role_operations
            and inputs.operation_type not in role_operations[inputs.role]):
        issues.append('role_operation_mismatch')
    return list(dict.fromkeys(issues))


def _oracle_profile(inputs):
    # This separately authored expectation table recognizes only a narrow,
    # unprotected documentation implementation. It does not call the selector.
    if inputs is None:
        return 'full'
    if inputs.protected is True:
        return 'protected'
    if inputs.role == 'reviewer':
        return 'reviewer'
    if (inputs.role == 'worker' and inputs.task_type in ('routine', 'documentation')
            and inputs.repository_area == 'documentation'
            and inputs.operation_type in ('implement', 'document')
            and inputs.review_mode == 'none' and inputs.dependency == 'known'
            and inputs.protected is False):
        return 'routine_documentation'
    return 'full'


def _select_candidate(catalog, inputs, bundle):
    selected = list(catalog['consumers']['agents'])
    if (inputs.role == 'worker' and inputs.task_type in ('routine', 'documentation')
            and inputs.repository_area == 'documentation'
            and inputs.operation_type in ('implement', 'document')
            and inputs.review_mode == 'none'
            and bundle['dependency'] == 'known' and not bundle['protected']):
        # The sole shadow omission is development Jev shadow-routing procedure.
        # Jev restrictions/threshold, every safety/review/model/full gate remain.
        selected.remove('RULE_JEV_SHADOW')
    return sorted(selected)


def _coverage(selected):
    chosen = set(selected)
    return {name: dict(required_rule_ids=list(required),
                       missing_rule_ids=sorted(set(required) - chosen),
                       complete=set(required).issubset(chosen))
            for name, required in COVERAGE_REQUIRED.items()}


def _comparison(inputs, selected):
    if (not isinstance(selected, (tuple, list))
            or any(not isinstance(name, str) or not re.fullmatch(r'RULE_[A-Z0-9_]{1,100}', name)
                   for name in selected)
            or len(selected) != len(set(selected))):
        raise ValueError('invalid_shadow_selection')
    profile = _oracle_profile(inputs)
    expected = set(EXPECTED_REQUIRED_BY_PROFILE[profile])
    return dict(expected_profile=profile, expected_required_rule_ids=sorted(expected),
                unexpected_omission=sorted(expected - set(selected)),
                unexpected_inclusion=sorted(set(selected) - expected),
                coverage=_coverage(selected))


def compare_candidate_rule_ids(root, inputs, selected_ids):
    """Independent literal-contract comparison, never a production selector."""
    catalog, _ = _authority(root if root is not None else DEFAULT_AUTHORITY_ROOT)
    if set(catalog['consumers']['agents']) != set(BASELINE_FULL_REQUIRED):
        raise ValueError('baseline_rule_graph_mismatch')
    return _comparison(_inputs(inputs), selected_ids)


def _routing_authorities(root):
    provenance = []
    acquired = {}
    for path in (CONFIG_PATH, WORKFLOW_POLICY_PATH):
        raw = context.local_path(root, path).read_bytes()
        text = raw.decode('utf-8')
        context._safe_evidence(text)
        acquired[path] = text
        provenance.append(dict(path=path, sha256=context.digest(raw)))
    config = tomllib.loads(acquired[CONFIG_PATH])
    expected_config = dict(model='gpt-6.1-sol', model_reasoning_effort='high',
                           agents=dict(default_subagent_model='gpt-6.1-sol',
                                       default_subagent_reasoning_effort='high'))
    if config != expected_config:
        raise ValueError('model_configuration_floor_or_schema_mismatch')
    policy = json.loads(acquired[WORKFLOW_POLICY_PATH], object_pairs_hook=rules._unique_keys)
    expected_keys = {'version', 'mode', 'review_skip_enabled', 'confidence_threshold',
                     'max_changed_lines', 'implementation_model', 'normal_effort',
                     'mandatory_effort', 'jev_model', 'api_timeout_seconds', 'jev_rates',
                     'escalation_effort', 'historical_sol_standard_short_context_rates'}
    if not isinstance(policy, dict) or set(policy) != expected_keys:
        raise ValueError('workflow_policy_schema_mismatch')
    if type(policy['version']) is not int or policy['version'] != WORKFLOW_POLICY_VERSION:
        raise ValueError('workflow_policy_version_mismatch')
    if (policy['mode'] != 'shadow' or policy['review_skip_enabled'] is not False
            or type(policy['confidence_threshold']) not in (int, float)
            or policy['confidence_threshold'] != 0.90
            or policy['implementation_model'] != 'gpt-6.1-sol'
            or policy['normal_effort'] != 'high' or policy['mandatory_effort'] != 'high'
            or policy['escalation_effort'] != 'xhigh'):
        raise ValueError('workflow_policy_required_floor_mismatch')
    if (type(policy['max_changed_lines']) is not int or policy['max_changed_lines'] != 80
            or type(policy['api_timeout_seconds']) is not int or policy['api_timeout_seconds'] != 10
            or policy['jev_model'] != 'jev-1.13.0' or policy['jev_rates'] is not None):
        raise ValueError('workflow_policy_versioned_parameters_mismatch')
    historical = policy['historical_sol_standard_short_context_rates']
    if (not isinstance(historical, dict) or set(historical) != {
            'model', 'scope', 'input', 'cached_input', 'output', 'source', 'retrieved_date'}
            or historical['scope'] != 'historical_reference_only'
            or historical['model'] not in ('gpt-6-sol', 'gpt-5.6-sol')
            or not isinstance(historical['source'], str)
            or not isinstance(historical['retrieved_date'], str)
            or any(type(historical[name]) not in (int, float)
                   or not math.isfinite(historical[name]) or historical[name] < 0
                   for name in ('input', 'cached_input', 'output'))):
        raise ValueError('historical_policy_must_not_be_execution_fallback')
    return provenance


def _authority(root):
    catalog = rules.load_catalog(root)
    if set(catalog['consumers']['agents']) != set(BASELINE_FULL_REQUIRED):
        raise ValueError('baseline_rule_graph_mismatch')
    provenance = []
    for consumer, path in rules.DOCUMENT_PATHS.items():
        raw = context.local_path(root, path).read_bytes()
        document = raw.decode('utf-8')
        rules.expand_document_rules(root, document, consumer)
        provenance.append(dict(path=path, sha256=context.digest(raw)))
    raw = context.local_path(root, rules.CATALOG_PATH).read_bytes()
    provenance.append(dict(path=rules.CATALOG_PATH, sha256=context.digest(raw)))
    provenance.extend(_routing_authorities(root))
    return catalog, sorted(provenance, key=lambda source: source['path'])


def _body_references(catalog, selected):
    return [dict(id=name, body_sha256=catalog['rules'][name]['body_sha256'],
                 catalog_path=rules.CATALOG_PATH,
                 catalog_sha256=catalog['canonical_sha256'], requires_full_body=True)
            for name in selected if name in catalog['rules']]


def _full_body_hash(catalog, selected):
    if not selected or any(name not in catalog['rules'] for name in selected):
        return None
    return canonical_hash([dict(id=name, body=catalog['rules'][name]['body'])
                           for name in selected])


def build_policy_capsule(root, bundle, inputs):
    """Return a deterministic shadow report and the full actual required policy.

    Unknown/uncertain/stale inputs use full fallback. Unavailable canonical
    authority blocks until it is reacquired; missing policy is never permission.
    root=None validates syntax only and forces repository-binding full fallback.
    The report does not slice changed files, select dependencies, skip review,
    prove verification, or authorize production capsule adoption.
    """
    authority_root = root if root is not None else DEFAULT_AUTHORITY_ROOT
    full = sorted(BASELINE_FULL_REQUIRED)
    report = dict(schema_version=SCHEMA_VERSION, capsule_version=CAPSULE_VERSION,
                  mode='shadow', production_adoption=PRODUCTION_ADOPTION,
                  actual_policy_mode='full_required', actual_rule_ids=full,
                  selected_rule_ids=full, omitted_rule_ids=[], candidate_rule_ids=[],
                  candidate_omitted_rule_ids=[], unexpected_omission=[], unexpected_inclusion=[],
                  candidate_body_references=[], candidate_full_body_sha256=None,
                  actual_policy=[], actual_full_body_sha256=None,
                  rule_catalog_sha256=None, rule_catalog_version=None,
                  authority_sources=[], authority_acquisition_required=False,
                  routing_authorities_validated=False, workflow_policy_version=None,
                  context_acquisition_required=False,
                  source_binding=dict(repository_validated=False, base=None, head=None,
                                      fingerprint=None, index_sha256=None, bundle_sha256=None),
                  inputs=None, expected_profile='full', expected_required_rule_ids=full,
                  coverage=_coverage([]), candidate_coverage=_coverage([]), fallback_reasons=[],
                  changed_file_slicing=False, dependency_selection_changed=False,
                  review_skip_enabled=False, jev_confidence_threshold=0.90,
                  classification_is_host_execution_proof=False)
    try:
        catalog, sources = _authority(authority_root)
    except (OSError, UnicodeError, ValueError, TypeError, RecursionError):
        report.update(status='BLOCKED', actual_policy_mode='full_required_unavailable',
                      authority_acquisition_required=True,
                      fallback_reasons=['canonical_authority_unavailable'])
        report['sha256'] = canonical_hash(report)
        return report
    report.update(rule_catalog_sha256=catalog['canonical_sha256'],
                  rule_catalog_version=catalog['rule_version'], authority_sources=sources,
                  routing_authorities_validated=True, workflow_policy_version=WORKFLOW_POLICY_VERSION,
                  actual_policy=[copy.deepcopy(catalog['rules'][name]) for name in full],
                  actual_full_body_sha256=_full_body_hash(catalog, full))
    reasons = []
    clean = None
    try:
        clean = _inputs(inputs)
        report['inputs'] = {**asdict(clean), 'changed_paths': list(clean.changed_paths)}
    except (ValueError, TypeError, RecursionError):
        reasons.append('input_parsing_error')
    try:
        context._validate_bundle(bundle, root=root)
        report['source_binding'].update({name: bundle[name] for name in
                                       ('base', 'head', 'fingerprint', 'index_sha256')})
        report['source_binding'].update(bundle_sha256=canonical_hash(bundle),
                                       repository_validated=root is not None)
    except (ValueError, OSError, TypeError, RecursionError, subprocess.CalledProcessError):
        reasons.append('bundle_validation_failed')
        report['context_acquisition_required'] = True
    if root is None:
        reasons.append('repository_binding_required')
        report['context_acquisition_required'] = True
    if clean is not None and 'bundle_validation_failed' not in reasons:
        reasons.extend(_issues(clean, bundle))
    reasons = list(dict.fromkeys(reasons))
    candidate = full
    if not reasons:
        try:
            candidate = _select_candidate(catalog, clean, bundle)
            comparison = _comparison(clean, candidate)
        except (ValueError, TypeError, KeyError, RecursionError):
            reasons.append('capsule_generation_error')
            candidate = full
            comparison = _comparison(None, full)
    else:
        comparison = _comparison(None, full)
    report.update({key: comparison[key] for key in
                  ('expected_profile', 'expected_required_rule_ids',
                   'unexpected_omission', 'unexpected_inclusion')})
    if comparison['unexpected_omission']:
        reasons.append('shadow_required_rule_omission')
    if comparison['unexpected_inclusion']:
        reasons.append('shadow_unexpected_rule_inclusion')
    report['candidate_rule_ids'] = sorted(candidate)
    report['candidate_omitted_rule_ids'] = sorted(set(full) - set(candidate))
    report['candidate_body_references'] = _body_references(catalog, sorted(candidate))
    report['candidate_full_body_sha256'] = _full_body_hash(catalog, sorted(candidate))
    effective = full if reasons else sorted(candidate)
    report.update(selected_rule_ids=effective, omitted_rule_ids=sorted(set(full) - set(effective)),
                  coverage=_coverage(effective), candidate_coverage=comparison['coverage'],
                  fallback_reasons=list(dict.fromkeys(reasons)),
                  status='FALLBACK' if reasons else 'SHADOW')
    # Last coherency boundary: never publish a usable snapshot after authority
    # bytes or the validated repository bundle changed during construction.
    # Revalidation retains the existing context/dependency selection unchanged.
    try:
        current_catalog, current_sources = _authority(authority_root)
        if current_catalog != catalog or current_sources != sources:
            raise ValueError('authority_changed')
    except (OSError, UnicodeError, ValueError, TypeError, RecursionError):
        report.update(status='BLOCKED', actual_policy_mode='full_required_unavailable',
                      actual_policy=[], actual_full_body_sha256=None,
                      candidate_body_references=[], candidate_full_body_sha256=None,
                      authority_acquisition_required=True, authority_sources=[],
                      routing_authorities_validated=False, context_acquisition_required=True,
                      coverage=_coverage([]), candidate_coverage=_coverage([]))
        report['source_binding']['repository_validated'] = False
        report['fallback_reasons'].append('canonical_authority_changed_during_generation')
    else:
        if root is not None and report['source_binding']['repository_validated']:
            try:
                context._validate_bundle(bundle, root=root)
            except (ValueError, OSError, TypeError, RecursionError, subprocess.CalledProcessError):
                report.update(status='FALLBACK', selected_rule_ids=full, omitted_rule_ids=[],
                              coverage=_coverage(full), context_acquisition_required=True)
                report['source_binding']['repository_validated'] = False
                report['fallback_reasons'].append('bundle_changed_during_generation')
    report['sha256'] = canonical_hash(report)
    return report
