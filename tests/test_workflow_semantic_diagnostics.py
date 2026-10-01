"""Offline checks for the immutable-input diagnostic, never live provider calls."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.workflow_eval import semantic_diagnostics as diag
from tools.workflow_eval import semantic_real as real


class Diagnostics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases, _ = real.load_cases(diag.FIXTURE)
        cls.plan = diag.protocol(cls.cases)

    def row(self, case='ER003', provider='jev', choice='no_regression', confidence=.54,
            repeat=1, usage=True):
        answer = dict(type='choice', choice=choice, confidence=confidence,
                      probabilities={c: .98 if c == choice else .01 for c in real.CHOICES})
        value = dict(status='OK', answer=answer, model='jev-1.13.0' if provider == 'jev' else real.SOL_MODEL,
                     reasoning_effort=None if provider == 'jev' else 'high', elapsed_seconds=.1,
                     usage=dict(input_tokens=10, output_tokens=2, total_tokens=12) if usage else None)
        return diag.observation(self.plan, case, provider, repeat, 1, value)

    def test_frozen_fixture_and_provenance_hashes(self):
        diag.verify_frozen()
        self.assertEqual(hashlib.sha256(diag.FIXTURE.read_bytes()).hexdigest(), diag.FIXTURE_SHA)

    def test_two_targets_three_anomalies_and_fixed_controls(self):
        self.assertEqual(self.plan['target_cases'], ['ER003', 'ER013'])
        self.assertEqual(self.plan['anomaly_observations'], 3)
        self.assertEqual(self.plan['control_cases'], ['ER007', 'ER016', 'ER001', 'ER010'])

    def test_repeat_not_new_case_and_retry_billed_once_per_attempt(self):
        rows = [self.row(provider='sol', repeat=i) for i in range(1, 4)]
        rows[0]['observation'] = diag.normalize(dict(status='UNAVAILABLE', reason='timeout',
            model=real.SOL_MODEL, reasoning_effort='high', elapsed_seconds=.1,
            usage=dict(input_tokens=10, output_tokens=2, total_tokens=12)), 'sol')
        retry = self.row(provider='sol'); retry['retry'] = 2; rows.append(retry)
        report = diag.summarize(self.plan, rows)
        self.assertEqual(report['unique_target_cases'], 2)
        self.assertEqual(report['cases']['ER003']['sol']['repeat_count'], 3)
        self.assertEqual(report['cases']['ER003']['sol']['usage']['total_tokens']['value'], 48)

    def test_duplicate_attempt_and_duplicate_slot_rejected(self):
        row = self.row()
        with self.assertRaises(ValueError): diag.summarize(self.plan, [row, row])
        with self.assertRaises(ValueError): diag.summarize(self.plan, [row, self.row()])

    def test_same_input_digest_and_target_control_identity(self):
        for key, value in [('payload_sha256', 'a'*64), ('group', 'control'), ('case_id', 'ER002')]:
            row = self.row(); row[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): diag.summarize(self.plan, [row])

    def test_oracle_leakage_rejected(self):
        payload = real.provider_payload(self.cases[2]); payload['expected_result'] = 'no_regression'
        with self.assertRaises(ValueError): diag.blind_prompt(payload)
        payload.pop('expected_result'); payload['evidence'] += ' expected_result=no_regression'
        with self.assertRaises(ValueError): diag.blind_prompt(payload)

    def test_low_confidence_never_pass_and_incomplete_is_unmeasured(self):
        report = diag.summarize(self.plan, [self.row()])
        self.assertEqual(report['verdict'], 'UNMEASURED')
        self.assertNotIn('PASS', json.dumps(report))

    def test_malformed_response_fail_closed_missing_probability_not_zero(self):
        value = dict(status='OK', model='jev-1.13.0', answer=dict(type='choice', choice='no_regression', confidence=.9))
        row = diag.observation(self.plan, 'ER003', 'jev', 1, 1, value)
        self.assertEqual(row['observation']['status'], 'UNAVAILABLE')
        self.assertIsNone(row['observation']['probabilities'])
        self.assertIsNone(diag.summarize(self.plan, [row])['cases']['ER003']['jev']['probability_margin']['mean'])

    def test_missing_usage_null_with_reason_coverage(self):
        metric = diag.summarize(self.plan, [self.row(usage=False)])['cases']['ER003']['jev']['usage']['total_tokens']
        self.assertIsNone(metric['value']); self.assertEqual(metric['coverage'], {'measured': 0, 'total': 1})
        self.assertTrue(metric['reason'])

    def test_unknown_preserved(self):
        stats = diag.summarize(self.plan, [self.row(provider='sol', choice='unknown')])['cases']['ER003']['sol']
        self.assertEqual(stats['unknown_count'], 1)
        self.assertEqual(stats['stable_binary_decision_count'], 0)

    def test_historical_source_is_preserved_while_active_replay_uses_high(self):
        import subprocess
        original = subprocess.check_output(['git', 'show', diag.BASE_SHA+':tools/workflow_eval/semantic_real.py'])
        self.assertIn(b"SOL_EFFORT = 'xhigh'", original)
        self.assertEqual(real.SOL_EFFORT, 'high')
        self.assertFalse(diag.summarize(self.plan, [])['official_results_modified'])

    def test_probability_margin_not_confidence_and_population_variance(self):
        rows = [self.row(repeat=1, confidence=.5), self.row(repeat=2, confidence=.7)]
        stats = diag.summarize(self.plan, rows)['cases']['ER003']['jev']
        self.assertAlmostEqual(stats['confidence']['standard_deviation'], .1)
        self.assertAlmostEqual(stats['probability_margin']['mean'], .97)

    def test_model_mismatch_retains_usage_but_excludes_choice(self):
        row = self.row(provider='sol'); row['observation']['model'] = 'wrong'
        with self.assertRaises(ValueError): diag.summarize(self.plan, [row])

    def test_nonfinite_confidence_and_raw_response_fields_rejected(self):
        row = self.row(); row['observation']['confidence'] = float('nan')
        with self.assertRaises(ValueError): diag.summarize(self.plan, [row])
        row = self.row(); row['raw_trace'] = 'secret'
        with self.assertRaises(ValueError): diag.summarize(self.plan, [row])

    def test_instability_cannot_disappear_in_partial_coverage(self):
        rows = [self.row(repeat=1), self.row(repeat=2, choice='regression')]
        self.assertEqual(diag.summarize(self.plan, rows)['verdict'], 'BLOCKED_INSTABILITY')

    def test_control_group_stability_is_within_case_not_mixed_label_frequency(self):
        rows = [self.row(case=k, choice='no_regression' if k in ('ER007', 'ER016') else 'regression')
                for k in diag.CONTROLS]
        stats = diag.summarize(self.plan, rows)['groups']['control']['jev']
        self.assertEqual(stats['choice_stability'], 1)
        self.assertEqual(stats['stable_binary_decision_count'], 4)

    def test_no_calls_means_null_decisions_not_zero(self):
        stats = diag.summarize(self.plan, [])['cases']['ER003']['sol']
        self.assertIsNone(stats['unknown_count']); self.assertIsNone(stats['choice_distribution'])

    def test_blind_execution_has_no_repo_or_oracle_and_keeps_usage(self):
        import subprocess
        answer = dict(category='mildly_ambiguous', rationale='The exclusion boundary is not explicit.')
        events = [dict(type='item.completed', item=dict(type='agent_message', text=json.dumps(answer))),
                  dict(type='turn.completed', usage=dict(input_tokens=20, output_tokens=8))]
        def runner(cmd, **kwargs):
            self.assertIn('--ignore-user-config', cmd); self.assertIn('--ephemeral', cmd)
            self.assertIn('gpt-6.1-sol', cmd); self.assertIn('model_reasoning_effort="high"', cmd)
            self.assertNotEqual(Path(cmd[cmd.index('-C')+1]), real.ROOT)
            for forbidden in ('ER003', 'expected_result', 'severity', '0.54', 'PR #19'):
                self.assertNotIn(forbidden, kwargs['input'])
            return subprocess.CompletedProcess(cmd, 0, '\n'.join(json.dumps(e) for e in events), '')
        review = diag.call_blind(real.provider_payload(self.cases[2]), runner=runner)
        self.assertEqual(review['status'], 'OK'); self.assertEqual(review['usage']['total_tokens'], 28)

    def test_blind_runtime_failure_not_ambiguity_and_timeout_usage_retained(self):
        import subprocess
        usage = json.dumps(dict(type='turn.completed', usage=dict(input_tokens=20, output_tokens=8)))
        def runner(*args, **kwargs): raise subprocess.TimeoutExpired('codex', 180, output=usage)
        review = diag.call_blind(real.provider_payload(self.cases[2]), runner=runner)
        self.assertEqual(review['status'], 'UNAVAILABLE'); self.assertIsNone(review['category'])
        self.assertEqual(review['reason'], 'timeout'); self.assertEqual(review['usage']['total_tokens'], 28)

    def test_history_hashes_not_modified_by_offline_aggregation(self):
        before = diag.history_snapshot('semantic-confidence-')
        diag.summarize(self.plan, [self.row()])
        self.assertEqual(before, diag.history_snapshot('semantic-confidence-'))

    def test_changed_protocol_rejected(self):
        plan = copy.deepcopy(self.plan); plan['jev_repeats'] = 3
        with self.assertRaises(ValueError): diag.summarize(plan, [])

    def test_wrong_model_response_is_unavailable_retains_billing(self):
        row = self.row(provider='sol'); obs = row['observation']
        value = dict(status='OK', model='gpt-6-sol', reasoning_effort='xhigh',
                     answer=dict(type='choice', choice=obs['choice'], confidence=obs['confidence'], probabilities=obs['probabilities']),
                     usage=obs['usage'], elapsed_seconds=.1)
        normalized = diag.normalize(value, 'sol')
        self.assertEqual(normalized['status'], 'UNAVAILABLE'); self.assertIsNone(normalized['choice'])
        self.assertEqual(normalized['usage']['total_tokens'], 12)

    def complete_rows(self):
        return [self.row(k, choice='no_regression' if k not in ('ER001', 'ER010') else 'regression', repeat=i)
                for k in diag.TARGETS+diag.CONTROLS for i in range(1, 6)] + [
                self.row(k, provider='sol', repeat=i) for k in diag.TARGETS for i in range(1, 4)]

    def blinds(self):
        return [dict(status='OK', category='materially_ambiguous', rationale='The exclusion boundary is absent.',
                reason=None, usage=dict(input_tokens=10, output_tokens=2, total_tokens=12), usage_reason=None,
                elapsed_seconds=.1, model=real.SOL_MODEL, reasoning_effort='high',
                prompt_sha256=real.fingerprint(diag.blind_prompt(real.provider_payload(next(c for c in self.cases if c['id']==k)))),
                input_scope='four_original_fields_only_no_repo_history_or_oracle', case_id=k, attempt_id=str(n)*32,
                retry=1, protocol_sha256=real.fingerprint(self.plan), payload_sha256=self.plan['payload_digests'][k])
                for n,k in enumerate(diag.TARGETS,1)]

    def test_audits_required_low_conf_escalation_and_billing_no_double_count(self):
        rows=self.complete_rows(); blind=self.blinds()
        audit={k:'PRIMARY_EVIDENCE_SUPPORTED' for k in diag.TARGETS}
        report=diag.finalize(self.plan,rows,blind,audit)
        self.assertEqual(report['verdict'],'SHADOW_CONTINUE_WITH_LOW_CONF_ESCALATION')
        self.assertEqual(report['combined_tokens']['value'],38*12)
        self.assertEqual(diag.finalize(self.plan,rows,[],audit)['verdict'],'UNMEASURED')

    def test_source_issue_blocks_and_blind_duplicates_stale_or_oracle_rejected(self):
        rows=self.complete_rows(); blind=self.blinds()
        audit={k:'GROUND_TRUTH_ISSUE_FOUND' for k in diag.TARGETS}
        self.assertEqual(diag.finalize(self.plan,rows,blind,audit)['verdict'],'BLOCKED_INSTABILITY')
        with self.assertRaises(ValueError): diag.finalize(self.plan,rows,blind+[blind[0]],{})
        for key,value in [('payload_sha256','a'*64),('model','gpt-6-sol'),('expected_result','no_regression')]:
            bad=copy.deepcopy(blind); bad[0][key]=value
            with self.subTest(key=key), self.assertRaises(ValueError): diag.finalize(self.plan,rows,bad,{})

    def test_known_binary_miss_blocks_even_if_stable(self):
        rows=[self.row(choice='regression',repeat=i) for i in range(1,6)]
        report=diag.summarize(self.plan,rows)
        self.assertEqual(report['binary_oracle_mismatch_observations'],5)
        self.assertEqual(report['verdict'],'BLOCKED_INSTABILITY')

    def test_orphan_retry_and_retry_after_success_rejected(self):
        row=self.row(provider='sol'); row['retry']=2
        with self.assertRaises(ValueError): diag.summarize(self.plan,[row])
        with self.assertRaises(ValueError): diag.summarize(self.plan,[self.row(provider='sol'),row])

    def test_harness_failure_blocks_experiment_not_success(self):
        row=self.row(); row['observation']=diag.normalize(dict(status='UNAVAILABLE',reason='invalid_response'),'jev')
        self.assertEqual(diag.summarize(self.plan,[row])['verdict'],'BLOCKED_INSTABILITY')

    def test_blind_usage_reason_allowlist_rejects_injected_metadata(self):
        blind=self.blinds(); blind[0]['usage_reason']='not_a_valid_usage_reason'
        with self.assertRaises(ValueError): diag.finalize(self.plan,self.complete_rows(),blind,{})

    def test_malformed_event_retains_known_billing_then_fails_closed(self):
        import subprocess
        events=[[],dict(type='turn.completed',usage=dict(input_tokens=20,output_tokens=8)),
                dict(type='item.completed',item=dict(type='agent_message',text=json.dumps(
                    dict(category='clearly_decidable',rationale='No ambiguity.'))))]
        def runner(cmd,**kwargs): return subprocess.CompletedProcess(cmd,0,'\n'.join(json.dumps(e) for e in events),'')
        review=diag.call_blind(real.provider_payload(self.cases[2]),runner=runner)
        self.assertEqual(review['status'],'UNAVAILABLE')
        self.assertEqual(review['usage']['total_tokens'],28)

    def test_model_mismatch_row_roundtrip_preserves_billing_and_blocks(self):
        row=diag.observation(self.plan,'ER003','sol',1,1,dict(status='OK',model='gpt-6-sol',
            reasoning_effort='xhigh',answer=dict(type='choice',choice='no_regression',confidence=.95,
            probabilities=dict(regression=.01,no_regression=.98,unknown=.01)),
            usage=dict(input_tokens=20,output_tokens=8,total_tokens=28),elapsed_seconds=.1))
        report=diag.summarize(self.plan,[row])
        self.assertEqual(report['verdict'],'BLOCKED_INSTABILITY')
        self.assertEqual(report['cases']['ER003']['sol']['usage']['total_tokens']['value'],28)
        self.assertEqual(report['cases']['ER003']['sol']['valid_repeat_count'],0)


if __name__ == '__main__': unittest.main()
