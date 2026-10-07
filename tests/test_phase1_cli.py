"""Public Phase 1 CLI uses strict files and keeps fresh reviewers fully expanded."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
from tools.workflow_eval import context
import test_context_packet_safety as fixture


class Phase1CLI(unittest.TestCase):
    setUp = fixture.ContextPacketSafety.setUp
    git = fixture.ContextPacketSafety.git

    def cli(self, *args):
        return subprocess.run([sys.executable, '-m', 'tools.workflow_eval.cli', *args],
            cwd=self.root, env=dict(os.environ, PYTHONPATH=str(ROOT), PYTHONUTF8='1'),
            capture_output=True, text=True, encoding='utf-8')

    def write(self, name, value):
        path = self.root / '.workflow-eval' / name
        path.write_text(json.dumps(value), encoding='utf-8')
        return str(path)

    def test_receipt_resume_and_fresh_reviewer_fallback_end_to_end(self):
        (self.root / '.workflow-eval').mkdir()
        (self.root / 'AGENTS.md').write_text('Preserve required checks.', encoding='utf-8')
        self.git('add', 'AGENTS.md')
        self.git('commit', '-qm', 'fixture rules')
        bundle = context.build_bundle(self.root, 'HEAD', ['docs/reference.md'], 'Update note.')
        bundle_path = self.write('bundle.json', bundle)
        prior_path = self.write('prior.json', context.build_context_packet(bundle, root=self.root))
        spec = self.root / '.workflow-eval/spec.md'
        spec.write_text('Update note.', encoding='utf-8')
        command = ['retention-receipt', prior_path, '--recipient', 'note_agent',
            '--continuity', 'note_session', '--acknowledgement', 'delivery_note',
            '--role', 'worker', '--observed-model', 'gpt-6.1-sol', '--observed-effort', 'medium',
            '--possession-confirmed']
        ran = self.cli(*command)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        receipt = self.root / '.workflow-eval/retention-receipt.json'
        options = ['resume-request', bundle_path, '--prior', prior_path, '--receipt', str(receipt),
            '--recipient', 'note_agent', '--continuity', 'note_session', '--task-name', 'continue_note',
            '--spec-file', str(spec)]
        ran = self.cli(*options, '--role', 'worker')
        self.assertEqual(ran.returncode, 0, ran.stderr)
        result = json.loads((self.root / '.workflow-eval/resume-request.json').read_text(encoding='utf-8'))
        self.assertEqual(result['route'], 'delta')
        ran = self.cli(*options, '--role', 'reviewer')
        self.assertEqual(ran.returncode, 0, ran.stderr)
        result = json.loads((self.root / '.workflow-eval/resume-request.json').read_text(encoding='utf-8'))
        self.assertEqual(result['route'], 'full')
        self.assertEqual(json.loads(result['request']['message'])['context_packet']['reused_paths'], [])

    def test_measurement_cli_persists_null_missing_reasons(self):
        (self.root / '.workflow-eval').mkdir()
        path = self.write('observed.json', dict(task_id='baseline', repository='27c7nmt5m8-coder/EA'))
        ran = self.cli('optimization-measurement', path)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        result = json.loads((self.root / '.workflow-eval/optimization-measurement.json').read_text(encoding='utf-8'))
        self.assertIsNone(result['total_tokens'])
        self.assertIn('total_tokens', result['missing_reasons'])

    def test_verification_cli_checks_actual_git_source_instead_of_caller_claims(self):
        (self.root / '.workflow-eval').mkdir()
        record = dict(source='a' * 40, tree='b' * 40, scope=['docs/reference.md'],
            command=['note-check'], platform='fixture', toolchain='fixture',
            exit_code=0, status='PASS', passed=1, failed=0, warnings=[], ci_identity=None,
            equivalence='LOCAL_ONLY', recorded_at='2026-10-07T00:00:00Z', log_paths=[])
        self.write('check.json', record)
        current = {key: record[key] for key in ('source', 'tree', 'scope', 'command',
                                               'platform', 'toolchain', 'equivalence')}
        current_path = self.write('current.json', current)
        ran = self.cli('verification-manifest', '.workflow-eval/check.json')
        self.assertEqual(ran.returncode, 0, ran.stderr)
        ran = self.cli('verification-context', '.workflow-eval/verification-manifest.json',
                       '--current', current_path)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        result = json.loads((self.root / '.workflow-eval/verification-context.json').read_text(encoding='utf-8'))
        self.assertFalse(result['verified_pass'])
        self.assertEqual(result['route'], 'original')
        self.assertIn('current_source_mismatch', result['reasons'])


if __name__ == '__main__':
    unittest.main()
