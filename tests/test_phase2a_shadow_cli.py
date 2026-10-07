"""Real Git CLI exercises keep shadow data separate from actual full routing."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
import test_policy_capsule as capsule_fixture
import test_dependency_index as index_fixture


class ShadowCliSupport:
    def save(self, name, value):
        directory = self.root / '.workflow-eval'
        directory.mkdir(exist_ok=True)
        path = directory / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        return str(path)

    def run_cli(self, *args, expected=0):
        result = subprocess.run([sys.executable, '-m', 'tools.workflow_eval.cli', *args],
            cwd=self.root, capture_output=True,
            env=os.environ | {'PYTHONPATH': str(ROOT), 'PYTHONUTF8': '1'})
        self.assertEqual(result.returncode, expected, result.stderr.decode('utf-8'))
        return result

    def output(self, name):
        return json.loads((self.root / '.workflow-eval' / name).read_text(encoding='utf-8'))


class CapsuleCli(ShadowCliSupport, unittest.TestCase):
    setUp = capsule_fixture.PolicyCapsuleTests.setUp
    git = capsule_fixture.PolicyCapsuleTests.git
    module = capsule_fixture.PolicyCapsuleTests.module
    inputs = capsule_fixture.PolicyCapsuleTests.inputs

    def test_shadow_candidates_never_replace_full_actual_rule_bodies(self):
        self.run_cli('policy-capsule', self.save('bundle.json', self.bundle),
                     '--input', self.save('input.json', asdict(self.inputs())))
        result = self.output('policy-capsule.json')
        self.assertEqual(result['status'], 'SHADOW')
        self.assertFalse(result['production_adoption'])
        self.assertEqual(result['unexpected_omission'], [])
        self.assertGreater(len(result['actual_policy']), len(result['selected_rule_ids']))
        self.assertTrue(all(rule['body'] for rule in result['actual_policy']))

    def test_missing_current_config_blocks_capsule_without_successful_policy(self):
        (self.root / '.codex/config.toml').unlink()
        self.run_cli('policy-capsule', self.save('bundle.json', self.bundle),
                     '--input', self.save('input.json', asdict(self.inputs())))
        result = self.output('policy-capsule.json')
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertFalse(result['production_adoption'])
        self.assertEqual(result['actual_policy'], [])


class DependencyCli(ShadowCliSupport, unittest.TestCase):
    setUp = index_fixture.DependencyIndexTests.setUp
    git = index_fixture.DependencyIndexTests.git
    write = index_fixture.DependencyIndexTests.write
    legacy = index_fixture.DependencyIndexTests.legacy

    def build(self):
        self.run_cli('dependency-index', '--path', 'main.py')
        return str(self.root / '.workflow-eval/dependency-index.json')

    def test_missing_legacy_and_default_unknown_keep_ordinary_exploration(self):
        self.run_cli('dependency-shadow', self.build(), '--root-path', 'main.py')
        result = self.output('dependency-shadow.json')
        self.assertEqual(result['actual_route'], 'legacy_full')
        self.assertFalse(result['production_adoption'])
        self.assertTrue(result['changed_files_full'])
        self.assertTrue(result['fallback'])
        self.assertIn('unknown_dependency', result['fallback_reasons'])
        self.assertIsNone(result['comparison']['false_negative_count'])

    def test_acquired_legacy_is_compared_without_rewriting_stale_identity(self):
        index = self.build()
        original = self.output('dependency-index.json')
        legacy = self.legacy(['pkg/__init__.py', 'pkg/helper.py', 'pkg/leaf.py'])
        self.run_cli('dependency-shadow', index, '--root-path', 'main.py', '--dependency', 'known',
                     '--legacy', self.save('legacy.json', legacy))
        result = self.output('dependency-shadow.json')
        self.assertEqual(result['comparison']['false_negative_count'], 0)
        self.assertEqual(result['actual_route'], 'legacy_full')
        self.assertTrue(result['promotion_blocked'])
        legacy['source'] = '0' * 40
        self.run_cli('dependency-shadow', index, '--root-path', 'main.py', '--dependency', 'known',
                     '--legacy', self.save('stale.json', legacy))
        stale = self.output('dependency-shadow.json')
        self.assertIsNone(stale['comparison']['false_negative_count'])
        self.assertTrue(stale['fallback'])
        self.assertEqual(self.output('dependency-index.json'), original)


if __name__ == '__main__':
    unittest.main()
