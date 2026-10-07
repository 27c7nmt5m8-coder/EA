"""Verification-only body deduplication over acquired Phase 1 artifacts.

Aliases preserve all caller-supplied source identity and current evidence. IDs
identify complete manifests, not PASS claims. Original bodies are sent once per
exact byte sequence within this delivery; no cross-recipient cache is assumed.
Trusted runner acquisition and actual current identity remain caller contracts.
"""
import copy
import hashlib
import re

from .context import _path_name, _safe_evidence
from .serialization import canonical_hash, canonical_json
from .verification_context import _read, verification_transport


FLAGS = ('reviewer_request', 'xhigh', 'blocked_judgment', 'unexplained')
SOURCE_FIELDS = {'source_identity', 'manifest', 'current'}
DELIVERY_FIELDS = {'schema_version', 'mode', 'verified_pass', 'expansion_requests',
                   'verifications', 'bodies', 'aliases', 'sha256'}
CHECK_FIELDS = {'verification_id', 'manifest', 'route', 'verified_pass', 'reasons', 'original_refs'}


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def _source(source):
    _safe_evidence(source)
    canonical_json(source)
    if (not isinstance(source, dict) or set(source) != SOURCE_FIELDS or
            not isinstance(source['source_identity'], dict) or not source['source_identity']):
        raise ValueError('invalid_verification_source')


def _flags(**options):
    if set(options) != set(FLAGS) or any(type(value) is not bool for value in options.values()):
        raise ValueError('invalid_verification_expansion')
    return options


def _body(text):
    _safe_evidence(text)
    raw = text.encode('utf-8')
    sha = hashlib.sha256(raw).hexdigest()
    return dict(body_id='body:' + sha, sha256=sha, size_bytes=len(raw), text=text)


def build_verification_delivery(artifact_root, sources, *, reviewer_request=False, xhigh=False,
                                blocked_judgment=False, unexplained=False):
    """Acquire every source, keeping one manifest and one body per exact identity.

    ``sources`` entries are ``{source_identity, manifest, current}``; identity is
    a nonempty JSON provenance object, preserved without projection. The same
    manifest at different surfaces shares a verification ID. Different artifact
    paths retain distinct manifests/IDs, while identical original bytes may
    share body references. All source occurrences and current identities remain.
    Missing originals block. Available artifact or record mismatches reject.
    """
    if not isinstance(sources, list) or not sources:
        raise ValueError('verification_sources_required')
    options = _flags(reviewer_request=reviewer_request, xhigh=xhigh,
                     blocked_judgment=blocked_judgment, unexplained=unexplained)
    checks, bodies, aliases = {}, {}, []
    for source in sources:
        _source(source)
        manifest = source['manifest']
        acquired = verification_transport(artifact_root, manifest, current=source['current'], **options)
        # Inspect originals again, including successful manifest-only checks.
        # An unavailable original cannot be hidden by a previously acquired PASS.
        missing, record_available, snapshots = [], False, []
        for index, artifact in enumerate(manifest['artifacts']):
            raw, text, problem = _read(artifact_root, artifact['path'])
            sha = artifact['sha256']
            size = artifact['size_bytes']
            if ((sha is not None and not _digest(sha)) or
                    (size is not None and (type(size) is not int or size < 0))):
                raise ValueError('verification_evidence_mismatch')
            if index == 0:
                record_available = text is not None
            if raw is not None and (hashlib.sha256(raw).hexdigest() != sha or len(raw) != size):
                raise ValueError('verification_evidence_mismatch')
            if problem:
                missing.append(problem)
            if text is not None:
                snapshots.append(dict(path=artifact['path'], text=text))
        if record_available and 'record_manifest_mismatch' in acquired['reasons']:
            raise ValueError('verification_evidence_mismatch')
        if missing:
            acquired['route'] = 'blocked'
            acquired['verified_pass'] = False
            acquired['reasons'] = list(dict.fromkeys([*acquired['reasons'], *missing]))
            for snapshot in snapshots:
                if not any(original['path'] == snapshot['path'] for original in acquired['originals']):
                    acquired['originals'].append(snapshot)
        verification_id = 'verification:' + canonical_hash(manifest)
        entry = checks.get(verification_id)
        if entry is None:
            entry = dict(verification_id=verification_id, manifest=copy.deepcopy(manifest),
                         route=acquired['route'], verified_pass=acquired['verified_pass'],
                         reasons=[], original_refs=[])
            checks[verification_id] = entry
        elif canonical_json(entry['manifest']) != canonical_json(manifest):
            raise ValueError('verification_identity_collision')
        rank = {'manifest': 0, 'original': 1, 'blocked': 2}
        entry['route'] = max((entry['route'], acquired['route']), key=rank.__getitem__)
        entry['verified_pass'] = entry['verified_pass'] and acquired['verified_pass']
        entry['reasons'] = sorted(set(entry['reasons']) | set(acquired['reasons']))
        roles = {artifact['path']: artifact['role'] for artifact in manifest['artifacts']}
        for original in acquired['originals']:
            body = _body(original['text'])
            previous = bodies.get(body['body_id'])
            if previous is not None and canonical_json(previous) != canonical_json(body):
                raise ValueError('verification_body_collision')
            bodies[body['body_id']] = body
            ref = dict(path=original['path'], role=roles.get(original['path'], 'log'), body_id=body['body_id'])
            if ref not in entry['original_refs']:
                entry['original_refs'].append(ref)
        aliases.append(dict(source_identity=copy.deepcopy(source['source_identity']),
                            current=copy.deepcopy(source['current']), verification_id=verification_id))
    verification_list = [checks[key] for key in sorted(checks)]
    mode = max((entry['route'] for entry in verification_list), key={'manifest': 0, 'original': 1, 'blocked': 2}.__getitem__)
    result = dict(schema_version=1, mode=mode,
                  verified_pass=all(entry['verified_pass'] for entry in verification_list),
                  expansion_requests=options, verifications=verification_list,
                  bodies=[bodies[key] for key in sorted(bodies)], aliases=aliases)
    _safe_evidence(result)
    result['sha256'] = canonical_hash(result)
    return result


def _delivery_sources(delivery):
    """Validate payload integrity before resolving any alias or body reference."""
    _safe_evidence(delivery)
    canonical_json(delivery)
    if (not isinstance(delivery, dict) or set(delivery) != DELIVERY_FIELDS or
            type(delivery['schema_version']) is not int or delivery['schema_version'] != 1 or
            not _digest(delivery['sha256']) or delivery['sha256'] != canonical_hash(
                {key: value for key, value in delivery.items() if key != 'sha256'}) or
            delivery['mode'] not in ('manifest', 'original', 'blocked') or
            type(delivery['verified_pass']) is not bool):
        raise ValueError('invalid_verification_delivery')
    options = delivery['expansion_requests']
    if not isinstance(options, dict):
        raise ValueError('invalid_verification_delivery')
    _flags(**options)
    if (not isinstance(delivery['bodies'], list) or not isinstance(delivery['verifications'], list) or
            not delivery['verifications'] or not isinstance(delivery['aliases'], list) or not delivery['aliases']):
        raise ValueError('invalid_verification_delivery')
    body_map = {}
    for body in delivery['bodies']:
        if (not isinstance(body, dict) or set(body) != {'body_id', 'sha256', 'size_bytes', 'text'} or
                not isinstance(body['text'], str) or canonical_json(body) != canonical_json(_body(body['text'])) or
                body['body_id'] in body_map):
            raise ValueError('invalid_verification_body')
        body_map[body['body_id']] = body
    check_map = {}
    referenced = set()
    for check in delivery['verifications']:
        if (not isinstance(check, dict) or set(check) != CHECK_FIELDS or
                check['verification_id'] != 'verification:' + canonical_hash(check['manifest']) or
                check['verification_id'] in check_map or check['route'] not in ('manifest', 'original', 'blocked') or
                type(check['verified_pass']) is not bool or not isinstance(check['reasons'], list) or
                not all(isinstance(reason, str) for reason in check['reasons']) or
                not isinstance(check['original_refs'], list)):
            raise ValueError('invalid_verification_reference')
        refs = set()
        for ref in check['original_refs']:
            if (not isinstance(ref, dict) or set(ref) != {'path', 'role', 'body_id'} or
                    not _path_name(ref['path']) or ref['role'] not in ('record', 'log') or
                    not isinstance(ref['body_id'], str) or ref['body_id'] not in body_map):
                raise ValueError('invalid_verification_reference')
            identity = canonical_json(ref)
            if identity in refs:
                raise ValueError('duplicate_verification_reference')
            refs.add(identity)
            referenced.add(ref['body_id'])
        check_map[check['verification_id']] = check
    if referenced != set(body_map):
        raise ValueError('unreferenced_verification_body')
    sources, used = [], set()
    for alias in delivery['aliases']:
        if (not isinstance(alias, dict) or set(alias) != {'source_identity', 'current', 'verification_id'} or
                not isinstance(alias['verification_id'], str) or alias['verification_id'] not in check_map):
            raise ValueError('invalid_verification_alias')
        source = dict(source_identity=alias['source_identity'], current=alias['current'],
                      manifest=check_map[alias['verification_id']]['manifest'])
        _source(source)
        sources.append(source)
        used.add(alias['verification_id'])
    if used != set(check_map):
        raise ValueError('unreferenced_verification_manifest')
    return sources


def validate_verification_delivery(artifact_root, delivery):
    """Verify structure/hash, then reacquire artifacts; never trust cached PASS.

    A newly unavailable original returns fresh BLOCKED evidence. Corruption or
    an available original mismatch rejects. The digest has no authority by itself.
    """
    sources = _delivery_sources(delivery)
    rebuilt = build_verification_delivery(artifact_root, sources, **delivery['expansion_requests'])
    if canonical_json(rebuilt) != canonical_json(delivery):
        unavailable = any(reason in ('artifact_unavailable', 'artifact_not_utf8')
                          for check in rebuilt['verifications'] for reason in check['reasons'])
        if rebuilt['mode'] == 'blocked' and unavailable:
            return rebuilt
        raise ValueError('verification_delivery_rebuild_mismatch')
    return rebuilt


def expand_verification_delivery(artifact_root, delivery, *, reviewer_request=False, xhigh=False,
                                 blocked_judgment=False, unexplained=False):
    """Revalidate existing delivery and acquire requested originals once each."""
    validated = validate_verification_delivery(artifact_root, delivery)
    options = _flags(reviewer_request=reviewer_request, xhigh=xhigh,
                     blocked_judgment=blocked_judgment, unexplained=unexplained)
    options = {name: options[name] or validated['expansion_requests'][name] for name in FLAGS}
    return build_verification_delivery(artifact_root, _delivery_sources(validated), **options)
