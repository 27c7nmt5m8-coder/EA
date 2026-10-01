"""Adversarial metadata imports exercise real shadow report boundaries, offline."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.workflow_eval import trace_eval as trace
from tools.workflow_eval import semantic_regression as semantic
from tools.workflow_eval import semantic_real as real
from tools.workflow_eval import jevgrep_benchmark as grep

ROOT = Path(__file__).resolve().parents[1]
BASE = 'a' * 40
DATASET = 'b' * 64
SENTINEL = 'synthetic raw transcript sentinel'


def measured(model='gpt-6.1-sol', effort='high'):
    return dict(status='OK', model=model, reasoning_effort=effort,
                answer=dict(type='choice', choice='regression', confidence=.95,
                            probabilities=dict(regression=.95, no_regression=.025, unknown=.025)),
                usage=dict(input_tokens=12, output_tokens=3, total_tokens=15), elapsed_seconds=.5)


class ContractHardening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.trace_case = json.loads((ROOT / 'tests/fixtures/workflow_trace_cases.json').read_bytes())['cases'][0]
        cls.semantic_cases, _ = semantic.load_cases(ROOT / 'tests/fixtures/workflow_semantic_regression_cases.json')
        cls.real_cases, cls.real_sha = real.load_cases(ROOT / 'tests/fixtures/workflow_semantic_real_cases.json')
        cls.grep_cases = grep.load_cases(ROOT / 'tests/fixtures/workflow_jevgrep_cases.json')

    def trace_inputs(self):
        c = copy.deepcopy(self.trace_case)
        fp = trace.case_fingerprint(c)
        a = dict(status='OK', task_id=c['task_id'], base_sha=c['base_sha'], case_fingerprint=fp,
                 model='gpt-6.1-sol', reasoning_effort='high',
                 usage=dict(input_tokens=100, output_tokens=20, total_tokens=120), elapsed_seconds=2.,
                 detected_segment_ids=[s['id'] for s in c['segments'] if s['expected_label'] in trace.ATTENTION_LABELS],
                 input_segment_ids=[s['id'] for s in c['segments']],
                 additional_context_retrieval_count=0, rework_count=0, test_failed_runs=0)
        b = copy.deepcopy(a)
        b['input_segment_ids'] = [s['id'] for s in c['segments'] if s['expected_label'] != 'repetition']
        j = dict(status='OK', case_fingerprint=fp, model='jev-fixture',
                 labels=[dict(segment_id=s['id'], label=s['expected_label'], confidence=.95,
                              evidence_segment_ids=[s['id']]) for s in c['segments']],
                 usage=dict(input_tokens=10, output_tokens=2, total_tokens=12), elapsed_seconds=.2)
        return c, a, b, j

    def trace_row(self):
        return trace.run_trace_case(*self.trace_inputs())

    def semantic_row(self):
        return semantic.run_case(self.semantic_cases[0], base_sha=BASE, dataset_sha256=DATASET,
                                 sol_evaluator=lambda c: measured(), jev_evaluator=lambda c: measured('jev-fixture', None))

    def test_semantic_import_rejects_invalid_observation_contracts(self):
        # Removing import validation must expose malformed observations as quality evidence.
        mutations = [('confidence', 1.5), ('confidence', True), ('confidence', float('nan')),
                     ('model', 'invalid-model'), ('choice', []), ('usage', {'total_tokens': -1}),
                     ('elapsed_seconds', -1), ('status', 'invented')]
        for arm in ('a', 'b'):
            for field, value in mutations:
                row = self.semantic_row(); row[arm][field] = value
                with self.subTest(arm=arm, field=field, value=value), self.assertRaises(ValueError):
                    semantic.summarize([row], current_base_sha=BASE, dataset_sha256=DATASET,
                                       expected_case_ids=[row['id']])

    def test_semantic_import_rejects_mutated_oracle_and_action_flags(self):
        for field, value in [('expected_regression', 'false'), ('severity', 'made-up'),
                             ('split', 'other'), ('mutation', 'made-up'), ('id', []),
                             ('shadow_only', False), ('actual_action', 'approve')]:
            row = self.semantic_row(); row[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                semantic.summarize([row], current_base_sha=BASE, dataset_sha256=DATASET)

    def test_trace_import_rejects_arbitrary_persisted_reasons(self):
        for location in ('exclusion', 'usage', 'duration', 'metric'):
            c, a, b, j = self.trace_inputs()
            if location == 'exclusion': b['status'] = 'UNAVAILABLE'
            elif location == 'usage': b['usage'] = None
            elif location == 'duration': b['elapsed_seconds'] = None
            else: b.pop('rework_count')
            row = trace.run_trace_case(c, a, b, j)
            if location == 'exclusion': row['exclusion_reason'] = SENTINEL
            elif location == 'usage': row['b']['usage_missing_reason'] = SENTINEL
            elif location == 'duration': row['b']['elapsed_missing_reason'] = SENTINEL
            else: row['b']['measurement_missing_reasons']['rework_count'] = SENTINEL
            with self.subTest(location=location), self.assertRaises(ValueError):
                trace.summarize_trace([row], expected_task_ids=[row['task_id']])

    def test_trace_import_malformed_label_containers_have_stable_error(self):
        for branch, field, value in [('labels', 'expected_label', []), ('labels', 'predicted_label', {}),
                ('jev', 'segment_id', []), ('jev', 'label', {}), ('jev', 'evidence_segment_ids', [[]])]:
            row = self.trace_row()
            target = row['labels'][0] if branch == 'labels' else row['jev']['labels'][0]
            target[field] = value
            with self.subTest(branch=branch, field=field), self.assertRaisesRegex(ValueError, '^invalid_trace_jev_contract$'):
                trace.summarize_trace([row])

    def test_trace_import_rejects_forged_quality_metrics(self):
        for field, value in [('task_success', False), ('false_negative_segment_ids', ['forged']),
                ('critical_miss_segment_ids', ['forged']), ('elapsed_seconds', True),
                ('usage', dict(input_tokens=100, output_tokens=20, total_tokens=1)),
                ('rework_count', -1), ('additional_context_retrieval_count', True)]:
            row = self.trace_row(); row['b'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): trace.summarize_trace([row])

    def test_trace_sol_rejects_tool_item_started_without_completed_event(self):
        c, a, b, j = self.trace_inputs()
        events = [dict(type='item.started', item=dict(type='command_execution', command='synthetic-command')),
                  dict(type='item.completed', item=dict(type='agent_message', text=json.dumps(dict(detected_segment_ids=a['detected_segment_ids'])))),
                  dict(type='turn.completed', usage=a['usage'])]
        result = trace.trace_sol_review(c, c['segments'], 'high', runner=lambda *args, **kwargs:
                    subprocess.CompletedProcess([], 0, '\n'.join(json.dumps(e) for e in events), ''))
        self.assertEqual(result['status'], 'UNAVAILABLE')

    def grep_row(self, case=None, historical=False):
        c = case or self.grep_cases[0]
        a = dict(task_id=c['id'], base_sha=c['base_sha'], sol_model='gpt-6-sol' if historical else 'gpt-6.1-sol',
                 sol_effort='xhigh' if historical else 'high', status='OK', found_files=c['must_find_files'],
                 sol_input_tokens=100, sol_output_tokens=20, task_success=1)
        b = dict(a, cache_bypassed=True, source_sha256='c'*64, stage_file_count=len(c['relevant_files']))
        return grep.evaluate_pair(c, a, b, current_base_sha=c['base_sha'], expected_source_sha256='c'*64,
                                  expected_source_paths=c['relevant_files'])

    def test_jevgrep_import_rejects_malformed_derived_measurements(self):
        for field in ('reason', 'metric', 'total', 'quality', 'comparison'):
            row = self.grep_row()
            if field == 'reason': row['b']['metrics']['elapsed_seconds']['reason'] = SENTINEL
            elif field == 'metric': row['b']['metrics']['sol_input_tokens']['value'] = True
            elif field == 'total': row['b']['metrics']['sol_total_tokens']['value'] = 1
            elif field == 'quality': row['b']['must_find_recall']['value'] = 1.5
            else: row['comparison_status'] = 'EXCLUDED'; row['exclusion_reasons'] = []
            with self.subTest(field=field), self.assertRaises(ValueError): grep.summarize_pairs([row])

    def narrow_grep_row(self):
        c = self.grep_cases[0]
        a = dict(task_id=c['id'], base_sha=c['base_sha'], sol_model='gpt-6.1-sol', sol_effort='high',
                 status='OK', found_files=c['must_find_files'], sol_input_tokens=100, sol_output_tokens=20, task_success=1)
        b = dict(a, cache_bypassed=True, source_sha256='c'*64, stage_file_count=len(c['must_find_files']))
        return grep.evaluate_pair(c, a, b, current_base_sha=c['base_sha'], expected_source_sha256='c'*64,
                                  expected_source_paths=c['must_find_files'])

    def test_jevgrep_import_binds_source_universe_coverage_to_allowlist(self):
        row = self.narrow_grep_row()
        original = copy.deepcopy(row)
        report = grep.summarize_pairs([row], cases=[self.grep_cases[0]])
        self.assertEqual(report['context_retrieval']['b']['source_universe_coverage']['value'], 1/3)
        self.assertEqual(row, original)
        historical = copy.deepcopy(row); historical.pop('comparison_binding')
        old_report = grep.summarize_pairs([historical], cases=[self.grep_cases[0]])
        self.assertEqual(old_report['context_retrieval']['b']['source_universe_coverage']['value'], 1/3)
        self.assertEqual(old_report['token']['a']['sol_total_tokens']['value'], 120)
        self.assertEqual(old_report['coverage_missing_data']['comparable_pairs'], 0)
        for value in (1, 0, None):
            altered = copy.deepcopy(row)
            altered['b']['metrics']['source_universe_coverage'] = dict(value=value, coverage=int(value is not None),
                reason=None if value is not None else 'not_measured')
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'jevgrep_derived_metric_mismatch'):
                grep.summarize_pairs([altered], cases=[self.grep_cases[0]])

    def test_combined_report_rejects_forged_jevgrep_source_universe_coverage(self):
        from tools.workflow_eval.experimental_cli import _report
        from types import SimpleNamespace
        import hashlib
        fixture = ROOT / 'tests/fixtures/workflow_jevgrep_cases.json'
        row = self.narrow_grep_row()
        row['dataset_sha256'] = hashlib.sha256(fixture.read_bytes()).hexdigest()
        row['b']['metrics']['source_universe_coverage']['value'] = 1
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'rows.json'; path.write_text(json.dumps([row]), encoding='utf-8')
            args = SimpleNamespace(base_sha=None, trace_rows=None, semantic_rows=None,
                                   jevgrep_rows=str(path), jevgrep_cases=str(fixture))
            outputs = []
            with self.assertRaisesRegex(ValueError, 'jevgrep_derived_metric_mismatch'):
                _report(args, Path(tmp), lambda *values: outputs.append(values))
            self.assertEqual(outputs, [])

    def test_trace_sol_rejects_substituted_or_duplicate_selected_segments_before_runner(self):
        case = self.trace_case
        segment = case['segments'][0]
        selections = [[dict(segment, text='different synthetic trace')],
                      [dict(segment, text='password=fictional-value')],
                      [dict(segment), dict(segment)], [dict(segment, extra='synthetic')],
                      [dict(segment, expected_label='unknown')], [dict(segment, id=[])],
                      [dict(id=segment['id'])], {'segments': [segment]}]
        for selection in selections:
            seen = []
            def runner(*args, **kwargs):
                seen.append(kwargs['input'])
                events = [dict(type='item.completed', item=dict(type='agent_message', text='{"detected_segment_ids":[]}')),
                          dict(type='turn.completed', usage=dict(input_tokens=1, output_tokens=1))]
                return subprocess.CompletedProcess(args[0], 0, '\n'.join(json.dumps(e) for e in events), '')
            with self.subTest(selection=selection):
                with self.assertRaisesRegex(ValueError, '^invalid_selected_segments$'):
                    trace.trace_sol_review(case, selection, 'high', runner=runner)
                self.assertEqual(seen, [])

    def test_trace_sol_canonical_unique_subsets_preserve_prompt_and_fingerprint(self):
        case = self.trace_case
        for selected in ([], [copy.deepcopy(case['segments'][-1]), copy.deepcopy(case['segments'][0])]):
            seen = []
            def runner(*args, **kwargs):
                seen.append(kwargs['input'])
                events = [dict(type='item.completed', item=dict(type='agent_message', text='{"detected_segment_ids":[]}')),
                          dict(type='turn.completed', usage=dict(input_tokens=1, output_tokens=1))]
                return subprocess.CompletedProcess(args[0], 0, '\n'.join(json.dumps(e) for e in events), '')
            result = trace.trace_sol_review(case, selected, 'high', runner=runner)
            self.assertEqual(result['status'], 'OK')
            self.assertEqual(result['case_fingerprint'], trace.case_fingerprint(case))
            self.assertEqual(result['input_segment_ids'], [s['id'] for s in selected])
            sent = json.loads(seen[0].split('Task and selected segments: ', 1)[1])
            self.assertEqual(sent, dict(task=case['task'], segments=[dict(id=s['id'], text=s['text']) for s in selected]))
            self.assertEqual(result['usage']['total_tokens'], 2)
        unsafe = copy.deepcopy(case)
        unsafe['segments'][0]['text'] = 'password=fictional-value'
        seen = []
        with self.assertRaisesRegex(ValueError, '^unsafe_trace$'):
            trace.trace_sol_review(unsafe, unsafe['segments'], 'high', runner=lambda *args, **kwargs: seen.append(kwargs['input']))
        self.assertEqual(seen, [])

    def test_jevgrep_import_rejects_mixed_high_and_historical_xhigh(self):
        with self.assertRaisesRegex(ValueError, 'mixed_sol_provenance'):
            grep.summarize_pairs([self.grep_row(), self.grep_row(self.grep_cases[1], historical=True)])

    def test_jevgrep_import_recomputes_comparison_from_source_binding(self):
        c = self.grep_cases[0]
        a = dict(task_id=c['id'], base_sha=c['base_sha'], sol_model='gpt-6.1-sol', sol_effort='high',
                 status='OK', found_files=c['must_find_files'], sol_input_tokens=100, sol_output_tokens=20, task_success=1)
        b = dict(a, cache_bypassed=True, source_sha256='c'*64, stage_file_count=len(c['relevant_files']))
        row = grep.evaluate_pair(c, a, b, current_base_sha=c['base_sha'], expected_source_sha256='d'*64,
                                 expected_source_paths=c['relevant_files'])
        self.assertEqual(row['comparison_status'], 'EXCLUDED')
        row.update(comparison_status='COMPARABLE', exclusion_reasons=[])
        with self.assertRaisesRegex(ValueError, 'jevgrep_comparison_mismatch'):
            grep.summarize_pairs([row], cases=[c])
        for value in ('opaque-provider-value', [], {}):
            altered = self.grep_row()
            altered['comparison_binding']['a_identity']['sol_model'] = value
            with self.subTest(binding_model=value), self.assertRaisesRegex(ValueError, 'invalid_jevgrep_comparison_binding'):
                grep.summarize_pairs([altered], cases=[c])
        altered = self.grep_row()
        altered.update(sol_model='gpt-6-sol', sol_effort='xhigh', model_provenance='legacy_historical')
        with self.assertRaisesRegex(ValueError, 'invalid_sol_provenance'):
            grep.summarize_pairs([altered], cases=[c])
        unknown = grep.evaluate_pair(c, dict(a, sol_model='opaque-provider-value'), dict(b, sol_model='opaque-provider-value'),
                                     current_base_sha=c['base_sha'], expected_source_sha256='c'*64,
                                     expected_source_paths=c['relevant_files'])
        self.assertNotIn('opaque-provider-value', json.dumps(unknown))
        self.assertEqual(grep.summarize_pairs([unknown], cases=[c])['coverage_missing_data']['comparable_pairs'], 0)

    def test_jevgrep_legacy_missing_comparison_binding_is_read_with_explicit_exclusion(self):
        row = self.grep_row(); row.pop('comparison_binding', None)
        result = grep.summarize_pairs([row], cases=[self.grep_cases[0]])
        self.assertEqual(result['coverage_missing_data']['comparable_pairs'], 0)
        self.assertEqual(result['coverage_missing_data']['excluded_case_reasons'][row['case_id']], ['comparison_binding_not_recorded'])
        self.assertEqual(result['token']['a']['sol_total_tokens']['value'], 120)

    def test_real_import_rejects_invalid_contract_without_erasing_partial_usage(self):
        row = real.run_case(self.real_cases[0], base_sha=BASE, dataset_sha256=self.real_sha,
                            sol_evaluator=lambda p: measured(), jev_evaluator=lambda p: measured('jev-1.13.0', None))
        for field, value in [('confidence', True), ('model', 'invalid'), ('usage_reason', SENTINEL),
                             ('elapsed_seconds', -1), ('reason', SENTINEL), ('status', 'invented')]:
            broken = copy.deepcopy(row); broken['b'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                real.summarize([broken], self.real_cases, base_sha=BASE, dataset_sha256=self.real_sha)
        partial = copy.deepcopy(row)
        partial['b'].update(status='UNAVAILABLE', choice=None, confidence=None, reason='timeout')
        report = real.summarize([partial], self.real_cases, base_sha=BASE, dataset_sha256=self.real_sha)
        self.assertEqual(report['tokens']['jev']['observed_total_tokens'], 15)
        self.assertEqual(report['quality']['jev']['unmeasured'], len(self.real_cases))

    def test_real_import_rejects_approval_flags(self):
        row = real.run_case(self.real_cases[0], base_sha=BASE, dataset_sha256=self.real_sha)
        for field, value in [('shadow_only', False), ('actual_action', 'approve')]:
            broken = dict(row, **{field:value})
            with self.subTest(field=field), self.assertRaises(ValueError):
                real.summarize([broken], self.real_cases, base_sha=BASE, dataset_sha256=self.real_sha)

    def test_real_generated_model_mismatch_retains_billing_and_critical_miss(self):
        case = next(c for c in self.real_cases if c['severity'] == 'critical' and c['expected_result'] == 'regression')
        def miss(payload):
            value = measured('jev-1.13.0', None)
            value['answer'].update(choice='no_regression', probabilities=dict(regression=.025, no_regression=.95, unknown=.025))
            return value
        row = real.run_case(case, base_sha=BASE, dataset_sha256=self.real_sha,
                            sol_evaluator=lambda p: measured('invalid-model'), jev_evaluator=miss)
        report = real.summarize([row], self.real_cases, base_sha=BASE, dataset_sha256=self.real_sha)
        self.assertEqual(report['tokens']['sol']['observed_total_tokens'], 15)
        self.assertEqual(report['critical_miss']['count'], 1)
        self.assertEqual(report['verdict'], 'BLOCKED_CRITICAL_MISS')

    def test_combined_report_binds_semantic_oracle_to_fixture(self):
        # An unchanged dataset hash must not permit rewriting the case oracle.
        row = self.semantic_row()
        raw = (ROOT / 'tests/fixtures/workflow_semantic_regression_cases.json').read_bytes()
        import hashlib
        row['dataset_sha256'] = hashlib.sha256(raw).hexdigest()
        row['expected_regression'] = not row['expected_regression']
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'rows.json'; path.write_text(json.dumps([row]), encoding='utf-8')
            result = subprocess.run([sys.executable, '-B', '-m', 'tools.workflow_eval.cli', 'experimental-report',
                '--semantic-rows', str(path), '--semantic-cases', str(ROOT / 'tests/fixtures/workflow_semantic_regression_cases.json')],
                cwd=tmp, env={**__import__('os').environ, 'PYTHONPATH': str(ROOT)}, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(list((Path(tmp) / '.workflow-eval').glob('*-report.json')))

    def test_combined_trace_report_binds_oracle_priority_and_trace_id(self):
        from tools.workflow_eval.experimental_cli import _report
        from types import SimpleNamespace
        import hashlib
        fixture = ROOT / 'tests/fixtures/workflow_trace_cases.json'
        sha = hashlib.sha256(fixture.read_bytes()).hexdigest()
        for field in ('label', 'priority', 'trace_id'):
            c, a, b, j = self.trace_inputs()
            original = trace.case_fingerprint(c)
            if field == 'label':
                c['segments'][0]['expected_label'] = 'completed'
                j['labels'][0]['label'] = 'completed'
            elif field == 'priority': c['critical_segment_ids'] = [c['segments'][0]['id']]
            else: c['trace_id'] = 'synthetic-other'
            for v in (a, b, j): v['case_fingerprint'] = trace.case_fingerprint(c)
            row = trace.run_trace_case(c, a, b, j)
            row.update(case_fingerprint=original, dataset_sha256=sha)
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'rows.json'; path.write_text(json.dumps([row]), encoding='utf-8')
                args = SimpleNamespace(base_sha=None, trace_rows=str(path), trace_cases=str(fixture),
                                       semantic_rows=None, jevgrep_rows=None)
                with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'trace_fixture_contract_mismatch'):
                    _report(args, Path(tmp), lambda *args: None)

    def test_jevgrep_import_rejects_raw_version_text(self):
        row = self.grep_row(); row['b']['jg_version'] = SENTINEL
        with self.assertRaises(ValueError): grep.summarize_pairs([row])
        c = self.grep_cases[0]
        with self.assertRaises(ValueError):
            grep.score_arm(c, dict(status='OK', found_files=[], jg_version=SENTINEL))

    def test_provider_reason_containers_become_fixed_unavailable_metadata(self):
        from tools.workflow_eval import semantic_prospective as prospective
        for normalizer in (lambda v: semantic.normalize_observation(v, 'jev'),
                           lambda v: real.normalize(v, 'jev'), prospective.normalize_jev):
            for reason in ([], {}):
                with self.subTest(normalizer=normalizer, reason=reason):
                    result = normalizer(dict(status='UNAVAILABLE', reason=reason))
                    self.assertEqual(result['status'], 'UNAVAILABLE')
                    self.assertIsInstance(result['reason'], str)

    def test_prospective_typed_schema_rejects_bool_and_float_versions(self):
        from tools.workflow_eval import semantic_prospective as p
        from test_workflow_semantic_prospective import snapshot
        plan = p.make_protocol('2030-01-01T00:00:00+00:00', 23, BASE)
        for version in (True, 1.0):
            altered = dict(plan, schema_version=version)
            with self.subTest(version=version), self.assertRaises(ValueError): p.validate_protocol(altered)
            s = snapshot(plan); s['schema_version'] = version
            with self.subTest(snapshot_version=version), self.assertRaises(ValueError): p.validate_snapshot(plan, s)

    def test_dataset_import_rejects_coerced_schema_versions(self):
        from tools.workflow_eval.experimental_cli import _trace
        from types import SimpleNamespace
        for name, loader in [('workflow_semantic_regression_cases.json', semantic.load_cases),
                             ('workflow_semantic_real_cases.json', real.load_cases),
                             ('workflow_jevgrep_cases.json', grep.load_cases),
                             ('workflow_trace_cases.json', None)]:
            dataset = json.loads((ROOT / 'tests/fixtures' / name).read_bytes())
            key = 'version' if 'version' in dataset else 'schema_version'
            for value in (True, 1.0):
                dataset[key] = value
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / 'cases.json'; path.write_text(json.dumps(dataset), encoding='utf-8')
                    with self.subTest(dataset=name, value=value), self.assertRaises(ValueError):
                        if loader: loader(path)
                        else: _trace(SimpleNamespace(cases=str(path), base_sha=None, live=False, observations=None), Path(tmp), lambda *args: None)
