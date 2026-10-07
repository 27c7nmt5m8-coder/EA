"""Small numeric extension to existing telemetry; never infer unavailable usage.

These measurements do not add cohort members. Prospective eligibility remains
the responsibility of the existing real_tasks/semantic_prospective validators.
"""
import math
import re

from .context import _safe_evidence
from .serialization import canonical_json
from .telemetry import USAGE_KEYS, usage_numbers

COUNTS = set(USAGE_KEYS) | {'changed_lines', 'context_bytes', 'reused_bytes',
    'resent_bytes', 'expanded_bytes', 'context_reacquisitions', 'missing_context_count',
    'review_attempts', 'review_findings', 'test_failed_runs', 'rework_count',
    'jev_usage', 'fallback_count', 'cache_reuse_count', 'delta_reuse_count'}
FIELDS = COUNTS | {'base_sha', 'head_sha', 'tree_sha', 'changed_paths', 'task_category',
    'protected', 'dependency', 'model', 'reasoning_effort', 'elapsed_seconds',
    'fallback_reasons', 'model_provenance'}


def measurement(task_id, repository, *, origin='baseline', **observed):
    if (not isinstance(task_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', task_id)
            or not isinstance(repository, str)
            or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository)
            or origin not in ('baseline', 'prospective', 'synthetic')
            or set(observed) - FIELDS):
        raise ValueError('invalid_measurement_identity_or_fields')
    row = {key: observed.get(key) for key in sorted(FIELDS)}
    for key in COUNTS:
        value = row[key]
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError('invalid_measurement_count')
    elapsed = row['elapsed_seconds']
    if elapsed is not None and (type(elapsed) not in (float, int)
                              or not math.isfinite(elapsed) or elapsed < 0):
        raise ValueError('invalid_measurement_elapsed')
    for key in ('base_sha', 'head_sha', 'tree_sha'):
        if row[key] is not None and not re.fullmatch(r'[0-9a-f]{40}', row[key]):
            raise ValueError('invalid_measurement_sha')
    if row['protected'] is not None and type(row['protected']) is not bool:
        raise ValueError('invalid_measurement_classification')
    if row['dependency'] not in (None, 'known', 'unknown'):
        raise ValueError('invalid_measurement_dependency')
    if row['model'] not in (None, 'gpt-6.1-sol') or row['reasoning_effort'] not in (None, 'medium', 'high', 'xhigh'):
        raise ValueError('invalid_measurement_model')
    for key in ('changed_paths', 'fallback_reasons'):
        if row[key] is not None and (not isinstance(row[key], list)
                or any(not isinstance(v, str) for v in row[key])):
            raise ValueError('invalid_measurement_list')
    for key in ('task_category', 'model_provenance'):
        if row[key] is not None and (not isinstance(row[key], str)
                or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', row[key])):
            raise ValueError('invalid_measurement_label')
    if row['model'] is not None and row['model_provenance'] not in ('host_metadata', 'provider_metadata'):
        raise ValueError('observed_model_provenance_required')
    if row['input_tokens'] is not None and row['output_tokens'] is not None:
        # Reuse existing consistency checks, but never fill unobserved totals.
        usage_numbers({k: row[k] for k in USAGE_KEYS if row[k] is not None})
    row.update(schema_version=1, task_id=task_id, repository=repository, origin=origin,
               cohort_eligible=False,
               missing_reasons={k: 'not_observed' for k, v in row.items() if v is None})
    _safe_evidence(row)
    canonical_json(row)
    return row
