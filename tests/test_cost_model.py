from pathlib import Path
import sys
import unittest
from dataclasses import replace
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cost_model import (
    Settings, MODES, MARKETS, COMPONENTS, tax_rule, af_capital_tax,
    order_costs, cost_total, buy_with_budget, simulate_paths, StartOrderWindow,
    historical_inputs, price_inputs, bootstrap_inputs, audit_rows,
)
from engine import simulate_historical_rebalanced_values


def term(ticker="A", market="SE", fund=False, interest=False):
    return dict(ticker=ticker, name=ticker, currency=MARKETS[market][1], market=market,
                fund=fund, interest_fund=interest, spread=0., annual_extra=0.,
                dividend_yield=0., withholding=0., buy_tax=0., fixed_extra=0.)


def simulate_flat(start="2026-01-02", end="2026-12-31", amount=100000., terms=None, settings=None, growth=0., mode=MODES[0]):
    terms = terms or [term()]
    settings = settings or Settings(include_costs=False, allowance_used_elsewhere=300000)
    dates = pd.bdate_range(start, end)
    prices = pd.DataFrame({t["ticker"]: np.linspace(100, 100 * (1 + growth), len(dates)) for t in terms}, index=dates)
    fx = prices * 0 + 1
    return simulate_paths(**historical_inputs(prices, fx), terms=terms,
                          weights=np.ones(len(terms)), amount=amount, mode=mode, settings=settings, record=True)


class BrokerageTests(unittest.TestCase):
    def fee(self, amount, cls="Mini", market="SE", fund=False, **kwargs):
        settings = Settings(brokerage_class=cls, **kwargs)
        return order_costs([[amount]], [[10. if market == "US" else 1.]], [term(market=market, fund=fund)], settings, "Köp")

    def test_swedish_classes(self):
        self.assertEqual(self.fee(100)["courtage"][0, 0], 1)
        self.assertEqual(self.fee(10000)["courtage"][0, 0], 25)
        self.assertEqual(self.fee(10000, "Small")["courtage"][0, 0], 39)
        self.assertEqual(self.fee(100000, "Medium")["courtage"][0, 0], 69)
        self.assertEqual(self.fee(1000000, "Fast Pris")["courtage"][0, 0], 99)

    def test_fast_price_etf_is_not_flat_99(self):
        self.assertEqual(self.fee(1000000, "Fast Pris", "SE_ETF", True)["courtage"][0, 0], 450)

    def test_usa_minimum_is_converted_from_usd(self):
        self.assertEqual(self.fee(100, "Small", "US")["courtage"][0, 0], 60)
        self.assertEqual(self.fee(100, "Medium", "US")["courtage"][0, 0], 80)
        self.assertEqual(self.fee(1000000, "Fast Pris", "US")["courtage"][0, 0], 790)

    def test_zero_order_costs_nothing(self):
        self.assertEqual(float(cost_total(self.fee(0, "Fast Pris", "US")).sum()), 0.)

    def test_fx_is_per_direction_on_cash_including_commission(self):
        settings = Settings()
        buy = order_costs([[10000]], [[10]], [term(market="US")], settings, "Köp")
        sell = order_costs([[10000]], [[10]], [term(market="US")], settings, "Sälj")
        self.assertAlmostEqual(buy["fx"][0, 0], 10025 * .0025)
        self.assertAlmostEqual(sell["fx"][0, 0], 9975 * .0025)

    def test_full_bid_ask_spread_is_halved_per_trade(self):
        t = term()
        t["spread"] = .002
        parts = order_costs([[10000]], [[1]], [t], Settings(), "Sälj")
        self.assertAlmostEqual(parts["spread"][0, 0], 10)

    def test_start_is_not_free_for_first_north_or_etfs(self):
        self.assertEqual(self.fee(10000, "Start", start_eligible=True)["courtage"][0, 0], 0)
        self.assertEqual(self.fee(10000, "Start", "SE_FN", start_eligible=True)["courtage"][0, 0], 25)
        self.assertEqual(self.fee(10000, "Start", "SE_ETF", True, start_eligible=True)["courtage"][0, 0], 25)
        self.assertEqual(self.fee(10000, "Start", "US", start_eligible=True)["courtage"][0, 0], 25)

    def test_last_free_start_order_is_not_duplicated_across_instruments(self):
        settings = Settings(brokerage_class="Start", start_eligible=True, previous_free_order_history=(("2025-12-01", 499),))
        parts = order_costs([[10000, 10000]], [[1, 1]], [term("A"), term("B")], settings, "Köp",
                            StartOrderWindow(settings, "2026-01-02", 20000).permission("2026-01-02"))
        np.testing.assert_allclose(parts["courtage"], [[0, 25]])

    def test_start_switches_to_mini_at_50000(self):
        settings = Settings(brokerage_class="Start", start_eligible=True, include_tax=False)
        result = simulate_flat(amount=50000, settings=settings)
        self.assertGreater(result["components"]["courtage"][0], 200)
        self.assertFalse(result["start_remaining"][0])

    def test_start_switches_to_mini_when_growth_reaches_limit(self):
        settings = Settings(brokerage_class="Start", start_eligible=True, include_tax=False)
        result = simulate_flat(amount=49000, growth=.1, settings=settings)
        self.assertFalse(result["start_remaining"][0])
        self.assertGreater(result["components"]["courtage"][0], 100)

    def test_standard_fund_has_no_online_brokerage(self):
        self.assertEqual(self.fee(100000, "Fast Pris", "FUND", True)["courtage"][0, 0], 0)

    def test_cash_budget_includes_all_buying_costs(self):
        terms = [term("A", "US"), term("B", "US")]
        amount, parts, cash = buy_with_budget(np.array([10000.]), [.5, .5], [[10, 10]], terms, Settings())
        self.assertAlmostEqual(amount.sum() + cost_total(parts).sum() + cash.sum(), 10000, places=6)
        self.assertGreaterEqual(cash[0], 0)
        self.assertLess(amount.sum(), 10000)

    def test_unfundable_orders_do_not_create_capital(self):
        terms = [term("A", "US"), term("B", "US"), term("C", "US")]
        amount, parts, cash = buy_with_budget(np.array([20.]), [1, 1, 1], [[10, 10, 10]], terms, Settings())
        self.assertLessEqual(np.count_nonzero(amount), 1)
        self.assertAlmostEqual(amount.sum() + cost_total(parts).sum() + cash.sum(), 20, places=6)


class TaxTests(unittest.TestCase):
    def test_2026_rate_and_shared_allowance(self):
        rate, allowance, assumed = tax_rule(2026, Settings(allowance_used_elsewhere=200000))
        self.assertAlmostEqual(rate, .01065)
        self.assertEqual(allowance, 100000)
        self.assertFalse(assumed)

    def test_2025_and_2024_are_not_given_2026_exemption(self):
        self.assertEqual(tax_rule(2025, Settings())[1], 150000)
        self.assertEqual(tax_rule(2024, Settings())[1], 0)
        self.assertAlmostEqual(tax_rule(2024, Settings())[0], .01086)

    def test_future_rate_is_an_explicit_assumption(self):
        self.assertEqual(tax_rule(2027, Settings(future_isk_rate=.012))[0], .012)
        self.assertTrue(tax_rule(2027, Settings())[2])

    def test_full_year_quarter_capital_base_and_deposit(self):
        result = simulate_flat()
        self.assertAlmostEqual(result["annual"][2026]["capital_base"][0], 100000)
        self.assertAlmostEqual(result["tax_isk"][0], 1065)

    def test_late_deposit_is_not_charged_one_full_year(self):
        result = simulate_flat(start="2026-12-01", end="2026-12-31")
        self.assertAlmostEqual(result["annual"][2026]["capital_base"][0], 25000)
        self.assertAlmostEqual(result["tax_isk"][0], 266.25)

    def test_isk_exemption_can_cover_the_entire_scenario(self):
        result = simulate_flat(amount=100000, settings=Settings(include_costs=False))
        self.assertEqual(result["tax_isk"][0], 0)

    def test_isk_can_be_due_even_when_market_falls(self):
        result = simulate_flat(growth=-.2)
        self.assertGreater(result["tax_isk"][0], 0)

    def test_af_gains_are_taxed_at_30_percent(self):
        result = simulate_flat(growth=.1)
        self.assertAlmostEqual(result["tax_af"][0], 3000, places=6)

    def test_unrealized_af_gains_are_not_silently_taxed(self):
        result = simulate_flat(growth=.1, settings=Settings(include_costs=False, liquidate=False))
        self.assertAlmostEqual(result["tax_af"][0], 0)
        self.assertAlmostEqual(result["latent_gain"][0], 10000, places=6)

    def test_af_fund_tax_uses_actual_january_opening_not_start_amount(self):
        result = simulate_flat(start="2025-12-30", end="2026-01-05", terms=[term(fund=True)])
        self.assertAlmostEqual(result["annual"][2025]["fund_opening"][0], 0)
        self.assertAlmostEqual(result["annual"][2026]["fund_opening"][0], 100000)
        self.assertAlmostEqual(result["tax_af"][0], 120)

    def test_stock_has_no_fund_schablon_tax(self):
        result = simulate_flat(start="2025-12-30", end="2026-01-05")
        self.assertEqual(result["tax_af"][0], 0)

    def test_unusable_loss_credit_is_not_a_promised_refund(self):
        self.assertEqual(float(af_capital_tax(-10000)), 0)
        self.assertAlmostEqual(float(af_capital_tax(-10000, loss_credit=True)), -2100)

    def test_capital_deficit_uses_30_then_21_percent(self):
        self.assertAlmostEqual(float(af_capital_tax(-200000, loss_credit=True)), -(30000 + .21 * 40000))

    def test_interest_fund_losses_are_not_70_percent_equity_losses(self):
        self.assertAlmostEqual(float(af_capital_tax(0, interest_net=-10000, loss_credit=True)), -3000)

    def test_same_year_netting_and_loss_offset_against_dividends(self):
        self.assertAlmostEqual(float(af_capital_tax(1000, dividends=200)), 360)
        self.assertAlmostEqual(float(af_capital_tax(-1000, dividends=1000)), 90)

    def test_estimated_distribution_is_not_added_to_return_again(self):
        t = term()
        t["dividend_yield"] = .02
        result = simulate_flat(growth=.1, terms=[t])
        # Gross gain stays 10,000; assumed dividend enters cost basis once.
        self.assertAlmostEqual(result["history"]["gross"][-1, 0], 110000, places=6)
        self.assertAlmostEqual(result["tax_af"][0], 3000, places=6)


class SimulationIntegrityTests(unittest.TestCase):
    def test_no_cost_or_tax_matches_the_existing_mathematical_engine(self):
        dates = pd.bdate_range("2025-01-02", "2026-02-05")
        rng = np.random.default_rng(4)
        prices = pd.DataFrame(100 * np.cumprod(1 + rng.normal(.0003, .008, (len(dates), 2)), axis=0), index=dates, columns=["A", "B"])
        for mode in MODES:
            with self.subTest(mode=mode):
                expected, _, _ = simulate_historical_rebalanced_values(prices, pd.Series({"A": 6000., "B": 4000.}), mode)
                result = simulate_paths(**historical_inputs(prices, prices * 0 + 1), terms=[term("A"), term("B")], weights=[.6, .4], amount=10000,
                                        mode=mode, settings=Settings(include_costs=False, include_tax=False))
                np.testing.assert_allclose(result["history"]["after_costs"][:, 0], expected.to_numpy(), atol=.00001)

    def test_fee_and_tax_toggles_are_independent(self):
        for costs in [False, True]:
            for tax in [False, True]:
                with self.subTest(costs=costs, tax=tax):
                    result = simulate_flat(growth=.1, settings=Settings(include_costs=costs, include_tax=tax, allowance_used_elsewhere=300000))
                    if not costs:
                        self.assertEqual(sum(v[0] for v in result["components"].values()), 0)
                    if not tax:
                        np.testing.assert_array_equal(result["history"]["isk"], result["history"]["after_costs"])
                        np.testing.assert_array_equal(result["history"]["af"], result["history"]["after_costs"])

    def test_audit_adds_up_to_net_value(self):
        result = simulate_flat(growth=.1, settings=Settings(allowance_used_elsewhere=300000))
        for account in ["ISK", "AF"]:
            rows = audit_rows(result, account)
            self.assertAlmostEqual(sum(value for _, value in rows[:-1]), rows[-1][1], places=7)

    def test_round_trip_fees_are_in_af_basis_and_sale_proceeds(self):
        result = simulate_flat(start="2026-02-01", end="2026-02-10", amount=10000, settings=Settings())
        fees = sum(v[0] for v in result["components"].values())
        self.assertAlmostEqual(result["annual"][2026]["equity_gains"][0], -fees, places=5)
        self.assertAlmostEqual(result["history"]["after_costs"][-1, 0], 10000 - fees, places=5)

    def test_foreign_returns_are_really_sek_returns(self):
        dates = pd.bdate_range("2026-01-02", periods=3)
        prices = pd.DataFrame({"A": [100, 100, 100], "USDSEK=X": [10, 10.5, 11]}, index=dates)
        universe = pd.DataFrame([dict(ticker="A", company_name="A", instrument_type="Aktie")])
        settings = Settings(include_costs=False, include_tax=True)
        sek, fx, terms = price_inputs(universe, prices, settings)
        result = simulate_paths(**historical_inputs(sek, fx), terms=terms, weights=[1], amount=10000, mode=MODES[0], settings=settings)
        self.assertAlmostEqual(result["history"]["gross"][-1, 0], 11000)
        self.assertAlmostEqual(result["tax_af"][0], 300)

    def test_no_fabricated_exchange_rate(self):
        dates = pd.bdate_range("2026-01-02", periods=3)
        universe = pd.DataFrame([dict(ticker="A", company_name="A", instrument_type="Aktie")])
        with self.assertRaisesRegex(ValueError, "Valutakurs saknas"):
            price_inputs(universe, pd.DataFrame({"A": [100, 101, 102]}, index=dates), Settings())

    def test_monte_carlo_is_repeatable_and_audit_path_replays_exactly(self):
        dates = pd.bdate_range("2026-01-02", periods=90)
        rng = np.random.default_rng(12)
        prices = pd.DataFrame(100 * np.cumprod(1 + rng.normal(.0002, .01, (90, 2)), axis=0), index=dates, columns=["A", "B"])
        fx = prices * 0 + 1
        inputs = bootstrap_inputs(prices, fx, dates[-1] + pd.DateOffset(months=3), paths=30)
        second = bootstrap_inputs(prices, fx, dates[-1] + pd.DateOffset(months=3), paths=30)
        np.testing.assert_array_equal(inputs["returns"], second["returns"])
        result = simulate_paths(**inputs, terms=[term("A"), term("B")], weights=[.5, .5], amount=10000, mode=MODES[1], settings=Settings())
        sliced = dict(inputs, returns=inputs["returns"][:, 7:8], fx_returns=inputs["fx_returns"][:, 7:8])
        replay = simulate_paths(**sliced, terms=[term("A"), term("B")], weights=[.5, .5], amount=10000, mode=MODES[1], settings=Settings(), record=True)
        for key in result["history"]:
            np.testing.assert_allclose(result["history"][key][:, 7], replay["history"][key][:, 0], atol=.00001)

    def test_multiple_rebalances_have_matching_order_and_cost_ledgers(self):
        result = simulate_flat(start="2025-01-02", end="2026-01-05", amount=100000, terms=[term("A"), term("B")], mode=MODES[1], settings=Settings())
        self.assertEqual(result["orders"][0], len(result["ledger"]))
        for component, column in [("courtage", "Courtage"), ("fx", "Växling"), ("spread", "Spread"), ("other", "Övrigt")]:
            self.assertAlmostEqual(result["components"][component][0], result["ledger"][column].sum(), places=5)

    def test_real_rebalances_are_cash_funded_and_the_ledger_reconciles(self):
        dates = pd.bdate_range("2025-01-02", "2025-06-30")
        prices = pd.DataFrame({"A": np.linspace(100, 180, len(dates)), "B": np.linspace(100, 80, len(dates))}, index=dates)
        result = simulate_paths(**historical_inputs(prices, prices * 0 + 1), terms=[term("A"), term("B")],
                                weights=[.5, .5], amount=100000, mode=MODES[1], settings=Settings(), record=True)
        self.assertGreater(len(result["ledger"]), 10)
        cash = 100000.
        for row in result["ledger"].to_dict("records"):
            fees = sum(row[key] for key in ["Courtage", "Växling", "Spread", "Övrigt"])
            cash += (row["Orderbelopp"] - fees) if row["Åtgärd"] == "Sälj" else -(row["Orderbelopp"] + fees)
            self.assertGreaterEqual(cash, -.0001)
        self.assertAlmostEqual(cash, result["cash"][0], places=5)
        self.assertAlmostEqual(result["ledger"]["Vinst_AF"].sum(), result["annual"][2025]["equity_gains"][0], places=5)
        np.testing.assert_allclose(result["final_basis"], 0, atol=.00001)

    def test_invalid_cost_assumptions_and_weights_are_rejected(self):
        t = term()
        t["spread"] = np.nan
        with self.assertRaisesRegex(ValueError, "avgiftsantagandena"):
            simulate_flat(terms=[t])
        dates = pd.bdate_range("2026-01-02", periods=3)
        p = pd.DataFrame({"A": [100., 101., 102.]}, index=dates)
        with self.assertRaisesRegex(ValueError, "målvikt"):
            simulate_paths(**historical_inputs(p, p * 0 + 1), terms=[term()], weights=[np.nan], amount=1000, mode=MODES[0], settings=Settings())



class AfSaleValuationTests(unittest.TestCase):
    def test_every_date_reserves_profit_tax_without_selling_the_holdings(self):
        dates = pd.bdate_range("2026-01-05", periods=3)
        prices = pd.DataFrame({"A": [100., 110., 120.]}, index=dates)
        result = simulate_paths(**historical_inputs(prices, prices * 0 + 1), terms=[term()], weights=[1], amount=100000,
                                mode=MODES[0], settings=Settings(include_costs=False, liquidate=False), record=True)
        np.testing.assert_allclose(result["history"]["af"][:, 0], [100000, 107000, 114000])
        np.testing.assert_allclose(result["history"]["af_tax_realized"], 0)
        self.assertAlmostEqual(result["history"]["af_tax_if_sold"][-1, 0], 6000)
        self.assertEqual(list(result["ledger"].Åtgärd), ["Köp"])
        self.assertAlmostEqual(result["final_values"].sum(), 120000)
        self.assertAlmostEqual(result["final_basis"].sum(), 100000)

    def test_each_valuation_matches_a_real_exit_on_that_date_including_fees(self):
        dates = pd.to_datetime(["2025-12-29", "2025-12-30", "2026-01-02", "2026-01-05", "2026-02-03"])
        prices = pd.DataFrame({"A": [100, 110, 130, 90, 120], "B": [100, 95, 120, 105, 115]}, index=dates)
        fx = pd.DataFrame({"A": [10, 10.2, 10.1, 10.3, 10.4], "B": [1.] * len(dates)}, index=dates)
        a, b = term("A", "US", fund=True), term("B")
        a.update(spread=.004, dividend_yield=.03, withholding=.05)
        settings = Settings(brokerage_class="Small", liquidate=False)
        result = simulate_paths(**historical_inputs(prices, fx), terms=[a, b], weights=[.6, .4], amount=100000,
                                mode=MODES[0], settings=settings)
        for i in range(1, len(dates)):
            exited = simulate_paths(**historical_inputs(prices.iloc[:i + 1], fx.iloc[:i + 1]), terms=[a, b], weights=[.6, .4], amount=100000,
                                    mode=MODES[0], settings=replace(settings, liquidate=True))
            self.assertAlmostEqual(result["history"]["af_if_sold"][i, 0], exited["history"]["af"][-1, 0], places=6)
            self.assertAlmostEqual(result["history"]["af_tax_if_sold"][i, 0], exited["tax_af"][0], places=6)

    def test_loss_offsets_current_year_gains_without_refunding_past_year_tax(self):
        # A doubles and is trimmed in December; its remaining value then falls.
        dates = pd.to_datetime(["2025-12-29", "2025-12-31", "2026-01-02", "2026-01-05"])
        prices = pd.DataFrame({"A": [100, 200, 50, 50], "B": [100, 100, 100, 100]}, index=dates)
        result = simulate_paths(**historical_inputs(prices, prices * 0 + 1), terms=[term("A"), term("B")], weights=[.5, .5], amount=100000,
                                mode=MODES[1], settings=Settings(include_costs=False, liquidate=False))
        self.assertAlmostEqual(result["annual"][2025]["af"][0], 3750)
        self.assertAlmostEqual(result["history"]["af_tax_if_sold"][-1, 0], 3750)
        self.assertAlmostEqual(result["history"]["af_sale_gain"][-1, 0], -18750)

    def test_same_year_loss_reduces_already_reserved_tax(self):
        dates = pd.to_datetime(["2026-01-29", "2026-01-30", "2026-02-02", "2026-02-03"])
        prices = pd.DataFrame({"A": [100, 200, 50, 50], "B": [100, 100, 100, 100]}, index=dates)
        result = simulate_paths(**historical_inputs(prices, prices * 0 + 1), terms=[term("A"), term("B")], weights=[.5, .5], amount=100000,
                                mode=MODES[1], settings=Settings(include_costs=False, liquidate=False))
        self.assertAlmostEqual(result["history"]["af_tax_realized"][-1, 0], 3750)
        self.assertAlmostEqual(result["history"]["af_tax_if_sold"][-1, 0], 0)
        self.assertGreater(result["history"]["af_if_sold"][-1, 0], result["history"]["af_realized"][-1, 0])

    def test_actual_terminal_sale_is_not_taxed_or_charged_twice(self):
        result = simulate_flat(growth=.2, settings=Settings(liquidate=True))
        self.assertAlmostEqual(result["history"]["af_sale_costs"][-1, 0], 0)
        self.assertAlmostEqual(result["history"]["af_tax_if_sold"][-1, 0], result["tax_af"][0])
        self.assertAlmostEqual(result["history"]["af"][-1, 0], result["history"]["after_costs"][-1, 0] - result["tax_af"][0])

    def test_sale_valuation_does_not_consume_start_free_orders(self):
        result = simulate_flat(amount=10000, growth=.1, settings=Settings(brokerage_class="Start", start_eligible=True, previous_free_order_history=(("2025-12-01", 498),), liquidate=False))
        self.assertEqual(result["orders"][0], 1)
        self.assertTrue(result["start_remaining"][0])
        np.testing.assert_allclose(result["history"]["af_sale_costs"], 0)

    def test_realized_only_view_and_tax_toggle_preserve_the_original_curve(self):
        for tax, view in [(True, False), (False, True)]:
            result = simulate_flat(growth=.2, settings=Settings(include_costs=False, include_tax=tax, liquidate=False, af_sale_view=view))
            np.testing.assert_allclose(result["history"]["af"], result["history"]["after_costs"])
        loss = simulate_flat(growth=-.2, settings=Settings(include_costs=False, liquidate=False))
        self.assertEqual(loss["history"]["af_tax_if_sold"][-1, 0], 0)

    def test_audit_reconciles_hypothetical_sale_costs_and_additional_tax(self):
        result = simulate_flat(growth=.2, terms=[term(market="US")], settings=Settings(liquidate=False))
        for account in ["AF", "ISK"]:
            rows = audit_rows(result, account)
            self.assertAlmostEqual(sum(value for _, value in rows[:-1]), rows[-1][1], places=7)

