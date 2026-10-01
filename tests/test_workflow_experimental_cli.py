"""Offline command contracts for the three isolated shadow experiments."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
BASE = '75cbae92b19274305e7299b930c694e439b5d8a2'


class ExperimentalCliTests(unittest.TestCase):
    def command(self, cwd, *args):
        return subprocess.run([PYTHON, '-m', 'tools.workflow_eval.cli', *args],
                              cwd=cwd, text=True, capture_output=True,
                              env={**__import__('os').environ, 'PYTHONPATH': str(ROOT)})

    def test_semantic_offline_is_separate_and_unmeasured(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ROOT / 'tests/fixtures/workflow_semantic_regression_cases.json'
            run = self.command(tmp, 'semantic-regression', '--cases', str(fixture),
                               '--base-sha', BASE)
            self.assertEqual(run.returncode, 0, run.stderr)
            directory = Path(tmp) / '.workflow-eval'
            reports = list(directory.glob('semantic-regression-*-report.json'))
            self.assertEqual(len(reports), 1)
            report = json.loads(reports[0].read_text(encoding='utf-8'))
            self.assertEqual(report['verdict'], 'UNMEASURED')
            self.assertIsNone(report['tokens']['combined'])
            self.assertFalse((directory / 'real-tasks.json').exists())

    def test_trace_offline_saves_metadata_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ROOT / 'tests/fixtures/workflow_trace_cases.json'
            run = self.command(tmp, 'trace-benchmark', '--cases', str(fixture),
                               '--base-sha', BASE)
            self.assertEqual(run.returncode, 0, run.stderr)
            directory = Path(tmp) / '.workflow-eval'
            rows = list(directory.glob('trace-eval-*-rows.json'))
            self.assertEqual(len(rows), 1)
            result = rows[0].read_text(encoding='utf-8')
            self.assertNotIn('Synthetic developer', result)
            self.assertNotIn('segments', result)
            self.assertFalse((directory / 'real-tasks.json').exists())

    def test_frozen_fixture_base_is_default_and_live_allows_descendant_main(self):
        from types import SimpleNamespace
        from tools.workflow_eval.experimental_cli import _base, _live_base
        self.assertEqual(_base(SimpleNamespace(base_sha=None), ROOT, fixture_base=BASE), BASE)
        current = _live_base(BASE)
        self.assertRegex(current, r"^[0-9a-f]{40}$")

    def test_default_trace_and_jevgrep_commands_run_without_explicit_base(self):
        for command, fixture_name in (
                ('trace-benchmark', 'workflow_trace_cases.json'),
                ('jevgrep-benchmark', 'workflow_jevgrep_cases.json')):
            with self.subTest(command=command), tempfile.TemporaryDirectory() as tmp:
                fixture = ROOT / 'tests/fixtures' / fixture_name
                run = self.command(tmp, command, '--cases', str(fixture))
                self.assertEqual(run.returncode, 0, run.stderr)

    def test_jevgrep_offline_never_installs_or_reports_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ROOT / 'tests/fixtures/workflow_jevgrep_cases.json'
            run = self.command(tmp, 'jevgrep-benchmark', '--cases', str(fixture),
                               '--base-sha', BASE)
            self.assertEqual(run.returncode, 0, run.stderr)
            directory = Path(tmp) / '.workflow-eval'
            reports = list(directory.glob('jevgrep-*-report.json'))
            self.assertEqual(len(reports), 1)
            report = json.loads(reports[0].read_text(encoding='utf-8'))
            self.assertEqual(report['coverage_missing_data']['comparable_pairs'], 0)
            self.assertFalse((directory / 'real-tasks.json').exists())

    def test_jevgrep_defaults_to_current_sol_and_reads_explicit_legacy_history(self):
        for options, model, provenance in (
                ((), 'gpt-6.1-sol', 'current'),
                (('--sol-model', 'gpt-6-sol'), 'gpt-6-sol', 'legacy_historical')):
            with self.subTest(model=model), tempfile.TemporaryDirectory() as tmp:
                fixture = ROOT / 'tests/fixtures/workflow_jevgrep_cases.json'
                run = self.command(tmp, 'jevgrep-benchmark', '--cases', str(fixture),
                                   '--base-sha', BASE, *options)
                self.assertEqual(run.returncode, 0, run.stderr)
                rows_path = next((Path(tmp) / '.workflow-eval').glob('jevgrep-*-rows.json'))
                rows = json.loads(rows_path.read_text(encoding='utf-8'))
                self.assertEqual(len(rows), 10)
                self.assertTrue(all(r['sol_model'] == model and
                                    r['model_provenance'] == provenance for r in rows))
                self.assertTrue(all(r['comparison_status'] == 'EXCLUDED' for r in rows))
                self.assertFalse((Path(tmp) / '.workflow-eval' / 'real-tasks.json').exists())

    def test_jevgrep_rejects_legacy_live_and_unknown_model_before_discovery(self):
        from types import SimpleNamespace
        from tools.workflow_eval.experimental_cli import _jevgrep
        # The guard must run before fixture/source/provider handling.
        with self.assertRaisesRegex(ValueError, 'legacy_sol_model_not_live'):
            _jevgrep(SimpleNamespace(live=True, sol_model='gpt-6-sol'), ROOT, None)
        for options, error in (
                (('--sol-model', 'gpt-6-sol', '--live'), 'Evaluation failed:'),
                (('--sol-model', 'gpt-6-astra'), 'invalid choice')):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as tmp:
                fixture = ROOT / 'tests/fixtures/workflow_jevgrep_cases.json'
                run = self.command(tmp, 'jevgrep-benchmark', '--cases', str(fixture),
                                   '--base-sha', BASE, *options)
                self.assertNotEqual(run.returncode, 0)
                self.assertIn(error, run.stderr)
                self.assertFalse((Path(tmp) / '.workflow-eval').exists())

    def test_experimental_report_keeps_eight_sections_and_missing_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ROOT / 'tests/fixtures/workflow_semantic_regression_cases.json'
            first = self.command(tmp, 'semantic-regression', '--cases', str(fixture),
                                 '--base-sha', BASE)
            self.assertEqual(first.returncode, 0, first.stderr)
            rows = next((Path(tmp) / '.workflow-eval').glob('semantic-regression-*-rows.json'))
            combined = self.command(tmp, 'experimental-report', '--semantic-rows', str(rows),
                                    '--semantic-cases', str(fixture), '--base-sha', BASE)
            self.assertEqual(combined.returncode, 0, combined.stderr)
            report = json.loads((Path(tmp) / '.workflow-eval' / 'experimental-summary.json').read_text(encoding='utf-8'))
            for field in ('quality', 'tokens', 'cost', 'time', 'context_retrieval',
                          'rework_test_failure', 'coverage_missing_data', 'limitations'):
                self.assertEqual(set(report[field]), {'trace', 'semantic', 'jevgrep'})
            self.assertEqual(report['pilot_status']['semantic'], 'UNMEASURED')
            self.assertEqual(report['cost']['trace']['value'], None)
            self.assertFalse(report['real_task_cohort_included'])

    def test_experimental_report_accepts_each_experiments_own_valid_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / '.workflow-eval'
            trace_fixture = ROOT / 'tests/fixtures/workflow_trace_cases.json'
            semantic_fixture = ROOT / 'tests/fixtures/workflow_semantic_regression_cases.json'
            grep_fixture = ROOT / 'tests/fixtures/workflow_jevgrep_cases.json'

            trace = self.command(tmp, 'trace-benchmark', '--cases', str(trace_fixture))
            semantic = self.command(tmp, 'semantic-regression', '--cases', str(semantic_fixture))
            grep = self.command(tmp, 'jevgrep-benchmark', '--cases', str(grep_fixture))
            self.assertEqual(trace.returncode, 0, trace.stderr)
            self.assertEqual(semantic.returncode, 0, semantic.stderr)
            self.assertEqual(grep.returncode, 0, grep.stderr)

            trace_rows = next(directory.glob('trace-eval-*-rows.json'))
            semantic_rows = next(directory.glob('semantic-regression-*-rows.json'))
            grep_rows = next(directory.glob('jevgrep-*-rows.json'))
            combined = self.command(
                tmp, 'experimental-report',
                '--trace-rows', str(trace_rows), '--trace-cases', str(trace_fixture),
                '--semantic-rows', str(semantic_rows), '--semantic-cases', str(semantic_fixture),
                '--jevgrep-rows', str(grep_rows), '--jevgrep-cases', str(grep_fixture))
            self.assertEqual(combined.returncode, 0, combined.stderr)
            report = json.loads((directory / 'experimental-summary.json').read_text(encoding='utf-8'))
            self.assertEqual(set(report['base_sha_by_experiment']), {'trace', 'semantic', 'jevgrep'})
            self.assertNotEqual(report['base_sha_by_experiment']['trace'],
                                report['base_sha_by_experiment']['semantic'])

    def test_stale_trace_fixture_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ROOT / 'tests/fixtures/workflow_trace_cases.json'
            run = self.command(tmp, 'trace-benchmark', '--cases', str(fixture),
                               '--base-sha', 'a' * 40)
            self.assertNotEqual(run.returncode, 0)
            self.assertFalse((Path(tmp) / '.workflow-eval' / 'real-tasks.json').exists())

    def test_report_rejects_trace_rows_rebased_away_from_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ROOT / 'tests/fixtures/workflow_trace_cases.json'
            run = self.command(tmp, 'trace-benchmark', '--cases', str(fixture))
            self.assertEqual(run.returncode, 0, run.stderr)
            original = next((Path(tmp) / '.workflow-eval').glob('trace-eval-*-rows.json'))
            rows = json.loads(original.read_text(encoding='utf-8'))
            for row in rows:
                row['base_sha'] = 'f' * 40
                row['a']['base_sha'] = 'f' * 40
                row['b']['base_sha'] = 'f' * 40
            changed = Path(tmp) / 'rebased-trace.json'
            changed.write_text(json.dumps(rows), encoding='utf-8')
            report = self.command(tmp, 'experimental-report', '--trace-rows', str(changed),
                                  '--trace-cases', str(fixture))
            self.assertNotEqual(report.returncode, 0)

    def test_report_rejects_jevgrep_rows_rebased_away_from_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ROOT / 'tests/fixtures/workflow_jevgrep_cases.json'
            run = self.command(tmp, 'jevgrep-benchmark', '--cases', str(fixture))
            self.assertEqual(run.returncode, 0, run.stderr)
            original = next((Path(tmp) / '.workflow-eval').glob('jevgrep-*-rows.json'))
            rows = json.loads(original.read_text(encoding='utf-8'))
            for row in rows:
                row['base_sha'] = 'f' * 40
            changed = Path(tmp) / 'rebased-jevgrep.json'
            changed.write_text(json.dumps(rows), encoding='utf-8')
            report = self.command(tmp, 'experimental-report', '--jevgrep-rows', str(changed),
                                  '--jevgrep-cases', str(fixture))
            self.assertNotEqual(report.returncode, 0)

    def test_report_rejects_same_base_rows_after_trace_fixture_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ROOT / 'tests/fixtures/workflow_trace_cases.json'
            run = self.command(tmp, 'trace-benchmark', '--cases', str(fixture), '--base-sha', BASE)
            self.assertEqual(run.returncode, 0, run.stderr)
            rows = next((Path(tmp) / '.workflow-eval').glob('trace-eval-*-rows.json'))
            edited = json.loads(fixture.read_text(encoding='utf-8'))
            edited['cases'][0]['segments'][0]['text'] = 'Changed same-base fixture content.'
            changed_fixture = Path(tmp) / 'changed-trace.json'
            changed_fixture.write_text(json.dumps(edited), encoding='utf-8')
            report = self.command(tmp, 'experimental-report', '--trace-rows', str(rows),
                                  '--trace-cases', str(changed_fixture), '--base-sha', BASE)
            self.assertNotEqual(report.returncode, 0)

    def test_unpaired_critical_miss_remains_blocked_in_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ROOT / 'tests/fixtures/workflow_trace_cases.json'
            run = self.command(tmp, 'trace-benchmark', '--cases', str(fixture), '--base-sha', BASE)
            self.assertEqual(run.returncode, 0, run.stderr)
            original = next((Path(tmp) / '.workflow-eval').glob('trace-eval-*-rows.json'))
            rows = json.loads(original.read_text(encoding='utf-8'))
            critical = next(r for r in rows if r['priority']['critical_segment_ids'])
            critical['a']['critical_miss_segment_ids'] = critical['priority']['critical_segment_ids']
            changed = Path(tmp) / 'observed-critical.json'
            changed.write_text(json.dumps(rows), encoding='utf-8')
            report = self.command(tmp, 'experimental-report', '--trace-rows', str(changed),
                                  '--trace-cases', str(fixture), '--base-sha', BASE)
            self.assertEqual(report.returncode, 0, report.stderr)
            result = json.loads((Path(tmp) / '.workflow-eval' / 'experimental-summary.json').read_text(encoding='utf-8'))
            self.assertEqual(result['pilot_status']['trace'], 'BLOCKED_CRITICAL_MISS')

    def test_trace_dataset_membership_change_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ROOT / 'tests/fixtures/workflow_trace_cases.json'
            run = self.command(tmp, 'trace-benchmark', '--cases', str(fixture), '--base-sha', BASE)
            self.assertEqual(run.returncode, 0, run.stderr)
            rows = next((Path(tmp) / '.workflow-eval').glob('trace-eval-*-rows.json'))
            edited = json.loads(fixture.read_text(encoding='utf-8'))
            extra = dict(edited['cases'][0], task_id='trace-11')
            edited['cases'].append(extra)
            changed = Path(tmp) / 'expanded-trace.json'
            changed.write_text(json.dumps(edited), encoding='utf-8')
            result = self.command(tmp, 'experimental-report', '--trace-rows', str(rows),
                                  '--trace-cases', str(changed), '--base-sha', BASE)
            self.assertNotEqual(result.returncode, 0)

    def test_jevgrep_discovery_rows_merge_path_is_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ROOT / 'tests/fixtures/workflow_jevgrep_cases.json'
            cases = json.loads(fixture.read_text(encoding='utf-8'))['cases']
            dataset_sha = __import__('hashlib').sha256(fixture.read_bytes()).hexdigest()
            discovery = []
            observations = {}
            for case in cases:
                discovery.append(dict(
                    case_id=case['id'], base_sha=BASE, dataset_sha256=dataset_sha,
                    retrieval_only=True,
                    b=dict(status='UNAVAILABLE', reason='unsupported_environment',
                           found_files=[])))
                observations[case['id']] = {}
            discovery_path = Path(tmp) / 'discovery.json'
            observations_path = Path(tmp) / 'b-observations.json'
            allowlist_path = Path(tmp) / 'allowlist.json'
            discovery_path.write_text(json.dumps(discovery), encoding='utf-8')
            observations_path.write_text(json.dumps(observations), encoding='utf-8')
            allowlist_path.write_text(json.dumps(['src/MT3SymbolState.mqh']), encoding='utf-8')
            run = self.command(
                tmp, 'jevgrep-benchmark', '--cases', str(fixture), '--base-sha', BASE,
                '--discovery-rows', str(discovery_path),
                '--b-observations', str(observations_path),
                '--source-allowlist', str(allowlist_path))
            self.assertEqual(run.returncode, 0, run.stderr)

    def test_discovery_merge_binds_sol_observation_and_preserves_retrieval(self):
        from tools.workflow_eval.experimental_cli import merge_discovery
        identity = dict(task_id='task_1', base_sha=BASE, sol_model='gpt-6-sol', sol_effort='xhigh')
        missing = dict(value=None, reason='not_reported', coverage=0)
        discovery = dict(status='OK', reason='completed', found_files=['src/MT3SymbolState.mqh'],
                         source_sha256='b' * 64, cache_bypassed=True, stage_file_count=1,
                         jg_version='@dzhng/jevgrep 0.4.4', metrics=dict(elapsed_seconds=dict(
                             value=1.5, reason=None, coverage=1), source_bytes=missing,
                             context_bytes=missing, jevgrep_tokens=missing,
                             source_universe_coverage=dict(value=0.5, reason=None, coverage=1)))
        sol = dict(identity, discovery_rows_sha256='c' * 64, sol_status='OK',
                   task_success=1, sol_input_tokens=100, sol_output_tokens=20,
                   sol_elapsed_seconds=4.0)
        combined = merge_discovery(discovery, sol, 'c' * 64, identity)
        self.assertEqual(combined['found_files'], discovery['found_files'])
        self.assertEqual(combined['source_sha256'], 'b' * 64)
        self.assertTrue(combined['cache_bypassed'])
        self.assertEqual(combined['elapsed_seconds'], 5.5)
        self.assertEqual(combined['source_universe_coverage']['value'], 0.5)
        from tools.workflow_eval.jevgrep_benchmark import score_arm
        case = json.loads((ROOT / 'tests/fixtures/workflow_jevgrep_cases.json').read_text(encoding='utf-8'))['cases'][0]
        self.assertEqual(score_arm(case, combined)['task_success']['value'], 1)
        with self.assertRaises(ValueError):
            merge_discovery(discovery, dict(sol, discovery_rows_sha256='d' * 64), 'c' * 64, identity)
        with self.assertRaises(ValueError):
            merge_discovery(discovery, dict(sol, source_universe_coverage=1), 'c' * 64, identity)

    def test_discovery_merge_preserves_unavailable_cases(self):
        from tools.workflow_eval.experimental_cli import merge_discovery
        identity = dict(task_id='task_1', base_sha=BASE, sol_model='gpt-6-sol', sol_effort='xhigh')
        discovery = dict(status='UNAVAILABLE', reason='unsupported_environment', found_files=[], metrics={})
        result = merge_discovery(discovery, None, 'c' * 64, identity)
        self.assertEqual(result['status'], 'UNAVAILABLE')
        self.assertEqual(result['reason'], 'unsupported_environment')
        discovery = dict(status='OK', reason='completed', found_files=[], metrics={})
        sol = dict(identity, discovery_rows_sha256='c' * 64, sol_status='FAIL')
        result = merge_discovery(discovery, sol, 'c' * 64, identity)
        self.assertEqual(result['status'], 'OK')  # Retrieval remains independently observed.
        self.assertEqual(result['sol_status'], 'FAIL')
        self.assertIsNone(result['task_success'])
        from tools.workflow_eval.jevgrep_benchmark import evaluate_pair, summarize_pairs
        case = json.loads((ROOT / 'tests/fixtures/workflow_jevgrep_cases.json').read_text(encoding='utf-8'))['cases'][0]
        identity = dict(identity, task_id=case['id'])
        sol = dict(identity, discovery_rows_sha256='c' * 64, sol_status='FAIL')
        failed = merge_discovery(discovery, sol, 'c' * 64, identity)
        row = evaluate_pair(case, dict(identity, status='UNAVAILABLE',
                           reason='observation_unavailable', found_files=[]), failed,
                           current_base_sha=BASE)
        self.assertEqual(row['comparison_status'], 'EXCLUDED')
        self.assertEqual(summarize_pairs([row])['pilot_status'], 'BLOCKED_CRITICAL_FILE_MISS')

    def test_report_rejects_same_base_jevgrep_rows_after_fixture_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ROOT / 'tests/fixtures/workflow_jevgrep_cases.json'
            run = self.command(tmp, 'jevgrep-benchmark', '--cases', str(fixture), '--base-sha', BASE)
            self.assertEqual(run.returncode, 0, run.stderr)
            rows = next((Path(tmp) / '.workflow-eval').glob('jevgrep-*-rows.json'))
            edited = json.loads(fixture.read_text(encoding='utf-8'))
            edited['cases'][0]['query'] = 'Changed same-base query.'
            changed_fixture = Path(tmp) / 'changed-jevgrep.json'
            changed_fixture.write_text(json.dumps(edited), encoding='utf-8')
            report = self.command(tmp, 'experimental-report', '--jevgrep-rows', str(rows),
                                  '--jevgrep-cases', str(changed_fixture), '--base-sha', BASE)
            self.assertNotEqual(report.returncode, 0)

    def test_unpaired_jevgrep_critical_file_miss_remains_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ROOT / 'tests/fixtures/workflow_jevgrep_cases.json'
            run = self.command(tmp, 'jevgrep-benchmark', '--cases', str(fixture), '--base-sha', BASE)
            self.assertEqual(run.returncode, 0, run.stderr)
            original = next((Path(tmp) / '.workflow-eval').glob('jevgrep-*-rows.json'))
            rows = json.loads(original.read_text(encoding='utf-8'))
            rows[0]['b']['critical_file_misses'] = ['src/MT3SymbolState.mqh']
            changed = Path(tmp) / 'critical-jevgrep.json'
            changed.write_text(json.dumps(rows), encoding='utf-8')
            report = self.command(tmp, 'experimental-report', '--jevgrep-rows', str(changed),
                                  '--jevgrep-cases', str(fixture), '--base-sha', BASE)
            self.assertEqual(report.returncode, 0, report.stderr)
            result = json.loads((Path(tmp) / '.workflow-eval' / 'experimental-summary.json').read_text(encoding='utf-8'))
            self.assertEqual(result['pilot_status']['jevgrep'], 'BLOCKED_CRITICAL_FILE_MISS')


if __name__ == '__main__':
    unittest.main()
