"""Independent, provenance-bound real-derived semantic shadow cohort.

Provider payloads contain four safe text fields only. Oracles stay in fixtures;
results contain numeric/allowlisted metadata, never provider transcripts.
"""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import uuid

from .semantic_regression import CHOICES, SEVERITIES, valid_answer
from .telemetry import usage_numbers
from .triage import SENSITIVE

SOL_MODEL = 'gpt-6.1-sol'
SOL_EFFORT = 'high'
HISTORICAL_SOL_EFFORT = 'xhigh'
RECORDED_SOL_EFFORTS = {SOL_EFFORT, HISTORICAL_SOL_EFFORT}
COHORT = 'semantic_real_derived'
ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'tests/fixtures/workflow_semantic_real_provenance.json'
FIELDS = {'id', 'source_pr', 'source_commit', 'semantic_contract', 'severity',
          'expected_result', 'original_evidence', 'mutated_evidence', 'rationale',
          'provenance', 'deterministic_ground_truth', 'mutation'}
LEAKAGE = re.compile(r'(?i)(expected[_ ]?(?:result|label)|severity\s*[:=]|'
                     r'(?:this|candidate|answer)\s+is\s+(?:a\s+)?(?:regression|no.regression)|'
                     r'final\s+review\s+(?:verdict|judgment)|\b(?:critical|important|minor)\b)')


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def provider_payload(case):
    payload = dict(requirement=case['semantic_contract'], baseline=case['original_evidence'],
                   candidate=case['mutated_evidence'], evidence=case['deterministic_ground_truth']['facts'])
    for value in payload.values():
        if (not isinstance(value, str) or not value or len(value) > 3000 or
                SENSITIVE.search(value) or LEAKAGE.search(value) or
                re.search(r'[A-Za-z0-9+/=_-]{80,}', value)):
            raise ValueError('unsafe_or_leaking_payload')
    return payload


def validate_cases(cases, root=ROOT, *, require_source_objects=False):
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if not isinstance(cases, list) or not cases:
        raise ValueError('invalid_real_cases')
    seen, source_hashes = set(), {}
    for case in cases:
        if not isinstance(case, dict) or set(case) != FIELDS:
            raise ValueError('invalid_real_case_fields')
        identity = case['id']
        if not isinstance(identity, str) or not re.fullmatch(r'ER[0-9]{3}', identity) or identity in seen:
            raise ValueError('duplicate_or_invalid_case_id')
        seen.add(identity)
        if (case['source_pr'] not in (11, 12, 17, 18) or
                manifest['source_heads'].get(str(case['source_pr'])) != case['source_commit'] or
                case['severity'] not in SEVERITIES or
                case['expected_result'] not in ('regression', 'no_regression')):
            raise ValueError('invalid_source_or_oracle')
        truth, provenance = case['deterministic_ground_truth'], case['provenance']
        if (not isinstance(truth, dict) or set(truth) != {'kind', 'anchor', 'facts'} or
                truth['kind'] not in ('test', 'specification', 'confirmed_review', 'diff') or
                not isinstance(provenance, dict) or set(provenance) != {'path', 'source_sha256', 'url', 'additional_evidence'}):
            raise ValueError('missing_ground_truth_or_provenance')
        path = provenance['path']
        if not isinstance(path, str) or '..' in Path(path).parts or Path(path).is_absolute():
            raise ValueError('unsafe_source_path')
        key = (case['source_commit'], path)
        if key not in source_hashes:
            try:
                raw = subprocess.check_output(['git', 'show', key[0] + ':' + path], cwd=root,
                                              stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError as exc:
                # Unmerged source PRs need not exist in an offline CI checkout.
                # Use the frozen author-verified manifest, never a network fetch.
                if require_source_objects:
                    raise ValueError('source_object_unavailable') from exc
                proof = manifest['source_artifacts'].get(key[0] + ':' + path)
                if not proof:
                    raise ValueError('source_object_unavailable') from exc
                source_hashes[key] = (proof['sha256'], '\n'.join(proof['anchors']))
                raw = None
            if raw is not None:
                source_hashes[key] = (hashlib.sha256(raw).hexdigest(), raw.decode('utf-8'))
        source_sha, source = source_hashes[key]
        if (source_sha != provenance['source_sha256'] or
                not isinstance(truth['anchor'], str) or not truth['anchor'] or truth['anchor'] not in source or
                provenance['url'] != 'https://github.com/27c7nmt5m8-coder/EA/blob/' + key[0] + '/' + path):
            raise ValueError('stale_fixture_provenance')
        if SENSITIVE.search(json.dumps(case, ensure_ascii=False)):
            raise ValueError('unsafe_fixture')
        provider_payload(case)
        if manifest['case_fingerprints'].get(identity) != fingerprint(case):
            raise ValueError('changed_fixed_oracle')
    return cases


def load_cases(path, root=ROOT, *, require_source_objects=False):
    raw = Path(path).read_bytes()
    dataset = json.loads(raw)
    if (not isinstance(dataset, dict) or set(dataset) != {'version', 'cohort', 'cases'} or
            dataset['version'] != 1 or dataset['cohort'] != COHORT):
        raise ValueError('synthetic_or_unknown_cohort')
    cases = validate_cases(dataset['cases'], root, require_source_objects=require_source_objects)
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if set(manifest['case_fingerprints']) != {c['id'] for c in cases}:
        raise ValueError('incomplete_fixed_cohort')
    return cases, hashlib.sha256(raw).hexdigest()


def normalize(value, arm, *, expected_effort=SOL_EFFORT):
    from .triage import policy
    result = dict(status='UNAVAILABLE', choice=None, confidence=None, usage=None,
                  usage_reason='missing_usage', elapsed_seconds=None, reason='invalid_response',
                  model=None, reasoning_effort=None)
    if not isinstance(value, dict): return result
    try:
        result.update(usage=usage_numbers(value.get('usage')), usage_reason=None)
    except (TypeError, ValueError): pass
    duration = value.get('elapsed_seconds')
    if type(duration) in (int, float) and math.isfinite(duration) and duration >= 0:
        result['elapsed_seconds'] = duration
    model, effort = value.get('model'), value.get('reasoning_effort')
    if arm == 'sol' and expected_effort not in RECORDED_SOL_EFFORTS:
        raise ValueError('unsupported_sol_effort_provenance')
    valid_model = (model == SOL_MODEL and effort == expected_effort if arm == 'sol'
                   else model == policy()['jev_model'])
    if valid_model:
        result.update(model=model, reasoning_effort=effort if arm == 'sol' else None)
    if value.get('status') != 'OK':
        reasons = {'timeout', 'missing_credentials', 'nonzero_exit', 'network_unavailable',
                   'invalid_response', 'not_run', 'model_unavailable'}
        result['reason'] = value.get('reason') if value.get('reason') in reasons else 'invalid_response'
        return result
    if not valid_model:
        result['reason'] = 'model_effort_mismatch'
        return result
    answer = value.get('answer')
    if not valid_answer(answer): return result
    result.update(status='OK', choice=answer['choice'], confidence=answer['confidence'], reason=None)
    return result


def run_case(case, *, base_sha, dataset_sha256, sol_evaluator=None, jev_evaluator=None):
    if not re.fullmatch(r'[0-9a-f]{40}', base_sha) or not re.fullmatch(r'[0-9a-f]{64}', dataset_sha256):
        raise ValueError('invalid_identity')
    payload = provider_payload(case)
    def observe(evaluator, arm):
        try:
            value = evaluator(dict(payload)) if evaluator else dict(status='UNAVAILABLE', reason='not_run')
        except (TimeoutError, subprocess.TimeoutExpired):
            value = dict(status='UNAVAILABLE', reason='timeout')
        except (ValueError, OSError, TypeError, KeyError):
            value = dict(status='UNAVAILABLE', reason='invalid_response')
        return normalize(value, arm)
    return dict(experiment=COHORT, id=case['id'], attempt_id=uuid.uuid4().hex, base_sha=base_sha,
                dataset_sha256=dataset_sha256, case_fingerprint=fingerprint(case),
                payload_sha256=fingerprint(payload), a=observe(sol_evaluator, 'sol'),
                b=observe(jev_evaluator, 'jev'), shadow_only=True, actual_action='none')


def ratio(numerator, denominator):
    return dict(value=numerator / denominator if denominator else None,
                numerator=numerator, denominator=denominator)


def summarize(rows, cases, *, base_sha, dataset_sha256):
    validate_cases(cases)
    expected = {c['id']: c for c in cases}
    groups, stale, duplicates, legacy = {}, 0, 0, 0
    identities = {}
    for row in rows:
        if not isinstance(row, dict) or row.get('experiment') != COHORT or row.get('id') not in expected:
            raise ValueError('mixed_or_unknown_cohort')
        if set(row) - {'attempt_id'} != {'experiment', 'id', 'base_sha', 'dataset_sha256', 'case_fingerprint',
                       'payload_sha256', 'a', 'b', 'shadow_only', 'actual_action'}:
            raise ValueError('unsafe_result_fields')
        for arm in ('a', 'b'):
            observation = row[arm]
            if not isinstance(observation, dict) or set(observation) != {
                    'status', 'choice', 'confidence', 'usage', 'usage_reason', 'elapsed_seconds',
                    'reason', 'model', 'reasoning_effort'}:
                raise ValueError('unsafe_observation_fields')
            if observation.get('usage') is not None and (not isinstance(observation['usage'], dict) or
                    set(observation['usage']) - {'input_tokens', 'output_tokens', 'total_tokens',
                    'cached_input_tokens', 'cache_write_input_tokens', 'reasoning_output_tokens'}):
                raise ValueError('unsafe_usage_fields')
        case = expected[row['id']]
        if (row.get('base_sha') != base_sha or row.get('dataset_sha256') != dataset_sha256 or
                row.get('case_fingerprint') != fingerprint(case) or
                row.get('payload_sha256') != fingerprint(provider_payload(case))):
            stale += 1
            continue
        if 'attempt_id' in row:
            if not isinstance(row['attempt_id'], str) or not re.fullmatch(r'[0-9a-f]{32}', row['attempt_id']):
                raise ValueError('invalid_attempt_identity')
            identity = ('attempt', row['attempt_id'])
        else:
            # Frozen v1 live observations remain immutable. A complete-row
            # fingerprint detects exact copied observations without relabeling.
            identity = ('legacy', fingerprint(row))
        row_hash = fingerprint(row)
        if identity in identities:
            if identities[identity] != row_hash:
                raise ValueError('conflicting_attempt_identity')
            duplicates += 1
            continue
        identities[identity] = row_hash
        legacy += identity[0] == 'legacy'
        groups.setdefault(row['id'], []).append(row)
    first = {identity: group[0] for identity, group in groups.items()}
    attempts = [r for group in groups.values() for r in group]
    sol_efforts = {r.get('a', {}).get('reasoning_effort') for r in attempts
                   if r.get('a', {}).get('model') == SOL_MODEL
                   and r.get('a', {}).get('reasoning_effort') in RECORDED_SOL_EFFORTS}
    if len(sol_efforts) > 1:
        raise ValueError('mixed_sol_effort_provenance')
    report_sol_effort = next(iter(sol_efforts), None)
    def accepted(row, arm):
        from .triage import policy
        observation = row.get(arm, {})
        model_ok = (observation.get('model') == SOL_MODEL and observation.get('reasoning_effort') == report_sol_effort
                    if arm == 'a' else observation.get('model') == policy()['jev_model'])
        confidence = observation.get('confidence')
        return (observation.get('status') == 'OK' and model_ok and observation.get('choice') in CHOICES
                and type(confidence) in (int, float) and math.isfinite(confidence) and 0 <= confidence <= 1)
    def prediction(row, arm):
        return row[arm]['choice'] if accepted(row, arm) else None
    def quality(arm):
        counts = dict(TP=0, TN=0, FP=0, FN=0)
        unknown = unmeasured = 0
        confidence, low = [], 0
        for identity, case in expected.items():
            row = first.get(identity)
            choice = prediction(row, arm) if row else None
            if choice is None:
                unmeasured += 1; continue
            confidence.append(row[arm]['confidence'])
            low += row[arm]['confidence'] < .90
            if choice == 'unknown': unknown += 1; continue
            positive = case['expected_result'] == 'regression'
            counts['TP' if positive and choice == 'regression' else 'FN' if positive else
                   'FP' if choice == 'regression' else 'TN'] += 1
        tp, tn, fp, fn = (counts[k] for k in ('TP', 'TN', 'FP', 'FN'))
        scored = tp + tn + fp + fn
        return dict(**{k: v if scored else None for k, v in counts.items()}, scored=scored,
                    sensitivity=ratio(tp, tp+fn), specificity=ratio(tn, tn+fp),
                    precision=ratio(tp, tp+fp), accuracy=ratio(tp+tn, scored),
                    unknown=unknown, unmeasured=unmeasured, expected=len(cases),
                    confidence=dict(mean=sum(confidence)/len(confidence) if confidence else None,
                                    observed=len(confidence), below_090=low),
                    reason=None if scored == len(cases) else 'partial_quality_coverage')
    def misses(severity):
        eligible = [c for c in cases if c['severity'] == severity and c['expected_result'] == 'regression']
        observed, missing = 0, []
        for case in eligible:
            predictions = [prediction(r, 'b') for r in groups.get(case['id'], [])]
            observed += any(p is not None for p in predictions)
            if any(p in ('no_regression', 'unknown') for p in predictions): missing.append(case['id'])
        return dict(count=len(missing), case_ids=missing, audited=observed, expected=len(eligible),
                    reason=None if observed == len(eligible) else 'incomplete_safety_coverage')
    def tokens(arm):
        measured = []
        for row in attempts:
            try: measured.append(usage_numbers(row.get(arm, {}).get('usage')))
            except (TypeError, ValueError): pass
        complete = len(first) == len(cases) and len(measured) == len(attempts) and bool(attempts)
        return dict(**{k: sum(v[k] for v in measured) if complete else None
                       for k in ('input_tokens', 'output_tokens', 'total_tokens')},
                    observed_total_tokens=sum(v['total_tokens'] for v in measured) if measured else None,
                    usage_attempts=len(measured), attempts=len(attempts), expected_cases=len(cases),
                    reason=None if complete else 'missing_usage_or_case_results')
    def duration(arm):
        values = [r.get(arm, {}).get('elapsed_seconds') for r in attempts]
        valid = [v for v in values if type(v) in (int, float) and math.isfinite(v) and v >= 0]
        complete = bool(attempts) and len(first) == len(cases) and len(valid) == len(values)
        return dict(seconds=sum(valid) if complete else None,
                    observed_seconds=sum(valid) if valid else None, observed=len(valid), attempts=len(attempts),
                    reason=None if complete else 'missing_duration_or_case_results')
    comparable = [r for r in first.values() if accepted(r, 'a') and accepted(r, 'b')
                  and prediction(r, 'a') != 'unknown' and prediction(r, 'b') != 'unknown']
    a, b = tokens('a'), tokens('b')
    critical, important = misses('critical'), misses('important')
    complete = len(comparable) == len(cases)
    return dict(experiment=COHORT, base_sha=base_sha, dataset_sha256=dataset_sha256,
                verdict='BLOCKED_CRITICAL_MISS' if critical['count'] else 'SHADOW_ONLY' if complete else 'UNMEASURED',
                shadow_only=True, actual_action='none', review_skip_enabled=False, confidence_threshold=.90,
                real_task_cohort_included=False, expected_cases=len(cases), unique_observed_cases=len(first),
                retry_rows=len(attempts)-len(first), stale_rows=stale, duplicate_rows=duplicates,
                legacy_identity_rows=legacy, sol_effort_provenance=report_sol_effort,
                case_counts=dict(source_pr=dict(Counter(str(c['source_pr']) for c in cases)),
                                 severity=dict(Counter(c['severity'] for c in cases)),
                                 expected_result=dict(Counter(c['expected_result'] for c in cases))),
                quality=dict(sol=quality('a'), jev=quality('b')), critical_miss=critical, important_miss=important,
                agreement=dict(agree=sum(r['a']['choice'] == r['b']['choice'] for r in comparable),
                               compared=len(comparable), expected=len(cases)),
                tokens=dict(sol=a, jev=b, combined=a['total_tokens']+b['total_tokens']
                            if a['total_tokens'] is not None and b['total_tokens'] is not None else None,
                            accounting='all_current_attempts_including_retries_no_cross_arm_duplication'),
                cost=dict(value=None, reason='verified_current_model_and_provider_prices_unavailable'),
                time=dict(sol=duration('a'), jev=duration('b')),
                context_retrieval=dict(value=None, reason='fixed_context_classification_not_observed'),
                rework_test_failure=dict(rework=None, test_failure=None, reason='no_development_tasks_executed'),
                coverage=dict(missing_case_ids=sorted(set(expected)-set(first)),
                              unavailable=dict(Counter(r[arm]['reason'] if r[arm]['reason'] in {
                                  'timeout', 'missing_credentials', 'nonzero_exit', 'network_unavailable',
                                  'invalid_response', 'not_run', 'model_unavailable', 'model_effort_mismatch'}
                                  else 'invalid_response' for r in first.values()
                                  for arm in ('a', 'b') if not accepted(r, arm))),
                              quality_policy='first_attempt_per_case_unknown_separate_from_binary_confusion_matrix',
                              safety_policy='any_current_attempt_miss_retained'),
                limitations=['real_pr_derived_condensed_mutations_not_real_task_cohort',
                             'legacy_attempt_identity_uses_complete_row_hash_exact_copy_dedup_only',
                             'oracle_fixed_by_primary_evidence_then_independently_reviewed_not_new_human_labeling',
                             'no_ea_quality_guarantee', 'pilot_does_not_authorize_adoption'])


from .semantic_real_adapters import call_jev, call_sol  # dedicated live adapters; shared schema above
