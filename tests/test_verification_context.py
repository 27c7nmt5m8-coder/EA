"""Artifact-backed transport must never turn a claim into acquired PASS evidence."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.workflow_eval.verification_context import build_verification_manifest, verification_transport


class VerificationContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.record = dict(source='a' * 40, tree='b' * 40, scope=['tools/check.py'],
                           command=['python', 'check.py'], platform='fictional-local',
                           toolchain={'python': '3.12'}, exit_code=0, status='PASS',
                           passed=3, failed=0, warnings=[], ci_identity=None,
                           equivalence='LOCAL_ONLY', recorded_at='2026-10-07T00:00:00Z', log_paths=['check.log'],
                           protected=False, dependency='known')
        self.log = 'Check one passed\nCheck two passed\nCheck three passed\n'
        self.write_record()
        (self.root / 'check.log').write_bytes(self.log.encode('utf-8'))
        self.current = {k: copy.deepcopy(self.record[k]) for k in
                        ('source', 'tree', 'scope', 'command', 'platform', 'toolchain', 'equivalence',
                         'protected', 'dependency')}

    def write_record(self):
        (self.root / 'result.json').write_text(json.dumps(self.record), encoding='utf-8')

    def manifest(self, **kwargs):
        return build_verification_manifest(self.root, 'result.json', log_paths=['check.log'], **kwargs)

    def transport(self, manifest=None, **kwargs):
        return verification_transport(self.root, self.manifest() if manifest is None else manifest,
                                      current=self.current, **kwargs)

    def test_exact_acquired_runner_result_transfers_manifest_without_losing_original(self):
        manifest = self.manifest()
        result = self.transport(manifest)
        self.assertEqual(result['route'], 'manifest')
        self.assertTrue(result['verified_pass'])
        self.assertEqual(result['originals'], [])
        self.assertEqual(manifest['passed'], 3)
        self.assertEqual(manifest['artifacts'][1]['sha256'], hashlib.sha256(self.log.encode()).hexdigest())
        self.assertEqual((self.root / 'check.log').read_text(), self.log)
        self.assertIn('ci_identity', manifest['missing_reasons'])

    def test_declared_nested_failures_warnings_or_missing_evidence_expand(self):
        contradictions = [dict(failed=1), dict(exit_code=1), dict(exit_code=False),
            dict(passed=-1), dict(warnings=[{'material': True, 'text': 'Check unavailable'}]),
            dict(warnings=['Unknown diagnostic']), dict(stale=True), dict(stale_evidence=True),
            dict(acquired=False), dict(missing_context_ids=['missing-note']),
            dict(missing_context_count=1)]
        for bad in contradictions:
            for nested in (False, True):
                with self.subTest(bad=bad, nested=nested):
                    record = copy.deepcopy(self.record)
                    if nested:
                        record['details'] = dict(status='PASS', **bad)
                    else:
                        record.update(bad)
                    (self.root / 'result.json').write_text(json.dumps(record), encoding='utf-8')
                    result = self.transport()
                    self.assertEqual(result['route'], 'original')
                    self.assertFalse(result['verified_pass'])
                    self.assertEqual(len(result['originals']), 2)

    def test_missing_or_invalid_timestamp_expands_original(self):
        for timestamp in (None, '', 'not-a-timestamp', '2026-10-07T00:00:00'):
            with self.subTest(timestamp=timestamp):
                self.record['recorded_at'] = timestamp
                self.write_record()
                result = self.transport()
                self.assertEqual(result['route'], 'original')
                self.assertFalse(result['verified_pass'])

    def test_nested_check_source_mismatch_expands_original(self):
        for field in ('source', 'commit', 'tree'):
            for container in ('details', 'checks'):
                with self.subTest(field=field, container=container):
                    record = copy.deepcopy(self.record)
                    check = dict(status='PASS', exit_code=0, **{field: 'c' * 40})
                    record[container] = [check] if container == 'checks' else check
                    (self.root / 'result.json').write_text(json.dumps(record), encoding='utf-8')
                    result = self.transport()
                    self.assertEqual(result['route'], 'original')
                    self.assertFalse(result['verified_pass'])

    def test_timestamped_diagnostics_and_counts_expand_without_changing_original(self):
        for diagnostic in ('FAILED (failures=1)', 'WARNING: Check unavailable', 'Ran 9 tests\nOK'):
            with self.subTest(diagnostic=diagnostic):
                text = '2026-10-07T00:00:00.1234567Z ' + diagnostic + '\n'
                (self.root / 'check.log').write_bytes(text.encode('utf-8'))
                result = self.transport()
                self.assertEqual(result['route'], 'original')
                self.assertFalse(result['verified_pass'])
                self.assertEqual(result['originals'][1]['text'], text)

    def test_protected_unknown_or_unclassified_scope_uses_original(self):
        for protected, dependency in ((True, 'known'), (False, 'unknown'), (None, None)):
            with self.subTest(protected=protected, dependency=dependency):
                self.record.update(protected=protected, dependency=dependency)
                self.write_record()
                result = self.transport()
                self.assertEqual(result['route'], 'original')
                self.assertFalse(result['verified_pass'])

    def test_all_expansion_demands_retain_manifest_and_full_originals(self):
        for option in ('reviewer_request', 'xhigh', 'blocked_judgment', 'unexplained'):
            with self.subTest(option=option):
                manifest = self.manifest()
                result = self.transport(manifest, **{option: True})
                self.assertEqual(result['route'], 'original')
                self.assertEqual(result['manifest'], manifest)
                self.assertEqual(result['originals'][1]['text'], self.log)

    def test_fail_and_material_warning_expand(self):
        for status, code, failures, warnings in [('FAIL', 1, 1, []),
                                                ('PASS', 0, 0, [{'text': 'Required native check unavailable', 'material': True}])]:
            with self.subTest(status=status, warnings=warnings):
                self.record.update(status=status, exit_code=code, failed=failures, warnings=warnings)
                self.write_record()
                result = self.transport()
                self.assertEqual(result['route'], 'original')
                self.assertFalse(result['verified_pass'])
                self.assertEqual(len(result['originals']), 2)

    def test_nonmaterial_warning_can_remain_manifest(self):
        self.record['warnings'] = [{'text': 'Informational diagnostic', 'material': False}]
        self.write_record()
        self.assertEqual(self.transport()['route'], 'manifest')

    def test_unknown_warning_materiality_expands(self):
        self.record['warnings'] = ['Unclassified diagnostic']
        self.write_record()
        self.assertEqual(self.transport()['route'], 'original')

    def test_blocked_unknown_and_unexecuted_never_certify_pass(self):
        for status in ('BLOCKED', 'UNKNOWN', 'NOT_RUN', 'INCOMPLETE', 'DELEGATED_TO_CI'):
            with self.subTest(status=status):
                self.record['status'] = status
                self.write_record()
                result = self.transport()
                self.assertEqual(result['route'], 'original')
                self.assertFalse(result['verified_pass'])

    def test_changed_original_bytes_expand_with_current_original(self):
        manifest = self.manifest()
        (self.root / 'check.log').write_bytes(b'Changed diagnostic\n')
        result = self.transport(manifest)
        self.assertEqual(result['route'], 'original')
        self.assertFalse(result['verified_pass'])
        self.assertIn('artifact_hash_mismatch', result['reasons'])
        self.assertEqual(result['originals'][1]['text'], 'Changed diagnostic\n')

    def test_missing_artifact_blocks_without_fabricated_pass(self):
        manifest = self.manifest()
        (self.root / 'check.log').unlink()
        result = self.transport(manifest)
        self.assertEqual(result['route'], 'blocked')
        self.assertFalse(result['verified_pass'])
        self.assertIn('artifact_unavailable', result['reasons'])
        self.assertEqual(len(result['originals']), 1)

    def test_manifest_claim_changes_cannot_replace_original_record(self):
        for field, value in [('passed', 99), ('status', 'FAIL'), ('source', 'c' * 40), ('tree', 'c' * 40),
                             ('scope', ['other.py']), ('exit_code', 9), ('warnings', [])]:
            with self.subTest(field=field):
                manifest = self.manifest()
                if field == 'warnings':
                    manifest[field] = [{'text': 'Unexpected warning', 'material': True}]
                else:
                    manifest[field] = value
                result = self.transport(manifest)
                self.assertEqual(result['route'], 'original')
                self.assertFalse(result['verified_pass'])
                self.assertIn('record_manifest_mismatch', result['reasons'])

    def test_equal_looking_boolean_or_float_manifest_values_still_mismatch(self):
        for field, value in [('passed', 3.0), ('failed', False), ('exit_code', False)]:
            with self.subTest(field=field):
                manifest = self.manifest()
                manifest[field] = value
                self.assertEqual(self.transport(manifest)['route'], 'original')

    def test_changed_artifact_size_type_is_not_an_exact_match(self):
        manifest = self.manifest()
        manifest['artifacts'][1]['size_bytes'] = float(manifest['artifacts'][1]['size_bytes'])
        self.assertEqual(self.transport(manifest)['route'], 'original')

    def test_original_crlf_bytes_are_preserved_during_expansion(self):
        raw = b'Check passed\r\nExact original\r\n'
        (self.root / 'check.log').write_bytes(raw)
        result = self.transport(reviewer_request=True)
        self.assertEqual(result['originals'][1]['text'].encode('utf-8'), raw)

    def test_source_tree_scope_and_command_mismatch_expand(self):
        for field, value in [('source', 'c' * 40), ('tree', 'c' * 40), ('scope', []),
                             ('command', ['another']), ('platform', 'other'), ('toolchain', {}),
                             ('equivalence', 'UNKNOWN')]:
            with self.subTest(field=field):
                current = dict(self.current, **{field: value})
                result = verification_transport(self.root, self.manifest(), current=current)
                self.assertEqual(result['route'], 'original')
                self.assertFalse(result['verified_pass'])

    def test_current_identity_is_required(self):
        for current in (None, {}, dict(self.current, source=None), dict(self.current, tree='invalid')):
            with self.subTest(current=current):
                result = verification_transport(self.root, self.manifest(), current=current)
                self.assertEqual(result['route'], 'original')
                self.assertFalse(result['verified_pass'])

    def test_invalid_record_metadata_cannot_be_certified_by_matching_current_claims(self):
        original = copy.deepcopy(self.record)
        for field, value in [('scope', 3), ('command', []), ('platform', False), ('toolchain', 'unknown'),
                             ('equivalence', {}), ('ci_identity', 'claimed-success')]:
            with self.subTest(field=field):
                self.record = copy.deepcopy(original)
                self.record[field] = value
                self.write_record()
                current = dict(self.current)
                if field in current:
                    current[field] = value
                result = verification_transport(self.root, self.manifest(), current=current)
                self.assertEqual(result['route'], 'original')
                self.assertFalse(result['verified_pass'])

    def test_record_material_uncertainty_and_nested_status_contradiction_expand(self):
        original = copy.deepcopy(self.record)
        for changes in ({'unexplained': True}, {'material_uncertainty': True},
                        {'details': {'status': 'FAIL'}}, {'ci_identity': {'commit': 'c' * 40, 'status': 'PASS'}}):
            with self.subTest(changes=changes):
                self.record = copy.deepcopy(original)
                self.record.update(changes)
                self.write_record()
                self.assertEqual(self.transport()['route'], 'original')

    def test_binary_original_blocks_without_lossy_text(self):
        (self.root / 'check.log').write_bytes(b'\xff\xfe\xfd')
        result = self.transport()
        self.assertEqual(result['route'], 'blocked')
        self.assertFalse(result['verified_pass'])
        self.assertIn('artifact_not_utf8', result['reasons'])
        self.assertEqual(len(result['originals']), 1)

    def test_contradictory_counts_exit_or_gate_status_expand(self):
        for changes in ({'failed': 1}, {'exit_code': 1}, {'passed': -1}, {'failed': True},
                        {'gates': ['PASS', 'FAIL']}, {'full_gate': 'FAIL'}, {'passed': None}, {'warnings': None}):
            with self.subTest(changes=changes):
                original = copy.deepcopy(self.record)
                self.record.update(changes)
                self.write_record()
                result = self.transport()
                self.assertEqual(result['route'], 'original')
                self.assertFalse(result['verified_pass'])
                self.record = original

    def test_raw_arbitrary_log_cannot_prove_counts_or_pass(self):
        (self.root / 'raw.log').write_text('PASS 3 passed 0 failed\n', encoding='utf-8')
        manifest = build_verification_manifest(self.root, 'raw.log', evidence_kind='raw_log')
        result = self.transport(manifest)
        self.assertEqual(result['route'], 'original')
        self.assertFalse(result['verified_pass'])
        self.assertIsNone(manifest['passed'])
        self.assertIsNone(manifest['status'])

    def test_logs_cannot_be_omitted_from_manifest(self):
        manifest = self.manifest()
        manifest['artifacts'] = manifest['artifacts'][:1]
        result = self.transport(manifest)
        self.assertEqual(result['route'], 'blocked')
        self.assertFalse(result['verified_pass'])
        self.assertEqual(result['originals'][1]['text'], self.log)

    def test_log_completeness_unknown_uses_original_route(self):
        del self.record['log_paths']
        self.write_record()
        self.assertEqual(self.transport()['route'], 'original')

    def test_log_contradiction_or_unclassified_warning_expands(self):
        for raw in ('FAIL: test failed\n', 'WARNING: unavailable native check\n',
                    'Ran 9 tests\nOK\n', 'passed: 9 failed: 0\n'):
            with self.subTest(raw=raw):
                (self.root / 'check.log').write_text(raw, encoding='utf-8')
                result = self.transport()
                self.assertEqual(result['route'], 'original')
                self.assertFalse(result['verified_pass'])

    def test_existing_gate_result_fields_preserved_without_invented_counts(self):
        self.record = dict(commit='a' * 40, gates=['PASS'] * 5, full_gate='PASS',
                           authoritative_release='INCOMPLETE', environment={'system': 'fictional'},
                           ci_native={'status': 'NOT_RUN'}, dirty=True)
        self.write_record()
        manifest = self.manifest()
        self.assertEqual(manifest['source'], 'a' * 40)
        self.assertEqual(manifest['status'], 'PASS')
        self.assertIsNone(manifest['passed'])
        self.assertEqual(self.transport(manifest)['route'], 'original')

    def test_sensitive_original_never_returned_even_on_expansion(self):
        manifest = self.manifest()
        fictional = ''.join(['pass', 'word', '=', 'fictional-value'])
        (self.root / 'check.log').write_text(fictional, encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'sensitive_evidence'):
            self.transport(manifest, reviewer_request=True)
        with self.assertRaisesRegex(ValueError, 'sensitive_evidence'):
            self.manifest()

    def test_sensitive_record_fields_rejected_before_transport(self):
        self.record['diagnostic'] = ''.join(['Bearer', ' ', 'fictional-value'])
        self.write_record()
        with self.assertRaisesRegex(ValueError, 'sensitive_evidence'):
            self.manifest()

    def test_traversal_and_absolute_paths_rejected(self):
        for path in ('../result.json', str(self.root / 'result.json'), 'nested/../result.json',
                     'nested\\result.json'):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'artifact_path'):
                build_verification_manifest(self.root, path)

    def test_symlink_paths_rejected(self):
        try:
            (self.root / 'alias.json').symlink_to(self.root / 'result.json')
        except OSError:
            self.skipTest('Symlink creation privilege unavailable on this host')
        with self.assertRaisesRegex(ValueError, 'artifact_path'):
            build_verification_manifest(self.root, 'alias.json')

    def test_missing_original_at_creation_is_blocked_not_pass(self):
        (self.root / 'result.json').unlink()
        manifest = self.manifest()
        result = self.transport(manifest)
        self.assertEqual(result['route'], 'blocked')
        self.assertFalse(result['verified_pass'])

    def test_missing_artifact_root_is_blocked_not_a_success(self):
        manifest = self.manifest()
        for path in self.root.iterdir():
            path.unlink()
        self.root.rmdir()
        result = self.transport(manifest)
        self.assertEqual(result['route'], 'blocked')
        self.assertFalse(result['verified_pass'])

    def test_invalid_json_and_duplicate_keys_require_original(self):
        for raw in ('not a result', '{"status":"PASS","status":"FAIL"}'):
            with self.subTest(raw=raw):
                (self.root / 'result.json').write_text(raw, encoding='utf-8')
                self.assertEqual(self.transport()['route'], 'original')


if __name__ == '__main__':
    unittest.main()
