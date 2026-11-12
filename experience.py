"""Akademin navigation, educational entry page, and data provenance."""
from html import escape
from pathlib import Path
import pandas as pd
import streamlit as st
from streamlit.components.v1 import html as component_html
from data import (
    get_category_instrument_lookup, get_fx_tickers, build_live_portfolio_values,
    build_live_watchlist_values, build_yfinance_instrument_universe, slice_price_history,
)
from engine import compute_historical_metrics, get_analysis_windows
from market_data import fetch_price_history, fetch_avanza_nav
from avanza_funds import get_avanza_funds
from risk_model import portfolio_prices_sek, select_risk_history, compute_risk_metrics

ACADEMY = "https://www.avanza.se/lar-dig-mer/avanza-akademin/sparstrategi.html"
PAGES = ["Översikt", "Portföljkollen", "Testa din strategi"]


def render_css():
    st.markdown(f'<style>{Path(__file__).with_name("styles.css").read_text(encoding="utf-8")}</style>', unsafe_allow_html=True)


def render_site_header():
    st.markdown(f"""
<div class="utility-bar"><span>En idé för Avanza Akademin</span><span class="concept-label">Interaktiv prototyp</span></div>
<header class="site-header">
  <a class="brand" href="?sida=oversikt" target="_self" aria-label="Avanza, till översikten">AVANZA<span class="brand-bars" aria-hidden="true"><i></i><i></i><i></i><i></i></span></a>
  <nav aria-label="Avanza"><a href="https://www.avanza.se/start" target="_blank" rel="noopener">Spara &amp; Investera</a><a class="current" href="{ACADEMY}" target="_blank" rel="noopener">Lär dig mer</a><a href="https://www.avanza.se/kundservice.html" target="_blank" rel="noopener">Kundservice</a></nav>
  <a class="academy-link" href="{ACADEMY}" target="_blank" rel="noopener">Avanza Akademin <span aria-hidden="true">↗</span></a>
</header>
""", unsafe_allow_html=True)


def navigate(page: str):
    st.session_state.academy_page = page
    st.query_params["sida"] = {"Översikt": "oversikt", "Portföljkollen": "portfoljkollen", "Testa din strategi": "simulator"}[page]


def render_navigation():
    if "academy_page" not in st.session_state:
        st.session_state.academy_page = {"portfoljkollen": "Portföljkollen", "simulator": "Testa din strategi"}.get(st.query_params.get("sida"), "Översikt")
    page = st.radio("Verktyg för din sparstrategi", PAGES, horizontal=True,
                    key="academy_page", label_visibility="collapsed", on_change=update_query)
    return "Rebalansering" if page == "Portföljkollen" else page


def update_query():
    st.query_params["sida"] = {"Översikt": "oversikt", "Portföljkollen": "portfoljkollen", "Testa din strategi": "simulator"}[st.session_state.academy_page]


def scroll_to_page_start(page):
    if st.session_state.get("_last_rendered_page") != page:
        with st.container(key="scroll-reset"):
            component_html('''<script>
            const main = window.parent.document.querySelector('[data-testid="stMain"]');
            const reset = () => { if (main) main.scrollTo({top: 0, behavior: "instant"}); };
            reset(); setTimeout(reset, 150); setTimeout(reset, 400);
            </script>''', height=0)
    st.session_state._last_rendered_page = page


def open_portfolio_simulation():
    st.session_state.mock_source = "Portfölj från Portföljkollen"
    st.session_state.mock_weight_mode = "Nuvarande portföljvikter"
    navigate("Testa din strategi")


def open_customer_demo():
    st.session_state.workspace_mode = "Mitt konto · demo"
    navigate("Portföljkollen")


def refresh_analysis():
    """Widget callbacks execute before the next complete analysis run."""
    pass


def preserve_shared_portfolio_state():
    # Interrupt Streamlit's cleanup of widgets that are absent on another page.
    # This keeps the selected portfolio intact while exploring the simulator.
    shared = {
        "profile_name", "selected_profile", "risk_appetite", "analysis_window",
        "risk_free_rate_pct", "concentration_threshold", "equity_buffer",
        "category_gap_threshold", "top_three_threshold", "minimum_trade_size",
        "min_portfolio_sharpe", "max_portfolio_volatility", "max_drawdown_tolerance",
        "data_mode", "mock_assets", "watch_selection", "mock_backtest_mode", "mock_future_mode", "mock_backtest_interval",
        "mock_future_horizon", "mock_backtest_custom_date", "mock_future_custom_date",
        "mock_backtest_custom_text", "mock_future_custom_text",
        "workspace_mode", "account_selected", "account_cash", "account_new_deposit", "account_allow_sales", "account_use_cash", "account_target_cash_pct",
        "account_import_kind", "account_import_cash", "opt_selected", "opt_objective", "opt_mode", "opt_window", "opt_start", "opt_end",
        "opt_train_share", "opt_sortino_target", "opt_formula",
    }
    for key in list(st.session_state):
        if key in shared or key.startswith(("target_weight_", "category_instrument_", "risk_", "cost_", "portfolio_", "goal_label_", "goal_ticker_", "goal_weight_")):
            st.session_state[key] = st.session_state[key]


def render_academy_home():
    st.markdown("""
<div class="breadcrumb">Lär dig mer <span>›</span> Avanza Akademin <span>›</span> Sparstrategi</div>
<section class="academy-hero">
  <div class="hero-copy"><div class="eyebrow"><span class="eyebrow-line"></span> SPARSTRATEGI I PRAKTIKEN</div>
    <h1>Lite mer koll.<br>En tydligare <em>sparstrategi.</em></h1>
    <p>Hur hänger din portfölj ihop? Och vad händer om du gör på ett annat sätt? Utforska, jämför och lär dig med två enkla verktyg.</p>
    <div class="hero-note"><span class="small-dot"></span> Prova med en exempelportfölj och fiktiva pengar</div>
  </div>
  <div class="hero-illustration" aria-hidden="true">
    <div class="illustration-grid"></div><div class="orbit orbit-one"></div><div class="orbit orbit-two"></div>
    <div class="allocation-wheel"><div><span>Din portfölj</span><strong>Din målbild.</strong></div></div>
    <div class="float-label label-global"><span></span>Globalt</div><div class="float-label label-rates"><span></span>Räntor</div><div class="float-label label-balance">↗ Hitta din balans</div>
    <div class="illustration-caption">Små justeringar. Större förståelse.</div>
  </div>
</section>
<div class="section-heading"><div><div class="eyebrow">FRÅN KUNSKAP TILL INSIKT</div><h2>Vad vill du utforska?</h2></div><p>Börja där du är. Verktygen hänger ihop.</p></div>
""", unsafe_allow_html=True)
    left, right = st.columns(2, gap="large")
    with left, st.container(border=True, key="portfolio-card"):
        st.markdown("""<div class="tool-card-top"><span class="step-number">01</span><span class="tool-tag">FÖRSTÅ DIN PORTFÖLJ</span><span class="tool-icon" aria-hidden="true">◔</span></div><h3>Lär känna din portfölj</h3><p>Se hur pengarna är fördelade, upptäck obalanser och jämför med den målbild du själv väljer.</p><div class="feature-row"><span>Fördelning</span><span>Målvikter</span><span>Ny insättning</span></div>""", unsafe_allow_html=True)
        st.button("Öppna Portföljkollen →", type="primary", on_click=navigate, args=("Portföljkollen",), width="stretch")
    with right, st.container(border=True, key="simulator-card"):
        st.markdown("""<div class="tool-card-top"><span class="step-number">02</span><span class="tool-tag">PROVA EN IDÉ</span><span class="tool-icon" aria-hidden="true">⌁</span></div><h3>Testa din sparstrategi</h3><p>Prova ett belopp, jämför olika fördelningar och utforska hur rebalansering kan påverka utvecklingen.</p><div class="feature-row"><span>Historisk jämförelse</span><span>Avgifter och skatt</span></div>""", unsafe_allow_html=True)
        st.button("Testa en strategi →", on_click=navigate, args=("Testa din strategi",), width="stretch")
    st.button("Utforska kundläget · demo →", key="open_customer_demo", on_click=open_customer_demo)
    st.markdown(f"""
<section class="learning-strip"><div class="learning-symbol" aria-hidden="true">↗</div><div><h3>Kunskap som gör verktygen mer användbara</h3><p>Läs om riskspridning, portföljfördelning och hur du bygger en strategi att hålla fast vid.</p></div><a href="{ACADEMY}" target="_blank" rel="noopener">Till Avanza Akademin <span aria-hidden="true">↗</span></a></section>
<div class="how-heading"><h2>En enkel väg till mer förståelse</h2></div>
<div class="how-grid"><div><span>1</span><h3>Utforska</h3><p>Utgå från en exempelportfölj eller välj egna instrument i simulatorn.</p></div><div><span>2</span><h3>Jämför</h3><p>Se skillnaden mellan din nuvarande fördelning och dina egna mål.</p></div><div><span>3</span><h3>Prova igen</h3><p>Ändra en vikt, ett belopp eller en strategi och se vad som händer.</p></div></div>
""", unsafe_allow_html=True)


def render_module_intro(active_module: str, profile_name: str):
    portfolio = active_module == "Rebalansering"
    title = "Lär känna din portfölj." if portfolio else "Ge din sparidé en provtur."
    subtitle = "Förstå fördelningen, jämför med dina mål och utforska vägar till bättre balans." if portfolio else "Se hur olika val hade påverkat ett testbelopp. Jämför historisk utveckling före och efter valda avgifter och skatt."
    label = "Portföljkollen" if portfolio else "Testa din strategi"
    st.markdown(f"""<div class="breadcrumb"><a href="?sida=oversikt" target="_self">Sparstrategi</a><span>›</span>{label}</div><section class="module-intro"><div class="eyebrow">SPARSTRATEGI I PRAKTIKEN</div><h1>{title}</h1><p>{subtitle}</p><span class="profile-badge">{'Målbild: ' + escape(profile_name) if portfolio else 'Fiktiva pengar · verkligt lärande'}</span></section>""", unsafe_allow_html=True)


def load_market_context(portfolio_template, watchlist_template, analysis_window, risk_free_rate_pct):
    lookup = get_category_instrument_lookup()
    fx = get_fx_tickers(portfolio_template["currency"].tolist() + watchlist_template["currency"].tolist() + [v["currency"] for v in lookup.values()])
    selectable = [*lookup.values(), *get_avanza_funds()]
    chosen_names = set(st.session_state.get("mock_assets", [])) | set(st.session_state.get("watch_selection", []))
    extras = [row["ticker"] for row in selectable if row["name"] in chosen_names]
    tickers = tuple(sorted(set(portfolio_template["ticker"].tolist() + watchlist_template["ticker"].tolist() + list(fx) + extras)))
    prices = fetch_price_history(tickers, "5y", mode=st.session_state.get("data_mode", "Exempeldata"))
    portfolio = build_live_portfolio_values(portfolio_template, prices)
    cash = float(st.session_state.get("account_cash", 0.)) if st.session_state.get("workspace_mode") == "Mitt konto · demo" else 0.
    portfolio.attrs["cash_value"] = cash
    watchlist = build_live_watchlist_values(watchlist_template, prices)
    universe = build_yfinance_instrument_universe(portfolio, watchlist)
    risk_portfolio = portfolio.loc[portfolio.value_sek > 0]
    sek = portfolio_prices_sek(prices, risk_portfolio)
    analysis = select_risk_history(sek, analysis_window, st.session_state.get("risk_custom_start"), st.session_state.get("risk_custom_end"))
    asset_metrics, summary = compute_risk_metrics(analysis, risk_portfolio.set_index("ticker")["value_sek"].to_dict(), risk_free_rate_pct, cash)
    return dict(full_price_history=prices, analysis_history=analysis, portfolio=portfolio,
                watchlist=watchlist, instrument_universe=universe,
                portfolio_asset_metrics=asset_metrics, portfolio_market_summary=summary,
                source=prices.attrs.get("source", "Okänd"),
                is_example=prices.attrs.get("is_example", False), fallback=False,
                cached=prices.attrs.get("cached", False), fetched_at=prices.attrs.get("fetched_at"))


def render_source_notice(context):
    if context["is_example"]:
        message = "Du utforskar en exempelportfölj med simulerade prisserier. Resultaten visar hur verktygen fungerar och är inte faktisk historisk avkastning."
        if st.session_state.get("workspace_mode") == "Mitt konto · demo":
            message = "Testläge · demo/importinnehav värderas med simulerade exempelkurser. Resultaten är inte faktisk historisk marknadsavkastning."
        st.info(message)
    else:
        last_date = context["full_price_history"].index[-1].strftime("%Y-%m-%d")
        prefix = "Demo/import" if st.session_state.get("workspace_mode") == "Mitt konto · demo" else "Exempelportfölj"
        st.caption(f"{prefix} · Marknadsdata från {context['source']} · Senaste kursdag i underlaget {last_date}.")
        if context.get("cached"):
            st.warning(f"Ny hämtning misslyckades. Analysen använder senast verifierad verklig historik från cachen, hämtad {context['fetched_at']}. Kursdatum redovisas ovan och per instrument.")


def render_data_controls(context):
    with st.expander("Datakälla och exempelportfölj", expanded=context.get("error", False)):
        st.radio("Välj prisdata", ["Marknadsdata", "Exempeldata"], key="data_mode", horizontal=True)
        st.caption(f"Aktiv datakälla: {context['source']}. Exempeldata använder fasta, simulerade serier. Marknadsdata hämtar Avanzas egna fonder som dagligt NAV från Avanza och övriga instrument/valutor från Yahoo Finance.")
        st.caption("Marknadsdata är standard. Exempeldata är ett separat, uttryckligt testläge med påhittade kursrörelser. Hämtningsfel ersätts aldrig automatiskt med exempelkurser.")
        st.write("Avanzas egna fonder identifieras med fond-ID och ISIN. Referens-ETF:er har sina ursprungliga namn. Ingen ETF-serie används som ersättning för en Avanza-fond. Inga kundkonton är anslutna.")
        st.write("Bevakningar och påminnelser visas som exempel i appen. De skickas inte utanför prototypen och sparas endast under den aktuella sessionen.")
        if st.button("Uppdatera prisdata"):
            fetch_price_history.clear()
            fetch_avanza_nav.clear()
            st.rerun()


def render_footer():
    st.markdown(f"""<footer class="site-footer"><div><strong>Investeringar innebär en risk</strong><p>Värdet kan både öka och minska. Historiska resultat och simulerade scenarier är ingen garanti för framtida avkastning.</p></div><div class="footer-bottom"><span>Konceptprototyp för Avanza Akademin · Framtagen av Valerio Fasano</span><a href="{ACADEMY}" target="_blank" rel="noopener">Läs mer om sparstrategi ↗</a></div></footer>""", unsafe_allow_html=True)
