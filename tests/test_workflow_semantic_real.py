"""Offline contracts for the separate real-derived shadow cohort."""
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.workflow_eval import semantic_real as real

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/workflow_semantic_real_cases.json'
BASE = 'ca2f7da9d65cf68433fd7d791e6dafe16ea3c1f1'
USAGE = dict(input_tokens=12, output_tokens=3, total_tokens=15)


def observation(choice='regression', model=real.SOL_MODEL, effort='xhigh'):
    probabilities = {k: .025 for k in real.CHOICES}
    probabilities[choice] = .95
    return dict(status='OK', answer=dict(type='choice', choice=choice,
                confidence=.95, probabilities=probabilities), model=model,
                reasoning_effort=effort, usage=USAGE, elapsed_seconds=.5)


class RealSemantic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases, cls.sha = real.load_cases(FIXTURE, ROOT)

    def row(self, case=None, a=None, b=None):
        case = case or next(c for c in self.cases if c['severity'] == 'critical'
                           and c['expected_result'] == 'regression')
        return real.run_case(case, base_sha=BASE, dataset_sha256=self.sha,
                             sol_evaluator=lambda payload: a or observation(),
                             jev_evaluator=lambda payload: b or observation(model='jev-1.13.0', effort=None))

    def report(self, rows):
        return real.summarize(rows, self.cases, base_sha=BASE, dataset_sha256=self.sha)

    def test_fixture_contracts_and_source_coverage(self):
        self.assertTrue(15 <= len(self.cases) <= 20)
        self.assertEqual({c['source_pr'] for c in self.cases}, {11, 12, 17, 18})
        self.assertEqual(len({c['semantic_contract'] for c in self.cases}), len(self.cases))
        self.assertTrue(any(c['expected_result'] == 'no_regression' for c in self.cases))

    def test_duplicate_unknown_source_missing_ground_truth_rejected(self):
        for field, value in [('source_pr', 99), ('deterministic_ground_truth', None),
                             ('provenance', {}), ('source_commit', 'f'*40)]:
            cases = copy.deepcopy(self.cases); cases[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                real.validate_cases(cases, ROOT)
        with self.assertRaises(ValueError):
            real.validate_cases(self.cases + [self.cases[0]], ROOT)

    def test_stale_source_hash_and_changed_oracle_rejected(self):
        for change in ('source_sha256', 'expected_result'):
            cases = copy.deepcopy(self.cases)
            if change == 'source_sha256':
                cases[0]['provenance']['source_sha256'] = 'f'*64
            else:
                cases[0]['expected_result'] = 'no_regression'
            with self.assertRaises(ValueError): real.validate_cases(cases, ROOT)

    def test_payload_has_no_oracle_id_severity_provenance(self):
        for case in self.cases:
            payload = real.provider_payload(case)
            self.assertEqual(set(payload), {'requirement', 'baseline', 'candidate', 'evidence'})
            self.assertNotIn(case['id'], json.dumps(payload))
            for key in ('expected_result', 'severity', 'provenance', 'source_pr'):
                self.assertNotIn(key, payload)

    def test_expected_label_leakage_and_raw_secret_rejected(self):
        for text in ['expected_result: regression', 'This is a regression.',
                     'severity: critical', 'TYPESAFE_API_KEY=secret123',
                     'password=supersecret', 'sk-proj-abcdefg12345']:
            case = copy.deepcopy(self.cases[0]); case['mutated_evidence'] = text
            with self.subTest(text=text), self.assertRaises(ValueError): real.provider_payload(case)

    def test_providers_receive_only_payload(self):
        seen = []
        def evaluator(payload):
            seen.append(payload)
            return observation()
        real.run_case(self.cases[0], base_sha=BASE, dataset_sha256=self.sha,
                      sol_evaluator=evaluator, jev_evaluator=evaluator)
        self.assertEqual(len(seen), 2)
        self.assertEqual(set(seen[0]), {'requirement', 'baseline', 'candidate', 'evidence'})

    def test_malformed_confidence_and_model_fail_closed_keep_usage(self):
        bad = observation(); bad['answer'] = {}
        invalid_conf = observation(); invalid_conf['answer']['confidence'] = 1.1
        for value in (bad, invalid_conf, observation(model='unknown'), observation(effort='high')):
            got = real.normalize(value, 'sol')
            self.assertNotEqual(got['status'], 'OK')
            self.assertIsNone(got['choice'])
            self.assertEqual(got['usage'], USAGE)

    def test_missing_usage_is_null_but_quality_survives(self):
        value = observation(); value['usage'] = None
        got = real.normalize(value, 'sol')
        self.assertEqual(got['status'], 'OK')
        self.assertIsNone(got['usage'])
        self.assertEqual(got['usage_reason'], 'missing_usage')
        report = self.report([self.row(a=value)])
        self.assertIsNone(report['tokens']['sol']['total_tokens'])
        self.assertEqual(report['quality']['sol']['TP'], 1)

    def test_critical_miss_survives_retry_invalid_pair_and_sol_recovery(self):
        row = self.row(b=observation('no_regression', 'jev-1.13.0', None))
        retry = self.row()
        retry['a']['model'] = 'unknown'
        report = self.report([row, retry])
        self.assertEqual(report['verdict'], 'BLOCKED_CRITICAL_MISS')
        self.assertEqual(report['critical_miss']['count'], 1)
        self.assertEqual(report['unique_observed_cases'], 1)
        self.assertEqual(report['retry_rows'], 1)

    def test_unknown_critical_prediction_is_miss_and_abstention(self):
        report = self.report([self.row(b=observation('unknown', 'jev-1.13.0', None))])
        self.assertEqual(report['critical_miss']['count'], 1)
        self.assertEqual(report['quality']['jev']['unknown'], 1)
        self.assertEqual(report['quality']['jev']['scored'], 0)

    def test_model_mismatch_excluded_from_agreement_not_safety(self):
        row = self.row(b=observation('no_regression', 'jev-1.13.0', None))
        row['a']['reasoning_effort'] = 'high'
        report = self.report([row])
        self.assertEqual(report['agreement']['compared'], 0)
        self.assertEqual(report['critical_miss']['count'], 1)

    def test_synthetic_and_unknown_case_rows_rejected_stale_excluded(self):
        row = self.row()
        for field, value in [('experiment', 'semantic_regression'), ('id', 'SR01')]:
            bad = copy.deepcopy(row); bad[field] = value
            with self.assertRaises(ValueError): self.report([bad])
        stale = copy.deepcopy(row); stale['dataset_sha256'] = 'f'*64
        report = self.report([stale])
        self.assertEqual(report['stale_rows'], 1)
        self.assertEqual(report['unique_observed_cases'], 0)
        self.assertIsNone(report['quality']['jev']['accuracy']['value'])

    def test_confusion_matrix_denominators_and_token_retry_billing(self):
        regression = next(c for c in self.cases if c['expected_result'] == 'regression')
        control = next(c for c in self.cases if c['expected_result'] == 'no_regression')
        rows = [self.row(regression), self.row(control, b=observation('no_regression','jev-1.13.0',None)), self.row(regression)]
        report = self.report(rows)
        self.assertEqual(report['quality']['jev']['TP'], 1)
        self.assertEqual(report['quality']['jev']['TN'], 1)
        self.assertEqual(report['quality']['jev']['accuracy'], dict(value=1, numerator=2, denominator=2))
        self.assertEqual(report['tokens']['jev']['observed_total_tokens'], 45)
        self.assertEqual(report['tokens']['jev']['usage_attempts'], 3)
        self.assertIsNone(report['tokens']['combined'])

    def test_live_jev_missing_credentials_timeout_nonzero_sol(self):
        payload = real.provider_payload(self.cases[0])
        with patch.dict('os.environ', {}, clear=True):
            self.assertEqual(real.call_jev(payload)['reason'], 'missing_credentials')
        def timeout(*args, **kwargs): raise TimeoutError()
        self.assertEqual(real.call_jev(payload, key='offline-test-key', opener=timeout)['reason'], 'timeout')
        def failed(cmd, **kwargs):
            self.assertIn('gpt-6.1-sol', cmd)
            self.assertIn('model_reasoning_effort="xhigh"', cmd)
            return subprocess.CompletedProcess(cmd, 1, '', '')
        self.assertEqual(real.call_sol(payload, runner=failed)['reason'], 'nonzero_exit')

    def test_sol_tools_rejected_and_raw_transcript_not_saved(self):
        payload = real.provider_payload(self.cases[0])
        events = [dict(type='item.completed', item=dict(type='command_execution', text='private trace')),
                  dict(type='turn.completed', usage=USAGE)]
        got = real.call_sol(payload, runner=lambda *a, **k: subprocess.CompletedProcess(a, 0, '\n'.join(json.dumps(e) for e in events), ''))
        self.assertEqual(got['reason'], 'invalid_response')
        self.assertNotIn('private trace', json.dumps(got))
        self.assertEqual(got['usage'], USAGE)

    def test_unmerged_source_history_offline_manifest_and_strict_live(self):
        with patch.object(real.subprocess, 'check_output', side_effect=subprocess.CalledProcessError(128, 'git')):
            self.assertEqual(len(real.validate_cases(self.cases, ROOT)), 19)
            with self.assertRaises(ValueError):
                real.validate_cases(self.cases, ROOT, require_source_objects=True)

    def test_imported_raw_fields_rejected_and_reason_redacted(self):
        row = self.row(); row['a']['private_trace'] = 'private raw trace'
        with self.assertRaises(ValueError): self.report([row])
        row = self.row(); row['a']['status'] = 'UNAVAILABLE'; row['a']['reason'] = 'password=supersecret'
        self.assertNotIn('supersecret', json.dumps(self.report([row])))

    def test_cli_offline_separate_and_exclusive_without_calls(self):
        from tools.workflow_eval.semantic_real_cli import execute, exclusive_output
        from types import SimpleNamespace
        args = SimpleNamespace(live=False, rows=None, base_sha=BASE, cases=str(FIXTURE))
        with tempfile.TemporaryDirectory() as directory, patch.object(real, 'call_jev') as jev, patch.object(real, 'call_sol') as sol:
            path = execute(args, Path(directory))
            report = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(report['verdict'], 'UNMEASURED')
            self.assertIsNone(report['tokens']['combined'])
            self.assertFalse((Path(directory)/'.workflow-eval/real-tasks.json').exists())
            jev.assert_not_called(); sol.assert_not_called()
            with self.assertRaises(FileExistsError): exclusive_output(path.parent, path.name, {})

    def test_sol_timeout_retains_completed_usage(self):
        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired('codex', 1, output=json.dumps(dict(type='turn.completed', usage=USAGE)))
        got = real.call_sol(real.provider_payload(self.cases[0]), runner=timeout)
        self.assertEqual(got['reason'], 'timeout')
        self.assertEqual(got['usage'], USAGE)

    def test_duplicate_attempt_identity_cannot_double_bill(self):
        row = self.row()
        report = self.report([row, copy.deepcopy(row)])
        self.assertEqual(report['tokens']['jev']['observed_total_tokens'], 15)
        self.assertEqual(report['retry_rows'], 0)
        self.assertEqual(report['duplicate_rows'], 1)

    def test_distinct_attempts_bill_and_conflicting_identity_rejected(self):
        one = self.row(); two = self.row()
        self.assertNotEqual(one['attempt_id'], two['attempt_id'])
        report = self.report([one, two])
        self.assertEqual(report['tokens']['jev']['observed_total_tokens'], 30)
        self.assertEqual(report['retry_rows'], 1)
        changed = copy.deepcopy(one); changed['b']['choice'] = 'no_regression'
        with self.assertRaises(ValueError): self.report([one, changed])

    def test_legacy_exact_copy_dedup_without_overwriting_frozen_rows(self):
        row = self.row(); row.pop('attempt_id')
        report = self.report([row, copy.deepcopy(row)])
        self.assertEqual(report['tokens']['sol']['observed_total_tokens'], 15)
        self.assertEqual(report['duplicate_rows'], 1)
        self.assertEqual(report['legacy_identity_rows'], 1)


if __name__ == '__main__': unittest.main()
