"""Numeric-only extraction from Codex usage events; raw transcripts stay local."""
import json
import math
from pathlib import Path

USAGE_KEYS = ('input_tokens', 'cached_input_tokens', 'cache_write_input_tokens',
              'output_tokens', 'reasoning_output_tokens', 'total_tokens')


def usage_numbers(value):
    if not isinstance(value, dict):
        raise ValueError('invalid_usage')
    result = {k: value.get(k, 0) for k in USAGE_KEYS}
    for number in result.values():
        if type(number) is not int or number < 0:
            raise ValueError('invalid_usage')
    if 'input_tokens' not in value or 'output_tokens' not in value:
        raise ValueError('missing_usage')
    result['total_tokens'] = value.get('total_tokens', result['input_tokens'] + result['output_tokens'])
    if (result['total_tokens'] != result['input_tokens'] + result['output_tokens']
            or result['cached_input_tokens'] > result['input_tokens']
            or result['reasoning_output_tokens'] > result['output_tokens']):
        raise ValueError('inconsistent_usage')
    return result


def extract_usage(events):
    previous = None
    updates = duplicates = 0
    inherited = None
    invalid = False
    models = set()
    completed = started = 0
    for event in events:
        payload = event.get('payload', {})
        if event.get('type') == 'turn_context':
            models.add((payload.get('model'), payload.get('effort')))
        if event.get('type') != 'event_msg':
            continue
        kind = payload.get('type')
        started += kind == 'task_started'
        completed += kind == 'task_complete'
        info = payload.get('info')
        if kind != 'token_count' or not info:
            continue
        try:
            current = usage_numbers(info['total_token_usage'])
            if previous is None and info.get('last_token_usage'):
                inherited = current != usage_numbers(info['last_token_usage'])
            if current == previous:
                duplicates += 1
                continue
            if previous and any(current[k] < previous[k] for k in USAGE_KEYS):
                invalid = True
            previous = current
            updates += 1
        except (KeyError, TypeError, ValueError):
            invalid = True
    task_known = (not invalid and inherited is False and started == completed == 1
                  and len(models) == 1 and next(iter(models))[0] == 'gpt-6-sol'
                  and next(iter(models))[1] in ('high', 'xhigh'))
    return dict(status='OK' if task_known else 'UNKNOWN',
                usage=None if invalid else previous, task_usage=previous if task_known else None,
                usage_scope='single_turn' if task_known else 'session_cumulative',
                observed_usage_updates=updates, duplicate_events=duplicates,
                gpt6_call_count=None, inherited_context=inherited,
                completed_turns=completed, models=sorted(models, key=lambda pair: tuple(str(x) for x in pair)))


def capture(path):
    with Path(path).open(encoding='utf-8') as source:
        return extract_usage(json.loads(line) for line in source if line.strip())


def validate_event(event):
    allowed = {'task_id', 'pair_id', 'arm', 'phase', 'event', 'round', 'status',
               'failed_cases', 'elapsed_seconds', 'timestamp', 'model', 'reasoning_effort'}
    if not isinstance(event, dict) or set(event) - allowed:
        raise ValueError('invalid_event_fields')
    import re
    for key in ('task_id', 'pair_id'):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', event.get(key, '')):
            raise ValueError('invalid_event_id')
    if event.get('arm') not in ('A', 'B-context', 'B'):
        raise ValueError('invalid_arm')
    if event.get('phase') not in ('implementation', 'self_review', 'additional_review',
                                 'escalated_review', 'audit', 'test', 'rework', 'context', 'jev'):
        raise ValueError('invalid_phase')
    if event.get('event') not in ('start', 'end'):
        raise ValueError('invalid_event_kind')
    if event.get('status') not in (None, 'PASS', 'FAIL', 'BLOCKED', 'UNKNOWN'):
        raise ValueError('invalid_event_status')
    for key in ('round', 'failed_cases'):
        if key in event and (type(event[key]) is not int or event[key] < 0):
            raise ValueError('invalid_event_number')
    if 'elapsed_seconds' in event:
        value = event['elapsed_seconds']
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError('invalid_event_duration')
    if event.get('model') not in (None, 'gpt-6-sol') or event.get('reasoning_effort') not in (None, 'high', 'xhigh'):
        raise ValueError('model_floor')
    if 'timestamp' in event:
        from datetime import datetime
        try:
            if datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00')).tzinfo is None:
                raise ValueError()
        except (TypeError, ValueError):
            raise ValueError('invalid_timestamp') from None
    return event


def summarize_events(events):
    endings = {}
    for event in events:
        validate_event(event)
        if event['event'] != 'end':
            continue
        identity = tuple(event.get(k) for k in ('task_id', 'pair_id', 'arm', 'phase', 'round'))
        if identity in endings:
            raise ValueError('duplicate_phase_end')
        endings[identity] = event
    reviews = [e for e in endings.values() if e['phase'] in ('self_review', 'additional_review', 'escalated_review', 'audit')]
    tests = [e for e in endings.values() if e['phase'] == 'test']
    reworks = [e for e in endings.values() if e['phase'] == 'rework']
    return dict(review_count=len(reviews) if reviews else None,
                review_seconds=sum(e['elapsed_seconds'] for e in reviews) if reviews and all('elapsed_seconds' in e for e in reviews) else None,
                test_failed_runs=sum(e.get('status') == 'FAIL' for e in tests) if tests else None,
                test_failed_cases=sum(e['failed_cases'] for e in tests) if tests and all('failed_cases' in e for e in tests) else None,
                test_unknown_runs=sum(e.get('status') not in ('PASS', 'FAIL') for e in tests),
                rework_count=len(reworks) if reworks else None,
                scope='explicit_phase_end_events_only; absence does not prove no unrecorded work')
