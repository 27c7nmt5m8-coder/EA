import tempfile
import unittest
from pathlib import Path


class StartupScanTests(unittest.TestCase):
    def module(self):
        from tools import build_tester_startup_scan
        return build_tester_startup_scan

    def test_detailed_transform_restores_every_baseline_byte(self):
        from tools.build_tester_journal_io import build as baseline
        from tools.build_tester_pipeline import SOURCE
        before={p.name:p.read_bytes() for p in SOURCE.iterdir() if p.is_file()}
        with tempfile.TemporaryDirectory() as tmp:
            a=baseline(Path(tmp)/'minimal',0).parent
            b=self.module().build(Path(tmp)/'detailed',0).parent
            for p in a.iterdir():
                self.assertEqual(self.module().restore_file(p.name,(b/p.name).read_bytes()),p.read_bytes(),p.name)
            self.assertEqual(set(p.name for p in b.iterdir())-set(p.name for p in a.iterdir()),{'TesterStartupScanDiag.mqh'})
        self.assertEqual(before,{p.name:p.read_bytes() for p in SOURCE.iterdir() if p.is_file()})

    def test_rejects_overlapping_children_and_unknown_fields(self):
        m=self.module()
        root=dict(span_id='1',parent_id='0',timer_id='1',server_s='10',symbol='ALL',context='ACTUAL',section='timer',start_wall_us='100',end_wall_us='200',duration_us='100',timeframe='0',detail='0',result='0')
        child=dict(root,span_id='2',parent_id='1',symbol='USDJPY',section='scan',start_wall_us='110',end_wall_us='190',duration_us='80')
        self.assertEqual(m.analyze_spans([root,child])['timer_count'],1)
        with self.assertRaises(ValueError):m.analyze_spans([root,dict(child,parent_id='9')])
        with self.assertRaises(ValueError):m.analyze_spans([root,child,dict(child,span_id='3')])
        with self.assertRaises(ValueError):m.analyze_spans([dict(root,section='unexpected')])
        with self.assertRaises(ValueError):m.analyze_spans([root,dict(root,span_id='2')])
        with self.assertRaises(ValueError):m.analyze_spans([root,child,dict(child,span_id='3',parent_id='2',symbol='EURJPY')])

    def test_nested_child_durations_are_not_double_counted(self):
        m=self.module()
        def row(i,p,stage,s,e):
            return dict(span_id=str(i),parent_id=str(p),timer_id='1',server_s='10',symbol='ALL' if i==1 else 'USDJPY',context='ACTUAL',section=stage,start_wall_us=str(s),end_wall_us=str(e),duration_us=str(e-s),timeframe='0',detail='0',result='1')
        r=m.analyze_spans([row(1,0,'timer',100,300),row(2,1,'scan',110,290),row(3,2,'analyze_tf',120,280),row(4,3,'handle_access',130,250)])
        self.assertEqual(r['exclusive_us']['timer'],20)
        self.assertEqual(r['exclusive_us']['scan'],20)
        self.assertEqual(sum(r['exclusive_us'].values()),200)

    def test_instrumentation_is_bounded_and_has_no_event_handler_file_io(self):
        h=Path('tools/TesterStartupScanDiag.mqh').read_text(encoding='utf-8')
        self.assertIn('SC_LIMIT=32768',h)
        self.assertIn('timer>100',h)
        self.assertNotIn('Sleep(',h)
        self.assertNotIn('FileWrite(',h.split('void SCExport()')[0])
        self.assertIn('MQL_TESTER',h)

    def test_scan_subtree_excludes_same_timer_siblings(self):
        from tools.analyze_startup_scan import scan_subtree
        rows=[dict(span_id=1,parent_id=0),dict(span_id=2,parent_id=1),
              dict(span_id=3,parent_id=2),dict(span_id=4,parent_id=1)]
        self.assertEqual([r['span_id'] for r in scan_subtree(rows,2)],[2,3])

    def test_phase_statistics_must_match_measured_roots(self):
        from tools.analyze_startup_scan import validate_phase_roots
        roots={i:dict(duration_us=i*10) for i in range(1,101)}
        phases=dict(STARTUP=dict(count=4,total_us=100,median_us=25,p95_us=38.5,p99_us=39.7,max_us=40),
                    WARMUP=dict(count=96,total_us=50400,median_us=525,p95_us=952.5,p99_us=990.5,max_us=1000))
        validate_phase_roots(phases,roots)
        phases['STARTUP']['median_us']=30
        with self.assertRaises(ValueError):validate_phase_roots(phases,roots)

    def test_attempt_and_observer_binding_are_required(self):
        from tools.analyze_startup_scan import validate_observation_binding
        from tools.mc_isolated_contention import tooling_hashes
        case=dict(case='fixture',mode=0,load='NORMAL',profile_sha256={'chart':'fictional'})
        attempt=dict(case,diagnostic_tool_sha256=tooling_hashes(),status='COLLECTABLE',exit_code=0)
        observed=dict(comparison_eligible=True,overhead_status='ACCEPTABLE')
        result=dict(case,status='PASS')
        validate_observation_binding(case,result,attempt,observed)
        for bad in (dict(attempt,case='other'),dict(attempt,profile_sha256={}),dict(attempt,diagnostic_tool_sha256={})):
            with self.assertRaises(ValueError):validate_observation_binding(case,result,bad,observed)
        with self.assertRaises(ValueError):validate_observation_binding(case,result,attempt,dict(observed,overhead_status='UNKNOWN'))

    def test_archived_startup_maxima_conserve_each_timer(self):
        import json
        cases=json.loads(Path('verification/mc_startup_scan_20261004/first_scans.json').read_text(encoding='utf-8'))
        self.assertEqual(len(cases),2)
        for case in cases:
            parsed=self.module().analyze_spans(case['rows'])
            self.assertEqual(parsed['timer_count'],1)
            self.assertEqual(parsed['span_count'],case['span_count'])
            self.assertEqual(sum(parsed['exclusive_us'].values()),sum(r['duration_us'] for r in parsed['roots']))
            self.assertEqual({r['timer_id'] for r in parsed['roots']},{case['max_timer_id']})

    def test_invalid_cli_arguments_never_echo_private_values(self):
        import subprocess,sys
        private='SYNTHETIC_PRIVATE_CLI_93462'
        cases=[('tools.build_tester_startup_scan',['unused','--mode',private]),
               ('tools.prepare_startup_scan',['--reference','unused','--working','unused','--evidence','unused','--namespace','CodexMCMultiUnused','--variant',private]),
               ('tools.analyze_startup_scan',['unused','unused','--output','unused','--'+private])]
        for module,args in cases:
            run=subprocess.run([sys.executable,'-X','utf8','-m',module,*args],capture_output=True,timeout=20)
            self.assertNotEqual(run.returncode,0)
            self.assertNotIn(private.encode(),run.stdout+run.stderr)
            self.assertIn(b'BLOCKED',run.stdout)


if __name__=='__main__':unittest.main()
