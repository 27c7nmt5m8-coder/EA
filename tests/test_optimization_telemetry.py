"""Unknown measurements remain unknown; synthetic transport is not a cohort task."""
import importlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class OptimizationTelemetry(unittest.TestCase):
    def test_missing_metrics_have_reasons_and_no_invented_usage(self):
        from importlib.util import find_spec
        self.assertIsNotNone(find_spec('tools.workflow_eval.optimization_telemetry'))
        m = importlib.import_module('tools.workflow_eval.optimization_telemetry')
        row = m.measurement('phase1_baseline', '27c7nmt5m8-coder/EA',
            base_sha='a' * 40, head_sha='a' * 40, tree_sha='b' * 40,
            changed_paths=[], changed_lines=0, task_category='developer_tooling',
            protected=False, dependency='known')
        self.assertIsNone(row['input_tokens'])
        self.assertIn('input_tokens', row['missing_reasons'])
        self.assertIsNone(row['model'])
        self.assertFalse(row['cohort_eligible'])
        row = m.measurement('synthetic_transport', '27c7nmt5m8-coder/EA', origin='synthetic',
                            reused_bytes=1200, resent_bytes=80)
        self.assertEqual(row['reused_bytes'], 1200)
        self.assertIsNone(row['total_tokens'])
        self.assertFalse(row['cohort_eligible'])

    def test_invalid_values_and_unbounded_payloads_cannot_be_persisted(self):
        from importlib.util import find_spec
        self.assertIsNotNone(find_spec('tools.workflow_eval.optimization_telemetry'))
        m = importlib.import_module('tools.workflow_eval.optimization_telemetry')
        for options in [dict(input_tokens=-1), dict(input_tokens=True),
                dict(total_tokens=float('nan')), dict(prompt='unbounded payload'),
                dict(repository='invalid'), dict(origin='synthetic', cohort_eligible=True)]:
            with self.subTest(options=options), self.assertRaises(ValueError):
                args = dict(options)
                repo = args.pop('repository', '27c7nmt5m8-coder/EA')
                m.measurement('note', repo, **args)


if __name__ == '__main__':
    unittest.main()
