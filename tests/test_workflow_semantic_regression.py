"""Offline contracts for shadow semantic regression evaluation."""
import copy
import io
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.workflow_eval import semantic_regression as semantic


FIXTURE = Path(__file__).parent / 'fixtures' / 'workflow_semantic_regression_cases.json'
BASE = 'a' * 40
DATASET = 'b' * 64
USAGE = dict(input_tokens=12, output_tokens=3, total_tokens=15)


def answer(choice='regression', confidence=.95):
    scores = {name: .025 for name in semantic.CHOICES}
    scores[choice] = .95
    return dict(type='choice', choice=choice, confidence=confidence, probabilities=scores)


def observation(choice='regression', usage=None):
    return dict(status='OK', answer=answer(choice), usage=USAGE if usage is None else usage,
                elapsed_seconds=.5)


class SemanticRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases, cls.sha = semantic.load_cases(FIXTURE)

    def run_one(self, case=None, sol=None, jev=None):
        def with_identity(fn, model, effort=None):
            if fn is None: return None
            def measured(c):
                result = fn(c)
                if isinstance(result, dict) and result.get('status') == 'OK':
                    result = dict(result)
                    result.setdefault('model', model)
                    if effort: result.setdefault('reasoning_effort', effort)
                return result
            return measured
        selected = case or self.cases[0]
        effort = 'xhigh' if selected['severity'] == 'critical' or selected['mutation'] == 'protected_as_candidate' or selected['dependency'] == 'unknown' else 'high'
        return semantic.run_case(case or self.cases[0], base_sha=BASE, dataset_sha256=DATASET,
                                 sol_evaluator=with_identity(sol, 'gpt-6-sol', effort),
                                 jev_evaluator=with_identity(jev, 'jev-fixture'))

    def test_fixed_fixture_has_all_mutations_and_human_expectations(self):
        self.assertEqual(len(self.cases), 20)
        self.assertEqual({c['mutation'] for c in self.cases}, semantic.MUTATIONS)
        for mutation in semantic.MUTATIONS:
            expectations = {c['expected_regression'] for c in self.cases if c['mutation'] == mutation}
            self.assertEqual(expectations, {True, False})

    def test_offline_has_no_provider_calls_or_fabricated_tokens(self):
        row = self.run_one()
        self.assertIsNone(row['a']['usage'])
        self.assertIsNone(row['b']['usage'])
        self.assertEqual(row['a']['reason'], 'not_run')
        report = semantic.summarize([row], current_base_sha=BASE, dataset_sha256=DATASET)
        self.assertIsNone(report['tokens']['combined'])
        self.assertIsNone(report['cost']['combined'])

    def test_no_predictions_have_null_quality_counts_with_reason_and_coverage(self):
        row = self.run_one()
        report = semantic.summarize([row], current_base_sha=BASE, dataset_sha256=DATASET,
                                    expected_case_ids=[c['id'] for c in self.cases])
        for arm in ('sol', 'jev'):
            quality = report['quality'][arm]
            self.assertEqual(quality['reason'], 'no_observed_predictions')
            self.assertEqual(quality['coverage'], {'observed': 0, 'total': 20, 'reason': None})
            for metric in ('detected_regression', 'missed_regression', 'false_positive', 'false_negative'):
                self.assertIsNone(quality[metric])
        self.assertEqual(report['quality']['critical_jev_miss'], 0)
        self.assertEqual(report['quality']['critical_jev_miss_coverage']['observed'], 0)
        self.assertEqual(report['quality']['critical_jev_miss_coverage']['reason'], 'missing_case_results')
        self.assertEqual(report['verdict'], 'UNMEASURED')

    def test_malformed_response_and_invalid_confidence_fail_closed(self):
        for bad in [None, {}, dict(status='OK', answer={'choice': 'regression'}, usage=USAGE),
                    dict(status='OK', answer=answer(confidence=float('nan')), usage=USAGE),
                    dict(status='OK', answer=answer(confidence=1.2), usage=USAGE)]:
            with self.subTest(bad=bad):
                got = semantic.normalize_observation(bad, 'jev')
                self.assertEqual(got['status'], 'UNAVAILABLE')
                self.assertIsNone(got['choice'])

    def test_model_effort_mismatch_is_excluded(self):
        bad = dict(observation(), model='gpt-6-sol', reasoning_effort='low')
        got = semantic.normalize_observation(bad, 'gpt-6-sol', 'high')
        self.assertEqual(got['reason'], 'model_effort_mismatch_or_missing')
        self.assertIsNone(got['choice'])

    def test_critical_protected_and_unknown_dependency_force_sol_xhigh(self):
        selected = [c for c in self.cases if c['severity'] == 'critical' or
                    c['mutation'] == 'protected_as_candidate' or c['dependency'] == 'unknown']
        self.assertGreaterEqual(len(selected), 3)
        for case in selected:
            with self.subTest(case=case['id']):
                row = semantic.run_case(case, base_sha=BASE, dataset_sha256=DATASET)
                self.assertEqual(row['a']['reasoning_effort'], 'xhigh')

    def test_missing_usage_is_null_and_does_not_erase_quality_observation(self):
        row = self.run_one(sol=lambda _: observation(),
                           jev=lambda _: dict(status='OK', answer=answer('no_regression'), usage=None))
        self.assertEqual(row['b']['reason'], 'missing_usage')
        self.assertIsNone(row['b']['usage'])
        report = semantic.summarize([row], current_base_sha=BASE, dataset_sha256=DATASET)
        self.assertEqual(report['quality']['jev']['missed_regression'], 1)
        self.assertIsNone(report['tokens']['jev'])
        self.assertEqual(report['coverage']['jev_usage'], 0)

    def test_timeout_is_unavailable(self):
        def timeout(_):
            raise TimeoutError()
        row = self.run_one(sol=timeout, jev=timeout)
        self.assertEqual(row['a']['reason'], 'timeout')
        self.assertEqual(row['b']['reason'], 'timeout')

    def test_jev_http_timeout_and_invalid_body_do_not_succeed(self):
        case = self.cases[0]
        def timeout(_req, timeout):
            raise TimeoutError()
        self.assertEqual(semantic.call_jev(case, key='fictional-key', opener=timeout)['reason'], 'timeout')
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, size): return b'{bad'
        self.assertEqual(semantic.call_jev(case, key='fictional-key', opener=lambda *_args, **_kw: Response())['reason'],
                         'invalid_response')

    def test_sol_nonzero_exit_and_timeout_do_not_succeed(self):
        class Exit:
            returncode = 1
            stdout = ''
        self.assertEqual(semantic.call_sol(self.cases[0], runner=lambda *_a, **_k: Exit())['reason'], 'nonzero_exit')
        def timeout(*_a, **_k):
            from subprocess import TimeoutExpired
            raise TimeoutExpired('codex', 1)
        self.assertEqual(semantic.call_sol(self.cases[0], runner=timeout)['reason'], 'timeout')

    def test_secret_or_opaque_fixture_is_rejected_before_provider(self):
        for value in ['password=fictional-value', 'account number=123456', 'x' * 90]:
            case = copy.deepcopy(self.cases[0]); case['candidate'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.run_one(case, sol=lambda _: observation(), jev=lambda _: observation())

    def test_result_contains_no_raw_fixture_text(self):
        row = self.run_one(sol=lambda _: observation(), jev=lambda _: observation())
        encoded = json.dumps(row)
        for field in ('requirement', 'baseline', 'candidate', 'evidence'):
            self.assertNotIn(self.cases[0][field], encoded)

    def test_critical_miss_blocks_and_survives_duplicate(self):
        case = next(c for c in self.cases if c['severity'] == 'critical' and c['expected_regression'])
        miss = self.run_one(case, sol=lambda _: observation(), jev=lambda _: observation('no_regression'))
        pass_row = self.run_one(case, sol=lambda _: observation(), jev=lambda _: observation())
        report = semantic.summarize([pass_row, miss], current_base_sha=BASE,
                                    dataset_sha256=DATASET,
                                    expected_case_ids=[c['id'] for c in self.cases])
        self.assertEqual(report['case_count'], 1)
        self.assertEqual(report['duplicate_case_count'], 1)
        self.assertEqual(report['quality']['critical_jev_miss'], 1)
        self.assertEqual(report['quality']['critical_jev_miss_coverage']['observed'], 1)
        self.assertEqual(report['verdict'], 'BLOCKED')
        self.assertEqual(len(report['coverage']['missing_case_ids']), 19)
        self.assertEqual(report['actual_action'], 'none')

    def test_partial_pilot_cannot_claim_complete(self):
        row = self.run_one(sol=lambda _: observation(), jev=lambda _: observation())
        expected = [c['id'] for c in self.cases]
        report = semantic.summarize([row], current_base_sha=BASE, dataset_sha256=DATASET,
                                    expected_case_ids=expected)
        self.assertEqual(report['verdict'], 'UNMEASURED')
        self.assertEqual(report['coverage']['expected_cases'], 20)
        self.assertEqual(report['coverage']['observed_case_ids'], [row['id']])
        self.assertEqual(len(report['coverage']['missing_case_ids']), 19)
        self.assertEqual(report['quality']['jev']['coverage']['total'], 20)
        self.assertIsNone(report['quality']['quality_not_worse'])
        self.assertIsNone(report['tokens']['combined'])

    def test_denominator_missing_or_duplicate_is_not_completion(self):
        row = self.run_one(sol=lambda _: observation(), jev=lambda _: observation())
        no_denominator = semantic.summarize([row], current_base_sha=BASE,
                                             dataset_sha256=DATASET)
        self.assertEqual(no_denominator['verdict'], 'UNMEASURED')
        self.assertIsNone(no_denominator['coverage']['expected_case_ids'])
        with self.assertRaises(ValueError):
            semantic.summarize([row], current_base_sha=BASE, dataset_sha256=DATASET,
                               expected_case_ids=[row['id'], row['id']])

    def test_complete_fixed_denominator_can_report_shadow_only(self):
        rows = []
        for case in self.cases:
            choice = 'regression' if case['expected_regression'] else 'no_regression'
            rows.append(self.run_one(case, sol=lambda _, selected=choice: observation(selected),
                                     jev=lambda _, selected=choice: observation(selected)))
        report = semantic.summarize(rows, current_base_sha=BASE, dataset_sha256=DATASET,
                                    expected_case_ids=[c['id'] for c in self.cases])
        self.assertEqual(report['verdict'], 'SHADOW_ONLY')
        self.assertEqual(report['coverage']['missing_case_ids'], [])
        self.assertEqual(report['coverage']['expected_cases'], 20)
        self.assertTrue(report['quality']['quality_not_worse'])
        self.assertEqual(report['tokens']['combined'], 600)

    def test_stale_result_is_excluded(self):
        row = self.run_one(sol=lambda _: observation(), jev=lambda _: observation('no_regression'))
        report = semantic.summarize([row], current_base_sha='c' * 40, dataset_sha256=DATASET)
        self.assertEqual(report['case_count'], 0)
        self.assertEqual(report['stale_result_count'], 1)
        self.assertIsNone(report['tokens']['combined'])

    def test_agreement_and_false_positive_are_measured(self):
        control = next(c for c in self.cases if c['expected_regression'] is False)
        row = self.run_one(control, sol=lambda _: observation('no_regression'),
                           jev=lambda _: observation('regression'))
        report = semantic.summarize([row], current_base_sha=BASE, dataset_sha256=DATASET,
                                    expected_case_ids=[control['id']])
        self.assertEqual(report['quality']['jev']['false_positive'], 1)
        self.assertEqual(report['quality']['agreement'], {'agree': 0, 'compared': 1})
        self.assertEqual(report['tokens']['combined'], 30)


if __name__ == '__main__':
    unittest.main()
