from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine
import data
import market_data
from portfolio_model import (instrument_catalog, initial_holdings, target_rows_for_profile,
                             build_portfolio_template, target_profile, contribution_message)


class FreeInstrumentModelTests(unittest.TestCase):
    def setUp(self):
        self.base = engine.get_risk_profiles()["Balanserad"]
        self.holdings = initial_holdings()
        self.targets = target_rows_for_profile(self.base)

    def prepared(self, targets):
        template = build_portfolio_template(self.holdings, targets)
        prices = market_data.make_example_history(tuple(template.ticker) + ("USDSEK=X",))
        portfolio = data.build_live_portfolio_values(template, prices)
        profile = target_profile(targets, self.base, "Egen")
        return engine.prepare_portfolio(portfolio, profile), profile

    def test_catalog_has_all_own_funds_stocks_and_reference_etfs(self):
        catalog = instrument_catalog()
        self.assertEqual(sum(ticker.startswith("AVANZA:") for ticker in catalog), 24)
        self.assertEqual(catalog["AVANZA:41567"]["market"], "FUND")
        self.assertEqual(catalog["AAPL"]["instrument_type"], "Aktie")
        self.assertEqual(catalog["VT"]["instrument_type"], "Fond/ETF")

    def test_renaming_does_not_change_identity_prices_weights_or_capital(self):
        original, _ = self.prepared(self.targets)
        self.targets[0]["label"] = "Min långsiktiga del <valfritt namn>"
        changed, _ = self.prepared(self.targets)
        for column in ("ticker", "row_id", "value_sek", "target_weight_pct", "trade_value"):
            pd.testing.assert_series_equal(original[column], changed[column])
        self.assertIn("Min långsiktiga del <valfritt namn>", changed.name.tolist())

    def test_removing_a_held_asset_keeps_capital_and_proposes_its_sale(self):
        original, _ = self.prepared(self.targets)
        removed = self.targets.pop(0)
        changed, _ = self.prepared(self.targets)
        row = changed.loc[changed.ticker == removed["ticker"]].iloc[0]
        self.assertEqual(row.target_weight_pct, 0)
        self.assertAlmostEqual(row.trade_value, -row.value_sek)
        self.assertAlmostEqual(changed.value_sek.sum(), original.value_sek.sum())
        self.assertAlmostEqual(changed.trade_value.sum(), 0)

    def test_new_and_replacement_instruments_start_without_invented_holdings(self):
        for ticker in ("AVANZA:41567", "AAPL"):
            with self.subTest(ticker=ticker):
                targets = [dict(id="new", ticker=ticker, label="Mitt val", weight=100.)]
                portfolio, profile = self.prepared(targets)
                row = portfolio.loc[portfolio.ticker == ticker].iloc[0]
                self.assertEqual(row.value_sek, 0)
                self.assertEqual(row.current_weight_pct, 0)
                self.assertEqual(row.target_weight_pct, 100)
                self.assertAlmostEqual(row.trade_value, portfolio.value_sek.sum())
                self.assertAlmostEqual(portfolio.trade_value.sum(), 0)
                self.assertEqual(profile["target_weights"], {ticker: 100})

    def test_drafts_and_empty_target_lists_do_not_create_equal_weight_targets(self):
        draft = [dict(id="draft", ticker=None, label="Välj senare", weight=100.)]
        for targets in ([], draft):
            portfolio, profile = self.prepared(targets)
            self.assertEqual(profile["raw_weight_total"], 0)
            self.assertTrue((portfolio.target_weight_pct == 0).all())
            self.assertGreater(portfolio.value_sek.sum(), 0)

    def test_duplicate_asset_ids_are_rejected_and_duplicate_labels_are_disambiguated(self):
        duplicate = dict(self.targets[0], id="another")
        with self.assertRaises(ValueError):
            target_profile(self.targets + [duplicate], self.base, "Egen")
        self.targets[0]["label"] = self.targets[1]["label"] = "Mitt sparande"
        portfolio, _ = self.prepared(self.targets)
        self.assertTrue(portfolio.name.is_unique)
        self.assertTrue(portfolio.row_id.is_unique)

    def test_deposit_percentage_uses_the_target_after_the_same_deposit(self):
        portfolio = pd.DataFrame(dict(name=["A", "B"], value_sek=[90., 10.], target_weight=[.5, .5], trade_value=[-40., 40.]))
        deployed = pd.DataFrame(dict(cash_allocation=[0., 20.]))
        share, sellers = contribution_message(portfolio, deployed, 20.)
        self.assertAlmostEqual(share, 40.)  # 20 / (60 - 10), rather than the old 20 / 40
        self.assertEqual(sellers, ["A"])
        deployed.cash_allocation = [0., 19.]
        self.assertAlmostEqual(contribution_message(portfolio, deployed, 20.)[0], 38.)

    def test_mixed_fund_targets_do_not_invent_an_equity_fraction(self):
        ticker = next(ticker for ticker, item in instrument_catalog().items() if item["asset_type"] == "Blandfond")
        profile = target_profile([dict(ticker=ticker, label="Auto", weight=100)], self.base, "Egen")
        self.assertFalse(profile["equity_target_known"])
        self.assertTrue(np.isnan(profile["equity_target"]))


class VerifiedPriceCacheTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        override = patch.object(market_data, "PRICE_CACHE", Path(self.directory.name))
        override.start()
        self.addCleanup(override.stop)
        market_data.fetch_price_history.clear()
        self.addCleanup(market_data.fetch_price_history.clear)
        self.prices = pd.DataFrame({"VT": [100., 102., 101.]}, index=pd.bdate_range("2026-01-02", periods=3))

    def test_real_history_can_be_reused_after_provider_failure(self):
        raw = pd.concat({"Close": self.prices}, axis=1)
        with patch.object(market_data.yf, "download", return_value=raw):
            first = market_data.fetch_price_history(("VT",), mode="Marknadsdata")
        self.assertFalse(first.attrs["cached"])
        market_data.fetch_price_history.clear()
        with patch.object(market_data.yf, "download", side_effect=ConnectionError("offline")), patch.object(market_data, "make_example_history") as synthetic:
            cached = market_data.fetch_price_history(("VT",), mode="Marknadsdata")
        self.assertTrue(cached.attrs["cached"])
        self.assertFalse(cached.attrs["is_example"])
        self.assertEqual(cached.attrs["source"], "Yahoo Finance")
        np.testing.assert_allclose(cached.VT, first.VT)
        synthetic.assert_not_called()

    def test_missing_corrupt_and_synthetic_cache_are_never_used_as_real_history(self):
        path = market_data._cache_path("VT", "5y")
        for payload in ("invalid json", "[]", json.dumps(dict(version=1, ticker="VT", period="5y", is_example=True, source="Yahoo Finance", prices=self.prices.to_json(orient="split")))):
            path.parent.mkdir(exist_ok=True)
            path.write_text(payload, encoding="utf-8")
            market_data.fetch_price_history.clear()
            with patch.object(market_data.yf, "download", side_effect=ConnectionError("offline")), patch.object(market_data, "make_example_history") as synthetic:
                with self.assertRaises(market_data.PriceDataError):
                    market_data.fetch_price_history(("VT",), mode="Marknadsdata")
            synthetic.assert_not_called()

    def test_cached_nav_keeps_its_actual_end_date_and_observation_count(self):
        raw = pd.DataFrame({"AVANZA:41567": [100., 101., np.nan], "USDSEK=X": [10., 10.1, 10.2]}, index=pd.bdate_range("2026-01-02", periods=3))
        market_data._save_real_prices(raw, tuple(raw.columns), "5y")
        cached = market_data._load_real_prices(tuple(raw.columns), "5y")
        self.assertEqual(cached.attrs["actual_last_dates"]["AVANZA:41567"], str(raw.index[1].date()))
        self.assertEqual(cached.attrs["actual_observations"]["AVANZA:41567"], 2)
        self.assertIsNone(market_data._load_real_prices(("VT",), "5y"))

    def test_incomplete_cached_portfolios_do_not_get_synthetic_missing_assets(self):
        market_data._save_real_prices(self.prices, ("VT",), "5y")
        with patch.object(market_data.yf, "download", side_effect=ConnectionError("offline")), patch.object(market_data, "make_example_history") as synthetic:
            with self.assertRaises(market_data.PriceDataError):
                market_data.fetch_price_history(("VT", "AAPL"), mode="Marknadsdata")
        synthetic.assert_not_called()
