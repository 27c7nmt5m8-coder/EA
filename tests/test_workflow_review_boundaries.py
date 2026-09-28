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

    def test_real_ea_high_is_rejected_before_provider_execution(self):
        from tools.workflow_eval.real_tasks import perform_review
        with patch('tools.workflow_eval.real_tasks.subprocess.run') as call:
            with self.assertRaisesRegex(ValueError,'model_floor'):
                perform_review('Review order risk changes.','Protected change.','high')
        call.assert_not_called()

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
                self.assertEqual(got['routing']['sol_effort'],'xhigh')
                call.assert_not_called()

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
