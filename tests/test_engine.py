import ast
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import data
import engine
import market_data


class OriginalCalculationRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = json.loads((ROOT / "tests" / "savr_baseline.json").read_text(encoding="utf-8"))
        cls.prices = market_data.make_example_history(tuple(cls.baseline["tickers"]))
        cls.portfolio = data.build_live_portfolio_values(data.load_live_portfolio_template(), cls.prices)
        cls.watchlist = data.build_live_watchlist_values(data.load_live_watchlist_template(), cls.prices)
        cls.universe = data.build_yfinance_instrument_universe(cls.portfolio, cls.watchlist)
        cls.asset_metrics, cls.summary = engine.compute_historical_metrics(cls.prices.iloc[-756:], cls.portfolio.set_index("ticker").value_sek.to_dict(), 2.0)
        cls.profile = engine.get_risk_profiles()["Balanserad"]
        cls.prepared = engine.prepare_portfolio(cls.portfolio, cls.profile, cls.asset_metrics)

    def test_unaffected_calculation_functions_match_original_ast(self):
        nodes = [n for n in ast.parse((ROOT / "engine.py").read_text(encoding="utf-8")).body if isinstance(n, ast.FunctionDef)]
        self.assertEqual(len(nodes), 33)
        changed = {"prepare_portfolio", "calculate_metrics", "detect_imbalances", "build_rebalance_notification"}
        self.assertEqual({node.name for node in nodes}, set(self.baseline["calculation_fingerprints"]))
        for node in nodes:
            if node.name in changed:
                continue
            with self.subTest(function=node.name):
                fingerprint = hashlib.sha256(ast.dump(node).encode()).hexdigest()
                self.assertEqual(fingerprint, self.baseline["calculation_fingerprints"][node.name])

    def test_portfolio_metrics_equal_original_savr_outputs(self):
        actual = engine.calculate_metrics(self.prepared, self.profile, self.summary)
        for key, expected in self.baseline["metrics"].items():
            with self.subTest(metric=key):
                if isinstance(expected, str):
                    self.assertEqual(actual[key], expected)
                else:
                    self.assertAlmostEqual(float(actual[key]), expected, places=7)

    def test_capital_conserved_by_rebalancing_and_contributions(self):
        self.assertAlmostEqual(self.prepared.trade_value.sum(), 0, places=7)
        self.assertAlmostEqual(self.prepared.current_weight_pct.sum(), 100)
        for amount in [0, 1000, 5000, 20000]:
            with self.subTest(contribution=amount):
                scenario = engine.simulate_contribution(self.prepared, amount)
                self.assertAlmostEqual(scenario.cash_allocation.sum(), amount)
                self.assertAlmostEqual(scenario.value_after_cash.sum(), self.prepared.value_sek.sum() + amount)

    def test_all_backtest_strategies_equal_original(self):
        assets = ["Apple", "Microsoft", "Investor B"]
        for mode, expected in self.baseline["backtests"].items():
            with self.subTest(strategy=mode):
                _, actual = engine.simulate_mock_backtest(self.universe, self.prices, assets, 10000, dict.fromkeys(assets, 1.0), "1 år bakåt", rebalance_mode=mode)
                for key, value in expected.items():
                    self.assertAlmostEqual(actual[key], value, places=7)

    def test_monte_carlo_equal_original_for_all_strategies(self):
        assets = ["Apple", "Microsoft", "Investor B"]
        for mode, expected in self.baseline["forecasts"].items():
            with self.subTest(strategy=mode):
                _, _, paths, actual = engine.simulate_mock_future(self.universe, self.prices, assets, 10000, dict.fromkeys(assets, 1.0), "3 månader framåt", simulations=128, rebalance_mode=mode)
                for key, value in expected.items():
                    self.assertAlmostEqual(actual[key], value, places=7)
                self.assertTrue((paths.p10 <= paths["median"]).all())
                self.assertTrue((paths["median"] <= paths.p90).all())


class DataProvenanceTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.cache = tempfile.TemporaryDirectory()
        self.addCleanup(self.cache.cleanup)
        override = patch.object(market_data, "PRICE_CACHE", Path(self.cache.name))
        override.start()
        self.addCleanup(override.stop)
        market_data.fetch_price_history.clear()

    def tearDown(self):
        market_data.fetch_price_history.clear()

    def test_example_data_never_calls_market_provider(self):
        with patch.object(market_data.yf, "download") as download:
            prices = market_data.fetch_price_history(("VT", "SEK=X"), mode="Exempeldata")
        download.assert_not_called()
        self.assertTrue(prices.attrs["is_example"])

    def test_failed_provider_never_substitutes_synthetic_prices(self):
        with patch.object(market_data.yf, "download", side_effect=ConnectionError("offline")), patch.object(market_data, "make_example_history") as synthetic:
            with self.assertRaises(market_data.PriceDataError):
                market_data.fetch_price_history(("VT", "SEK=X"), mode="Marknadsdata")
        synthetic.assert_not_called()

    def test_successful_market_prices_keep_yahoo_provenance(self):
        sample = pd.concat({"Close": pd.DataFrame({"VT": [100., 102., 101.]}, index=pd.bdate_range("2026-10-28", periods=3))}, axis=1)
        with patch.object(market_data.yf, "download", return_value=sample):
            prices = market_data.fetch_price_history(("VT",), mode="Marknadsdata")
        self.assertEqual(prices.attrs["source"], "Yahoo Finance")
        self.assertFalse(prices.attrs["is_example"])
        np.testing.assert_array_equal(prices.VT.to_numpy(), [100., 102., 101.])

    def test_partial_market_data_does_not_mix_with_example_prices(self):
        sample = pd.concat({"Close": pd.DataFrame({"VT": [100., 102.]}, index=pd.bdate_range("2026-10-28", periods=2))}, axis=1)
        with patch.object(market_data.yf, "download", return_value=sample):
            with self.assertRaises(market_data.PriceDataError):
                market_data.fetch_price_history(("VT", "SEK=X"), mode="Marknadsdata")

