"""Portable checks of actual retained timing evidence; no native processes."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.analyze_mc_multisymbol import require_export
from tools.build_tester_journal_io import build, analyze_io_trace
from tools.build_tester_journal_latency import analyze_journal_trace
from tools.build_tester_timer_latency import analyze_timer_trace
from tools.mc_multisymbol_runner import validate_replay_rows, validate_result_binding

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT/'verification/mc_journal_io_20261003_r1'
CASE = 'CodexMCMultiJournalIO20261003R1_N3_M2_NORMAL'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


class FrozenTimerEvidenceTest(unittest.TestCase):
    def test_generated_current_and_500k_sources_match_compiled_hashes(self):
        manifest = load(EVIDENCE/'matrix/manifest.json')
        self.assertEqual(len(manifest), 4)
        self.assertEqual({(c['count'],c['mode'],c['load']) for c in manifest},
                         {(3,m,load) for m in (0,2) for load in ('NORMAL','CPU_CONTENTION')})
        for mode in (0,2):
            with tempfile.TemporaryDirectory() as temp:
                directory = build(Path(temp)/'generated',mode).parent
                case = next(c for c in manifest if c['mode']==mode)
                for name, expected in case['source_sha256'].items():
                    data = (directory/name).read_bytes()
                    if name=='TesterMCSchedulerValidation.mqh':
                        self.assertEqual(data.count(b'MCV_DURATION_LIMIT=12000000'),1)
                        data = data.replace(b'MCV_DURATION_LIMIT=12000000',b'MCV_DURATION_LIMIT=3000000')
                    self.assertEqual(hashlib.sha256(data).hexdigest(),expected,(mode,name))

    def test_retained_native_partition_analysis_is_exactly_reproducible(self):
        directory = EVIDENCE/'native'/CASE
        result = load(directory/'result.json')
        manifest = load(EVIDENCE/'matrix/manifest.json')
        validate_result_binding(result,next(c for c in manifest if c['case']==CASE))
        timers = require_export(directory,result,'_timer_sections.csv')
        summaries = require_export(directory,result,'_timer_summary.csv')
        journal = require_export(directory,result,'_journal_sections.csv')
        io = require_export(directory,result,'_journal_io.csv')
        expected = load(EVIDENCE/'analysis.json')
        self.assertEqual(analyze_timer_trace(timers,summaries),expected['timer'])
        self.assertEqual(analyze_journal_trace(journal,timers,summaries),expected['journal'])
        self.assertEqual(analyze_io_trace(io,journal,timers,summaries),expected['io'])

    def test_fresh_completed_numeric_evidence_has_no_mismatch(self):
        directory = EVIDENCE/'native'/CASE
        result,attempt = load(directory/'result.json'),load(directory/'attempt.json')
        self.assertEqual(attempt['status'],'COLLECTABLE')
        self.assertEqual(attempt['exit_code'],0)
        self.assertEqual((result['runtime_errors'],result['warnings']),(0,0))
        replay = require_export(directory,result,'_replay.csv')
        self.assertEqual(validate_replay_rows(replay,int(result['scheduler']['comparisons'])),
                         result['actual_replay_rows'])


if __name__=='__main__':
    unittest.main()
