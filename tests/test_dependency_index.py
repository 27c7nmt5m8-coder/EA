"""Static dependency candidates never replace independent ordinary exploration."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.workflow_eval.context import fingerprint
from tools.workflow_eval.serialization import canonical_hash, canonical_json
from tools.workflow_eval.dependency_index import (build_dependency_index,
    compare_dependency_shadow, validate_dependency_index)
from tools.workflow_eval import dependency_index


class DependencyIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Fictional fixture')
        self.git('config', 'user.email', ''.join(['fixture', '@', 'example.invalid']))
        self.write('pkg/__init__.py', '')
        self.write('pkg/leaf.py', 'def calculate(value):\n    return value + 1\n')
        self.write('pkg/helper.py', 'from .leaf import calculate\ndef helper(value):\n    return calculate(value)\n')
        self.write('main.py', 'from pkg.helper import helper\nresult = helper(2)\n')
        self.write('tests/test_helper.py', 'from pkg.helper import helper\ndef test_helper():\n    assert helper(2) == 3\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'fictional baseline')

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, stderr=subprocess.DEVNULL).decode('utf-8').strip()

    def write(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode('utf-8'))

    def track(self):
        self.git('add', '.')

    def legacy(self, paths, material_paths=None):
        return dict(schema_version=1, paths=paths, material_paths=paths if material_paths is None else material_paths,
            acquired=True, independent=True, source=self.git('rev-parse', 'HEAD'), tree=self.git('rev-parse', 'HEAD^{tree}'),
            fingerprint=fingerprint(self.root), dependency_hashes={p: hashlib.sha256((self.root/p).read_bytes()).hexdigest() for p in paths},
            provenance={'method': 'independent_fixture_read', 'evidence_id': 'fictional-case'})

    def test_direct_transitive_imports_interfaces_and_calls_have_exact_hashes(self):
        index = build_dependency_index(self.root, ['main.py'])
        edges = index['edges']
        wanted = {('main.py', 'pkg/helper.py', 'python_import'),
                  ('pkg/helper.py', 'pkg/leaf.py', 'python_import'),
                  ('main.py', 'pkg/helper.py', 'direct_call')}
        actual = {(e['source_path'], e['dependency_path'], e['relation_type']) for e in edges}
        self.assertTrue(wanted.issubset(actual))
        for edge in edges:
            self.assertEqual(edge['schema_version'], 1)
            self.assertEqual(edge['source_sha256'], hashlib.sha256((self.root / edge['source_path']).read_bytes()).hexdigest())
            self.assertEqual(edge['dependency_sha256'], hashlib.sha256((self.root / edge['dependency_path']).read_bytes()).hexdigest())
        self.assertTrue(any(e['relation_type'] == 'public_interface' and e['symbol'] == 'helper' for e in edges))
        self.assertNotIn('return calculate', canonical_json(index))
        self.assertEqual(validate_dependency_index(self.root, index), index)

    def test_test_to_source_relation_is_proven_by_import_not_filename_guess(self):
        index = build_dependency_index(self.root, ['tests/test_helper.py'])
        self.assertTrue(any(e['relation_type'] == 'test_source' and e['dependency_path'] == 'pkg/helper.py' for e in index['edges']))

    def test_canonical_semantic_hash_stable_and_timing_measured_separately(self):
        first = build_dependency_index(self.root, ['main.py'])
        second = build_dependency_index(self.root, ['main.py'])
        self.assertEqual(first['canonical_sha256'], second['canonical_sha256'])
        self.assertGreaterEqual(first['build_metrics']['build_time_seconds'], 0)
        self.assertIsNone(first['build_metrics']['input_tokens'])
        self.assertIn('input_tokens', first['build_metrics']['missing_reasons'])

    def test_mql_relative_include_candidates_never_claim_complete_semantics(self):
        self.write('native/main.mq5', '#include "part.mqh"\n')
        self.write('native/part.mqh', 'int CountValues() { return 1; }\n')
        self.track()
        index = build_dependency_index(self.root, ['native/main.mq5'])
        self.assertTrue(any(e['dependency_path'] == 'native/part.mqh' and e['relation_type'] == 'mql_include' for e in index['edges']))
        self.assertIn('mql_semantics_not_parsed', {u['reason'] for u in index['unresolved']})
        result = compare_dependency_shadow(self.root, index, ['native/main.mq5'], legacy=self.legacy(['native/part.mqh']))
        self.assertTrue(result['fallback'])
        self.assertFalse(result['production_adoption'])

    def test_unsupported_dynamic_reflection_parse_generated_and_macro_fallbacks(self):
        examples = {'dynamic.py': 'module = __import__("pkg.helper")\n',
            'reflect.py': 'def find(value):\n    return getattr(value, "target")\n',
            'broken.py': 'def broken(:\n', 'generated.py': '# Automatically generated; do not edit\nimport pkg.helper\n',
            'macro.mq5': '#define HEADER "part.mqh"\n#include HEADER\n',
            'angle.mq5': '#include <Trade/Trade.mqh>\n',
            'unknown.py': 'from missing_package import thing\n',
            'symbol.py': 'from pkg.leaf import missing_name\n',
            'conditional.py': 'if True:\n    import pkg.helper\n',
            'config.py': 'CONFIG_PATH = choose_config()\n'}
        for path, text in examples.items():
            self.write(path, text)
        self.track()
        index = build_dependency_index(self.root, list(examples))
        reasons = {u['reason'] for u in index['unresolved']}
        for expected in ('dynamic_import', 'reflection', 'parse_failure', 'generated_code', 'unknown_macro',
                         'ambiguous_include', 'unresolved_import', 'unresolved_symbol', 'conditional_import', 'indirect_configuration'):
            self.assertIn(expected, reasons)
        result = compare_dependency_shadow(self.root, index, list(examples), legacy=self.legacy([]))
        self.assertTrue(result['fallback'])
        self.assertEqual(result['actual_route'], 'legacy_full')
        self.assertFalse(result['production_adoption'])

    def test_protected_files_and_uncertain_task_force_ordinary_exploration(self):
        self.write('guard.py', 'risk_limit = 1\n')
        self.track()
        index = build_dependency_index(self.root, ['guard.py'])
        result = compare_dependency_shadow(self.root, index, ['guard.py'], legacy=self.legacy([]))
        self.assertTrue(result['fallback'])
        clean = build_dependency_index(self.root, ['main.py'])
        for settings in ({'protected': True}, {'dependency': 'unknown'}, {'task': 'change order handling'}):
            with self.subTest(settings=settings):
                result = compare_dependency_shadow(self.root, clean, ['main.py'], legacy=self.legacy([]), **settings)
                self.assertTrue(result['fallback'])
                self.assertFalse(result['production_adoption'])

    def test_literal_tracked_file_and_configuration_edges_preserve_unknown_config_semantics(self):
        self.write('settings.json', '{"fictional_mode": "test"}\n')
        self.write('settings.py', 'CONFIG_PATH = "settings.json"\n')
        self.track()
        index = build_dependency_index(self.root, ['settings.py'])
        self.assertTrue(any(e['dependency_path'] == 'settings.json' and e['relation_type'] == 'configuration_reference' for e in index['edges']))
        self.assertIn('unsupported_data_semantics', {u['reason'] for u in index['unresolved']})

    def test_from_package_import_module_and_aliased_direct_call_are_candidates(self):
        self.write('alias_import.py', 'from pkg import leaf\nanswer = leaf.calculate(1)\n')
        self.track()
        index = build_dependency_index(self.root, ['alias_import.py'])
        self.assertTrue(any(e['source_path'] == 'alias_import.py' and e['dependency_path'] == 'pkg/leaf.py'
                            and e['relation_type'] == 'direct_call' for e in index['edges']))

    def test_unresolved_noncall_symbols_and_unsupported_syntax_are_unknown(self):
        self.write('attribute.py', 'setting = UNKNOWN_SOURCE.selected\n')
        self.write('matching.py', 'match 1:\n    case 1:\n        matched = True\n')
        self.track()
        index = build_dependency_index(self.root, ['attribute.py', 'matching.py'])
        self.assertIn('unresolved_symbol', {u['reason'] for u in index['unresolved']})
        self.assertIn('unsupported_syntax', {u['reason'] for u in index['unresolved']})

    def test_builtin_shadowing_and_dynamic_module_exports_require_fallback(self):
        self.write('shadowing.py', 'print = choose_handler\nresult = print(1)\n')
        self.write('exporting.py', 'def __getattr__(name):\n    return name\n')
        self.track()
        index = build_dependency_index(self.root, ['shadowing.py', 'exporting.py'])
        self.assertIn('unresolved_symbol', {u['reason'] for u in index['unresolved']})
        self.assertIn('reflection', {u['reason'] for u in index['unresolved']})

    def test_rebound_or_parameter_shadowed_imports_do_not_claim_direct_target(self):
        self.write('rebound.py', 'from pkg.leaf import calculate\ncalculate = 3\ncalculate(1)\n')
        self.write('parameter.py', 'from pkg.leaf import calculate\ndef indirect(calculate):\n    return calculate(1)\n')
        self.track()
        index = build_dependency_index(self.root, ['rebound.py', 'parameter.py'])
        self.assertFalse(any(e['source_path'] in ('rebound.py', 'parameter.py') and e['relation_type'] == 'direct_call'
                             and e['dependency_path'] == 'pkg/leaf.py' for e in index['edges']))
        self.assertIn('shadowed_or_rebound_import', {u['reason'] for u in index['unresolved']})

    def test_repository_change_during_comparison_invalidates_metric_claims(self):
        index = build_dependency_index(self.root, ['main.py'])
        legacy = self.legacy(['pkg/helper.py'])
        acquire = dependency_index._legacy
        def change_after_acquisition(root, observed, identity):
            result = acquire(root, observed, identity)
            self.write('pkg/leaf.py', 'def calculate(value):\n    return value + 9\n')
            return result
        with patch.object(dependency_index, '_legacy', side_effect=change_after_acquisition):
            result = compare_dependency_shadow(self.root, index, ['main.py'], legacy=legacy)
        self.assertTrue(result['fallback'])
        self.assertIsNone(result['comparison']['true_positive_count'])
        self.assertIn('repository_changed_during_shadow', result['fallback_reasons'])

    def test_ambiguous_package_prefix_and_namespace_scope_are_unknown(self):
        self.write('pkg.py', 'value = 1\n')
        self.write('namespace/part.py', 'value = 1\n')
        self.write('namespace_client.py', 'import namespace.part\n')
        self.track()
        index = build_dependency_index(self.root, ['main.py', 'namespace_client.py'])
        self.assertIn('ambiguous_import', {u['reason'] for u in index['unresolved']})
        self.assertIn('namespace_package_scope', {u['reason'] for u in index['unresolved']})

    def test_source_dependency_or_git_head_changes_invalidate_index(self):
        index = build_dependency_index(self.root, ['main.py'])
        self.write('pkg/leaf.py', 'def calculate(value):\n    return value + 2\n')
        with self.assertRaisesRegex(ValueError, 'stale_dependency_index'):
            validate_dependency_index(self.root, index)
        result = compare_dependency_shadow(self.root, index, ['main.py'], legacy=self.legacy(['pkg/leaf.py']))
        self.assertTrue(result['fallback'])
        self.assertIsNone(result['comparison']['true_positive_count'])

    def test_corruption_and_resigned_semantic_omission_reject(self):
        for resign in (False, True):
            with self.subTest(resign=resign):
                index = build_dependency_index(self.root, ['main.py'])
                index['edges'] = []
                if resign:
                    index['canonical_sha256'] = canonical_hash({k: v for k, v in index.items() if k not in ('canonical_sha256', 'build_metrics')})
                with self.assertRaises(ValueError):
                    validate_dependency_index(self.root, index)

    def test_missing_untracked_and_traversal_paths_never_become_known_none(self):
        self.write('untracked.py', 'value = 1\n')
        for path in ('missing.py', 'untracked.py', '../outside.py', str(self.root / 'main.py')):
            with self.subTest(path=path), self.assertRaises(ValueError):
                build_dependency_index(self.root, [path])

    def test_independent_legacy_comparison_reports_real_tp_fp_fn_and_material_block(self):
        self.write('missed.py', 'value = 1\n')
        self.track()
        index = build_dependency_index(self.root, ['main.py'])
        legacy = self.legacy(['pkg/helper.py', 'missed.py'], material_paths=['missed.py'])
        result = compare_dependency_shadow(self.root, index, ['main.py'], legacy=legacy)
        comparison = result['comparison']
        self.assertEqual(comparison['true_positive_paths'], ['pkg/helper.py'])
        self.assertEqual(comparison['false_negative_paths'], ['missed.py'])
        self.assertIn('pkg/leaf.py', comparison['false_positive_paths'])
        self.assertEqual(comparison['material_false_negative_count'], 1)
        self.assertTrue(result['promotion_blocked'])
        self.assertIn('material_false_negative', result['fallback_reasons'])
        self.assertEqual(result['actual_route'], 'legacy_full')
        self.assertFalse(result['production_adoption'])
        self.assertTrue(result['changed_files_full'])

    def test_unknown_stale_unacquired_legacy_metrics_remain_null(self):
        index = build_dependency_index(self.root, ['main.py'])
        original = self.legacy(['pkg/helper.py'])
        variants = [None, dict(original, acquired=False), dict(original, independent=False),
                    dict(original, source='c' * 40), dict(original, dependency_hashes={}), dict(original, provenance={})]
        for legacy in variants:
            with self.subTest(legacy=legacy):
                result = compare_dependency_shadow(self.root, index, ['main.py'], legacy=legacy)
                self.assertTrue(result['fallback'])
                self.assertIsNone(result['comparison']['false_negative_count'])
                self.assertIn('legacy_evidence', result['comparison']['missing_reasons'])

    def test_legacy_dependency_hash_mismatch_and_unknown_material_subset_fallback(self):
        index = build_dependency_index(self.root, ['main.py'])
        for mutation in ('hash', 'subset'):
            with self.subTest(mutation=mutation):
                legacy = self.legacy(['pkg/helper.py'])
                if mutation == 'hash':
                    legacy['dependency_hashes']['pkg/helper.py'] = 'c' * 64
                else:
                    legacy['material_paths'] = ['pkg/leaf.py']
                result = compare_dependency_shadow(self.root, index, ['main.py'], legacy=legacy)
                self.assertTrue(result['fallback'])
                self.assertIsNone(result['comparison']['true_positive_count'])

    def test_symlink_scoped_source_is_rejected(self):
        try:
            (self.root / 'alias.py').symlink_to(self.root / 'main.py')
        except OSError:
            self.skipTest('Symlink creation privilege unavailable on this host')
        self.track()
        with self.assertRaises(ValueError):
            build_dependency_index(self.root, ['alias.py'])

    def test_secret_like_source_or_identifier_never_stored(self):
        fictional = ''.join(['pass', 'word', ' = "fictional-value"\n'])
        self.write('sensitive.py', fictional)
        self.track()
        with self.assertRaisesRegex(ValueError, 'sensitive_evidence'):
            build_dependency_index(self.root, ['sensitive.py'])


if __name__ == '__main__':
    unittest.main()
