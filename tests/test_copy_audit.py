"""Behavioural checks for the approved copy audit and its calculation fixes."""
from pathlib import Path
import sys
import unittest
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine
from risk_model import compute_risk_metrics, MIN_OBSERVATIONS
from cost_model import Settings, StartOrderWindow, simulate_paths, MODES
from test_cost_model import term


class RiskAvailabilityTests(unittest.TestCase):
    def test_insufficient_observations_stay_missing_in_summary_and_holdings(self):
        for size in (0, 1, MIN_OBSERVATIONS):
            with self.subTest(prices=size):
                prices = pd.DataFrame({"A": np.linspace(100, 110, size)}, index=pd.bdate_range("2026-01-02", periods=size))
                assets, summary = compute_risk_metrics(prices, {"A": 1}, 2)
                self.assertFalse(summary["metrics_valid"])
                self.assertEqual(summary["observations"], max(0, size - 1))
                for key in ("annual_return_pct", "annual_volatility_pct", "sharpe_ratio", "max_drawdown_pct"):
                    self.assertTrue(np.isnan(summary[key]))
                    self.assertTrue(assets[key].isna().all())
                portfolio = pd.DataFrame([dict(name="A", ticker="A", category="Sverigefond", value_sek=100,
                                              last_review_value_sek=100, risk_level=4, asset_type="Aktiefond")])
                profile = dict(target_weights={"Sverigefond": 100}, equity_target=100)
                prepared = engine.prepare_portfolio(portfolio, profile, assets)
                self.assertTrue(prepared.annual_volatility_pct.isna().all())
                settings = dict(market_summary=summary, concentration_threshold=100, equity_buffer=0,
                                category_gap_threshold=0, min_portfolio_sharpe=0, max_portfolio_volatility=20,
                                max_drawdown_tolerance=20)
                insights = engine.detect_imbalances(prepared, "Egen", profile, settings)
                self.assertTrue(all(item["tone"] != "warning" for item in insights))
                self.assertIn("saknar tillräckligt underlag", insights[0]["body"])

    def test_valid_constant_prices_keep_measured_zero_but_undefined_sharpe(self):
        prices = pd.DataFrame({"A": np.full(30, 100.)}, index=pd.bdate_range("2026-01-02", periods=30))
        assets, summary = compute_risk_metrics(prices, {"A": 1}, 2)
        self.assertTrue(summary["metrics_valid"])
        for key in ("annual_return_pct", "annual_volatility_pct", "max_drawdown_pct"):
            self.assertEqual(summary[key], 0)
        self.assertTrue(np.isnan(summary["sharpe_ratio"]))
        self.assertTrue(assets.sharpe_ratio.isna().all())


class RebalanceCopyTests(unittest.TestCase):
    def notification(self, gaps, threshold, trade=True):
        frame = pd.DataFrame({"name": ["Fond A", "Fond B"], "category": ["Kategori A", "Kategori B"],
                              "weight_gap_pct": gaps, "trailing_1m_pct": [np.nan, np.nan]})
        trades = pd.DataFrame([dict(name="Fond A", trade_action="Sälj", trade_amount=1000),
                               dict(name="Fond B", trade_action="Köp", trade_amount=1000)])
        return engine.build_rebalance_notification(frame, trades if trade else trades.iloc[:0], "Egen", "Månadsvis", threshold)

    def test_on_target_and_at_tolerance_do_not_request_trades(self):
        for gaps in ([0, 0], [-5, 5], [-1e-12, 1e-12]):
            result = self.notification(gaps, 5)
            self.assertIn("inom dina valda viktgränser", result["body"])
            self.assertNotIn("sälj", result["body"])

    def test_drift_uses_percentage_points_and_only_actual_proposed_orders(self):
        result = self.notification([-10, 10], 5)
        self.assertIn("10 procentenheter över mål", result["body"])
        self.assertIn("10 procentenheter under mål", result["body"])
        self.assertIn("sälj Fond A för 1 000 kr", result["body"])
        self.assertNotIn("nan", result["body"])
        result = self.notification([-10, 10], 5, trade=False)
        self.assertIn("Inga affärer föreslås", result["body"])
        self.assertNotIn("gör mindre justeringar", result["body"])

    def test_only_an_existing_direction_is_described(self):
        result = self.notification([-8, 3], 5)
        self.assertIn("över mål", result["body"])
        self.assertNotIn("under mål", result["body"])


class StartCalendarTests(unittest.TestCase):
    def settings(self, history=()):
        return Settings(brokerage_class="Start", start_eligible=True, previous_free_order_history=history,
                        liquidate=False, include_tax=False)

    def test_exact_calendar_boundary_and_leap_year(self):
        window = StartOrderWindow(self.settings((("2024-02-29", 499),)), "2025-02-27", 10000)
        self.assertEqual(window.permission("2025-02-27")[1][0], 1)
        self.assertEqual(window.permission("2025-02-28")[1][0], 1)
        self.assertEqual(window.permission("2025-03-01")[1][0], 500)
        window = StartOrderWindow(self.settings((("2025-06-15", 499),)), "2026-06-14", 10000)
        self.assertEqual(window.permission("2026-06-14")[1][0], 1)
        self.assertEqual(window.permission("2026-06-15")[1][0], 500)

    def test_500_orders_can_expire_without_permanent_loss(self):
        window = StartOrderWindow(self.settings((("2025-06-15", 499),)), "2026-01-02", 10000)
        window.record("2026-01-02", [[1000]], [term()])
        self.assertTrue(window.eligible[0])
        self.assertEqual(window.permission("2026-01-02")[1][0], 0)
        self.assertEqual(window.permission("2026-06-15")[1][0], 499)
        self.assertTrue(window.eligible[0])

    def test_exceeding_limit_is_permanent_and_path_specific(self):
        window = StartOrderWindow(self.settings((("2025-12-01", 499),)), "2026-01-02", [10000, 10000], paths=2)
        window.record("2026-01-02", [[1000, 1000], [1000, 0]], [term("A"), term("B")])
        np.testing.assert_array_equal(window.eligible, [False, True])
        np.testing.assert_array_equal(window.permission("2027-02-01")[0], [False, True])
        lost_before_start = StartOrderWindow(self.settings((("2024-01-02", 501),)), "2026-01-02", 10000)
        self.assertFalse(lost_before_start.eligible[0])

    def test_asset_limit_is_permanent_even_after_value_falls(self):
        window = StartOrderWindow(self.settings(), "2026-01-02", 49999)
        window.update_wealth(50000)
        window.update_wealth(40000)
        self.assertFalse(window.permission("2027-01-04")[0][0])

    def test_only_actual_qualifying_stock_orders_consume_allowance(self):
        window = StartOrderWindow(self.settings(), "2026-01-02", 10000)
        for _ in range(1000):
            window.permission("2026-01-02")
        window.record("2026-01-02", [[100, 100, 100, 0]],
                      [term("A"), term("B", market="SE_FN"), term("C", market="FUND", fund=True), term("D")])
        self.assertEqual(window.permission("2026-01-02")[1][0], 499)

    def test_more_than_500_lifetime_orders_remain_free_when_spread_over_years(self):
        dates = pd.bdate_range("2023-01-02", "2025-12-31")
        returns = np.broadcast_to(np.r_[np.full(12, .001), np.full(12, -.001)], (len(dates)-1, 2, 24)).copy()
        result = simulate_paths(dates, returns, np.ones(24), np.zeros_like(returns),
                                [term(str(i)) for i in range(24)], np.ones(24), 20000,
                                MODES[1], self.settings())
        self.assertTrue((result["orders"] > 500).all())
        self.assertTrue(result["start_remaining"].all())
        np.testing.assert_allclose(result["components"]["courtage"], 0)
