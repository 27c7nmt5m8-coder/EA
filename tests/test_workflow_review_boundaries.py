"""Final-review counterexamples, all fictional and offline."""
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ReviewBoundaries(unittest.TestCase):
    def events(self, answer='{"route":"review"}'):
        return [dict(type='item.completed', item=dict(type='agent_message', text=answer)),
                dict(type='turn.completed', usage=dict(input_tokens=100, output_tokens=10))]

    def row(self):
        facts=dict(paths=['docs/dev-note.md'],dependency='known',module_count=1,tests='PASS',
                   changed_lines=1,missing_context=[],sensitive=False,scope_ok=True,current=True,protected=False)
        review=dict(status='OK',route='review',model='gpt-6-sol',reasoning_effort='high',
                    usage=dict(input_tokens=100,output_tokens=10),elapsed_seconds=1)
        return dict(id='case',severity='ordinary',truth='review',facts=facts,a=copy.deepcopy(review),
                    b=copy.deepcopy(review),jev=dict(status='NOT_RUN',attempts=0,usage=None),
                    shadow=dict(shadow_route='review',mandatory_reasons=[]))

    def test_invalid_sol_judgment_retains_completed_usage(self):
        from tools.workflow_eval.benchmark import parse_codex
        got=parse_codex(self.events('invalid JSON'))
        self.assertEqual(got['status'],'UNKNOWN')
        self.assertEqual(got['usage']['total_tokens'],110)
        self.assertIsNone(got['route'])

    def test_nonzero_sol_exit_retains_usage_without_retaining_raw_output(self):
        from tools.workflow_eval.benchmark import sol_review
        completed=subprocess.CompletedProcess([],1,stdout='\n'.join(json.dumps(e) for e in self.events()),stderr='private diagnostic')
        with patch('tools.workflow_eval.benchmark.subprocess.run',return_value=completed):
            got=sol_review('Developer note.','Sentence changed.','high')
        self.assertEqual(got['status'],'UNAVAILABLE')
        self.assertEqual(got['usage']['total_tokens'],110)
        self.assertNotIn('private diagnostic',json.dumps(got))

    def test_invalid_jev_answer_retains_known_usage(self):
        from tools.workflow_eval.triage import call_jev
        payload=dict(model='jev-1.13.0',usage=dict(input_tokens=100,output_tokens=10),answers=dict(routing={}))
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):return json.dumps(payload).encode()
        got=call_jev(dict(task='Developer note.',evidence='Sentence changed.'),key='fictional-key',opener=lambda *a,**k:Response())
        self.assertEqual(got['status'],'UNAVAILABLE')
        self.assertEqual(got['usage']['total_tokens'],110)
        self.assertIsNone(got['answer'])

    def test_timeout_retains_any_completed_numeric_usage(self):
        from tools.workflow_eval.benchmark import sol_review
        from tools.workflow_eval.real_tasks import perform_review
        for real in (False,True):
            with self.subTest(real=real):
                answer=json.dumps(dict(verdict='unknown',findings=[],missing_context_ids=['interface'])) if real else '{"route":"review"}'
                stdout='\n'.join(json.dumps(e) for e in self.events(answer)).encode()
                target='tools.workflow_eval.'+('real_tasks' if real else 'benchmark')+'.subprocess.run'
                with patch(target,side_effect=subprocess.TimeoutExpired([],1,output=stdout)):
                    got=perform_review('Developer note.','Sentence changed.') if real else sol_review('Developer note.','Sentence changed.','high')
                self.assertEqual(got['status'],'UNAVAILABLE')
                self.assertEqual(got['usage']['total_tokens'],110)
                self.assertEqual(got['observed_completed_turns'],1)

    def test_malformed_stream_preserves_usage_but_cannot_pass(self):
        from tools.workflow_eval.benchmark import parse_codex
        from tools.workflow_eval.telemetry import codex_events
        stdout='{invalid}\n'+'\n'.join(json.dumps(e) for e in self.events())
        got=parse_codex(codex_events(stdout))
        self.assertEqual(got['status'],'UNKNOWN')
        self.assertEqual(got['usage']['total_tokens'],110)

    def test_real_ea_high_is_standard_and_reaches_provider(self):
        from tools.workflow_eval.real_tasks import perform_review
        completed = subprocess.CompletedProcess([], 1, stdout='', stderr='')
        with patch('tools.workflow_eval.real_tasks.subprocess.run', return_value=completed) as call:
            got = perform_review('Review order risk changes.', 'Protected change.')
        self.assertEqual(got['reasoning_effort'], 'high')
        self.assertEqual(got['model'], 'gpt-6.1-sol')
        cmd = call.call_args.args[0]
        self.assertEqual(cmd[cmd.index('-m')+1], 'gpt-6.1-sol')
        self.assertIn('model_reasoning_effort="high"', cmd)
        self.assertEqual(call.call_count, 1)

    def test_untracked_documents_are_protected_and_counted_before_triage(self):
        from tools.workflow_eval.context import build_bundle
        from tools.workflow_eval.cli import main
        for protected in (False,True):
            with self.subTest(protected=protected),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                def git(*args):return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.DEVNULL)
                git('init','-q');git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid')
                (root/'seed.md').write_text('Note.\n',encoding='utf-8');git('add','.');git('commit','-qm','fixture')
                (root/'docs').mkdir()
                content=('Order safety adjustment.\n' if protected else 'Developer note.\n')+'New line.\n'*90
                (root/'docs/dev-note.md').write_text(content,encoding='utf-8')
                bundle=build_bundle(root,'HEAD',[],'Update developer note.')
                self.assertEqual(bundle['protected'],protected)
                self.assertGreaterEqual(bundle.get('changed_lines',0),91)
                out=root/'.workflow-eval';out.mkdir()
                (out/'bundle.json').write_text(json.dumps(bundle),encoding='utf-8')
                (out/'test.json').write_text(json.dumps(dict(status='PASS',fingerprint=bundle['fingerprint'])),encoding='utf-8')
                with patch('tools.workflow_eval.cli.Path.cwd',return_value=root),patch('tools.workflow_eval.cli.call_jev') as call,patch('sys.stdout',new=io.StringIO()):
                    main(['triage',str(out/'bundle.json'),'--test-evidence',str(out/'test.json'),'--live-jev'])
                got=json.loads((out/'triage.json').read_text(encoding='utf-8'))
                self.assertEqual(got['routing']['sol_effort'],'high')
                self.assertEqual(got['routing']['shadow_route'],'review')
                self.assertFalse(got['routing']['actual_review_skipped'])
                call.assert_not_called()

    def test_policy_keeps_safety_constants_and_has_no_old_model_fallback(self):
        from tools.workflow_eval.triage import policy
        rules = policy()
        self.assertEqual(rules['implementation_model'], 'gpt-6.1-sol')
        self.assertEqual(rules['normal_effort'], 'high')
        self.assertEqual(rules['mandatory_effort'], 'high')
        self.assertEqual(rules['escalation_effort'], 'xhigh')
        self.assertIs(rules['review_skip_enabled'], False)
        self.assertEqual(rules['confidence_threshold'], .90)
        for update in (dict(implementation_model='gpt-6-sol'), dict(mandatory_effort='xhigh'),
                       dict(confidence_threshold=.91), dict(review_skip_enabled=True)):
            with patch('tools.workflow_eval.triage.json.loads', return_value=dict(rules, **update)):
                with self.assertRaisesRegex(ValueError, 'unsafe_policy'): policy()

    def test_ordinary_and_mandatory_routes_stay_high_despite_xhigh_availability(self):
        from tools.workflow_eval.triage import route
        answer = dict(type='choice', choice='candidate', confidence=.99,
                      probabilities=dict(candidate=.99, review=.01, unknown=0))
        for update, mandatory in (({}, False), (dict(protected=True), True),
                                  (dict(dependency='unknown'), True),
                                  (dict(paths=['src/Risk.mqh']), True)):
            with self.subTest(update=update):
                got = route(dict(self.row()['facts'], **update), answer)
                self.assertEqual(got['sol_model'], 'gpt-6.1-sol')
                self.assertEqual(got['sol_effort'], 'high')
                self.assertEqual(bool(got['mandatory_reasons']), mandatory)
                self.assertEqual(got['shadow_route'], 'review' if mandatory else 'candidate')
                self.assertEqual(got['actual_route'], 'review')
                self.assertFalse(got['actual_review_skipped'])

    def test_xhigh_requires_explicit_evidence_and_retains_provenance(self):
        from tools.workflow_eval.real_tasks import perform_review
        from tools.workflow_eval.triage import route
        completed = subprocess.CompletedProcess([], 1, stdout='', stderr='')
        escalation = dict(reason='high_review_material_uncertainty', evidence='High review R1: unresolved interface contract.')
        with patch('tools.workflow_eval.real_tasks.subprocess.run', return_value=completed) as call:
            got = perform_review('Developer note.', 'Sentence changed.', 'xhigh', escalation=escalation)
        self.assertEqual(got['reasoning_effort'], 'xhigh')
        self.assertEqual(got['escalation'], escalation)
        self.assertIn('model_reasoning_effort="xhigh"', call.call_args.args[0])
        routed = route(self.row()['facts'], escalation=escalation)
        self.assertEqual(routed['sol_effort'], 'xhigh')
        self.assertEqual(routed['shadow_route'], 'review')
        for invalid in (None, {}, dict(reason='protected', evidence='Risk change'),
                        dict(reason='high_review_material_uncertainty', evidence=' ')):
            with self.subTest(escalation=invalid), patch('tools.workflow_eval.real_tasks.subprocess.run') as call:
                with self.assertRaises(ValueError):
                    perform_review('Developer note.', 'Sentence changed.', 'xhigh', escalation=invalid)
                call.assert_not_called()

    def test_provider_failure_does_not_retry_old_model_or_lower_effort(self):
        from tools.workflow_eval.real_tasks import perform_review
        with patch('tools.workflow_eval.real_tasks.subprocess.run', side_effect=OSError('unavailable')) as call:
            got = perform_review('Developer note.', 'Sentence changed.')
        self.assertEqual(got['status'], 'UNAVAILABLE')
        self.assertEqual(got['model'], 'gpt-6.1-sol')
        self.assertEqual(got['reasoning_effort'], 'high')
        self.assertEqual(call.call_count, 1)

    def test_mandatory_high_and_evidenced_real_xhigh_records_are_valid(self):
        from tools.workflow_eval.real_tasks import validate_record
        from tools.workflow_eval.report import summarize
        from tests.test_workflow_real_tasks import RealTaskTests
        for effort in ('high', 'xhigh'):
            with self.subTest(effort=effort):
                real = RealTaskTests().record()
                synthetic = self.row()
                synthetic['facts']['protected'] = True
                for arm in ('a', 'b'):
                    real[arm].update(model='gpt-6.1-sol', reasoning_effort=effort)
                    if effort == 'xhigh':
                        real[arm]['escalation'] = dict(reason='high_review_material_uncertainty',
                            evidence='High review R1: unresolved interface contract.')
                    synthetic[arm].update(model='gpt-6.1-sol', reasoning_effort=effort)
                validate_record(real)
                report = summarize([synthetic])
                self.assertEqual(report['valid_pairs'], 1)
                self.assertEqual(report['review_provenance'][0]['reasoning_effort'], effort)
                self.assertIsNone(report['standard_short_context_sol_api_equivalent_usd']['a'])

    def test_active_high_records_allow_only_absent_or_null_escalation(self):
        from tools.workflow_eval.real_tasks import validate_record
        from tests.test_workflow_real_tasks import RealTaskTests
        for explicit_null in (False, True):
            with self.subTest(explicit_null=explicit_null):
                row = RealTaskTests().record()
                for arm in ('a', 'b'):
                    row[arm].update(model='gpt-6.1-sol', reasoning_effort='high')
                    if explicit_null: row[arm]['escalation'] = None
                self.assertEqual(validate_record(row), row)

    def test_active_xhigh_records_reject_missing_provenance_on_each_arm(self):
        from tools.workflow_eval.real_tasks import validate_record
        from tests.test_workflow_real_tasks import RealTaskTests
        for arm in ('a', 'b'):
            for status in ('OK', 'UNKNOWN', 'UNAVAILABLE'):
                for explicit_null in (False, True):
                    with self.subTest(arm=arm, status=status, explicit_null=explicit_null):
                        row = RealTaskTests().record()
                        row[arm].update(model='gpt-6.1-sol', reasoning_effort='xhigh', status=status)
                        if explicit_null: row[arm]['escalation'] = None
                        with self.assertRaisesRegex(ValueError, 'explicit_escalation_evidence_required'):
                            validate_record(row)

    def test_active_record_rejects_invalid_or_contradictory_provenance(self):
        from tools.workflow_eval.real_tasks import validate_record
        from tests.test_workflow_real_tasks import RealTaskTests
        for arm in ('a', 'b'):
            for model, effort, escalation in (
                    ('gpt-6.1-sol', 'xhigh', {}),
                    ('gpt-6.1-sol', 'xhigh', dict(reason='protected', evidence='Risk change.')),
                    ('gpt-6.1-sol', 'xhigh', dict(reason='high_review_material_uncertainty', evidence=' \t\n')),
                    ('gpt-6.1-sol', 'xhigh', dict(reason='high_review_material_uncertainty', evidence='password=fictional-secret-value')),
                    ('gpt-6.1-sol', 'high', dict(reason='high_review_material_uncertainty', evidence='High review R1: unresolved contract.')),
                    ('gpt-6.1-sol', 'high', {}),
                    ('gpt-6-luna', 'high', None),
                    ('gpt-6.1-sol', 'medium', None)):
                with self.subTest(arm=arm, model=model, effort=effort, escalation=escalation):
                    row = RealTaskTests().record()
                    row[arm].update(model=model, reasoning_effort=effort, escalation=escalation)
                    with self.assertRaises(ValueError): validate_record(row)

    def test_historical_ingestion_does_not_enable_execution_fallback(self):
        from tools.workflow_eval.real_tasks import validate_record, perform_review
        from tests.test_workflow_real_tasks import RealTaskTests
        historical = RealTaskTests().record()
        original = copy.deepcopy(historical)
        validate_record(historical)
        self.assertEqual(historical, original)
        for arm in ('a', 'b'):
            self.assertNotIn('escalation', historical[arm])
            self.assertEqual((historical[arm]['model'], historical[arm]['reasoning_effort']), ('gpt-6-sol', 'xhigh'))
        with patch('tools.workflow_eval.real_tasks.subprocess.run', side_effect=OSError('unavailable')) as call:
            got = perform_review('Developer note.', 'Sentence changed.')
        cmd = call.call_args.args[0]
        self.assertEqual(cmd[cmd.index('-m')+1], 'gpt-6.1-sol')
        self.assertEqual(got['model'], 'gpt-6.1-sol')
        self.assertEqual(got['status'], 'UNAVAILABLE')
        self.assertEqual(call.call_count, 1)

    def test_legacy_pricing_remains_historical_and_not_used_for_new_model(self):
        from tools.workflow_eval.report import summarize
        historical = self.row()
        for arm in ('a', 'b'):
            historical[arm]['usage'].update(cached_input_tokens=20, cache_write_input_tokens=0)
            historical[arm]['usage_fields'] = list(historical[arm]['usage'])
        self.assertEqual(summarize([historical])['standard_short_context_sol_api_equivalent_usd']['a'], .000264)
        current = copy.deepcopy(historical)
        for arm in ('a', 'b'): current[arm]['model'] = 'gpt-6.1-sol'
        self.assertIsNone(summarize([current])['standard_short_context_sol_api_equivalent_usd']['a'])

    def test_benchmark_comparison_does_not_change_active_mandatory_route(self):
        from tools.workflow_eval.benchmark import run_case
        case = dict(id='critical', split='holdout', truth='review', severity='critical',
                    task='Review order safety.', facts=self.row()['facts'],
                    context_blocks=[dict(id='a', text='Fictional contract.')],
                    selected_context_ids=['a'], required_context_ids=['a'])
        for comparison in (None, 'xhigh'):
            with self.subTest(comparison=comparison), patch('tools.workflow_eval.benchmark.sol_review', return_value={}) as sol, \
                    patch('tools.workflow_eval.benchmark.call_jev') as jev:
                got = run_case(case, 0, live_jev=True, comparison_effort=comparison)
                self.assertEqual(sol.call_count, 2)
                self.assertTrue(all(c.args[2] == (comparison or 'high') for c in sol.call_args_list))
                self.assertEqual(got['shadow']['sol_effort'], 'high')
                self.assertTrue(got['shadow']['mandatory_reasons'])
                self.assertEqual(got['shadow']['shadow_route'], 'review')
                jev.assert_not_called()

    def test_telemetry_accepts_new_model_and_preserves_historical_provenance(self):
        from tools.workflow_eval.telemetry import extract_usage, validate_event
        for model in ('gpt-6.1-sol', 'gpt-6-sol'):
            events = [dict(type='turn_context', payload=dict(model=model, effort='high')),
                      dict(type='event_msg', payload=dict(type='task_started')),
                      dict(type='event_msg', payload=dict(type='token_count', info=dict(
                          total_token_usage=dict(input_tokens=100, output_tokens=10),
                          last_token_usage=dict(input_tokens=100, output_tokens=10)))),
                      dict(type='event_msg', payload=dict(type='task_complete'))]
            got = extract_usage(events)
            self.assertEqual(got['status'], 'OK')
            self.assertEqual(got['models'], [(model, 'high')])
            validate_event(dict(task_id='task', pair_id='pair', arm='A', phase='additional_review',
                                event='end', model=model, reasoning_effort='high'))

    def test_real_pairs_do_not_mix_effort_or_model_provenance(self):
        from tools.workflow_eval.real_tasks import summarize
        from tests.test_workflow_real_tasks import RealTaskTests
        for mismatch in (dict(model='gpt-6.1-sol'), dict(reasoning_effort='high')):
            row = RealTaskTests().record()
            row['b'].update(mismatch)
            if row['b']['model'] == 'gpt-6.1-sol' and row['b']['reasoning_effort'] == 'xhigh':
                row['b']['escalation'] = dict(reason='high_review_material_uncertainty',
                                            evidence='High review R1: unresolved interface contract.')
            self.assertEqual(summarize([row])['valid_review_pairs'], 0)

    def test_missing_cache_is_absent_and_cannot_create_cost_estimate(self):
        from tools.workflow_eval.telemetry import usage_numbers
        from tools.workflow_eval.report import summarize
        usage=usage_numbers(dict(input_tokens=100,output_tokens=10))
        self.assertNotIn('cached_input_tokens',usage)
        got=summarize([self.row()])
        self.assertEqual(got['valid_pairs'],1)
        self.assertEqual(got['standard_short_context_sol_api_equivalent_usd'],dict(a=None,b=None))

    def test_available_cache_metadata_can_produce_reference_estimate(self):
        from tools.workflow_eval.report import summarize
        row=self.row()
        for arm in ('a','b'):
            row[arm]['usage'].update(cached_input_tokens=20,cache_write_input_tokens=0)
            row[arm]['usage_fields']=list(row[arm]['usage'])
        self.assertEqual(summarize([row])['standard_short_context_sol_api_equivalent_usd']['a'],.000264)

    def test_decomposition_uses_report_pair_eligibility(self):
        from tools.workflow_eval.report import summarize
        from tools.workflow_eval.analysis import decompose
        for failure in ('status','effort'):
            with self.subTest(failure=failure):
                row=self.row()
                if failure=='status':row['a']['status']='UNKNOWN'
                else:row['b']['reasoning_effort']='xhigh'
                got=decompose([row])
                self.assertEqual(got['pairs'],summarize([row])['valid_pairs'])
                self.assertIsNone(got['net_tokens_removed'])
                self.assertEqual(got['observed_gpt6_usage_subtotals']['a']['total_tokens'],110)

    def test_excluded_jev_overhead_is_retained_without_becoming_paired_savings(self):
        from tools.workflow_eval.analysis import decompose
        valid=self.row();excluded=self.row();excluded['id']='failed';excluded['a']['status']='UNKNOWN'
        excluded['jev']=dict(status='UNAVAILABLE',attempts=1,usage=dict(input_tokens=20,output_tokens=10))
        got=decompose([valid,excluded])
        self.assertEqual(got['pairs'],1)
        self.assertEqual(got['jev_known_token_subtotal'],30)
        self.assertEqual(got['jev_tokens_added'],0)
        self.assertEqual(got['net_tokens_removed'],0)

    def test_case_only_repository_alias_cannot_inflate_cohort(self):
        from tools.workflow_eval.real_tasks import summarize
        from tests.test_workflow_real_tasks import RealTaskTests
        original=RealTaskTests().record()
        alias=dict(original,repository=original['repository'].swapcase())
        with self.assertRaisesRegex(ValueError,'duplicate_real_task'):summarize([original,alias])


if __name__=='__main__':unittest.main()
