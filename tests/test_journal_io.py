"""Atomic write observation preserves exact I/O and short-circuit behavior."""
import importlib
from pathlib import Path
import tempfile
import unittest
from tests import test_journal_latency as fixtures
from tools.build_tester_pipeline import MAIN
from tools.build_tester_journal_latency import build as journal_build


class JournalIOTest(unittest.TestCase):
    def module(self):return importlib.import_module('tools.build_tester_journal_io')

    def fixture(self):
        module=self.module()
        journal,timers,summaries=fixtures.JournalLatencyTest().fixture()
        root=journal[1]
        io=[root | {'stage':s,'duration_us':str(value),'calls':str(count)}
            for s,value,count in zip(module.IO_STAGES,(5,4,1,3,2,300,1,1,0,308),(1,1,2,2,2,2,2,2,0,2))]
        return io,journal,timers,summaries

    def test_all_generated_files_restore_and_original_protocol_remains_identical(self):
        module=self.module()
        for mode in (0,2):
            with tempfile.TemporaryDirectory() as tmp:
                base=journal_build(Path(tmp)/'journal',mode).parent
                output=module.build(Path(tmp)/'io',mode).parent
                for p in base.iterdir():
                    self.assertEqual(p.read_bytes(),module.restore_file(p.name,(output/p.name).read_bytes()),p.name)
                original=(base/'MT3AIProtocol.mqh').read_bytes()
                self.assertEqual(original,(output/'MT3AIProtocol.mqh').read_bytes())
                core=module.atomic_function(original)
                self.assertEqual(core,module.restore_atomic_function((output/'TesterJournalIOLatencyDiag.mqh').read_bytes()))

    def test_synchronous_flush_is_attributed_with_correct_parent_bounds(self):
        result=self.module().analyze_io_trace(*self.fixture())
        self.assertEqual(result['dominant_io_stage'],'flush')
        self.assertEqual(result['dominant_io_us'],300)
        self.assertEqual(result['persist_unpartitioned_us'],3)
        self.assertEqual(result['flush_success_status'],'UNKNOWN_VOID_RETURN')

    def test_missing_overlapping_or_impossible_call_counts_are_rejected(self):
        module=self.module();rows,journal,timers,summaries=self.fixture()
        for changed in (rows[:-1],rows+[rows[-1]],
                        [r | {'duration_us':'400'} if r['stage']=='flush' else r for r in rows],
                        [r | {'calls':'3'} if r['stage']=='flush' else r for r in rows],
                        [r | {'calls':'3'} if r['stage']=='serialize_csv' else r for r in rows],
                        [r | {'stage':'unknown'} if r['stage']=='flush' else r for r in rows]):
            with self.assertRaises(ValueError):module.analyze_io_trace(changed,journal,timers,summaries)

    def test_completed_atomic_outcomes_must_match_short_circuit_counts(self):
        module=self.module();rows,journal,timers,summaries=self.fixture()
        variants=(
            [r | {'calls':'0','duration_us':'0'} if r['stage'] in ('move','delete') else r for r in rows],
            [r | {'duration_us':'0'} | ({'calls':'2'} if r['stage']=='delete' else {}) for r in rows],
            [r | {'calls':'0','duration_us':'0'} if r['stage']=='serialize_csv' else
             r | {'calls':'1'} if r['stage'] not in ('serialize_json','delete') else r for r in rows],
        )
        for index,changed in enumerate(variants):
            with self.subTest(index=index):
                with self.assertRaises(ValueError):module.analyze_io_trace(changed,journal,timers,summaries)

    def test_unvisited_persist_cannot_have_io_calls_even_with_zero_duration(self):
        module=self.module();rows,journal,timers,summaries=self.fixture()
        early=[r | {'duration_us':'0','calls':'1' if r['stage']=='sample_guard' else '0'}
               if r['stage'] in fixtures.JournalLatencyTest().module().JOURNAL_STAGES else r for r in journal]
        rows=[r | {'duration_us':'0'} for r in rows]
        with self.assertRaises(ValueError):module.analyze_io_trace(rows,early,timers,summaries)

    def test_success_and_failure_atomic_paths_remain_valid(self):
        module=self.module();rows,journal,timers,summaries=self.fixture()
        # JSON conversion/open/short-write/move failure; then CSV open/write failure,
        # both writes succeeding, and a persist visit with no dirty records.
        for counts in ((1,0,1,0,0,0,0,0,0,1),(1,0,1,1,0,0,0,0,0,1),
                       (1,0,1,1,1,1,1,0,1,1),(1,0,1,1,1,1,1,1,1,1),
                       (1,1,2,2,1,1,1,1,0,2),(1,1,2,2,2,2,2,1,1,2),
                       (1,1,2,2,2,2,2,2,0,2),(0,)*10):
            altered=[r | {'calls':str(n),'duration_us':'0'} for r,n in zip(rows,counts)]
            with self.subTest(counts=counts):module.analyze_io_trace(altered,journal,timers,summaries)


if __name__=='__main__':unittest.main()
