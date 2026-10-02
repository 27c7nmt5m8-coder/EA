"""Fail-closed test-only universe selection and frozen matrix contracts."""
import unittest
from pathlib import Path
import tempfile
import time
from unittest.mock import patch
from tools.mc500k_stress import AffinityMonitor, Process
from tools.analyze_mc_multisymbol import order_accepted, snapshot_lifecycle_counts

from tools.mc_multisymbol_runner import CASE_SYMBOLS, build_cases, selection_copy, frozen_config, validate_case_evidence, prepare_matrix, sha256, validate_replay_rows, verify_engine, validate_result_binding, save_affinity_evidence


ORIGINAL = (
    'RiskMode=2||0||0||2||N\n'
    'MinimumSignalScore=70||70||1||95||N\n'
    'MonteCarloRuns=10000||10000||1||100000||N\n'
    'MaxSpreadATR=2.6||0.1||0.01||1.0||N\n'
    'MaxSpreadSL=0.4||0.15||0.015||1.5||N\n'
    'ScanMode=0||0||0||3||N\n'
    'CustomSymbols=\n'
)


class MatrixContractTest(unittest.TestCase):
    def test_unfinished_cycle_is_not_implicitly_cancelled(self):
        snapshots = [dict(cycle=str(n), completed='1' if n == 4 else '0') for n in (1, 2, 3, 4)]
        cycles = {1: dict(status='cancelled'), 2: dict(status='censored'), 4: dict(status='completed')}
        self.assertEqual(snapshot_lifecycle_counts('ACTUAL', snapshots, cycles),
                         dict(unfinished=3, cancelled=1, censored=1))
        self.assertEqual(snapshot_lifecycle_counts('SHADOW', snapshots, cycles),
                         dict(unfinished=3, cancelled=0, censored=0))

    def test_evidence_write_failure_preserves_primary_failure(self):
        original = ValueError('observed affinity drift')
        with patch('tools.mc_multisymbol_runner.batch.dump', side_effect=OSError('fixture write failed')):
            save_affinity_evidence(Path('unused'), None, original)
            self.assertEqual(original.__notes__, ['affinity evidence save failed: OSError'])
            with self.assertRaises(OSError):
                save_affinity_evidence(Path('unused'), None)

    def test_unavailable_startup_evidence_is_unknown(self):
        with patch('tools.mc_multisymbol_runner.batch.dump') as dump:
            save_affinity_evidence(Path('unused'), None, ValueError('fixture startup failure'))
            self.assertEqual(dump.call_args.args[1]['status'], 'UNKNOWN')
            self.assertEqual(dump.call_args.args[1]['mask'], 'UNKNOWN')

    def test_successful_call_with_rejection_retcode_is_not_accepted(self):
        for code in ('10008', '10009', '10010'):
            self.assertTrue(order_accepted({'success': '1', 'retcode': code}))
        self.assertFalse(order_accepted({'success': '1', 'retcode': '10030'}))
        self.assertFalse(order_accepted({'success': '0', 'retcode': '10009'}))

    def test_affinity_drift_evidence_cannot_claim_pass(self):
        class API:
            def pin(self, process, mask):
                return mask
        root = Process(1, 0, 100, 'terminal64.exe', 255)
        monitor = AffinityMonitor(API(), root, 0, time.monotonic())
        monitor.known[2] = Process(2, 1, 101, 'metatester64.exe', 1)
        with self.assertRaises(ValueError):
            monitor.observe(root, 'owned_terminal')
        self.assertEqual(monitor.evidence()['status'], 'BLOCKED')
        self.assertEqual(monitor.evidence()['affinity_drift'][0]['observed_mask'], 255)

    def test_wrong_build_epoch_or_case_result_cannot_be_reused(self):
        frozen = dict(case='CodexMCMulti6230_N2_M0_NORMAL', mode=0, load='NORMAL', symbols=['USDJPY', 'EURUSD'])
        result = frozen | {'status': 'PASS'}
        validate_result_binding(result, frozen)
        for bad in (result | {'case': 'CodexMCMulti6182_N2_M0_NORMAL'},
                    result | {'mode': 2}, result | {'load': 'CPU_CONTENTION'},
                    result | {'symbols': ['USDJPY']}, result | {'status': 'BLOCKED'}):
            with self.assertRaises(ValueError):
                validate_result_binding(bad, frozen)

    def test_exact_symbol_groups_and_twelve_conditions(self):
        self.assertEqual(CASE_SYMBOLS[2], ('USDJPY', 'EURUSD'))
        self.assertEqual(CASE_SYMBOLS[3], ('USDJPY', 'EURUSD', 'EURJPY'))
        self.assertEqual(CASE_SYMBOLS[4], ('USDJPY', 'EURUSD', 'EURJPY', 'XAUUSD'))
        rows = build_cases()
        self.assertEqual(len(rows), 12)
        self.assertEqual({(r['count'], r['mode'], r['load']) for r in rows},
                         {(n, m, load) for n in (2, 3, 4) for m in (0, 2)
                          for load in ('NORMAL', 'CPU_CONTENTION')})

    def test_tester_copy_changes_only_symbol_selection(self):
        copied = selection_copy(ORIGINAL, CASE_SYMBOLS[3])
        old = dict(line.split('=', 1) for line in ORIGINAL.splitlines())
        new = dict(line.split('=', 1) for line in copied.splitlines())
        self.assertEqual({k: v for k, v in old.items() if k not in ('ScanMode', 'CustomSymbols')},
                         {k: v for k, v in new.items() if k not in ('ScanMode', 'CustomSymbols')})
        self.assertEqual(new['ScanMode'], '2||0||0||3||N')
        self.assertEqual(new['CustomSymbols'], 'USDJPY,EURUSD,EURJPY')
        self.assertEqual(old['ScanMode'], '0||0||0||3||N')

    def test_unknown_or_duplicate_selection_fields_fail_closed(self):
        with self.assertRaises(ValueError):
            selection_copy(ORIGINAL.replace('CustomSymbols=\n', ''), CASE_SYMBOLS[2])
        with self.assertRaises(ValueError):
            selection_copy(ORIGINAL + 'ScanMode=0||0||0||3||N\n', CASE_SYMBOLS[2])
        with self.assertRaises(ValueError):
            selection_copy(ORIGINAL, ('USDJPY', 'XAUUSD', 'USDJPY'))

    def test_config_retains_all_baseline_market_conditions(self):
        old = ('[Tester]\nExpert=old\\EA.ex5\nExpertParameters=original.set\nSymbol=USDJPY\n'
               'Period=M1\nOptimization=0\nModel=4\nFromDate=2026.09.14\nToDate=2026.09.19\n'
               'ForwardMode=0\nDeposit=100000\nCurrency=USD\nLeverage=1000\n'
               'ExecutionMode=0\nVisual=0\nUseLocal=1\nUseRemote=0\nUseCloud=0\n'
               'Report=old\nReplaceReport=0\nShutdownTerminal=1\n')
        new = frozen_config(old, 'new\\EA.ex5', 'testcopy.set', 'newreport')
        previous = dict(line.split('=', 1) for line in old.splitlines() if '=' in line)
        updated = dict(line.split('=', 1) for line in new.splitlines() if '=' in line)
        for key in previous.keys() - {'Expert', 'ExpertParameters', 'Report'}:
            self.assertEqual(updated[key], previous[key])
        self.assertEqual(updated['ExpertParameters'], 'testcopy.set')
        with self.assertRaises(ValueError):
            frozen_config(old.replace('Model=4', 'Model=0'), 'new\\EA.ex5', 'testcopy.set', 'newreport')

    def test_evidence_rejects_missing_symbols_shadow_and_tick_fields(self):
        names = CASE_SYMBOLS[2]
        good = {'symbols': {'USDJPY': {'shadow_callbacks': 3, 'quote_samples': 4},
                            'EURUSD': {'shadow_callbacks': 2, 'quote_samples': 5}},
                'simultaneous_shadow_active': 2, 'runtime_errors': 0,
                'numerical_mismatches': 0, 'queue_depth': 'UNKNOWN'}
        validate_case_evidence(good, names)
        for damaged in (
            good | {'symbols': {'USDJPY': good['symbols']['USDJPY']}},
            good | {'simultaneous_shadow_active': 1},
            good | {'queue_depth': 0},
            good | {'numerical_mismatches': 1},
            good | {'symbols': {'USDJPY': {'shadow_callbacks': 0, 'quote_samples': 4},
                                'EURUSD': good['symbols']['EURUSD']}},
        ):
            with self.assertRaises(ValueError):
                validate_case_evidence(damaged, names)

    def test_prepare_matrix_fails_on_source_or_set_drift(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)
            original = path / 'original.set'
            original.write_text(ORIGINAL, encoding='utf-16')
            bundle = path / 'bundle'
            bundle.mkdir()
            (bundle / 'EA.mq5').write_text('tester only', encoding='utf-8')
            (bundle / 'EA.ex5').write_bytes(b'ex5')
            old_config = ('[Tester]\nExpert=old\\EA.ex5\nExpertParameters=original.set\nSymbol=USDJPY\n'
                          'Period=M1\nOptimization=0\nModel=4\nFromDate=2026.09.14\nToDate=2026.09.19\n'
                          'ForwardMode=0\nDeposit=100000\nCurrency=USD\nLeverage=1000\n'
                          'ExecutionMode=0\nVisual=0\nUseLocal=1\nUseRemote=0\nUseCloud=0\n'
                          'Report=old\nReplaceReport=0\nShutdownTerminal=1\n')
            manifest = prepare_matrix(original, old_config, {0: bundle, 2: bundle}, path / 'native', path / 'evidence')
            self.assertEqual(len(manifest), 12)
            self.assertEqual(len({m['original_set_sha256'] for m in manifest}), 1)
            self.assertEqual(len({m['source_sha256']['EA.mq5'] for m in manifest}), 1)
            self.assertTrue(all(sha256(Path(m['config'])) == m['config_sha256'] and
                                sha256(Path(m['set_path'])) == m['selected_set_sha256'] for m in manifest))
            engine = path / 'terminal.exe'
            engine.write_bytes(b'build6230')
            hashes = {str(engine): sha256(engine)}
            rebuilt = prepare_matrix(original, old_config, {0: bundle, 2: bundle}, path / 'native',
                                     path / 'evidence6230', namespace='CodexMCMulti6230', engine_sha256=hashes)
            self.assertTrue(all(m['case'].startswith('CodexMCMulti6230_') for m in rebuilt))
            self.assertTrue(all(m['engine_sha256'] == hashes for m in rebuilt))
            self.assertTrue(set(m['config'] for m in manifest).isdisjoint(m['config'] for m in rebuilt))
            verify_engine(rebuilt[0])
            engine.write_bytes(b'different-build')
            with self.assertRaises(ValueError):
                verify_engine(rebuilt[0])
            original.write_text(ORIGINAL + 'RiskMode=0\n', encoding='utf-16')
            with self.assertRaises(ValueError):
                prepare_matrix(original, old_config, {0: bundle, 2: bundle}, path / 'native2', path / 'evidence2',
                               expected_set_sha256=manifest[0]['original_set_sha256'])

    def test_numeric_pairs_require_exact_bits_and_complete_coverage(self):
        base = dict(symbol='USDJPY', kind='SHADOW', cycle='1', samples='30', input_digest='FIXTURE',
                    actual_compared='1', actual_equal='1', equal_reference='1', sequence_exact='1',
                    sequence_errors='0', sequence_draws='20000000', operations='20000000',
                    risk_bits='3FF0000000000000', allowed='1', rng='123', candidate='4')
        rows = [base | {'mode': '0'}, base | {'mode': '2'}]
        self.assertEqual(validate_replay_rows(rows, 2), 2)
        for damaged in (rows[:1], [rows[0], rows[1] | {'risk_bits': '0'}],
                        [rows[0], rows[1] | {'sequence_exact': '0'}], [rows[0], rows[0]]):
            with self.assertRaises(ValueError):
                validate_replay_rows(damaged, 2)


if __name__ == '__main__':
    unittest.main()
