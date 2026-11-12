from pathlib import Path
import sys
import unittest
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from optimization_model import (Formula, curve_factory, curve_metrics, optimize_portfolio, project_weights,
                                OBJECTIVES, MODES, weight_condition_bounds)
from account_model import demo_accounts, parse_holdings_csv, preview_orders
from cost_model import Settings
from engine import simulate_historical_rebalanced_values, prepare_portfolio, calculate_metrics
from risk_model import compute_risk_metrics
from data import build_live_portfolio_values
from portfolio_model import build_portfolio_template, target_profile


def prices_for_search(periods=520):
    rng = np.random.default_rng(123)
    common = rng.normal(.0003, .008, periods)
    returns = np.stack([common + rng.normal(.0003, .004, periods), -.2 * common + rng.normal(.0002, .005, periods),
                        .4 * common + rng.normal(.0001, .006, periods)], axis=1)
    return pd.DataFrame(100 * np.cumprod(1 + returns, axis=0),
                        index=pd.bdate_range("2023-01-02", periods=periods), columns=["A", "B", "C"])


class ObjectiveAndSolverTests(unittest.TestCase):
    def test_curve_matches_existing_strategy_engine_for_each_rebalance_rule(self):
        prices = prices_for_search(300)
        weights = np.array([.5, .3, .2])
        for mode in MODES:
            with self.subTest(mode=mode):
                expected, _, _ = simulate_historical_rebalanced_values(prices, pd.Series(weights, index=prices.columns), mode)
                np.testing.assert_allclose(curve_factory(prices, mode)(weights), expected, atol=1e-12)

    def test_cagr_is_geometric_and_drawdown_includes_the_initial_value(self):
        dates = pd.to_datetime(["2023-01-01", "2024-01-01", "2025-01-01"])
        metrics = curve_metrics([100., 80., 121.], dates)
        self.assertAlmostEqual(metrics["CAGR"], ((121 / 100) ** (365.25 / 731) - 1) * 100)
        self.assertAlmostEqual(metrics["MaxDrawdown"], 20.)
        self.assertAlmostEqual(metrics["Utveckling"], 21.)

    def test_sortino_uses_lower_partial_deviation_over_all_observations(self):
        r = np.tile([.01, -.02], 30)
        values = np.r_[100., 100 * np.cumprod(1 + r)]
        metrics = curve_metrics(values, pd.bdate_range("2024-01-02", periods=len(values)), target_pct=0)
        expected = r.mean() / np.sqrt(np.mean(np.minimum(r, 0) ** 2)) * np.sqrt(252)
        self.assertAlmostEqual(metrics["Sortino"], expected)
        positive = np.r_[100., 100 * np.cumprod(1 + np.linspace(.001, .01, 60))]
        self.assertTrue(np.isnan(curve_metrics(positive, pd.bdate_range("2024-01-02", periods=len(positive)))["Sortino"]))

    def test_formula_supports_only_bounded_arithmetic_and_named_metrics(self):
        metrics = {"CAGR": 8., "MaxDrawdown": 20., "Sharpe": .8, "Sortino": 1.2, "Volatilitet": 10.}
        self.assertEqual(Formula("CAGR - 0.5 * MaxDrawdown").evaluate(metrics), -2.)
        self.assertAlmostEqual(Formula("(sharpe + Sortino) / 2").evaluate(metrics), 1.)
        for expression in ("__import__('os')", "Sharpe.real", "[CAGR][0]", "2 ** 100000", "True", "1e309", "sum([CAGR])", "1 + 2"):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                Formula(expression)
        with self.assertRaises(ValueError):
            Formula("CAGR / (Sharpe - Sharpe)").evaluate(metrics)

    def test_projection_respects_bounds_and_rejects_infeasible_constraints(self):
        weights = project_weights([.8, .1, .1], [.2, .2, .2], [.4, .5, .5])
        self.assertAlmostEqual(weights.sum(), 1.)
        self.assertTrue((weights >= [.2, .2, .2]).all())
        self.assertTrue((weights <= [.4, .5, .5]).all())
        for lower, upper in (([.6, .6], [1, 1]), ([0, 0], [.2, .2]), ([.4, 0], [.3, 1])):
            with self.assertRaises(ValueError):
                project_weights([.5, .5], lower, upper)

    def test_every_objective_obeys_locked_weights_and_caps(self):
        prices = prices_for_search()
        for objective in OBJECTIVES:
            with self.subTest(objective=objective):
                result = optimize_portfolio(prices, [.2, 0, 0], [.2, .6, .6], objective=objective,
                    formula="CAGR - 0.5 * MaxDrawdown", mode=MODES[1], starts=3)
                self.assertAlmostEqual(result["weights"].sum(), 1., places=8)
                self.assertAlmostEqual(result["weights"][0], .2, places=8)
                self.assertTrue((result["weights"] <= np.array([.2, .6, .6]) + 1e-8).all())

    def test_min_exact_max_are_inclusive_and_leave_other_weights_free(self):
        lower, upper = weight_condition_bounds(["min", "=", "max"], [20, 25, 55])
        np.testing.assert_allclose(lower, [.2, .25, 0])
        np.testing.assert_allclose(upper, [1, .25, .55])
        for vector in ([.2, .25, .55], [.75, .25, 0]):
            np.testing.assert_allclose(project_weights(vector, lower, upper), vector, atol=1e-9)
        lower, upper = weight_condition_bounds(["max", "max"], [100, 100])
        np.testing.assert_array_equal(lower, [0, 0])
        np.testing.assert_array_equal(upper, [1, 1])

    def test_weight_conditions_reject_invalid_values_and_impossible_totals(self):
        for conditions, values in ((["min"], [np.nan]), (["max"], [np.inf]), (["="], [-1]),
                (["min"], [101]), (["other"], [20]), (["min"], [None]), (["min"], []), ([], [])):
            with self.subTest(conditions=conditions, values=values), self.assertRaises(ValueError):
                weight_condition_bounds(conditions, values)
        for conditions, values in ((["min", "min"], [60, 60]), (["max", "max"], [40, 40]),
                                    (["=", "min"], [70, 40])):
            lower, upper = weight_condition_bounds(conditions, values)
            with self.subTest(conditions=conditions, values=values), self.assertRaisesRegex(ValueError, "går inte ihop"):
                project_weights([.5, .5], lower, upper)

    def test_portfolio_sharpe_uses_diversification_rather_than_the_best_single_instrument(self):
        rng = np.random.default_rng(98)
        factor = rng.normal(0., .009, 520)
        returns = np.stack([.0005 + factor + rng.normal(0., .002, 520),
                            .0004 - .8 * factor + rng.normal(0., .002, 520)], axis=1)
        prices = pd.DataFrame(100 * np.cumprod(1 + returns, axis=0),
            index=pd.bdate_range("2023-01-02", periods=520), columns=["A", "B"])
        lower, upper = weight_condition_bounds(["min", "max"], [20, 80])
        result = optimize_portfolio(prices, lower, upper, mode=MODES[1])
        train_curve = curve_factory(result["train"], MODES[1])
        singles = [curve_metrics(train_curve(weights), result["train"].index)["Sharpe"]
                   for weights in ([1., 0.], [0., 1.])]
        self.assertTrue((result["weights"] > .2).all())
        self.assertTrue((result["weights"] < .8).all())
        self.assertGreater(result["score"], max(singles) + .5)

    def test_validation_prices_do_not_change_optimized_weights(self):
        prices = prices_for_search()
        first = optimize_portfolio(prices, [0, 0, 0], [1, 1, 1], starts=3)
        changed = prices.copy()
        start = len(first["train"])
        changed.iloc[start:, 0] *= np.linspace(1., 4., len(changed) - start)
        second = optimize_portfolio(changed, [0, 0, 0], [1, 1, 1], starts=3)
        np.testing.assert_allclose(first["weights"], second["weights"], atol=1e-10)
        self.assertEqual(first["train"].index[-1], first["validation"].index[0])
        self.assertEqual(len(first["train"]) + len(first["validation"]) - 2, len(prices) - 1)

    def test_sharpe_search_is_not_worse_than_a_dense_feasible_grid(self):
        prices = prices_for_search()[["A", "B"]]
        result = optimize_portfolio(prices, [0, 0], [1, 1], starts=5)
        train = result["train"]
        score = max(curve_metrics(curve_factory(train, MODES[0])([weight, 1 - weight]), train.index)["Sharpe"]
                    for weight in np.linspace(0, 1, 301))
        self.assertGreaterEqual(result["score"] + 1e-5, score)

    def test_short_history_and_undefined_sharpe_fail_explicitly(self):
        with self.assertRaisesRegex(ValueError, "252"):
            optimize_portfolio(prices_for_search(100), [0, 0, 0], [1, 1, 1])
        flat = prices_for_search() * 0 + 100
        with self.assertRaisesRegex(ValueError, "definierat"):
            optimize_portfolio(flat, [0, 0, 0], [1, 1, 1], starts=2)


class AccountAdapterTests(unittest.TestCase):
    def test_demo_accounts_have_real_instrument_identities_and_distinct_types(self):
        accounts = demo_accounts()
        self.assertEqual(accounts["demo_isk"]["account"], "ISK")
        self.assertEqual(accounts["demo_af"]["account"], "AF")
        self.assertNotEqual(accounts["demo_isk"]["holdings"], accounts["demo_af"]["holdings"])

    def test_csv_accepts_swedish_numbers_and_merges_duplicate_positions(self):
        content = "instrument;antal;omkostnadsbelopp\nINVE-B.ST;10,5;1000\nINVE-B.ST;2,5;300\n"
        account = parse_holdings_csv(content, account="AF", cash=500)
        self.assertEqual(account["holdings"][0]["units"], 13.)
        self.assertEqual(account["holdings"][0]["cost_basis_sek"], 1300.)
        self.assertEqual(account["cash"], 500.)

    def test_unknown_instruments_negative_units_and_missing_columns_are_rejected(self):
        for content in ("instrument;antal\nUNKNOWN;1\n", "instrument;antal\nINVE-B.ST;-1\n", "instrument;belopp\nINVE-B.ST;1\n"):
            with self.assertRaises(ValueError):
                parse_holdings_csv(content)

    def portfolio(self, missing_basis=False):
        account = parse_holdings_csv("instrument;antal;omkostnadsbelopp\nINVE-B.ST;10;500\nVOLV-B.ST;10;500\n", account="AF")
        if missing_basis:
            account["holdings"][0]["cost_basis_sek"] = np.nan
        targets = [dict(id="a", ticker="INVE-B.ST", label="Investor", weight=20.), dict(id="b", ticker="VOLV-B.ST", label="Volvo", weight=80.)]
        template = build_portfolio_template(account["holdings"], targets)
        dates = pd.bdate_range("2026-01-02", periods=30)
        prices = pd.DataFrame({"INVE-B.ST": np.full(30, 100.), "VOLV-B.ST": np.full(30, 100.)}, index=dates)
        portfolio = build_live_portfolio_values(template, prices)
        return prepare_portfolio(portfolio, target_profile(targets, {}, "Egen")), prices

    def test_order_plan_is_cash_funded_and_does_not_change_the_holdings(self):
        portfolio, prices = self.portfolio()
        before = portfolio.value_sek.copy()
        result = preview_orders(portfolio, prices, Settings(account="AF"), cash=200.)
        self.assertAlmostEqual(result["after_total"] + result["fees"], result["before_total"], places=6)
        self.assertGreaterEqual(result["cash"], -1e-6)
        self.assertGreater(result["tax"], 0.)
        pd.testing.assert_series_equal(portfolio.value_sek, before)

    def test_no_sales_and_reserved_cash_only_use_the_new_deposit(self):
        portfolio, prices = self.portfolio()
        result = preview_orders(portfolio, prices, Settings(account="AF"), cash=200., new_deposit=100.,
                                allow_sales=False, use_cash=False)
        self.assertFalse((result["orders"]["Åtgärd"] == "Sälj").any())
        buys = result["orders"].loc[result["orders"]["Åtgärd"] == "Köp", "Modellbelopp"].sum()
        self.assertLessEqual(buys + result["fees"], 100. + 1e-6)
        self.assertGreaterEqual(result["cash"], 200. - 1e-6)

    def test_missing_af_basis_is_unknown_rather_than_a_zero_tax_claim(self):
        portfolio, prices = self.portfolio(missing_basis=True)
        result = preview_orders(portfolio, prices, Settings(account="AF"))
        self.assertIsNone(result["tax"])
        self.assertFalse(result["tax_known"])

    def test_cash_targets_keep_the_full_weight_vector_and_reserve_the_cash(self):
        portfolio, prices = self.portfolio()
        profile = target_profile([dict(ticker="INVE-B.ST", weight=40.), dict(ticker="VOLV-B.ST", weight=40.)], {}, "Egen", cash_target_pct=20.)
        self.assertAlmostEqual(sum(profile["target_weights"].values()), 80.)
        portfolio["target_weight"] = portfolio.ticker.map(profile["target_weights"]) / 100
        portfolio["target_weight_pct"] = portfolio["target_weight"] * 100
        result = preview_orders(portfolio, prices, Settings(account="ISK", include_costs=False), cash=200.)
        self.assertAlmostEqual(result["cash"], 440.)
        self.assertAlmostEqual(result["after_total"], 2200.)
        self.assertAlmostEqual(result["after"].sum(), 1760.)

    def test_nominal_cash_does_not_count_as_a_market_order(self):
        from cost_model import price_inputs, historical_inputs, simulate_paths
        dates = pd.bdate_range("2026-01-02", periods=30)
        raw = pd.DataFrame({"INVE-B.ST": np.linspace(100, 105, 30), "__cash__": np.ones(30)}, index=dates)
        universe = pd.DataFrame([dict(ticker="INVE-B.ST", company_name="Investor", currency="SEK", instrument_type="Aktie", market="SE"),
                                  dict(ticker="__cash__", company_name="Likvid", currency="SEK", instrument_type="Likvid", market="FUND")])
        settings = Settings(include_costs=False, include_tax=False, liquidate=False)
        sek, fx, terms = price_inputs(universe, raw, settings)
        result = simulate_paths(**historical_inputs(sek, fx), terms=terms, weights=[.5, .5], amount=1000., mode=MODES[0], settings=settings, record=True)
        self.assertEqual(result["orders"][0], 1)
        self.assertNotIn("__cash__", result["ledger"].Ticker.tolist())
        self.assertAlmostEqual(result["history"]["gross"][-1, 0], 1025.)

    def test_cash_is_in_account_weights_and_risk_with_zero_assumed_return(self):
        prices = prices_for_search(300)[["A"]]
        assets, all_stock = compute_risk_metrics(prices, {"A": 100.}, 2.)
        _, half_cash = compute_risk_metrics(prices, {"A": 100.}, 2., cash_value=100.)
        self.assertAlmostEqual(half_cash["annual_volatility_pct"], all_stock["annual_volatility_pct"] / 2)
        self.assertAlmostEqual(half_cash["annual_return_pct"], all_stock["annual_return_pct"] / 2)
        portfolio = pd.DataFrame([dict(name="A", ticker="A", category="A", row_id="A", value_sek=100., last_review_value_sek=100., asset_type="Aktiefond", risk_level=5.)])
        portfolio.attrs["cash_value"] = 100.
        profile = dict(target_weights={"A": 100.}, equity_target=100.)
        prepared = prepare_portfolio(portfolio, profile, assets)
        metrics = calculate_metrics(prepared, profile, half_cash)
        self.assertAlmostEqual(prepared.current_weight_pct.iloc[0], 50.)
        self.assertEqual(metrics["total_value"], 200.)
        self.assertEqual(metrics["equity_exposure"], 50.)
