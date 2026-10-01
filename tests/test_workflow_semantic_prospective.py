"""Offline event protocol and accounting; no live/provider/GitHub calls."""
import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.workflow_eval import semantic_prospective as p
from tools.workflow_eval.semantic_prospective_report import report

T = '2030-01-01T00:00:00+00:00'
SHA = 'a'*40
HASH = 'b'*64


def snapshot(protocol, number=900, mandatory=False):
    item=dict(item_id='I1', requirement='Preserve the specified interface.', baseline='The input is optional.',
              candidate='The input remains optional.', evidence='The interface test covers omission.',
              origins=['user_requirement','test_intent'], dependency='known', protected_areas=[], critical_dependency=False)
    return dict(schema_version=1,repository=p.REPO,pr_number=number,task_id=p.task_id(protocol,number),
                base_sha=SHA,head_sha='c'*40,merge_base_sha=SHA,diff_digest=HASH,source_fingerprint=HASH,
                changed_files=['src/Test.mqh'] if mandatory else ['tests/interface_scenarios.cpp'],
                items=[item],known_requirements=['Preserve the interface.'],known_protected_areas=[],
                test_evidence=[dict(kind='test',digest=HASH,status='PASS')],
                created_at='2030-01-01T00:00:01+00:00',observed_at='2030-01-01T00:00:02+00:00',
                snapshot_at='2030-01-01T00:00:03+00:00',prior_review_known=False,github_reviews=0,
                kind='ea_development')


def attempt(provider='jev', choice='no_regression', confidence=.95, usage=True):
    return dict(attempt_id=p.new_id(),item_id='I1' if provider=='jev' else None,
        status='OK',reason=None,choice=choice if provider=='jev' else None,
        confidence=confidence if provider=='jev' else None,
        probabilities={k:.98 if k==choice else .01 for k in p.CHOICES} if provider=='jev' else None,
        usage=dict(input_tokens=10,output_tokens=2,total_tokens=12) if usage else None,
        usage_reason=None if usage else 'missing_usage',elapsed_seconds=.2,
        requested_model='jev-1.13.0' if provider=='jev' else 'gpt-6.1-sol',requested_effort=None if provider=='jev' else 'high',
        effective_model='jev-1.13.0' if provider=='jev' else None,effective_effort=None,
        effective_identity_reason=None if provider=='jev' else 'backend_not_exposed',raw_result_digest=HASH,
        raw_digest_reason=None,execution='live',findings=None if provider=='jev' else [dict(item_id='I1',choice=choice,counts=dict(critical=0,important=0,minor=0))],
        exposed_to_jev=False if provider=='sol' else None,started_at='2030-01-01T00:00:04+00:00',
        completed_at='2030-01-01T00:00:05+00:00',head_sha='c'*40,diff_digest=HASH,source_fingerprint=HASH)


class Prospective(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.protocol=p.make_protocol(T,21,SHA)
        self.ledger=p.Ledger(Path(self.tmp.name)/'.workflow-eval/semantic-prospective',self.protocol)
        self.s=snapshot(self.protocol); self.id=self.s['task_id']

    def emit(self,kind,data,at): return self.ledger.append(kind,self.id,data,at)
    def freeze(self): self.emit('snapshot',self.s,'2030-01-01T00:00:03+00:00')
    def jev(self,value=None):
        a=value or attempt(); a.update(snapshot_digest=p.digest(self.s),contract_digest=p.digest(self.s['items']))
        self.emit('jev_request',{k:a[k] for k in ('attempt_id','item_id','snapshot_digest','contract_digest',
            'head_sha','diff_digest','source_fingerprint','started_at')},a['started_at'])
        return self.emit('jev',a,'2030-01-01T00:00:05+00:00')
    def ticket(self):
        return self.emit('review_start',dict(model='gpt-6.1-sol',effort='high',blinded=True,
            snapshot_digest=p.digest(self.s),contract_digest=p.digest(self.s['items'])), '2030-01-01T00:00:06+00:00')
    def sol(self,value=None):
        a=value or attempt('sol'); a.update(snapshot_digest=p.digest(self.s),contract_digest=p.digest(self.s['items']),
            started_at='2030-01-01T00:00:07+00:00',completed_at='2030-01-01T00:00:08+00:00')
        return self.emit('sol',a,'2030-01-01T00:00:08+00:00')
    def truth(self,choice='no_regression',severity=None,state='RESOLVED'):
        return self.emit('truth',dict(snapshot_digest=p.digest(self.s),head_sha=self.s['head_sha'],diff_digest=self.s['diff_digest'],items=[dict(item_id='I1',state=state,choice=choice,severity=severity,
            evidence=[dict(kind='source',digest=HASH),dict(kind='test',digest=HASH)] if state=='RESOLVED' else [],
            adjudicator_model='gpt-6.1-sol',adjudicator_effort='high')]),'2030-01-01T00:00:09+00:00')
    def complete(self,choice='no_regression',truth='no_regression',severity=None,confidence=.95):
        self.freeze(); self.jev(attempt(choice=choice,confidence=confidence)); self.ticket(); self.sol(attempt('sol',truth)); self.truth(truth,severity)
    def r(self): return report(self.protocol,self.ledger.read())

    def test_zero_cohort_and_no_actual_savings(self):
        r=self.r(); self.assertEqual(r['pr_level']['unique_prospective_prs'],0)
        self.assertIsNone(r['actual_token_savings']); self.assertEqual(r['verdict'],'SHADOW_CONTINUE')
    def test_duplicate_pr_and_revision_not_new_task(self):
        self.freeze()
        with self.assertRaises(ValueError): self.freeze()
        self.emit('revision',dict(head_sha='d'*40,diff_digest=HASH,fix_commits=None,red_green_tests=None), '2030-01-01T00:00:04+00:00')
        self.assertEqual(self.r()['pr_level']['unique_prospective_prs'],1)
    def test_historical_and_tooling_and_created_before_activation_rejected(self):
        for number in (11,12,17,18,19,20,21):
            s=snapshot(self.protocol,number)
            with self.assertRaises(ValueError): p.validate_snapshot(self.protocol,s)
        s=copy.deepcopy(self.s); s['created_at']=T
        with self.assertRaises(ValueError): p.validate_snapshot(self.protocol,s)
        s=copy.deepcopy(self.s); s['changed_files']=['tools/workflow_eval/helper.py']
        with self.assertRaises(ValueError): p.validate_snapshot(self.protocol,s)
    def test_timestamp_order_and_jev_before_sol(self):
        self.freeze()
        with self.assertRaises(ValueError): self.ticket()
        a=attempt(); a['completed_at']=T
        with self.assertRaises(ValueError): self.jev(a)
    def test_contamination_excluded_but_usage_kept(self):
        self.freeze(); self.jev(); self.ticket(); a=attempt('sol'); a['exposed_to_jev']=True
        self.sol(a); self.truth()
        r=self.r(); self.assertEqual(r['pr_level']['contaminated'],1)
        self.assertEqual(r['items']['binary_denominator'],0)
        self.assertEqual(r['tokens']['combined']['total_tokens']['value'],24)
    def test_digest_and_head_mismatch_rejected(self):
        self.freeze(); a=attempt(); a.update(snapshot_digest='e'*64,contract_digest=p.digest(self.s['items']))
        with self.assertRaises(ValueError): self.emit('jev',a,'2030-01-01T00:00:05+00:00')
        self.jev(); self.ticket(); a=attempt('sol'); a['snapshot_digest']='e'*64
        with self.assertRaises(ValueError): self.emit('sol',a,'2030-01-01T00:00:08+00:00')
    def test_oracle_leakage_and_duplicate_items(self):
        s=copy.deepcopy(self.s); s['items'][0]['expected_result']='no_regression'
        with self.assertRaises(ValueError): p.validate_snapshot(self.protocol,s)
        s=copy.deepcopy(self.s); s['items'][0]['evidence']='expected_result=no_regression'
        with self.assertRaises(ValueError): p.validate_snapshot(self.protocol,s)
        s=copy.deepcopy(self.s); s['items'].append(s['items'][0])
        with self.assertRaises(ValueError): p.validate_snapshot(self.protocol,s)
    def test_unknown_and_unresolved_not_tn(self):
        self.complete(choice='unknown'); r=self.r(); self.assertEqual(r['items']['TN'],0)
        self.assertEqual(r['items']['binary_denominator'],0)
    def test_unresolved_truth_not_binary(self):
        self.freeze(); self.jev(); self.ticket(); self.sol(); self.truth(None,None,'GROUND_TRUTH_UNRESOLVED')
        self.assertEqual(self.r()['pr_level']['ground_truth_unresolved'],1)
        self.assertEqual(self.r()['items']['binary_denominator'],0)
    def test_critical_and_important_miss_preserved_after_fix_and_exclusion(self):
        self.complete(truth='regression',severity='critical'); r=self.r()
        self.assertEqual(r['verdict'],'BLOCKED_CRITICAL_MISS'); self.assertEqual(r['items']['critical_misses'],1)
        self.emit('revision',dict(head_sha='d'*40,diff_digest=HASH,fix_commits=1,red_green_tests=1), '2030-01-01T00:00:10+00:00')
        self.assertEqual(self.r()['items']['critical_misses'],1)
    def test_important_miss_individual(self):
        self.complete(truth='regression',severity='important')
        self.assertEqual(self.r()['misses'][0]['state'],'IMPORTANT_MISS')
    def test_missing_usage_and_retry_billing(self):
        self.freeze(); bad=attempt(usage=False); bad.update(status='UNAVAILABLE',reason='timeout',choice=None,confidence=None,probabilities=None)
        self.jev(bad); a=attempt(); a.update(started_at='2030-01-01T00:00:05+00:00',completed_at='2030-01-01T00:00:06+00:00')
        a.update(snapshot_digest=p.digest(self.s),contract_digest=p.digest(self.s['items']))
        self.emit('jev_request',{k:a[k] for k in ('attempt_id','item_id','snapshot_digest','contract_digest',
            'head_sha','diff_digest','source_fingerprint','started_at')},a['started_at'])
        self.emit('jev',a,'2030-01-01T00:00:06+00:00')
        r=self.r(); self.assertEqual(r['pr_level']['unique_prospective_prs'],1)
        self.assertIsNone(r['tokens']['jev']['total_tokens']['value']); self.assertEqual(r['tokens']['jev']['total_tokens']['measured_subtotal'],12)
    def test_threshold_fixed_and_storage_separation(self):
        altered=copy.deepcopy(self.protocol); altered['confidence_threshold']=.8
        with self.assertRaises(ValueError): p.validate_protocol(altered)
        with self.assertRaises(ValueError): p.Ledger(Path(self.tmp.name)/'.workflow-eval/real-tasks',self.protocol)
    def test_protected_mandatory_high(self):
        self.s=snapshot(self.protocol,mandatory=True); self.complete()
        self.assertEqual(self.r()['pr_level']['routing']['MANDATORY_HIGH'],1)
        self.assertEqual(self.r()['counterfactual']['candidate_prs'],0)
    def test_duplicate_attempt_stale_chain_and_malformed(self):
        self.freeze(); self.jev(); events=self.ledger.read(); a=copy.deepcopy(events[-1]['data'])
        with self.assertRaises(ValueError): self.emit('jev',a,'2030-01-01T00:00:06+00:00')
        self.assertEqual(p.normalize_jev(dict(status='OK',answer={'choice':'no_regression'}))['status'],'UNAVAILABLE')
        path=sorted(self.ledger.path.glob('event-*.json'))[0]; obj=json.loads(path.read_text()); obj['data']['head_sha']='e'*40; path.write_text(json.dumps(obj))
        with self.assertRaises(ValueError): self.ledger.read()
    def test_ground_truth_cannot_be_single_ai_claim(self):
        self.freeze(); self.jev(); self.ticket(); self.sol()
        data=dict(snapshot_digest=p.digest(self.s),head_sha=self.s['head_sha'],diff_digest=self.s['diff_digest'],items=[dict(item_id='I1',state='RESOLVED',choice='regression',severity='important',
            evidence=[dict(kind='review',digest=HASH)],adjudicator_model='gpt-6.1-sol',adjudicator_effort='high')])
        with self.assertRaises(ValueError): self.emit('truth',data,'2030-01-01T00:00:09+00:00')

    def test_routing_priority_and_threshold_boundary(self):
        item=self.s['items'][0]
        for value,expected in ((attempt(confidence=.9),'SHADOW_HIGH_CONF'),(attempt(confidence=.89),'LOW_CONF_ESCALATE'),
                               (attempt(choice='unknown'),'UNKNOWN_ESCALATE'),(None,'PROVIDER_ESCALATE')):
            self.assertEqual(p.route(self.s,item,value),expected)
        item['dependency']='unknown'; self.assertEqual(p.route(self.s,item,attempt()),'MANDATORY_HIGH')
        item['dependency']='known'; item['critical_dependency']=True
        self.assertEqual(p.route(self.s,item,None),'MANDATORY_HIGH')
    def test_critical_miss_survives_contamination_exclusion(self):
        self.freeze(); self.jev(); self.ticket(); a=attempt('sol','regression'); a['exposed_to_jev']=True
        self.sol(a); self.truth('regression','critical'); r=self.r()
        self.assertEqual(r['items']['binary_denominator'],0)
        self.assertEqual(r['items']['critical_misses'],1); self.assertEqual(r['verdict'],'BLOCKED_CRITICAL_MISS')
    def test_counterfactual_is_separate_and_includes_jev_overhead(self):
        self.complete(); r=self.r()
        self.assertEqual(r['counterfactual']['label'],'COUNTERFACTUAL_ONLY')
        self.assertEqual(r['counterfactual']['token_savings'],0)
        self.assertEqual(r['tokens']['combined']['total_tokens']['value'],24)
        self.assertIsNone(r['actual_token_savings']); self.assertEqual(r['actual_reviews_skipped'],0)
    def test_band_denominators_and_confidence_not_retries(self):
        self.complete(confidence=.69); r=self.r()
        self.assertEqual(r['confidence_bands']['0.50-0.69']['item_count'],1)
        self.assertEqual(r['confidence_bands']['0.50-0.69']['accuracy']['denominator'],1)
        self.assertFalse(r['calibration_claim'])
    def test_malformed_provider_keeps_known_usage(self):
        a=p.normalize_jev(dict(status='OK',model='jev-1.13.0',answer={},
            usage=dict(input_tokens=10,output_tokens=2,total_tokens=12)))
        self.assertEqual(a['status'],'UNAVAILABLE'); self.assertIsNone(a['choice'])
        self.assertEqual(a['usage']['total_tokens'],12)
    def test_pending_provider_blocks_review_and_billing_is_null(self):
        self.freeze(); a=attempt(); a.update(snapshot_digest=p.digest(self.s),contract_digest=p.digest(self.s['items']))
        self.emit('jev_request',{k:a[k] for k in ('attempt_id','item_id','snapshot_digest','contract_digest',
            'head_sha','diff_digest','source_fingerprint','started_at')},a['started_at'])
        with self.assertRaises(ValueError): self.ticket()
        self.assertIsNone(self.r()['tokens']['jev']['total_tokens']['value'])
        self.assertEqual(self.r()['pending_jev_requests'],1)
    def test_wrong_head_source_and_raw_fields_rejected(self):
        self.freeze(); self.jev(); self.ticket()
        for key,value in (('head_sha','d'*40),('source_fingerprint','e'*64),('raw_trace','private data')):
            a=attempt('sol'); a[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError): self.sol(a)
    def test_offline_provenance_never_primary_and_confirmed_truth_cannot_be_rewritten(self):
        self.freeze(); a=attempt(); a['execution']='offline_fixture'; self.jev(a); self.ticket(); self.sol(); self.truth()
        self.assertEqual(self.r()['pr_level']['eligible'],0)
        with self.assertRaises(ValueError): self.truth('regression','critical')
    def test_duplicate_preflight_not_primary_or_ineligible_inflation(self):
        for _ in range(2): self.ledger.append('preflight',None,dict(pr_number=20,reason='NOT_ELIGIBLE_HISTORICAL'),'2030-01-01T00:00:01+00:00')
        r=self.r(); self.assertEqual(r['pr_level']['unique_prospective_prs'],0)
        self.assertEqual(r['pr_level']['ineligible'],1)
    def test_reviewer_packet_has_no_jev_metadata(self):
        from tools.workflow_eval.semantic_prospective_cli import reviewer_packet
        self.freeze(); self.jev()
        t=p.replay(self.protocol,self.ledger.read())[self.id]; packet=reviewer_packet(t)
        rendered=json.dumps(packet)
        for value in ('confidence','probabilities','SHADOW_HIGH_CONF','"jev"','expected_result'):
            self.assertNotIn(value,rendered)

    def test_cli_freezes_git_bytes_digest_but_not_raw_source(self):
        from tools.workflow_eval.semantic_prospective_cli import freeze,SPEC_FIELDS
        import hashlib
        info=dict(number=900,state='open',merged_at=None,created_at=self.s['created_at'],
            base=dict(sha=SHA,repo=dict(full_name=p.REPO)),head=dict(sha='c'*40))
        def fetch(path): return [] if 'reviews?' in path else copy.deepcopy(info)
        def git(*args):
            if args[0]=='cat-file': return b''
            if args[0]=='merge-base': return SHA.encode()
            if args[0]=='rev-parse': return SHA.encode()
            if '--name-only' in args: return b'tests/interface_scenarios.cpp\0'
            return b'private source bytes used only for digest'
        e=freeze(self.ledger,900,{k:self.s[k] for k in SPEC_FIELDS},fetcher=fetch,git_runner=git,
                 clock=lambda:'2030-01-01T00:00:03+00:00')
        self.assertEqual(e['data']['diff_digest'],hashlib.sha256(b'private source bytes used only for digest').hexdigest())
        self.assertNotIn('private source bytes',json.dumps(e))
    def test_cli_github_failure_records_ineligible_never_case(self):
        from tools.workflow_eval.semantic_prospective_cli import freeze,SPEC_FIELDS
        def fetch(path): raise ValueError('github_unavailable')
        e=freeze(self.ledger,900,{k:self.s[k] for k in SPEC_FIELDS},fetcher=fetch,
                 clock=lambda:'2030-01-01T00:00:03+00:00')
        self.assertEqual(e['data']['reason'],'GITHUB_UNAVAILABLE')
        self.assertEqual(self.r()['pr_level']['unique_prospective_prs'],0)
    def test_ground_truth_wrong_revision_rejected(self):
        self.freeze(); self.jev(); self.ticket(); self.sol()
        data=dict(snapshot_digest=p.digest(self.s),head_sha='d'*40,diff_digest=HASH,items=[])
        with self.assertRaises(ValueError): self.emit('truth',data,'2030-01-01T00:00:09+00:00')
    def test_post_review_contract_phrases_and_python_tooling_rejected(self):
        for phrase in ('review findings show a defect.','Sol found a regression.','merge outcome is accepted.'):
            s=copy.deepcopy(self.s); s['items'][0]['evidence']=phrase
            with self.subTest(phrase=phrase),self.assertRaises(ValueError): p.validate_snapshot(self.protocol,s)
        s=copy.deepcopy(self.s); s['changed_files']=['tests/test_developer_tooling.py']
        with self.assertRaises(ValueError): p.validate_snapshot(self.protocol,s)

    def test_partial_effective_identity_cannot_downgrade_effort(self):
        self.freeze(); self.jev(); self.ticket()
        a=attempt('sol'); a['effective_effort']='high'
        with self.assertRaises(ValueError): self.sol(a)
        a.update(status='UNAVAILABLE',reason='model_effort_mismatch',findings=None,
                 effective_identity_reason='model_effort_mismatch')
        self.sol(a)
        self.assertEqual(self.r()['tokens']['sol']['total_tokens']['value'],12)
        self.assertEqual(self.r()['pr_level']['eligible'],0)

    def test_declared_backend_mismatch_is_failed_but_keeps_usage(self):
        self.freeze(); self.jev(); self.ticket()
        a=attempt('sol'); a['effective_identity_reason']='model_effort_mismatch'
        with self.assertRaises(ValueError): self.sol(a)
        a.update(status='UNAVAILABLE',reason='model_effort_mismatch',findings=None,effective_effort='medium')
        self.sol(a)
        self.assertEqual(self.r()['tokens']['sol']['total_tokens']['value'],12)
        self.assertEqual(self.r()['items']['binary_denominator'],0)

    def test_pending_reservation_rejects_second_stale_process(self):
        self.freeze(); a=attempt(); a.update(snapshot_digest=p.digest(self.s),contract_digest=p.digest(self.s['items']))
        keys=('attempt_id','item_id','snapshot_digest','contract_digest','head_sha','diff_digest','source_fingerprint','started_at')
        reservation={k:a[k] for k in keys}
        self.emit('jev_request',reservation,a['started_at'])
        # Another CLI may have read the old no-pending state before this append.
        second=dict(reservation,attempt_id=p.new_id())
        with self.assertRaises(ValueError): self.emit('jev_request',second,a['started_at'])
        self.emit('jev',a,a['completed_at'])
        self.assertEqual(self.r()['pending_jev_requests'],0)
        self.ticket()

    def test_resolved_items_survive_other_item_unresolved(self):
        other=copy.deepcopy(self.s['items'][0]); other['item_id']='I2'; self.s['items'].append(other)
        self.freeze(); self.jev()
        a=attempt(); a.update(item_id='I2',started_at='2030-01-01T00:00:05+00:00')
        self.jev(a); self.ticket()
        a=attempt('sol'); a['findings'].append(dict(item_id='I2',choice='unknown',counts=dict(critical=0,important=0,minor=0)))
        self.sol(a)
        truth=[dict(item_id='I1',state='RESOLVED',choice='no_regression',severity=None,
                    evidence=[dict(kind='source',digest=HASH),dict(kind='test',digest=HASH)],
                    adjudicator_model=p.MODEL,adjudicator_effort=p.EFFORT),
               dict(item_id='I2',state='GROUND_TRUTH_UNRESOLVED',choice=None,severity=None,evidence=[],
                    adjudicator_model=p.MODEL,adjudicator_effort=p.EFFORT)]
        self.emit('truth',dict(items=truth,snapshot_digest=p.digest(self.s),head_sha=self.s['head_sha'],diff_digest=HASH),
                  '2030-01-01T00:00:09+00:00')
        r=self.r(); self.assertEqual(r['pr_level']['eligible'],0)
        self.assertEqual(r['items']['binary_denominator'],1); self.assertEqual(r['items']['TN'],1)
        self.assertEqual(r['items']['semantic_item_denominator'],2)

    def test_later_retry_critical_miss_blocks_without_primary_inflation(self):
        self.freeze(); self.jev(attempt(choice='regression'))
        a=attempt(); a.update(started_at='2030-01-01T00:00:05+00:00')
        self.jev(a); self.ticket(); self.sol(attempt('sol','regression')); self.truth('regression','critical')
        r=self.r(); self.assertEqual(r['items']['TP'],1); self.assertEqual(r['items']['FN'],0)
        self.assertEqual(r['items']['critical_misses'],1); self.assertEqual(r['verdict'],'BLOCKED_CRITICAL_MISS')
        self.assertEqual(r['pr_level']['unique_prospective_prs'],1)
        self.assertEqual(r['misses'][0]['attempt_ids'],[a['attempt_id']])

    def test_retry_safety_miss_attributed_to_actual_confidence_band(self):
        self.freeze(); self.jev(attempt(choice='regression',confidence=.45))
        a=attempt(); a.update(started_at='2030-01-01T00:00:05+00:00')
        self.jev(a); self.ticket(); self.sol(attempt('sol','regression')); self.truth('regression','critical')
        r=self.r(); low=r['confidence_bands']['<0.50']; high=r['confidence_bands']['>=0.90']
        self.assertEqual(low['critical_miss'],0); self.assertEqual(high['critical_miss'],1)
        self.assertEqual(low['accuracy']['denominator'],1); self.assertEqual(high['accuracy']['denominator'],0)
        self.assertEqual(high['safety_audit_item_count'],1)


if __name__=='__main__': unittest.main()
