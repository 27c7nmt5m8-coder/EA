"""Exact completed-review evidence reuse against fictional local Git trees."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.workflow_eval import context


class ReviewAttestation(unittest.TestCase):
    def setUp(self):
        # Removing validation or hashing of any input must break these tests.
        self.assertIsNotNone(importlib.util.find_spec('tools.workflow_eval.attestation'),
                             'exact completed-review reuse module is required')
        from tools.workflow_eval import attestation
        self.m = attestation
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'repo'
        self.root.mkdir()
        self.cache = Path(self.tmp.name) / 'cache'
        self.git('init', '-q')
        self.git('config', 'core.autocrlf', 'false')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture' + chr(64) + 'example.invalid')
        (self.root / 'docs').mkdir()
        (self.root / 'docs/dev-note.md').write_bytes(b'before\n')
        (self.root / 'docs/reference.md').write_bytes(b'reference\n')
        (self.root / 'AGENTS.md').write_bytes(b'Read the entire note.\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture base')
        self.base = self.git('rev-parse', 'HEAD').decode().strip()
        (self.root / 'docs/dev-note.md').write_bytes(b'after\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture change')
        self.bundle = self.make_bundle()
        self.args = dict(specification='Update the developer note.',
                         repository_rules='Read the entire note.', unresolved_questions=[],
                         instruction_version='fixture-v1',
                         verification=dict(status='PASS', acquired=True, stale=False,
                                           commit=self.bundle['head'], tree=self.tree(),
                                           source_equivalence='git_tree_exact', commit_sensitive=False,
                                           required_checks=['note-check'],
                                           checks=[dict(name='note-check', status='PASS',
                                                        exit_code=0, warnings=[])]))
        (self.root / '.workflow-eval').mkdir()
        self.log_path = '.workflow-eval/note.log'
        (self.root / self.log_path).write_bytes(b'Ran 1 test\nOK\n')
        log = self.artifact(self.log_path, 'log')
        self.args['verification']['checks'][0]['artifacts'] = [log]
        self.args['verification']['log_paths'] = [self.log_path]
        self.refresh_original()
        self.review = dict(status='OK', completed=True, independent=True,
                           fresh_context=True, read_only=True, acquired_verification=True,
                           material_uncertainty=False, stale_evidence=False,
                           verdict='pass', findings=[], missing_context_ids=[])
        self.receipt = dict(source='host', receipt_id='fixture-run-1',
                            model='gpt-6.1-sol', reasoning_effort='high', fork_turns='none',
                            observed=True, completed=True, independent=True,
                            fresh_context=True, read_only=True)

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root,
                                       stderr=subprocess.DEVNULL)

    def artifact(self, name, role):
        raw = (self.root / name).read_bytes()
        return dict(path=name, role=role, sha256=context.digest(raw), size_bytes=len(raw))

    def refresh_original(self):
        record = self.args['verification']
        body = {name: value for name, value in record.items() if name != 'artifacts'}
        self.record_path = '.workflow-eval/note.json'
        (self.root / self.record_path).write_text(json.dumps(body), encoding='utf-8')
        record['artifacts'] = [self.artifact(self.record_path, 'record'),
                               self.artifact(self.log_path, 'log')]

    def tree(self):
        return self.git('rev-parse', 'HEAD^{tree}').decode().strip()

    def make_bundle(self):
        return context.build_bundle(self.root, self.base, ['docs/reference.md'],
                                    'Update developer note.')

    def create(self, **overrides):
        args = dict(self.args, **overrides)
        from tools.workflow_eval.serialization import canonical_hash
        receipt = None if self.receipt is None else dict(self.receipt,
                    identity_sha256=canonical_hash(self.m.build_identity(self.root, self.bundle, **args)),
                    review_sha256=canonical_hash(self.review))
        return self.m.create_attestation(self.root, self.bundle, self.review,
                                         receipt, **args)

    def save(self):
        attestation = self.create()
        self.m.save_attestation(self.cache, attestation)
        return attestation

    def test_canonical_identity_types_cannot_be_rehashed_into_an_exact_hit(self):
        from tools.workflow_eval.serialization import canonical_hash, canonical_json
        value = self.save()
        original_key = value['identity_sha256']
        value['identity']['policy_version'] = float(value['identity']['policy_version'])
        value['identity_sha256'] = canonical_hash(value['identity'])
        value['host_receipt']['identity_sha256'] = value['identity_sha256']
        value['attestation_sha256'] = canonical_hash({
            k: v for k, v in value.items() if k != 'attestation_sha256'})
        (self.cache / (original_key + '.json')).write_text(canonical_json(value), encoding='utf-8')
        self.assertFalse(self.m.lookup_attestation(self.cache, self.root, self.bundle, **self.args)['hit'])

    def lookup(self, **overrides):
        return self.m.lookup_attestation(self.cache, self.root, self.bundle,
                                         **dict(self.args, **overrides))

    def miss(self, result):
        self.assertFalse(result['hit'])
        self.assertTrue(result['full_review_required'])
        self.assertFalse(result['actual_review_skipped'])

    def test_exact_completed_review_is_reused_as_evidence(self):
        self.save()
        result = self.lookup()
        self.assertTrue(result['hit'])
        self.assertFalse(result['full_review_required'])
        self.assertFalse(result['actual_review_skipped'])
        self.assertFalse(result['new_review_executed'])
        self.assertFalse(result['review_skip_enabled'])
        self.assertEqual(result['mandatory_review_satisfied_by'], 'matching_attestation')
        self.assertEqual(result['attestation']['review']['verdict'], 'pass')

    def test_local_repository_paths_are_hashes_not_exposed(self):
        identity = self.m.build_identity(self.root, self.bundle, **self.args)
        self.assertNotIn(self.root.as_posix(), json.dumps(identity))
        self.assertNotIn(str(self.root), json.dumps(identity))

    def test_every_cached_identity_field_mutation_is_a_miss(self):
        attestation = self.save()
        from tools.workflow_eval.serialization import canonical_hash
        original = json.loads(json.dumps(attestation))
        path = self.cache / (attestation['identity_sha256'] + '.json')
        for field in attestation['identity']:
            altered = copy.deepcopy(original)
            value = altered['identity'][field]
            altered['identity'][field] = ('changed' if isinstance(value, str) else
                                          [] if isinstance(value, dict) else {} if isinstance(value, list)
                                          else None)
            altered['identity_sha256'] = canonical_hash(altered['identity'])
            altered['host_receipt']['identity_sha256'] = altered['identity_sha256']
            altered['attestation_sha256'] = canonical_hash({
                k: v for k, v in altered.items() if k != 'attestation_sha256'})
            with self.subTest(field=field):
                path.write_text(json.dumps(altered), encoding='utf-8')
                self.miss(self.lookup())
        path.write_text(json.dumps(original), encoding='utf-8')
        self.assertTrue(self.lookup()['hit'])

    def test_changed_supplied_inputs_require_new_review(self):
        self.save()
        mutations = [dict(specification='Update a different note.'),
                     dict(repository_rules='Read both notes.'),
                     dict(unresolved_questions=['Explain punctuation.']),
                     dict(instruction_version='fixture-v2'),
                     dict(reviewer_model='gpt-6-sol'),
                     dict(reviewer_effort='medium'),
                     dict(reviewer_effort='xhigh', escalation=dict(
                         reason='explicit_project_xhigh_rule', evidence='Fixture rule requires second reading.'))]
        evidence = copy.deepcopy(self.args['verification'])
        evidence['checks'][0]['duration_seconds'] = 2
        mutations.append(dict(verification=evidence))
        for change in mutations:
            with self.subTest(change=change):
                self.miss(self.lookup(**change))

    def test_noncompleted_or_uncertain_review_cannot_create_attestation(self):
        changes = [dict(status='UNKNOWN'), dict(completed=False), dict(independent=False),
                   dict(fresh_context=False), dict(read_only=False),
                   dict(acquired_verification=False), dict(material_uncertainty=True),
                   dict(stale_evidence=True), dict(verdict='unknown'),
                   dict(missing_context_ids=['reference']),
                   dict(findings=[dict(severity='important', code='NOTE', evidence_id='note', reason='Missing line.')]),
                   dict(findings=[dict(severity='critical', code='NOTE', evidence_id='note', reason='Missing line.')])]
        for change in changes:
            original = self.review
            self.review = dict(original, **change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.create()
            self.review = original

    def test_receipt_must_observe_completed_exact_host_execution(self):
        changes = [dict(source='caller'), dict(receipt_id=''), dict(observed=False),
                   dict(model='gpt-6-sol'), dict(reasoning_effort='medium'),
                   dict(reasoning_effort='xhigh'), dict(fork_turns='all'),
                   dict(completed=False), dict(independent=False),
                   dict(fresh_context=False), dict(read_only=False)]
        for change in changes:
            original = self.receipt
            self.receipt = dict(original, **change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.create()
            self.receipt = original
        with self.assertRaises(ValueError):
            self.m.create_attestation(self.root, self.bundle, self.review, None, **self.args)

    def test_cache_integrity_and_provenance_mutations_fail_closed(self):
        attestation = self.save()
        path = self.cache / (attestation['identity_sha256'] + '.json')
        from tools.workflow_eval.serialization import canonical_hash
        mutations = [lambda a: a['host_receipt'].update(observed=False),
                     lambda a: a['host_receipt'].update(source='caller'),
                     lambda a: a['host_receipt'].update(receipt_id=''),
                     lambda a: a['host_receipt'].update(model='gpt-6-sol'),
                     lambda a: a['host_receipt'].update(reasoning_effort='medium'),
                     lambda a: a['host_receipt'].update(fork_turns='all'),
                     lambda a: a['host_receipt'].update(completed=False),
                     lambda a: a['host_receipt'].update(independent=False),
                     lambda a: a['host_receipt'].update(fresh_context=False),
                     lambda a: a['host_receipt'].update(read_only=False),
                     lambda a: a['host_receipt'].update(identity_sha256='f' * 64),
                     lambda a: a['host_receipt'].update(review_sha256='f' * 64),
                     lambda a: a['review'].update(completed=False),
                     lambda a: a['review'].update(acquired_verification=False),
                     lambda a: a.update(source_head='f' * 40),
                     lambda a: a.update(schema_version=99)]
        for mutation in mutations:
            altered = copy.deepcopy(attestation)
            mutation(altered)
            # Even a rehashed invalid receipt/record remains inadmissible.
            altered['attestation_sha256'] = canonical_hash({
                k: v for k, v in altered.items() if k != 'attestation_sha256'})
            path.write_text(json.dumps(altered), encoding='utf-8')
            self.miss(self.lookup())

    def test_missing_malformed_and_duplicate_key_cache_are_misses(self):
        self.miss(self.lookup())
        attestation = self.save()
        path = self.cache / (attestation['identity_sha256'] + '.json')
        for text in ('{', '{}', '[]', 'null', '{"schema_version":1,"schema_version":1}'):
            path.write_text(text, encoding='utf-8')
            self.miss(self.lookup())

    def test_forged_bundle_diff_path_body_and_hash_are_rejected(self):
        self.save()
        mutations = [lambda b: b.update(patch=''), lambda b: b.update(changed_paths=[]),
                     lambda b: b['blocks'][0].update(text='fiction'),
                     lambda b: b['blocks'][0].update(sha256='a' * 64),
                     lambda b: b.update(fingerprint='a' * 64),
                     lambda b: b.update(base='a' * 40)]
        original = self.bundle
        for mutation in mutations:
            self.bundle = copy.deepcopy(original)
            mutation(self.bundle)
            self.miss(self.lookup())
        self.bundle = original

    def test_dirty_tracked_index_untracked_and_dependency_changes_miss(self):
        self.save()
        path = self.root / 'docs/dev-note.md'
        path.write_bytes(b'dirty\n')
        self.bundle = self.make_bundle()
        self.miss(self.lookup())
        self.git('add', '.')
        self.bundle = self.make_bundle()
        self.miss(self.lookup())
        self.git('reset', '--hard', '-q', 'HEAD')
        extra = self.root / 'docs/extra.md'
        extra.write_bytes(b'extra\n')
        self.bundle = self.make_bundle()
        self.miss(self.lookup())
        extra.unlink()
        (self.root / 'docs/reference.md').write_bytes(b'different reference\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'dependency changed')
        self.bundle = self.make_bundle()
        self.miss(self.lookup())

    def test_alias_and_cloned_repository_identity_do_not_match(self):
        self.save()
        clone = Path(self.tmp.name) / 'clone'
        subprocess.check_call(['git', 'clone', '-q', str(self.root), str(clone)],
                              stderr=subprocess.DEVNULL)
        bundle = context.build_bundle(clone, self.base, ['docs/reference.md'], 'Update developer note.')
        self.miss(self.m.lookup_attestation(self.cache, clone, bundle, **self.args))

    def test_metadata_only_new_commit_reuses_only_equal_review_inputs(self):
        attestation = self.save()
        self.git('commit', '--allow-empty', '-qm', 'metadata only')
        self.bundle = self.make_bundle()
        self.assertNotEqual(self.bundle['head'], attestation['source_head'])
        self.assertTrue(self.lookup()['hit'])
        evidence = copy.deepcopy(self.args['verification'])
        evidence['commit'] = self.bundle['head']
        self.miss(self.lookup(verification=evidence))

    def test_same_tree_without_explicit_verification_applicability_misses(self):
        self.args['verification'].pop('source_equivalence')
        self.args['verification'].pop('commit_sensitive')
        self.refresh_original()
        self.save()
        self.git('commit', '--allow-empty', '-qm', 'metadata only')
        self.bundle = self.make_bundle()
        self.miss(self.lookup())

    def test_required_originals_missing_modified_or_nontext_require_full_review(self):
        self.save()
        for name in (self.log_path, self.record_path):
            path = self.root / name
            original = path.read_bytes()
            for mutation in (None, b'changed\n', b'\xff\xfe'):
                with self.subTest(name=name, mutation=mutation):
                    if mutation is None:
                        path.unlink()
                    else:
                        path.write_bytes(mutation)
                    self.miss(self.lookup())
                    path.write_bytes(original)
        self.assertTrue(self.lookup()['hit'])

    def test_digest_or_acquired_flags_cannot_replace_original_artifacts(self):
        for mutation in (lambda r: r.pop('artifacts'),
                         lambda r: r.update(artifacts=[]),
                         lambda r: r['checks'][0].pop('artifacts'),
                         lambda r: r['checks'][0].update(artifacts=[]),
                         lambda r: r['artifacts'][0].update(sha256='f' * 64),
                         lambda r: r['artifacts'][0].update(size_bytes=0),
                         lambda r: r['artifacts'][0].update(path='../absent.json')):
            record = copy.deepcopy(self.args['verification'])
            mutation(record)
            with self.subTest(record=record), self.assertRaises(ValueError):
                self.create(verification=record)

    def test_check_and_top_level_extra_artifacts_are_all_acquired(self):
        for location in ('top', 'check'):
            record = copy.deepcopy(self.args['verification'])
            missing = dict(path='.workflow-eval/absent.log', role='log', sha256='f' * 64, size_bytes=1)
            if location == 'top':
                record['artifacts'].append(missing)
            else:
                record['checks'][0]['artifacts'].append(missing)
            with self.subTest(location=location), self.assertRaises(ValueError):
                self.create(verification=record)

    def test_rehashed_original_record_must_match_claimed_source_and_checks(self):
        body = {k: v for k, v in self.args['verification'].items() if k != 'artifacts'}
        for mutation in (dict(commit='f' * 40), dict(tree='f' * 40), dict(status='FAIL'),
                         dict(checks=[]), dict(log_paths=[])):
            path = self.root / self.record_path
            original = path.read_bytes()
            path.write_text(json.dumps(dict(body, **mutation)), encoding='utf-8')
            record = copy.deepcopy(self.args['verification'])
            record['artifacts'][0] = self.artifact(self.record_path, 'record')
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.create(verification=record)
            path.write_bytes(original)

    def test_sensitive_or_contradictory_full_originals_cannot_certify_pass(self):
        original = copy.deepcopy(self.args['verification'])
        path = self.root / self.log_path
        for body in (b'FAILED\n', b'WARNING investigate\n',
                     ('pass' + 'word' + chr(61) + 'fictional-value\n').encode('utf-8')):
            path.write_bytes(body)
            self.args['verification']['checks'][0]['artifacts'] = [self.artifact(self.log_path, 'log')]
            self.refresh_original()
            with self.subTest(body_kind=body[:4]), self.assertRaises(ValueError):
                self.create()
        self.args['verification'] = original
        path.write_bytes(b'Ran 1 test\nOK\n')
        self.refresh_original()

    def test_changed_merge_result_and_base_require_new_review(self):
        self.save()
        old_head = self.bundle['head']
        self.git('checkout', '-qb', 'parallel', self.base)
        (self.root / 'docs/other.md').write_bytes(b'parallel note\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'parallel change')
        self.git('checkout', '-q', old_head)
        self.git('merge', '--no-ff', '-qm', 'merge result', 'parallel')
        self.bundle = self.make_bundle()
        self.miss(self.lookup())
        self.git('checkout', '-q', old_head)
        self.base = old_head
        self.bundle = self.make_bundle()
        self.miss(self.lookup())

    def test_protected_unknown_missing_and_stale_evidence_fail_closed(self):
        self.save()
        self.miss(self.lookup(specification='Assess lot sizing.'))
        self.bundle = context.build_bundle(self.root, self.base, ['docs/absent.md'], 'Update developer note.')
        self.miss(self.lookup())
        self.bundle = self.make_bundle()
        for mutation in [dict(acquired=False), dict(stale=True), dict(status='FAIL'),
                         dict(tree='f' * 40), dict(commit='f' * 40),
                         dict(required_checks=['unexecuted']), dict(checks=[]),
                         dict(checks=[dict(name='note-check', status='PASS', exit_code=2, warnings=[])]),
                         dict(checks=[dict(name='note-check', status='PASS', exit_code=0, warnings=['Investigate.'])])]:
            evidence = dict(self.args['verification'], **mutation)
            with self.subTest(mutation=mutation):
                self.miss(self.lookup(verification=evidence))
        with self.assertRaises(ValueError):
            self.create(verification=None)


if __name__ == '__main__':
    unittest.main()
