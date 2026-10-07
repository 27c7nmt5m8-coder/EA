"""Source-bound, audited specification transport with fictional local authorities."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.workflow_eval.context import digest
from tools.workflow_eval.serialization import canonical_hash, canonical_json


class DecisionLedger(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('tools.workflow_eval.decision_ledger'),
                             'source-bound decision ledger is required')
        from tools.workflow_eval import decision_ledger
        self.m = decision_ledger
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git('init', '-q')
        self.git('config', 'core.autocrlf', 'false')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture' + chr(64) + 'example.invalid')
        (self.root / 'docs').mkdir()
        (self.root / 'src').mkdir()
        (self.root / '.agents').mkdir()
        shutil.copytree(ROOT / '.agents/rules', self.root / '.agents/rules')
        (self.root / 'AGENTS.md').write_bytes(b'Acquire the complete current specification.\n')
        (self.root / 'docs/spec.md').write_bytes(b'Write the developer note. Use concise headings.\n')
        (self.root / 'src/example.txt').write_bytes(b'current source\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture authority')
        self.inputs = dict(active_specification='Write the developer note.',
                           specification_provenance_ids=['task'],
                           accepted_decisions=[dict(id='heading-1', text='Use concise headings.', provenance_ids=['task'])],
                           forbidden_changes=['Do not remove the source example.'],
                           unresolved_questions=[], provenance=[dict(id='task', path='docs/spec.md',
                               sha256=digest((self.root / 'docs/spec.md').read_bytes()))],
                           updated_at='2026-10-07T00:00:00Z')
        self.authority_paths = dict(repository_rules=['AGENTS.md'], canonical_docs=['docs/spec.md', '.agents/rules/canonical.json'],
                                    source=['src/example.txt'])

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, stderr=subprocess.DEVNULL)

    def create(self, **overrides):
        return self.m.create_ledger(self.root, **dict(self.inputs, **overrides))

    def rehash(self, ledger):
        ledger['sha256'] = canonical_hash({k: v for k, v in ledger.items() if k != 'sha256'})
        return ledger

    def render(self, ledger, **overrides):
        args = dict(authority_paths=self.authority_paths,
                    prior_verified_specification='Original full accepted specification.')
        args.update(overrides)
        return self.m.render_ledger(self.root, ledger, **args)

    def test_canonical_hash_stable_under_dictionary_key_order(self):
        ledger = self.create()
        reordered = json.loads(json.dumps(ledger, sort_keys=True))
        self.assertEqual(self.m.validate_ledger(self.root, reordered)['sha256'], ledger['sha256'])
        self.assertEqual(ledger['sha256'], canonical_hash({k: v for k, v in ledger.items() if k != 'sha256'}))

    def test_changed_decision_creates_version_and_traces_supersession(self):
        old = self.create()
        new = self.m.update_ledger(self.root, old, replacements=[dict(decision_id='heading-1', reason='Clarified format.',
            replacement=dict(id='heading-2', text='Use numbered headings.', provenance_ids=['task']))],
            updated_at='2026-10-07T00:01:00Z')
        self.assertEqual(new['ledger_version'], 2)
        self.assertNotEqual(new['sha256'], old['sha256'])
        self.assertEqual(new['previous_sha256'], old['sha256'])
        self.assertEqual(new['accepted_decisions'][0]['id'], 'heading-2')
        self.assertEqual(new['superseded_decisions'][0]['decision']['text'], 'Use concise headings.')
        self.assertEqual(new['superseded_decisions'][0]['replacement_id'], 'heading-2')
        self.assertEqual(new['superseded_decisions'][0]['reason'], 'Clarified format.')
        self.assertEqual(old['accepted_decisions'][0]['id'], 'heading-1')
        self.m.validate_ledger(self.root, new)

    def test_multistep_history_is_validated_and_cannot_be_silently_rewritten(self):
        ledger = self.create()
        for version in (2, 3):
            ledger = self.m.update_ledger(self.root, ledger, additions=[dict(id='note-' + str(version),
                text='Retain annotation ' + str(version) + '.', provenance_ids=['task'])],
                updated_at=f'2026-10-07T00:0{version}:00Z')
        self.assertEqual(ledger['ledger_version'], 3)
        self.assertEqual(len(ledger['history']), 2)
        self.m.validate_ledger(self.root, ledger)
        forged = copy.deepcopy(ledger)
        forged['history'][0]['active_specification'] = 'Different original specification.'
        self.rehash(forged)
        with self.assertRaises(ValueError):
            self.m.validate_ledger(self.root, forged)

    def test_unknown_schema_bad_version_hash_or_repository_rejects(self):
        original = self.create()
        for change in (dict(schema_version=99), dict(schema_version=True), dict(ledger_version=1.0),
                       dict(ledger_version=3), dict(source_commit='f' * 40), dict(source_tree='f' * 40),
                       dict(repository_identity='f' * 64), dict(previous_sha256='f' * 64), dict(updated_at='invalid')):
            ledger = self.rehash(dict(original, **change))
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.m.validate_ledger(self.root, ledger)
        broken = dict(original, sha256='f' * 64)
        with self.assertRaises(ValueError):
            self.m.validate_ledger(self.root, broken)

    def test_every_critical_invariant_and_policy_field_is_required_even_after_rehash(self):
        original = self.create()
        for field in ('safety_invariants', 'protected_invariants', 'model_policy', 'review_policy'):
            self.assertTrue(original[field])
            for key in original[field]:
                ledger = copy.deepcopy(original)
                del ledger[field][key]
                self.rehash(ledger)
                with self.subTest(field=field, key=key), self.assertRaises(ValueError):
                    self.m.validate_ledger(self.root, ledger)
            ledger = copy.deepcopy(original)
            ledger[field] = {}
            self.rehash(ledger)
            self.assertEqual(self.render(ledger)['route'], 'full_authority')

    def test_weakened_policy_or_invariant_body_rejects(self):
        ledger = self.create()
        for field in ('safety_invariants', 'protected_invariants', 'model_policy', 'review_policy'):
            forged = copy.deepcopy(ledger)
            key = next(iter(forged[field]))
            forged[field][key] = 'weakened'
            self.rehash(forged)
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.m.validate_ledger(self.root, forged)

    def test_stale_source_dirty_bytes_index_or_commit_falls_back(self):
        ledger = self.create()
        path = self.root / 'src/example.txt'
        path.write_bytes(b'changed source\n')
        with self.assertRaises(ValueError):
            self.m.validate_ledger(self.root, ledger)
        self.assertEqual(self.render(ledger)['route'], 'full_authority')
        self.git('add', '.')
        with self.assertRaises(ValueError):
            self.m.validate_ledger(self.root, ledger)
        self.git('commit', '-qm', 'source changed')
        with self.assertRaises(ValueError):
            self.m.validate_ledger(self.root, ledger)
        with self.assertRaises(ValueError):
            self.m.update_ledger(self.root, ledger, additions=[], updated_at='2026-10-07T00:01:00Z')

    def test_explicit_rebind_retains_audited_prior_source(self):
        ledger = self.create()
        self.git('commit', '--allow-empty', '-qm', 'new source metadata')
        rebound = self.m.update_ledger(self.root, ledger, additions=[], rebind_source=True,
                                     updated_at='2026-10-07T00:01:00Z')
        self.assertNotEqual(rebound['source_commit'], ledger['source_commit'])
        self.assertEqual(rebound['history'][0]['source_commit'], ledger['source_commit'])
        self.m.validate_ledger(self.root, rebound)

    def test_missing_or_changed_provenance_is_not_a_hash_assertion(self):
        ledger = self.create()
        path = self.root / 'docs/spec.md'
        original = path.read_bytes()
        for content in (None, b'different specification\n'):
            if content is None:
                path.unlink()
            else:
                path.write_bytes(content)
            with self.assertRaises(ValueError):
                self.m.validate_ledger(self.root, ledger)
            path.write_bytes(original)
        with self.assertRaises(ValueError):
            self.create(specification_provenance_ids=[])
        with self.assertRaises(ValueError):
            self.create(accepted_decisions=[dict(id='heading-1', text='Heading.', provenance_ids=['absent'])])

    def test_invalid_replacement_reason_identity_or_history_rejects(self):
        ledger = self.create()
        replacement = dict(id='heading-2', text='Heading.', provenance_ids=['task'])
        for change in (dict(decision_id='absent', reason='Changed.', replacement=replacement),
                       dict(decision_id='heading-1', reason='', replacement=replacement),
                       dict(decision_id='heading-1', reason='Changed.', replacement=ledger['accepted_decisions'][0])):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.m.update_ledger(self.root, ledger, replacements=[change], updated_at='2026-10-07T00:01:00Z')
        with self.assertRaises(ValueError):
            self.m.update_ledger(self.root, ledger, updated_at=ledger['updated_at'])

    def test_successful_render_transfers_full_known_spec_without_claiming_completeness(self):
        ledger = self.create(unresolved_questions=['Which annotation is required?'])
        result = self.render(ledger)
        self.assertEqual(result['route'], 'ledger')
        self.assertTrue(result['independent_review_required'])
        self.assertTrue(result['omissions_are_unknown'])
        self.assertIn('Write the developer note.', result['payload']['active_specification'])
        self.assertEqual(result['payload']['unresolved_questions'], ['Which annotation is required?'])
        self.assertIn('Use concise headings.', result['payload']['accepted_decisions'][0]['text'])
        self.assertEqual(result['payload']['provenance_bodies'][0]['text'], 'Write the developer note. Use concise headings.\n')

    def test_invalid_ledger_expands_actual_full_authorities_and_prior_spec(self):
        result = self.render({'schema_version': 999})
        self.assertEqual(result['route'], 'full_authority')
        self.assertTrue(result['independent_review_required'])
        self.assertTrue(result['omissions_are_unknown'])
        self.assertIn('Original full accepted specification.', result['payload']['prior_verified_specification'])
        self.assertEqual(result['payload']['authorities']['source'][0]['text'], 'current source\n')
        self.assertTrue(result['payload']['authorities']['repository_rules'])

    def test_missing_fallback_authority_or_prior_spec_blocks(self):
        (self.root / 'src/example.txt').unlink()
        self.assertEqual(self.render(None)['route'], 'blocked')
        (self.root / 'src/example.txt').write_bytes(b'current source\n')
        self.assertEqual(self.render(None, prior_verified_specification=None)['route'], 'blocked')

    def test_corrupt_actual_catalog_blocks_fallback_until_full_policy_is_acquired(self):
        path = self.root / '.agents/rules/canonical.json'
        original = path.read_bytes()
        path.write_bytes(b'{}')
        self.assertEqual(self.render(None)['route'], 'blocked')
        path.write_bytes(original)
        self.assertEqual(self.render(None)['route'], 'full_authority')

    def test_fallback_expands_marked_rules_and_preserves_original_identity(self):
        path = self.root / 'AGENTS.md'
        raw = b'<!-- canonical-rules: agents version=phase2a-1 -->\n'
        path.write_bytes(raw)
        result = self.render(None)
        self.assertEqual(result['route'], 'full_authority')
        original = result['payload']['authorities']['repository_rules'][0]
        self.assertEqual(original['path'], 'AGENTS.md')
        self.assertEqual(original['sha256'], digest(raw))
        self.assertEqual(original['text'], raw.decode('utf-8'))
        self.assertIn('expanded_text', original)
        self.assertIn('Never place orders on a live account.', original['expanded_text'])

    def test_secret_screening_and_missing_fields_are_fail_closed(self):
        marker = 'pass' + 'word' + chr(61) + 'fictional-value'
        with self.assertRaises(ValueError):
            self.create(active_specification=marker)
        ledger = self.create()
        for field in ('active_specification', 'forbidden_changes', 'provenance', 'updated_at', 'unresolved_questions'):
            incomplete = copy.deepcopy(ledger)
            del incomplete[field]
            self.rehash(incomplete)
            self.assertEqual(self.render(incomplete)['route'], 'full_authority')


if __name__ == '__main__':
    unittest.main()
