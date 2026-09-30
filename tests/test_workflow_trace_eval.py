"""Offline safety and accounting checks for trace shadow experiments."""

import copy
import json
from pathlib import Path
import unittest
from types import SimpleNamespace

from tools.workflow_eval import trace_eval as m


FIXTURE = Path(__file__).parent / 'fixtures' / 'workflow_trace_cases.json'


class TraceEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = json.loads(FIXTURE.read_text(encoding='utf-8'))['cases']

    def observations(self, case=None):
        case = copy.deepcopy(case or self.cases[0])
        fingerprint = m.case_fingerprint(case)
        expected = [s['id'] for s in case['segments'] if s['expected_label'] in m.ATTENTION_LABELS]
        effort = 'xhigh' if case['protected'] or case['dependency'] == 'unknown' or case['critical_segment_ids'] else 'high'
        review = dict(status='OK', task_id=case['task_id'], base_sha=case['base_sha'],
                      case_fingerprint=fingerprint, model='gpt-6-sol', reasoning_effort=effort,
                      usage=dict(input_tokens=100, output_tokens=20, total_tokens=120),
                      elapsed_seconds=2.0, detected_segment_ids=expected,
                      input_segment_ids=[s['id'] for s in case['segments']],
                      additional_context_retrieval_count=0, rework_count=0, test_failed_runs=0)
        jev = dict(status='OK', case_fingerprint=fingerprint,
                   labels=[dict(segment_id=s['id'], label=s['expected_label'], confidence=.95,
                                evidence_segment_ids=[s['id']]) for s in case['segments']],
                   usage=dict(input_tokens=10, output_tokens=2, total_tokens=12), elapsed_seconds=.2)
        b = copy.deepcopy(review)
        b['input_segment_ids'] = [s['id'] for s in case['segments'] if s['expected_label'] != 'repetition']
        return case, copy.deepcopy(review), b, jev

    def test_fixture_is_safe_distinct_and_covers_all_labels(self):
        self.assertEqual(len(self.cases), 10)
        self.assertEqual(len({c['task_id'] for c in self.cases}), 10)
        self.assertEqual({s['expected_label'] for c in self.cases for s in c['segments']}, m.LABELS)
        for case in self.cases:
            self.assertEqual(len(m.case_fingerprint(case)), 64)

    def test_metadata_only_result_never_serializes_trace_text(self):
        case, a, b, jev = self.observations()
        case['segments'][0]['text'] = 'Unique harmless synthetic phrase alpha.'
        fingerprint = m.case_fingerprint(case)
        for value in (a, b, jev):
            value['case_fingerprint'] = fingerprint
            value['raw_trace'] = 'Unique harmless synthetic phrase alpha.'
        row = m.run_trace_case(case, a, b, jev)
        self.assertNotIn('Unique harmless synthetic phrase alpha.', json.dumps(row))
        self.assertTrue(row['comparable'])
        self.assertFalse(row['review_skip_enabled'])

    def test_malformed_jev_response_fails_closed(self):
        case, a, b, jev = self.observations()
        for broken in (None, {}, dict(jev, labels=[]), dict(jev, labels=[dict(segment_id='s1', label='invented', confidence=.9, evidence_segment_ids=['s1'])])):
            with self.subTest(broken=broken):
                row = m.run_trace_case(case, a, b, broken)
                self.assertFalse(row['comparable'])
                self.assertEqual(row['jev']['status'], 'INVALID')

    def test_confidence_must_be_finite_probability(self):
        case, a, b, jev = self.observations()
        for confidence in (-.01, 1.01, float('nan'), float('inf'), True):
            broken = copy.deepcopy(jev)
            broken['labels'][0]['confidence'] = confidence
            self.assertEqual(m.run_trace_case(case, a, b, broken)['jev']['status'], 'INVALID')

    def test_missing_usage_is_null_with_reason_and_coverage(self):
        case, a, b, jev = self.observations()
        b['usage'] = None; jev['usage'] = None
        row = m.run_trace_case(case, a, b, jev)
        report = m.summarize_trace([row])
        self.assertTrue(row['comparable'])
        self.assertIsNone(report['token']['sol']['b']['total_tokens'])
        self.assertIsNone(report['token']['jev_total_tokens'])
        self.assertIsNone(report['token']['b_combined_total_tokens'])
        self.assertEqual({x['source'] for x in report['coverage']['missing_usage']}, {'b', 'jev'})
        self.assertEqual(row['jev']['usage_missing_reason'], 'missing_usage')

    def test_timeout_and_unavailable_never_compare(self):
        case, a, b, jev = self.observations()
        jev['status'] = 'TIMEOUT'
        self.assertFalse(m.run_trace_case(case, a, b, jev)['comparable'])
        jev['status'] = 'OK'; b['status'] = 'UNAVAILABLE'
        self.assertFalse(m.run_trace_case(case, a, b, jev)['comparable'])

    def test_mismatched_model_effort_or_base_excluded(self):
        case, a, b, jev = self.observations()
        for change in (dict(model='gpt-6-luna'), dict(reasoning_effort='xhigh'), dict(base_sha='other')):
            altered = dict(b, **change)
            row = m.run_trace_case(case, a, altered, jev)
            self.assertFalse(row['comparable'])
            self.assertEqual(m.summarize_trace([row])['comparable_pairs'], 0)

    def test_critical_cases_require_sol_xhigh(self):
        case, a, b, jev = self.observations(self.cases[4])
        a['reasoning_effort'] = b['reasoning_effort'] = 'high'
        self.assertFalse(m.run_trace_case(case, a, b, jev)['comparable'])
        a['reasoning_effort'] = b['reasoning_effort'] = 'xhigh'
        self.assertTrue(m.run_trace_case(case, a, b, jev)['comparable'])

    def test_critical_miss_survives_pair_exclusion(self):
        case, a, b, jev = self.observations(self.cases[4])
        b['detected_segment_ids'] = []
        a['reasoning_effort'] = 'high'
        row = m.run_trace_case(case, a, b, jev)
        report = m.summarize_trace([row])
        self.assertEqual(report['comparable_pairs'], 0)
        self.assertEqual(report['decision'], 'BLOCKED_CRITICAL_MISS')
        self.assertEqual(len(report['quality']['critical_misses']), 1)

    def test_jev_critical_miss_blocks_even_with_sol_success(self):
        case, a, b, jev = self.observations(self.cases[4])
        jev['labels'][1]['label'] = 'progress'
        report = m.summarize_trace([m.run_trace_case(case, a, b, jev)])
        self.assertEqual(report['decision'], 'BLOCKED_CRITICAL_MISS')
        self.assertEqual(report['quality']['focus_labels']['blocked']['missed'], 1)

    def test_duplicate_task_is_not_extra_pilot_case(self):
        row = m.run_trace_case(*self.observations())
        report = m.summarize_trace([row, copy.deepcopy(row)])
        self.assertEqual(report['tasks'], 1)
        self.assertEqual(report['duplicate_tasks_excluded'], 1)
        self.assertEqual(report['comparable_pairs'], 1)

    def test_dataset_denominator_exposes_missing_tasks(self):
        row = m.run_trace_case(*self.observations(self.cases[0]))
        expected = [self.cases[0]['task_id'], self.cases[1]['task_id']]
        report = m.summarize_trace([row, copy.deepcopy(row)], expected_task_ids=expected)
        self.assertEqual(report['tasks'], 1)
        self.assertEqual(report['duplicate_tasks_excluded'], 1)
        self.assertEqual(report['coverage']['expected_task_ids'], sorted(expected))
        self.assertEqual(report['coverage']['observed_task_ids'], [expected[0]])
        self.assertEqual(report['coverage']['missing_task_ids'], [expected[1]])
        self.assertEqual(report['coverage']['unmeasured_task_ids'], [expected[1]])
        self.assertEqual(report['coverage']['comparable_task_coverage'], .5)
        self.assertEqual(report['coverage']['jev_label_denominator'], 2)
        self.assertEqual(report['coverage']['jev_label_coverage'], .5)
        self.assertEqual(report['decision'], 'INCOMPLETE_PILOT')

    def test_full_dataset_stays_shadow_only_and_unknown_denominator_is_incomplete(self):
        row = m.run_trace_case(*self.observations(self.cases[0]))
        complete = m.summarize_trace([row], expected_task_ids=[row['task_id']])
        self.assertEqual(complete['coverage']['missing_task_ids'], [])
        self.assertEqual(complete['decision'], 'SHADOW_ONLY_INSUFFICIENT_FOR_ADOPTION')
        unknown = m.summarize_trace([row])
        self.assertIsNone(unknown['coverage']['expected_task_ids'])
        self.assertIsNone(unknown['coverage']['missing_task_ids'])
        self.assertIsNone(unknown['coverage']['jev_label_denominator'])
        self.assertEqual(unknown['coverage']['dataset_denominator_reason'], 'expected_task_ids_not_provided')
        self.assertEqual(unknown['decision'], 'INCOMPLETE_PILOT')

    def test_unmeasured_expected_task_and_unexpected_row_fail_closed(self):
        case, a, b, jev = self.observations(self.cases[0])
        b['status'] = 'UNAVAILABLE'
        row = m.run_trace_case(case, a, b, jev)
        report = m.summarize_trace([row], expected_task_ids=[case['task_id']])
        self.assertEqual(report['coverage']['missing_task_ids'], [])
        self.assertEqual(report['coverage']['unmeasured_task_ids'], [case['task_id']])
        self.assertEqual(report['decision'], 'INCOMPLETE_PILOT')
        with self.assertRaises(ValueError):
            m.summarize_trace([row], expected_task_ids=['other-task'])
        with self.assertRaises(ValueError):
            m.summarize_trace([row], expected_task_ids=[case['task_id'], case['task_id']])

    def test_offline_quality_counts_are_null_with_reason_and_coverage(self):
        case = self.cases[0]
        row = m.run_trace_case(case, {'status': 'NOT_RUN'}, {'status': 'NOT_RUN'},
                               {'status': 'NOT_RUN'})
        report = m.summarize_trace([row], expected_task_ids=[case['task_id']])
        quality = report['quality']
        self.assertIsNone(quality['label_accuracy'])
        self.assertIsNone(quality['false_positive'])
        self.assertIsNone(quality['false_negative'])
        for label in m.FOCUS_LABELS:
            self.assertEqual(quality['focus_labels'][label],
                             dict(expected=None, detected=None, missed=None))
        for arm in ('a', 'b'):
            self.assertTrue(all(value is None for value in quality['paired_sol'][arm].values()))
        self.assertEqual(quality['measurement_reasons']['jev_labels'], 'no_jev_label_observations')
        self.assertEqual(quality['measurement_reasons']['paired_sol'], 'no_comparable_sol_pairs')
        self.assertEqual(report['coverage']['jev_labeled_segments'], 0)
        self.assertEqual(report['coverage']['paired_sol_quality_cases'], 0)
        self.assertEqual(report['coverage']['safety_miss_audit']['jev_observed_tasks'], 0)
        self.assertEqual(report['quality']['critical_misses'], [])
        self.assertEqual(report['decision'], 'INCOMPLETE_PILOT')

    def test_rerun_safety_misses_survive_deduplication(self):
        case, a, b, jev = self.observations(self.cases[9])
        first = m.run_trace_case(case, a, b, jev)
        a['detected_segment_ids'] = []
        b['detected_segment_ids'] = []
        jev['labels'][1]['label'] = 'progress'  # important context miss
        jev['labels'][2]['label'] = 'progress'  # critical blocked miss
        rerun = m.run_trace_case(case, a, b, jev)
        report = m.summarize_trace([first, rerun, copy.deepcopy(rerun)],
                                   expected_task_ids=[case['task_id'], self.cases[0]['task_id']])
        self.assertEqual(report['tasks'], 1)
        self.assertEqual(report['duplicate_tasks_excluded'], 2)
        self.assertEqual(report['comparable_pairs'], 1)
        self.assertEqual(report['quality']['a_critical_misses'], 1)
        self.assertEqual(report['quality']['b_critical_misses'], 1)
        self.assertEqual(len(report['quality']['critical_misses']), 2)
        self.assertEqual(len(report['quality']['important_misses']), 2)
        self.assertEqual(len(report['quality']['jev_critical_misses']), 1)
        self.assertEqual(len(report['quality']['jev_important_misses']), 1)
        self.assertEqual(report['coverage']['missing_task_ids'], [self.cases[0]['task_id']])
        self.assertEqual(report['decision'], 'BLOCKED_CRITICAL_MISS')

    def test_paired_sol_quality_separately_tracks_false_results(self):
        case, a, b, jev = self.observations(self.cases[1])
        b['detected_segment_ids'] = ['s1']
        report = m.summarize_trace([m.run_trace_case(case, a, b, jev)])
        self.assertEqual(report['quality']['paired_sol']['a']['task_success'], 1)
        self.assertEqual(report['quality']['paired_sol']['b']['task_success'], 0)
        self.assertEqual(report['quality']['paired_sol']['b']['false_positive'], 1)
        self.assertEqual(report['quality']['paired_sol']['b']['false_negative'], 1)

    def test_stale_results_are_invalid(self):
        case, a, b, jev = self.observations()
        case['segments'][0]['text'] = 'Changed safe synthetic text.'
        row = m.run_trace_case(case, a, b, jev)
        self.assertFalse(row['comparable'])
        self.assertEqual(row['a']['reason'], 'stale_or_mismatched_case')
        self.assertEqual(row['jev']['reason'], 'stale_jev_result')

    def test_secret_like_trace_is_rejected(self):
        case = copy.deepcopy(self.cases[0])
        case['segments'][0]['text'] = 'password=fictional-secret-value'
        with self.assertRaises(ValueError):
            m.case_fingerprint(case)

    def test_live_gate_and_injected_selection(self):
        case, a, b, jev = self.observations(self.cases[2])
        calls = []
        def reviewer(case_arg, segments, effort):
            calls.append([s['id'] for s in segments])
            return copy.deepcopy(a if len(calls) == 1 else b)
        def classifier(case_arg):
            return jev
        with self.assertRaisesRegex(ValueError, 'explicit_flag'):
            m.execute_trace_case(case, reviewer, classifier)
        with self.assertRaisesRegex(ValueError, 'stale_trace_base_sha'):
            m.execute_trace_case(case, reviewer, classifier, live=True, current_base_sha='0'*40)
        self.assertEqual(calls, [])
        row = m.execute_trace_case(case, reviewer, classifier, live=True, current_base_sha=case['base_sha'])
        self.assertTrue(row['comparable'])
        self.assertEqual(calls, [['s1', 's2'], ['s1']])

    def test_low_confidence_or_priority_repetition_is_still_sent_to_sol(self):
        case, a, b, jev = self.observations(self.cases[9])
        jev['labels'][1]['label'] = 'repetition'  # important, even at high confidence
        jev['labels'][2]['label'] = 'repetition'  # critical and low confidence
        jev['labels'][2]['confidence'] = .01
        calls = []
        def reviewer(case_arg, segments, effort):
            calls.append([s['id'] for s in segments])
            return copy.deepcopy(a if len(calls) == 1 else b)
        row = m.execute_trace_case(case, reviewer, lambda *_: jev, live=True,
                                   current_base_sha=case['base_sha'])
        self.assertEqual(calls, [['s1', 's2', 's3'], ['s1', 's2', 's3']])
        self.assertTrue(row['comparable'])

    def test_imported_model_and_effort_text_never_serialized(self):
        case, a, b, jev = self.observations(self.cases[9])
        a['model'] = 'password=fictional-secret-value'
        b['reasoning_effort'] = 'token=fictional-secret-value'
        b['detected_segment_ids'] = []
        row = m.run_trace_case(case, a, b, jev)
        serialized = json.dumps(row)
        self.assertNotIn('fictional-secret-value', serialized)
        self.assertEqual(row['a']['status'], 'INVALID')
        self.assertEqual(row['b']['status'], 'INVALID')
        self.assertFalse(row['comparable'])
        self.assertEqual(m.summarize_trace([row])['decision'], 'BLOCKED_CRITICAL_MISS')

    def test_classifier_failure_does_not_run_b(self):
        case, a, b, jev = self.observations()
        calls = []
        def reviewer(*args):
            calls.append(True); return a
        def classifier(*args):
            raise TimeoutError()
        row = m.execute_trace_case(case, reviewer, classifier, live=True, current_base_sha=case['base_sha'])
        self.assertEqual(len(calls), 1)
        self.assertEqual(row['jev']['status'], 'UNAVAILABLE')
        self.assertFalse(row['comparable'])

    def test_sol_adapter_accepts_only_one_valid_read_only_answer(self):
        case = self.cases[0]
        event_text = '\n'.join([
            json.dumps(dict(type='item.completed', item=dict(type='agent_message',
                         text=json.dumps(dict(detected_segment_ids=[]))))),
            json.dumps(dict(type='turn.completed', usage=dict(input_tokens=10, output_tokens=2))),
        ])
        seen = []
        def runner(cmd, **kwargs):
            seen.append((cmd, kwargs))
            return SimpleNamespace(returncode=0, stdout=event_text)
        result = m.trace_sol_review(case, case['segments'], 'high', runner=runner)
        self.assertEqual(result['status'], 'OK')
        self.assertEqual(result['usage']['total_tokens'], 12)
        self.assertIn('--sandbox', seen[0][0])
        self.assertIn('read-only', seen[0][0])
        self.assertNotIn(case['segments'][0]['text'], json.dumps(result))

    def test_sol_adapter_nonzero_and_missing_usage(self):
        case = self.cases[0]
        failure = m.trace_sol_review(case, case['segments'], 'high',
                                     runner=lambda *a, **k: SimpleNamespace(returncode=7, stdout=''))
        self.assertEqual(failure['status'], 'UNAVAILABLE')
        self.assertEqual(failure['reason'], 'sol_nonzero_exit')
        event_text = '\n'.join([
            json.dumps(dict(type='item.completed', item=dict(type='agent_message',
                         text=json.dumps(dict(detected_segment_ids=[]))))),
            json.dumps(dict(type='turn.completed', usage=None)),
        ])
        result = m.trace_sol_review(case, case['segments'], 'high',
                                    runner=lambda *a, **k: SimpleNamespace(returncode=0, stdout=event_text))
        self.assertEqual(result['status'], 'OK')
        self.assertIsNone(result['usage'])
        self.assertEqual(result['usage_missing_reason'], 'missing_usage')

    def test_sol_adapter_rejects_tool_use_or_out_of_scope_segment(self):
        case = self.cases[0]
        for events in [
            [dict(type='item.completed', item=dict(type='command_execution')),
             dict(type='item.completed', item=dict(type='agent_message', text='{"detected_segment_ids":[]}')),
             dict(type='turn.completed', usage=dict(input_tokens=1, output_tokens=1))],
            [dict(type='item.completed', item=dict(type='agent_message', text='{"detected_segment_ids":["other"]}')),
             dict(type='turn.completed', usage=dict(input_tokens=1, output_tokens=1))],
        ]:
            text = '\n'.join(json.dumps(event) for event in events)
            result = m.trace_sol_review(case, case['segments'], 'high',
                                        runner=lambda *a, **k: SimpleNamespace(returncode=0, stdout=text))
            self.assertEqual(result['status'], 'UNAVAILABLE')

    def test_jev_adapter_requires_live_flag_and_sanitizes_provider_failure(self):
        case = self.cases[0]
        called = []
        def opener(*args, **kwargs):
            called.append(True)
            raise TimeoutError('synthetic private diagnostic')
        offline = m.call_trace_jev(case, key='fictional-key', opener=opener)
        self.assertEqual(offline['status'], 'NOT_RUN')
        self.assertEqual(called, [])
        live = m.call_trace_jev(case, live=True, key='fictional-key', opener=opener)
        self.assertEqual(live['status'], 'UNAVAILABLE')
        self.assertNotIn('synthetic private diagnostic', json.dumps(live))

    def test_jev_adapter_parses_typed_labels_without_raw_response(self):
        case = self.cases[0]
        answers = {}
        for i, segment in enumerate(case['segments']):
            label = segment['expected_label']
            answers[f'segment_{i}'] = dict(type='choice', choice=label, confidence=1,
                                           probabilities={key: int(key == label) for key in m.LABELS})
        payload = json.dumps(dict(model='jev-test', usage=dict(input_tokens=6, output_tokens=2),
                                  answers=answers)).encode()
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def read(self, limit): return payload
        result = m.call_trace_jev(case, live=True, key='fictional-key', opener=lambda *a, **k: Response())
        self.assertEqual(result['status'], 'OK')
        self.assertEqual(result['usage']['total_tokens'], 8)
        self.assertNotIn(case['segments'][0]['text'], json.dumps(result))


if __name__ == '__main__':
    unittest.main()
