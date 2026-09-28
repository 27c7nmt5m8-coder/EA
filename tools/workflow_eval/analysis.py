"""Arithmetic decomposition of paired review usage; no causal quality claims."""
from .telemetry import usage_numbers


def decompose(rows):
    totals = {arm: {key: sum(usage_numbers(r[arm]['usage'])[key] for r in rows)
                    for key in ('input_tokens', 'output_tokens', 'total_tokens')} for arm in ('a', 'b')}
    known_jev = sum(usage_numbers(r['jev']['usage'])['total_tokens'] for r in rows if r.get('jev', {}).get('usage'))
    missing_jev = any(r.get('jev', {}).get('attempts', 0) and not r['jev'].get('usage') for r in rows)
    removed = totals['a']['input_tokens'] - totals['b']['input_tokens']
    extra = totals['b']['output_tokens'] - totals['a']['output_tokens']
    denominator = totals['a']['total_tokens']
    routing = dict(mandatory=0, semantic_review_or_unknown=0, low_confidence_candidates=0, candidates=0)
    for r in rows:
        if r['shadow']['mandatory_reasons']:
            routing['mandatory'] += 1
        elif r['shadow']['shadow_route'] == 'candidate':
            routing['candidates'] += 1
        elif r.get('jev', {}).get('answer', {}).get('choice') == 'candidate':
            routing['low_confidence_candidates'] += 1
        else:
            routing['semantic_review_or_unknown'] += 1
    groups = []
    for effort in sorted({r['a']['reasoning_effort'] for r in rows}):
        group = [r for r in rows if r['a']['reasoning_effort'] == effort]
        groups.append(dict(effort=effort, cases=len(group),
                           a_output=sum(r['a']['usage']['output_tokens'] for r in group),
                           b_output=sum(r['b']['usage']['output_tokens'] for r in group)))
    return dict(pairs=len(rows), totals=totals, input_tokens_removed=removed, extra_output_tokens=extra,
                jev_tokens_added=None if missing_jev else known_jev,
                net_tokens_removed=None if missing_jev else removed-extra-known_jev,
                input_saving_points=100*removed/denominator if denominator else None,
                output_penalty_points=100*extra/denominator if denominator else None,
                jev_penalty_points=100*known_jev/denominator if denominator and not missing_jev else None,
                routing=routing, output_by_effort=groups,
                causal_explanation_confirmed=False,
                limitation='Reported output includes non-visible generation; original reasoning/visible breakdown unavailable. No calls were skipped.')
