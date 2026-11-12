from pathlib import Path
import sys
import unittest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class AppFlows(unittest.TestCase):
    def setUp(self):
        from unittest.mock import patch
        import market_data
        def provider(tickers, period="5y", mode="Marknadsdata"):
            prices = market_data.make_example_history(tuple(tickers))
            if mode == "Marknadsdata":
                prices.attrs.update(is_example=False, fallback=False, source="Avanza NAV + Yahoo Finance", cached=False,
                    actual_last_dates={ticker: str(prices[ticker].last_valid_index().date()) for ticker in tickers})
            return prices
        self.provider = patch("experience.fetch_price_history", side_effect=provider)
        self.provider.start()
        self.addCleanup(self.provider.stop)

    def target(self, app, ticker):
        return next(row for row in app.session_state.portfolio_targets if row.get("ticker") == ticker)

    def new_app(self):
        from streamlit.elements.lib import policies
        policies._shown_default_value_warning = False
        return AppTest.from_file(str(ROOT / "app.py")).run(timeout=30)

    def assert_healthy(self, app):
        self.assertEqual([e.message for e in app.exception], [])
        self.assertFalse(any("Session State API" in warning.value for warning in app.warning))

    def test_home_and_both_entry_points(self):
        for index in [0, 1]:
            app = self.new_app()
            self.assert_healthy(app)
            app.button[index].click().run(timeout=30)
            self.assert_healthy(app)
            if index == 0:
                self.assertEqual(app.metric[0].value, "430 635 kr")
            else:
                self.assertTrue(app.success)

    def test_custom_portfolio_survives_simulator_reruns_and_return(self):
        app = self.new_app()
        app.button[0].click().run()
        app.selectbox(key="selected_profile").select("Egen profil").run()
        row = self.target(app, "VT")
        app.number_input(key=f"goal_weight_{row['id']}").set_value(55.0).run()
        app.selectbox(key=f"goal_ticker_{row['id']}").select("ACWI").run()
        before = app.metric[0].value
        app.button(key="simulate_portfolio").click().run(timeout=30)
        self.assert_healthy(app)
        self.assertEqual(app.session_state.selected_profile, "Egen profil")
        self.assertEqual(self.target(app, "ACWI")["id"], row["id"])
        self.assertEqual(app.radio[1].value, "Portfölj från Portföljkollen")
        app.radio[3].set_value("Månadsvis rebalansering").run(timeout=30)
        self.assert_healthy(app)
        self.assertEqual(self.target(app, "ACWI")["weight"], 55.0)
        self.assertEqual(self.target(app, "ACWI")["id"], row["id"])
        app.radio(key="academy_page").set_value("Portföljkollen").run()
        self.assert_healthy(app)
        self.assertEqual(app.metric[0].value, before)
        self.assertEqual(app.number_input(key=f"goal_weight_{row['id']}").value, 55.0)

    def test_questionnaire_and_notification_previews(self):
        app = self.new_app()
        app.button[0].click().run()
        next(b for b in app.button if b.label == "Använd enkätens risknivå").click().run()
        self.assert_healthy(app)
        self.assertEqual(app.session_state.selected_profile, "Egen profil")
        next(b for b in app.button if b.label == "Visa exempelnotiser").click().run()
        self.assert_healthy(app)
        self.assertTrue(any("Apple" in item.value for item in app.markdown))

    def test_empty_simulation_selection_is_explained(self):
        app = self.new_app()
        app.button[1].click().run()
        app.multiselect[0].set_value([]).run()
        self.assert_healthy(app)
        self.assertTrue(any("Välj minst ett instrument" in item.value for item in app.info))

    def test_simulator_custom_dates_and_zero_weight(self):
        app = self.new_app()
        app.button[1].click().run()
        app.radio[2].set_value("Anpassad").run()
        app.number_input(key="mock_weight_Apple").set_value(0.0).run()
        self.assert_healthy(app)
        app.selectbox(key="mock_backtest_mode").select("Eget datum").run()
        app.text_input(key="mock_backtest_custom_text").set_value("01012025").run()
        self.assert_healthy(app)
        self.assertTrue(app.success)
        app.text_input(key="mock_backtest_custom_text").set_value("ogiltigt").run()
        self.assert_healthy(app)
        self.assertTrue(app.warning)

    def test_fee_and_tax_checkboxes_change_the_results_independently(self):
        app = self.new_app()
        app.button[1].click().run()
        app.checkbox(key="cost_tax").uncheck().run()
        self.assert_healthy(app)
        self.assertEqual(len(app.metric), 2)  # gross and after-costs for the historical view
        app.checkbox(key="cost_include").uncheck().run()
        self.assert_healthy(app)
        self.assertEqual(app.metric[0].value, app.metric[1].value)
        app.checkbox(key="cost_tax").check().run()
        app.number_input(key="cost_other_allowance").set_value(300000).run()
        self.assert_healthy(app)
        self.assertNotEqual(app.metric[1].value, app.metric[2].value)

    def test_courtage_class_and_account_survive_navigation(self):
        app = self.new_app()
        app.button[1].click().run()
        app.selectbox(key="cost_class").select("Fast Pris").run()
        app.selectbox(key="cost_account").select("AF").run()
        app.radio(key="academy_page").set_value("Portföljkollen").run()
        self.assert_healthy(app)
        self.assertEqual(app.selectbox(key="cost_class").value, "Fast Pris")
        self.assertEqual(app.selectbox(key="cost_account").value, "AF")
        app.radio(key="academy_page").set_value("Testa din strategi").run()
        self.assert_healthy(app)
        self.assertEqual(app.selectbox(key="cost_account").value, "AF")

    def test_large_amount_and_optional_terminal_sale(self):
        app = self.new_app()
        app.button[1].click().run()
        next(n for n in app.number_input if n.label == "Belopp för simuleringen").set_value(1000000).run()
        self.assert_healthy(app)
        app.checkbox(key="cost_liquidate").uncheck().run()
        self.assert_healthy(app)
        self.assertTrue(any("Orealiserad vinst/förlust" in item.value for item in app.markdown))

    def test_start_requires_eligibility_confirmation(self):
        app = self.new_app()
        app.button[1].click().run()
        app.selectbox(key="cost_class").select("Start").run()
        self.assert_healthy(app)
        self.assertFalse(app.checkbox(key="cost_start_eligible").value)
        app.checkbox(key="cost_start_eligible").check().run()
        self.assert_healthy(app)

    def test_af_sale_view_updates_curve_and_allows_a_past_sale_date(self):
        app = self.new_app()
        app.button[1].click().run()
        app.selectbox(key="cost_account").select("AF").run()
        app.checkbox(key="cost_liquidate").uncheck().run()
        self.assert_healthy(app)
        self.assertTrue(app.checkbox(key="cost_af_sale_view").value)
        self.assertNotEqual(app.metric[1].value, app.metric[3].value)
        from datetime import timedelta
        chosen = app.date_input(key="af_sale_date_history").value - timedelta(days=7)
        app.date_input(key="af_sale_date_history").set_value(chosen).run()
        self.assert_healthy(app)
        self.assertTrue(any("Beräkningsdatum:" in caption.value for caption in app.caption))
        app.checkbox(key="cost_af_sale_view").uncheck().run()
        self.assert_healthy(app)
        self.assertEqual(app.metric[1].value, app.metric[3].value)
        app.radio(key="academy_page").set_value("Portföljkollen").run()
        app.radio(key="academy_page").set_value("Testa din strategi").run()
        self.assert_healthy(app)
        self.assertFalse(app.checkbox(key="cost_af_sale_view").value)
        app.checkbox(key="cost_tax").uncheck().run()
        self.assert_healthy(app)
        self.assertEqual(len(app.metric), 2)

    def test_avanza_zero_auto_and_bond_funds_can_be_simulated_without_brokerage(self):
        app = self.new_app()
        app.button[1].click().run()
        app.selectbox(key="fund_filter").select("Avanzas egna fonder").run()
        app.multiselect(key="mock_assets").set_value(["Avanza Zero", "Avanza Auto 1", "Avanza Ränta Kort"]).run()
        app.selectbox(key="cost_class").select("Fast Pris").run()
        self.assert_healthy(app)
        self.assertEqual(app.metric[0].value, app.metric[1].value)
        self.assertEqual(app.session_state.mock_assets, ["Avanza Zero", "Avanza Auto 1", "Avanza Ränta Kort"])
        app.radio(key="academy_page").set_value("Portföljkollen").run()
        app.selectbox(key="selected_profile").select("Egen profil").run()
        row = self.target(app, "EWD")
        app.selectbox(key=f"goal_ticker_{row['id']}").select("AVANZA:41567").run()
        self.assert_healthy(app)
        app.radio(key="academy_page").set_value("Testa din strategi").run()
        self.assert_healthy(app)
        self.assertIn("Avanza Zero", app.multiselect(key="mock_assets").value)

    def test_sharpe_window_risk_free_rate_and_horizon_are_independent_controls(self):
        app = self.new_app()
        app.button[0].click().run()
        before = app.metric[2].value
        app.selectbox(key="analysis_window").select("3 månader").run()
        self.assert_healthy(app)
        self.assertNotEqual(app.metric[2].value, before)
        annual = float(app.metric[2].value.replace(",", "."))
        app.number_input(key="risk_horizon_months").set_value(36).run()
        self.assertEqual(float(app.metric[2].value.replace(",", ".")), annual)
        app.selectbox(key="risk_sharpe_basis").select("Vald sparhorisont").run()
        self.assert_healthy(app)
        self.assertNotEqual(float(app.metric[2].value.replace(",", ".")), annual)
        app.number_input(key="risk_free_rate_pct").set_value(5.).run()
        self.assert_healthy(app)
        self.assertTrue(any("63 dagsavkastningar" in caption.value for caption in app.caption))

    def test_custom_risk_dates_are_separate_from_the_historical_comparison(self):
        from datetime import date
        app = self.new_app()
        app.button[1].click().run()
        before = [metric.value for metric in app.metric]
        app.selectbox(key="analysis_window").select("Egna datum").run()
        app.date_input(key="risk_custom_start").set_value(date(2026, 1, 1)).run()
        app.date_input(key="risk_custom_end").set_value(date(2026, 6, 30)).run()
        self.assert_healthy(app)
        self.assertEqual([metric.value for metric in app.metric], before)
        self.assertFalse(any(tab.label == "Framåtblick" for tab in app.tabs))
        self.assertFalse(any(button.key == "use_savings_horizon" for button in app.button))
        self.assertEqual(app.date_input(key="risk_custom_start").value, date(2026, 1, 1))
        self.assertEqual(app.date_input(key="risk_custom_end").value, date(2026, 6, 30))
        app.date_input(key="risk_custom_start").set_value(date(2026, 7, 1)).run()
        self.assert_healthy(app)
        self.assertTrue(app.warning)

    def test_returns_percentages_chart_units_and_deduction_bases(self):
        app = self.new_app()
        app.button[1].click().run()
        self.assert_healthy(app)
        self.assertTrue(all("% sedan start" in metric.delta for metric in app.metric))
        self.assertEqual(app.radio(key="cost_result_view_history").value, "Procent (%)")
        before = [metric.value for metric in app.metric]
        app.radio(key="cost_result_view_history").set_value("Kronor (kr)").run()
        self.assert_healthy(app)
        self.assertEqual([metric.value for metric in app.metric], before)
        app.selectbox(key="cost_percentage_base_history").select("Vinsten före avdrag").run()
        self.assert_healthy(app)
        self.assertTrue(any("ingen positiv vinst" in info.value for info in app.info))
        app.selectbox(key="cost_percentage_base_history").select("Slutvärdet före avdrag").run()
        self.assert_healthy(app)
        self.assertTrue(any("Procentbas: slutvärdet före avdrag" in caption.value for caption in app.caption))

    def test_portfolio_copy_and_sharpe_comparisons_follow_selected_scale(self):
        from engine import format_decimal_sv
        import numpy as np
        app = self.new_app()
        app.button[0].click().run()
        self.assert_healthy(app)
        self.assertIn("Exempelportfölj", [item.value for item in app.subheader])
        self.assertTrue(any("värderad 2026-11-02" in item.value for item in app.caption))
        self.assertEqual(app.metric[3].label, "Volatilitet · årsbasis")
        holdings = next(item.value for item in app.dataframe if "Värde" in item.value.columns)
        self.assertIn(app.metric[4].value, holdings.Instrument.to_list())
        app.selectbox(key="selected_profile").select("Egen profil").run()
        app.slider(key="min_portfolio_sharpe").set_value(2.).run()
        app.number_input(key="risk_horizon_months").set_value(36).run()
        app.selectbox(key="risk_sharpe_basis").select("Vald sparhorisont").run()
        self.assert_healthy(app)
        scaled_target = format_decimal_sv(2 * np.sqrt(3))
        diagnosis = next(item.value for item in app.markdown if "Genomsnittlig avkastning · årsbasis" in item.value)
        self.assertIn(f"Min Sharpe · 36 mån (skalad):</strong> {scaled_target}", diagnosis)
        self.assertTrue(any(f"mot ditt mål på {scaled_target} på samma skala" in item.value for item in app.markdown))
        self.assertIn("historiska marknadspriser", diagnosis)
        self.assertIn("Använd modellens förslag", [item.label for item in app.button])
        drift = next(item.value for item in app.dataframe if "Avvikelse mot mål" in item.value.columns)
        self.assertTrue(drift["Avvikelse mot mål"].str.endswith(" p.p.").all())

    def test_missing_and_short_portfolio_history_show_dashes(self):
        from datetime import date
        app = self.new_app()
        app.button[0].click().run()
        app.selectbox(key="analysis_window").select("Egna datum").run()
        app.date_input(key="risk_custom_start").set_value(date(2026, 1, 1)).run()
        for end in (date(2026, 1, 2), date(2025, 12, 31)):
            app.date_input(key="risk_custom_end").set_value(end).run()
            self.assert_healthy(app)
            self.assertEqual(app.metric[2].value, "—")
            self.assertEqual(app.metric[3].value, "—")
            diagnosis = next(item.value for item in app.markdown if "Genomsnittlig avkastning · årsbasis" in item.value)
            self.assertIn("årsbasis:</strong> —", diagnosis)
            self.assertIn("Historisk drawdown:</strong> —", diagnosis)
            details = next(item.value for item in app.dataframe if "Volatilitet · årsbasis" in item.value.columns)
            self.assertTrue((details["Volatilitet · årsbasis"] == "—").all())

    def test_explicit_example_mode_and_real_data_have_different_source_copy(self):
        from unittest.mock import patch
        import market_data
        for example in (False, True):
            def fixture(tickers, period="5y", **kwargs):
                prices = market_data.make_example_history(tuple(tickers))
                prices.attrs.update(is_example=example, fallback=False, source="Simulerade exempeldata" if example else "Avanza NAV + Yahoo Finance")
                return prices
            with patch("experience.fetch_price_history", side_effect=fixture):
                app = self.new_app()
                app.button[0].click().run()
                app.radio(key="data_mode").set_value("Exempeldata" if example else "Marknadsdata").run()
                self.assert_healthy(app)
                diagnosis = next(item.value for item in app.markdown if "Genomsnittlig avkastning · årsbasis" in item.value)
                self.assertIn("simulerade prisserier" if example else "historiska marknadspriser", diagnosis)
                self.assertEqual(any("simulerade prisserier" in item.value for item in app.info), example)

    def test_af_exit_explanation_matches_tax_and_sale_toggles(self):
        from cost_model import VERIFIED_DATE
        app = self.new_app()
        app.button[1].click().run()
        app.selectbox(key="cost_account").select("AF").run()
        app.checkbox(key="cost_liquidate").uncheck().run()
        self.assert_healthy(app)
        self.assertTrue(any("AF-nettot i försäljningsvyn inkluderar tänkta säljavgifter" in item.value for item in app.markdown))
        self.assertFalse(any("avslutande säljavgifter dras inte av" in item.value for item in app.markdown))
        self.assertTrue(any(f"Prislista kontrollerad {VERIFIED_DATE}" in item.value for item in app.caption))
        app.checkbox(key="cost_af_sale_view").uncheck().run()
        self.assertTrue(any("inga avslutande säljordrar eller tänkta säljavgifter" in item.value for item in app.markdown))
        app.checkbox(key="cost_liquidate").check().run()
        self.assertTrue(any("Avslutande säljordrar och deras avgifter ingår" in item.value for item in app.markdown))

    def test_dated_start_history_survives_navigation(self):
        from datetime import date
        app = self.new_app()
        app.session_state.cost_start_history_data = [{"Datum": date(2025, 12, 1), "Antal gratisaffärer": 499}]
        app.button[1].click().run()
        app.selectbox(key="cost_class").select("Start").run()
        app.checkbox(key="cost_start_eligible").check().run()
        self.assert_healthy(app)
        self.assertTrue(any("tolvmånadersperiod" in item.value for item in app.caption))
        app.radio(key="academy_page").set_value("Portföljkollen").run()
        self.assert_healthy(app)
        self.assertEqual(app.session_state.cost_start_history_data[0]["Antal gratisaffärer"], 499)
        app.radio(key="academy_page").set_value("Testa din strategi").run()
        self.assert_healthy(app)
        self.assertEqual(app.session_state.cost_start_history_data[0]["Datum"], date(2025, 12, 1))

    def test_target_names_add_remove_and_transfer_keep_instrument_identity(self):
        app = self.new_app()
        app.button[0].click().run()
        before = app.metric[0].value
        row = self.target(app, "VT")
        app.text_input(key=f"goal_label_{row['id']}").set_value("Mitt sparande <eget namn>").run()
        self.assert_healthy(app)
        self.assertEqual(app.session_state.selected_profile, "Egen profil")
        self.assertEqual(app.metric[0].value, before)
        app.button(key="simulate_portfolio").click().run()
        self.assert_healthy(app)
        table = next(item.value for item in app.dataframe if "Innehav från Portföljkollen" in item.value.columns)
        renamed = table.loc[table.Ticker == "VT"].iloc[0]
        self.assertEqual(renamed["Innehav från Portföljkollen"], "Mitt sparande <eget namn>")
        self.assertFalse(any("<span>Mitt sparande <eget namn>" in item.value for item in app.markdown))
        app.radio(key="academy_page").set_value("Portföljkollen").run()
        app.button(key="goal_add").click().run()
        draft = next(row for row in app.session_state.portfolio_targets if not row.get("ticker"))
        app.selectbox(key=f"goal_ticker_{draft['id']}").select("AVANZA:41567").run()
        app.text_input(key=f"goal_label_{draft['id']}").set_value("Min Zero").run()
        app.number_input(key=f"goal_weight_{draft['id']}").set_value(20.).run()
        self.assert_healthy(app)
        self.assertEqual(app.metric[0].value, before)
        table = next(item.value for item in app.dataframe if "Instrument" in item.value.columns and "Värde" in item.value.columns)
        self.assertEqual(table.loc[table.Instrument == "Min Zero", "Värde"].iloc[0], "0 kr")
        app.button(key=f"goal_remove_{row['id']}").click().run()
        self.assert_healthy(app)
        self.assertEqual(app.metric[0].value, before)
        drift = next(item.value for item in app.dataframe if "Avvikelse mot mål" in item.value.columns)
        self.assertEqual(drift.loc[drift.Innehav == "Mitt sparande <eget namn>", "Målvikt"].iloc[0], "0 %")

    def test_duplicate_selection_is_rejected_and_empty_target_list_is_recoverable(self):
        app = self.new_app()
        app.button[0].click().run()
        before = app.metric[0].value
        app.button(key="goal_add").click().run()
        draft = next(row for row in app.session_state.portfolio_targets if not row.get("ticker"))
        app.selectbox(key=f"goal_ticker_{draft['id']}").select("VT").run()
        self.assert_healthy(app)
        self.assertTrue(any("finns redan i målbilden" in item.value for item in app.info))
        for row in list(app.session_state.portfolio_targets):
            app.button(key=f"goal_remove_{row['id']}").click().run()
            self.assert_healthy(app)
        self.assertEqual(app.metric[0].value, before)
        self.assertEqual(app.session_state.portfolio_targets, [])
        self.assertFalse(any("kan finansiera ungefär" in item.value for item in app.success))
        app.button(key="goal_add").click().run()
        row = app.session_state.portfolio_targets[0]
        app.selectbox(key=f"goal_ticker_{row['id']}").select("AVANZA:41567").run()
        app.number_input(key=f"goal_weight_{row['id']}").set_value(100.).run()
        self.assert_healthy(app)
        self.assertTrue(any("kan finansiera ungefär" in item.value for item in app.success))

    def test_unheld_young_target_does_not_shorten_current_portfolio_risk_history(self):
        from avanza_funds import get_avanza_funds
        app = self.new_app()
        app.button[0].click().run()
        before = app.metric[2].value
        app.button(key="goal_add").click().run()
        row = next(row for row in app.session_state.portfolio_targets if not row.get("ticker"))
        young = max(get_avanza_funds(), key=lambda fund: fund["start_date"])
        app.selectbox(key=f"goal_ticker_{row['id']}").select(young["ticker"]).run()
        app.number_input(key=f"goal_weight_{row['id']}").set_value(10.).run()
        self.assert_healthy(app)
        self.assertEqual(app.metric[2].value, before)
        self.assertTrue(any("756 dagsavkastningar" in item.value for item in app.caption))

    def test_real_data_is_default_and_offline_state_does_not_substitute_examples(self):
        from unittest.mock import patch
        from market_data import PriceDataError
        with patch("experience.fetch_price_history", side_effect=PriceDataError("Verklig historik saknas")):
            app = self.new_app()
            app.button[0].click().run()
            self.assert_healthy(app)
            self.assertEqual(app.radio(key="data_mode").value, "Marknadsdata")
            self.assertEqual(len(app.metric), 0)
            self.assertTrue(app.error)
            self.assertTrue(any(button.key == "goal_add" for button in app.button))
        app.radio(key="data_mode").set_value("Exempeldata").run()
        self.assert_healthy(app)
        self.assertTrue(any("simulerade prisserier" in item.value for item in app.info))

    def test_historical_only_view_exposes_underlying_dates_and_deposit_assumption(self):
        app = self.new_app()
        app.button[1].click().run()
        self.assert_healthy(app)
        self.assertFalse(any("Framåtblick" in tab.label for tab in app.tabs))
        self.assertFalse(any(button.key == "use_fund_market_data" for button in app.button))
        self.assertFalse(any("framtidsscenarier" in item.value.lower() for item in app.markdown))
        coverage = next(item.value for item in app.dataframe if "Senast rapporterade kursdag" in item.value.columns)
        self.assertEqual(len(coverage), 3)
        self.assertTrue(any("gemensamma dagsavkastningar" in item.value for item in app.caption))
        app.radio(key="academy_page").set_value("Portföljkollen").run()
        self.assert_healthy(app)
        self.assertTrue(any("inte använder försäljningslikvid" in item.value for item in app.markdown))

    def test_goal_weights_can_be_tested_without_inventing_current_holdings(self):
        app = self.new_app()
        app.button[0].click().run()
        app.button(key="goal_add").click().run()
        row = next(row for row in app.session_state.portfolio_targets if not row.get("ticker"))
        app.selectbox(key=f"goal_ticker_{row['id']}").select("AVANZA:41567").run()
        app.text_input(key=f"goal_label_{row['id']}").set_value("Mitt eget fondnamn").run()
        app.number_input(key=f"goal_weight_{row['id']}").set_value(20.).run()
        app.button(key="simulate_portfolio").click().run()
        next(item for item in app.radio if item.label == "Hur ska beloppet fördelas?").set_value("Målvikter").run()
        self.assert_healthy(app)
        coverage = next(item.value for item in app.dataframe if "Senast rapporterade kursdag" in item.value.columns)
        self.assertIn("Mitt eget fondnamn", coverage.Instrument.tolist())
        self.assertIn("AVANZA:41567", coverage["Ticker/fond-ID"].tolist())
        table = next(item.value for item in app.dataframe if "Innehav från Portföljkollen" in item.value.columns)
        self.assertEqual(table.loc[table.Ticker == "AVANZA:41567", "Nuvarande vikt"].iloc[0], "0 %")

    def test_customer_accounts_preserve_separate_goals_and_restore_learning_context(self):
        app = self.new_app()
        app.button[0].click().run()
        before = app.metric[0].value
        public = self.target(app, "VT")
        app.text_input(key=f"goal_label_{public['id']}").set_value("Mitt publika exempel").run()
        app.selectbox(key="workspace_mode").select("Mitt konto · demo").run()
        self.assert_healthy(app)
        self.assertEqual(app.number_input(key="account_cash").value, 5000.)
        self.assertEqual(app.selectbox(key="cost_account").value, "ISK")
        self.assertTrue(app.selectbox(key="cost_account").disabled)
        row = app.session_state.portfolio_targets[0]
        app.text_input(key=f"goal_label_{row['id']}").set_value("Mitt ISK-mål").run()
        app.button(key="account_save_goal").click().run()
        app.text_input(key=f"goal_label_{row['id']}").set_value("Tillfällig ändring").run()
        app.button(key="account_restore_goal").click().run()
        self.assert_healthy(app)
        self.assertEqual(app.session_state.portfolio_targets[0]["label"], "Mitt ISK-mål")
        app.selectbox(key="account_selected").select("demo_af").run()
        self.assert_healthy(app)
        self.assertEqual(app.selectbox(key="cost_account").value, "AF")
        self.assertEqual(app.number_input(key="account_cash").value, 10000.)
        app.selectbox(key="account_selected").select("demo_isk").run()
        self.assert_healthy(app)
        self.assertEqual(app.session_state.portfolio_targets[0]["label"], "Mitt ISK-mål")
        app.selectbox(key="workspace_mode").select("Lär dig mer").run()
        self.assert_healthy(app)
        self.assertEqual(app.metric[0].value, before)
        self.assertEqual(self.target(app, "VT")["label"], "Mitt publika exempel")

    def test_customer_cash_and_no_sale_deposit_plan_are_transferred_to_historical_view(self):
        app = self.new_app()
        app.button(key="open_customer_demo").click().run()
        self.assert_healthy(app)
        before = app.metric[0].value
        app.checkbox(key="account_allow_sales").uncheck().run()
        app.checkbox(key="account_use_cash").uncheck().run()
        app.number_input(key="account_new_deposit").set_value(5000.).run()
        self.assert_healthy(app)
        self.assertEqual(app.metric[0].value, before)
        orders = next(item.value for item in app.dataframe if "Modellbelopp" in item.value.columns)
        self.assertFalse((orders["Åtgärd"] == "Sälj").any())
        app.button(key="simulate_portfolio").click().run()
        self.assert_healthy(app)
        source = next(item.value for item in app.dataframe if "Innehav från Portföljkollen" in item.value.columns)
        self.assertIn("Likvida medel", source["Innehav från Portföljkollen"].tolist())
        coverage = next(item.value for item in app.dataframe if "Senast rapporterade kursdag" in item.value.columns)
        self.assertIn("Likvid i SEK · 0 % antagen ränta", coverage.Källa.tolist())

    def test_optimizer_applies_only_goal_weights_and_stales_after_input_changes(self):
        app = self.new_app()
        app.button[0].click().run()
        before = app.metric[0].value
        app.button(key="opt_run").click().run(timeout=60)
        self.assert_healthy(app)
        self.assertIn("opt_result", app.session_state)
        result = app.session_state.opt_result
        self.assertAlmostEqual(sum(result["weights"]), 1., places=8)
        self.assertGreaterEqual(len(result["train"])-1, 252)
        self.assertGreaterEqual(len(result["validation"])-1, 63)
        app.button(key="opt_apply").click().run(timeout=60)
        self.assert_healthy(app)
        self.assertEqual(app.metric[0].value, before)
        self.assertEqual(app.session_state.selected_profile, "Egen profil")
        self.assertAlmostEqual(sum(row["weight"] for row in app.session_state.portfolio_targets), 100.)
        app.selectbox(key="opt_mode").select("Månadsvis rebalansering").run()
        self.assert_healthy(app)
        self.assertTrue(any("Villkor eller prisunderlag har ändrats" in item.value for item in app.info))
        self.assertFalse(any(item.key == "opt_apply" for item in app.button))

    def test_min_exact_max_editor_drives_the_search_and_changes_stale_the_result(self):
        import json
        import streamlit as st
        from unittest.mock import patch
        app = self.new_app()
        app.button[0].click().run()
        selected = app.session_state.opt_selected[:3]
        app.multiselect(key="opt_selected").set_value(selected).run()
        editor = next(item for item in app.dataframe if "Villkor" in item.value.columns)
        self.assertEqual(editor.value.columns.tolist(), ["Instrument", "Villkor", "Vikt (%)"])
        self.assertTrue((editor.value["Villkor"] == "max").all())
        self.assertTrue((editor.value["Vikt (%)"] == 100).all())
        config = json.loads(editor.proto.columns)["Villkor"]["type_config"]
        self.assertEqual(config["type"], "selectbox")
        self.assertEqual(config["options"], ["min", "=", "max"])
        original_editor = st.data_editor
        def conditions(data, *args, **kwargs):
            result = original_editor(data, *args, **kwargs)
            if "Villkor" in result:
                result = result.copy()
                result["Villkor"] = ["min", "=", "max"]
                result["Vikt (%)"] = [20., 25., 55.]
            return result
        with patch("optimization_ui.st.data_editor", side_effect=conditions):
            app.button(key="opt_run").click().run(timeout=60)
        self.assert_healthy(app)
        result = app.session_state.opt_result
        indices = [result["columns"].index(ticker) for ticker in selected]
        self.assertAlmostEqual(result["lower"][indices[0]], .2)
        self.assertAlmostEqual(result["upper"][indices[2]], .55)
        self.assertGreaterEqual(result["weights"][indices[0]] + 1e-8, .2)
        self.assertAlmostEqual(result["weights"][indices[1]], .25, places=8)
        self.assertLessEqual(result["weights"][indices[2]], .55 + 1e-8)
        self.assertAlmostEqual(sum(result["weights"]), 1., places=8)
        app.run()
        self.assert_healthy(app)
        self.assertTrue(any("Villkor eller prisunderlag har ändrats" in item.value for item in app.info))
        self.assertFalse(any(item.key == "opt_apply" for item in app.button))

    def test_weight_condition_cannot_override_the_customer_no_sale_rule(self):
        import streamlit as st
        from unittest.mock import patch
        app = self.new_app()
        app.button(key="open_customer_demo").click().run()
        app.checkbox(key="account_allow_sales").uncheck().run()
        current_value = app.metric[0].value
        original_editor = st.data_editor
        def exclude_held_position(data, *args, **kwargs):
            result = original_editor(data, *args, **kwargs)
            if "Villkor" in result:
                result = result.copy()
                result.loc[0, "Villkor"] = "max"
                result.loc[0, "Vikt (%)"] = 0.
            return result
        with patch("optimization_ui.st.data_editor", side_effect=exclude_held_position):
            app.button(key="opt_run").click().run(timeout=60)
        self.assert_healthy(app)
        self.assertTrue(any("går inte ihop" in item.value for item in app.error))
        self.assertNotIn("opt_result", app.session_state)
        self.assertEqual(app.metric[0].value, current_value)

    def test_custom_formula_errors_do_not_execute_code_and_valid_formula_can_run(self):
        app = self.new_app()
        app.button[0].click().run()
        app.selectbox(key="opt_objective").select("Egen formel").run()
        app.text_input(key="opt_formula").set_value("__import__('os')").run()
        app.button(key="opt_run").click().run(timeout=60)
        self.assert_healthy(app)
        self.assertTrue(app.error)
        self.assertNotIn("opt_result", app.session_state)
        app.text_input(key="opt_formula").set_value("CAGR - 0.5 * MaxDrawdown").run()
        app.button(key="opt_run").click().run(timeout=60)
        self.assert_healthy(app)
        self.assertIn("opt_result", app.session_state)

    def test_help_is_on_demand_while_data_status_stays_visible(self):
        app = self.new_app()
        app.button[0].click().run()
        self.assert_healthy(app)
        self.assertTrue(app.metric[2].proto.help)
        self.assertTrue(any("Marknadsdata från" in item.value for item in app.caption))
        self.assertTrue(any("dagsavkastningar" in item.value for item in app.caption))
        self.assertFalse(any("Historik väljer vilka kursdagar" in item.value for item in app.caption))
        self.assertTrue(any("Historik väljer vilka kursdagar" in item.value for item in app.markdown))

    def test_imported_account_adapter_does_not_change_another_session(self):
        from account_model import parse_holdings_csv
        app = self.new_app()
        app.button(key="open_customer_demo").click().run()
        accounts = dict(app.session_state.account_catalog)
        accounts["imported"] = parse_holdings_csv("instrument;antal;omkostnadsbelopp\nINVE-B.ST;10;1000\n", account="AF", cash=500.)
        app.session_state.account_catalog = accounts
        app.run()
        app.selectbox(key="account_selected").select("imported").run()
        self.assert_healthy(app)
        self.assertEqual(app.selectbox(key="cost_account").value, "AF")
        self.assertEqual(app.number_input(key="account_cash").value, 500.)
        other = self.new_app()
        other.button(key="open_customer_demo").click().run()
        self.assert_healthy(other)
        self.assertNotIn("imported", other.session_state.account_catalog)

    def test_reserved_cash_optimizer_result_can_be_applied_without_losing_cash_weight(self):
        app = self.new_app()
        app.button(key="open_customer_demo").click().run()
        app.checkbox(key="account_allow_sales").uncheck().run()
        app.checkbox(key="account_use_cash").uncheck().run()
        app.number_input(key="account_new_deposit").set_value(5000.).run()
        app.button(key="opt_run").click().run(timeout=60)
        self.assert_healthy(app)
        result = app.session_state.opt_result
        weights = dict(zip(result["columns"], result["weights"]))
        self.assertGreater(weights["__cash__"], 0.)
        app.button(key="opt_apply").click().run(timeout=60)
        self.assert_healthy(app)
        self.assertAlmostEqual(app.session_state.account_target_cash_pct, weights["__cash__"] * 100)
        actual = {row["ticker"]: row["weight"] / 100 for row in app.session_state.portfolio_targets}
        for ticker in actual:
            self.assertAlmostEqual(actual[ticker], weights[ticker], places=8)
        self.assertAlmostEqual(sum(actual.values()) + app.session_state.account_target_cash_pct / 100, 1.)

