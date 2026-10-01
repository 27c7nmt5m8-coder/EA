"""Offline request-cost provenance and ledger reconciliation contracts."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.workflow_eval.pricing import (
    RATES, ledger_cost, request_cost, summarize_review_costs, validate_pricing_requests,
)


class WorkflowPricing(unittest.TestCase):
    def observation(self, tokens=100, **updates):
        result = dict(request_id='one', usage_scope='request', model='gpt-6.1-sol',
                      effective_service_tier='default', regional_processing=False,
                      context_input_tokens=tokens, usage=dict(input_tokens=tokens,
                      cached_input_tokens=0, cache_write_input_tokens=0, output_tokens=10))
        result.update(updates)
        return result

    def test_rates_date_and_offline_claim(self):
        self.assertEqual(RATES['as_of'], '2026-10-02')
        self.assertEqual(request_cost(self.observation())['pricing_basis'], 'current_standard_text')

    def test_safe_optional_ledger_validation_preserves_unknowns(self):
        self.assertIsNone(validate_pricing_requests(None))
        rows = [dict(request_id='req_Unknown-2', usage_scope=None, model='unknown',
                     effective_service_tier='auto', regional_processing=None,
                     context_input_tokens=None, usage=dict(input_tokens=100, output_tokens=10))]
        self.assertIs(validate_pricing_requests(rows), rows)
        self.assertIsNone(request_cost(rows[0])['amount_usd'])
        self.assertEqual(validate_pricing_requests([]), [])
        incomplete = [dict(self.observation(), context_input_tokens=99)]
        self.assertIs(validate_pricing_requests(incomplete), incomplete)
        self.assertIsNone(request_cost(incomplete[0])['amount_usd'])

    def test_safe_ledger_validation_rejects_raw_nested_and_secret_content(self):
        invalids = [dict(self.observation(), prompt='fictional text'),
                    dict(self.observation(), raw_response={}),
                    dict(self.observation(), usage=dict(input_tokens=100, output_tokens=10, details={})),
                    dict(self.observation(), model='sk-proj-fictional-test-token'),
                    dict(self.observation(), request_id='ghp_fictional_test_token'),
                    dict(self.observation(), effective_service_tier={'tier': 'default'}),
                    dict(self.observation(), regional_processing='false'),
                    dict(self.observation(), context_input_tokens=True),
                    dict(self.observation(), usage=dict(input_tokens='fictional raw data'))]
        for row in invalids:
            with self.subTest(field=set(row)):
                with self.assertRaisesRegex(ValueError, 'invalid_pricing_schema|sensitive_pricing_metadata'):
                    validate_pricing_requests([row])
                self.assertIsNone(request_cost(row)['amount_usd'])
        for ledger in ({}, 'raw text', [None]):
            with self.assertRaises(ValueError):
                validate_pricing_requests(ledger)

    def test_long_context_counts_cached_and_cache_write_input(self):
        row = self.observation(272001)
        row['usage'].update(cached_input_tokens=250000, cache_write_input_tokens=22001)
        got = request_cost(row)
        self.assertAlmostEqual(got['amount_usd'], (250000 * .1 * 2 + 22001 * 2.5 * 2 + 10 * 10 * 1.5) / 1e6)
        self.assertTrue(got['long_context'])

    def test_unbounded_numeric_input_cannot_emit_nonfinite_money(self):
        row = self.observation(10 ** 400)
        self.assertIs(validate_pricing_requests([row])[0], row)
        self.assertIsNone(request_cost(row)['amount_usd'])

    def test_threshold_applies_to_entire_request(self):
        for tokens, multiplier, output_multiplier in [(271999, 1, 1), (272000, 1, 1), (272001, 2, 1.5)]:
            with self.subTest(tokens=tokens):
                got = request_cost(self.observation(tokens))
                self.assertAlmostEqual(got['amount_usd'], (tokens * 2 * multiplier + 100 * output_multiplier) / 1e6)
                self.assertEqual(got['long_context'], tokens > 272000)

    def test_effective_tiers_and_explicit_region(self):
        for tier, multiplier in [('default', 1), ('priority', 2), ('fast', 2), ('flex', .5), ('batch', .5)]:
            row = self.observation(effective_service_tier=tier, processing_mode='batch')
            self.assertAlmostEqual(request_cost(row)['amount_usd'], .0003 * multiplier)
            row['regional_processing'] = True
            self.assertAlmostEqual(request_cost(row)['amount_usd'], .0003 * multiplier * 1.1)
        self.assertIsNone(request_cost(self.observation(effective_service_tier='batch'))['amount_usd'])

    def test_cache_categories_and_historical_model(self):
        row = self.observation()
        row['usage'].update(cached_input_tokens=50, cache_write_input_tokens=20)
        self.assertAlmostEqual(request_cost(row)['amount_usd'], .000215)
        row['model'] = 'gpt-6-sol'
        got = request_cost(row)
        self.assertAlmostEqual(got['amount_usd'], .00022)
        self.assertEqual(got['pricing_basis'], 'historical_standard_text_scenario')

    def test_missing_provenance_is_unknown(self):
        for key in ['model', 'effective_service_tier', 'regional_processing', 'context_input_tokens', 'usage_scope']:
            row = self.observation(); del row[key]
            self.assertIsNone(request_cost(row)['amount_usd'], key)
        for key in ['cached_input_tokens', 'cache_write_input_tokens']:
            row = self.observation(); del row['usage'][key]
            self.assertIsNone(request_cost(row)['amount_usd'], key)
        for changes in [dict(model='unknown'), dict(effective_service_tier='auto'),
                        dict(regional_processing=None), dict(context_input_tokens=99), dict(usage_scope='session_cumulative')]:
            self.assertIsNone(request_cost(self.observation(**changes))['amount_usd'])

    def test_invalid_numbers_overlap_and_reasoning_subset(self):
        for key in ['input_tokens', 'output_tokens', 'cached_input_tokens', 'cache_write_input_tokens']:
            for invalid in [True, -1, 1.5, float('nan'), float('inf')]:
                row = self.observation(); row['usage'][key] = invalid
                self.assertIsNone(request_cost(row)['amount_usd'], (key, invalid))
        for usage_updates in [dict(cached_input_tokens=90, cache_write_input_tokens=20),
                              dict(reasoning_output_tokens=11), dict(total_tokens=111)]:
            row = self.observation(); row['usage'].update(usage_updates)
            self.assertIsNone(request_cost(row)['amount_usd'])
        row = self.observation(); row['usage']['reasoning_output_tokens'] = 10
        self.assertAlmostEqual(request_cost(row)['amount_usd'], .0003)
        self.assertIsNone(request_cost(self.observation(context_input_tokens=True))['amount_usd'])

    def test_ledger_prices_each_context_before_summing(self):
        first = self.observation(200000)
        second = self.observation(200000, request_id='two')
        expected = dict(input_tokens=400000, output_tokens=20, cached_input_tokens=0, cache_write_input_tokens=0)
        got = ledger_cost([first, second], 'gpt-6.1-sol', expected)
        self.assertAlmostEqual(got['amount_usd'], .8002)
        self.assertEqual(got['coverage'], 1)

    def test_ledger_rejects_mismatch_duplicates_and_incomplete_requests(self):
        row = self.observation()
        expected = copy.deepcopy(row['usage'])
        for requests, model, totals in [([row], 'gpt-6-sol', expected), ([row, row], 'gpt-6.1-sol', expected),
                ([row], 'gpt-6.1-sol', dict(expected, input_tokens=101)),
                ([dict(row, effective_service_tier=None)], 'gpt-6.1-sol', expected),
                ([dict(row, request_id=None)], 'gpt-6.1-sol', expected), ([], 'gpt-6.1-sol', expected)]:
            self.assertIsNone(ledger_cost(requests, model, totals)['amount_usd'])
        incomplete = dict(row, request_id='two', effective_service_tier=None)
        got = ledger_cost([row, incomplete], 'gpt-6.1-sol', expected)
        self.assertIsNone(got['amount_usd'])
        self.assertAlmostEqual(got['known_request_subtotal_usd'], .0003)
        self.assertEqual(got['coverage'], .5)

    def test_ledger_requires_safe_opaque_request_identifiers(self):
        row = self.observation()
        for identifier in ['a' * 81, 'request with spaces', 'mail@example.invalid', '../request', '', None]:
            invalid = dict(row, request_id=identifier)
            self.assertIsNone(ledger_cost([invalid], row['model'], row['usage'])['amount_usd'])
        safe = dict(row, request_id='req_One-2')
        self.assertIsNotNone(ledger_cost([safe], row['model'], row['usage'])['amount_usd'])

    def test_review_summary_requires_every_reconciled_ledger(self):
        row = self.observation()
        review = dict(model=row['model'], usage=row['usage'], pricing_requests=[row])
        complete = summarize_review_costs([review, copy.deepcopy(review)])
        self.assertAlmostEqual(complete['amount_usd'], .0006)
        self.assertEqual(complete['priced_reviews'], 2)
        self.assertEqual(complete['coverage'], 1)
        self.assertEqual(complete['missing_reasons'], {})
        missing = dict(model=row['model'], usage=row['usage'])
        partial = summarize_review_costs([review, missing])
        self.assertIsNone(partial['amount_usd'])
        self.assertAlmostEqual(partial['known_request_subtotal_usd'], .0003)
        self.assertEqual(partial['missing_reasons'], {'missing_request_ledger': 1})
        self.assertEqual(partial['missing_reviews'], 1)
        self.assertEqual(partial['coverage'], .5)
        mismatch = dict(review, usage=dict(row['usage'], input_tokens=101))
        got = summarize_review_costs([mismatch])
        self.assertIsNone(got['amount_usd'])
        self.assertEqual(got['missing_reasons'], {'ledger_usage_mismatch': 1})
        self.assertAlmostEqual(got['known_request_subtotal_usd'], .0003)
        self.assertIsNone(summarize_review_costs([])['amount_usd'])


if __name__ == '__main__':
    unittest.main()
