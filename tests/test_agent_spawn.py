"""Spawn arguments are generated, not proof of host execution metadata."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
from tools.workflow_eval import context
import test_context_packet_safety as packet_fixture
try:
    from tools.workflow_eval.spawn import build_spawn_request
except ImportError:
    build_spawn_request = None


class AgentSpawn(unittest.TestCase):
    setUp = packet_fixture.ContextPacketSafety.setUp
    git = packet_fixture.ContextPacketSafety.git

    def request(self, role='worker', **kwargs):
        self.assertIsNotNone(build_spawn_request, 'spawn request helper missing')
        options = dict(specification='Update developer note; preserve required checks.',
                       repository_rules='No live orders. Preserve mandatory independent review.',
                       unresolved_questions=[])
        options.update(kwargs)
        return build_spawn_request(self.root, role, 'bounded_task', self.bundle, **options)

    def test_roles_are_explicit_even_with_parent_high_defaults(self):
        for role, effort in [('explorer', 'medium'), ('researcher', 'medium'),
                             ('worker', 'medium'), ('reviewer', 'high')]:
            with self.subTest(role=role):
                args = self.request(role)
                self.assertEqual(set(args), {'task_name', 'message', 'model', 'reasoning_effort', 'fork_turns'})
                self.assertEqual(args['model'], 'gpt-6.1-sol')
                self.assertEqual(args['reasoning_effort'], effort)
                self.assertEqual(args['fork_turns'], 'none')
                payload = json.loads(args['message'])
                self.assertEqual(payload['read_only'], role != 'worker')
                self.assertEqual(payload['independent_context'], role == 'reviewer')

    def test_supported_bounded_turns_only_in_role_limits(self):
        for role, scopes in [('explorer', ['1', '2']), ('researcher', ['1', '2']),
                             ('worker', ['1', '2', '3'])]:
            for scope in scopes:
                self.assertEqual(self.request(role, fork_turns=scope)['fork_turns'], scope)
        for scope in ['1', '2', 'all']:
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                self.request('reviewer', fork_turns=scope)

    def test_unsupported_or_omitted_values_cannot_escape(self):
        for value in [None, 1, 0, True, '', '0', '-1', '01', 'last_n', 'NONE', '4', '1.0']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.request(fork_turns=value)

    def test_full_history_requires_explicit_override_capability(self):
        # Current host forbids model/effort overrides with all. A reason cannot
        # make that incompatible call legal; caller must use none plus packet.
        for reason in [None, '', 'Exact historical constraints needed.']:
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, 'full_history'):
                self.request(fork_turns='all', full_history_reason=reason)

    def test_worker_high_conditions_remain(self):
        self.assertEqual(self.request(complex_work=True)['reasoning_effort'], 'high')
        bundle = context.build_bundle(self.root, 'HEAD', ['docs/reference.md'], 'Inspect lot safety.')
        self.bundle = bundle
        self.assertEqual(self.request()['reasoning_effort'], 'high')
        for role in ['explorer', 'researcher']:
            self.assertEqual(self.request(role)['reasoning_effort'], 'medium')
        with self.assertRaises(ValueError):
            self.request(complex_work='false')

    def test_fresh_reviewer_expands_retained_handles_and_preserves_bytes(self):
        packet = context.build_context_packet(self.bundle, prior=self.prior,
                                              root=self.root, recipient_has_content=True)
        self.assertTrue(packet['reused_paths'])
        payload = json.loads(self.request('reviewer', packet=packet)['message'])
        self.assertEqual(payload['context_packet']['reused_paths'], [])
        self.assertEqual(payload['context_packet']['blocks'][1]['text'], 'exact\r\n本文\n')
        self.assertEqual(payload['context_packet']['base'], self.bundle['base'])
        self.assertEqual(payload['context_packet']['patch'], self.bundle['patch'])
        self.assertEqual(payload['unresolved_questions'], [])

    def test_missing_context_stops_until_acquired(self):
        self.bundle = context.build_bundle(self.root, 'HEAD', ['docs/missing.md'], 'Update developer note.')
        with self.assertRaisesRegex(ValueError, 'context_expansion_required'):
            self.request()
        (self.root / 'docs/missing.md').write_text('Required dependency evidence.', encoding='utf-8')
        self.bundle = context.build_bundle(self.root, 'HEAD', ['docs/missing.md'], 'Update developer note.')
        self.assertEqual(self.request()['fork_turns'], 'none')

    def test_unknown_dependency_requests_investigation_not_review_approval(self):
        (self.root / 'helper.py').write_text('print(1)\n', encoding='utf-8')
        self.bundle = context.build_bundle(self.root, 'HEAD', [], 'Update developer note.')
        payload = json.loads(self.request('reviewer')['message'])
        self.assertTrue(payload['dependency_investigation_required'])
        self.assertEqual(payload['context_packet']['reused_paths'], [])

    def test_stale_and_forged_packets_are_rejected(self):
        packet = context.build_context_packet(self.bundle)
        bad = copy.deepcopy(packet)
        bad['blocks'][0]['text'] = 'forged'
        with self.assertRaises(ValueError):
            self.request(packet=bad)
        (self.root / 'docs/reference.md').write_text('Changed dependency.', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.request(packet=packet)

    def test_verification_digest_requires_original_evidence(self):
        verification = dict(status='BLOCKED', gates=['BLOCKED'], warning='Synthetic unavailable tool.')
        packet = context.build_context_packet(self.bundle, verification=verification)
        with self.assertRaisesRegex(ValueError, 'verification_evidence_required'):
            self.request('reviewer', packet=packet)
        payload = json.loads(self.request('reviewer', packet=packet, verification=verification)['message'])
        self.assertEqual(payload['verification_evidence'], verification)
        self.assertTrue(payload['context_packet']['verification']['requires_full_evidence'])
        with self.assertRaises(ValueError):
            self.request(packet=packet, verification=dict(status='PASS'))

    def test_invalid_roles_specs_questions_and_sensitive_text_are_rejected(self):
        for options in [dict(role='root'), dict(specification=''), dict(repository_rules=''),
                        dict(unresolved_questions='unknown'), dict(unresolved_questions=[1]),
                        dict(specification='password=synthetic_forbidden')]:
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.request(**options)

    def test_spawn_cli_generates_only_tool_arguments(self):
        # Exercise the real CLI and safe evidence loaders against fixture Git.
        for name, data in [('bundle.json', self.bundle)]:
            (self.root / name).write_text(json.dumps(data), encoding='utf-8')
        (self.root / 'AGENTS.md').write_text('No live orders.', encoding='utf-8')
        (self.root / 'spec.md').write_text('Update note; preserve checks.', encoding='utf-8')
        # Build again after creating the required explicit evidence files.
        self.bundle = context.build_bundle(self.root, 'HEAD', [], 'Update developer note.')
        # Evidence inputs must be ignored to avoid self-referential fingerprint.
        (self.root / '.gitignore').write_text('bundle.json\n.workflow-eval/\n', encoding='utf-8')
        self.bundle = context.build_bundle(self.root, 'HEAD', [], 'Update developer note.')
        (self.root / 'bundle.json').write_text(json.dumps(self.bundle), encoding='utf-8')
        result = subprocess.run([sys.executable, '-m', 'tools.workflow_eval.cli', 'spawn-request',
                                 'bundle.json', '--role', 'reviewer', '--task-name', 'review_note',
                                 '--spec-file', 'spec.md'], cwd=self.root, capture_output=True,
                                env=__import__('os').environ | {'PYTHONPATH': str(ROOT)})
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        args = json.loads((self.root / '.workflow-eval/spawn-request.json').read_text())
        self.assertEqual(args['fork_turns'], 'none')
        self.assertEqual(args['reasoning_effort'], 'high')


if __name__ == '__main__':
    unittest.main()
