"""Source-bound specification transport with auditable decision supersession.

The ledger records trusted accepted decisions, not proof of user authorization
or an exhaustive replacement for conversation, source, rules or review. Missing
information is unknown. Its canonical hashes detect corruption, not malicious
rewriting of all records and hashes. Critical policies are acquired from the
current canonical rule catalog; a ledger cannot weaken their bodies or floors.

All provenance references are safe repository-relative files with actual SHA256
and UTF-8 bodies. Git commit/tree plus working/index fingerprint bind the source.
History retains previous snapshots without recursively duplicating history.
Ordinary updates require current evidence; explicit rebind_source permits a new
version only after reacquiring current authorities and retained prior provenance.
Invalid/stale/incomplete ledgers expand full independent authorities; unavailable
authority or prior verified specification blocks transport rather than approving
an omitted requirement. Read-only independent review and full source context
remain mandatory outside this transport helper.
"""
import copy
from datetime import datetime
from pathlib import Path
import re
import subprocess

from . import context
from .serialization import canonical_hash, canonical_json
from .verification_context import _read

SCHEMA_VERSION = 1
CATALOG_PATH = '.agents/rules/canonical.json'
FIELDS = {'schema_version', 'ledger_version', 'repository_identity', 'source_commit', 'source_tree',
          'source_fingerprint', 'accepted_decisions', 'active_specification', 'specification_provenance_ids',
          'forbidden_changes', 'safety_invariants', 'protected_invariants', 'model_policy', 'review_policy',
          'unresolved_questions', 'superseded_decisions', 'provenance', 'updated_at', 'rule_catalog_hash',
          'rule_catalog_version', 'previous_sha256', 'transition_reason', 'history', 'sha256'}
UNSET = object()


def _sha(value, length=64):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{%d}' % length, value) is not None


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _id(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,119}', value) is not None


def _strings(value, *, nonempty=False):
    return (isinstance(value, list) and (bool(value) or not nonempty)
            and all(_text(item) for item in value) and len(value) == len(set(value)))


def _time(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', value):
        raise ValueError('invalid_ledger_timestamp')
    try:
        return datetime.fromisoformat(value[:-1] + '+00:00')
    except ValueError:
        raise ValueError('invalid_ledger_timestamp') from None


def _repository(root):
    return context.digest(context.git(root, 'rev-parse', '--path-format=absolute', '--git-common-dir').strip())


def _source(root):
    return dict(repository_identity=_repository(root),
                source_commit=context.git(root, 'rev-parse', 'HEAD').decode().strip(),
                source_tree=context.git(root, 'rev-parse', 'HEAD^{tree}').decode().strip(),
                source_fingerprint=context.fingerprint(root))


def _policies(root):
    # Import lazily: the rule catalog loader remains the single authority and
    # ledger imports do not create a spawn/resume import cycle.
    from .rules import load_catalog, resolve_rules, SAFETY_RULE_IDS, MODEL_RULE_IDS, REVIEW_RULE_IDS, PROTECTED_RULE_IDS
    catalog = load_catalog(root)
    ids = list(dict.fromkeys([*SAFETY_RULE_IDS, *MODEL_RULE_IDS, *REVIEW_RULE_IDS, *PROTECTED_RULE_IDS]))
    resolved = {rule['id']: rule['body'] for rule in resolve_rules(root, ids)}
    safety = {name: resolved[name] for name in SAFETY_RULE_IDS}
    protected = {name: resolved[name] for name in PROTECTED_RULE_IDS}
    model = dict(model='gpt-6.1-sol', root_effort='high', orchestrator_effort='high', integrate_effort='high',
                 verify_effort='high', routine_worker_effort='medium', complex_worker_effort='high',
                 explorer_effort='medium', researcher_effort='medium', evidence_based_xhigh=True,
                 automatic_astra=False, silent_fallback=False, jev_confidence=0.90,
                 rules={name: resolved[name] for name in MODEL_RULE_IDS})
    review = dict(model='gpt-6.1-sol', reasoning_effort='high', mandatory=True, independent=True,
                  fresh_context=True, read_only=True, full_required_context=True, review_skip_enabled=False,
                  verification_digests_are_evidence=False,
                  rules={name: resolved[name] for name in REVIEW_RULE_IDS})
    return dict(safety_invariants=safety, protected_invariants=protected, model_policy=model,
                review_policy=review, rule_catalog_hash=catalog['canonical_sha256'],
                rule_catalog_version=catalog['rule_version'])


def _decision(value, provenance_ids):
    if (not isinstance(value, dict) or set(value) != {'id', 'text', 'provenance_ids'}
            or not _id(value['id']) or not _text(value['text'])
            or not _strings(value['provenance_ids'], nonempty=True)
            or not set(value['provenance_ids']).issubset(provenance_ids)):
        raise ValueError('invalid_or_unbound_ledger_decision')


def _provenance(root, entries, *, historical_commit=None):
    if not isinstance(entries, list) or not entries:
        raise ValueError('ledger_provenance_required')
    ids, paths, bodies = set(), set(), []
    for entry in entries:
        if (not isinstance(entry, dict) or set(entry) != {'id', 'path', 'sha256'}
                or not _id(entry['id']) or not context._path_name(entry['path'])
                or not _sha(entry['sha256']) or entry['id'] in ids or entry['path'] in paths):
            raise ValueError('invalid_ledger_provenance')
        ids.add(entry['id'])
        paths.add(entry['path'])
        raw, text, problem = _read(root, entry['path'])
        if historical_commit is not None and (problem or context.digest(raw) != entry['sha256']):
            # A committed original is recoverable after a later source update.
            # Ignored/uncommitted originals must still be retained locally.
            raw = context.git(root, 'show', historical_commit + ':' + entry['path'])
            text = raw.decode('utf-8')
            context._safe_evidence(text)
            problem = None
        if problem or text is None or context.digest(raw) != entry['sha256']:
            raise ValueError('missing_or_changed_ledger_provenance')
        bodies.append(dict(id=entry['id'], path=entry['path'], sha256=entry['sha256'], text=text))
    return ids, bodies


def _core(root, value, policies, *, historical=False):
    context._safe_evidence(value)
    if (not isinstance(value, dict) or set(value) != FIELDS
            or type(value['schema_version']) is not int or value['schema_version'] != SCHEMA_VERSION
            or type(value['ledger_version']) is not int or value['ledger_version'] < 1
            or not isinstance(value['history'], list)
            or value['sha256'] != canonical_hash({k: v for k, v in value.items() if k != 'sha256'})
            or not _text(value['active_specification']) or not _text(value['transition_reason'])
            or not _strings(value['forbidden_changes'], nonempty=True)
            or not _strings(value['unresolved_questions'])
            or not _strings(value['specification_provenance_ids'], nonempty=True)):
        raise ValueError('invalid_ledger_schema_or_hash')
    _time(value['updated_at'])
    for field, actual in policies.items():
        if canonical_json(value[field]) != canonical_json(actual):
            raise ValueError('missing_stale_or_weakened_critical_ledger_policy')
    if (not _sha(value['repository_identity']) or value['repository_identity'] != _repository(root)
            or not _sha(value['source_commit'], 40) or not _sha(value['source_tree'], 40)
            or not _sha(value['source_fingerprint'])):
        raise ValueError('invalid_ledger_source_identity')
    tree = context.git(root, 'rev-parse', '--verify', value['source_commit'] + '^{tree}').decode().strip()
    if tree != value['source_tree']:
        raise ValueError('ledger_source_tree_mismatch')
    ids, _ = _provenance(root, value['provenance'],
                         historical_commit=value['source_commit'] if historical else None)
    if not set(value['specification_provenance_ids']).issubset(ids):
        raise ValueError('unbound_ledger_specification')
    if not isinstance(value['accepted_decisions'], list) or not isinstance(value['superseded_decisions'], list):
        raise ValueError('invalid_ledger_decision_state')
    active, retired, replacements = {}, {}, {}
    for decision in value['accepted_decisions']:
        _decision(decision, ids)
        if decision['id'] in active:
            raise ValueError('duplicate_ledger_decision')
        active[decision['id']] = decision
    for item in value['superseded_decisions']:
        if (not isinstance(item, dict) or set(item) != {'decision', 'reason', 'replacement_id', 'ledger_version'}
                or not _text(item['reason']) or not _id(item['replacement_id'])
                or type(item['ledger_version']) is not int or not 2 <= item['ledger_version'] <= value['ledger_version']):
            raise ValueError('invalid_ledger_supersession')
        _decision(item['decision'], ids)
        name = item['decision']['id']
        if name in active or name in retired:
            raise ValueError('duplicate_ledger_decision')
        retired[name] = item
        replacements[name] = item['replacement_id']
    for name in retired:
        visited = set()
        while name in retired:
            if name in visited:
                raise ValueError('cyclic_ledger_supersession')
            visited.add(name)
            name = replacements[name]
        if name not in active:
            raise ValueError('missing_ledger_replacement')
    if not historical:
        current = _source(root)
        if canonical_json({name: value[name] for name in current}) != canonical_json(current):
            raise ValueError('stale_ledger_source')


def _transition(previous, current):
    old = {item['id']: item for item in previous['accepted_decisions']}
    active = {item['id']: item for item in current['accepted_decisions']}
    retired = {item['decision']['id']: item for item in current['superseded_decisions']}
    prior_retired = {item['decision']['id']: item for item in previous['superseded_decisions']}
    if not set(previous['forbidden_changes']).issubset(current['forbidden_changes']):
        raise ValueError('ledger_forbidden_change_removed')
    for name, item in prior_retired.items():
        if name not in retired or canonical_json(item) != canonical_json(retired[name]):
            raise ValueError('rewritten_ledger_supersession')
    for name, decision in old.items():
        if name in active:
            if canonical_json(decision) != canonical_json(active[name]):
                raise ValueError('silently_rewritten_ledger_decision')
        elif (name not in retired or canonical_json(retired[name]['decision']) != canonical_json(decision)
              or retired[name]['ledger_version'] != current['ledger_version']):
            raise ValueError('untraced_ledger_supersession')
    for name in retired.keys() - prior_retired.keys():
        if name not in old:
            raise ValueError('invented_ledger_supersession')
    if _time(current['updated_at']) <= _time(previous['updated_at']):
        raise ValueError('ledger_timestamp_not_advanced')


def _validate(root, ledger, *, current=True):
    policies = _policies(root)
    _core(root, ledger, policies, historical=not current)
    history = ledger['history']
    if len(history) + 1 != ledger['ledger_version']:
        raise ValueError('unknown_ledger_version_or_missing_history')
    previous = None
    for index, snapshot in enumerate([*history, {k: v for k, v in ledger.items() if k != 'history'}]):
        if not isinstance(snapshot, dict) or set(snapshot) != FIELDS - {'history'}:
            raise ValueError('invalid_ledger_history_snapshot')
        reconstructed = dict(snapshot, history=history[:index])
        _core(root, reconstructed, policies, historical=index < len(history) or not current)
        if snapshot['ledger_version'] != index + 1:
            raise ValueError('unknown_ledger_history_version')
        if previous is None:
            if snapshot['previous_sha256'] is not None or snapshot['superseded_decisions']:
                raise ValueError('invalid_initial_ledger_state')
        else:
            if snapshot['previous_sha256'] != previous['sha256']:
                raise ValueError('broken_ledger_hash_chain')
            _transition(previous, reconstructed)
        previous = reconstructed
    if current:
        actual = _source(root)
        if canonical_json({name: ledger[name] for name in actual}) != canonical_json(actual):
            raise ValueError('source_changed_during_ledger_acquisition')
    return copy.deepcopy(ledger)


def validate_ledger(root, ledger):
    """Validate source, full authority bodies, policies, hash chain and trace."""
    try:
        return _validate(Path(root).resolve(), ledger)
    except (ValueError, KeyError, TypeError, OSError, UnicodeError, subprocess.SubprocessError,
            RecursionError, ImportError):
        raise ValueError('invalid_stale_or_incomplete_ledger_expand_full_authority') from None


def create_ledger(root, *, active_specification, specification_provenance_ids, accepted_decisions,
                  forbidden_changes, unresolved_questions, provenance, updated_at,
                  safety_invariants=None, protected_invariants=None, model_policy=None, review_policy=None):
    """Acquire current authorities and record explicit trusted accepted inputs."""
    root = Path(root).resolve()
    policies = _policies(root)
    for name, provided in (('safety_invariants', safety_invariants), ('protected_invariants', protected_invariants),
                           ('model_policy', model_policy), ('review_policy', review_policy)):
        if provided is not None and canonical_json(provided) != canonical_json(policies[name]):
            raise ValueError('missing_or_weakened_ledger_critical_policy')
    value = dict(schema_version=SCHEMA_VERSION, ledger_version=1, **_source(root), **policies,
                 accepted_decisions=copy.deepcopy(accepted_decisions), active_specification=active_specification,
                 specification_provenance_ids=copy.deepcopy(specification_provenance_ids),
                 forbidden_changes=copy.deepcopy(forbidden_changes), unresolved_questions=copy.deepcopy(unresolved_questions),
                 superseded_decisions=[], provenance=copy.deepcopy(provenance), updated_at=updated_at,
                 previous_sha256=None, transition_reason='initial_authoritative_snapshot', history=[])
    value['sha256'] = canonical_hash(value)
    return validate_ledger(root, value)


def update_ledger(root, ledger, *, updated_at, replacements=(), additions=(), rebind_source=False,
                  active_specification=UNSET, specification_change_reason=None,
                  unresolved_questions=UNSET, forbidden_changes=UNSET,
                  provenance=UNSET, specification_provenance_ids=UNSET):
    """Append one audited version; existing decision IDs cannot be overwritten."""
    root = Path(root).resolve()
    if type(rebind_source) is not bool:
        raise ValueError('explicit_ledger_source_rebind_required')
    old = _validate(root, ledger, current=not rebind_source)
    if not isinstance(replacements, (list, tuple)) or not isinstance(additions, (list, tuple)):
        raise ValueError('invalid_ledger_transition')
    active = {item['id']: copy.deepcopy(item) for item in old['accepted_decisions']}
    all_ids = set(active) | {item['decision']['id'] for item in old['superseded_decisions']}
    new = copy.deepcopy(old)
    new['history'].append({k: copy.deepcopy(v) for k, v in old.items() if k != 'history'})
    new['ledger_version'] += 1
    new['previous_sha256'] = old['sha256']
    new['updated_at'] = updated_at
    new['transition_reason'] = 'explicit_source_rebind' if rebind_source else 'versioned_ledger_update'
    new.update(_source(root))
    for change in replacements:
        if (not isinstance(change, dict) or set(change) != {'decision_id', 'replacement', 'reason'}
                or not _text(change['reason']) or change['decision_id'] not in active
                or not isinstance(change['replacement'], dict) or change['replacement'].get('id') in all_ids):
            raise ValueError('explicit_new_ledger_replacement_and_reason_required')
        replacement = copy.deepcopy(change['replacement'])
        new['superseded_decisions'].append(dict(decision=active.pop(change['decision_id']), reason=change['reason'],
                                               replacement_id=replacement.get('id'), ledger_version=new['ledger_version']))
        active[replacement.get('id')] = replacement
        all_ids.add(replacement.get('id'))
    for decision in additions:
        if not isinstance(decision, dict) or decision.get('id') in all_ids:
            raise ValueError('duplicate_or_reused_ledger_decision_id')
        active[decision.get('id')] = copy.deepcopy(decision)
        all_ids.add(decision.get('id'))
    new['accepted_decisions'] = list(active.values())
    for name, value in (('active_specification', active_specification), ('unresolved_questions', unresolved_questions),
                        ('forbidden_changes', forbidden_changes), ('provenance', provenance),
                        ('specification_provenance_ids', specification_provenance_ids)):
        if value is not UNSET:
            new[name] = copy.deepcopy(value)
    if new['active_specification'] != old['active_specification']:
        if not _text(specification_change_reason):
            raise ValueError('explicit_specification_change_reason_required')
        new['transition_reason'] = specification_change_reason
    elif specification_change_reason is not None:
        raise ValueError('specification_change_reason_without_change')
    new['sha256'] = canonical_hash({k: v for k, v in new.items() if k != 'sha256'})
    return validate_ledger(root, new)


def render_ledger(root, ledger, *, authority_paths=None, prior_verified_specification=None):
    """Transfer full known requirements or independently acquire full authority.

    prior_verified_specification is the trusted original full text supplied by
    the caller; this API does not infer that its label establishes verification.
    It must be acquired, not a digest. Missing originals block the fallback.
    """
    result = dict(route='blocked', payload=None, reasons=[], independent_review_required=True,
                  full_context_required=True, omissions_are_unknown=True, missing_context=[])
    try:
        value = validate_ledger(root, ledger)
        _, bodies = _provenance(root, value['provenance'])
        payload = {name: copy.deepcopy(value[name]) for name in FIELDS - {'history'}}
        payload['history_receipts'] = [dict(ledger_version=item['ledger_version'], sha256=item['sha256'],
                                          source_commit=item['source_commit']) for item in value['history']]
        payload['provenance_bodies'] = bodies
        result.update(route='ledger', payload=payload)
        return result
    except (ValueError, KeyError, TypeError, OSError, UnicodeError, subprocess.SubprocessError, RecursionError):
        result['reasons'].append('ledger_invalid_stale_or_incomplete')
    authorities = {}
    try:
        from .rules import load_catalog, expand_document_rules, DOCUMENT_PATHS, RULE_MARKER_PREFIX
        catalog = load_catalog(root)
        initial_source = _source(root)
        if authority_paths is None:
            tracked = context.git(root, 'ls-files', '-z', '--', 'src').split(b'\0')
            authority_paths = dict(repository_rules=['AGENTS.md'], canonical_docs=['README_JA.md', 'VALIDATION_JA.md', CATALOG_PATH],
                                   source=[name.decode('utf-8') for name in tracked if name])
        if not isinstance(authority_paths, dict) or set(authority_paths) != {'repository_rules', 'canonical_docs', 'source'}:
            raise ValueError('full_authority_categories_required')
        for category, names in authority_paths.items():
            if not _strings(names, nonempty=True):
                raise ValueError('full_authority_category_missing')
            names = list(names)
            if category == 'canonical_docs' and CATALOG_PATH not in names:
                names.append(CATALOG_PATH)
            originals = []
            for name in names:
                raw, text, problem = _read(root, name)
                if problem or text is None:
                    raise ValueError('full_authority_original_unavailable')
                original = dict(path=name, sha256=context.digest(raw), text=text)
                if RULE_MARKER_PREFIX in text:
                    consumers = [consumer for consumer, path in DOCUMENT_PATHS.items() if path == name]
                    if len(consumers) != 1:
                        raise ValueError('unknown_marked_authority_document')
                    expanded = expand_document_rules(root, text, consumers[0])
                    original.update(expanded_text=expanded['text'],
                                    included_rule_ids=expanded['included_rule_ids'],
                                    catalog_sha256=expanded['catalog_sha256'])
                originals.append(original)
            authorities[category] = originals
        if not _text(prior_verified_specification):
            result['missing_context'].append('prior_verified_specification')
        else:
            context._safe_evidence(prior_verified_specification)
        actual = _source(root)
        if canonical_json(actual) != canonical_json(initial_source):
            raise ValueError('source_changed_during_full_authority_acquisition')
        if load_catalog(root)['canonical_sha256'] != catalog['canonical_sha256']:
            raise ValueError('policy_changed_during_full_authority_acquisition')
        result['payload'] = dict(authorities=authorities, prior_verified_specification=prior_verified_specification,
                                 canonical_policy_sha256=catalog['canonical_sha256'], **actual)
        if not result['missing_context']:
            result['route'] = 'full_authority'
    except (ValueError, KeyError, TypeError, OSError, UnicodeError, subprocess.SubprocessError, RecursionError):
        result['reasons'].append('full_authority_acquisition_failed')
        result['missing_context'].append('full_authority_originals')
    return result
