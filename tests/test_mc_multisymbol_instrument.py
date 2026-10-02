"""Contracts for the isolated multi-symbol MC Tester build."""
import tempfile
import unittest
import re
from pathlib import Path

from tools.build_tester_pipeline import SOURCE, MAIN, STATE


class MultiInstrumentTest(unittest.TestCase):
    def test_four_symbol_duration_capture_does_not_repeat_observed_overflow(self):
        from tools.build_tester_mc_multisymbol import build
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / 'multi'
            build(out, 0)
            header = (out / 'TesterMCSchedulerValidation.mqh').read_text(encoding='utf-8')
        capacity = int(re.search(r'MCV_DURATION_LIMIT=(\d+);', header).group(1))
        self.assertGreaterEqual(capacity, 3_241_875)
        self.assertLessEqual(capacity, 4 * 3_000_000)
        self.assertIn('n>=MCV_DURATION_LIMIT', header)

    def test_generated_identity_shadow_and_source_isolation(self):
        from tools.build_tester_mc_multisymbol import build
        before = {p.name: p.read_bytes() for p in SOURCE.iterdir() if p.is_file()}
        with tempfile.TemporaryDirectory() as td:
            for mode in (0, 2):
                out = Path(td) / str(mode)
                build(out, mode)
                scheduler = (out / 'TesterMCSchedulerDiag.mqh').read_text(encoding='utf-8-sig')
                state = (out / STATE).read_text(encoding='utf-8-sig')
                main = (out / MAIN).read_text(encoding='utf-8-sig')
                multi = (out / 'TesterMCMultiDiag.mqh').read_text(encoding='utf-8-sig')
                self.assertIn('MCSFind(const string symbol,const string kind,const int cycle)', scheduler)
                self.assertIn('MCSFind(symbol,kind,cycle)', scheduler)
                self.assertIn('MCS_RECORD_LIMIT=3000000', scheduler)
                self.assertIn('n>=MCS_RECORD_LIMIT', scheduler)
                self.assertIn('MCSCapture(m_symbol,"ACTUAL",m_tpmcCycle', state)
                self.assertIn('MCSActualCallback(m_symbol,"ACTUAL",m_tpmcCycle', (out / 'TesterMCTimelineMethods.mqh').read_text(encoding='utf-8-sig'))
                self.assertIn('MCMArm();', main)
                self.assertIn('MCMService(deadline);', main)
                self.assertLess(main.index('g_symbols[i].AdvanceMonteCarlo(deadline)'), main.index('MCMService(deadline);'))
                self.assertLess(main.index('MCMService(deadline);'), main.index('DispatchQueue();'))
                self.assertIn('MCSReplay g_mcmShadow[4]', multi)
                self.assertIn('MCMOverlapActive()', multi)
                self.assertIn('r.Advance0(deadline)', multi)
                self.assertIn('r.Advance2(deadline)', multi)
                self.assertNotIn('g_symbols[', multi)
                self.assertNotIn('g_returns', multi)
                self.assertNotIn('GlobalVariableSet', multi)
                self.assertIn('MCMExport();', main)
                self.assertIn('MCMValidationStatus()', multi)
                status = multi[multi.index('string MCMValidationStatus()'):multi.index('int MCMCompletedCount()')]
                self.assertNotIn('g_mcmNaturalOverlapUs==0', status)
                self.assertIn('g_mcmOverlapEnd<=g_mcmOverlapStart', status)
                self.assertIn('MCM_ARM_LIMIT=600', multi)
                self.assertIn('"UNKNOWN",(double)overlap', multi)
                self.assertIn('"input_arrivals"', multi)
                self.assertIn('"queue_depth","broker_latency"', multi)
                self.assertIn('"symbol","kind","cycle","server_start_s"', scheduler)
                with self.assertRaises(ValueError):
                    build(out, mode)
        self.assertEqual(before, {p.name: p.read_bytes() for p in SOURCE.iterdir() if p.is_file()})

    def test_changed_source_anchor_fails_closed(self):
        from tools.build_tester_mc_multisymbol import qualify_scheduler
        with self.assertRaisesRegex(ValueError, 'anchor'):
            qualify_scheduler('changed')


if __name__ == '__main__':
    unittest.main()
