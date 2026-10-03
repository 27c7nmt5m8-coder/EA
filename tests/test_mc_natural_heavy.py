"""Explicit natural-history window and ACTUAL-only overlap contracts."""
import tempfile
import unittest
from pathlib import Path
from tools import mc_multisymbol_runner as runner
from tools.mc500k_batch import FIELDS, FIXED
from tools.analyze_mc_natural_heavy import natural_overlap


def config(start='2026.06.01', end='2026.06.13'):
    values = dict(FIXED, Expert='old\\EA.ex5', ExpertParameters='old.set',
                  Symbol='USDJPY', FromDate=start, ToDate=end, Report='old')
    return '[Tester]\n' + '\n'.join(k+'='+values[k] for k in FIELDS)+'\n'


class NaturalWindowTest(unittest.TestCase):
    def test_june_requires_explicit_contract_and_preserves_baseline(self):
        with self.assertRaises(ValueError):
            runner.frozen_config(config(), 'new\\EA.ex5', 'new.set', 'new')
        text = runner.frozen_config(config(), 'new\\EA.ex5', 'new.set', 'new',
                                    market_window='JUNE_NATURAL')
        before = dict(x.split('=', 1) for x in config().splitlines() if '=' in x)
        after = dict(x.split('=', 1) for x in text.splitlines() if '=' in x)
        for key in before.keys() - {'Expert', 'ExpertParameters', 'Report'}:
            self.assertEqual(before[key], after[key])

    def test_unknown_or_mixed_window_is_rejected(self):
        for text, window in ((config(), 'UNKNOWN'), (config(end='2026.06.14'), 'JUNE_NATURAL'),
                             (config(start='2026.09.14', end='2026.09.19'), 'JUNE_NATURAL')):
            with self.assertRaises(ValueError):
                runner.frozen_config(text, 'new\\EA.ex5', 'new.set', 'new', market_window=window)

    def test_export_prefix_is_bound_to_verified_config_and_window(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/'case.ini'
            path.write_bytes(config().encode())
            case = dict(config=str(path), config_sha256=runner.sha256(path), mode=2,
                        market_window='JUNE_NATURAL')
            self.assertEqual(runner.expected_export_prefix(case),
                             'CodexMCV2_20260927_USDJPY_2026.06.01_A2.60_S0.40')
            with self.assertRaises(ValueError):
                runner.expected_export_prefix(case | {'market_window': 'SEPTEMBER_BASELINE'})
            path.write_bytes(config(end='2026.06.14').encode())
            with self.assertRaises(ValueError):
                runner.expected_export_prefix(case)

    def test_normal_june_matrix_has_only_four_conditions(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            original = root/'original.set'
            original.write_bytes('ScanMode=0||0||0||3||N\nCustomSymbols=\n'.encode('utf-16'))
            bundle = root/'bundle'; bundle.mkdir()
            (bundle/'EA.mq5').write_bytes(b'tester fixture')
            (bundle/'EA.ex5').write_bytes(b'fixture only')
            manifest = runner.prepare_matrix(original, config(), {0: bundle, 2: bundle},
                root/'native', root/'matrix', counts=(3, 4), loads=('NORMAL',),
                market_window='JUNE_NATURAL')
            self.assertEqual(len(manifest), 4)
            self.assertEqual({(c['count'], c['mode'], c['load']) for c in manifest},
                             {(n, m, 'NORMAL') for n in (3, 4) for m in (0, 2)})
            self.assertTrue(all(c['market_window']=='JUNE_NATURAL' for c in manifest))
            for c in manifest:
                self.assertIn('2026.06.01', runner.expected_export_prefix(c))

    def test_launch_preflight_rejects_forbidden_june_load_and_universe(self):
        case=dict(market_window='JUNE_NATURAL', count=3, symbols=list(runner.CASE_SYMBOLS[3]),
                  mode=2, load='NORMAL')
        runner.validate_case_contract(case)
        for damaged in (case | {'load':'CPU_CONTENTION'}, case | {'mode':3},
                        case | {'count':2,'symbols':list(runner.CASE_SYMBOLS[2])},
                        case | {'symbols':['USDJPY']}, case | {'market_window':'UNKNOWN'}):
            with self.assertRaises(ValueError):
                runner.verify_staged(damaged)

    def test_june_result_cannot_reuse_legacy_september_success(self):
        case=dict(case='fixture', mode=2, load='NORMAL', symbols=list(runner.CASE_SYMBOLS[3]),
                  market_window='JUNE_NATURAL')
        result=case | {'status':'PASS'}
        runner.validate_result_binding(result,case)
        del result['market_window']
        with self.assertRaises(ValueError):runner.validate_result_binding(result,case)


def fixture(symbol, start, end, terminal='COMPLETE'):
    base = dict(symbol=symbol, cycle='1', parent='0', trigger='INITIAL',
                input_version='1', history_version='1', state_version='1',
                samples='30', input_digest='FIXTURE', win_rate='0.50')
    events = [base | dict(event=kind, seq=str(i+1), wall_us=str(wall), server_s='100')
              for i, (kind, wall) in enumerate((('REQUEST', start-1), ('START', start), (terminal, end)))]
    snap = dict(symbol=symbol, kind='ACTUAL', cycle='1', samples='30', input_digest='FIXTURE',
                input_version='1', history_version='1', completed='1' if terminal=='COMPLETE' else '0',
                start_wall_us=str(start+1), end_wall_us=str(end-1) if terminal=='COMPLETE' else '0')
    return events, snap


class NaturalOverlapTest(unittest.TestCase):
    def data(self, specs):
        events, snapshots = [], []
        for spec in specs:
            rows, snapshot = fixture(*spec); events.extend(rows); snapshots.append(snapshot)
        events.sort(key=lambda e:int(e['wall_us']))
        for i,e in enumerate(events): e['seq']=str(i+1)
        return events, snapshots

    def test_three_actual_symbols_require_positive_execution_clock_overlap(self):
        events, snapshots = self.data([('USDJPY', 10, 40), ('EURUSD', 20, 50), ('EURJPY', 30, 60)])
        result = natural_overlap(events, snapshots, runner.CASE_SYMBOLS[3])
        self.assertEqual(result['maximum_active_symbols'], 3)
        self.assertEqual(result['target_overlap_us'], 9)
        self.assertEqual(result['completed_overlap'], 'OBSERVED')

    def test_equal_market_time_and_touching_intervals_do_not_prove_overlap(self):
        events, snapshots = self.data([('USDJPY', 10, 20), ('EURUSD', 20, 30), ('EURJPY', 30, 40)])
        result = natural_overlap(events, snapshots, runner.CASE_SYMBOLS[3])
        self.assertEqual(result['target_overlap_us'], 0)
        self.assertEqual(result['completed_overlap'], 'UNOBSERVED')

    def test_censored_prefix_is_not_completed_coverage(self):
        events, snapshots = self.data([('USDJPY', 10, 40), ('EURUSD', 20, 50), ('EURJPY', 30, 60, 'RUN_END')])
        result = natural_overlap(events, snapshots, runner.CASE_SYMBOLS[3])
        self.assertEqual(result['simultaneous_activity'], 'OBSERVED')
        self.assertEqual(result['completed_overlap'], 'PARTIAL')

    def test_shadow_does_not_supply_missing_actual_symbol(self):
        events, snapshots = self.data([('USDJPY', 10, 40), ('EURUSD', 20, 50)])
        snapshots.append(dict(symbol='EURJPY', kind='SHADOW', cycle='1'))
        result = natural_overlap(events, snapshots, runner.CASE_SYMBOLS[3])
        self.assertEqual(result['completed_overlap'], 'UNOBSERVED')

    def test_input_mismatch_missing_snapshot_or_bad_clock_is_rejected(self):
        events, snapshots = self.data([('USDJPY', 10, 40)])
        for damaged in ([], [snapshots[0] | {'input_digest': 'OTHER'}],
                        [snapshots[0] | {'completed': '0'}]):
            with self.assertRaises(ValueError):
                natural_overlap(events, damaged, runner.CASE_SYMBOLS[3])
        events[-1]['wall_us']='5'
        with self.assertRaises(ValueError):
            natural_overlap(events, snapshots, runner.CASE_SYMBOLS[3])

    def test_independent_clocks_and_duplicate_global_sequence_are_rejected(self):
        events, snapshots = self.data([('USDJPY', 10, 40), ('EURUSD', 20, 50), ('EURJPY', 30, 60)])
        mixed = sorted(events, key=lambda e:e['symbol'])
        with self.assertRaises(ValueError):
            natural_overlap(mixed, snapshots, runner.CASE_SYMBOLS[3])
        events[2]['seq']=events[1]['seq']
        with self.assertRaises(ValueError):
            natural_overlap(events, snapshots, runner.CASE_SYMBOLS[3])

    def test_later_completion_marker_does_not_extend_calculation(self):
        events, snapshots = self.data([('USDJPY', 10, 40), ('EURUSD', 20, 50), ('EURJPY', 30, 60)])
        snapshots[0]['end_wall_us']='25'
        result=natural_overlap(events, snapshots, runner.CASE_SYMBOLS[3])
        self.assertEqual(result['target_overlap_us'], 0)
        self.assertEqual(result['completed_overlap'], 'UNOBSERVED')

    def test_low_nonfinite_or_changed_win_rate_cannot_manufacture_heavy(self):
        for rate in ('0.01', 'nan', 'inf', '1.01'):
            events, snapshots = self.data([('USDJPY', 10, 40)])
            for row in events:row['win_rate']=rate
            with self.assertRaises(ValueError):
                natural_overlap(events, snapshots, runner.CASE_SYMBOLS[3])
        events, snapshots = self.data([('USDJPY', 10, 40)])
        events[1]['win_rate']='0.60'
        with self.assertRaises(ValueError):
            natural_overlap(events, snapshots, runner.CASE_SYMBOLS[3])

    def test_three_active_in_four_symbol_universe_is_not_four_symbol_coverage(self):
        events, snapshots = self.data([('EURUSD', 10, 40), ('EURJPY', 20, 50), ('XAUUSD', 30, 60)])
        result=natural_overlap(events,snapshots,runner.CASE_SYMBOLS[4])
        self.assertEqual(result['completed_overlap'],'UNOBSERVED')
        self.assertEqual(result['overlap_by_cardinality']['3']['duration_us'],9)
        self.assertEqual(result['overlap_by_cardinality']['4']['duration_us'],0)
        witness=result['overlap_by_cardinality']['3']['witnesses'][0]
        self.assertEqual({c['symbol'] for c in witness['cycles']},{'EURUSD','EURJPY','XAUUSD'})


if __name__ == '__main__':
    unittest.main()
