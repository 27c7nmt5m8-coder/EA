"""Exact-content transport regressions; fixtures contain fictional evidence only."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.workflow_eval import context as m


class ContextPacketSafety(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git('init', '-q')
        self.git('config', 'core.autocrlf', 'false')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        (self.root / 'docs').mkdir()
        (self.root / 'docs/dev-note.md').write_bytes(b'before\n')
        (self.root / 'docs/reference.md').write_bytes('exact\r\n本文\n'.encode('utf-8'))
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture')
        self.bundle = m.build_bundle(self.root, 'HEAD', ['docs/reference.md'], 'Update developer note.')
        self.prior = m.build_context_packet(self.bundle)
        (self.root / 'docs/dev-note.md').write_bytes(b'after\n')
        self.bundle = m.build_bundle(self.root, 'HEAD', ['docs/reference.md'], 'Update developer note.')

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root)

    def retained(self):
        return m.build_context_packet(self.bundle, prior=self.prior,
                                      root=self.root, recipient_has_content=True)

    def test_fresh_recipient_gets_full_text_by_default(self):
        packet = m.build_context_packet(self.bundle, prior=self.prior)
        self.assertEqual(packet['reused_paths'], [])
        self.assertFalse(packet['fresh_context_requires_expansion'])
        self.assertEqual(packet['blocks'][1]['text'], 'exact\r\n本文\n')

    def test_retained_recipient_requires_repository_freshness_and_exact_bytes(self):
        packet = self.retained()
        self.assertEqual(packet['reused_paths'], ['docs/reference.md'])
        expanded = m.expand_context_packet(packet, self.bundle, root=self.root)
        self.assertEqual(expanded['blocks'][1]['text'].encode('utf-8'),
                         b'exact\r\n\xe6\x9c\xac\xe6\x96\x87\n')
        self.assertFalse(expanded['fresh_context_requires_expansion'])
        (self.root / 'docs/reference.md').write_bytes(b'changed after bundle\n')
        with self.assertRaises(ValueError):
            self.retained()
        with self.assertRaises(ValueError):
            m.expand_context_packet(packet, self.bundle, root=self.root)

    def test_forged_text_hash_or_scope_is_rejected(self):
        for mutate in (lambda b: b['blocks'][1].update(text='different text'),
                       lambda b: b.update(changed_paths=[]),
                       lambda b: b.update(protected=0),
                       lambda b: b.update(schema_version=True),
                       lambda b: b['blocks'].append(copy.deepcopy(b['blocks'][0])),
                       lambda b: b['blocks'][1].update(path='../outside.md')):
            bundle = copy.deepcopy(self.bundle)
            mutate(bundle)
            with self.subTest(bundle=bundle), self.assertRaises(ValueError):
                m.build_context_packet(bundle, prior=self.prior, root=self.root,
                                       recipient_has_content=True)

    def test_prior_hash_alone_is_not_possession_evidence(self):
        prior = copy.deepcopy(self.prior)
        prior['blocks'][0]['text'] = 'forged prior body'
        with self.assertRaises(ValueError):
            m.build_context_packet(self.bundle, prior=prior, root=self.root,
                                   recipient_has_content=True)
        packet = self.retained()
        # A prior handle cannot bootstrap another handle without retained full text.
        next_packet = m.build_context_packet(self.bundle, prior=packet, root=self.root,
                                             recipient_has_content=True)
        self.assertEqual(next_packet['reused_paths'], [])

    def test_expansion_rejects_inconsistent_packet_even_when_no_paths_requested(self):
        packet = self.retained()
        for mutate in (lambda p: p.update(reused_paths=[]),
                       lambda p: p.update(fresh_context_requires_expansion=False),
                       lambda p: p['blocks'][1].update(content_handle='wrong handle'),
                       lambda p: p.update(task='different task'),
                       lambda p: p['blocks'][0].update(text='corrupt changed body'),
                       lambda p: p['blocks'].pop(0),
                       lambda p: p.update(reused_paths=['ghost.md'])):
            bad = copy.deepcopy(packet)
            mutate(bad)
            with self.subTest(packet=bad), self.assertRaises(ValueError):
                m.expand_context_packet(bad, self.bundle, [], root=self.root)

    def test_protected_unknown_and_expansion_disable_reuse(self):
        for task, related in [('Update risk safety constraints.', ['docs/reference.md']),
                              ('Discuss risk', ['docs/reference.md']),
                              ('Update developer note.', ['docs/reference.md', 'docs/missing.md'])]:
            bundle = m.build_bundle(self.root, 'HEAD', related, task)
            packet = m.build_context_packet(bundle, prior=self.prior, root=self.root,
                                             recipient_has_content=True)
            self.assertEqual(packet['reused_paths'], [])
            if task == 'Discuss risk':
                self.assertIs(bundle['protected'], True)
        (self.root / 'src').mkdir()
        (self.root / 'src/example.mqh').write_bytes(b'int Example;\n')
        bundle = m.build_bundle(self.root, 'HEAD', ['docs/reference.md'], 'Update module.')
        packet = m.build_context_packet(bundle, prior=self.prior, root=self.root,
                                         recipient_has_content=True)
        self.assertEqual(packet['reused_paths'], [])

    def test_distinct_context_ids_keep_same_text_multiplicity(self):
        task = dict(context_blocks=[dict(id='module-a', text='Value = 1'),
                                    dict(id='module-b', text='Value = 1')],
                    selected_context_ids=['module-a', 'module-a', 'module-b'],
                    required_context_ids=['module-a', 'module-b'])
        self.assertEqual(m.select_context(task)['text'], 'Value = 1\n\nValue = 1')

    def test_verification_sensitive_keys_and_embedded_values_are_rejected(self):
        for verification in [dict(branch='password=fictional-value'),
                             dict(status='{"password":"fictional-value"}'),
                             dict(status='{"account_number":"123456"}'),
                             dict(status=r'{"pass\u0077ord":"fictional-value"}'),
                             dict(branch='fictional-value', password='fictional-value'),
                             dict(full_gate='PASS', nested={'access_token': 'fictional-value'}),
                             dict(full_gate='PASS', nested={'token': 'fictional-value'}),
                             dict(full_gate='PASS', branch='account_number: 123456')]:
            with self.subTest(verification=verification), self.assertRaises(ValueError):
                m.build_context_packet(self.bundle, verification=verification)

    def test_verification_digest_is_diagnostic_not_validation(self):
        v = dict(full_gate='FAIL', gates=['PASS', 'FAIL', 'BLOCKED', 'UNKNOWN', 'NOT_RUN'],
                 ci_native=dict(status='UNKNOWN', equivalence='UNKNOWN', reason='not executed'))
        got = m.build_context_packet(self.bundle, verification=v)['verification']
        self.assertIs(got['requires_full_evidence'], True)
        self.assertEqual(got['summary']['gates'], v['gates'])
        self.assertEqual(got['summary']['ci_native']['reason'], 'not executed')

    def test_expansion_rejects_forged_nonallowlisted_verification_summary(self):
        packet = m.build_context_packet(self.bundle, verification={'full_gate': 'PASS'})
        for update in ({'verbose': 'unrelated raw content'}, {'token': 'fictional-value'},
                       {'gates': [{'status': 'FAIL'}]}, {'full_gate': {'status': 'FAIL'}},
                       {'ci_native': {'status': 'PASS', 'verbose': 'raw log'}}):
            bad = copy.deepcopy(packet)
            bad['verification']['summary'].update(update)
            with self.subTest(update=update), self.assertRaises(ValueError):
                m.expand_context_packet(bad, self.bundle, root=self.root)

    def test_hash_collision_cannot_replace_different_retained_body(self):
        with patch.object(m, 'digest', return_value='a' * 64):
            first = m.build_bundle(self.root, 'HEAD', ['docs/reference.md'], 'Update developer note.')
            prior = m.build_context_packet(first)
            (self.root / 'docs/reference.md').write_bytes(b'different reference\n')
            self.git('add', 'docs/reference.md')
            self.git('commit', '-qm', 'new reference')
            current = m.build_bundle(self.root, 'HEAD', ['docs/reference.md'], 'Update developer note.')
            packet = m.build_context_packet(current, prior=prior, root=self.root,
                                             recipient_has_content=True)
            self.assertEqual(packet['reused_paths'], [])
            self.assertEqual(packet['blocks'][1]['text'], 'different reference\n')

    def test_cli_default_full_retained_handle_and_exact_expansion(self):
        target = self.root / '.workflow-eval'
        target.mkdir()
        (target / 'input.json').write_text(json.dumps(self.bundle), encoding='utf-8')
        (target / 'prior.json').write_text(json.dumps(self.prior), encoding='utf-8')
        for args, want in [([], []), (['--recipient-has-content'], ['docs/reference.md']),
                           (['--recipient-has-content', '--expand', 'docs/reference.md'], [])]:
            with self.subTest(args=args):
                p = subprocess.run([sys.executable, '-c',
                                    'import sys; sys.path.insert(0, sys.argv.pop(1)); '
                                    'from tools.workflow_eval.cli import main; '
                                    'sys.exit(main(sys.argv[1:]))', str(ROOT), 'packet',
                                    str(target / 'input.json'), '--prior', str(target / 'prior.json'), *args],
                                   cwd=self.root, capture_output=True, text=True)
                self.assertEqual(p.returncode, 0, p.stderr)
                packet = json.loads((target / 'context-packet.json').read_text(encoding='utf-8'))
                self.assertEqual(packet['reused_paths'], want)
                self.assertEqual(packet['fresh_context_requires_expansion'], bool(want))
                if not want:
                    self.assertEqual(packet['blocks'][1]['text'], 'exact\r\n本文\n')

    def test_malformed_schema_and_prior_are_rejected_before_transport(self):
        for value in (None, [], {}, {'schema_version': 1, 'blocks': []}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                m.build_context_packet(value)
        with self.assertRaises(ValueError):
            m.build_context_packet(self.bundle, prior={'schema_version': 1, 'blocks': []})
        with self.assertRaises(ValueError):
            m.build_context_packet(self.bundle, prior=self.prior, recipient_has_content=True)

    def test_cli_rejects_duplicate_json_keys_and_nonfinite_values(self):
        target = self.root / '.workflow-eval'
        target.mkdir()
        raw = json.dumps(self.bundle)
        for bad in [raw.replace('"protected": false', '"protected": true, "protected": false'),
                    raw[:-1] + ', "unused": NaN}']:
            with self.subTest(bad=bad):
                (target / 'input.json').write_text(bad, encoding='utf-8')
                p = subprocess.run([sys.executable, '-c',
                                    'import sys; sys.path.insert(0, sys.argv.pop(1)); '
                                    'from tools.workflow_eval.cli import main; '
                                    'sys.exit(main(sys.argv[1:]))', str(ROOT), 'packet',
                                    str(target / 'input.json')], cwd=self.root,
                                   capture_output=True, text=True)
                self.assertNotEqual(p.returncode, 0)
                self.assertFalse((target / 'context-packet.json').exists())

    def test_cli_stale_forged_and_sensitive_inputs_fail_without_output(self):
        for kind in ('stale', 'forged', 'sensitive'):
            with self.subTest(kind=kind):
                bundle = copy.deepcopy(self.bundle)
                if kind == 'forged':
                    bundle['changed_paths'] = []
                if kind == 'sensitive':
                    bundle['task'] = 'password=fictional-value'
                target = self.root / '.workflow-eval'
                target.mkdir(exist_ok=True)
                (target / 'input.json').write_text(json.dumps(bundle), encoding='utf-8')
                (target / 'prior.json').write_text(json.dumps(self.prior), encoding='utf-8')
                if kind == 'stale':
                    (self.root / 'docs/dev-note.md').write_bytes(b'new changes\n')
                p = subprocess.run([sys.executable, '-c',
                                    'import sys; sys.path.insert(0, sys.argv.pop(1)); '
                                    'from tools.workflow_eval.cli import main; '
                                    'sys.exit(main(sys.argv[1:]))', str(ROOT), 'packet',
                                    str(target / 'input.json'), '--prior', str(target / 'prior.json')],
                                   cwd=self.root, capture_output=True, text=True)
                self.assertNotEqual(p.returncode, 0)
                self.assertFalse((target / 'context-packet.json').exists())
                (self.root / 'docs/dev-note.md').write_bytes(b'after\n')


if __name__ == '__main__':
    unittest.main()
