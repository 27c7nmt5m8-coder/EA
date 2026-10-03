"""Timer attribution must preserve the frozen EA and reject corrupt telemetry."""
import importlib
import inspect
from pathlib import Path
import tempfile
import unittest

from tools.build_tester_mc_multisymbol import build as baseline_build
from tools.build_tester_pipeline import MAIN, STATE, SOURCE


class TimerLatencyTest(unittest.TestCase):
    def summaries(self, module):
        rows = [dict(stage='OnTimer',count='1',total_us='364',max_us='364',
                     recorded='1',unknown='0',bookkeeping_max_us='1')]
        return rows + [dict(stage=stage,count='1',total_us=str(value),max_us=str(value),
                            recorded='1',unknown='0',bookkeeping_max_us='1')
                       for stage,value in zip(module.STAGES,(2,3,350,3,2,1,1,2))]

    def module(self):
        self.assertTrue((SOURCE.parent / 'tools/build_tester_timer_latency.py').is_file(),
                        'timestamped OnTimer attribution is not implemented')
        return importlib.import_module('tools.build_tester_timer_latency')

    def test_generated_mc_and_trading_files_remain_byte_identical(self):
        module = self.module()
        before = {p.name: p.read_bytes() for p in SOURCE.iterdir() if p.is_file()}
        with tempfile.TemporaryDirectory() as tmp:
            original = baseline_build(Path(tmp) / 'base', 2).parent
            generated = module.build(Path(tmp) / 'timed', 2).parent
            self.assertEqual(module.restore_main((generated / MAIN).read_bytes()),
                             (original / MAIN).read_bytes())
            for p in original.iterdir():
                if p.name != MAIN:
                    self.assertEqual((generated / p.name).read_bytes(), p.read_bytes(), p.name)
            self.assertEqual(set(p.name for p in generated.iterdir()) - set(p.name for p in original.iterdir()),
                             {'TesterTimerLatencyDiag.mqh'})
        self.assertEqual(before, {p.name: p.read_bytes() for p in SOURCE.iterdir() if p.is_file()})

    def test_unsupported_modes_and_product_destination_fail_closed(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            for mode in (1, 3, 4, 5):
                with self.assertRaises(ValueError):
                    module.build(Path(tmp) / str(mode), mode)
            with self.assertRaises(ValueError):
                module.build(SOURCE / 'forbidden-diagnostic', 2)

    def test_strict_partition_attributes_maximum_without_inventing_population_percentiles(self):
        module = self.module()
        rows = [dict(timer_id='1',server_s='123',start_wall_us='10',end_wall_us='374',
                     stage=stage,symbol='ALL',duration_us=str(value),total_us='364')
                for stage,value in zip(module.STAGES, (2, 3, 350, 3, 2, 1, 1, 2))]
        result = module.analyze_timer_trace(rows,self.summaries(module))
        self.assertEqual(result['maximum_timer_id'], 1)
        self.assertEqual(result['dominant_stage'], 'scan')
        self.assertEqual(result['observed_timer_count'], 1)
        self.assertEqual(result['population_p95_us'], 'UNKNOWN')

    def test_incomplete_negative_and_contradictory_timing_is_not_evidence(self):
        module = self.module()
        row=dict(timer_id='1',server_s='123',start_wall_us='10',end_wall_us='374',
                 stage='scan',symbol='ALL',duration_us='350',total_us='364')
        summary=self.summaries(module)
        for rows in ([row], [row | {'duration_us':'-1'}], [row | {'stage':'unexpected'}],
                     [row | {'end_wall_us':'9'}], [row | {'duration_us':'NaN'}]):
            with self.assertRaises(ValueError):
                module.analyze_timer_trace(rows, summary)

    def test_unknown_population_summary_cannot_be_silently_discarded(self):
        module = self.module()
        rows = [dict(timer_id='1',server_s='123',start_wall_us='10',end_wall_us='374',
                     stage=stage,symbol='ALL',duration_us=str(value),total_us='364')
                for stage,value in zip(module.STAGES,(2,3,350,3,2,1,1,2))]
        summaries = self.summaries(module) + [dict(stage='unrecognized',count='100',total_us='1000',max_us='364',
                                                  recorded='1',unknown='0',bookkeeping_max_us='1')]
        with self.assertRaises(ValueError):
            module.analyze_timer_trace(rows,summaries)

    def test_retained_maxima_and_id_must_agree_with_population_bounds(self):
        module = self.module()
        rows = [dict(timer_id='1',server_s='123',start_wall_us='10',end_wall_us='374',
                     stage=stage,symbol='ALL',duration_us=str(value),total_us='364')
                for stage,value in zip(module.STAGES,(2,3,350,3,2,1,1,2))]
        summaries=self.summaries(module)
        too_small=[r | {'total_us':'1','max_us':'1'} if r['stage']=='scan' else r for r in summaries]
        too_large=[r | {'total_us':'365'} if r['stage']=='OnTimer' else r for r in summaries]
        for changed_rows, changed_summary in ((rows,too_small),(rows,too_large),
                                               ([r | {'timer_id':'101'} for r in rows],summaries)):
            with self.assertRaises(ValueError):
                module.analyze_timer_trace(changed_rows,changed_summary)

    def test_zero_unknown_requires_exact_retained_record_count(self):
        module=self.module()
        rows=[dict(timer_id='1',server_s='123',start_wall_us='10',end_wall_us='374',
                   stage=stage,symbol='ALL',duration_us=str(value),total_us='364')
              for stage,value in zip(module.STAGES,(2,3,350,3,2,1,1,2))]
        with self.assertRaises(ValueError):
            module.analyze_timer_trace(rows,[r | {'count':'2'} for r in self.summaries(module)])

    def test_nested_probe_restores_the_entire_generated_state_and_mc_core(self):
        module=self.module()
        self.assertIn('nested',inspect.signature(module.build).parameters,
                      'Scan/CopyBuffer attribution has not been implemented')
        with tempfile.TemporaryDirectory() as tmp:
            base=baseline_build(Path(tmp)/'base',2).parent
            output=module.build(Path(tmp)/'nested',2,nested=True).parent
            self.assertEqual(module.restore_state((output/STATE).read_bytes()),(base/STATE).read_bytes())
            self.assertEqual(module.restore_main((output/MAIN).read_bytes()),(base/MAIN).read_bytes())
            for p in base.iterdir():
                if p.name not in (MAIN,STATE):
                    self.assertEqual(p.read_bytes(),(output/p.name).read_bytes(),p.name)

    def test_sequential_copy_spans_cannot_exceed_their_scan_parent(self):
        module=self.module()
        row=dict(timer_id='1',server_s='123',start_wall_us='10',end_wall_us='374',
                 stage='scan',symbol='ALL',duration_us='350',total_us='364')
        rows=[row | {'stage':stage,'duration_us':str(value)} for stage,value in zip(module.STAGES,(2,3,350,3,2,1,1,2))]
        rows+=[row | {'stage':'symbol_scan','symbol':'EURJPY'}]
        rows+=[row | {'stage':stage,'symbol':'EURJPY','duration_us':str(value)}
               for stage,value in zip(module.NESTED_STAGES,(1,2,3,344,200,200))]
        with self.assertRaises(ValueError):
            module.analyze_timer_trace(rows,self.summaries(module))

    def test_nested_probe_must_stay_within_first_100_callbacks(self):
        module=self.module()
        rows=[]
        for timer in range(1,102):
            row=dict(timer_id=str(timer),server_s='123',start_wall_us='10',end_wall_us='374',
                     stage='scan',symbol='ALL',duration_us='350',total_us='364')
            rows += [row | {'stage':stage,'duration_us':str(value)}
                     for stage,value in zip(module.STAGES,(2,3,350,3,2,1,1,2))]
        row=rows[-1]
        rows += [row | {'stage':'symbol_scan','symbol':'EURJPY','duration_us':'350'}]
        rows += [row | {'stage':stage,'symbol':'EURJPY','duration_us':str(value)}
                 for stage,value in zip(module.NESTED_STAGES,(1,2,3,344,100,100))]
        summaries=[r | {'count':'101','recorded':'101','total_us':str(int(r['total_us'])*101)}
                   for r in self.summaries(module)]
        with self.assertRaises(ValueError):
            module.analyze_timer_trace(rows,summaries)

    def test_probed_frame_cannot_omit_an_entire_symbol_detail_group(self):
        module=self.module()
        row=dict(timer_id='1',server_s='123',start_wall_us='10',end_wall_us='374',
                 stage='scan',symbol='ALL',duration_us='350',total_us='364')
        rows=[row | {'stage':stage,'duration_us':str(value)}
              for stage,value in zip(module.STAGES,(2,3,350,3,2,1,1,2))]
        rows += [row | {'stage':'symbol_scan','symbol':symbol,'duration_us':str(value)}
                 for symbol,value in (('EURJPY',300),('USDJPY',50))]
        rows += [row | {'stage':stage,'symbol':'EURJPY','duration_us':str(value)}
                 for stage,value in zip(module.NESTED_STAGES,(1,2,3,294,100,100))]
        with self.assertRaises(ValueError):
            module.analyze_timer_trace(rows,self.summaries(module))


if __name__ == '__main__':
    unittest.main()
