"""Prospective cohort contracts; entirely fictional records, no provider calls."""
import copy
import importlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class RealTaskTests(unittest.TestCase):
    def module(self, name):
        try:
            return importlib.import_module('tools.workflow_eval.' + name)
        except ModuleNotFoundError:
            self.fail('real task measurement implementation is missing')

    def record(self, pr=11):
        review = dict(status='OK', model='gpt-6-sol', reasoning_effort='xhigh',
                      usage=dict(input_tokens=100, output_tokens=10), elapsed_seconds=2,
                      judgment=dict(verdict='needs_changes', findings=[], missing_context_ids=[]),
                      observed_completed_turns=1)
        return dict(schema_version=1, repository='owner/EA', request_id='pr:'+str(pr),
                    origin='prospective', kind='ea_review', head='a'*40, base='b'*40,
                    started_at='2026-09-28T00:00:00+00:00', completed_at='2026-09-28T00:05:00+00:00',
                    mandatory=True, a=copy.deepcopy(review), b=copy.deepcopy(review),
                    jev=dict(status='NOT_RUN', attempts=0, usage=None, elapsed_seconds=0),
                    shadow_route='review', context_reacquisitions=0, missing_context_items=0,
                    rework_count=None, test_failed_runs=None,
                    audit=dict(status='PENDING', false_negatives=None, critical_misses=None,
                               a_false_negatives=None,b_false_negatives=None,a_critical_misses=None,b_critical_misses=None),
                    task_total_usage=None, task_elapsed_seconds=None)

    def test_duplicate_pr_cannot_inflate_sample_count(self):
        m = self.module('real_tasks')
        row = self.record()
        with self.assertRaises(ValueError): m.summarize([row, dict(row, head='c'*40)])

    def test_fixture_and_retrospective_records_do_not_count_toward_real_target(self):
        rows = [self.record(), dict(self.record(12), origin='synthetic'), dict(self.record(13), origin='retrospective')]
        got = self.module('real_tasks').summarize(rows)
        self.assertEqual(got['real_samples'], 1)
        self.assertEqual(got['target_minimum'], 30)
        self.assertEqual(got['target_goal'], 50)
        self.assertFalse(got['quality_certified'])

    def test_pending_audit_and_rework_are_unknown_not_zero(self):
        got = self.module('real_tasks').summarize([self.record()])
        for key in ['false_negatives', 'critical_misses', 'rework_count', 'quality_preserving_reduction_percent']:
            self.assertIsNone(got[key])
        self.assertEqual(got['audit_complete_samples'], 0)
        self.assertFalse(got['review_skip_enabled'])

    def test_critical_miss_blocks_even_with_failed_partner(self):
        row = self.record(); row['b']['status'] = 'UNAVAILABLE'
        row['audit'] = dict(status='CHECKED', false_negatives=1, critical_misses=1,
                            a_false_negatives=1,b_false_negatives=0,a_critical_misses=1,b_critical_misses=0)
        got = self.module('real_tasks').summarize([row])
        self.assertEqual(got['decision'], 'BLOCKED_CRITICAL_MISS')
        self.assertEqual(got['observed_critical_misses'], 1)

    def test_below_floor_provenance_is_rejected(self):
        row = self.record(); row['b']['reasoning_effort'] = 'high'
        with self.assertRaises(ValueError): self.module('real_tasks').validate_record(row)

    def test_unknown_fields_and_credentials_are_not_logged(self):
        for update in [dict(raw_prompt='source'), dict(repository='token=fictional-secret-value')]:
            with self.assertRaises(ValueError): self.module('real_tasks').validate_record(dict(self.record(), **update))

    def test_audit_update_keeps_identity_and_cannot_clear_critical_history(self):
        m = self.module('real_tasks'); original = self.record()
        checked = copy.deepcopy(original); checked['audit']=dict(status='CHECKED', false_negatives=1, critical_misses=1,
            a_false_negatives=1,b_false_negatives=0,a_critical_misses=1,b_critical_misses=0)
        self.assertEqual(m.update_record(original, checked)['audit']['critical_misses'], 1)
        cleared = copy.deepcopy(checked); cleared['audit']['critical_misses']=0
        with self.assertRaises(ValueError): m.update_record(checked, cleared)
        moved = dict(checked, head='c'*40)
        with self.assertRaises(ValueError): m.update_record(original, moved)

    def test_ea_kind_cannot_bypass_floor_using_false_mandatory_flag(self):
        row=self.record();row.update(mandatory=False,shadow_route='candidate')
        for arm in ('a','b'):row[arm]['reasoning_effort']='high'
        with self.assertRaisesRegex(ValueError,'intrinsic_ea_floor'):self.module('real_tasks').validate_record(row)

    def test_nested_usage_and_provenance_do_not_accept_raw_content(self):
        for field,value in [('usage',dict(input_tokens=100,output_tokens=10,raw_prompt='fictional source')),
                            ('usage_fields',['raw_prompt']),('observed_completed_turns','raw text'),
                            ('evidence_sha256','raw text')]:
            row=self.record();row['a'][field]=value
            with self.assertRaisesRegex(ValueError,'invalid_usage_schema|invalid_provenance'):self.module('real_tasks').validate_record(row)

    def test_invalid_pair_cannot_erase_measured_provider_usage(self):
        row=self.record();row['a']['status']='UNAVAILABLE'
        row['jev']=dict(status='UNAVAILABLE',attempts=1,usage=dict(input_tokens=20,output_tokens=10),elapsed_seconds=1)
        got=self.module('real_tasks').summarize([row])
        self.assertEqual(got['jev_total_tokens'],30)
        self.assertEqual(got['b_all_provider_total_tokens'],140)
        self.assertEqual(got['valid_review_pairs'],0)

    def test_partial_reviews_keep_known_usage_and_unknown_attempts_separate(self):
        row=self.record();row['b'].update(status='UNAVAILABLE',usage=None,judgment=None)
        got=self.module('real_tasks').summarize([row])
        self.assertEqual(got['observed_gpt6_usage_subtotals']['a']['total_tokens'],110)
        self.assertEqual(got['gpt6_usage_missing_attempts'],dict(a=0,b=1))
        self.assertEqual(got['review_attempts'],dict(a=1,b=1))
        self.assertIsNone(got['observed_gpt6_usage_totals']['b']['total_tokens'])
        self.assertIsNone(got['paired_review_reduction_percent']['total_tokens'])

    def test_failed_partner_does_not_count_as_paired_audit(self):
        row=self.record();row['b'].update(status='UNAVAILABLE',usage=None,judgment=None)
        row['audit']=dict(status='CHECKED',false_negatives=1,critical_misses=1,
            a_false_negatives=1,b_false_negatives=0,a_critical_misses=1,b_critical_misses=0)
        got=self.module('real_tasks').summarize([row])
        self.assertEqual(got['audit_complete_samples'],1)
        self.assertEqual(got['paired_audit_complete_samples'],0)

    def test_missing_attempt_count_and_contradictory_success_are_rejected(self):
        row=self.record();row['jev'].update(status='UNAVAILABLE',attempts=3)
        self.assertEqual(self.module('real_tasks').summarize([row])['jev_usage_missing_attempts'],3)
        row=self.record();row['a']['judgment']=None
        with self.assertRaises(ValueError):self.module('real_tasks').validate_record(row)
        row=self.record();row['jev'].update(status='OK',usage=dict(input_tokens=1,output_tokens=1))
        with self.assertRaises(ValueError):self.module('real_tasks').validate_record(row)

    def test_arm_specific_audits_preserve_context_quality_comparison(self):
        row=self.record();row['audit']=dict(status='CHECKED',false_negatives=2,critical_misses=1,
            a_false_negatives=0,b_false_negatives=2,a_critical_misses=0,b_critical_misses=1)
        got=self.module('real_tasks').summarize([row])
        self.assertEqual(got['a_false_negatives'],0)
        self.assertEqual(got['b_false_negatives'],2)
        self.assertEqual(got['paired_audit_complete_samples'],1)

    def test_failed_review_time_is_retained_in_observations(self):
        row=self.record();row['a'].update(status='UNAVAILABLE',elapsed_seconds=300)
        got=self.module('real_tasks').summarize([row])
        self.assertEqual(got['observed_review_seconds'],dict(a=300,b=2))
        self.assertEqual(got['b_including_jev_seconds'],2)

    def test_sparse_legacy_usage_and_missing_jev_time_are_not_zero(self):
        row=dict(id='x',truth='review',severity='critical',a=copy.deepcopy(self.record()['a']),
                 b=copy.deepcopy(self.record()['b']),jev=dict(status='UNAVAILABLE',attempts=1,
                     usage=dict(input_tokens=20,output_tokens=10)))
        for arm in ('a','b'):row[arm]['route']='review'
        got=self.module('report').summarize([row])
        self.assertEqual(got['jev_total_tokens'],30)
        self.assertEqual(got['b_all_provider_total_tokens'],140)
        self.assertIsNone(got['b_including_jev_seconds'])

    def test_explicit_critical_fixture_ignores_low_risk_facts(self):
        from unittest.mock import patch
        m=self.module('benchmark');facts=dict(paths=['docs/dev-note.md'],dependency='known',module_count=1,
            tests='PASS',changed_lines=1,missing_context=[],sensitive=False,scope_ok=True,current=True,protected=False)
        case=dict(id='c',split='holdout',truth='review',severity='critical',task='Developer note.',facts=facts,
            context_blocks=[dict(id='a',text='Sentence.')],selected_context_ids=['a'],required_context_ids=['a'])
        with patch.object(m,'sol_review',return_value={}) as call:
            got=m.run_case(case,0)
        self.assertTrue(all(c.args[2]=='xhigh' for c in call.call_args_list))
        self.assertEqual(got['shadow']['shadow_route'],'review')

    def test_missing_attempted_jev_usage_keeps_complete_total_unknown(self):
        row = self.record(); row['jev'].update(status='UNAVAILABLE', attempts=1)
        got = self.module('real_tasks').summarize([row])
        self.assertIsNone(got['jev_total_tokens'])
        self.assertIsNone(got['b_all_provider_total_tokens'])

    def test_review_parser_retains_usage_provenance_and_rejects_tools(self):
        m = self.module('real_tasks')
        events = [dict(type='item.completed', item=dict(type='agent_message', text=json.dumps(
            dict(verdict='unknown', findings=[], missing_context_ids=['interface'])))),
                  dict(type='turn.completed', usage=dict(input_tokens=100, output_tokens=20))]
        got = m.parse_review(events)
        self.assertEqual(got['usage']['total_tokens'], 120)
        self.assertIsNone(got['reported_reasoning_output_tokens'])
        self.assertEqual(got['judgment']['missing_context_ids'], ['interface'])
        events.insert(0, dict(type='item.completed', item=dict(type='command_execution')))
        self.assertEqual(m.parse_review(events)['status'], 'UNKNOWN')

    def test_structured_review_output_can_represent_critical_findings(self):
        m=self.module('real_tasks')
        path=Path(m.__file__).with_name('review-schema.json')
        self.assertTrue(path.is_file(),'structured review schema is missing')
        schema=json.loads(path.read_text())
        self.assertIn('critical',schema['properties']['findings']['items']['properties']['severity']['enum'])
        events=[dict(type='item.completed',item=dict(type='agent_message',text=json.dumps(dict(verdict='needs_changes',
            findings=[dict(severity='critical',code='LOSS_LIMIT',evidence_id='src/example.mqh:1',reason='Loss limit omitted.')],
            missing_context_ids=[])))),dict(type='turn.completed',usage=dict(input_tokens=1,output_tokens=10))]
        self.assertEqual(m.parse_review(events)['judgment']['findings'][0]['severity'],'critical')

    def test_decomposition_reconciles_input_output_and_jev(self):
        row = dict(id='h', a=dict(usage=dict(input_tokens=1000, output_tokens=100), reasoning_effort='high'),
                   b=dict(usage=dict(input_tokens=900, output_tokens=120), reasoning_effort='high'),
                   jev=dict(status='OK', usage=dict(input_tokens=20, output_tokens=10), answer=dict(choice='candidate', confidence=.89)),
                   shadow=dict(shadow_route='review', mandatory_reasons=[]))
        got = self.module('analysis').decompose([row])
        self.assertEqual(got['input_tokens_removed'], 100)
        self.assertEqual(got['extra_output_tokens'], 20)
        self.assertEqual(got['jev_tokens_added'], 30)
        self.assertEqual(got['net_tokens_removed'], 50)
        self.assertEqual(got['routing']['low_confidence_candidates'], 1)


if __name__ == '__main__':
    unittest.main()
