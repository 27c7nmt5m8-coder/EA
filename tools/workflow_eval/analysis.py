"""Arithmetic decomposition of eligible paired usage; no causal quality claims."""
from .telemetry import usage_numbers
from .report import paired_rows


def decompose(rows):
    valid, paired_originals = paired_rows(rows)
    totals = {arm: {key: sum(r[arm]['usage'][key] for r in valid)
                    for key in ('input_tokens', 'output_tokens', 'total_tokens')} for arm in ('a', 'b')}
    observed = {arm: dict(input_tokens=0, output_tokens=0, total_tokens=0) for arm in ('a', 'b')}
    missing = dict(a=0, b=0)
    known_jev = paired_jev = missing_jev = paired_missing_jev = 0
    for r in rows:
        for arm in ('a', 'b'):
            try:
                measured = usage_numbers(r[arm]['usage'])
                for key in observed[arm]: observed[arm][key] += measured[key]
            except (KeyError, ValueError, TypeError): missing[arm] += 1
        try:
            measured = usage_numbers(r.get('jev', {}).get('usage'))
            known_jev += measured['total_tokens']
            if id(r) in paired_originals: paired_jev += measured['total_tokens']
        except (ValueError, TypeError):
            attempts = r.get('jev', {}).get('attempts', 0)
            missing_jev += attempts
            if id(r) in paired_originals: paired_missing_jev += attempts
    denominator = totals['a']['total_tokens']
    removed = totals['a']['input_tokens'] - totals['b']['input_tokens'] if valid else None
    extra = totals['b']['output_tokens'] - totals['a']['output_tokens'] if valid else None
    routing = dict(mandatory=0, semantic_review_or_unknown=0, low_confidence_candidates=0, candidates=0)
    for r in rows:
        shadow = r.get('shadow', {})
        if shadow.get('mandatory_reasons'):
            routing['mandatory'] += 1
        elif shadow.get('shadow_route') == 'candidate':
            routing['candidates'] += 1
        elif (r.get('jev', {}).get('answer') or {}).get('choice') == 'candidate':
            routing['low_confidence_candidates'] += 1
        else:
            routing['semantic_review_or_unknown'] += 1
    groups = []
    for effort in sorted({r['a']['reasoning_effort'] for r in valid}):
        group = [r for r in valid if r['a']['reasoning_effort'] == effort]
        groups.append(dict(effort=effort, cases=len(group),
                           a_output=sum(r['a']['usage']['output_tokens'] for r in group),
                           b_output=sum(r['b']['usage']['output_tokens'] for r in group)))
    return dict(pairs=len(valid), attempted_pairs=len(rows), invalid_pairs=len(rows)-len(valid), totals=totals,
                observed_gpt6_usage_subtotals=observed, gpt6_usage_missing_records=missing,
                jev_known_token_subtotal=known_jev, jev_usage_missing_attempts=missing_jev,
                input_tokens_removed=removed, extra_output_tokens=extra,
                jev_tokens_added=paired_jev if valid and not paired_missing_jev else None,
                net_tokens_removed=removed-extra-paired_jev if valid and not paired_missing_jev else None,
                input_saving_points=100*removed/denominator if denominator else None,
                output_penalty_points=100*extra/denominator if denominator else None,
                jev_penalty_points=100*paired_jev/denominator if denominator and not paired_missing_jev else None,
                routing=routing, routing_scope='all attempted rows; savings require eligible matched pairs',
                output_by_effort=groups, causal_explanation_confirmed=False,
                limitation='Reported output includes non-visible generation; original reasoning/visible breakdown unavailable. No calls were skipped.')
