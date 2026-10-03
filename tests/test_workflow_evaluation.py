"""Offline behavioral contracts; no real credentials or provider requests."""
import copy
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class WorkflowEvaluation(unittest.TestCase):
    def module(self, name):
        try:
            return importlib.import_module('tools.workflow_eval.' + name)
        except ModuleNotFoundError:
            self.fail('workflow evaluation implementation is missing')

    def facts(self, **updates):
        result = dict(paths=['docs/dev-note.md'], dependency='known', module_count=1,
                      tests='PASS', changed_lines=4, missing_context=[], sensitive=False,
                      scope_ok=True, current=True, protected=False)
        result.update(updates)
        return result

    def answer(self, **updates):
        result = dict(type='choice', choice='candidate', confidence=.95,
                      probabilities=dict(candidate=.96, review=.03, unknown=.01))
        result.update(updates)
        return result

    def test_usage_deduplicates_cumulative_and_does_not_double_count_reasoning(self):
        m = self.module('telemetry')
        events = [dict(type='event_msg', payload=dict(type='token_count', info=dict(
            total_token_usage=dict(input_tokens=i, cached_input_tokens=c,
                                   output_tokens=o, reasoning_output_tokens=2, total_tokens=i+o))))
                  for i, c, o in [(100, 60, 10), (100, 60, 10), (300, 180, 20)]]
        got = m.extract_usage(events)
        self.assertEqual(got['usage']['total_tokens'], 320)
        self.assertEqual(got['usage']['cached_input_tokens'], 180)
        self.assertEqual(got['observed_usage_updates'], 2)

    def test_reset_and_inherited_usage_are_unknown_not_savings(self):
        m = self.module('telemetry')
        events = [dict(type='event_msg', payload=dict(type='token_count', info=dict(
            total_token_usage=dict(input_tokens=i, output_tokens=10, total_tokens=i+10))))
                  for i in [100, 20]]
        self.assertEqual(m.extract_usage(events)['status'], 'UNKNOWN')

    def test_important_changes_cannot_bypass_sol_even_with_high_confidence(self):
        m = self.module('triage')
        for updates in [dict(paths=['src/MT3Config.mqh']), dict(dependency='unknown'),
                        dict(module_count=2), dict(protected=True), dict(tests='BLOCKED'),
                        dict(missing_context=['interface']), dict(current=False),
                        dict(scope_ok=False), dict(paths=['tests/run_all.py'])]:
            with self.subTest(updates=updates):
                got = m.route(self.facts(**updates), self.answer())
                self.assertEqual(got['shadow_route'], 'review')
                self.assertFalse(got['actual_review_skipped'])
                self.assertEqual(got['sol_effort'], 'high')

    def test_low_risk_candidate_is_shadow_only_and_low_confidence_escalates(self):
        m = self.module('triage')
        got = m.route(self.facts(), self.answer())
        self.assertEqual(got['shadow_route'], 'candidate')
        self.assertEqual(got['actual_route'], 'review')
        self.assertFalse(got['actual_review_skipped'])
        self.assertEqual(m.route(self.facts(), self.answer(confidence=.89))['shadow_route'], 'review')

    def test_invalid_distribution_and_noul_fail_closed(self):
        m = self.module('triage')
        for a in [self.answer(confidence=float('nan')), self.answer(type='noul'),
                  self.answer(probabilities=dict(candidate=.1, review=.9, unknown=0)),
                  self.answer(probabilities=dict(candidate=1.1, review=-.1, unknown=0))]:
            self.assertEqual(m.route(self.facts(), a)['shadow_route'], 'review')

    def test_state_with_unknown_fields_or_secrets_is_never_sent(self):
        m = self.module('triage')
        state = dict(task='Update developer note.', evidence='The requested sentence is present.')
        self.assertEqual(m.safe_state(state), state)
        for unsafe in [dict(state, unexpected='raw content'),
                       dict(state, evidence='password=fictional-value'),
                       dict(state, task='mail person@example.invalid')]:
            with self.assertRaises(ValueError):
                m.safe_state(unsafe)

    def test_http_failure_is_sanitized_without_retry(self):
        m = self.module('triage')
        from urllib.error import HTTPError
        calls = []
        def failing(request, timeout):
            calls.append(request)
            raise HTTPError(request.full_url, 401, 'fictional-secret', {}, None)
        got = m.call_jev(dict(task='Developer note.', evidence='Sentence updated.'),
                         key='fictional-key', opener=failing)
        self.assertEqual(len(calls), 1)
        self.assertEqual(got['status'], 'UNAVAILABLE')
        self.assertNotIn('fictional-secret', json.dumps(got))

    def test_bundle_tracks_untracked_deletions_and_stale_evidence(self):
        m = self.module('context')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=root)
            git('init', '-q'); git('config', 'user.email', 'fixture@example.invalid')
            git('config', 'user.name', 'Fixture')
            (root/'note.md').write_text('before\n', encoding='utf-8')
            git('add', '.'); git('commit', '-qm', 'fixture')
            (root/'note.md').unlink(); (root/'new.md').write_text('new\n', encoding='utf-8')
            bundle = m.build_bundle(root, 'HEAD', ['new.md'], 'Update note')
            self.assertEqual(set(bundle['changed_paths']), {'note.md', 'new.md'})
            self.assertTrue(m.is_current(root, bundle))
            (root/'new.md').write_text('changed\n', encoding='utf-8')
            self.assertFalse(m.is_current(root, bundle))

    def test_selection_reports_missing_required_context_without_truncating(self):
        m = self.module('context')
        task = dict(context_blocks=[dict(id='a', text='one'), dict(id='b', text='two')],
                    selected_context_ids=['a'], required_context_ids=['a', 'b'])
        selected = m.select_context(task)
        self.assertEqual(selected['missing_context'], ['b'])
        self.assertEqual(selected['text'], 'one')

    def test_report_blocks_critical_miss_and_keeps_missing_values_unknown(self):
        m = self.module('report')
        row = dict(id='one', split='holdout', truth='review', severity='critical',
                   a=dict(status='OK', route='review', usage=dict(input_tokens=100, output_tokens=20, total_tokens=120), elapsed_seconds=2),
                   b=dict(status='OK', route='candidate', usage=dict(input_tokens=80, output_tokens=10, total_tokens=90), elapsed_seconds=1),
                   shadow=dict(shadow_route='candidate', actual_review_skipped=False),
                   jev=dict(status='OK', answer=self.answer(), usage=dict(input_tokens=10, output_tokens=2)),
                   missing_context=[], rework_count=None)
        for arm in ('a', 'b'):
            row[arm].update(model='gpt-6-sol', reasoning_effort='xhigh')
        got = m.summarize([row])
        self.assertEqual(got['critical_misses'], 1)
        self.assertEqual(got['gpt6_reduction_percent']['input_tokens'], 20)
        self.assertEqual(got['rework_count'], None)
        self.assertFalse(got['review_skip_enabled'])
        self.assertEqual(got['decision'], 'BLOCKED_CRITICAL_MISS')

    def test_pair_failure_is_excluded_instead_of_counted_as_zero_tokens(self):
        m = self.module('report')
        got = m.summarize([dict(id='x', split='holdout', a=dict(status='OK'), b=dict(status='UNAVAILABLE'))])
        self.assertEqual(got['valid_pairs'], 0)
        self.assertEqual(got['gpt6_reduction_percent']['total_tokens'], None)

    def test_codex_events_capture_usage_without_retaining_raw_output(self):
        m = self.module('benchmark')
        events = [dict(type='item.completed', item=dict(type='agent_message', text='{"route":"review"}')),
                  dict(type='turn.completed', usage=dict(input_tokens=100, cached_input_tokens=50, output_tokens=8))]
        got = m.parse_codex(events)
        self.assertEqual(got['route'], 'review')
        self.assertEqual(got['usage']['total_tokens'], 108)
        self.assertEqual(got['observed_completed_turns'], 1)

    def test_model_tool_execution_or_missing_usage_invalidates_benchmark(self):
        m = self.module('benchmark')
        for events in [[dict(type='item.completed', item=dict(type='command_execution', command='echo secret'))],
                       [dict(type='item.completed', item=dict(type='agent_message', text='{"route":"candidate"}'))]]:
            self.assertEqual(m.parse_codex(events)['status'], 'UNKNOWN')

    def test_phase_events_count_failed_runs_and_rework_without_guessing(self):
        m = self.module('telemetry')
        rows = [dict(task_id='t', pair_id='p', arm='A', phase=phase, event='end',
                     round=1, status=status, elapsed_seconds=duration, failed_cases=cases)
                for phase, status, duration, cases in [('additional_review', 'PASS', 3, 0),
                                                       ('test', 'FAIL', 2, 4), ('rework', 'PASS', 5, 0)]]
        got = m.summarize_events(rows)
        self.assertEqual(got['review_count'], 1)
        self.assertEqual(got['review_seconds'], 3)
        self.assertEqual(got['test_failed_runs'], 1)
        self.assertEqual(got['test_failed_cases'], 4)
        self.assertEqual(got['rework_count'], 1)

    def test_cli_offline_help_and_record_reject_unknown_secret_fields(self):
        root = Path(__file__).resolve().parents[1]
        m = self.module('cli')
        process = subprocess.run([sys.executable, '-m', 'tools.workflow_eval.cli', '--help'],
                                 cwd=root, capture_output=True, text=True)
        self.assertEqual(process.returncode, 0)
        with self.assertRaises(ValueError):
            self.module('telemetry').validate_event(dict(task_id='t', pair_id='p', arm='A',
                phase='review', event='end', password='fictional'))

    def test_incomplete_report_record_is_excluded(self):
        m = self.module('report')
        row = dict(id='x', a=dict(status='OK', usage=dict(input_tokens=1, output_tokens=1)),
                   b=dict(status='OK', usage=dict(input_tokens=1, output_tokens=1)))
        self.assertEqual(m.summarize([row])['valid_pairs'], 0)

    def test_missing_context_is_expanded_before_review(self):
        m = self.module('context')
        task = dict(context_blocks=[dict(id='a', text='one'), dict(id='b', text='required detail')],
                    selected_context_ids=['a'], required_context_ids=['a', 'b'])
        got = m.expand_context(task)
        self.assertEqual(got['initial_missing_context'], ['b'])
        self.assertEqual(got['missing_context'], [])
        self.assertIn('required detail', got['text'])

    def test_plain_english_be_is_not_break_even_but_protected_terms_remain(self):
        m = self.module('triage')
        self.assertIsNone(m.PROTECTED.search('The event may be start or end.'))
        for sentence in ['Change BE behavior.', 'Change Break Even.', 'Change stop loss.', 'Change take profit.']:
            self.assertIsNotNone(m.PROTECTED.search(sentence))

    def test_bundle_rename_retains_old_and_new_paths(self):
        m = self.module('context')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=root)
            git('init', '-q'); git('config', 'user.email', 'fixture@example.invalid'); git('config', 'user.name', 'Fixture')
            (root/'old.md').write_text('documentation\n', encoding='utf-8')
            git('add', '.'); git('commit', '-qm', 'fixture')
            git('mv', 'old.md', 'new.md')
            self.assertEqual(set(m.build_bundle(root, 'HEAD', [], 'Rename note')['changed_paths']), {'old.md', 'new.md'})

    def test_output_stays_local_when_generated_directory_is_a_symlink(self):
        m = self.module('cli')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'repo'; root.mkdir()
            outside = Path(tmp)/'outside'; outside.mkdir()
            try:
                (root/'.workflow-eval').symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest('symlink creation unavailable')
            with self.assertRaises(ValueError):
                m.output(root, 'metrics.json', {})

    def test_missing_phase_measurements_are_null(self):
        m = self.module('telemetry')
        got = m.summarize_events([])
        for key in ['review_count', 'review_seconds', 'test_failed_runs', 'test_failed_cases', 'rework_count']:
            self.assertIsNone(got[key])

    def test_shared_context_is_materialized_without_copying_into_each_fixture(self):
        m = self.module('cli')
        dataset = dict(common_context_blocks=[dict(id='shared', text='reference')],
                       cases=[dict(id='t', context_blocks=[dict(id='task', text='change')])])
        self.assertEqual([b['text'] for b in m.dataset_cases(dataset)[0]['context_blocks']], ['change', 'reference'])

    def review_row(self):
        return dict(id='critical', truth='review', severity='critical', facts=self.facts(protected=True),
                    a=dict(status='OK', route='candidate', model='gpt-6-sol', reasoning_effort='xhigh',
                           usage=dict(input_tokens=100, output_tokens=10), elapsed_seconds=1),
                    b=dict(status='OK', route='review', model='gpt-6-sol', reasoning_effort='xhigh',
                           usage=dict(input_tokens=80, output_tokens=10), elapsed_seconds=1),
                    jev=dict(status='UNAVAILABLE', attempts=1, usage=None))

    def test_critical_observation_blocks_even_when_partner_measurement_failed(self):
        for failure in (False, True):
            row = self.review_row()
            if failure: row['b']['status'] = 'UNAVAILABLE'
            got = self.module('report').summarize([row])
            self.assertEqual(got['critical_misses'], 1)
            self.assertEqual(got['decision'], 'BLOCKED_CRITICAL_MISS')

    def test_missing_attempted_jev_usage_never_becomes_complete_savings(self):
        got = self.module('report').summarize([self.review_row()])
        self.assertIsNone(got['jev_total_tokens'])
        self.assertIsNone(got['b_all_provider_total_tokens'])
        self.assertIsNone(got['all_provider_total_reduction_percent'])
        self.assertEqual(got['jev_known_token_subtotal'], 0)
        self.assertEqual(got['jev_usage_missing_attempts'], 1)

    def test_raw_critical_jev_miss_blocks_even_when_shadow_escalated(self):
        row = self.review_row(); row['a']['route'] = 'review'
        row['jev'] = dict(status='OK', answer=self.answer(confidence=.5), attempts=1,
                          usage=dict(input_tokens=2, output_tokens=1))
        row['shadow'] = dict(shadow_route='review')
        self.assertEqual(self.module('report').summarize([row])['decision'], 'BLOCKED_CRITICAL_MISS')

    def test_report_rejects_missing_or_below_floor_model_provenance(self):
        for model, effort in [('gpt-6-luna', 'low'), (None, None), ('gpt-6.1-sol', 'medium')]:
            row = self.review_row()
            for arm in ('a', 'b'): row[arm].update(model=model, reasoning_effort=effort)
            self.assertEqual(self.module('report').summarize([row])['valid_pairs'], 0)

    def test_protected_safety_meanings_and_credentials_are_rejected(self):
        m = self.module('triage')
        for text in ['EA safety behavior', 'Document disabling the spread cap.',
                     'Disable the duplicate-prevention check.', '最大DD制限', 'プロップファーム制限']:
            self.assertIsNotNone(m.PROTECTED.search(text), text)
            got = m.route(self.facts(protected=bool(m.PROTECTED.search(text))), self.answer())
            self.assertEqual(got['sol_effort'], 'high')
        for text in ["token = 'fictional-access-token-value'", 'access_token: fictional-access-value']:
            with self.assertRaises(ValueError): m.safe_state(dict(task='Developer note.', evidence=text))

    def test_unknown_benchmark_facts_are_rejected_before_any_model_call(self):
        from unittest.mock import patch
        case = dict(id='x', split='holdout', truth='candidate', severity='low', task='Developer note.',
                    facts=self.facts(api_key='fictional-secret-for-review'),
                    context_blocks=[dict(id='a', text='Updated sentence.')],
                    selected_context_ids=['a'], required_context_ids=['a'])
        m = self.module('benchmark')
        for facts in [case['facts'], self.facts(paths=['token=fictional-access-value'])]:
            with patch.object(m, 'sol_review') as call:
                with self.assertRaises(ValueError): m.run_case(dict(case, facts=facts), 0)
                call.assert_not_called()

    def test_index_change_invalidates_bundle_and_deletion_requires_context(self):
        m = self.module('context')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'docs').mkdir()
            def git(*args): return subprocess.check_output(['git', *args], cwd=root)
            git('init', '-q'); git('config', 'user.email', 'fixture@example.invalid'); git('config', 'user.name', 'Fixture')
            path = root/'docs/dev-note.md'; path.write_text('original\n', encoding='utf-8')
            git('add', '.'); git('commit', '-qm', 'fixture')
            path.write_text('working\n', encoding='utf-8'); git('add', '.')
            bundle = m.build_bundle(root, 'HEAD', [], 'Update note')
            blob = git('rev-parse', 'HEAD:docs/dev-note.md').decode().strip()
            git('update-index', '--cacheinfo', '100644,'+blob+',docs/dev-note.md')
            self.assertFalse(m.is_current(root, bundle))
            path.unlink()
            deleted = m.build_bundle(root, 'HEAD', [], 'Delete note')
            self.assertIn('docs/dev-note.md', deleted['expansion_required'])
            self.assertEqual(deleted['dependency'], 'unknown')

    def test_malformed_model_json_and_mixed_telemetry_efforts_are_unknown(self):
        events = [dict(type='item.completed', item=dict(type='agent_message', text='[]')),
                  dict(type='turn.completed', usage=dict(input_tokens=1, output_tokens=1))]
        self.assertEqual(self.module('benchmark').parse_codex(events)['status'], 'UNKNOWN')
        got = self.module('telemetry').extract_usage([dict(type='turn_context', payload=dict(model='gpt-6-sol', effort=e))
                                                    for e in ['high', None]])
        self.assertEqual(got['status'], 'UNKNOWN')


    def test_context_selection_keeps_distinct_ids_with_identical_text(self):
        m = self.module('context')
        task = dict(context_blocks=[dict(id='a', text='same evidence'),
                                    dict(id='b', text='same evidence')],
                    selected_context_ids=['a', 'b'], required_context_ids=['a', 'b'])
        got = m.select_context(task)
        self.assertEqual(got['text'], 'same evidence\n\nsame evidence')
        self.assertEqual(got['missing_context'], [])

    def test_context_packet_reuses_only_exact_unchanged_low_risk_related_text(self):
        m = self.module('context')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'docs').mkdir()
            def git(*args): return subprocess.check_output(['git', *args], cwd=root)
            git('init', '-q'); git('config', 'user.email', 'fixture@example.invalid')
            git('config', 'user.name', 'Fixture')
            changed = root/'docs/dev-note.md'; related = root/'docs/reference.md'
            changed.write_text('before\n', encoding='utf-8')
            related.write_text('stable reference\n', encoding='utf-8')
            git('add', '.'); git('commit', '-qm', 'fixture')
            prior_bundle = m.build_bundle(root, 'HEAD', ['docs/reference.md'], 'Update developer note')
            prior = m.build_context_packet(prior_bundle)
            changed.write_text('after\n', encoding='utf-8')
            bundle = m.build_bundle(root, 'HEAD', ['docs/reference.md'], 'Update developer note')
            packet = m.build_context_packet(bundle, prior=prior, root=root, recipient_has_content=True)
            modes = {b['path']: b['content_mode'] for b in packet['blocks']}
            self.assertEqual(modes['docs/dev-note.md'], 'full')
            self.assertEqual(modes['docs/reference.md'], 'reused_exact')
            reused = next(b for b in packet['blocks'] if b['path'] == 'docs/reference.md')
            self.assertNotIn('text', reused)
            self.assertEqual(packet['reused_paths'], ['docs/reference.md'])
            self.assertTrue(packet['fresh_context_requires_expansion'])
            expanded = m.expand_context_packet(packet, bundle, ['docs/reference.md'], root=root)
            restored = next(b for b in expanded['blocks'] if b['path'] == 'docs/reference.md')
            self.assertEqual(restored['text'], related.read_bytes().decode('utf-8'))
            self.assertEqual(expanded['reused_paths'], [])
            self.assertFalse(expanded['fresh_context_requires_expansion'])

    def test_context_packet_disables_reuse_for_unknown_or_protected_scope(self):
        m = self.module('context')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'docs').mkdir(); (root/'src').mkdir()
            def git(*args): return subprocess.check_output(['git', *args], cwd=root)
            git('init', '-q'); git('config', 'user.email', 'fixture@example.invalid')
            git('config', 'user.name', 'Fixture')
            related = root/'docs/reference.md'; source = root/'src/module.mqh'
            related.write_text('stable reference\n', encoding='utf-8')
            source.write_text('int Value(){ return 1; }\n', encoding='utf-8')
            git('add', '.'); git('commit', '-qm', 'fixture')
            prior = m.build_context_packet(m.build_bundle(
                root, 'HEAD', ['docs/reference.md'], 'Update developer note'))
            source.write_text('int Value(){ return 2; }\n', encoding='utf-8')
            bundle = m.build_bundle(root, 'HEAD', ['docs/reference.md'], 'Update module')
            self.assertEqual(bundle['dependency'], 'unknown')
            packet = m.build_context_packet(bundle, prior=prior, root=root, recipient_has_content=True)
            self.assertEqual(packet['reused_paths'], [])
            self.assertFalse(packet['fresh_context_requires_expansion'])
            self.assertTrue(all(b['content_mode'] == 'full' for b in packet['blocks']))

    def test_context_packet_verification_keeps_digest_and_small_allowlisted_summary(self):
        m = self.module('context')
        bundle = dict(schema_version=3, base='a'*40, head='b'*40, fingerprint='c'*64,
                      index_sha256='d'*64, changed_paths=[], changed_lines=0, patch='',
                      blocks=[], task='Developer note.', dependency='known',
                      expansion_required=[], protected=False, status_porcelain='')
        verification = dict(full_gate='PASS', authoritative_release='INCOMPLETE',
                            commit='b'*40, branch='topic', gates=['PASS']*5,
                            verbose={'large': 'detail that should not be copied'})
        packet = m.build_context_packet(bundle, verification=verification)
        self.assertRegex(packet['verification']['sha256'], r'^[0-9a-f]{64}$')
        self.assertEqual(packet['verification']['summary']['full_gate'], 'PASS')
        self.assertNotIn('verbose', packet['verification']['summary'])


if __name__ == '__main__':
    unittest.main()
