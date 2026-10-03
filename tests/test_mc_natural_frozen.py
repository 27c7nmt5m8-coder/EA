"""Portable replay of fresh, hash-bound June evidence; never launches MT5."""
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from tools.analyze_mc_natural_heavy import natural_overlap
from tools.build_tester_journal_io import build
from tools.build_tester_timer_latency import analyze_timer_trace
from tools.mc_multisymbol_runner import (
    selection_copy, validate_case_contract, validate_replay_rows, validate_result_binding,
)
from tools.mc500k_batch import analyze_rows, reason_names

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT/'verification/mc_natural_heavy_20261003'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(data):
    return hashlib.sha256(data).hexdigest()


class FrozenNaturalEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.manifest = load(EVIDENCE/'manifest.json')
        self.retained = load(EVIDENCE/'retention.json')['cases']
        self.analysis = {c['case']:c for c in load(EVIDENCE/'analysis.json')['cases']}

    def rows(self, case, name):
        directory = EVIDENCE/'native'/case['case']
        data = (directory/name).read_bytes()
        meta = self.retained[case['case']][name]
        self.assertEqual(digest(data), meta['sha256'])
        result = load(directory/'result.json')
        origin = meta.get('origin_filename', name)
        self.assertEqual(meta['origin_sha256'], result['exports'][origin])
        rows = list(csv.DictReader(io.StringIO(data.decode('ascii'))))
        if meta['selection'] == 'ALL':
            self.assertEqual(meta['sha256'], meta['origin_sha256'])
        else:
            self.assertEqual(len(rows), meta['retained_rows'])
            self.assertEqual(list(rows[0]), meta['columns'])
        return rows

    def named(self, case, suffix):
        names = [n for n in self.retained[case['case']] if n.endswith(suffix)]
        self.assertEqual(len(names), 1)
        return self.rows(case, names[0])

    def test_four_conditions_inputs_and_product_scope(self):
        self.assertEqual(len(self.manifest), 4)
        self.assertEqual({(c['count'],c['mode'],c['load']) for c in self.manifest},
                         {(n,m,'NORMAL') for n in (3,4) for m in (0,2)})
        baseline = load(ROOT/'verification/mc_multisymbol_20261002_6230/baseline_inputs.json')
        self.assertEqual(digest(baseline['text'].encode(baseline['encoding'])), baseline['sha256'])
        configs = load(EVIDENCE/'frozen_configs.json')
        for c in self.manifest:
            validate_case_contract(c)
            self.assertEqual(c['market_window'], 'JUNE_NATURAL')
            self.assertEqual(c['original_set_sha256'], baseline['sha256'])
            self.assertEqual(digest(selection_copy(baseline['text'],tuple(c['symbols'])).encode('utf-16')),
                             c['selected_set_sha256'])
            self.assertEqual(digest(configs[c['case']].encode()), c['config_sha256'])
            self.assertIn('FromDate=2026.06.01\nToDate=2026.06.13', configs[c['case']])
        product = load(ROOT/'verification/mc_multisymbol_20261002_6230/finish_validation.json')['product_source']['sha256']
        for name, expected in product.items():
            self.assertEqual(digest((ROOT/'src'/name).read_bytes()), expected)

    def test_generated_sources_match_fresh_compiled_bundles(self):
        for mode in (0,2):
            c = next(c for c in self.manifest if c['mode']==mode)
            with tempfile.TemporaryDirectory() as td:
                directory = build(Path(td)/'bundle',mode).parent
                for name, expected in c['source_sha256'].items():
                    self.assertEqual(digest((directory/name).read_bytes()),expected,(mode,name))
        self.assertTrue(all(r['errors']==r['warnings']==0 and r['fresh_ex5']
                            for r in load(EVIDENCE/'compile_results.json')))

    def test_natural_overlap_reproduces_actual_only_coverage(self):
        maxima = []
        for c in self.manifest:
            events = self.rows(c,'lifecycle.csv')
            self.assertTrue(all(e['event'] in self.retained[c['case']]['lifecycle.csv']['selection'] for e in events))
            observed = natural_overlap(events,self.named(c,'_snapshots.csv'),c['symbols'])
            self.assertEqual(observed,self.analysis[c['case']]['natural'])
            self.assertEqual(observed['completed_overlap'],'UNOBSERVED')
            maxima.append(observed['maximum_active_symbols'])
        self.assertEqual(maxima,[2,2,3,2])
        current4 = next(c for c in self.manifest if c['count']==4 and c['mode']==0)
        three = self.analysis[current4['case']]['natural']['overlap_by_cardinality']['3']
        self.assertEqual(three['duration_us'],15693681)
        completed = [w for w in three['witnesses'] if all(c['status']=='completed' for c in w['cycles'])]
        self.assertEqual((len(completed),sum(w['duration_us'] for w in completed)),(32,14637146))

    def test_exact_numeric_replay_and_fresh_completion(self):
        total = actual = shadow = 0
        for c in self.manifest:
            directory = EVIDENCE/'native'/c['case']
            result, attempt = load(directory/'result.json'),load(directory/'attempt.json')
            validate_result_binding(result,c)
            self.assertEqual(attempt['status'],'COLLECTABLE')
            self.assertEqual(attempt['exit_code'],0)
            self.assertLess(attempt['elapsed_seconds'],attempt['timeout_seconds'])
            self.assertEqual((result['runtime_errors'],result['warnings'],result['deinit_reason']),(0,0,1))
            self.assertEqual(result['report_metrics']['history_quality'],100)
            replay = self.named(c,'_replay.csv')
            self.assertEqual(validate_replay_rows(replay,int(result['scheduler']['comparisons'])),result['actual_replay_rows'])
            total += len(replay)
            actual += sum(int(r['actual_compared']) for r in replay if r['kind']=='ACTUAL')
            shadow += sum(int(r['actual_compared']) for r in replay if r['kind']=='SHADOW')
        self.assertEqual((total,actual,shadow),(3144,2986,28))

    def test_retained_timer_maxima_reproduce_without_population_claims(self):
        for c in self.manifest:
            timers = self.named(c,'_timer_sections.csv')
            summaries = self.named(c,'_timer_summary.csv')
            self.assertEqual(analyze_timer_trace(timers,summaries),self.analysis[c['case']]['timer'])
            self.assertEqual(self.analysis[c['case']]['timer']['population_p95_us'],'UNKNOWN')

    def test_opportunity_funnel_orders_and_force_reproduce(self):
        for c in self.manifest:
            result = load(EVIDENCE/'native'/c['case']/'result.json')
            name = result['scheduler']['prefix'].replace('20260927_','20260927Detail_')+'.csv'
            details = self.rows(c,name)
            requests = self.named(c,'_requests.csv')
            timings = self.named(c,'_timings.csv')
            for symbol in c['symbols']:
                expected = self.analysis[c['case']]['symbols'][symbol]
                analysis = analyze_rows([r for r in details if r['symbol']==symbol],reason_names())
                self.assertEqual(analysis['funnel'],expected['funnel'])
                self.assertEqual(analysis['outcomes'],expected['outcomes'])
                force = [r for r in requests if r['symbol']==symbol and r['force']=='1']
                heavy = [r for r in force if r['heavy_start']=='1']
                self.assertEqual((len(force),len(heavy),len(force)-len(heavy)),
                                 (expected['force_requests'],expected['heavy_force'],expected['immediate_force']))
                sent = [r for r in timings if r['symbol']==symbol and r['event']=='ENTRY_SEND']
                self.assertEqual(len(sent),expected['order_calls'])
                self.assertEqual(sum(r['success']=='1' and r['retcode'] in ('10008','10009','10010') for r in sent),expected['order_acceptance'])

    def test_sequence_differences_have_direct_retained_evidence(self):
        for group in load(EVIDENCE/'sequence_differences.json'):
            cases = {c['mode']:c for c in self.manifest if c['count']==group['count']}
            events = {m:self.rows(c,'opportunities.csv') for m,c in cases.items()}
            guards = {m:self.named(c,'_guards.csv') for m,c in cases.items()}
            self.assertNotIn('INSUFFICIENT_EVIDENCE',group['classification_counts'])
            for d in group['evidence']:
                for mode,key in ((0,'current_timeline'),(2,'fixed500k_timeline')):
                    self.assertEqual(d[key],[e for e in events[mode] if e['opp_id']==d['id']])
                if d['classification']=='EXPECTED_SEQUENCE_CHANGE':
                    mode = 0 if d['guard_side']=='CURRENT' else 2
                    for g in d['guards']:
                        self.assertIn(g,guards[mode])
                    self.assertTrue(any(g['reason'] in ('RECEIPT','PATTERN') and any(
                        e['event']=='ACCEPTED' and e['opp_id']==g['prior_claimant_id'] and
                        int(e['server_s'])<=int(g['first_s']) for e in events[mode]) for g in d['guards']))
                elif d['classification']=='MC_STATE_CHANGE':
                    self.assertTrue(any(e['event']=='ELIGIBLE' and e['position_kind']=='0' and e['active']=='1' and e['ready']=='0' for e in d['current_timeline']))
                    self.assertTrue(any(e['event']=='ACCEPTED' and e['ready']==e['allowed']=='1' for e in d['fixed500k_timeline']))
                elif d['classification']=='POSITION_STATE_CHANGE':
                    self.assertTrue(any(e['event']=='ELIGIBLE' and e['position_kind']!='0' for e in d['fixed500k_timeline']))
                else:
                    self.fail('unsupported causal classification')


if __name__=='__main__':
    unittest.main()
