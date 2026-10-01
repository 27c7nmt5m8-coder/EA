"""Offline text-token API equivalents; missing billing evidence stays unknown.

Observations describe one request, never cumulative session usage. ``model`` and
``effective_service_tier`` must come from the response, not requested settings.
Input includes disjoint uncached, cached and cache-write categories. Explicit
context_input_tokens records the full request input, including cached tokens.
These equivalents do not establish actual CLI, subscription or JEV billing.
"""
import json
import math
import re
from decimal import Decimal
from pathlib import Path

from .triage import SENSITIVE


RATES = json.loads(Path(__file__).with_name('pricing_rates.json').read_text(encoding='utf-8'))
COUNTS = ('input_tokens', 'output_tokens', 'cached_input_tokens', 'cache_write_input_tokens')
USAGE_FIELDS = frozenset((*COUNTS, 'total_tokens', 'reasoning_output_tokens'))
REQUEST_FIELDS = frozenset(('request_id', 'usage_scope', 'model', 'effective_service_tier',
                            'regional_processing', 'context_input_tokens', 'usage', 'processing_mode'))
STRING_FIELDS = ('request_id', 'usage_scope', 'model', 'effective_service_tier', 'processing_mode')
SECRET_PREFIXES = re.compile(r'(?i)(?:sk-|gh[pousr]_|github_pat_|hf_|AKIA|ASIA|AIza)')


def validate_pricing_requests(requests):
    """Validate optional metadata before persistence; never infer pricing evidence.

    Return the same list (or None). Reject raw content, nested provider payloads,
    unsafe strings and invalid types with fixed-code ValueErrors. Missing fields,
    null values and safe unknown labels may persist: request_cost leaves their
    price unknown. This validates metadata safety, not complete billing evidence.
    """
    if requests is None:
        return None
    if not isinstance(requests, list):
        raise ValueError('invalid_pricing_schema')
    for request in requests:
        if not isinstance(request, dict) or set(request) - REQUEST_FIELDS:
            raise ValueError('invalid_pricing_schema')
        for field in STRING_FIELDS:
            value = request.get(field)
            if value is None:
                continue
            if not isinstance(value, str):
                raise ValueError('invalid_pricing_schema')
            if SENSITIVE.search(value) or SECRET_PREFIXES.search(value):
                raise ValueError('sensitive_pricing_metadata')
            pattern = r'[A-Za-z0-9_-]{1,80}' if field == 'request_id' else r'[A-Za-z0-9_.-]{1,100}'
            if not re.fullmatch(pattern, value):
                raise ValueError('invalid_pricing_schema')
        if request.get('regional_processing') is not None and type(request['regional_processing']) is not bool:
            raise ValueError('invalid_pricing_schema')
        context = request.get('context_input_tokens')
        if context is not None and (type(context) is not int or context < 0):
            raise ValueError('invalid_pricing_schema')
        usage = request.get('usage')
        if usage is not None:
            if not isinstance(usage, dict) or set(usage) - USAGE_FIELDS:
                raise ValueError('invalid_pricing_schema')
            if any(value is not None and (type(value) is not int or value < 0) for value in usage.values()):
                raise ValueError('invalid_pricing_schema')
    return requests


def _unknown(reason):
    return dict(amount_usd=None, reason=reason)


def _money(value):
    """Keep output JSON numeric and finite even for malformed huge counters."""
    result = float(value)
    return result if math.isfinite(result) else None


def _usage(value):
    if (not isinstance(value, dict) or set(value) - USAGE_FIELDS
            or not all(key in value for key in COUNTS)):
        return None
    keys = COUNTS + tuple(key for key in ('total_tokens', 'reasoning_output_tokens') if key in value)
    if any(type(value[key]) is not int or value[key] < 0 for key in keys):
        return None
    if (value['cached_input_tokens'] + value['cache_write_input_tokens'] > value['input_tokens']
            or value.get('total_tokens', value['input_tokens'] + value['output_tokens'])
            != value['input_tokens'] + value['output_tokens']
            or value.get('reasoning_output_tokens', 0) > value['output_tokens']):
        return None
    return {key: value[key] for key in COUNTS}


def request_cost(observation):
    """Return a nullable USD equivalent using explicit per-request evidence."""
    try:
        validate_pricing_requests([observation])
    except ValueError:
        return _unknown('invalid_or_unsafe_request_metadata')
    if not isinstance(observation, dict) or observation.get('usage_scope') != 'request':
        return _unknown('missing_request_usage_scope')
    model = observation.get('model')
    if not isinstance(model, str) or model not in RATES['models']:
        return _unknown('unknown_model')
    tier = observation.get('effective_service_tier')
    if not isinstance(tier, str) or tier not in RATES['effective_tier_multipliers']:
        return _unknown('unknown_effective_service_tier')
    if tier == 'batch' and observation.get('processing_mode') != 'batch':
        return _unknown('missing_batch_processing_evidence')
    regional = observation.get('regional_processing')
    if type(regional) is not bool:
        return _unknown('unknown_regional_processing')
    usage = _usage(observation.get('usage'))
    if usage is None:
        return _unknown('invalid_or_missing_usage')
    context = observation.get('context_input_tokens')
    if type(context) is not int or context != usage['input_tokens']:
        return _unknown('missing_or_inconsistent_request_context')
    rates = RATES['models'][model]
    long = context > RATES['long_context']['threshold_input_tokens']
    input_multiplier = Decimal(str(RATES['long_context']['input_multiplier'] if long else 1))
    output_multiplier = Decimal(str(RATES['long_context']['output_multiplier'] if long else 1))
    uncached = usage['input_tokens'] - usage['cached_input_tokens'] - usage['cache_write_input_tokens']
    input_cost = sum(Decimal(tokens) * Decimal(str(rates[name])) for tokens, name in (
        (uncached, 'input'), (usage['cached_input_tokens'], 'cached_input'),
        (usage['cache_write_input_tokens'], 'cache_write_input')))
    cost = input_cost * input_multiplier + Decimal(usage['output_tokens']) * Decimal(str(rates['output'])) * output_multiplier
    cost *= Decimal(str(RATES['effective_tier_multipliers'][tier]))
    if regional:
        cost *= Decimal(str(RATES['regional_multiplier']))
    amount = _money(cost / Decimal(RATES['unit_tokens']))
    if amount is None:
        return _unknown('cost_out_of_range')
    return dict(amount_usd=amount, reason=None,
                pricing_basis=rates['basis'], rates_as_of=RATES['as_of'], long_context=long)


def ledger_cost(requests, expected_model, expected_usage):
    """Price complete reconciled requests; a known subset never becomes a total."""
    if not isinstance(requests, list):
        return _unknown('missing_request_ledger')
    expected = _usage(expected_usage)
    amounts = []
    totals = dict.fromkeys(COUNTS, 0)
    seen = set()
    reason = None
    for request in requests:
        if not isinstance(request, dict):
            reason = reason or 'invalid_request_ledger'
            continue
        identifier = request.get('request_id')
        if (not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', identifier)
                or identifier in seen):
            reason = reason or 'missing_or_duplicate_request_id'
            continue
        seen.add(identifier)
        if request.get('model') != expected_model:
            reason = reason or 'mixed_or_unexpected_model'
            continue
        priced = request_cost(request)
        usage = _usage(request.get('usage'))
        if priced['amount_usd'] is None:
            reason = reason or priced['reason']
            continue
        amounts.append(Decimal(str(priced['amount_usd'])))
        for key in COUNTS:
            totals[key] += usage[key]
    if expected is None:
        reason = reason or 'invalid_or_missing_expected_usage'
    elif totals != expected:
        reason = reason or 'ledger_usage_mismatch'
    if not requests:
        reason = reason or 'empty_request_ledger'
    subtotal = _money(sum(amounts, Decimal(0)))
    if subtotal is None:
        reason = reason or 'cost_out_of_range'
    return dict(amount_usd=None if reason else subtotal, reason=reason,
                known_request_subtotal_usd=subtotal, priced_requests=len(amounts),
                total_requests=len(requests), coverage=len(amounts) / len(requests) if requests else None)


def summarize_review_costs(reviews):
    """Sum reconciled API equivalents, retaining unknown reviews and coverage."""
    if not isinstance(reviews, list):
        reviews = []
    costs = [ledger_cost(review.get('pricing_requests'), review.get('model'), review.get('usage'))
             if isinstance(review, dict) else _unknown('invalid_review') for review in reviews]
    subtotals = [cost.get('known_request_subtotal_usd', 0) for cost in costs]
    known = _money(sum((Decimal(str(value)) for value in subtotals), Decimal(0))) if all(
        value is not None for value in subtotals) else None
    priced = sum(cost['amount_usd'] is not None for cost in costs)
    missing = {}
    for cost in costs:
        if cost['amount_usd'] is None:
            reason = cost['reason']
            missing[reason] = missing.get(reason, 0) + 1
    return dict(amount_usd=_money(sum((Decimal(str(cost['amount_usd'])) for cost in costs), Decimal(0)))
                if reviews and priced == len(reviews) else None,
                known_request_subtotal_usd=known, priced_reviews=priced, total_reviews=len(reviews),
                missing_reviews=len(reviews) - priced, missing_reasons=missing,
                coverage=priced / len(reviews) if reviews else None)
