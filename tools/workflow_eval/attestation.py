"""Content-addressed reuse of completed independent review evidence.

This is a local trusted-evidence cache, not an authentication service. Callers
must acquire the original verification record and an actual host receipt through
their trusted workflow. Setting observed/acquired flags or inventing a receipt
does not prove an execution occurred. Hashes detect mismatches, not malicious
replacement of a record plus its hashes. Requested settings are never receipts.
Read-only/independence observations are workflow metadata, not OS permissions.

The verification input is an original record with status PASS, acquired=True,
stale=False, commit/tree and nonempty required_checks covered by checks carrying
name/status/exit_code/warnings. Missing, failed or warned checks cannot be cached.
The envelope additionally declares artifacts (path, role, sha256, size_bytes),
including exactly one role='record' original JSON and log originals. Required
checks each declare nonempty artifacts lists referencing logs. log_paths declares
the complete log scope. The original JSON must equal this envelope excluding
its top-level artifacts field (avoiding a circular record self-hash); every
original is reopened, hashed, decoded and screened under the repository root.
Ignored .workflow-eval paths are allowed. Flags/digests without originals fail.
Different source commits need explicit source_equivalence='git_tree_exact' and
commit_sensitive=False applicability in that same original record, as well as
Git-proven equal trees and every other review input equal. Commit-sensitive CI
or build checks must not assert this applicability. No digest infers PASS.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from . import context
from .serialization import canonical_hash, canonical_json
from .triage import ACTIVE_SOL_MODEL, PROTECTED, policy, review_effort
from .verification_context import _read, _record, _nested_problems, _log_problems

SCHEMA_VERSION = 1
MAX_CACHE_BYTES = 2 * 1024 * 1024
REVIEW_FIELDS = {'status', 'completed', 'independent', 'fresh_context', 'read_only',
                 'acquired_verification', 'material_uncertainty', 'stale_evidence',
                 'verdict', 'findings', 'missing_context_ids'}
RECEIPT_FIELDS = {'source', 'receipt_id', 'model', 'reasoning_effort', 'fork_turns',
                  'observed', 'completed', 'independent', 'fresh_context', 'read_only',
                  'identity_sha256', 'review_sha256'}
ATTESTATION_FIELDS = {'schema_version', 'identity', 'identity_sha256', 'source_head',
                      'verification', 'review', 'host_receipt', 'attestation_sha256'}


def _sha(value, length=64):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{%d}' % length, value) is not None


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _commit_tree(root, commit):
    if not _sha(commit, 40):
        raise ValueError('invalid_source_commit')
    tree = context.git(root, 'rev-parse', '--verify', commit + '^{tree}').decode().strip()
    if not _sha(tree, 40):
        raise ValueError('invalid_source_tree')
    return tree


def _verification(root, record, tree, current_head):
    context._safe_evidence(record)
    if (not isinstance(record, dict) or record.get('status') != 'PASS'
            or record.get('acquired') is not True or record.get('stale') is not False
            or record.get('tree') != tree
            or _commit_tree(root, record.get('commit')) != tree):
        raise ValueError('acquired_current_verification_required')
    required, checks = record.get('required_checks'), record.get('checks')
    if (not isinstance(required, list) or not required
            or any(not _text(name) for name in required) or len(required) != len(set(required))
            or not isinstance(checks, list) or not checks):
        raise ValueError('required_verification_missing')
    names = []
    for check in checks:
        if (not isinstance(check, dict) or not _text(check.get('name'))
                or check.get('status') != 'PASS' or type(check.get('exit_code')) is not int
                or check['exit_code'] != 0 or check.get('warnings') != []):
            raise ValueError('verification_failure_warning_or_unknown')
        names.append(check['name'])
    if len(names) != len(set(names)) or not set(required).issubset(names):
        raise ValueError('required_verification_missing')
    if record['commit'] != current_head and not (
            record.get('source_equivalence') == 'git_tree_exact'
            and record.get('commit_sensitive') is False):
        raise ValueError('source_commit_verification_applicability_unknown')
    _acquire_artifacts(root, record)
    canonical_json(record)


def _acquire_artifacts(root, record):
    """Acquire all declared originals; source/check claims need exact bodies."""
    references = record.get('artifacts')
    if not isinstance(references, list) or not references:
        raise ValueError('original_verification_artifacts_required')
    all_references, record_names = {}, []

    def add(artifacts, *, logs_only=False):
        if not isinstance(artifacts, list) or not artifacts:
            raise ValueError('original_verification_artifacts_required')
        local_names = set()
        for artifact in artifacts:
            if (not isinstance(artifact, dict) or set(artifact) != {'path', 'role', 'sha256', 'size_bytes'}
                    or not context._path_name(artifact['path']) or not _sha(artifact['sha256'])
                    or type(artifact['size_bytes']) is not int or artifact['size_bytes'] < 0
                    or artifact['role'] not in ('record', 'log')
                    or (logs_only and artifact['role'] != 'log')):
                raise ValueError('invalid_original_verification_artifact')
            name = artifact['path']
            if name in local_names:
                raise ValueError('duplicate_original_verification_artifact')
            local_names.add(name)
            if name in all_references and canonical_json(all_references[name]) != canonical_json(artifact):
                raise ValueError('contradictory_original_verification_artifact')
            all_references[name] = artifact
            if artifact['role'] == 'record':
                record_names.append(name)

    add(references)
    if len(record_names) != 1:
        raise ValueError('one_original_verification_record_required')
    for check in record['checks']:
        # Even extra, non-required checks cannot conceal declared originals.
        add(check.get('artifacts'), logs_only=True)
        for field in ('commit', 'source', 'tree'):
            if field in check and canonical_json(check[field]) != canonical_json(
                    record['tree'] if field == 'tree' else record['commit']):
                raise ValueError('contradictory_check_source')
    logs = sorted(name for name, artifact in all_references.items() if artifact['role'] == 'log')
    declared = record.get('log_paths')
    if (not logs or not isinstance(declared, list) or len(declared) != len(set(declared))
            or not all(context._path_name(name) for name in declared) or sorted(declared) != logs):
        raise ValueError('original_verification_log_scope_missing_or_mismatched')
    observed = {}
    for name, artifact in all_references.items():
        raw, text, problem = _read(root, name)
        if (problem or text is None or context.digest(raw) != artifact['sha256']
                or len(raw) != artifact['size_bytes']):
            raise ValueError('original_verification_artifact_unavailable_or_mismatched')
        observed[name] = text
        if artifact['role'] == 'log' and list(_log_problems(text, record.get('passed'), record.get('failed'))):
            raise ValueError('contradictory_original_verification_log')
    for check in record['checks']:
        for reference in check['artifacts']:
            if list(_log_problems(observed[reference['path']], check.get('passed'), check.get('failed'))):
                raise ValueError('contradictory_original_check_log')
    original = _record(observed[record_names[0]])
    expected = {key: value for key, value in record.items() if key != 'artifacts'}
    if original is None or canonical_json(original) != canonical_json(expected):
        raise ValueError('original_verification_record_envelope_mismatch')
    if list(_nested_problems(original)):
        raise ValueError('contradictory_original_verification_record')
    # Detect changes while acquiring multiple originals as well as at lookup.
    for name, artifact in all_references.items():
        raw, text, problem = _read(root, name)
        if (problem or text is None or context.digest(raw) != artifact['sha256']
                or len(raw) != artifact['size_bytes']):
            raise ValueError('original_verification_artifact_changed_during_acquisition')


def _rule_hashes(root, names):
    paths = {'AGENTS.md', '.codex/config.toml', '.agents/skills/model-orchestrator/SKILL.md',
             '.agents/skills/typesafe-ai/SKILL.md'}
    for name in names:
        parent = Path(name).parent
        for ancestor in [parent, *parent.parents]:
            if str(ancestor) != '.':
                paths.add(ancestor.as_posix() + '/AGENTS.md')
    # Compressed rule consumers are not complete without their validated source.
    # A missing catalog must cause a cache miss/full fresh review, not an identity
    # that accidentally omits the referenced safety authority.
    marked = any('<!-- canonical-rules: ' in context.local_path(root, name).read_text(encoding='utf-8')
                 for name in paths if context.local_path(root, name).is_file())
    catalog = context.local_path(root, '.agents/rules/canonical.json')
    if marked or catalog.is_file():
        from .rules import load_catalog, expand_document_rules
        load_catalog(root)
        paths.add('.agents/rules/canonical.json')
        for name in sorted(paths):
            path = context.local_path(root, name)
            if not path.is_file():
                continue
            document = path.read_text(encoding='utf-8')
            if '<!-- canonical-rules: ' in document:
                consumer = ('model-orchestrator' if '/model-orchestrator/' in name else
                            'typesafe-ai' if '/typesafe-ai/' in name else 'agents')
                expand_document_rules(root, document, consumer)
    return {name: context.digest(context.local_path(root, name).read_bytes())
            for name in sorted(paths) if context.local_path(root, name).is_file()}


def build_identity(root, bundle, *, specification, repository_rules, verification,
                   unresolved_questions, instruction_version,
                   reviewer_model=ACTIVE_SOL_MODEL, reviewer_effort='high', escalation=None):
    """Rebuild actual Git/bundle evidence; never accept caller-supplied hashes.

    Only clean known unprotected fully acquired contexts are eligible. The
    current commit is provenance, not identity: exact trees can have different
    commit metadata, provided the original verification explicitly applies.
    """
    root = Path(root).resolve()
    context._validate_bundle(bundle, root)
    if (not _text(specification) or not _text(repository_rules) or not _text(instruction_version)
            or not isinstance(unresolved_questions, list)
            or any(not _text(question) for question in unresolved_questions)):
        raise ValueError('explicit_review_inputs_required')
    context._safe_evidence([specification, repository_rules, unresolved_questions, instruction_version])
    if reviewer_model != ACTIVE_SOL_MODEL:
        raise ValueError('observed_active_model_required')
    review_effort(reviewer_effort, escalation)
    if (bundle['protected'] or bundle['dependency'] != 'known' or bundle['expansion_required']
            or PROTECTED.search('\n'.join([specification, *unresolved_questions]))):
        raise ValueError('full_independent_review_required')
    if bundle['status_porcelain']:
        raise ValueError('clean_review_tree_required')
    head = context.git(root, 'rev-parse', 'HEAD').decode().strip()
    tree = _commit_tree(root, head)
    _verification(root, verification, tree, head)
    common = context.git(root, 'rev-parse', '--git-common-dir').decode().strip()
    common = (root / common).resolve()
    # No remote URL is emitted: URLs may contain credentials. Local repository
    # and common-dir identity are conservative; another checkout is a miss.
    repository = {'worktree_sha256': canonical_hash(os.path.normcase(str(root))),
                  'git_common_dir_sha256': canonical_hash(os.path.normcase(str(common)))}
    changed = set(bundle['changed_paths'])
    contents = {block['path']: context.digest(context.local_path(root, block['path']).read_bytes())
                for block in bundle['blocks']}
    actual_patch = context.git(root, 'diff', '--no-ext-diff', '--no-textconv', '--binary',
                               bundle['base'], '--')
    module_root = Path(__file__).parent
    schema_hash = context.digest((module_root / 'review-schema.json').read_bytes())
    # Bind the instruction/validation implementation as well as version labels.
    implementation_hashes = {name: context.digest((module_root / name).read_bytes())
                             for name in ('attestation.py', 'context.py', 'triage.py',
                                          'serialization.py', 'spawn.py', 'verification_context.py',
                                          'rules.py', 'verification_delivery.py', 'decision_ledger.py')}
    rules = policy()
    identity = dict(repository=repository, tree=tree, base=bundle['base'],
                    diff_sha256=context.digest(actual_patch),
                    changed_paths=list(bundle['changed_paths']),
                    changed_content_hashes={name: contents.get(name) for name in sorted(changed)},
                    dependency_hashes={name: value for name, value in sorted(contents.items()) if name not in changed},
                    task_sha256=canonical_hash(bundle['task']), specification_sha256=canonical_hash(specification),
                    repository_rules_sha256=canonical_hash(repository_rules),
                    rule_file_hashes=_rule_hashes(root, contents),
                    policy_sha256=canonical_hash(rules), policy_version=rules['version'],
                    classification={'protected': bundle['protected'], 'dependency': bundle['dependency'],
                                    'expansion_required': bundle['expansion_required']},
                    verification_sha256=canonical_hash(verification),
                    questions_sha256=canonical_hash(unresolved_questions),
                    reviewer_model=reviewer_model, reviewer_effort=reviewer_effort,
                    escalation_sha256=canonical_hash(escalation),
                    bundle_schema_version=bundle['schema_version'],
                    attestation_schema_version=SCHEMA_VERSION, review_schema_sha256=schema_hash,
                    instruction_version=instruction_version, implementation_hashes=implementation_hashes)
    if not context.is_current(root, bundle):
        raise ValueError('repository_changed_during_attestation')
    return identity


def _review(record):
    context._safe_evidence(record)
    if (not isinstance(record, dict) or set(record) != REVIEW_FIELDS
            or record['status'] != 'OK' or record['verdict'] != 'pass'
            or any(record[field] is not True for field in ('completed', 'independent', 'fresh_context',
                                                           'read_only', 'acquired_verification'))
            or record['material_uncertainty'] is not False or record['stale_evidence'] is not False
            or record['missing_context_ids'] != [] or not isinstance(record['findings'], list)):
        raise ValueError('completed_independent_ok_review_required')
    for finding in record['findings']:
        if (not isinstance(finding, dict) or set(finding) != {'severity', 'code', 'evidence_id', 'reason'}
                or finding['severity'] != 'minor' or not isinstance(finding['code'], str)
                or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', finding['code'])
                or not _text(finding['evidence_id']) or not _text(finding['reason'])):
            raise ValueError('unresolved_important_findings_or_invalid_review')


def _receipt(record, identity, review):
    context._safe_evidence(record)
    if (not isinstance(record, dict) or set(record) != RECEIPT_FIELDS
            or record['source'] != 'host' or not _text(record['receipt_id'])
            or any(record[field] is not True for field in ('observed', 'completed', 'independent',
                                                           'fresh_context', 'read_only'))
            or record['model'] != identity['reviewer_model']
            or record['reasoning_effort'] != identity['reviewer_effort']
            or record['fork_turns'] != 'none'
            or record['identity_sha256'] != canonical_hash(identity)
            or record['review_sha256'] != canonical_hash(review)):
        raise ValueError('matching_observed_host_receipt_required')


def _validate_attestation(value, identity=None, root=None, head=None):
    if (not isinstance(value, dict) or set(value) != ATTESTATION_FIELDS
            or type(value['schema_version']) is not int or value['schema_version'] != SCHEMA_VERSION
            or not isinstance(value['identity'], dict) or not _sha(value['source_head'], 40)
            or value['identity_sha256'] != canonical_hash(value['identity'])
            or value['attestation_sha256'] != canonical_hash({
                k: v for k, v in value.items() if k != 'attestation_sha256'})):
        raise ValueError('invalid_attestation')
    context._safe_evidence(value)
    if identity is not None and canonical_json(value['identity']) != canonical_json(identity):
        raise ValueError('attestation_inputs_differ')
    if value['identity'].get('reviewer_model') != ACTIVE_SOL_MODEL:
        raise ValueError('attestation_model_floor')
    if value['identity'].get('reviewer_effort') not in ('high', 'xhigh'):
        raise ValueError('attestation_effort_floor')
    if value['identity'].get('verification_sha256') != canonical_hash(value['verification']):
        raise ValueError('attestation_verification_mismatch')
    _review(value['review'])
    _receipt(value['host_receipt'], value['identity'], value['review'])
    if root is not None:
        if _commit_tree(root, value['source_head']) != identity['tree']:
            raise ValueError('attestation_source_tree_mismatch')
        _verification(root, value['verification'], identity['tree'], head)
        if value['source_head'] != head and not (
                value['verification'].get('source_equivalence') == 'git_tree_exact'
                and value['verification'].get('commit_sensitive') is False):
            raise ValueError('attestation_source_applicability_unknown')


def create_attestation(root, bundle, review, host_receipt, **inputs):
    """Record an already completed review; this function executes no reviewer."""
    identity = build_identity(root, bundle, **inputs)
    _review(review)
    _receipt(host_receipt, identity, review)
    value = dict(schema_version=SCHEMA_VERSION, identity=identity,
                 identity_sha256=canonical_hash(identity), source_head=bundle['head'],
                 verification=inputs['verification'], review=review, host_receipt=host_receipt)
    value['attestation_sha256'] = canonical_hash(value)
    _validate_attestation(value, identity, root, bundle['head'])
    # A caller's later mutation must not mutate this completed record in memory.
    return json.loads(canonical_json(value))


def save_attestation(cache_dir, attestation):
    """Atomically save a validated record in a caller-controlled trusted cache."""
    _validate_attestation(attestation)
    directory = Path(cache_dir)
    if directory.is_symlink():
        raise ValueError('uncertain_cache_location')
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (attestation['identity_sha256'] + '.json')
    if target.is_symlink():
        raise ValueError('uncertain_cache_location')
    raw = canonical_json(attestation).encode('utf-8')
    if len(raw) > MAX_CACHE_BYTES:
        raise ValueError('attestation_too_large')
    fd, temporary = tempfile.mkstemp(prefix='.attestation-', dir=directory)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return target


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate_attestation_key')
        result[key] = value
    return result


def _invalid_constant(_):
    raise ValueError('nonfinite_attestation')


def lookup_attestation(cache_dir, root, bundle, **inputs):
    """Rebuild current inputs and return a miss/full review on any uncertainty."""
    result = dict(hit=False, full_review_required=True, actual_review_skipped=False,
                  new_review_executed=False, review_skip_enabled=False,
                  mandatory_review_satisfied_by=None, reason='full_review_required', attestation=None)
    try:
        identity = build_identity(root, bundle, **inputs)
        directory = Path(cache_dir)
        path = directory / (canonical_hash(identity) + '.json')
        if directory.is_symlink() or path.is_symlink():
            raise ValueError('uncertain_cache_location')
        with path.open('rb') as stream:
            raw = stream.read(MAX_CACHE_BYTES + 1)
        if len(raw) > MAX_CACHE_BYTES:
            raise ValueError('attestation_too_large')
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object,
                           parse_constant=_invalid_constant)
        _validate_attestation(value, identity, root, bundle['head'])
        # Rebuild after reading: a stale identity is not a cache hit.
        if build_identity(root, bundle, **inputs) != identity:
            raise ValueError('repository_changed_during_attestation')
        result.update(hit=True, full_review_required=False, reason='exact_completed_review_evidence',
                      mandatory_review_satisfied_by='matching_attestation', attestation=value)
    except (ValueError, KeyError, TypeError, OSError, UnicodeError, subprocess.SubprocessError, RecursionError):
        # Do not expose exception text: paths and source evidence may be private.
        result['reason'] = 'missing_mismatched_or_uncertain_attestation'
    return result
