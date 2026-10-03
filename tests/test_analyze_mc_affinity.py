import copy
import unittest
from tools.analyze_mc_affinity import comparison_fields


class ComparisonTests(unittest.TestCase):
    def case(self):
        return dict(chart_processed_ticks=10,symbol_bar_process_total=2,trades=1,
                    symbols={'FAKE':dict(funnel={'signals':2},outcomes={'entered':1},
                        mc_lifecycle={'waiting_opportunities':1,'wall_elapsed_ms':{'median':2}},
                        order_acceptance=1,quote_samples=10,quote_advances=10)})

    def test_compute_timing_change_does_not_fake_trade_funnel_difference(self):
        left=self.case();right=copy.deepcopy(left)
        right['symbols']['FAKE']['mc_lifecycle']['wall_elapsed_ms']['median']=20
        self.assertEqual(comparison_fields(left),comparison_fields(right))

    def test_opportunity_difference_is_not_hidden_by_equal_trades(self):
        left=self.case();right=copy.deepcopy(left)
        right['symbols']['FAKE']['funnel']['signals']=3
        self.assertNotEqual(comparison_fields(left),comparison_fields(right))
