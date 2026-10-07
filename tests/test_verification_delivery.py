"""Verification dedup preserves acquired originals and every source identity."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.workflow_eval.serialization import canonical_hash, canonical_json
from tools.workflow_eval.verification_context import build_verification_manifest
from tools.workflow_eval.verification_delivery import (build_verification_delivery,
    expand_verification_delivery, validate_verification_delivery)
from tools.workflow_eval import verification_delivery


class VerificationDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.log = 'Fictional exact check 日本語\r\n'
        self.record = dict(source='a' * 40, tree='b' * 40, scope=['tools/check.py'],
            command=['python', 'check.py'], platform='fictional-local', toolchain={'python': '3.12'},
            exit_code=0, status='PASS', passed=1, failed=0, warnings=[], ci_identity=None,
            equivalence='LOCAL_ONLY', recorded_at='2026-10-07T00:00:00Z', log_paths=['check.log'],
            protected=False, dependency='known')
        self.current = {name: copy.deepcopy(self.record[name]) for name in
            ('source', 'tree', 'scope', 'command', 'platform', 'toolchain', 'equivalence', 'protected', 'dependency')}
        self.write_record()
        (self.root / 'check.log').write_bytes(self.log.encode('utf-8'))

    def write_record(self, path='result.json'):
        (self.root / path).write_bytes(json.dumps(self.record, ensure_ascii=False).encode('utf-8'))

    def source(self, surface='review_payload', record_path='result.json', logs=None):
        manifest = build_verification_manifest(self.root, record_path,
                    log_paths=['check.log'] if logs is None else logs)
        return dict(source_identity={'surface': surface, 'source_path': record_path, 'sequence': 7},
                    current=copy.deepcopy(self.current), manifest=manifest)

    def delivery(self, **kwargs):
        return build_verification_delivery(self.root,
                    [self.source('review_payload'), self.source('completion_report')], **kwargs)

    def resign(self, delivery):
        delivery['sha256'] = canonical_hash({k: v for k, v in delivery.items() if k != 'sha256'})

    def test_repeated_originals_transfer_each_body_once_and_keep_aliases(self):
        sources = [self.source('review_payload'), self.source('completion_report')]
        result = build_verification_delivery(self.root, sources, reviewer_request=True)
        self.assertEqual(result['mode'], 'original')
        self.assertEqual(len(result['verifications']), 1)
        self.assertEqual(len(result['bodies']), 2)
        self.assertEqual([a['source_identity'] for a in result['aliases']], [s['source_identity'] for s in sources])
        self.assertEqual([a['current'] for a in result['aliases']], [s['current'] for s in sources])
        texts = [b['text'] for b in result['bodies']]
        self.assertEqual(texts.count(self.log), 1)
        self.assertEqual(canonical_json(result).count('Fictional exact check'), 1)
        self.assertEqual((self.root / 'check.log').read_bytes(), self.log.encode('utf-8'))

    def test_verified_pass_uses_one_manifest_without_raw_or_digest_summary(self):
        result = self.delivery()
        self.assertEqual(result['mode'], 'manifest')
        self.assertTrue(result['verified_pass'])
        self.assertEqual(len(result['verifications']), 1)
        self.assertEqual(result['bodies'], [])
        self.assertNotIn('summary', result)
        self.assertEqual(validate_verification_delivery(self.root, result), result)

    def test_canonical_verification_id_stable_under_json_key_order(self):
        first = self.source()
        second = copy.deepcopy(first)
        second['manifest'] = dict(reversed(list(second['manifest'].items())))
        second['source_identity']['surface'] = 'other_source'
        result = build_verification_delivery(self.root, [first, second])
        self.assertEqual(len(result['verifications']), 1)
        ids = [a['verification_id'] for a in result['aliases']]
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(ids[0], 'verification:' + canonical_hash(first['manifest']))

    def test_distinct_artifact_paths_keep_identity_while_exact_log_body_is_shared(self):
        self.write_record('copy.json')
        result = build_verification_delivery(self.root,
                    [self.source(), self.source('ci_archive', 'copy.json')], reviewer_request=True)
        self.assertEqual(len(result['verifications']), 2)
        self.assertEqual(len(result['bodies']), 2)
        paths = {r['path'] for v in result['verifications'] for r in v['original_refs']}
        self.assertEqual(paths, {'result.json', 'copy.json', 'check.log'})
        log_ids = [r['body_id'] for v in result['verifications'] for r in v['original_refs'] if r['path'] == 'check.log']
        self.assertEqual(log_ids[0], log_ids[1])

    def test_fail_warning_blocked_contradiction_require_originals(self):
        original = copy.deepcopy(self.record)
        for changes in ({'status': 'FAIL', 'exit_code': 1, 'failed': 1},
                        {'warnings': [{'text': 'Unavailable native check', 'material': True}]},
                        {'status': 'BLOCKED'}, {'details': {'status': 'FAIL'}}):
            with self.subTest(changes=changes):
                self.record = copy.deepcopy(original)
                self.record.update(changes)
                self.write_record()
                result = self.delivery()
                self.assertEqual(result['mode'], 'original')
                self.assertFalse(result['verified_pass'])
                self.assertEqual(len(result['bodies']), 2)
                self.assertEqual(len(result['aliases']), 2)

    def test_alias_current_mismatch_is_not_hidden_by_same_verification_id(self):
        first, second = self.source(), self.source('other_source')
        second['current']['tree'] = 'c' * 40
        result = build_verification_delivery(self.root, [first, second])
        self.assertEqual(result['mode'], 'original')
        self.assertFalse(result['verified_pass'])
        self.assertIn('current_tree_mismatch', result['verifications'][0]['reasons'])

    def test_hash_or_manifest_metadata_mismatch_rejected(self):
        for mutation in ('artifact', 'manifest'):
            with self.subTest(mutation=mutation):
                source = self.source()
                if mutation == 'artifact':
                    source['manifest']['artifacts'][1]['sha256'] = 'c' * 64
                else:
                    source['manifest']['passed'] = 9
                with self.assertRaisesRegex(ValueError, 'verification_evidence_mismatch'):
                    build_verification_delivery(self.root, [source])

    def test_mutated_original_rejected_and_missing_original_blocked(self):
        source = self.source()
        (self.root / 'check.log').write_bytes(b'Changed original\n')
        with self.assertRaisesRegex(ValueError, 'verification_evidence_mismatch'):
            build_verification_delivery(self.root, [source])
        (self.root / 'check.log').unlink()
        result = build_verification_delivery(self.root, [source])
        self.assertEqual(result['mode'], 'blocked')
        self.assertFalse(result['verified_pass'])
        self.assertEqual(len(result['bodies']), 1)

    def test_digest_only_claims_cannot_be_verification_sources(self):
        for source in ({'sha256': 'a' * 64, 'status': 'PASS'},
                       dict(source_identity={'surface': 'digest'}, current=self.current,
                            manifest={'sha256': 'a' * 64, 'status': 'PASS'})):
            with self.subTest(source=source), self.assertRaises(ValueError):
                build_verification_delivery(self.root, [source])
        with self.assertRaises(ValueError):
            build_verification_delivery(self.root, [])

    def test_reviewer_and_xhigh_expansion_reacquire_full_originals(self):
        initial = self.delivery()
        for flag in ('reviewer_request', 'xhigh'):
            with self.subTest(flag=flag):
                result = expand_verification_delivery(self.root, initial, **{flag: True})
                self.assertEqual(result['mode'], 'original')
                self.assertEqual(len(result['bodies']), 2)
                self.assertEqual(result['aliases'], initial['aliases'])
                self.assertEqual(validate_verification_delivery(self.root, result), result)

    def test_validation_reacquires_original_and_blocks_missing_artifacts(self):
        delivery = self.delivery()
        (self.root / 'check.log').unlink()
        result = validate_verification_delivery(self.root, delivery)
        self.assertEqual(result['mode'], 'blocked')
        self.assertFalse(result['verified_pass'])

    def test_artifact_disappearing_after_phase1_acquisition_keeps_available_originals(self):
        source = self.source()
        read = verification_delivery._read
        def disappear(root, name):
            if name == 'check.log':
                (self.root / 'check.log').unlink(missing_ok=True)
            return read(root, name)
        with patch.object(verification_delivery, '_read', side_effect=disappear):
            result = build_verification_delivery(self.root, [source])
        self.assertEqual(result['mode'], 'blocked')
        self.assertFalse(result['verified_pass'])
        self.assertEqual(len(result['bodies']), 1)
        self.assertEqual(result['verifications'][0]['original_refs'][0]['path'], 'result.json')

    def test_malformed_reference_types_rejected_with_validation_error(self):
        for field in ('alias_id', 'body_id'):
            with self.subTest(field=field):
                delivery = self.delivery(reviewer_request=True)
                if field == 'alias_id':
                    delivery['aliases'][0]['verification_id'] = []
                else:
                    delivery['verifications'][0]['original_refs'][0]['body_id'] = []
                self.resign(delivery)
                with self.assertRaises(ValueError):
                    validate_verification_delivery(self.root, delivery)

    def test_payload_integrity_and_resigned_body_corruption_rejected(self):
        for resign in (False, True):
            with self.subTest(resign=resign):
                delivery = self.delivery(reviewer_request=True)
                delivery['bodies'][0]['text'] += 'Changed'
                if resign:
                    self.resign(delivery)
                with self.assertRaises(ValueError):
                    validate_verification_delivery(self.root, delivery)

    def test_resigned_alias_or_status_forgery_rejected_by_rebuild(self):
        for field in ('alias', 'status', 'reference'):
            with self.subTest(field=field):
                delivery = self.delivery(reviewer_request=True)
                if field == 'alias':
                    delivery['aliases'][0]['verification_id'] = 'verification:' + 'c' * 64
                elif field == 'status':
                    delivery['verified_pass'] = True
                else:
                    delivery['verifications'][0]['original_refs'][0]['body_id'] = 'body:' + 'c' * 64
                self.resign(delivery)
                with self.assertRaises(ValueError):
                    validate_verification_delivery(self.root, delivery)

    def test_sensitive_original_alias_or_current_never_sent(self):
        fictional = ''.join(['pass', 'word', '=', 'fictional-value'])
        for where in ('original', 'alias', 'current'):
            with self.subTest(where=where):
                source = self.source()
                if where == 'original':
                    (self.root / 'check.log').write_bytes(fictional.encode())
                elif where == 'alias':
                    source['source_identity']['description'] = fictional
                else:
                    source['current']['diagnostic'] = fictional
                with self.assertRaisesRegex(ValueError, 'sensitive_evidence'):
                    build_verification_delivery(self.root, [source])
                (self.root / 'check.log').write_bytes(self.log.encode('utf-8'))

    def test_path_traversal_in_artifact_reference_rejected(self):
        source = self.source()
        source['manifest']['artifacts'][0]['path'] = '../result.json'
        with self.assertRaisesRegex(ValueError, 'artifact_path'):
            build_verification_delivery(self.root, [source])

    def test_nonidentical_logs_are_not_deduplicated(self):
        other = copy.deepcopy(self.record)
        other['log_paths'] = ['other.log']
        (self.root / 'other.json').write_bytes(json.dumps(other).encode())
        (self.root / 'other.log').write_bytes(b'Different original\n')
        result = build_verification_delivery(self.root,
                    [self.source(), self.source('other_source', 'other.json', ['other.log'])], reviewer_request=True)
        self.assertEqual(len(result['bodies']), 4)


if __name__ == '__main__':
    unittest.main()
