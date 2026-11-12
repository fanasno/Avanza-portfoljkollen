from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import data
import market_data
from avanza_funds import get_avanza_funds
from risk_model import (select_risk_history, sharpe_from_values, horizon_factor,
                        portfolio_prices_sek, compute_risk_metrics)
from cost_model import Settings, default_terms, order_costs, cost_total, bootstrap_inputs


class AvanzaFundTests(unittest.TestCase):
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

    def test_catalog_has_24_distinct_verified_funds_including_all_autos(self):
        funds = get_avanza_funds()
        self.assertEqual(len(funds), 24)
        self.assertEqual(len({f["isin"] for f in funds}), 24)
        self.assertTrue({f"Avanza Auto {i}" for i in range(1, 7)}.issubset({f["name"] for f in funds}))
        zero = next(f for f in funds if f["name"] == "Avanza Zero")
        self.assertEqual(zero["isin"], "SE0001718388")
        self.assertEqual(zero["total_fee_pct"], 0)

    def test_all_funds_are_selectable_and_metadata_is_not_replaced_by_etfs(self):
        prices = market_data.make_example_history(("VT", "EWD", "XLK", "IEMG", "IWM", "BND", "USDSEK=X", "AAPL", "MSFT", "NVDA", "INVE-B.ST", "VOLV-B.ST"))
        portfolio = data.build_live_portfolio_values(data.load_live_portfolio_template(), prices)
        watchlist = data.build_live_watchlist_values(data.load_live_watchlist_template(), prices)
        universe = data.build_yfinance_instrument_universe(portfolio, watchlist)
        real = universe[universe.ticker.str.startswith("AVANZA:")]
        self.assertEqual(len(real), 24)
        self.assertTrue((real.instrument_type == "Fond").all())
        self.assertTrue((real.currency == "SEK").all())
        self.assertAlmostEqual(float(universe.loc[universe.ticker == "VT", "position_value_sek"].iloc[0]), float(portfolio.loc[portfolio.ticker == "VT", "value_sek"].iloc[0]))
        self.assertIn("AVANZA:41567", [f["ticker"] for f in data.get_category_instrument_catalog()["Sverigefond"]])

    def test_zero_has_no_brokerage_or_fx_in_any_class_and_bond_fund_keeps_tax_type(self):
        zero = default_terms({"ticker": "AVANZA:41567", "instrument_type": "Fond", "currency": "SEK", "fund_type": "EQUITY_FUND"})
        for name in ["Mini", "Small", "Medium", "Fast Pris", "Start"]:
            parts = order_costs([[100000]], [[1]], [zero], Settings(brokerage_class=name), "Köp")
            self.assertEqual(cost_total(parts).sum(), 0)
        self.assertEqual(zero["market"], "FUND")
        bond = default_terms({"ticker": "AVANZA:1684019", "instrument_type": "Fond", "currency": "SEK", "fund_type": "INTEREST_FUND"})
        self.assertTrue(bond["interest_fund"])

    def test_raw_nav_dates_use_stockholm_calendar_and_weekly_data_is_rejected(self):
        dates = pd.date_range("2026-01-05", periods=6, freq="B", tz="Europe/Stockholm")
        raw = {"dataSerie": [{"x": int(date.timestamp() * 1000), "y": 100 + i} for i, date in enumerate(dates)]}
        series = market_data.parse_avanza_nav(raw)
        self.assertEqual(series.index[0], pd.Timestamp("2026-01-05"))
        self.assertEqual(series.iloc[-1], 105)
        weekly = {"dataSerie": [{"x": int((dates[0] + pd.Timedelta(days=7*i)).timestamp() * 1000), "y": 100+i} for i in range(6)]}
        with self.assertRaises(ValueError):
            market_data.parse_avanza_nav(weekly)

    def test_native_nav_is_not_sent_to_yahoo_or_replaced_with_synthetic_prices(self):
        series = pd.Series([100., 101., 102.], index=pd.bdate_range("2026-10-28", periods=3), name="AVANZA:41567")
        with patch.object(market_data, "fetch_avanza_nav", return_value=series), patch.object(market_data.yf, "download") as yahoo:
            result = market_data.fetch_price_history((series.name,), mode="Marknadsdata")
        yahoo.assert_not_called()
        self.assertEqual(result.attrs["source"], "Avanza NAV")
        self.assertFalse(result.attrs["is_example"])
        np.testing.assert_array_equal(result[series.name], series)

    def test_failed_fund_source_does_not_create_example_prices(self):
        with patch.object(market_data, "fetch_avanza_nav", side_effect=ConnectionError("offline")), patch.object(market_data, "make_example_history") as synthetic:
            with self.assertRaises(market_data.PriceDataError):
                market_data.fetch_price_history(("AVANZA:41567",), mode="Marknadsdata")
        synthetic.assert_not_called()

    def test_example_data_does_not_invent_pre_launch_history(self):
        result = market_data.make_example_history(("AVANZA:2480007",))
        self.assertGreaterEqual(result.iloc[:, 0].first_valid_index(), pd.Timestamp("2026-05-27"))


class SharpeTests(unittest.TestCase):
    def prices(self):
        dates = pd.bdate_range("2021-11-01", periods=1261)
        rng = np.random.default_rng(78)
        r = rng.normal(.0002, .009, len(dates)-1)
        r[-63:] += .001
        return pd.DataFrame({"A": np.r_[100., 100*np.cumprod(1+r)]}, index=dates)

    def test_history_window_is_independent_of_annualization(self):
        prices = self.prices()
        year = select_risk_history(prices, "1 år")
        three_year = select_risk_history(prices, "3 år")
        self.assertEqual(len(year)-1, 252)
        self.assertEqual(len(three_year)-1, 756)
        self.assertNotAlmostEqual(sharpe_from_values(year.values)[0], sharpe_from_values(three_year.values)[0])
        self.assertEqual(len(select_risk_history(prices, "3 månader"))-1, 63)

    def test_custom_dates_are_inclusive_and_invalid_interval_is_empty(self):
        prices = self.prices()
        selected = select_risk_history(prices, "Egna datum", prices.index[10], prices.index[60])
        self.assertEqual(len(selected), 51)
        self.assertTrue(select_risk_history(prices, "Egna datum", prices.index[60], prices.index[10]).empty)

    def test_sharpe_uses_geometrically_converted_daily_risk_free_rate(self):
        prices = self.prices()
        returns = prices.pct_change().iloc[1:, 0]
        expected = (returns.mean()-((1+.04)**(1/252)-1))/returns.std(ddof=1)*np.sqrt(252)
        self.assertAlmostEqual(sharpe_from_values(prices.values, 4)[0], expected, places=10)
        self.assertLess(sharpe_from_values(prices.values, 4)[0], sharpe_from_values(prices.values, 0)[0])

    def test_horizon_scaling_is_a_separate_explicit_factor(self):
        self.assertEqual(horizon_factor(12), 1)
        self.assertAlmostEqual(horizon_factor(36), np.sqrt(3))
        self.assertAlmostEqual(horizon_factor(3), .5)
        with self.assertRaises(ValueError):
            horizon_factor(0)

    def test_short_constant_or_nonpositive_series_are_undefined(self):
        self.assertTrue(np.isnan(sharpe_from_values(np.linspace(100, 102, 10))[0]))
        self.assertTrue(np.isnan(sharpe_from_values(np.full(50, 100.))[0]))
        self.assertTrue(np.isnan(sharpe_from_values(np.r_[np.arange(50)+100, -1])[0]))

    def test_portfolio_risk_uses_sek_and_common_available_history(self):
        dates = pd.bdate_range("2026-01-05", periods=100)
        prices = pd.DataFrame({"US": np.full(100, 100.), "USDSEK=X": np.linspace(10, 12, 100),
                               "FUND": np.r_[np.full(30, np.nan), np.linspace(100, 110, 70)]}, index=dates)
        portfolio = pd.DataFrame({"ticker": ["US", "FUND"], "currency": ["USD", "SEK"]})
        sek = portfolio_prices_sek(prices, portfolio)
        self.assertEqual(sek.index[0], dates[30])
        self.assertAlmostEqual(sek.US.iloc[-1], 1200)
        _, summary = compute_risk_metrics(sek, {"US": 1, "FUND": 1}, 2)
        self.assertEqual(summary["observations"], 69)
        self.assertTrue(summary["risk_valid"])

    def test_forecast_training_window_does_not_move_the_scenario_start_into_the_past(self):
        prices = self.prices()
        fx = prices*0+1
        training = prices.iloc[200:350]
        result = bootstrap_inputs(prices, fx, prices.index[-1]+pd.DateOffset(months=1), paths=8,
                                  training_sek=training, training_fx=fx.reindex(training.index))
        self.assertEqual(result["dates"][0], prices.index[-1])
        source = training.pct_change().iloc[1:, 0].to_numpy()
        self.assertTrue(np.isin(result["returns"].ravel(), source).all())
