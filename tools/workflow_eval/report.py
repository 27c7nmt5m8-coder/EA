"""Paired metrics, missing-evidence handling and an unconditional no-skip release."""
from .telemetry import usage_numbers
from .triage import HISTORICAL_SOL_MODELS, RECORDED_SOL_MODELS
from .pricing import summarize_review_costs


def paired_rows(rows):
    valid = []
    paired_originals = set()
    for row in rows:
        if row.get('a', {}).get('status') != 'OK' or row.get('b', {}).get('status') != 'OK':
            continue
        try:
            normalized = dict(row)
            for arm in ('a', 'b'):
                import math
                duration = row[arm]['elapsed_seconds']
                if type(duration) not in (int, float) or not math.isfinite(duration) or duration < 0:
                    raise ValueError('invalid_duration')
                if row[arm]['route'] not in ('candidate', 'review', 'unknown'):
                    raise ValueError('invalid_route')
                effort = row[arm].get('reasoning_effort')
                if (row[arm].get('model') not in RECORDED_SOL_MODELS or effort not in ('high', 'xhigh')):
                    raise ValueError('model_floor')
                normalized[arm] = dict(row[arm], usage=usage_numbers(row[arm]['usage']))
            if row['a'].get('model') != row['b'].get('model') or row['a'].get('reasoning_effort') != row['b'].get('reasoning_effort'):
                raise ValueError('unmatched_models')
            valid.append(normalized)
            paired_originals.add(id(row))
        except (KeyError, ValueError, TypeError):
            continue
    return valid, paired_originals


def summarize(rows):
    valid, paired_originals = paired_rows(rows)
    totals = {arm: {key: sum(r[arm]['usage'][key] for r in valid)
                    for key in ('input_tokens', 'output_tokens', 'total_tokens')} for arm in ('a', 'b')}
    reduction = {k: round(100 * (totals['a'][k] - totals['b'][k]) / totals['a'][k], 4)
                 if totals['a'][k] else None for k in totals['a']}
    comparable = [r for r in valid if r.get('jev', {}).get('status') == 'OK']
    agrees = sum(r['jev']['answer']['choice'] == r['b']['route'] for r in comparable)
    misses = [r for r in valid if r.get('truth') in ('review', 'unknown') and r['b']['route'] == 'candidate']
    # Safety observations survive partner/model/usage failures excluded from savings.
    critical = [r for r in rows if r.get('severity') == 'critical' and r.get('truth') in ('review', 'unknown')
                and any(r.get(arm, {}).get('status') == 'OK' and r[arm].get('route') == 'candidate'
                        for arm in ('a', 'b'))]
    shadow_misses = [r for r in valid if r.get('truth') in ('review', 'unknown')
                     and r.get('shadow', {}).get('shadow_route') == 'candidate']
    critical_shadow = [r for r in rows if r.get('severity') == 'critical' and r.get('truth') in ('review', 'unknown')
                       and r.get('shadow', {}).get('shadow_route') == 'candidate']
    critical_shadow += [r for r in rows if r.get('severity') == 'critical' and r.get('truth') in ('review', 'unknown')
                       and r.get('jev', {}).get('status') == 'OK'
                       and r['jev'].get('answer', {}).get('choice') == 'candidate']
    jev_raw_misses = [r for r in comparable if r.get('truth') in ('review', 'unknown')
                      and r['jev']['answer']['choice'] == 'candidate']
    labels_known = all(r.get('truth') in ('candidate', 'review', 'unknown') for r in valid)
    reworks = [r.get('rework_count') for r in valid]
    known_jev_tokens = 0
    paired_jev_tokens = 0
    missing_jev_usage = 0
    for r in rows:
        jev = r.get('jev', {})
        try:
            measured = usage_numbers(jev.get('usage'))
            known_jev_tokens += measured['total_tokens']
            if id(r) in paired_originals:paired_jev_tokens += measured['total_tokens']
        except ValueError:
            missing_jev_usage += jev.get('attempts', 0)
    jev_tokens = None if missing_jev_usage else known_jev_tokens
    elapsed = {arm: round(sum(r[arm]['elapsed_seconds'] for r in valid), 6) for arm in ('a', 'b')}
    jev_seconds = []
    import math
    for r in valid:
        jev=r.get('jev',{})
        duration=jev.get('elapsed_seconds',0 if not jev.get('attempts',0) else None)
        if type(duration) not in (int,float) or not math.isfinite(duration) or duration<0:jev_seconds=None;break
        jev_seconds.append(duration)
    b_known_tokens=0
    b_usage_complete=bool(rows)
    for r in rows:
        try:
            b_known_tokens+=usage_numbers(r['b']['usage'])['total_tokens']
            if r['b'].get('status')!='OK':b_usage_complete=False
        except (KeyError,ValueError,TypeError):b_usage_complete=False
    result = dict(scope='synthetic_fixed_review_tasks; not end-to-end EA development',
                  pairs=len(rows), valid_pairs=len(valid), invalid_pairs=len(rows)-len(valid),
                  gpt6_totals=totals, gpt6_reduction_percent=reduction,
                  review_seconds=elapsed, b_including_jev_seconds=round(elapsed['b']+sum(jev_seconds), 6) if jev_seconds is not None else None,
                  agreement_count=agrees, agreement_denominator=len(comparable),
                  jev_sol_agreement_rate=agrees/len(comparable) if comparable else None,
                  agreement_coverage=len(comparable)/len(valid) if valid else None,
                  sol_false_negatives=len(misses), critical_misses=len({r['id'] for r in critical+critical_shadow}),
                  shadow_false_negatives=len(shadow_misses), jev_raw_false_negatives=len(jev_raw_misses),
                  critical_case_count=sum(r.get('severity') == 'critical' for r in valid),
                  missing_context_cases=sum(bool(r.get('missing_context')) for r in valid),
                  missing_context_items=sum(len(r.get('missing_context', [])) for r in valid),
                  unresolved_missing_context_cases=sum(bool(r.get('unresolved_missing_context')) for r in valid),
                  shadow_escalation_rate=sum(r.get('shadow', {}).get('shadow_route') == 'review' for r in valid)/len(valid) if valid else None,
                  actual_sol_review_rate=1.0 if valid else None, review_skip_enabled=False,
                  actual_reviews_skipped=0, rework_count=sum(reworks) if reworks and all(type(x) is int for x in reworks) else None,
                  jev_total_tokens=jev_tokens, jev_known_token_subtotal=known_jev_tokens,
                  paired_jev_token_subtotal=paired_jev_tokens,b_known_gpt6_token_subtotal=b_known_tokens,
                  b_all_provider_total_tokens=b_known_tokens+jev_tokens if jev_tokens is not None and b_usage_complete else None,
                  quality_certified=False, labels_complete=labels_known,
                  decision='BLOCKED_CRITICAL_MISS' if critical or critical_shadow else 'SHADOW_ONLY_INSUFFICIENT_FOR_ADOPTION',
                  remediation='Analyze misses and revise routing before any separate skip implementation.' if critical or critical_shadow else None)
    result['review_provenance'] = [dict(model=model, reasoning_effort=effort,
                                       pairs=sum(r['a']['model'] == model and r['a']['reasoning_effort'] == effort for r in valid))
                                    for model, effort in sorted({(r['a']['model'], r['a']['reasoning_effort']) for r in valid})]
    result['a_false_negatives'] = sum(r.get('truth') in ('review', 'unknown') and r.get('a', {}).get('status') == 'OK'
                                    and r['a'].get('route') == 'candidate' for r in rows)
    result['a_context_task_errors'] = sum(r.get('truth') != r['a']['route'] for r in valid if r.get('truth'))
    result['b_context_task_errors'] = sum(r.get('truth') != r['b']['route'] for r in valid if r.get('truth'))
    result['observed_completed_sol_turns'] = {arm: sum(r[arm].get('observed_completed_turns', 0) for r in valid) for arm in ('a', 'b')}
    result['exact_gpt6_backend_calls'] = None
    result['jev_usage_missing_attempts'] = missing_jev_usage
    result['model_versions'] = sorted({r['jev']['model'] for r in comparable if r['jev'].get('model')})
    result['jev_model_drift'] = len(result['model_versions']) > 1
    result['jev_critical_cases_evaluated'] = sum(r.get('severity') == 'critical' for r in comparable)
    result['jev_false_negative_denominator'] = sum(r.get('truth') in ('review', 'unknown') for r in comparable)
    paired_jev_complete=all(not r.get('jev',{}).get('attempts',0) or r.get('jev',{}).get('usage') for r in valid)
    result['all_provider_total_reduction_percent'] = round(100*(totals['a']['total_tokens']-totals['b']['total_tokens']-paired_jev_tokens)/totals['a']['total_tokens'],4) if totals['a']['total_tokens'] and jev_tokens is not None and paired_jev_complete else None
    # Legacy rates apply only to historical GPT-6 Sol provenance. New-model
    # pricing is unverified, so its estimate stays unknown.
    scenario = {}
    for arm in ('a', 'b'):
        eligible = valid and all(r[arm].get('model') in HISTORICAL_SOL_MODELS and r[arm]['usage']['input_tokens'] <= 272000
                                 and {'cached_input_tokens','cache_write_input_tokens'} <= set(r[arm].get('usage_fields', []))
                                 and r[arm]['usage'].get('cache_write_input_tokens') == 0 for r in valid)
        scenario[arm] = round(sum(((r[arm]['usage']['input_tokens']-r[arm]['usage']['cached_input_tokens'])*2
                                  +r[arm]['usage']['cached_input_tokens']*.2+r[arm]['usage']['output_tokens']*10)/1e6
                                 for r in valid),6) if eligible else None
    result['standard_short_context_sol_api_equivalent_usd'] = scenario
    result['observed_text_token_api_equivalent'] = {
        arm: summarize_review_costs([r.get(arm) for r in rows]) for arm in ('a', 'b')}
    result['all_provider_cost_usd'] = None
    result['cost_limitations'] = 'The legacy scenario field remains historical GPT-6 Sol only. Observed request text-token API equivalents require reconciled model/tier/cache/context/region evidence; missing evidence stays unknown. Actual CLI billing and JEV rates unavailable.'
    return result
