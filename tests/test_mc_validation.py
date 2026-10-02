"""Generator contract tests; native MQL compilation remains a separate gate."""
import importlib
import re
import tempfile
import unittest
from pathlib import Path

from tools.build_tester_mc_scheduler import build as scheduler_build
from tools.build_tester_pipeline import SOURCE, STATE, MAIN


class ValidationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = SOURCE.parent / 'tools/build_tester_mc_validation.py'
        if not path.exists():
            raise AssertionError('validation generator has not been implemented')
        cls.module = importlib.import_module('tools.build_tester_mc_validation')

    def test_modes_are_bounded_and_output_never_overwrites(self):
        before = {p.name: p.read_bytes() for p in SOURCE.iterdir() if p.is_file()}
        with tempfile.TemporaryDirectory() as td:
            states = {}
            for mode in (0, 2):
                out = Path(td) / str(mode)
                main = self.module.build(out, mode)
                states[mode] = (out / STATE).read_bytes()
                self.assertIn('if(!MQLInfoInteger(MQL_TESTER))', main.read_text(encoding='utf-8-sig'))
                with self.assertRaises(ValueError):
                    self.module.build(out, mode)
            self.assertEqual(states[0].replace(b'operations<20000', b'operations<500000'), states[2])
            for mode in (-1, 1, 3, 4, 5, 6):
                with self.assertRaises(ValueError):
                    self.module.build(Path(td) / ('bad' + str(mode)), mode)
        with self.assertRaises(ValueError):
            self.module.build(SOURCE / 'bad', 0)
        self.assertEqual(before, {p.name: p.read_bytes() for p in SOURCE.iterdir() if p.is_file()})

    def test_baseline_generator_keeps_original_output(self):
        with tempfile.TemporaryDirectory() as td:
            before = Path(td) / 'before'
            after = Path(td) / 'after'
            scheduler_build(before, 0)
            self.module.build(Path(td) / 'validation', 0)
            scheduler_build(after, 0)
            self.assertEqual({p.name: p.read_bytes() for p in before.iterdir()},
                             {p.name: p.read_bytes() for p in after.iterdir()})

    def test_update_mc_risk_core_retains_every_original_early_decision(self):
        # Any changed branch, threshold, seed/reset, history/expiry check or
        # return in the extracted request core must fail this exact comparison.
        # Bootstrap replay cannot cover the minimum-samples/win-rate returns.
        def body(text, declaration):
            start = text.index(declaration) + len(declaration)
            end = text.index('\ndatetime UTCNow()', start)
            return text[start:end]

        with tempfile.TemporaryDirectory() as td:
            baseline = Path(td) / 'baseline'
            scheduler_build(baseline, 0)
            original = (baseline / STATE).read_text(encoding='utf-8-sig')
            expected = body(original, 'void UpdateMonteCarloRisk(bool force=false,int tpmcPath=0)\n')
            self.assertTrue(expected.startswith('{\n'))
            self.assertTrue(expected.rstrip().endswith('}'))
            for mode in (0, 2):
                with self.subTest(mode=mode):
                    out = Path(td) / ('validation' + str(mode))
                    self.module.build(out, mode)
                    generated = (out / STATE).read_text(encoding='utf-8-sig')
                    actual = body(generated, 'void UpdateMonteCarloRiskCore(bool force=false,int tpmcPath=0)\n')
                    self.assertEqual(expected, actual)

    def test_generated_contract_preserves_numeric_core_and_times_all_returns(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / 'v'
            self.module.build(out, 2)
            state = (out / STATE).read_text(encoding='utf-8-sig')
            original = (SOURCE / STATE).read_text(encoding='utf-8-sig')
            a = '  double risk=MinimumRiskPercent+m_mcCandidate*MonteCarloRiskStep;'
            b = '  if(dd<=MonteCarloMaxDrawdownPercent*MonteCarloSafetyFactor || m_mcCandidate==0)'
            numeric = original[original.index(a):original.index(b, original.index(a))]
            actual = state[state.index(a, state.index('void AdvanceMonteCarloCore')):state.index(b, state.index('void AdvanceMonteCarloCore'))]
            actual = actual.replace('  m_tpbLastDD=dd;m_tpbDDSeen=true;MCSActualLevel(m_tpmcCycle,m_mcCandidate,dd,m_mcRandom);\n', '')
            self.assertEqual(numeric, actual)
            self.assertNotIn('MCVVerifyDraw', state)
            wrapper = state[state.index('void UpdateMonteCarloRisk('):state.index('void UpdateMonteCarloRiskCore(')]
            self.assertIn('UpdateMonteCarloRiskCore(force,tpmcPath);', wrapper)
            self.assertIn('MCVRequestEnd(', wrapper)
            self.assertNotIn('return;', wrapper)
            main = (out / MAIN).read_text(encoding='utf-8-sig')
            self.assertIn('EventSetMillisecondTimer(ScanTimerMilliseconds)', main)
            config = (out / 'MT3Config.mqh').read_text(encoding='utf-8-sig')
            self.assertIn('input int ScanTimerMilliseconds=1000;', config)
            self.assertIn('input int MonteCarloTimerBudgetMs=20;', config)
            self.assertIn('MonteCarloTimerBudgetMs', main)
            self.assertIn('MCVTickEnd(', main)
            replay = (out / 'TesterMCSchedulerCore.mqh').read_text(encoding='utf-8-sig')
            self.assertIn('MCVVerifyDraw(k);', replay)
            for mode in (0, 2):
                start = replay.index(a, replay.index('void Advance' + str(mode)))
                replay_numeric = replay[start:replay.index(b, start)]
                self.assertEqual(numeric, replay_numeric.replace('  MCVVerifyDraw(k);\n', '').replace('  Level(dd);\n', ''))
            for mode in (1, 3, 4, 5):
                self.assertNotIn('void Advance' + str(mode) + '(', replay)
            scheduler = (out / 'TesterMCSchedulerDiag.mqh').read_text(encoding='utf-8-sig')
            self.assertIn('s.operations==r.totalOperations', scheduler)
            self.assertIn('sampleIndex!=(int)(expected%(uint)ArraySize(m_mcReturns))', scheduler)

    def test_receipt_trace_and_exports_use_stable_unscoped_identity(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / 'v'
            self.module.build(out, 0)
            methods = (out / 'TesterMCSchedulerValidationMethods.mqh').read_text(encoding='utf-8-sig')
            self.assertIn('ScopeDigest(m_symbol+"/"+IntegerToString(bar)+"/"+signature)', methods)
            identity = methods[methods.index('string MCVIdentity'):methods.index('string MCVOwnedOpportunity')]
            self.assertNotIn('g_statePrefix', identity)
            canonical = (out / 'TesterBottleneckMethods.mqh').read_text(encoding='utf-8-sig')
            canonical_signature = canonical[canonical.index(' string signature;'):canonical.index(' string id=ScopeDigest')]
            validation_signature = identity[identity.index(' string signature;'):identity.index(' return ScopeDigest')]
            self.assertEqual(re.sub(r'\s+', '', canonical_signature), re.sub(r'\s+', '', validation_signature))
            patterns = (out / 'MT3ReversalPatterns.mqh').read_text(encoding='utf-8-sig')
            self.assertIn('MCVGuard(p,"RECEIPT"', patterns)
            self.assertIn('MCVGuard(p,"LEGACY"', patterns)
            self.assertIn('MCVClaim(p,ids[i]);', patterns)
            header = (out / 'TesterMCSchedulerValidation.mqh').read_text(encoding='utf-8-sig')
            self.assertIn('"UNKNOWN","UNKNOWN","UNKNOWN"', header)
            self.assertIn('"enqueue_latency_us"', header)
            self.assertIn('"p99_us"', (out / 'TesterMCSchedulerDiag.mqh').read_text(encoding='utf-8-sig'))
            for p in out.glob('Tester*.mqh'):
                self.assertNotIn('CodexMCSched', p.read_text(encoding='utf-8-sig'))

    def test_no_request_and_non_order_observations_use_compact_storage(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / 'v'
            self.module.build(out, 0)
            state = (out / STATE).read_text(encoding='utf-8-sig')
            self.assertIn('if(m_tpmcCycle!=r.before.cycle) {m_mcvLastRequestInput=', state)
            self.assertIn('MCVManageEnd(started,finished,server);', state)
            self.assertEqual(state.count('MCVTimingAppend('), 1)
            header = (out / 'TesterMCSchedulerValidation.mqh').read_text(encoding='utf-8-sig')
            self.assertIn('if(!r.force && r.before.cycle==after.cycle)', header)
            self.assertIn('MCVDuration(g_mcvNoRequestUs,r.elapsed)', header)
            self.assertNotIn('g_mcvGuards[i].bar<bar', header)
            self.assertIn('g_mcvGuards[i].id==id && g_mcvGuards[i].reason==reason && g_mcvGuards[i].bar==bar', header)

    def test_duration_capacity_retains_frozen_matrix_samples_without_raising_record_limits(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / 'v'
            self.module.build(out, 0)
            header = (out / 'TesterMCSchedulerValidation.mqh').read_text(encoding='utf-8-sig')
            self.assertIn('const int MCV_DURATION_LIMIT=3000000;', header)
            self.assertIn('int MCV_LIMIT=2000000;', header)
            self.assertEqual(header.count('MCV_DURATION_LIMIT'), 2)
            duration = header[header.index('void MCVDuration('):header.index('void MCVRequestEnd(')]
            # Store every raw duration, with allocation/capacity failures still
            # observable. No sampling, binning or silent truncation is allowed.
            self.assertIn('if(n>=MCV_DURATION_LIMIT || ArrayResize(values,n+1,8192)!=n+1) {g_mcvUnknown++;return;}', duration)
            self.assertIn('values[n]=duration;', duration)
            self.assertNotIn('n>=MCV_LIMIT', duration)
            self.assertEqual(header.count('n>=MCV_LIMIT'), 4)
            # The largest frozen case needs 2,484,032 samples; 3m provides at
            # least 20 percent headroom without changing other record storage.
            limit = int(re.search(r'const int MCV_DURATION_LIMIT=(\d+);', header).group(1))
            self.assertGreaterEqual(limit, 2484032 * 1.2)
            self.assertEqual(limit * 8, 24000000)

    def test_account_redaction_is_confined_to_analytical_serialization(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / 'v'
            self.module.build(out, 2)
            log = (out / 'MT3TradeLog.mqh').read_text(encoding='utf-8-sig')
            original = (SOURCE / 'MT3TradeLog.mqh').read_text(encoding='utf-8-sig')
            self.assertIn('CodexMCV2_20260927_TradeLogs', log)
            self.assertIn('JsonQuote("REDACTED_TESTER_ACCOUNT")', log)
            self.assertIn('LogCSVAdd(h,row,"Account","REDACTED_TESTER_ACCOUNT",true);', log)
            self.assertIn('if(MQLInfoInteger(MQL_TESTER) && r.account=="REDACTED_TESTER_ACCOUNT") r.account=g_account;', log)
            self.assertIn('return r.account==g_account && r.magic==MagicNumber;', log)
            # Undo only the four documented reporting edits: every other byte
            # of the analytical parser/serializer must retain product behavior.
            restored = log.replace('CodexMCV2_20260927_TradeLogs', 'MT3Logs_v244')
            restored = restored.replace('JsonQuote("REDACTED_TESTER_ACCOUNT")', 'JsonQuote(r.account)')
            restored = restored.replace('LogCSVAdd(h,row,"Account","REDACTED_TESTER_ACCOUNT",true);', 'LogCSVAdd(h,row,"Account",r.account,true);')
            restored = restored.replace('\n if(MQLInfoInteger(MQL_TESTER) && r.account=="REDACTED_TESTER_ACCOUNT") r.account=g_account;', '')
            self.assertEqual(original, restored)
            for name in ('MT3TradeJournal.mqh', 'MT3AIProtocol.mqh', 'MT3Config.mqh'):
                self.assertEqual((SOURCE / name).read_bytes(), (out / name).read_bytes())

    def test_privacy_roundtrip_runs_only_after_test_and_exports_no_record(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / 'v'
            self.module.build(out, 0)
            main = (out / MAIN).read_text(encoding='utf-8-sig')
            before, on_tester = main.split('double OnTester()', 1)
            self.assertNotIn('MCVPrivacySelfTest()', before)
            self.assertIn('MCVPrivacySelfTest()', on_tester)
            header = (out / 'TesterMCSchedulerValidation.mqh').read_text(encoding='utf-8-sig')
            test = header[header.index('bool MCVPrivacySelfTest()'):header.index('void MCVExport()')]
            self.assertIn('ParseTradeRecord(json,restored)', test)
            self.assertIn('TradeRecordJSON(restored)==json', test)
            self.assertIn('restored.account==g_account', test)
            self.assertIn('restored.dataset==TradeLogRoot()', test)
            self.assertIn('!ParseTradeRecord(TradeRecordJSON(wrongMagic),rejected)', test)
            self.assertNotIn('FileWrite(', test)
            self.assertNotIn('WriteAIFile(', test)
            self.assertEqual(test.count('Print('), 1)
            self.assertIn('Print("TESTER_MC_PRIVACY_SELFTEST ",ok?"PASS":"FAIL")', test)


if __name__ == '__main__':
    unittest.main()
