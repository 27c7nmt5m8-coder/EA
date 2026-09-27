"""Regression tests for false-green prevention; no native executable is launched."""
import copy
import unittest
import run_all as runner


class ReleaseContract(unittest.TestCase):
    def test_release_always_requires_current_ci_and_clean_local_evidence(self):
        self.assertEqual(runner.release_status('PASS', False, 'PASS', 'PASS', False), 'INCOMPLETE')
        self.assertEqual(runner.release_status('PASS', True, 'PASS', 'PASS', False), 'PASS')
        for full, ci, meta, scope, dirty in [
            ('INCOMPLETE', True, 'PASS', 'PASS', False),
            ('PASS', True, 'NOT_RUN', 'PASS', False),
            ('PASS', True, 'PASS', 'FAIL', False),
            ('PASS', True, 'PASS', 'PASS', True),
        ]:
            self.assertEqual(runner.release_status(full, ci, meta, scope, dirty), 'INCOMPLETE')

    def test_blocked_is_not_pass(self):
        self.assertTrue(hasattr(runner, 'combined_status'), 'combined gate is missing')
        self.assertEqual(runner.combined_status(['BLOCKED', 'BLOCKED', 'PASS', 'PASS', 'PASS'], False), 'INCOMPLETE')

    def test_only_native_can_be_delegated(self):
        self.assertEqual(runner.combined_status(['BLOCKED', 'BLOCKED', 'PASS', 'PASS', 'PASS'], True), 'PASS')
        self.assertEqual(runner.combined_status(['BLOCKED', 'BLOCKED', 'BLOCKED', 'PASS', 'PASS'], True), 'INCOMPLETE')
        self.assertEqual(runner.combined_status(['FAIL', 'BLOCKED', 'PASS', 'PASS', 'PASS'], True), 'FAIL')
        self.assertEqual(runner.combined_status(['NOT_RUN'] * 5, True), 'INCOMPLETE')
        self.assertEqual(runner.combined_status(['PASS'] * 5, False), 'PASS')

    def test_ci_identity_and_steps_are_required(self):
        run = dict(head_sha='a'*40, head_branch='fix/example', path='.github/workflows/ci.yml',
                   event='push', status='completed', conclusion='success',
                   repository={'full_name': 'example/repo'}, run_attempt=1)
        job = dict(name='native-windows', head_sha='a'*40, status='completed', conclusion='success',
                   steps=[dict(name=n, conclusion='success') for n in runner.CI_STEPS])
        self.assertTrue(runner.valid_ci(run, [job], 'example/repo', 'fix/example', 'a'*40))
        for field, value in [('head_sha', 'b'*40), ('head_branch', 'main'), ('event', 'pull_request'),
                             ('path', 'other.yml'), ('status', 'in_progress'), ('conclusion', 'failure')]:
            altered = dict(run, **{field: value})
            self.assertFalse(runner.valid_ci(altered, [job], 'example/repo', 'fix/example', 'a'*40), field)
        for conclusion in ['skipped', 'cancelled', None, 'failure']:
            altered = copy.deepcopy(job)
            altered['steps'][0]['conclusion'] = conclusion
            self.assertFalse(runner.valid_ci(run, [altered], 'example/repo', 'fix/example', 'a'*40))
        self.assertFalse(runner.valid_ci(run, [], 'example/repo', 'fix/example', 'a'*40))
        self.assertFalse(runner.valid_ci(run, [job], 'other/repo', 'fix/example', 'a'*40))


if __name__ == '__main__':
    unittest.main()
