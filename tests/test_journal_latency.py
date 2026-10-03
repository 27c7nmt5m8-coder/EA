"""Journal timing remains observational and rejects incomplete attribution."""
import importlib
from pathlib import Path
import tempfile
import unittest

from tools.build_tester_pipeline import MAIN
from tools.build_tester_timer_latency import build as timer_build, STAGES


class JournalLatencyTest(unittest.TestCase):
    def module(self):
        return importlib.import_module('tools.build_tester_journal_latency')

    def fixture(self):
        module=self.module()
        root=dict(timer_id='1',server_s='123',start_wall_us='10',end_wall_us='410',
                  stage='journal_root',symbol='ALL',duration_us='350',total_us='400',calls='1')
        timers=[{k:v for k,v in root.items() if k!='calls'} | {'stage':s,'duration_us':str(v)}
                for s,v in zip(STAGES,(10,0,20,10,0,0,350,10))]
        summaries=[dict(stage='OnTimer',count='1',total_us='400',max_us='400',
                        recorded='1',unknown='0',bookkeeping_max_us='1')]
        summaries += [dict(stage=s,count='1',total_us=str(v),max_us=str(v),
                          recorded='1',unknown='0',bookkeeping_max_us='1')
                      for s,v in zip(STAGES,(10,0,20,10,0,0,350,10))]
        rows=[root, root | {'stage':'symbol_journal','symbol':'EURJPY','duration_us':'340'}]
        rows += [root | {'stage':s,'symbol':'EURJPY','duration_us':str(v)}
                 for s,v in zip(module.JOURNAL_STAGES,(1,2,3,4,320,1,2,3))]
        return rows,timers,summaries

    def test_reversible_journal_and_service_transforms_preserve_all_other_files(self):
        module=self.module()
        for mode in (0,2):
            with tempfile.TemporaryDirectory() as tmp:
                baseline=timer_build(Path(tmp)/'timer',mode,nested=True).parent
                measured=module.build(Path(tmp)/'journal',mode).parent
                altered={MAIN,'MT3TradeJournal.mqh','TesterTimerLatencyDiag.mqh'}
                for p in baseline.iterdir():
                    restored=module.restore_file(p.name,(measured/p.name).read_bytes()) if p.name in altered else (measured/p.name).read_bytes()
                    self.assertEqual(p.read_bytes(),restored,p.name)
                self.assertEqual({p.name for p in measured.iterdir()}-{p.name for p in baseline.iterdir()},
                                 {'TesterJournalLatencyDiag.mqh'})

    def test_long_journal_partition_is_attributed_without_double_counting(self):
        module=self.module()
        result=module.analyze_journal_trace(*self.fixture())
        self.assertEqual(result['maximum_journal_us'],350)
        self.assertEqual(result['dominant_symbol'],'EURJPY')
        self.assertEqual(result['dominant_phase'],'persist')
        self.assertEqual(result['unattributed_journal_us'],10)
        self.assertEqual(result['queue_depth'],'UNKNOWN')

    def test_missing_corrupt_duplicate_or_mixed_clock_evidence_is_rejected(self):
        module=self.module()
        rows,timers,summaries=self.fixture()
        variants=(rows[:-1], rows+[rows[-1]],
                  [r | {'duration_us':'999'} if r['stage']=='persist' else r for r in rows],
                  [r | {'server_s':'124'} if r['stage']=='persist' else r for r in rows],
                  [r | {'calls':'0'} if r['stage']=='persist' else r for r in rows],
                  [r | {'stage':'unexpected'} if r['stage']=='persist' else r for r in rows],
                  [r | {'duration_us':'NaN'} if r['stage']=='persist' else r for r in rows],
                  [r for r in rows if r['stage']!='journal_root'])
        for changed in variants:
            with self.subTest(changed=changed[-1]['stage']):
                with self.assertRaises(ValueError):module.analyze_journal_trace(changed,timers,summaries)

    def test_impossible_phase_count_sequences_are_rejected(self):
        module=self.module();rows,timers,summaries=self.fixture()
        for omitted in ('sample_guard','collect_ids','persist'):
            altered=[r | {'calls':'0','duration_us':'0'} if r['stage']==omitted else r for r in rows]
            with self.subTest(omitted=omitted):
                with self.assertRaises(ValueError):module.analyze_journal_trace(altered,timers,summaries)

    def test_unmeasured_symbol_parent_is_unknown_and_residual_is_visible(self):
        module=self.module();rows,timers,summaries=self.fixture()
        early=[r | {'duration_us':'0','calls':'1' if r['stage']=='sample_guard' else '0'}
               if r['stage'] in module.JOURNAL_STAGES else r for r in rows]
        result=module.analyze_journal_trace(early,timers,summaries)
        self.assertEqual(result['dominant_phase'],'UNKNOWN')
        self.assertEqual(result['symbol_unattributed_us']['EURJPY'],340)
        self.assertEqual(result['total_unpartitioned_journal_us'],350)


if __name__=='__main__':unittest.main()
