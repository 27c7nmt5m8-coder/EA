"""Only the confirmed continuing recipient can reuse exact prior full content."""
import copy
import importlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
import test_context_packet_safety as fixture
from tools.workflow_eval import context


class ResumeContext(unittest.TestCase):
    setUp = fixture.ContextPacketSafety.setUp
    git = fixture.ContextPacketSafety.git

    def api(self):
        from importlib.util import find_spec
        self.assertIsNotNone(find_spec('tools.workflow_eval.resume'))
        return importlib.import_module('tools.workflow_eval.resume')

    def prepare(self):
        m = self.api()
        prior = context.build_context_packet(self.bundle, root=self.root)
        receipt = m.retention_receipt(self.root, prior, recipient_id='agent_note',
            continuity_id='session_note', acknowledgement_id='confirmed_delivery',
            role='worker', model='gpt-6.1-sol', reasoning_effort='medium',
            possession_confirmed=True)
        return m, prior, receipt

    def resume(self, m, prior, receipt, **overrides):
        kwargs = dict(recipient_id='agent_note', continuity_id='session_note',
            prior=prior, receipt=receipt, specification='Update developer note.',
            repository_rules='Preserve required checks.', unresolved_questions=[])
        kwargs.update(overrides)
        return m.build_resume_request(self.root, 'worker', 'continue_note', self.bundle, **kwargs)

    def test_exact_followup_sends_handles_only_for_unchanged_related_content(self):
        m, prior, receipt = self.prepare()
        got = self.resume(m, prior, receipt)
        self.assertEqual(got['route'], 'delta')
        self.assertEqual(got['request']['target'], 'agent_note')
        packet = json.loads(got['request']['message'])['context_packet']
        self.assertEqual(packet['reused_paths'], ['docs/reference.md'])
        self.assertEqual(packet['blocks'][0]['text'], 'after\n')
        self.assertEqual(context.expand_context_packet(packet, self.bundle, root=self.root), prior)

    def test_identity_continuity_possession_and_provenance_miss_use_full_route(self):
        m, prior, receipt = self.prepare()
        for field, value in [('recipient_id', 'different'), ('continuity_id', 'different'),
                ('repository_identity', '0' * 64), ('packet_hash', '0' * 64),
                ('possession_confirmed', False), ('reasoning_effort', 'high'),
                ('model', 'unavailable'), ('acknowledgement_id', '')]:
            bad = copy.deepcopy(receipt)
            bad[field] = value
            with self.subTest(field=field):
                got = self.resume(m, prior, bad)
                self.assertEqual(got['route'], 'full')
                self.assertFalse(json.loads(got['request']['message'])['context_packet']['reused_paths'])

    def test_boolean_and_integer_receipt_fields_are_not_interchangeable(self):
        m, prior, receipt = self.prepare()
        for field, value in [('schema_version', True), ('possession_confirmed', 1)]:
            bad = copy.deepcopy(receipt)
            bad[field] = value
            self.assertEqual(self.resume(m, prior, bad)['route'], 'full')

    def test_reviewer_questions_unknown_and_expansion_force_full(self):
        m, prior, receipt = self.prepare()
        for options in [dict(unresolved_questions=['Need more dependency context.']),
                        dict(context_expansion_requested=True)]:
            self.assertEqual(self.resume(m, prior, receipt, **options)['route'], 'full')
        got = m.build_resume_request(self.root, 'reviewer', 'fresh_review', self.bundle,
            recipient_id='agent_note', continuity_id='session_note', prior=prior,
            receipt=receipt, specification='Review note.', repository_rules='Required checks.',
            unresolved_questions=[])
        self.assertEqual(got['route'], 'full')
        self.assertEqual(got['request']['fork_turns'], 'none')
        self.assertEqual(got['request']['reasoning_effort'], 'high')

    def test_prior_handles_and_stale_source_cannot_establish_retention(self):
        m, prior, receipt = self.prepare()
        got = self.resume(m, prior, receipt)
        handles = json.loads(got['request']['message'])['context_packet']
        with self.assertRaises(ValueError):
            m.retention_receipt(self.root, handles, recipient_id='agent_note',
                continuity_id='session_note', acknowledgement_id='confirmed_delivery',
                role='worker', model='gpt-6.1-sol', reasoning_effort='medium',
                possession_confirmed=True)
        (self.root / 'docs/reference.md').write_bytes(b'updated\n')
        current = context.build_bundle(self.root, 'HEAD', ['docs/reference.md'], 'Update note.')
        got = m.build_resume_request(self.root, 'worker', 'continue_note', current,
            recipient_id='agent_note', continuity_id='session_note', prior=prior,
            receipt=receipt, specification='Update note.', repository_rules='Required checks.',
            unresolved_questions=[])
        self.assertEqual(got['route'], 'full')

    def test_protected_and_unknown_scopes_keep_original_full_route(self):
        m, prior, receipt = self.prepare()
        protected = context.build_bundle(self.root, 'HEAD', ['docs/reference.md'],
                                         'Update risk guidance.')
        options = dict(recipient_id='agent_note', continuity_id='session_note',
            prior=prior, receipt=receipt, specification='Update note.',
            repository_rules='Required checks.', unresolved_questions=[])
        self.assertEqual(m.build_resume_request(self.root, 'worker', 'continue_note',
                                               protected, **options)['route'], 'full')
        (self.root / 'extra.py').write_bytes(b'print(1)\n')
        unknown = context.build_bundle(self.root, 'HEAD', ['docs/reference.md'], 'Update note.')
        got = m.build_resume_request(self.root, 'worker', 'continue_note', unknown, **options)
        self.assertEqual(got['route'], 'full')
        self.assertTrue(json.loads(got['request']['message'])['dependency_investigation_required'])

    def test_protected_specification_cannot_reuse_a_high_recipient(self):
        m, prior, receipt = self.prepare()
        receipt = m.retention_receipt(self.root, prior, recipient_id='agent_note',
            continuity_id='session_note', acknowledgement_id='confirmed_delivery', role='worker',
            model='gpt-6.1-sol', reasoning_effort='high', possession_confirmed=True)
        got = self.resume(m, prior, receipt, specification='Update risk guidance.', complex_work=True)
        self.assertEqual(got['route'], 'full')


if __name__ == '__main__':
    unittest.main()
