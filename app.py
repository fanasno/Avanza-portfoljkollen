"""Avanza Akademin concept, adapted from fanasno/savr-portfoliokollen-testsavr."""
import numpy as np
import pandas as pd
import streamlit as st
from html import escape
from market_data import PriceDataError
from portfolio_model import build_portfolio_template, target_profile, contribution_message
from portfolio_ui import ensure_portfolio_state, reset_targets, render_target_editor
from account_ui import render_account_context, render_account_actions
from optimization_ui import render_optimizer
from help_ui import explain, METRIC_HELP
from engine import *
from data import *
from charts import *
from brand import THEME
from cost_ui import render_cost_settings, run_simulation, render_trade_costs, contribution_after_costs
from risk_ui import render_risk_controls, render_risk_period_note, sharpe_display, sharpe_basis_label, risk_pct
from risk_model import horizon_factor, portfolio_prices_sek
from fund_ui import filter_instruments, render_fund_facts
from experience import (
    render_css, render_site_header, render_navigation, render_academy_home,
    render_module_intro, render_source_notice, render_data_controls, render_footer,
    open_portfolio_simulation, refresh_analysis, load_market_context,
    preserve_shared_portfolio_state, scroll_to_page_start,
)

st.set_page_config(page_title="Sparstrategi · Avanza Akademin", page_icon="↗", layout="wide")


def get_active_category_instrument_map(selected_profile: str, category_order: list[str]) -> dict[str, str]:
    default_map = get_default_category_instrument_map()
    lookup = get_category_instrument_lookup()
    if selected_profile != "Egen profil":
        return dict(default_map)

    active_map = {}
    for category in category_order:
        state_key = f"category_instrument_{category}"
        candidate = st.session_state.get(state_key, default_map[category])
        instrument = lookup.get(candidate)
        if instrument is None or instrument["category"] != category:
            candidate = default_map[category]
        active_map[category] = candidate
    return active_map


def use_savings_horizon(last_date):
    st.session_state.mock_future_mode = "Eget datum"
    st.session_state.mock_future_custom_date = (pd.Timestamp(last_date) + pd.DateOffset(months=int(st.session_state.risk_horizon_months))).date()
    st.session_state.mock_future_custom_text = ""



def apply_profile_defaults(profile_name: str) -> None:
    if profile_name == "Egen profil":
        st.session_state.selected_profile = "Egen profil"
        return
    base_profile = get_risk_profiles()[profile_name]
    reset_targets(base_profile)
    default_instruments = get_default_category_instrument_map()
    current_profile_name = str(st.session_state.get("profile_name", "")).strip()
    default_profile_names = {f"{name} profil" for name in get_risk_profiles()} | {"Min profil"}
    st.session_state.selected_profile = profile_name
    if not current_profile_name or current_profile_name in default_profile_names:
        st.session_state.profile_name = f"{profile_name} profil"
    st.session_state.risk_appetite = int(base_profile["risk_appetite"])
    st.session_state.concentration_threshold = base_profile["max_single_holding"]
    st.session_state.equity_buffer = int(base_profile["equity_buffer"])
    st.session_state.category_gap_threshold = int(base_profile["category_gap_threshold"])
    st.session_state.top_three_threshold = int(base_profile["top_three_threshold"])
    st.session_state.minimum_trade_size = int(base_profile["minimum_trade_size"])
    st.session_state.min_portfolio_sharpe = float(base_profile["min_portfolio_sharpe"])
    st.session_state.max_portfolio_volatility = float(base_profile["max_portfolio_volatility"])
    st.session_state.max_drawdown_tolerance = float(base_profile["max_drawdown_tolerance"])
    for category, weight in base_profile["target_weights"].items():
        st.session_state[f"target_weight_{category}"] = float(weight)
    for category, ticker in default_instruments.items():
        st.session_state[f"category_instrument_{category}"] = ticker



def handle_profile_selection_change() -> None:
    apply_profile_defaults(st.session_state.selected_profile)



def apply_recommended_risk_targets(risk_appetite: int) -> None:
    recommended = get_risk_preference_defaults(risk_appetite)
    st.session_state.min_portfolio_sharpe = float(recommended["min_portfolio_sharpe"])
    st.session_state.max_portfolio_volatility = float(recommended["max_portfolio_volatility"])
    st.session_state.max_drawdown_tolerance = float(recommended["max_drawdown_tolerance"])



def calculate_risk_questionnaire_profile() -> dict:
    total_weighted_score = 0.0
    answers = []
    for question in get_risk_questionnaire():
        selected_label = st.session_state.get(
            question["key"], question["options"][0]["label"]
        )
        selected_option = next(
            option for option in question["options"] if option["label"] == selected_label
        )
        weighted_score = question["weight"] * selected_option["score"]
        total_weighted_score += weighted_score
        answers.append(
            {
                "question": question["question"],
                "answer": selected_label,
                "weight": question["weight"],
                "score": selected_option["score"],
                "weighted_score": weighted_score,
            }
        )

    risk_level = max(1, min(10, int(round(total_weighted_score / 10))))
    return {
        "risk_level": risk_level,
        "score_100": total_weighted_score,
        "answers": answers,
    }



def apply_questionnaire_risk_profile() -> None:
    result = calculate_risk_questionnaire_profile()
    st.session_state.selected_profile = "Egen profil"
    st.session_state.risk_appetite = result["risk_level"]
    apply_recommended_risk_targets(result["risk_level"])



def render_insights(insights: list) -> None:
    for insight in insights:
        st.markdown(
            f"""
            <div class="insight {insight['tone']}">
                <h4>{escape(insight['title'])}</h4>
                <p>{escape(insight['body'])}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )



def render_notification_cards(title: str, messages: list, tone: str = "info") -> None:
    st.markdown(f"#### {title}")
    if not messages:
        st.markdown(
            """
            <div class="insight info">
                <h4>Inga notiser valda ännu</h4>
                <p>Välj innehav eller intervall för att skapa en första notisfeed.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    for message in messages:
        st.markdown(
            f"""
            <div class="insight {tone}">
                <h4>{escape(message['title'])}</h4>
                <p>{escape(message['body'])}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )



def set_session_defaults(defaults: dict) -> None:
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value



def normalize_legacy_state() -> None:
    module_aliases = {
        "Lär med fake-pengar": "Testa din strategi",
        "Testinvest": "Testa din strategi",
    }
    active_module = st.session_state.get("active_module")
    if active_module in module_aliases:
        st.session_state.active_module = module_aliases[active_module]

    if st.session_state.get("selected_profile") == "Forsiktig":
        st.session_state.selected_profile = "Försiktig"
    if st.session_state.get("profile_name") == "Forsiktig profil":
        st.session_state.profile_name = "Försiktig profil"
    if st.session_state.get("mock_rebalance_mode") == "Köp och behåll":
        st.session_state.mock_rebalance_mode = "Buy and hold"
    if st.session_state.get("mock_source") not in {None, "Egna instrument", "Portfölj från Portföljkollen"}:
        st.session_state.mock_source = "Egna instrument"
    if st.session_state.get("rebalancer_header_chip") in {"Rebalansering", "Smart Rebalancer"}:
        st.session_state.rebalancer_header_chip = "Portföljkollen"
    if st.session_state.get("testinvest_header_chip") == "Testinvest":
        st.session_state.testinvest_header_chip = "Testa din strategi"



def initialize_session_state(
    default_profile: dict,
    category_order: list[str],
    default_backtest_date: pd.Timestamp,
    default_future_date: pd.Timestamp,
) -> None:
    default_instruments = get_default_category_instrument_map()
    set_session_defaults(
        {
            "profile_name": "Min profil",
            "risk_appetite": int(default_profile["risk_appetite"]),
            "analysis_window": "3 år",
            "risk_free_rate_pct": 2.0,
            "concentration_threshold": default_profile["max_single_holding"],
            "equity_buffer": int(default_profile["equity_buffer"]),
            "category_gap_threshold": int(default_profile["category_gap_threshold"]),
            "top_three_threshold": int(default_profile["top_three_threshold"]),
            "minimum_trade_size": int(default_profile["minimum_trade_size"]),
            "min_portfolio_sharpe": float(default_profile["min_portfolio_sharpe"]),
            "max_portfolio_volatility": float(default_profile["max_portfolio_volatility"]),
            "max_drawdown_tolerance": float(default_profile["max_drawdown_tolerance"]),
            "active_module": "Rebalansering",
            "selected_profile": "Balanserad",
            "watch_selection": ["Apple", "Investor B"],
            "watch_interval": "Månadsvis",
            "rebalance_interval": "Månadsvis",
            "watch_active": False,
            "rebalance_active": False,
            "mock_source": "Egna instrument",
            "mock_assets": ["Apple", "Microsoft", "Investor B"],
            "mock_amount": 10000,
            "mock_backtest_interval": "1 månad bakåt",
            "mock_future_horizon": "1 månad framåt",
            "mock_weight_mode": "Likavikt",
            "mock_rebalance_mode": "Buy and hold",
            "mock_backtest_mode": "Snabbval",
            "mock_future_mode": "Snabbval",
            "mock_backtest_custom_date": default_backtest_date.date(),
            "mock_future_custom_date": default_future_date.date(),
            "mock_backtest_custom_text": "",
            "mock_future_custom_text": "",
            "rebalancer_header_chip": "Portföljkollen",
            "testinvest_header_chip": "Testa din strategi",
        }
    )

    for question in get_risk_questionnaire():
        if question["key"] not in st.session_state:
            midpoint_index = min(1, len(question["options"]) - 1)
            st.session_state[question["key"]] = question["options"][midpoint_index]["label"]

    for category in category_order:
        weight_key = f"target_weight_{category}"
        if weight_key not in st.session_state:
            st.session_state[weight_key] = float(default_profile["target_weights"][category])
        instrument_key = f"category_instrument_{category}"
        if instrument_key not in st.session_state:
            st.session_state[instrument_key] = default_instruments[category]

    normalize_legacy_state()



def get_module_header_config(active_module: str) -> tuple[str, str, list[str], dict[str, tuple[str, str]]]:
    if active_module == "Rebalansering":
        return (
            "Portföljkollen",
            "rebalancer_header_chip",
            ["Portföljkollen", "Marknadsdata", "Riskprofil"],
            {
                "Portföljkollen": (
                    "Vad verktyget gör",
                    "Du får hjälp att förstå portföljen, upptäcka obalanser och se tydliga köp- och säljförslag utifrån din målprofil.",
                ),
                "Marknadsdata": (
                    "Datakälla",
                    "Analysen bygger på aktuella priser, valutakurser och historisk utveckling för portföljens innehav.",
                ),
                "Riskprofil": (
                    "Hur riskprofilen används",
                    "Riskprofilen sätter ramar för aktieandel, koncentration och hur stora svängningar portföljen bör tåla. Standardprofilerna ger färdiga riktlinjer, medan Egen profil låter dig styra själv.",
                ),
            },
        )

    return (
        "Testa din strategi",
        "testinvest_header_chip",
        ["Testa din strategi", "Historisk jämförelse", "Marknadsdata"],
        {
            "Testa din strategi": (
                "Vad verktyget gör",
                "Du kan prova idéer med ett testbelopp och jämföra hur olika fördelningar, rebalanseringar, avgifter och skatt hade påverkat den historiska utvecklingen.",
            ),
            "Historisk jämförelse": (
                "Så fungerar den historiska jämförelsen",
                "Valda instrument jämförs över samma tillgängliga historik med buy and hold eller rebalansering. Valda avgifter och kontoskatt räknas av i nettot.",
            ),
            "Marknadsdata": (
                "Datakälla",
                "Testa din strategi bygger på historiska prisrörelser för de instrument du väljer.",
            ),
        },
    )



def build_selected_profile_config(
    profiles: dict,
    selected_profile: str,
    selected_profile_name: str,
    raw_target_weights: dict,
) -> dict:
    if selected_profile in profiles:
        return {
            **profiles[selected_profile],
            "target_weights": dict(profiles[selected_profile]["target_weights"]),
            "raw_weight_total": 100.0,
            "profile_name": selected_profile_name,
        }

    return build_personal_profile(
        selected_profile_name,
        raw_target_weights,
        int(st.session_state.concentration_threshold),
    )



def build_personalization_settings(portfolio_market_summary: dict) -> dict:
    return {
        "concentration_threshold": int(st.session_state.concentration_threshold),
        "equity_buffer": int(st.session_state.equity_buffer),
        "category_gap_threshold": int(st.session_state.category_gap_threshold),
        "top_three_threshold": int(st.session_state.top_three_threshold),
        "min_portfolio_sharpe": float(st.session_state.min_portfolio_sharpe),
        "max_portfolio_volatility": float(st.session_state.max_portfolio_volatility),
        "max_drawdown_tolerance": float(st.session_state.max_drawdown_tolerance),
        "market_summary": portfolio_market_summary,
    }



def get_history_date_bounds(full_price_history: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp]:
    if full_price_history.empty:
        return (
            pd.Timestamp.today().normalize() - pd.DateOffset(years=1),
            pd.Timestamp.today().normalize(),
        )

    return (
        pd.Timestamp(full_price_history.index.min()).normalize(),
        pd.Timestamp(full_price_history.index.max()).normalize(),
    )



def render_tools(active_module: str) -> None:

    profiles = get_risk_profiles()
    notification_intervals = get_notification_intervals()
    category_order = list(profiles["Balanserad"]["target_weights"].keys())
    default_profile = profiles["Balanserad"]
    default_category_instruments = get_default_category_instrument_map()
    set_session_defaults(
        {
            "profile_name": "Min profil",
            "risk_appetite": int(default_profile["risk_appetite"]),
            "analysis_window": "3 år",
            "risk_free_rate_pct": 2.0,
            "concentration_threshold": default_profile["max_single_holding"],
            "equity_buffer": int(default_profile["equity_buffer"]),
            "category_gap_threshold": int(default_profile["category_gap_threshold"]),
            "top_three_threshold": int(default_profile["top_three_threshold"]),
            "minimum_trade_size": int(default_profile["minimum_trade_size"]),
            "min_portfolio_sharpe": float(default_profile["min_portfolio_sharpe"]),
            "max_portfolio_volatility": float(default_profile["max_portfolio_volatility"]),
            "max_drawdown_tolerance": float(default_profile["max_drawdown_tolerance"]),
            "active_module": "Rebalansering",
            "selected_profile": "Balanserad",
            "mock_assets": ["Apple", "Microsoft", "Investor B"],
            "watch_selection": ["Apple", "Investor B"],
            **{
                f"category_instrument_{category}": ticker
                for category, ticker in default_category_instruments.items()
            },
        }
    )
    normalize_legacy_state()

    if st.session_state.get("_data_policy_version") != 2:
        st.session_state.data_mode = "Marknadsdata"
        st.session_state._data_policy_version = 2
    active_category_instruments = get_active_category_instrument_map(st.session_state.selected_profile, category_order)
    initial_profile = dict(profiles.get(st.session_state.selected_profile, default_profile))
    if st.session_state.selected_profile == "Egen profil":
        initial_profile["target_weights"] = {category: float(st.session_state.get(f"target_weight_{category}", weight))
                                             for category, weight in default_profile["target_weights"].items()}
    ensure_portfolio_state(initial_profile, active_category_instruments)
    is_customer = render_account_context()
    portfolio_template = build_portfolio_template(st.session_state.portfolio_holdings, st.session_state.portfolio_targets)
    watchlist_template = load_live_watchlist_template()

    try:
        market_context = load_market_context(
            portfolio_template,
            watchlist_template,
            st.session_state.analysis_window,
            float(st.session_state.risk_free_rate_pct),
        )
    except PriceDataError as error:
        render_module_intro(active_module, st.session_state.profile_name)
        st.error(str(error))
        render_data_controls(dict(source="Ingen komplett verklig historik tillgänglig", error=True))
        with st.expander("Ändra instrument i målbilden", expanded=True):
            render_target_editor()
        return
    full_price_history = market_context["full_price_history"]
    analysis_history = market_context["analysis_history"]
    portfolio = market_context["portfolio"]
    watchlist = market_context["watchlist"]
    instrument_universe = market_context["instrument_universe"]
    portfolio_asset_metrics = market_context["portfolio_asset_metrics"]
    portfolio_market_summary = market_context["portfolio_market_summary"]

    history_first_date, history_last_date = get_history_date_bounds(full_price_history)
    default_backtest_date = max(history_first_date, history_last_date - pd.DateOffset(months=1))
    default_future_date = history_last_date + pd.DateOffset(months=6)
    initialize_session_state(
        default_profile,
        category_order,
        default_backtest_date,
        default_future_date,
    )

    selected_profile = st.session_state.selected_profile
    selected_profile_name = st.session_state.profile_name.strip() or selected_profile
    selected_profile_config = target_profile(
        st.session_state.portfolio_targets,
        dict(profiles.get(selected_profile, default_profile), max_single_holding=int(st.session_state.concentration_threshold)),
        selected_profile_name,
        cash_target_pct=float(st.session_state.account_target_cash_pct) if is_customer else 0.,
    )
    personalization_settings = build_personalization_settings(portfolio_market_summary)
    personalization_settings["sharpe_scale"] = (
        horizon_factor(st.session_state.get("risk_horizon_months", 12))
        if st.session_state.get("risk_sharpe_basis") == "Vald sparhorisont" else 1.0
    )
    personalization_settings["sharpe_basis_label"] = (
        f"{st.session_state.risk_horizon_months} mån (skalad)"
        if st.session_state.get("risk_sharpe_basis") == "Vald sparhorisont" else "årsbasis"
    )
    portfolio_df = prepare_portfolio(portfolio, selected_profile_config, portfolio_asset_metrics)
    portfolio_df.attrs["cash_value"] = portfolio_market_summary.get("cash_value", 0.)
    metrics = calculate_metrics(portfolio_df, selected_profile_config, portfolio_market_summary)
    insights = detect_imbalances(
        portfolio_df,
        selected_profile_name,
        selected_profile_config,
        personalization_settings,
    )
    if not portfolio_market_summary["risk_valid"]:
        insights = [item for item in insights if "sharpe" not in str(item).lower()]
    trade_plan = build_trade_plan(portfolio_df, int(st.session_state.minimum_trade_size))
    if selected_profile_config["raw_weight_total"] <= 0:
        trade_plan = trade_plan.iloc[:0]
        insights = [{"tone": "info", "title": "Välj din målbild", "body": "Lägg till minst ett instrument med positiv målvikt. Dina befintliga innehav finns kvar i nuläget."}]
    render_module_intro(active_module, selected_profile_name)
    render_source_notice(market_context)
    render_risk_controls(full_price_history)
    cost_settings = render_cost_settings(instrument_universe)

    if active_module == "Rebalansering":
        with st.expander("Anpassa målprofil och risk", expanded=False):
            st.write("")
            st.subheader("Din målbild")
            st.caption(
                "Här anpassar du målprofil, riskramar och målvikter för rebalanseringen."
            )

            settings_profile_tab, settings_questionnaire_tab, settings_risk_tab, settings_weight_tab = st.tabs(
                ["Profil", "Riskprofil-enkät", "Riskramar", "Målvikter"]
            )
            custom_profile_enabled = st.session_state.selected_profile == "Egen profil"

            with settings_profile_tab:
                profile_col, profile_help_col = st.columns([1.15, 0.85], gap="large")

                with profile_col:
                    st.selectbox(
                        "Välj basprofil",
                        options=[*profiles.keys(), "Egen profil"],
                        key="selected_profile",
                        on_change=handle_profile_selection_change,
                    )
                    st.text_input("Namn på din profil", key="profile_name")
                    st.slider(
                        "Riskbenägenhet",
                        min_value=1,
                        max_value=10,
                        step=1,
                        key="risk_appetite",
                        disabled=not custom_profile_enabled,
                    )
                    st.caption(
                        "Standardprofilerna har förvalda riskramar. Ändringar i målbilden aktiverar Egen profil; där kan du också justera risknivå och riskmål."
                    )

                with profile_help_col:
                    st.markdown(
                        f"""
                        <div class="section-card">
                            <strong>Profilstatus</strong>
                            <div class="micro-kpi">
                                <div>
                                    Basprofil
                                    <strong>{st.session_state.selected_profile}</strong>
                                </div>
                                <div>
                                    Risknivå
                                    <strong>{st.session_state.risk_appetite} / 10</strong>
                                </div>
                                <div>
                                    Analys
                                    <strong>{st.session_state.analysis_window}</strong>
                                </div>
                            </div>
                            <div class="mock-note">
                                {"Standardprofilen har förvalda mål för vikt, Sharpe, volatilitet och drawdown. Egna ändringar i målbilden aktiverar Egen profil." if not custom_profile_enabled else "Egen profil är aktiv. Här kan du sätta dina egna riskramar och målvikter."}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if not custom_profile_enabled:
                        st.info("Välj Egen profil för att justera riskmål, eller ändra målvikterna så aktiveras den automatiskt.")
                    else:
                        st.success("Egen profil är aktiv. Dina ändringar påverkar analysen direkt.")

            with settings_questionnaire_tab:
                questionnaire_result = calculate_risk_questionnaire_profile()
                questionnaire_col, questionnaire_summary_col = st.columns([1.1, 0.9], gap="large")

                with questionnaire_col:
                    for question in get_risk_questionnaire():
                        st.selectbox(
                            question["question"],
                            options=[option["label"] for option in question["options"]],
                            key=question["key"],
                        )

                with questionnaire_summary_col:
                    st.markdown(
                        f"""
                        <div class="section-card">
                            <strong>Föreslagen risknivå från enkäten</strong>
                            <div class="micro-kpi">
                                <div>
                                    Risknivå
                                    <strong>{questionnaire_result['risk_level']} / 10</strong>
                                </div>
                                <div>
                                    Poäng
                                    <strong>{questionnaire_result['score_100']:.0f} / 100</strong>
                                </div>
                                <div>
                                    Effekt
                                    <strong>Uppdaterar riskmål</strong>
                                </div>
                            </div>
                            <div class="mock-note">
                                Enkäten väger främst in horisont, reaktion på förlust, mål, erfarenhet och likviditetsbehov.
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.button(
                        "Använd enkätens risknivå",
                        width="stretch",
                        on_click=apply_questionnaire_risk_profile,
                    )
                    st.caption(
                        "När knappen används sätts risknivå 1-10 och modellens föreslagna gränser för års-Sharpe, årsvolatilitet och drawdown. Förslaget bygger på fasta modellregler."
                    )
                    with st.expander("Varför frågorna väger olika mycket"):
                        st.markdown(
                            """
                            - Modellen ger reaktionen på en förlust på 20 % störst vikt som ett antagande om riskvilja vid börsfall.
                            - Placeringshorisont väger nästan lika tungt eftersom längre tidshorisont normalt ger högre riskförmåga.
                            - Mål med sparandet, erfarenhet och likviditetsbehov påverkar också nivån, men bör inte dominera hela profilen på egen hand.
                            """
                        )

            with settings_risk_tab:
                recommended_risk_defaults = get_risk_preference_defaults(int(st.session_state.risk_appetite))
                st.caption(
                    f"Modellens förslag för risknivå {st.session_state.risk_appetite}: "
                    f"års-Sharpe minst {format_decimal_sv(recommended_risk_defaults['min_portfolio_sharpe'])}, "
                    f"årsvolatilitet max {format_pct(recommended_risk_defaults['max_portfolio_volatility'])}, "
                    f"max drawdown {format_pct(recommended_risk_defaults['max_drawdown_tolerance'])}."
                )
                st.button(
                    "Använd modellens förslag",
                    use_container_width=False,
                    on_click=apply_recommended_risk_targets,
                    args=(int(st.session_state.risk_appetite),),
                    disabled=not custom_profile_enabled,
                )

                risk_col_left, risk_col_right = st.columns(2, gap="large")
                with risk_col_left:
                    st.slider(
                        "Minsta historiska Sharpekvot · årsbasis",
                        min_value=-1.0,
                        max_value=2.0,
                        step=0.05,
                        key="min_portfolio_sharpe",
                        disabled=not custom_profile_enabled,
                    )
                    st.slider(
                        "Max historisk volatilitet · årsbasis (%)",
                        min_value=1.0,
                        max_value=40.0,
                        step=0.5,
                        key="max_portfolio_volatility",
                        disabled=not custom_profile_enabled,
                    )
                    st.slider(
                        "Max historisk drawdown (%)",
                        min_value=1.0,
                        max_value=60.0,
                        step=1.0,
                        key="max_drawdown_tolerance",
                        disabled=not custom_profile_enabled,
                    )
                    st.slider(
                        "Gräns för enskilt innehav",
                        min_value=0,
                        max_value=100,
                        step=1,
                        key="concentration_threshold",
                        disabled=not custom_profile_enabled,
                    )

                with risk_col_right:
                    st.slider(
                        "Tolerans över aktiemål innan varning (p.p.)",
                        min_value=0,
                        max_value=30,
                        step=1,
                        key="equity_buffer",
                        disabled=not custom_profile_enabled,
                    )
                    st.slider(
                        "Gräns för avvikelse mot målvikt (p.p.)",
                        min_value=0,
                        max_value=30,
                        step=1,
                        key="category_gap_threshold",
                        disabled=not custom_profile_enabled,
                    )
                    st.slider(
                        "Gräns för tre största innehav tillsammans",
                        min_value=0,
                        max_value=100,
                        step=1,
                        key="top_three_threshold",
                        disabled=not custom_profile_enabled,
                    )
                    st.slider(
                        "Minsta köp/sälj som visas",
                        min_value=0,
                        max_value=25000,
                        step=500,
                        key="minimum_trade_size",
                        disabled=not custom_profile_enabled,
                    )

            with settings_weight_tab:
                render_target_editor()

            if not is_customer and selected_profile_config["raw_weight_total"] > 0 and abs(selected_profile_config["raw_weight_total"] - 100) > 0.01:
                st.info(
                    f"Du har satt målvikter som summerar till {format_pct(selected_profile_config['raw_weight_total'])}. "
                    "Appen normaliserar dem automatiskt till 100 % innan analysen körs."
                )
        st.write("")
    if active_module == "Rebalansering":
        render_optimizer(portfolio_df, full_price_history, instrument_universe, cost_settings)
        st.write("")
        metric_cols = st.columns(5)
        metric_cols[0].metric("Portföljvärde", format_sek(metrics["total_value"]), help=METRIC_HELP["value"])
        metric_cols[1].metric(
            "Aktieexponering",
            format_pct(metrics["equity_exposure"]),
            help=METRIC_HELP["equity"],
            delta=(f"{format_decimal_sv(metrics['equity_gap'], decimals=2, signed=True)} p.p. mot målbild"
                   if selected_profile_config["raw_weight_total"] > 0 and selected_profile_config["equity_target_known"]
                   else ("Blandfonders aktieandel saknas" if selected_profile_config["raw_weight_total"] > 0 else "Välj målvikter")),
            delta_color="off", delta_arrow="off",
        )
        metric_cols[2].metric(
            f"Sharpe · {sharpe_basis_label()}",
            sharpe_display(metrics["portfolio_sharpe"]),
            help=METRIC_HELP["sharpe"],
            delta=f"Mål {sharpe_display(st.session_state.min_portfolio_sharpe)}", delta_color="off", delta_arrow="off",
        )
        metric_cols[3].metric(
            "Volatilitet · årsbasis",
            risk_pct(metrics["portfolio_volatility_pct"]),
            help=METRIC_HELP["volatility"],
            delta=f"Tak {format_pct(st.session_state.max_portfolio_volatility)}", delta_color="off", delta_arrow="off",
        )
        metric_cols[4].metric(
            "Största innehav",
            metrics["largest_name"],
            help=METRIC_HELP["largest"],
            delta=format_pct(metrics["largest_weight_pct"]), delta_color="off", delta_arrow="off",
        )
        render_risk_period_note(analysis_history, portfolio_market_summary)

        st.write("")
        left_col, right_col = st.columns([1.05, 1], gap="large")

        with left_col:
            st.button("Testa den här portföljen →", on_click=open_portfolio_simulation, key="simulate_portfolio")
            st.subheader("Dina innehav · demo/import" if is_customer else "Exempelportfölj")
            valuation_date = portfolio_prices_sek(full_price_history, portfolio.loc[portfolio.value_sek > 0]).index[-1]
            st.caption(f"Kapitalfördelning värderad {valuation_date:%Y-%m-%d}. " + ("Demo/import · likvid ingår i kontovikterna." if is_customer else "Innehaven är exempel; inget kundkonto är anslutet."))
            display_df = portfolio_df[["name", "value_sek", "current_weight_pct", "trailing_1m_pct"]].copy()
            display_df.columns = ["Instrument", "Värde", "Vikt", "1 mån"]
            display_df["Värde"] = display_df["Värde"].map(format_sek)
            display_df["Vikt"] = display_df["Vikt"].map(format_pct)
            display_df["1 mån"] = display_df["1 mån"].map(lambda value: risk_pct(value, signed=True))
            st.dataframe(display_df, width="stretch", hide_index=True)
            with st.expander("Instrument och riskmått"):
                detail = portfolio_df[["name", "ticker", "category", "annual_volatility_pct", "sharpe_ratio"]].copy()
                detail.columns = ["Instrument", "Ticker", "Kategori", "Volatilitet · årsbasis", "Sharpe"]
                detail["Volatilitet · årsbasis"] = detail["Volatilitet · årsbasis"].map(risk_pct)
                detail["Sharpe"] = detail["Sharpe"].map(sharpe_display) if portfolio_market_summary["risk_valid"] else "—"
                st.caption("Sharpe använder samma analysperiod och visningsskala som portföljmåttet ovan. Volatilitet uttrycks på årsbasis.")
                st.dataframe(detail, width="stretch", hide_index=True)

        with right_col:
            st.subheader("Nuvarande viktfördelning")
            explain("Om fördelningen", "Diagrammet visar nuvarande kapitalandelar. I kundläget kompletteras instrumentvikterna med likvidandelen i kontots sammanfattning.")
            allocation_df = portfolio_df.copy()
            if portfolio_market_summary.get("cash_value", 0.) > 0:
                allocation_df = pd.concat([allocation_df, pd.DataFrame([dict(name="Likvida medel", category="Likvida medel", value_sek=portfolio_market_summary["cash_value"])])], ignore_index=True)
            st.plotly_chart(build_current_allocation_chart(allocation_df), width="stretch")

    if active_module == "Rebalansering":
        st.write("")
        insight_col, support_col = st.columns([1.1, 0.9], gap="large")

        with insight_col:
            st.subheader("Vad Portföljkollen ser")
            render_insights(insights)

        with support_col:
            st.subheader("Snabb diagnos")
            st.markdown(
                f"""
                <div class="panel">
                    <strong>Största tre innehav:</strong> {format_pct(metrics["top_three_share"])}<br><br>
                    <strong>Koncentrationsindex:</strong> {metrics["hhi"]}<br><br>
                    <strong>Genomsnittlig avkastning · årsbasis:</strong> {risk_pct(metrics["portfolio_return_pct"], signed=True)}<br>
                    <small>Genomsnittlig dagsavkastning × 252, beräknad över valt analysfönster.</small><br><br>
                    <strong>Historisk drawdown:</strong> {risk_pct(abs(metrics["portfolio_max_drawdown_pct"]))}<br><br>
                    <strong>Din gräns för största innehav:</strong> {selected_profile_config["max_single_holding"]} %<br><br>
                    <strong>Min Sharpe · {sharpe_basis_label()}:</strong> {sharpe_display(st.session_state.min_portfolio_sharpe)}<br><br>
                    <strong>Max volatilitet · årsbasis:</strong> {format_pct(st.session_state.max_portfolio_volatility)}<br><br>
                    <strong>Tolkning:</strong> Analysen följer dina trösklar, dina målvikter och {"simulerade prisserier (exempeldata)" if market_context["is_example"] else "historiska marknadspriser"}.
                </div>
                """,
                unsafe_allow_html=True,
            )

    if active_module == "Rebalansering":
        st.write("")
        st.subheader("Föreslagen målallokering")
        explain("Om målallokeringen", "Målvikterna visar önskad fördelning. Affärsförslaget räknar om vikterna till köp och försäljningar. I kundläget begränsas förslaget av tillåten likvid och dina val om försäljningar.")
        comparison_df = portfolio_df.copy()
        if is_customer and (portfolio_market_summary.get("cash_value", 0.) > 0 or selected_profile_config["cash_target_pct"] > 0):
            comparison_df = pd.concat([comparison_df, pd.DataFrame([dict(name="Likvida medel", category="Likvida medel", current_weight_pct=portfolio_market_summary.get("cash_value", 0.) / metrics["total_value"] * 100, target_weight_pct=selected_profile_config["cash_target_pct"])])], ignore_index=True)
        st.plotly_chart(build_comparison_chart(comparison_df), width="stretch")

        if not is_customer:
            trade_display = trade_plan[
                [
                    "name",
                    "category",
                    "current_weight_pct",
                    "target_weight_pct",
                    "trade_action",
                    "trade_amount",
                ]
            ].copy()
            trade_display.columns = [
                "Instrument",
                "Kategori",
                "Nuvarande vikt",
                "Målvikt",
                "Åtgärd",
                "Belopp",
            ]
            trade_display["Nuvarande vikt"] = trade_display["Nuvarande vikt"].map(format_pct)
            trade_display["Målvikt"] = trade_display["Målvikt"].map(format_pct)
            trade_display["Belopp"] = trade_display["Belopp"].map(format_sek)
            if trade_display.empty:
                st.info(
                    "Inga köp eller sälj visas just nu eftersom alla avvikelser ligger under din valda gräns för minsta affär."
                )
            else:
                st.dataframe(trade_display, width="stretch", hide_index=True)

            largest_sell = trade_plan.loc[trade_plan["trade_action"] == "Sälj"].head(1)
            largest_buy = trade_plan.loc[trade_plan["trade_action"] == "Köp"].head(1)
            if not largest_sell.empty and not largest_buy.empty:
                sell_row = largest_sell.iloc[0]
                buy_row = largest_buy.iloc[0]
                st.info(
                    f"Förslag: minska {sell_row['name']} med {format_sek(sell_row['trade_amount'])} "
                    f"och öka {buy_row['name']} med {format_sek(buy_row['trade_amount'])} som första steg."
                )
            elif trade_display.empty:
                st.info("Portföljen ligger nära dina egna mål eller så har du filtrerat bort små affärer.")

    if active_module == "Rebalansering":
        st.write("")
        if is_customer:
            render_account_actions(portfolio_df, full_price_history, cost_settings)
        else:
            render_trade_costs(portfolio_df, trade_plan, full_price_history, cost_settings)
        if not is_customer:
            with st.expander("Bevakningar och påminnelser · exempel", expanded=False):
                st.subheader("Utforska bevakningar och påminnelser")
                st.caption(
                    "Notisflödet visar exempel på bevakningsnotiser och rebalanseringspåminnelser baserade på portföljens utveckling."
                )

                watch_tab, rebalance_tab = st.tabs(["Bevakade instrument", "Rebalanseringspåminnelse"])

                with watch_tab:
                    watch_control_col, watch_feed_col = st.columns([0.95, 1.05], gap="large")

                    with watch_control_col:
                        watch_selection = st.multiselect(
                            "Vilka instrument vill du bevaka?",
                            options=instrument_universe["company_name"].tolist(),
                            key="watch_selection",
                        )
                        watch_interval = st.selectbox(
                            "Hur ofta vill du få uppdateringar?",
                            options=list(notification_intervals.keys()),
                            index=list(notification_intervals.keys()).index(st.session_state.watch_interval),
                        )
                        watch_notifications = build_watch_notifications(
                            instrument_universe, full_price_history, watch_selection, watch_interval
                        )

                        activate_watch = st.button("Aktivera bevakning", width="stretch")
                        test_watch = st.button("Visa exempelnotiser", width="stretch")

                        if activate_watch:
                            st.session_state.watch_interval = watch_interval
                            st.session_state.watch_active = True
                            st.toast(
                                f"Bevakning aktiv för {len(watch_selection)} instrument med intervallet {watch_interval.lower()}."
                            )

                        if test_watch and not watch_notifications.empty:
                            for _, row in watch_notifications.head(3).iterrows():
                                st.toast(row["notification_text"])

                        st.markdown(
                            f"""
                            <div class="panel">
                                <strong>Status:</strong> {"Aktiv" if st.session_state.watch_active else "Inte aktiv"}<br><br>
                                <strong>Exempel på nästa datum:</strong> {format_date_sv((watch_notifications["next_send_at"].iloc[0] if not watch_notifications.empty else pd.Timestamp.today()))}<br><br>
                                <strong>Intervall:</strong> {watch_interval}
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                    with watch_feed_col:
                        if not watch_notifications.empty:
                            watch_display = watch_notifications[
                                [
                                    "company_name",
                                    "ticker",
                                    "position_value_sek",
                                    "current_price",
                                    "change_pct",
                                    "notification_text",
                                ]
                            ].copy()
                            watch_display.columns = [
                                "Instrument",
                                "Ticker",
                                "Bevakat värde",
                                "Senaste kurs",
                                f"Förändring sedan {notification_intervals[watch_interval]['reference_text']}",
                                "Exempel på notis",
                            ]
                            watch_display["Bevakat värde"] = watch_display["Bevakat värde"].map(format_sek)
                            watch_display["Senaste kurs"] = watch_display["Senaste kurs"].map(
                                lambda x: f"{x:,.2f}".replace(",", " ").replace(".", ",")
                            )
                            change_column = f"Förändring sedan {notification_intervals[watch_interval]['reference_text']}"
                            watch_display[change_column] = watch_display[change_column].map(format_signed_pct)
                            st.dataframe(watch_display, width="stretch", hide_index=True)
                        else:
                            st.info("Välj minst ett instrument för att skapa notiser.")

                        watch_messages = []
                        for _, row in watch_notifications.head(3).iterrows():
                            watch_messages.append(
                                {
                                    "title": f"{row['company_name']} ({row['ticker']})",
                                    "body": row["notification_text"],
                                }
                            )
                        render_notification_cards("Förhandsvisning av pushnotiser", watch_messages, tone="info")

                with rebalance_tab:
                    rebalance_control_col, rebalance_feed_col = st.columns([0.95, 1.05], gap="large")

                    with rebalance_control_col:
                        rebalance_interval = st.selectbox(
                            "När vill du få påminnelse om rebalansering?",
                            options=list(notification_intervals.keys()),
                            index=list(notification_intervals.keys()).index(st.session_state.rebalance_interval),
                            key="rebalance_interval_selector",
                        )
                        rebalance_notification = build_rebalance_notification(
                            portfolio_df, trade_plan, selected_profile_name, rebalance_interval,
                            category_gap_threshold=float(st.session_state.category_gap_threshold),
                        )
                        if selected_profile_config["raw_weight_total"] <= 0:
                            rebalance_notification.update(title="Välj din målbild", short_text="Välj minst ett instrument med positiv målvikt.",
                                                          body="Välj minst ett instrument med positiv målvikt innan en rebalansering kan föreslås.")

                        activate_rebalance = st.button(
                            "Aktivera rebalanseringspåminnelse", width="stretch"
                        )
                        test_rebalance = st.button("Visa exempelpåminnelse", width="stretch")

                        if activate_rebalance:
                            st.session_state.rebalance_interval = rebalance_interval
                            st.session_state.rebalance_active = True
                            st.toast(
                            f"Rebalanseringspåminnelse sparad med intervallet {rebalance_interval.lower()}."
                            )

                        if test_rebalance:
                            st.toast(rebalance_notification["short_text"])

                        st.markdown(
                            f"""
                            <div class="panel">
                                <strong>Status:</strong> {"Aktiv" if st.session_state.rebalance_active else "Inte aktiv"}<br><br>
                                <strong>Exempel på nästa datum:</strong> {format_date_sv(rebalance_notification["next_send_at"])}<br><br>
                                <strong>Profil:</strong> {selected_profile_name}<br><br>
                                <strong>Syfte:</strong> Påminna när portföljen glidit från målvikterna.
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                    with rebalance_feed_col:
                        drift_display = portfolio_df[
                            [
                                "name",
                                "current_weight_pct",
                                "target_weight_pct",
                                "weight_gap_pct",
                                "trailing_1m_pct",
                            ]
                        ].copy()
                        drift_display.columns = [
                            "Innehav",
                            "Nuvarande vikt",
                            "Målvikt",
                            "Avvikelse mot mål",
                            "Senaste månaden",
                        ]
                        drift_display["Nuvarande vikt"] = drift_display["Nuvarande vikt"].map(format_pct)
                        drift_display["Målvikt"] = drift_display["Målvikt"].map(format_pct)
                        drift_display["Avvikelse mot mål"] = drift_display["Avvikelse mot mål"].map(
                            lambda value: f"{format_decimal_sv(value, signed=True)} p.p."
                        )
                        drift_display["Senaste månaden"] = drift_display["Senaste månaden"].map(
                            lambda value: risk_pct(value, signed=True)
                        )
                        st.dataframe(drift_display, width="stretch", hide_index=True)

                        render_notification_cards(
                            "Förhandsvisning av rebalanseringsnotis",
                            [
                                {
                                    "title": rebalance_notification["title"],
                                    "body": rebalance_notification["body"],
                                }
                            ],
                            tone="warning",
                        )

    if active_module == "Testa din strategi":
        st.write("")
        st.subheader("Bygg ditt test")
        st.caption(
            "Prova hur ett belopp hade utvecklats över tid och hur olika fördelningar och rebalanseringar kan påverka historiska utfall."
        )
        active_holdings = portfolio_df.loc[portfolio_df.value_sek > 0].copy()
        simulation_prices = full_price_history.copy()
        simulation_universe = instrument_universe
        source_portfolio = portfolio_df.copy()
        account_cash = float(portfolio_market_summary.get("cash_value", 0.))
        if is_customer and (account_cash > 0 or selected_profile_config["cash_target_pct"] > 0):
            cash_row = dict(name="Likvida medel", ticker="__cash__", current_weight_pct=account_cash / metrics["total_value"] * 100,
                            target_weight_pct=selected_profile_config["cash_target_pct"], value_sek=account_cash)
            if account_cash > 0:
                active_holdings = pd.concat([active_holdings, pd.DataFrame([cash_row])], ignore_index=True)
            source_portfolio = pd.concat([source_portfolio, pd.DataFrame([cash_row])], ignore_index=True)
            simulation_prices["__cash__"] = 1.

        portfolio_simulation_assets = active_holdings["name"].tolist()
        portfolio_simulation_weights = {
            row["name"]: float(row["current_weight_pct"])
            for _, row in active_holdings[["name", "current_weight_pct"]].iterrows()
        }
        goal_holdings = source_portfolio.loc[source_portfolio.target_weight_pct > 0].copy()
        goal_simulation_weights = goal_holdings.set_index("name")["target_weight_pct"].to_dict()

        mock_source = st.radio(
            "Vad vill du simulera?",
            options=["Egna instrument", "Portfölj från Portföljkollen"],
            index=0 if st.session_state.mock_source == "Egna instrument" else 1,
            horizontal=True,
        )
        st.session_state.mock_source = mock_source

        if mock_source == "Egna instrument":
            available_instruments = filter_instruments(instrument_universe)
            mock_assets = st.multiselect(
                "Vilka instrument ska ingå i simuleringen?",
                options=available_instruments,
                key="mock_assets",
            )
        else:
            mock_assets = portfolio_simulation_assets
            simulation_universe = instrument_universe.loc[instrument_universe.ticker.isin(portfolio_df.ticker)].copy()
            if is_customer and (account_cash > 0 or selected_profile_config["cash_target_pct"] > 0):
                simulation_universe = pd.concat([simulation_universe, pd.DataFrame([dict(ticker="__cash__", company_name="Likvida medel", currency="SEK", instrument_type="Likvid", market="FUND")])], ignore_index=True)
            names_by_ticker = source_portfolio.set_index("ticker")["name"].to_dict()
            simulation_universe["company_name"] = simulation_universe.ticker.map(names_by_ticker)
            st.info(
                "Testa din strategi använder instrumenten från Portföljkollen. Välj nuvarande portföljvikter eller målvikter för att granska motsvarande fördelning historiskt."
            )
            portfolio_selection_display = source_portfolio[
                ["name", "ticker", "current_weight_pct", "target_weight_pct"]
            ].copy()
            portfolio_selection_display.columns = [
                "Innehav från Portföljkollen",
                "Ticker",
                "Nuvarande vikt",
                "Målvikt",
            ]
            portfolio_selection_display["Nuvarande vikt"] = portfolio_selection_display[
                "Nuvarande vikt"
            ].map(format_pct)
            portfolio_selection_display["Målvikt"] = portfolio_selection_display["Målvikt"].map(format_pct)
            st.dataframe(portfolio_selection_display, width="stretch", hide_index=True)

        mock_config_col, mock_summary_col = st.columns([1.1, 0.9], gap="large")
        with mock_config_col:
            mock_amount = st.number_input(
                "Belopp för simuleringen",
                min_value=1000,
                max_value=100000000,
                value=int(st.session_state.mock_amount),
                step=1000,
            )
            st.session_state.mock_amount = mock_amount

            available_weight_modes = ["Likavikt", "Anpassad"]
            if mock_source == "Portfölj från Portföljkollen":
                available_weight_modes = ["Nuvarande portföljvikter", "Målvikter", *available_weight_modes]
            if st.session_state.mock_weight_mode not in available_weight_modes:
                st.session_state.mock_weight_mode = available_weight_modes[0]
            mock_weight_mode = st.radio(
                "Hur ska beloppet fördelas?",
                options=available_weight_modes,
                index=available_weight_modes.index(st.session_state.mock_weight_mode),
                horizontal=True,
            )
            st.session_state.mock_weight_mode = mock_weight_mode
            rebalance_modes = list(get_mock_rebalance_modes().keys())
            mock_rebalance_mode = st.radio(
                "Hur ska portföljen hanteras över tid?",
                options=rebalance_modes,
                index=rebalance_modes.index(st.session_state.mock_rebalance_mode),
                horizontal=True,
            )
            st.session_state.mock_rebalance_mode = mock_rebalance_mode
            st.caption(get_mock_rebalance_modes()[mock_rebalance_mode]["description"])

            raw_mock_weights = {}
            if mock_weight_mode == "Nuvarande portföljvikter":
                raw_mock_weights = portfolio_simulation_weights.copy()
                st.caption(
                    "Beloppet fördelas efter de nuvarande vikterna i Portföljkollen, så att Testa din strategi kan användas för att analysera samma portföljhistorik."
                )
            elif mock_weight_mode == "Målvikter":
                mock_assets = goal_holdings["name"].tolist()
                raw_mock_weights = goal_simulation_weights.copy()
                st.caption("Beloppet fördelas efter målvikterna i Portföljkollen. Nya målinstrument ingår även om det nuvarande innehavet är noll.")
            elif mock_weight_mode == "Likavikt":
                raw_mock_weights = {asset: 1.0 for asset in mock_assets}
            else:
                st.markdown("**Sätt egen vikt per instrument**")
                for asset in mock_assets:
                    weight_key = f"mock_weight_{asset}"
                    if weight_key not in st.session_state:
                        st.session_state[weight_key] = 100 / max(len(mock_assets), 1)
                    raw_mock_weights[asset] = st.number_input(
                        asset,
                        min_value=0.0,
                        max_value=100.0,
                        step=1.0,
                        key=weight_key,
                    )

            allocation_preview = {}
            raw_mock_total = 0.0
            if raw_mock_weights:
                allocation_preview, raw_mock_total = normalize_target_weights(raw_mock_weights)

            if mock_weight_mode == "Anpassad" and raw_mock_weights:
                st.caption(
                    f"Egen vikt summerar till {format_pct(raw_mock_total)}. Appen normaliserar automatiskt till 100 %."
                )

        with mock_summary_col:
            preview_items = "".join(
                [
                    f"<div><span>{escape(asset)}</span><strong>{format_pct(weight)}</strong></div>"
                    for asset, weight in allocation_preview.items()
                ]
            )
            st.markdown(
                f"""
                <div class="section-card">
                    <strong>Upplägg för ditt test</strong>
                    <div class="micro-kpi">
                        <div>
                            Belopp
                            <strong>{format_sek(mock_amount)}</strong>
                        </div>
                        <div>
                            Källa
                            <strong>{mock_source}</strong>
                        </div>
                        <div>
                            Antal instrument
                            <strong>{len(mock_assets)}</strong>
                        </div>
                        <div>
                            Rebalansering
                            <strong>{mock_rebalance_mode}</strong>
                        </div>
                    </div>
                    <div class="micro-kpi">
                        {preview_items if preview_items else '<div><span>Välj minst ett instrument</span><strong>0,0 %</strong></div>'}
                    </div>
                    <div class="mock-note">
                        Översikten visar hur beloppet fördelas och hur vald rebalanseringslogik påverkar utvecklingen över tid.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        mock_assets = [asset for asset in mock_assets if raw_mock_weights.get(asset, 0) > 0]
        render_fund_facts(mock_assets, simulation_universe)

        selected_tickers = simulation_universe.loc[simulation_universe.company_name.isin(mock_assets), "ticker"]
        actual_dates = full_price_history.attrs.get("actual_last_dates", {})
        selected_last_dates = [pd.Timestamp(actual_dates.get(ticker, full_price_history[ticker].last_valid_index()))
                               for ticker in selected_tickers if ticker in full_price_history and full_price_history[ticker].notna().any()]
        scenario_last_date = min(selected_last_dates) if selected_last_dates else history_last_date
        max_backtest_date = max(history_first_date, history_last_date - pd.Timedelta(days=1))
        st.subheader("Historisk jämförelse")

        backtest_mode = st.selectbox(
            "Bakåtblick: välj startpunkt",
            options=["Snabbval", "Eget datum"],
            key="mock_backtest_mode",
        )
        if backtest_mode == "Snabbval":
            backtest_interval = st.selectbox(
                "Period",
                options=list(get_mock_backtest_intervals().keys()),
                key="mock_backtest_interval",
            )
            backtest_custom_start = None
        else:
            backtest_calendar_value = pd.Timestamp(st.session_state.mock_backtest_custom_date).normalize()
            if backtest_calendar_value < history_first_date:
                backtest_calendar_value = history_first_date
            if backtest_calendar_value > max_backtest_date:
                backtest_calendar_value = max_backtest_date
            backtest_calendar = st.date_input(
                "Välj startdatum",
                value=backtest_calendar_value.date(),
                min_value=history_first_date.date(),
                max_value=max_backtest_date.date(),
                format="DD/MM/YYYY",
                key="mock_backtest_custom_date",
            )
            st.text_input(
                "Eller skriv datum (ddmmyyyy)",
                key="mock_backtest_custom_text",
                placeholder="01032025",
            )
            backtest_custom_start, backtest_text_valid = resolve_input_date(
                backtest_calendar, st.session_state.mock_backtest_custom_text
            )
            if st.session_state.mock_backtest_custom_text.strip() and not backtest_text_valid:
                st.warning("Kunde inte tolka datumet. Skriv det som ddmmyyyy, till exempel 01032025.")
            backtest_interval = st.session_state.mock_backtest_interval

        if not mock_assets:
            st.info("Välj minst ett instrument för att köra simuleringen bakåt i tiden.")
        elif backtest_mode == "Eget datum" and (
            backtest_custom_start is None or backtest_custom_start < history_first_date
            or backtest_custom_start >= history_last_date
            or (st.session_state.mock_backtest_custom_text.strip() and not backtest_text_valid)
        ):
            st.info("Välj ett giltigt startdatum för att köra simuleringen bakåt i tiden.")
        else:
            start_date = backtest_custom_start
            if start_date is None:
                days = get_mock_backtest_intervals()[backtest_interval]["trading_days"]
                start_date = full_price_history.index[max(0, len(full_price_history) - days - 1)]
            run_simulation(simulation_universe, simulation_prices, mock_assets, raw_mock_weights,
                           mock_amount, mock_rebalance_mode, cost_settings, start_date=start_date)

    if active_module == "Rebalansering" and not is_customer:
        st.write("")
        st.subheader("Ny insättning")
        explain("Om ny insättning", "Insättningen fördelas till de delar som ligger under målvikten. Inga innehav säljs och deras försäljningslikvid används inte. Köpen görs efter valda avgifter; procenten avser köpbehovet efter samma insättning.")

        extra_contribution = st.slider(
            "Extra insättning",
            min_value=1000,
            max_value=20000,
            value=5000,
            step=1000,
        )
        contribution_df = contribution_after_costs(portfolio_df, extra_contribution, full_price_history, cost_settings)
        funded_share, retained_sellers = contribution_message(portfolio_df, contribution_df, extra_contribution)
        financing_note = (
            " Förutsätter att du behåller " + ", ".join(retained_sellers) + " och inte använder försäljningslikvid från dem till köpen."
            if retained_sellers else " Beräkningen använder enbart insättningen och ingen försäljningslikvid."
        )

        contribution_cols = st.columns([1, 1], gap="large")
        with contribution_cols[0]:
            st.plotly_chart(build_contribution_chart(contribution_df), width="stretch")
        with contribution_cols[1]:
            cash_plan = contribution_df.loc[contribution_df["cash_allocation"] >= .01].copy()
            cash_plan = cash_plan.sort_values("cash_allocation", ascending=False)
            cash_display = cash_plan[["name", "cash_allocation", "weight_after_cash_pct"]].copy()
            cash_display.columns = ["Instrument", "Föreslagen insättning", "Vikt efter insättning"]
            cash_display["Föreslagen insättning"] = cash_display["Föreslagen insättning"].map(format_sek)
            cash_display["Vikt efter insättning"] = cash_display["Vikt efter insättning"].map(format_pct)
            st.dataframe(cash_display, width="stretch", hide_index=True)
            if selected_profile_config["raw_weight_total"] > 0:
                st.success(f"Utan försäljningar: {format_sek(extra_contribution)} kan finansiera ungefär {format_pct(funded_share)} av köpbehovet efter insättningen.")
                explain("Villkor för insättningen", financing_note.strip(), key="contribution_financing_help")
            else:
                st.info("Välj positiva målvikter för att fördela insättningen. Beloppet ligger tills vidare kvar som likvid.")

    if active_module == "Rebalansering" and not is_customer:
        st.caption(f"Köp {format_sek(contribution_df.cash_allocation.sum())} · Avgifter {format_sek(contribution_df.attrs['fees'])} · Likvid {format_sek(contribution_df.attrs['uninvested_cash'])}")

    render_data_controls(market_context)

    with st.expander("Så beräknas analysen"):
        st.markdown(
            """
            - Portföljvärdena beräknas från den valda datakällans instrumentpriser och valutakurser.
            - Riskanalysen använder historisk avkastning i SEK, volatilitet, max drawdown och Sharpekvot över det synliga analysfönstret. Årsbasis och vald sparhorisont är separata visningsskalor; faktisk beräkningsperiod och antal observationer redovisas.
            - Riskbenägenhet 1-10 är en heuristisk skala som översätts till mål för Sharpe, volatilitet och drawdown.
            - Rebalanseringen jämför nuvarande vikter mot dina egna målvikter, riskgränser och Sharpe-/volmål.
            - Köp- och säljförslag visas i kronor för att göra förändringarna lätta att förstå och jämföra.
            - Sektionen för ny insättning använder nytt kapital först på de delar som ligger under målvikten.
            - Bevakade instrument använder prisförändringar i den valda datakällan för olika intervall och visar hur en pushnotis kan formuleras.
            - Rebalanseringspåminnelsen visar när portföljen avviker från vald profil och vilka förändringar som kan krävas för att återgå till målvikterna.
            - I Testa din strategi kan du välja mellan buy and hold, månadsvis rebalansering och kvartalsvis rebalansering för att se hur målvikter påverkar utvecklingen över tid.
            - Datakällan visas ovanför analysen. Exempeldata är simulerade prisserier. Marknadsdata använder Avanza NAV för Avanzas egna fonder och Yahoo Finance för övriga instrument och valutakurser. Inga kundkonton är anslutna.
            """
        )



def main() -> None:
    render_css()
    preserve_shared_portfolio_state()
    render_site_header()
    active_module = render_navigation()
    scroll_to_page_start(active_module)
    if active_module == "Översikt":
        render_academy_home()
    else:
        render_tools(active_module)
    render_footer()


if __name__ == "__main__":
    main()
