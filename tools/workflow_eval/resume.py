"""Recipient-bound followups; possession is an explicit trusted host assertion.

This module cannot inspect a model's memory. The caller must confirm delivery
and retained full content through its host before issuing a receipt. A caller's
hash handle, requested model, or matching agent name alone is not that evidence.
Invalid continuity returns a fresh full spawn request, never a partial followup.
"""
import re
import json

from .context import (git, digest, _validate_packet, build_bundle,
                      build_context_packet, expand_context_packet, _safe_evidence)
from .serialization import canonical_hash, canonical_json
from .spawn import build_spawn_request, ROLE_SCOPES


def repository_identity(root):
    # Hash local repository identity; neither credential-bearing remotes nor
    # local account/user path text goes into receipts or model payloads.
    common = git(root, 'rev-parse', '--path-format=absolute', '--git-common-dir').strip()
    return digest(common)


def _identifier(value):
    return isinstance(value, str) and bool(re.fullmatch(r'[A-Za-z0-9_./:-]{1,160}', value))


def retention_receipt(root, prior, *, recipient_id, continuity_id,
                      acknowledgement_id, role, model, reasoning_effort,
                      possession_confirmed):
    _validate_packet(prior)
    if (not all(_identifier(v) for v in (recipient_id, continuity_id, acknowledgement_id))
            or role not in ROLE_SCOPES or role == 'reviewer'
            or model != 'gpt-6.1-sol' or reasoning_effort not in ('medium', 'high')
            or possession_confirmed is not True or prior['reused_paths']):
        raise ValueError('confirmed_full_delivery_required')
    bundle = build_bundle(root, prior['base'],
                          [b['path'] for b in prior['blocks']], prior['task'])
    expand_context_packet(prior, bundle, root=root)
    if prior['dependency'] != 'known' or prior['protected'] or prior['expansion_required']:
        raise ValueError('retention_not_eligible')
    receipt = dict(schema_version=1, recipient_id=recipient_id,
        continuity_id=continuity_id, acknowledgement_id=acknowledgement_id,
        role=role, model=model, reasoning_effort=reasoning_effort,
        repository_identity=repository_identity(root), packet_hash=canonical_hash(prior),
        head=prior['head'], fingerprint=prior['fingerprint'],
        possession_confirmed=True,
        possessed_blocks={b['path']: b['sha256'] for b in prior['blocks']})
    _safe_evidence(receipt)
    return receipt


def build_resume_request(root, role, task_name, bundle, *, recipient_id,
                         continuity_id, prior, receipt, specification,
                         repository_rules, unresolved_questions, verification=None,
                         complex_work=False, context_expansion_requested=False):
    full = build_spawn_request(root, role, task_name, bundle,
        specification=specification, repository_rules=repository_rules,
        unresolved_questions=unresolved_questions, verification=verification,
        complex_work=complex_work)
    fallback = lambda reason: dict(route='full', request=full, fallback_reason=reason,
                                  reused_bytes=0)
    payload = json.loads(full['message'])
    if role == 'reviewer':
        return fallback('reviewer_requires_fresh_context')
    if (payload['protected_task'] or bundle['dependency'] != 'known'
            or bundle['expansion_required'] or unresolved_questions
            or context_expansion_requested is not False):
        return fallback('full_context_required')
    if verification is not None and (
            verification.get('stale') is not False
            or verification.get('commit') != bundle['head']):
        return fallback('verification_freshness_unproven')
    try:
        expected = retention_receipt(root, prior, recipient_id=recipient_id,
            continuity_id=continuity_id, acknowledgement_id=receipt['acknowledgement_id'],
            role=role, model=full['model'], reasoning_effort=full['reasoning_effort'],
            possession_confirmed=True)
        if canonical_json(receipt) != canonical_json(expected):
            return fallback('recipient_continuity_or_possession_mismatch')
        packet = build_context_packet(bundle, prior=prior, verification=verification,
                                      root=root, recipient_has_content=True)
    except (KeyError, TypeError, ValueError):
        return fallback('invalid_or_stale_retention_evidence')
    if not packet['reused_paths']:
        return fallback('no_exact_duplicate_content')
    # Reuse the full validated role/spec/rules/instructions without truncation;
    # only previously delivered unchanged source bodies become exact handles.
    payload.update(context_packet=packet, recipient_id=recipient_id,
                   continuity_id=continuity_id, context_mode='delta')
    reused_bytes = sum(len(b['text'].encode('utf-8')) for b in bundle['blocks']
                       if b['path'] in packet['reused_paths'])
    return dict(route='delta', request=dict(target=recipient_id,
        message=canonical_json(payload)), fallback_reason=None, reused_bytes=reused_bytes)
