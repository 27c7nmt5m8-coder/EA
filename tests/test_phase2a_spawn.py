"""Fresh spawn must resolve canonical policy bodies, never only IDs."""
import json
from pathlib import Path
import shutil
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
from tools.workflow_eval import context
from tools.workflow_eval.spawn import build_spawn_request
from tools.workflow_eval.serialization import canonical_hash
import test_context_packet_safety as fixture


class CanonicalSpawn(unittest.TestCase):
    setUp = fixture.ContextPacketSafety.setUp
    git = fixture.ContextPacketSafety.git

    def install_rules(self):
        shutil.copytree(ROOT / '.agents/rules', self.root / '.agents/rules')
        (self.root / 'AGENTS.md').write_bytes((ROOT / 'AGENTS.md').read_bytes())
        self.bundle = context.build_bundle(self.root, 'HEAD', [], 'Inspect developer workflow.')

    def request(self):
        return build_spawn_request(self.root, 'reviewer', 'independent_review', self.bundle,
            specification='Preserve actual source and all required deterministic checks.',
            repository_rules=(self.root / 'AGENTS.md').read_text(encoding='utf-8'),
            unresolved_questions=[])

    def test_fresh_reviewer_has_every_required_rule_body(self):
        self.install_rules()
        from tools.workflow_eval.rules import instruction_texts, required_rule_ids
        message = self.request()['message']
        payload = json.loads(message)
        required = required_rule_ids(self.root, 'agents')
        for body in instruction_texts(self.root, required):
            self.assertIn(body, payload['repository_rules'])
        self.assertEqual(payload['context_packet']['reused_paths'], [])
        self.assertEqual(self.request()['reasoning_effort'], 'high')

    def test_missing_canonical_authority_cannot_use_compressed_document(self):
        self.install_rules()
        (self.root / '.agents/rules/canonical.json').unlink()
        self.bundle = context.build_bundle(self.root, 'HEAD', [], 'Inspect developer workflow.')
        with self.assertRaises(ValueError):
            self.request()

    def test_corrupt_canonical_authority_cannot_generate_spawn(self):
        self.install_rules()
        catalog = self.root / '.agents/rules/canonical.json'
        catalog.write_text('{}', encoding='utf-8')
        self.bundle = context.build_bundle(self.root, 'HEAD', [], 'Inspect developer workflow.')
        with self.assertRaises(ValueError):
            self.request()

    def test_rule_body_already_in_rules_is_not_repeated_in_instructions(self):
        self.install_rules()
        payload = json.loads(self.request()['message'])
        for body in payload['instructions']:
            self.assertNotIn(body, payload['repository_rules'])
        self.assertTrue(payload['independent_context'])
        self.assertTrue(payload['read_only'])


class VerificationSpawn(unittest.TestCase):
    setUp = fixture.ContextPacketSafety.setUp
    git = fixture.ContextPacketSafety.git

    def evidence(self):
        from tools.workflow_eval.verification_context import build_verification_manifest
        from tools.workflow_eval.verification_delivery import build_verification_delivery
        directory = self.root / '.workflow-eval'
        directory.mkdir()
        record = dict(source=self.bundle['head'], tree=self.git('rev-parse', 'HEAD^{tree}').decode().strip(),
            scope=['docs/dev-note.md'], command=['fictional-check'], platform='fictional',
            toolchain={'checker': '1'}, exit_code=0, status='PASS', passed=1, failed=0,
            warnings=[], ci_identity=None, equivalence='LOCAL_ONLY',
            recorded_at='2026-10-07T00:00:00Z', protected=False, dependency='known',
            log_paths=['.workflow-eval/check.log'])
        (directory / 'check.json').write_text(json.dumps(record), encoding='utf-8')
        (directory / 'check.log').write_text('Exact fictional verification body.\n', encoding='utf-8')
        manifest = build_verification_manifest(self.root, '.workflow-eval/check.json',
                                               log_paths=record['log_paths'])
        current = {name: record[name] for name in
            ('source', 'tree', 'scope', 'command', 'platform', 'toolchain', 'equivalence', 'protected', 'dependency')}
        sources = [dict(source_identity={'surface': surface}, manifest=manifest, current=current)
                   for surface in ('review', 'completion')]
        # Evidence artifacts are intentionally ignored workflow outputs.
        self.bundle = context.build_bundle(self.root, 'HEAD', ['docs/reference.md'], 'Update developer note.')
        return build_verification_delivery(self.root, sources, reviewer_request=True)

    def request(self, delivery, **kwargs):
        return build_spawn_request(self.root, 'reviewer', 'independent_review', self.bundle,
            specification='Preserve exact source and deterministic checks.',
            repository_rules='Preserve independent review. No live orders.', unresolved_questions=[],
            verification_delivery=delivery, **kwargs)

    def test_spawn_preserves_original_once_and_both_source_aliases(self):
        payload = json.loads(self.request(self.evidence())['message'])
        delivered = payload['verification_evidence']
        self.assertEqual(len(delivered['aliases']), 2)
        self.assertEqual(len(delivered['bodies']), 2)
        self.assertEqual(sum('Exact fictional verification body.' in b['text']
                             for b in delivered['bodies']), 1)
        self.assertTrue(payload['context_packet']['verification']['requires_full_evidence'])
        self.assertEqual(payload['context_packet']['verification']['sha256'], canonical_hash(delivered))

    def test_spawn_rejects_different_source_even_when_resigned(self):
        delivery = self.evidence()
        for alias in delivery['aliases']:
            alias['current']['source'] = 'f' * 40
        delivery['sha256'] = canonical_hash({k: v for k, v in delivery.items() if k != 'sha256'})
        with self.assertRaises(ValueError):
            self.request(delivery)

    def test_spawn_cannot_send_duplicate_verification_representations(self):
        with self.assertRaisesRegex(ValueError, 'one_verification'):
            self.request(self.evidence(), verification={'status': 'PASS'})

    def test_missing_original_is_blocked_and_never_cached_pass(self):
        delivery = self.evidence()
        (self.root / '.workflow-eval/check.log').unlink()
        payload = json.loads(self.request(delivery)['message'])
        self.assertEqual(payload['verification_evidence']['mode'], 'blocked')
        self.assertFalse(payload['verification_evidence']['verified_pass'])


if __name__ == '__main__':
    unittest.main()
