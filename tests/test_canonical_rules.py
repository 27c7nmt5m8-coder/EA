"""Canonical policy contracts: full bodies, exact baseline coverage and fail-closed graph."""
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class CanonicalRulesTests(unittest.TestCase):
    def rules(self):
        self.assertTrue((ROOT / 'tools/workflow_eval/rules.py').is_file(),
                        'canonical resolver must exist before policy references are shortened')
        return importlib.import_module('tools.workflow_eval.rules')

    def test_repeated_ids_resolve_exact_body_once_for_fresh_recipient(self):
        r = self.rules()
        catalog = r.load_catalog(ROOT)
        resolved = r.resolve_rules(ROOT, ['RULE_NO_LIVE_ORDER'] * 3)
        self.assertEqual(resolved, [catalog['rules']['RULE_NO_LIVE_ORDER']])
        self.assertEqual(r.instruction_texts(ROOT, ['RULE_NO_LIVE_ORDER'] * 3),
                         [catalog['rules']['RULE_NO_LIVE_ORDER']['body']])

    def test_unknown_missing_corrupt_and_circular_references_fail_closed(self):
        r = self.rules()
        with self.assertRaises(ValueError):
            r.resolve_rules(ROOT, ['RULE_UNKNOWN'])
        catalog = r.load_catalog(ROOT)
        variants = []
        missing = copy.deepcopy(catalog)
        del missing['rules']['RULE_NO_LIVE_ORDER']
        variants.append(missing)
        corrupt = copy.deepcopy(catalog)
        corrupt['rules']['RULE_NO_LIVE_ORDER']['body'] += ' altered'
        variants.append(corrupt)
        circular = copy.deepcopy(catalog)
        circular['rules']['RULE_NO_LIVE_ORDER']['requires'] = ['RULE_NO_LIVE_ORDER']
        variants.append(circular)
        for data in variants:
            with self.subTest(data=data['canonical_sha256']), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / r.CATALOG_PATH
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps(data), encoding='utf-8')
                with self.assertRaises(ValueError):
                    r.load_catalog(tmp)
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            r.load_catalog(tmp)

    def test_cycle_and_missing_edge_are_detected_even_with_recomputed_identity(self):
        r = self.rules()
        from tools.workflow_eval.serialization import canonical_hash
        for edge, reason in [('RULE_NO_LIVE_ORDER', 'circular_reference'),
                             ('RULE_ABSENT_DEPENDENCY', 'reference_invalid')]:
            data = r.load_catalog(ROOT)
            data['rules']['RULE_NO_LIVE_ORDER']['requires'] = [edge]
            data['canonical_sha256'] = canonical_hash({k: v for k, v in data.items()
                                                     if k != 'canonical_sha256'})
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / r.CATALOG_PATH
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps(data), encoding='utf-8')
                with self.assertRaisesRegex(ValueError, reason):
                    r.load_catalog(tmp)

    def test_external_rule_source_link_cannot_escape_repository(self):
        r = self.rules()
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / 'canonical.json'
            external.write_bytes((ROOT / r.CATALOG_PATH).read_bytes())
            path = Path(tmp) / r.CATALOG_PATH
            path.parent.parent.mkdir(parents=True)
            try:
                path.parent.symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                if os.name != 'nt':
                    self.skipTest('This host cannot create a filesystem symlink: ' + str(exc))
                # Windows directory junctions need no symlink privilege. Static
                # PowerShell cmdlets create only these explicitly named temp paths.
                env = dict(os.environ, CANONICAL_TEST_LINK_PATH=str(path.parent),
                           CANONICAL_TEST_TARGET_DIRECTORY=outside)
                result = subprocess.run(['powershell', '-NoProfile', '-Command',
                    'New-Item -ItemType Junction -Path $env:CANONICAL_TEST_LINK_PATH '
                    '-Value $env:CANONICAL_TEST_TARGET_DIRECTORY '
                    '-ErrorAction Stop | Out-Null'],
                    capture_output=True, text=True, env=env)
                self.assertEqual(result.returncode, 0, result.stderr)
            with self.assertRaisesRegex(ValueError, 'path_outside_repository'):
                r.load_catalog(tmp)

    def test_document_secret_screen_and_invalid_marker_fail_closed(self):
        r = self.rules()
        doc = (ROOT / 'AGENTS.md').read_text(encoding='utf-8')
        unsafe = doc + '\n' + 'bea' + 'rer ' + 'fictional-value'
        with self.assertRaisesRegex(ValueError, 'sensitive_evidence'):
            r.expand_document_rules(ROOT, unsafe, 'agents')
        with self.assertRaises(ValueError):
            r.expand_document_rules(ROOT, doc + doc, 'agents')
        with self.assertRaises(ValueError):
            r.expand_document_rules(ROOT, doc.replace('version=phase2a-1', 'version=unknown'), 'agents')

    def test_documents_expand_required_bodies_and_never_deliver_ids_only(self):
        r = self.rules()
        documents = {'agents': 'AGENTS.md',
                     'model-orchestrator': '.agents/skills/model-orchestrator/SKILL.md',
                     'typesafe-ai': '.agents/skills/typesafe-ai/SKILL.md'}
        for consumer, path in documents.items():
            doc = (ROOT / path).read_text(encoding='utf-8')
            expanded = r.expand_document_rules(ROOT, doc, consumer)
            expected = r.resolve_rules(ROOT, r.required_rule_ids(ROOT, consumer))
            self.assertEqual(expanded['included_rule_ids'], [entry['id'] for entry in expected])
            for entry in expected:
                self.assertEqual(expanded['text'].count(entry['body']), 1)
            with self.assertRaises(ValueError):
                r.expand_document_rules(ROOT, doc.replace(r.RULE_MARKER_PREFIX, 'broken: '), consumer)

    def test_semantic_coverage_accounts_for_actual_baseline_blocks_and_full_target_bodies(self):
        r = self.rules()
        coverage = r.validate_semantic_coverage(ROOT)
        self.assertEqual(coverage['baseline_commit'], 'fc9ba7336350d438eb0d0e69ac15d0c036dd53fd')
        self.assertEqual(set(coverage['sources']), {'AGENTS.md',
            '.agents/skills/model-orchestrator/SKILL.md', '.agents/skills/typesafe-ai/SKILL.md'})
        self.assertGreater(len(coverage['clauses']), 75)
        self.assertTrue(all(c['baseline_body'] and c['target_body'] for c in coverage['clauses']))
        self.assertEqual(coverage['unmapped_clause_ids'], [])

    def test_coverage_detects_omitted_clause_changed_target_and_source_hash(self):
        r = self.rules()
        original = json.loads((ROOT / r.COVERAGE_PATH).read_text(encoding='utf-8'))
        mutations = []
        missing = copy.deepcopy(original)
        missing['clauses'].pop()
        mutations.append(missing)
        changed = copy.deepcopy(original)
        changed['clauses'][0]['target_sha256'] = '0' * 64
        mutations.append(changed)
        altered = copy.deepcopy(original)
        next(iter(altered['sources'].values()))['source_sha256'] = '0' * 64
        mutations.append(altered)
        for data in mutations:
            with tempfile.TemporaryDirectory() as tmp:
                for rel in (r.CATALOG_PATH, r.COVERAGE_PATH):
                    target = Path(tmp) / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes((ROOT / rel).read_bytes())
                (Path(tmp) / r.COVERAGE_PATH).write_text(json.dumps(data), encoding='utf-8')
                with self.assertRaises(ValueError):
                    r.validate_semantic_coverage(tmp)

    def test_role_floors_review_security_and_protected_consumers_are_complete(self):
        r = self.rules()
        for consumer in ('agents', 'model-orchestrator'):
            selected = set(r.required_rule_ids(ROOT, consumer))
            self.assertTrue(set(r.SAFETY_RULE_IDS + r.MODEL_RULE_IDS + r.REVIEW_RULE_IDS) <= selected)
        fixed = r.instruction_texts(ROOT, r.required_rule_ids(ROOT, 'spawn-common'))
        self.assertEqual(fixed, [
            'Read the actual evidence and acquire any relevant dependencies before deciding.',
            'Unknown dependencies require investigation; never silently approve incomplete context.',
            'Verification digests do not replace original records or required logs. Preserve warnings, failures and unexecuted checks.',
            'Preserve mandatory independent Sol High review and deterministic verification; never place live orders.',
            'Report actual host execution metadata only when observable; requested settings are not proof.'])

    def test_typesafe_api_guidance_and_deterministic_policy_values_are_preserved(self):
        r = self.rules()
        from tools.workflow_eval.triage import policy
        self.assertEqual(r.JEV_CONFIDENCE_THRESHOLD, policy()['confidence_threshold'])
        self.assertEqual(r.REVIEW_SKIP_ENABLED, policy()['review_skip_enabled'])
        coverage = r.validate_semantic_coverage(ROOT)
        api = [c for c in coverage['clauses'] if c['source_path'] ==
               '.agents/skills/typesafe-ai/SKILL.md']
        self.assertTrue(api)
        for clause in api:
            self.assertEqual(clause['target_kind'], 'document')
            self.assertEqual(clause['baseline_body'].replace('\r\n', '\n'), clause['target_body'])

    def test_metrics_measure_expanded_recipient_bytes_separately_from_raw_documents(self):
        r = self.rules()
        metrics = r.measure_rule_bytes(ROOT)
        self.assertLess(metrics['agents_raw_bytes'], metrics['agents_baseline_bytes'])
        self.assertGreater(metrics['agents_expanded_bytes'], metrics['agents_raw_bytes'])
        self.assertEqual(metrics['observed_token_count'], None)
        self.assertGreater(metrics['deduplicated_rule_bytes'], 0)


if __name__ == '__main__':
    unittest.main()
