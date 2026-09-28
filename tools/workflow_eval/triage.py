"""Fail-closed development review routing; recommendations never execute actions."""
import json
import math
import os
from pathlib import Path
import re
import time
from urllib import request, error

CHOICES = {'candidate', 'review', 'unknown'}
SENSITIVE = re.compile(r'(?i)(password\s*[:=]|bearer\s+|-----BEGIN|[\w.+-]+@[\w.-]+|'
                       r'(?:sk-proj-|gh[pousr]_)[A-Za-z0-9_-]+|'
                       r'(?:api[_ -]?key|secret|credential|access[_ -]?token|token)[\"\x27]?\s*[:=]\s*[\"\x27]?[A-Za-z0-9_-]{6,}|'
                       r'account[_ -]?(?:id|number|balance)\s*[:=])')
PROTECTED = re.compile(r'(?i)((?-i:\bBE\b)|\b(?:SL|TP|break.?even|stop.?loss|take.?profit|trailing|lot|risk|margin|order|position|'
                       r'entry|exit|balance|equity|drawdown|monte.?carlo|fintokei|'
                       r'fail.?open|mutex|worker|backtest|win.?rate|expectancy|safety|spread|'
                       r'duplicate.?prevention|forced.?stop|prop.?firm|daily.?loss|max(?:imum)?.?DD)\b|'
                       r'売買|資金管理|注文|安全|損失|証拠金|取引0|利確|損切|決済|口座|期待値|勝率|最大DD|プロップファーム|重複防止|スプレッド)')

FACT_FIELDS = {'dependency', 'module_count', 'tests', 'paths', 'changed_lines',
               'missing_context', 'sensitive', 'scope_ok', 'current', 'protected'}


def validate_facts(facts):
    if not isinstance(facts, dict) or set(facts) != FACT_FIELDS:
        raise ValueError('invalid_facts_schema')
    for field in ('paths', 'missing_context'):
        if not isinstance(facts[field], list) or any(not isinstance(x, str) for x in facts[field]):
            raise ValueError('invalid_facts_schema')
    if facts['dependency'] not in ('known', 'unknown') or facts['tests'] not in ('PASS', 'FAIL', 'BLOCKED', 'UNKNOWN'):
        raise ValueError('invalid_facts_schema')
    for field in ('module_count', 'changed_lines'):
        if type(facts[field]) is not int or facts[field] < 0:
            raise ValueError('invalid_facts_schema')
    for field in ('sensitive', 'scope_ok', 'current', 'protected'):
        if type(facts[field]) is not bool:
            raise ValueError('invalid_facts_schema')
    return facts


def policy():
    value = json.loads(Path(__file__).with_name('policy.json').read_text(encoding='utf-8'))
    if (value['mode'] not in ('off', 'shadow') or value['review_skip_enabled'] is not False
            or value['implementation_model'] != 'gpt-6-sol' or value['normal_effort'] != 'high'
            or value['mandatory_effort'] != 'xhigh'
            or not .90 <= value['confidence_threshold'] <= 1):
        raise ValueError('unsafe_policy')
    return value


def mandatory_reasons(facts):
    reasons = []
    for field in ('dependency', 'module_count', 'tests', 'paths', 'changed_lines',
                  'missing_context', 'sensitive', 'scope_ok', 'current', 'protected'):
        if field not in facts:
            reasons.append('missing_' + field)
    if facts.get('dependency') != 'known': reasons.append('unknown_dependency')
    if type(facts.get('module_count')) is not int or facts['module_count'] != 1: reasons.append('multiple_or_unknown_modules')
    if facts.get('tests') != 'PASS': reasons.append('tests_not_pass')
    paths = facts.get('paths')
    if (not isinstance(paths, list) or not paths or any(
            not isinstance(p, str) or not re.fullmatch(r'docs/dev-[A-Za-z0-9_-]+\.md', p)
            for p in paths)):
        reasons.append('outside_low_risk_allowlist')
    if type(facts.get('changed_lines')) is not int or not 0 <= facts['changed_lines'] <= policy()['max_changed_lines']:
        reasons.append('change_size_unknown_or_large')
    if facts.get('missing_context') != []: reasons.append('missing_context')
    for field, expected in [('sensitive', False), ('protected', False), ('scope_ok', True), ('current', True)]:
        if facts.get(field) is not expected: reasons.append(field)
    return reasons


def valid_answer(answer):
    if not isinstance(answer, dict) or answer.get('type') != 'choice' or answer.get('choice') not in CHOICES:
        return False
    confidence = answer.get('confidence')
    probs = answer.get('probabilities')
    if type(confidence) not in (float, int) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
        return False
    if not isinstance(probs, dict) or set(probs) != CHOICES:
        return False
    if any(type(p) not in (float, int) or not math.isfinite(p) or not 0 <= p <= 1 for p in probs.values()):
        return False
    return abs(sum(probs.values()) - 1) < .0001 and probs[answer['choice']] == max(probs.values())


def route(facts, answer=None):
    rules = policy()
    reasons = mandatory_reasons(facts)
    candidate = (not reasons and rules['mode'] == 'shadow' and valid_answer(answer)
                 and answer['confidence'] >= rules['confidence_threshold'] and answer['choice'] == 'candidate')
    return dict(actual_route='review', actual_review_skipped=False,
                shadow_route='candidate' if candidate else 'review',
                sol_model='gpt-6-sol', sol_effort='xhigh' if reasons else 'high',
                mandatory_reasons=reasons, confidence=answer['confidence'] if valid_answer(answer) else None,
                policy_version=rules['version'])


def safe_state(state):
    if not isinstance(state, dict) or set(state) != {'task', 'evidence'}:
        raise ValueError('state_not_allowlisted')
    for value in state.values():
        if not isinstance(value, str) or len(value) > 6000 or SENSITIVE.search(value) or PROTECTED.search(value):
            raise ValueError('unsafe_state')
        if re.search(r'[A-Za-z0-9+/=_-]{80,}', value):
            raise ValueError('opaque_state')
    return state


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise error.HTTPError(req.full_url, code, 'redirect_denied', headers, fp)


def call_jev(state, key=None, opener=None):
    start = time.perf_counter()
    base = dict(status='UNAVAILABLE', answer=None, usage=None, model=None, attempts=0)
    try:
        state = safe_state(state)
        key = key or os.environ.get('TYPESAFE_API_KEY')
        if not key:
            base['reason'] = 'missing_credentials'
            return base
        body = dict(model=policy()['jev_model'], state=state, questions=dict(routing=dict(
            type='choice', instructions='Assess only this developer documentation requirement against the evidence. '
            'Should an additional Sol review be considered? No final safety or completion approval.',
            criteria=dict(candidate='Requirement is clearly met; optional duplicate review is a candidate for omission.',
                          review='Requirement is unmet, ambiguous, or needs semantic review.',
                          unknown='Evidence is insufficient.'))))
        req = request.Request('https://api.typesafe.ai/v1/systemone', data=json.dumps(body).encode('utf-8'),
                              headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
        base['attempts'] = 1
        opener = opener or request.build_opener(NoRedirect()).open
        with opener(req, timeout=policy()['api_timeout_seconds']) as response:
            raw = response.read(65537)
        if len(raw) > 65536:
            raise ValueError('large_response')
        result = json.loads(raw)
        from .telemetry import usage_numbers
        base['usage'] = usage_numbers(result['usage'])
        answer = result['answers']['routing']
        if not valid_answer(answer) or not re.fullmatch(r'jev-[A-Za-z0-9_.-]+', result['model']):
            raise ValueError('invalid_response')
        base.update(status='OK', answer={k: answer[k] for k in ('type', 'choice', 'confidence', 'probabilities')},
                    model=result['model'], reason=None)
    except error.HTTPError as exc:
        base['reason'] = 'http_' + str(exc.code)
    except (OSError, TimeoutError):
        base['reason'] = 'network_unavailable'
    except (ValueError, KeyError, TypeError):
        base['reason'] = 'unsafe_input_or_invalid_response'
    finally:
        base['elapsed_seconds'] = round(time.perf_counter() - start, 6)
    return base
