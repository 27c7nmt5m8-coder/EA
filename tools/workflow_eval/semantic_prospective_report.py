"""Separate PR/item denominators, immutable misses and all-attempt billing."""
import statistics

from . import semantic_prospective as p

ROUTES=('SHADOW_HIGH_CONF','LOW_CONF_REVIEW','PROVIDER_REVIEW','UNKNOWN_REVIEW','MANDATORY_HIGH')
BANDS=('<0.50','0.50-0.69','0.70-0.89','>=0.90')


def confidence_band(value):
    return BANDS[0 if value<.50 else 1 if value<.70 else 2 if value<.90 else 3]


def measured(values):
    known=[v for v in values if v is not None]
    return dict(value=sum(known) if values and len(known)==len(values) else None,
        measured_subtotal=sum(known) if known else None,
        reason=None if values and len(known)==len(values) else 'missing_or_no_measurements',
        coverage=dict(measured=len(known),total=len(values)))
def ratio(n,d): return dict(value=n/d if d else None,numerator=n,denominator=d,reason=None if d else 'empty_denominator')
def quality(records):
    binary=[r for r in records if r['eligible'] and r['truth'] in ('regression','no_regression') and r['jev'] in ('regression','no_regression')]
    counts={key:sum(r['jev']==a and r['truth']==b for r in binary) for key,a,b in (
        ('TP','regression','regression'),('TN','no_regression','no_regression'),
        ('FP','regression','no_regression'),('FN','no_regression','regression'))}
    tp,tn,fp,fn=(counts[k] for k in ('TP','TN','FP','FN'))
    agreement=[r for r in records if r['eligible'] and r['jev'] in ('regression','no_regression') and r['sol'] in ('regression','no_regression')]
    return dict(counts,binary_denominator=len(binary),recall=ratio(tp,tp+fn),precision=ratio(tp,tp+fp),
        specificity=ratio(tn,tn+fp),accuracy=ratio(tp+tn,len(binary)),
        agreement=ratio(sum(r['jev']==r['sol'] for r in agreement),len(agreement)))


def report(protocol,events):
    tasks=p.replay(protocol,events)
    records=[]; misses=[]; comparisons={}; routes={k:0 for k in ROUTES}; all_attempts=[]
    eligible=[]; contaminated=[]; unresolved=[]; complete=[]; primary_attempts={}; provider_errors=0
    for tid,t in tasks.items():
        s=t['snapshot']; all_attempts += [('jev',a) for a in t['jev']]+[('sol',a) for a in t['sol']]
        all_attempts += [('jev',dict(usage=None,elapsed_seconds=None)) for _ in t['pending_jev']]
        jev={}
        for a in t['jev']:
            # First valid pre-review result, never highest-confidence retry.
            if a['item_id'] not in jev or jev[a['item_id']]['status']!='OK': jev[a['item_id']]=a
        sol=next((a for a in t['sol'] if a['status']=='OK'),None)
        tainted=(t['ticket'] is not None and not t['ticket']['blinded']) or any(a['exposed_to_jev'] for a in t['sol'])
        if tainted: contaminated.append(tid)
        truth={i['item_id']:i for i in (t['truth'] or {}).get('items',[])}
        resolved=len(truth)==len(s['items']) and all(i['state']=='RESOLVED' for i in truth.values())
        if not resolved: unresolved.append(tid)
        live=bool(t['jev']) and all(a['execution']=='live' for a in t['jev']+t['sol'])
        floor_mismatch=any(a['reason']=='model_effort_mismatch' for a in t['sol'])
        valid=resolved and not tainted and live and not floor_mismatch and sol is not None and len(jev)==len(s['items'])
        if valid: eligible.append(tid)
        comparison=[]; sol_items={i['item_id']:i for i in (sol or {}).get('findings',[]) or []}
        primary_attempts[tid]=dict(jev=jev,sol=sol)
        for item in s['items']:
            key=item['item_id']; a=jev.get(key); g=truth.get(key)
            routing=p.route(s,item,a); comparison.append(routing)
            jc=a['choice'] if a and a['status']=='OK' else None
            sc=sol_items.get(key,{}).get('choice')
            gt=g['choice'] if g and g['state']=='RESOLVED' else None
            item_live=bool(a) and all(x['execution']=='live' for x in t['sol']+[x for x in t['jev'] if x['item_id']==key])
            item_valid=gt is not None and not tainted and item_live and not floor_mismatch and sol is not None
            record=dict(task_id=tid,item_id=key,eligible=item_valid,jev=jc,sol=sc,truth=gt,
                confidence=a['confidence'] if a and a['status']=='OK' else None,
                severity=g['severity'] if g and g['state']=='RESOLVED' else None,routing=routing)
            records.append(record)
            observed_misses=[x for x in t['jev'] if x['item_id']==key and x['status']=='OK' and x['choice']=='no_regression']
            if gt=='regression' and observed_misses:
                severity=g['severity']
                misses.append(dict(task_id=tid,pr_number=s['pr_number'],item_id=key,severity=severity,
                    attempt_ids=[x['attempt_id'] for x in observed_misses],
                    observed_confidences=[x['confidence'] for x in observed_misses],
                    confidence=max(x['confidence'] for x in observed_misses),
                    high_confidence=any(x['confidence']>=.90 for x in observed_misses),
                    primary_comparison_eligible=item_valid,state={'critical':'BLOCKED_CRITICAL_MISS',
                    'important':'IMPORTANT_MISS','minor':'MINOR_MISS'}[severity],
                    frozen_head_sha=s['head_sha'],recovered_or_fixed_does_not_erase=True))
        # Mandatory always wins; otherwise prefer any failure/unknown/low input.
        task_route=next(k for k in ('MANDATORY_HIGH','PROVIDER_REVIEW','UNKNOWN_REVIEW','LOW_CONF_REVIEW','SHADOW_HIGH_CONF') if k in comparison)
        routes[task_route]+=1; comparisons[tid]=task_route
        if valid and all(r['jev'] in ('regression','no_regression') and r['sol'] in ('regression','no_regression') for r in records if r['task_id']==tid):
            complete.append(tid)
        provider_errors+=sum(a['status']!='OK' for a in t['jev'])
    preflight={e['data']['pr_number'] for e in events if e['kind']=='preflight'}
    counts=quality(records)
    for severity in ('critical','important','minor'):
        counts[severity+'_misses']=sum(m['severity']==severity for m in misses)
    confidences=[r['confidence'] for r in records if r['confidence'] is not None]
    counts['confidence_distribution']=dict(min=min(confidences) if confidences else None,
        max=max(confidences) if confidences else None,mean=statistics.mean(confidences) if confidences else None,
        standard_deviation=statistics.pstdev(confidences) if len(confidences)>=2 else None,
        coverage=dict(measured=len(confidences),total=len(records)),reason=None if confidences else 'unmeasured')
    counts['unknown_or_unavailable_items']=sum(r['jev'] not in ('regression','no_regression') for r in records)
    bands={}
    for band in BANDS:
        members=[r for r in records if r['confidence'] is not None and
            confidence_band(r['confidence'])==band]
        q=quality(members)
        bands[band]=dict(case_count=len({r['task_id'] for r in members}),item_count=len(members),
            eligible_item_count=sum(r['eligible'] for r in members),accuracy=q['accuracy'],agreement=q['agreement'],
            regression_miss=q['FN'],false_positive=q['FP'],
            critical_miss=sum(m['severity']=='critical' and any(confidence_band(c)==band for c in m['observed_confidences']) for m in misses),
            important_miss=sum(m['severity']=='important' and any(confidence_band(c)==band for c in m['observed_confidences']) for m in misses),
            safety_audit_item_count=len({(tid,a['item_id']) for tid,t in tasks.items() for a in t['jev']
                                        if a['status']=='OK' and confidence_band(a['confidence'])==band}),
            safety_audit_scope='All valid attempts in their observed confidence band; unique PR/item per band, nonadditive across bands.',
            review_required_rate=ratio(sum(r['routing']!='SHADOW_HIGH_CONF' for r in members),len(members)))
    tokens={}
    for provider in ('jev','sol','combined'):
        subset=[a for arm,a in all_attempts if provider=='combined' or arm==provider]
        tokens[provider]={k:measured([(a['usage'] or {}).get(k) for a in subset]) for k in ('input_tokens','output_tokens','total_tokens')}
    processing={arm:measured([a['elapsed_seconds'] for name,a in all_attempts if name==arm]) for arm in ('jev','sol')}
    retry_times=[]
    for task in tasks.values():
        seen=set()
        for arm in ('jev','sol'):
            for a in task[arm]:
                key=(arm,a['item_id'])
                if key in seen: retry_times.append(a['elapsed_seconds'])
                seen.add(key)
    candidate=[tid for tid in eligible if comparisons[tid]=='SHADOW_HIGH_CONF' and
        all(a['choice']=='no_regression' for a in primary_attempts[tid]['jev'].values())]
    avoid=[a for tid in candidate for a in tasks[tid]['sol']]
    overhead=[a for arm,a in all_attempts if arm=='jev']
    known_cf=bool(overhead) and all(a['usage'] is not None for a in overhead+avoid)
    cf_tokens=sum(a['usage']['total_tokens'] for a in avoid)-sum(a['usage']['total_tokens'] for a in overhead) if known_cf else None
    time_cf=bool(overhead) and all(a['elapsed_seconds'] is not None for a in overhead+avoid)
    cf_seconds=sum(a['elapsed_seconds'] for a in avoid)-sum(a['elapsed_seconds'] for a in overhead) if time_cf else None
    verdict=('BLOCKED_CRITICAL_MISS' if counts['critical_misses'] else
        'SHADOW_REMEDIATION_REQUIRED' if counts['important_misses'] or contaminated else
        'SHADOW_READY_FOR_ROUTING_PROPOSAL' if len(eligible)>=20 and candidate and len(complete)==len(tasks) and not provider_errors and not counts['FN'] and tokens['combined']['total_tokens']['value'] is not None else
        'SHADOW_CONTINUE')
    # Any changed label across repeated valid attempts is observed instability.
    instability=0
    for task in tasks.values():
        for key in {a['item_id'] for a in task['jev']}:
            instability+=len({a['choice'] for a in task['jev'] if a['item_id']==key and a['status']=='OK'})>1
    if verdict!='BLOCKED_CRITICAL_MISS' and instability: verdict='SHADOW_REMEDIATION_REQUIRED'
    rework_keys=('confirmed_findings','fix_commits','red_green_tests','review_rounds','reopened_issues',
                 'regressions_after_fix','context_retrieval','test_failures','orchestration_wall_seconds')
    return dict(protocol_version=1,cohort_id=protocol['cohort_id'],shadow_only=True,review_skip_enabled=False,
        confidence_threshold=.90,actual_reviews_skipped=0,actual_token_savings=None,
        actual_savings_reason='All normal Sol High reviews remain required.',
        pr_level=dict(unique_prospective_prs=len(tasks),eligible=len(eligible),
            ineligible=len(set(preflight)-{t['snapshot']['pr_number'] for t in tasks.values()}),
            preflight_observations=sum(e['kind']=='preflight' for e in events),excluded_registered_prs=len(tasks)-len(eligible),
            contaminated=len(contaminated),ground_truth_unresolved=len(unresolved),complete_comparisons=len(complete),
            complete_comparison_coverage=ratio(len(complete),len(tasks)),routing=routes,
            checkpoint_reached=len(eligible)>=10,primary_goal_reached=len(eligible)>=20),
        items=dict(counts,semantic_item_denominator=len(records)),confidence_bands=bands,
        calibration_claim=False,misses=misses,verdict=verdict,tokens=tokens,
        low_confidence_rate=ratio(sum(c<.90 for c in confidences),len(confidences)),
        low_confidence_review_precision=ratio(sum(r['truth']=='regression' for r in records
            if r['eligible'] and r['truth'] is not None and r['confidence'] is not None and r['confidence']<.90),
            sum(r['eligible'] and r['truth'] is not None and r['confidence'] is not None and r['confidence']<.90 for r in records)),
        provider_reliability=ratio(sum(a['status']=='OK' for t in tasks.values() for a in t['jev']),
                                  sum(len(t['jev']) for t in tasks.values())),
        provider_unavailable_attempts=provider_errors,pending_jev_requests=sum(len(t['pending_jev']) for t in tasks.values()),instability_items=instability,
        failure_action='PROVIDER_UNAVAILABLE_REVIEW' if provider_errors else None,
        processing_seconds=processing,retry_seconds=measured(retry_times),
        billing_scope='Jev attempts and normal reviews of the first frozen head, including retries/failures/contamination.',
        complete_development_billing=dict(tokens=None,processing_seconds=None,
            reason='Later remediation/adjudication reviews are not collected by this primary-head recorder.'),
        sol_findings={k:measured([sum(i['counts'][k] for i in (primary_attempts[tid]['sol'] or {}).get('findings',[]) or [])
            if primary_attempts[tid]['sol'] is not None else None for tid in tasks]) for k in ('critical','important','minor')},
        cost=dict(value=None,reason='actual_price_tier_cache_billing_evidence_not_collected',coverage=dict(measured=0,total=len(all_attempts))),
        rework={k:measured([(t['rework'] or {}).get(k) for t in tasks.values()]) for k in rework_keys},
        counterfactual=dict(label='COUNTERFACTUAL_ONLY',candidate_prs=len(candidate),
            high_review_required_prs=len(tasks)-len(candidate),token_savings=cf_tokens,
            token_reason=None if known_cf else 'missing_usage_or_no_attempts',
            processing_sum_savings_seconds=cf_seconds,time_reason=None if time_cf else 'missing_time_or_no_attempts',
            scope='Hypothetical avoided Sol attempts minus all measured Jev overhead; not actual savings.'),
        limitations=['Pre-review knowledge/blinding and ground truth evidence require truthful external attestations.',
                     'Source hashes are provenance, not automatic semantic proof. Backend identity may be unavailable.',
                     'Twenty PRs do not establish per-band calibration or authorize routing adoption.'])
