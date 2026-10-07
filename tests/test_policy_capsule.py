"""Shadow policy selection must never alter production authority or scope."""
import copy
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.workflow_eval import context, rules
AUTHORITY_FILES = [rules.CATALOG_PATH, *rules.DOCUMENT_PATHS.values(),
                   '.codex/config.toml', 'tools/workflow_eval/policy.json']


class PolicyCapsuleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.git('init','-q')
        self.git('config','core.autocrlf','false')
        self.git('config','user.name','Fixture')
        self.git('config','user.email','fixture'+chr(64)+'example.invalid')
        for rel in AUTHORITY_FILES:
            target=self.root/rel
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes((ROOT/rel).read_bytes())
        (self.root/'docs').mkdir()
        (self.root/'docs/note.md').write_text('Before.\n',encoding='utf-8')
        self.git('add','.')
        self.git('commit','-qm','fixture')
        (self.root/'docs/note.md').write_text('After.\n',encoding='utf-8')
        self.bundle=context.build_bundle(self.root,'HEAD',[],'Update developer note.')

    def git(self,*args):
        return subprocess.check_output(['git',*args],cwd=self.root,stderr=subprocess.DEVNULL)

    def module(self):
        self.assertTrue((ROOT/'tools/workflow_eval/policy_capsule.py').is_file(),
                        'Shadow capsule implementation must exist')
        return importlib.import_module('tools.workflow_eval.policy_capsule')

    def inputs(self,**overrides):
        values=dict(role='worker',task_type='routine',changed_paths=tuple(self.bundle['changed_paths']),
                    protected=self.bundle['protected'],dependency=self.bundle['dependency'],
                    repository_area='documentation',operation_type='implement',review_mode='none')
        values.update(overrides)
        return self.module().CapsuleInput(**values)

    def build(self,**overrides):
        return self.module().build_policy_capsule(self.root,self.bundle,self.inputs(**overrides))

    def assert_full_production(self,report):
        self.assertIs(report['production_adoption'],False)
        self.assertEqual(set(report['actual_rule_ids']),set(rules.GLOBAL_RULE_IDS))
        self.assertEqual({e['id']:e['body'] for e in report['actual_policy']},
                         {e['id']:e['body'] for e in rules.resolve_rules(self.root,rules.GLOBAL_RULE_IDS)})
        self.assertIs(report['changed_file_slicing'],False)
        self.assertIs(report['dependency_selection_changed'],False)

    def test_routine_shadow_is_deterministic_and_actual_policy_remains_full(self):
        result=self.build()
        self.assertEqual(result,self.build())
        self.assertEqual(result['status'],'SHADOW')
        self.assertEqual(result['unexpected_omission'],[])
        self.assertEqual(result['unexpected_inclusion'],[])
        self.assertEqual(result['omitted_rule_ids'],['RULE_JEV_SHADOW'])
        self.assert_full_production(result)
        self.assertEqual(result['source_binding']['bundle_sha256'],
                         self.module().canonical_hash(self.bundle))
        self.assertTrue(result['source_binding']['repository_validated'])

    def test_reviewer_has_every_required_safety_model_security_context_and_gate(self):
        result=self.build(role='reviewer',task_type='review',operation_type='review',
                          review_mode='mandatory_independent')
        self.assertEqual(set(result['selected_rule_ids']),set(rules.GLOBAL_RULE_IDS))
        self.assertTrue(all(item['complete'] for item in result['coverage'].values()))
        self.assert_full_production(result)

    def test_protected_selection_is_full_and_cannot_downgrade_review(self):
        (self.root/'docs/note.md').write_text('Preserve risk controls.\n',encoding='utf-8')
        self.bundle=context.build_bundle(self.root,'HEAD',[],'Inspect risk controls.')
        result=self.build(task_type='complex')
        self.assertEqual(result['status'],'FALLBACK')
        self.assertIn('protected_task_requires_full_policy',result['fallback_reasons'])
        self.assertEqual(set(result['selected_rule_ids']),set(rules.GLOBAL_RULE_IDS))
        self.assert_full_production(result)

    def test_unknown_classification_role_dependency_protected_and_mode_use_full_fallback(self):
        for overrides in [dict(task_type='unknown'),dict(role='unknown'),dict(dependency='unknown'),
                          dict(protected=None),dict(repository_area='unknown'),
                          dict(operation_type='unknown'),dict(review_mode='unknown')]:
            with self.subTest(overrides=overrides):
                result=self.build(**overrides)
                self.assertEqual(result['status'],'FALLBACK')
                self.assertTrue(result['fallback_reasons'])
                self.assertEqual(set(result['selected_rule_ids']),set(rules.GLOBAL_RULE_IDS))
                self.assert_full_production(result)

    def test_unknown_actual_path_and_caller_path_mismatch_use_full_fallback(self):
        result=self.build(changed_paths=('docs/absent.md',))
        self.assertIn('changed_paths_mismatch',result['fallback_reasons'])
        (self.root/'unclassified.txt').write_text('Fictional source.\n',encoding='utf-8')
        self.bundle=context.build_bundle(self.root,'HEAD',[],'Inspect note.')
        result=self.build(repository_area='mixed')
        self.assertIn('unknown_path',result['fallback_reasons'])
        self.assert_full_production(result)

    def test_missing_version_corruption_and_missing_required_source_block_authority(self):
        path=self.root/rules.CATALOG_PATH
        original=path.read_bytes()
        agents=self.root/'AGENTS.md'
        original_agents=agents.read_bytes()
        for mutation in ('missing','version','corruption','missing_document'):
            with self.subTest(mutation=mutation):
                try:
                    if mutation=='missing': path.unlink()
                    elif mutation=='missing_document': agents.unlink()
                    else:
                        data=json.loads(original)
                        if mutation=='version': data['rule_version']='unknown'
                        else: data['rules']['RULE_SECURITY']['body']='Altered.'
                        path.write_text(json.dumps(data),encoding='utf-8')
                    result=self.build()
                    self.assertEqual(result['status'],'BLOCKED')
                    self.assertEqual(result['actual_policy'],[])
                    self.assertFalse(result['production_adoption'])
                    self.assertTrue(result['authority_acquisition_required'])
                finally:
                    path.write_bytes(original)
                    agents.write_bytes(original_agents)

    def test_independent_expected_table_detects_false_omission_and_inclusion(self):
        mod=self.module()
        candidate=list(rules.GLOBAL_RULE_IDS)
        candidate.remove('RULE_SECURITY')
        comparison=mod.compare_candidate_rule_ids(self.root,self.inputs(),candidate)
        self.assertEqual(comparison['unexpected_omission'],['RULE_SECURITY'])
        self.assertEqual(comparison['unexpected_inclusion'],['RULE_JEV_SHADOW'])
        with patch.object(mod,'_select_candidate',return_value=candidate):
            result=self.build()
        self.assertEqual(result['status'],'FALLBACK')
        self.assertEqual(result['unexpected_omission'],['RULE_SECURITY'])
        self.assert_full_production(result)
        self.assertEqual(set(result['selected_rule_ids']),set(rules.GLOBAL_RULE_IDS))

    def test_stale_or_forged_bundle_and_unbound_root_never_enable_candidate_policy(self):
        (self.root/'docs/note.md').write_text('Newer.\n',encoding='utf-8')
        result=self.build()
        self.assertEqual(result['status'],'FALLBACK')
        self.assertIn('bundle_validation_failed',result['fallback_reasons'])
        self.assertFalse(result['source_binding']['repository_validated'])
        forged=copy.deepcopy(self.bundle)
        forged['changed_paths']=[]
        result=self.module().build_policy_capsule(self.root,forged,self.inputs())
        self.assertEqual(result['status'],'FALLBACK')
        unbound=self.module().build_policy_capsule(None,self.bundle,self.inputs())
        self.assertEqual(unbound['status'],'FALLBACK')
        self.assertIn('repository_binding_required',unbound['fallback_reasons'])

    def test_body_references_bind_actual_complete_canonical_bodies(self):
        result=self.build()
        catalog=rules.load_catalog(self.root)
        for entry in result['candidate_body_references']:
            self.assertEqual(entry['catalog_sha256'],catalog['canonical_sha256'])
            self.assertEqual(entry['body_sha256'],catalog['rules'][entry['id']]['body_sha256'])
            self.assertTrue(entry['requires_full_body'])
        self.assertFalse(result['review_skip_enabled'])
        self.assertEqual(result['jev_confidence_threshold'],.90)

    def test_parser_selector_and_unknown_reference_errors_fall_back_without_authority_loss(self):
        mod=self.module()
        malformed=mod.build_policy_capsule(self.root,self.bundle,{'role':'worker'})
        self.assertEqual(malformed['status'],'FALLBACK')
        self.assertIn('input_parsing_error',malformed['fallback_reasons'])
        self.assert_full_production(malformed)
        with patch.object(mod,'_select_candidate',side_effect=ValueError('fictional_failure')):
            failed=self.build()
        self.assertIn('capsule_generation_error',failed['fallback_reasons'])
        self.assert_full_production(failed)
        unknown=[*rules.GLOBAL_RULE_IDS,'RULE_UNKNOWN_REFERENCE']
        with patch.object(mod,'_select_candidate',return_value=unknown):
            failed=self.build()
        self.assertIn('RULE_UNKNOWN_REFERENCE',failed['unexpected_inclusion'])
        self.assertIsNone(failed['candidate_full_body_sha256'])
        self.assert_full_production(failed)

    def test_non_git_root_is_full_fallback_and_never_source_validated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for rel in AUTHORITY_FILES:
                target=root/rel
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes((ROOT/rel).read_bytes())
            report=self.module().build_policy_capsule(root,self.bundle,self.inputs())
            self.assertEqual(report['status'],'FALLBACK')
            self.assertFalse(report['source_binding']['repository_validated'])
            self.assertIn('bundle_validation_failed',report['fallback_reasons'])
            self.assertEqual(set(report['actual_rule_ids']),set(rules.GLOBAL_RULE_IDS))

    def test_read_only_role_cannot_claim_write_operation_as_known_classification(self):
        result=self.build(role='explorer',task_type='exploration',operation_type='implement')
        self.assertEqual(result['status'],'FALLBACK')
        self.assertIn('role_operation_mismatch',result['fallback_reasons'])
        self.assert_full_production(result)

    def test_catalog_parsing_missing_rule_and_invalid_document_version_block(self):
        path=self.root/rules.CATALOG_PATH
        original=path.read_bytes()
        agents=self.root/'AGENTS.md'
        original_agents=agents.read_bytes()
        for mutation in ('parsing','missing_rule','document_version'):
            with self.subTest(mutation=mutation):
                try:
                    if mutation=='parsing':
                        path.write_text('{invalid',encoding='utf-8')
                    elif mutation=='missing_rule':
                        data=json.loads(original)
                        del data['rules']['RULE_CONTEXT_FULL']
                        path.write_text(json.dumps(data),encoding='utf-8')
                    else:
                        agents.write_text(original_agents.decode('utf-8').replace(
                            'version=phase2a-1','version=unknown'),encoding='utf-8')
                    report=self.build()
                    self.assertEqual(report['status'],'BLOCKED')
                    self.assertEqual(report['actual_policy'],[])
                    self.assertTrue(report['authority_acquisition_required'])
                finally:
                    path.write_bytes(original)
                    agents.write_bytes(original_agents)

    def test_current_policy_version_threshold_review_floor_and_hidden_routing_are_authority(self):
        path=self.root/'tools/workflow_eval/policy.json'
        original=path.read_bytes()
        changes=[('version',999),('confidence_threshold',.89),('review_skip_enabled',True),
                 ('normal_effort','medium'),('mandatory_effort','medium'),
                 ('implementation_model','gpt-6-sol'),('escalation_effort','high'),
                 ('mode','production'),('fallback_model','gpt-6-astra')]
        for key,value in changes:
            with self.subTest(key=key,value=value):
                try:
                    data=json.loads(original)
                    data[key]=value
                    path.write_text(json.dumps(data),encoding='utf-8')
                    result=self.build()
                    self.assertEqual(result['status'],'BLOCKED')
                    self.assertEqual(result['actual_policy'],[])
                    self.assertTrue(result['authority_acquisition_required'])
                finally:
                    path.write_bytes(original)

    def test_config_root_and_default_agent_floor_missing_authorities_and_history_scope(self):
        config=self.root/'.codex/config.toml'
        policy=self.root/'tools/workflow_eval/policy.json'
        original_config=config.read_bytes()
        original_policy=policy.read_bytes()
        replacements=[('model = "gpt-6.1-sol"','model = "gpt-6-sol"'),
                      ('model_reasoning_effort = "high"','model_reasoning_effort = "medium"'),
                      ('default_subagent_model = "gpt-6.1-sol"','default_subagent_model = "gpt-5.6-sol"'),
                      ('default_subagent_reasoning_effort = "high"','default_subagent_reasoning_effort = "medium"')]
        for old,new in replacements:
            with self.subTest(old=old):
                try:
                    config.write_text(original_config.decode('utf-8').replace(old,new),encoding='utf-8')
                    self.assertEqual(self.build()['status'],'BLOCKED')
                finally:
                    config.write_bytes(original_config)
        for path,original in [(config,original_config),(policy,original_policy)]:
            with self.subTest(missing=path.name):
                try:
                    path.unlink()
                    self.assertEqual(self.build()['status'],'BLOCKED')
                finally:
                    path.write_bytes(original)
        try:
            data=json.loads(original_policy)
            data['historical_sol_standard_short_context_rates']['scope']='execution_fallback'
            policy.write_text(json.dumps(data),encoding='utf-8')
            self.assertEqual(self.build()['status'],'BLOCKED')
        finally:
            policy.write_bytes(original_policy)
        valid=self.build()
        self.assertEqual(valid['status'],'SHADOW')
        self.assertTrue({'.codex/config.toml','tools/workflow_eval/policy.json'} <=
                        {source['path'] for source in valid['authority_sources']})

    def test_routine_caller_label_cannot_omit_jev_shadow_for_actual_jev_documentation(self):
        (self.root/'docs/note.md').write_text('Explain Jev shadow routing.\n',encoding='utf-8')
        self.bundle=context.build_bundle(self.root,'HEAD',[],'Update developer note.')
        report=self.build()
        self.assertEqual(report['status'],'FALLBACK')
        self.assertIn('jev_scope_requires_full_policy',report['fallback_reasons'])
        self.assertEqual(set(report['selected_rule_ids']),set(rules.GLOBAL_RULE_IDS))
        self.assert_full_production(report)

    def test_authority_mutation_during_generation_never_claims_coherent_shadow(self):
        mod=self.module()
        original=mod._select_candidate
        config=self.root/'.codex/config.toml'
        saved=config.read_bytes()
        def mutate_authority(*args):
            selected=original(*args)
            config.write_bytes(saved+b'\n# Concurrent formatting change.\n')
            return selected
        try:
            with patch.object(mod,'_select_candidate',side_effect=mutate_authority):
                report=self.build()
            self.assertEqual(report['status'],'BLOCKED')
            self.assertEqual(report['actual_policy'],[])
            self.assertIn('canonical_authority_changed_during_generation',report['fallback_reasons'])
            self.assertFalse(report['routing_authorities_validated'])
            self.assertFalse(report['source_binding']['repository_validated'])
        finally:
            config.write_bytes(saved)

    def test_bundle_mutation_during_generation_never_claims_coherent_shadow(self):
        mod=self.module()
        original=mod._select_candidate
        def mutate_bundle(*args):
            selected=original(*args)
            (self.root/'docs/note.md').write_text('Concurrent source change.\n',encoding='utf-8')
            return selected
        with patch.object(mod,'_select_candidate',side_effect=mutate_bundle):
            report=self.build()
        self.assertEqual(report['status'],'FALLBACK')
        self.assertFalse(report['source_binding']['repository_validated'])
        self.assertIn('bundle_changed_during_generation',report['fallback_reasons'])
        self.assertTrue(report['context_acquisition_required'])
        self.assert_full_production(report)


if __name__=='__main__':
    unittest.main()
