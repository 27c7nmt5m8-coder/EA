"""Selective migration contracts on the current High-first experiment foundation."""
import copy
import json
from pathlib import Path
import sys
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
from tools.workflow_eval import real_tasks, report, triage
import test_workflow_real_tasks as real_fixture
import test_workflow_review_boundaries as synthetic_fixture


class Sol61Migration(unittest.TestCase):
    def test_project_defaults_preserve_high_first_and_jev_boundaries(self):
        config = tomllib.loads((ROOT / '.codex/config.toml').read_text(encoding='utf-8'))
        self.assertEqual(config['model'], triage.ACTIVE_SOL_MODEL)
        self.assertEqual(config['model_reasoning_effort'], 'high')
        self.assertEqual(config['agents'], dict(default_subagent_model=triage.ACTIVE_SOL_MODEL,
                                              default_subagent_reasoning_effort='high'))
        policy = triage.policy()
        self.assertEqual(policy['mandatory_effort'], 'high')
        self.assertEqual(policy['normal_effort'], 'high')
        self.assertEqual(policy['escalation_effort'], 'xhigh')
        self.assertEqual(policy['confidence_threshold'], .90)
        self.assertFalse(policy['review_skip_enabled'])

    def test_role_defaults_use_sol61_without_changing_reviewer_policy(self):
        agents = (ROOT / 'AGENTS.md').read_text(encoding='utf-8')
        skill = (ROOT / '.agents/skills/model-orchestrator/SKILL.md').read_text(encoding='utf-8')
        self.assertIn('root / orchestrator / integrate / verifyは `gpt-6.1-sol / high`', agents)
        self.assertIn('workerは通常 `gpt-6.1-sol / medium`', agents)
        self.assertIn('explorer / researcherは `gpt-6.1-sol / medium`', agents)
        self.assertIn('reviewerは独立contextの `gpt-6.1-sol / high`', agents)
        self.assertIn('Explorer/researcher use GPT-6.1 Sol Medium', skill)
        self.assertIn('Reviewers use independent Sol High contexts', skill)

    def test_latest_routing_cases_preserve_high_first_and_astra_approval(self):
        cases = json.loads((ROOT / '.agents/skills/model-orchestrator/fixtures/routing_cases.json').read_text())
        observed = json.loads((ROOT / '.agents/skills/model-orchestrator/fixtures/routing_dry_run.json').read_text())
        expected = {row['id']: row for row in cases['cases']}
        actual = {row['id']: row for row in observed['cases']}
        self.assertEqual(set(expected), set('ABCDEFGHIJKLM'))
        for case in ('D', 'H'):
            self.assertEqual(expected[case]['expected']['routes'], ['Sol/high'])
        self.assertEqual(expected['L']['expected']['routes'], ['Sol/xhigh'])
        self.assertIn('user_approved_astra_review', actual['M']['evidence'])

    def record(self, model='gpt-6.1-sol'):
        row = real_fixture.RealTaskTests().record()
        for arm in ('a', 'b'):
            row[arm].update(model=model, reasoning_effort='high',
                            usage=dict(input_tokens=100, cached_input_tokens=20,
                                       cache_write_input_tokens=0, output_tokens=10),
                            usage_fields=['cached_input_tokens', 'cache_write_input_tokens'])
        return row

    def request(self, model='gpt-6.1-sol'):
        return dict(request_id='request_one', usage_scope='request', model=model,
                    effective_service_tier='priority', regional_processing=False,
                    context_input_tokens=100, usage=copy.deepcopy(self.record(model)['a']['usage']))

    def test_optional_pricing_ledger_preserves_schema_v1_and_active_escalation(self):
        row = self.record()
        for arm in ('a', 'b'):
            row[arm]['pricing_requests'] = [self.request()]
        self.assertIs(real_tasks.validate_record(row), row)
        row['a']['reasoning_effort'] = 'xhigh'
        with self.assertRaises(ValueError):
            real_tasks.validate_record(row)
        row['a']['escalation'] = dict(reason='high_review_material_uncertainty', evidence='R1: unresolved interface contract')
        self.assertIs(real_tasks.validate_record(row), row)

    def test_pricing_metadata_rejects_raw_and_nested_unapproved_fields(self):
        for field in ('raw_response', 'prompt', 'api_key'):
            row = self.record()
            request = self.request()
            request[field] = 'Synthetic forbidden metadata'
            row['a']['pricing_requests'] = [request]
            with self.subTest(field=field), self.assertRaises(ValueError):
                real_tasks.validate_record(row)
        row = self.record()
        request = self.request()
        request['usage']['prompt'] = 'Synthetic forbidden metadata'
        row['a']['pricing_requests'] = [request]
        with self.assertRaises(ValueError):
            real_tasks.validate_record(row)

    def test_both_reports_require_observed_ledger_and_preserve_historical_prices(self):
        for model, scenario in [('gpt-6-sol', .000264), ('gpt-6.1-sol', .000262)]:
            synthetic = synthetic_fixture.ReviewBoundaries().row()
            real = self.record(model)
            for arm in ('a', 'b'):
                synthetic[arm].update(model=model, reasoning_effort='high', usage=real[arm]['usage'],
                                      usage_fields=real[arm]['usage_fields'])
            for summarize, row in ((report.summarize, synthetic), (real_tasks.summarize, real)):
                with self.subTest(model=model, summarize=summarize.__module__):
                    result = summarize([row])
                    self.assertIsNone(result['observed_text_token_api_equivalent']['a']['amount_usd'])
                    for arm in ('a', 'b'):
                        row[arm]['pricing_requests'] = [self.request(model)]
                    result = summarize([row])
                    self.assertAlmostEqual(result['observed_text_token_api_equivalent']['a']['amount_usd'], scenario * 2)
                    self.assertIsNone(result['all_provider_cost_usd'])


if __name__ == '__main__':
    unittest.main()
