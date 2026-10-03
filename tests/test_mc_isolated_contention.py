import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess


class IsolatedTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('tools.mc_isolated_contention'),
                             'isolated runner is not implemented')
        from tools import mc_isolated_contention as runner
        self.m = runner

    def test_cpu_case_cannot_run_before_normal_pair_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, 'NORMAL'):
                self.m.require_normal_pair(Path(td), 2)

    def test_timer_percentiles_use_whole_population_not_top_records(self):
        rows = [dict(event='OnTimer', count='1000', total_us='10000', median_us='10',
                     p95_us='10', p99_us='10', max_us='10')]
        result = self.m.timer_population(rows, [dict(stage='OnTimer', count='1000', total_us='10000', max_us='10', unknown='0')])
        self.assertEqual(result['p99_us'], 10)
        self.assertEqual(result['count'], 1000)

    def test_missing_p99_is_unknown_not_top256_estimate(self):
        with self.assertRaises(ValueError):
            self.m.timer_population([dict(event='OnTimer', count='10')], [])

    def test_population_count_mismatch_rejects_metrics(self):
        row = dict(event='OnTimer', count='10', total_us='100', median_us='10', p95_us='10', p99_us='10', max_us='10')
        with self.assertRaises(ValueError):
            self.m.timer_population([row], [dict(stage='OnTimer', count='9', total_us='90', max_us='10', unknown='0')])

    def test_builder_adds_p99_only_to_diagnostic_copy(self):
        from tools.build_tester_pipeline import SOURCE
        original = {p.name: p.read_bytes() for p in SOURCE.iterdir() if p.is_file()}
        with tempfile.TemporaryDirectory() as td:
            main = self.m.build(Path(td) / 'bundle', 0)
            from tools.mc500k_batch import schema_contract
            schemas, _, _ = schema_contract(main.parent)
            self.assertIn(('symbol','kind','cycle','event','count','total_us','median_us','p90_us','p95_us','p99_us','max_us'), schemas)
        self.assertEqual(original, {p.name: p.read_bytes() for p in SOURCE.iterdir() if p.is_file()})

    def test_private_metadata_rejection_does_not_keep_original_summary(self):
        from tools.mc500k_batch import PrivacyGuard
        guard = PrivacyGuard.__new__(PrivacyGuard)
        guard.values = {'FAKE-PRIVATE-VALUE'}
        result = self.m.safe_summary({'processes':[{'image':'FAKE-PRIVATE-VALUE'}]},guard)
        self.assertFalse(result['comparison_eligible'])
        self.assertNotIn('FAKE-PRIVATE-VALUE',json.dumps(result))

    def test_failed_worker_never_passes_shutdown(self):
        class Finished:
            def wait(self, timeout):
                return 1
        with tempfile.TemporaryDirectory() as td:
            status, _ = self.m.stop_workers([Finished()],Path(td)/'stop')
        self.assertEqual(status,'BLOCKED')

    def test_timeout_requests_action_without_terminate_or_kill(self):
        class Pending:
            def wait(self, timeout):
                raise subprocess.TimeoutExpired('owned-fake',timeout)
            def terminate(self):
                raise AssertionError('termination is forbidden')
            def kill(self):
                raise AssertionError('killing is forbidden')
        with tempfile.TemporaryDirectory() as td:
            status, _ = self.m.stop_workers([Pending()],Path(td)/'stop')
        self.assertEqual(status,'NEEDS_USER_ACTION')

    def test_pending_worker_status_is_not_overwritten_by_later_failure(self):
        class Pending:
            def wait(self, timeout):
                raise subprocess.TimeoutExpired('owned-fake',timeout)
        class Failed:
            def wait(self, timeout):
                return 1
        with tempfile.TemporaryDirectory() as td:
            status, _ = self.m.stop_workers([Pending(),Failed()],Path(td)/'stop')
        self.assertEqual(status,'NEEDS_USER_ACTION')

    def test_profile_rejects_attached_ea_without_loading_it(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            for n in range(1,5):
                (p/f'chart0{n}.chr').write_text('<chart>\n</chart>',encoding='utf-8')
            self.assertEqual(len(self.m.profile_state(p)),4)
            (p/'chart01.chr').write_text('<chart>\n<Expert name="fake">\n</chart>',encoding='utf-8')
            with self.assertRaises(ValueError):
                self.m.profile_state(p)

    def test_untrusted_exception_values_are_not_reported(self):
        error = ValueError("invalid literal for int(): 'FAKE_PRIVATE_VALUE'")
        self.assertEqual(self.m.safe_error_code(error),'UNCLASSIFIED')
        self.assertEqual(self.m.safe_error_code(ValueError('OBSERVER_OVERHEAD_TOO_HIGH')),'OBSERVER_OVERHEAD_TOO_HIGH')

    def placement(self, mask=255):
        return {'affinity':mask,'groups':[0],'cpu_sets':[],'priority':32}

    def observed(self, mask=255):
        return {'processes':[dict(role=role,name=name,
            initial_placement=self.placement(mask), final_placement=self.placement(mask))
            for role,name in [('controller','python.exe'),('owned_terminal','terminal64.exe'),
                              ('owned_descendant','metatester64.exe')]]}

    def test_stable_but_different_pair_placement_is_rejected(self):
        left = self.m.placement_signature(self.observed(1))
        right = self.m.placement_signature(self.observed(255))
        with self.assertRaisesRegex(ValueError,'placement'):
            self.m.require_matching_placement(left,right)

    def test_optional_unknown_placement_does_not_become_pair_pass(self):
        observed = self.observed()
        observed['processes'][0]['initial_placement']['cpu_sets']='UNKNOWN'
        with self.assertRaises(ValueError):
            self.m.placement_signature(observed)

    def test_cpu_workers_must_inherit_normal_controller_placement(self):
        observed = self.observed()
        observed['processes'].append(dict(role='owned_load_generator',name='python.exe',
            initial_placement=self.placement(1),final_placement=self.placement(1)))
        with self.assertRaisesRegex(ValueError,'placement'):
            self.m.placement_signature(observed)

    def test_worker_readiness_needs_identity_and_actual_work(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'ready.json'
            p.write_text(json.dumps(dict(pid=10,born=100,owner_pid=20,owner_born=200,
                                        operations=0,cpu_seconds=0)),encoding='utf-8')
            with self.assertRaises(ValueError):
                self.m.read_worker_ready(p,10,100,20,200)
            p.write_text(json.dumps(dict(pid=10,born=100,owner_pid=20,owner_born=200,
                                        operations=1000,cpu_seconds=.01)),encoding='utf-8')
            self.assertEqual(self.m.read_worker_ready(p,10,100,20,200)['operations'],1000)
            with self.assertRaises(ValueError):
                self.m.read_worker_ready(p,10,101,20,200)


if __name__ == '__main__':
    unittest.main()
