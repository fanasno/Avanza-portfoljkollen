"""Visible Sharpe settings and transparent, comparable risk summaries."""
import numpy as np
import pandas as pd
import streamlit as st
from help_ui import explain
from engine import format_decimal_sv, format_pct
from risk_model import get_risk_windows, horizon_factor, sharpe_from_values, select_risk_history


def render_risk_controls(prices):
    for key, value in {"risk_horizon_months": 12, "risk_sharpe_basis": "Årsbasis",
                       "risk_custom_start": prices.index[max(0, len(prices) - 757)].date(),
                       "risk_custom_end": prices.index[-1].date()}.items():
        if key not in st.session_state:
            st.session_state[key] = value
    with st.container(border=True):
        st.markdown("### Sharpe, historik och sparhorisont")
        a, b = st.columns(2)
        a.selectbox("Historik som används för riskanalys", list(get_risk_windows()), key="analysis_window")
        b.number_input("Riskfri ränta · % per år", min_value=-5., max_value=20., step=.1, key="risk_free_rate_pct")
        if st.session_state.analysis_window == "Egna datum":
            a.date_input("Analys från", key="risk_custom_start")
            b.date_input("Analys till", key="risk_custom_end")
            if st.session_state.risk_custom_start > st.session_state.risk_custom_end:
                st.warning("Analysens startdatum måste vara före slutdatumet.")
        a.number_input("Din sparhorisont · månader", min_value=1, max_value=120, step=1, key="risk_horizon_months")
        b.selectbox("Visa Sharpe på", ["Årsbasis", "Vald sparhorisont"], key="risk_sharpe_basis")
        explain("Historik, årsbasis och horisont", "Historik väljer vilka kursdagar beräkningen bygger på. Årsbasis är en jämförbar årsenhet och betyder inte att bara ett års kurser används. Sparhorisonten ändrar visningsskalan.\n\nHorisontskalan använder års-Sharpe × √(månader/12), under antagande om stabila och okorrelerade avkastningar. Längre spartid ger inte automatiskt bättre avkastning eller ett säkrare utfall.\n\nRiskmålen gäller års-Sharpe. Strategijämförelsen och optimeringen har egna historikval. Kort historik ger osäkrare riskmått.", key="risk_controls_help")



def sharpe_display(annual):
    if not np.isfinite(annual):
        return "—"
    factor = horizon_factor(st.session_state.risk_horizon_months) if st.session_state.risk_sharpe_basis == "Vald sparhorisont" else 1.
    return format_decimal_sv(annual * factor)


def risk_pct(value, signed=False):
    if not np.isfinite(value):
        return "—"
    return f"{format_decimal_sv(value, signed=signed)} %"


def sharpe_basis_label():
    return "årsbasis" if st.session_state.risk_sharpe_basis == "Årsbasis" else f"{st.session_state.risk_horizon_months} mån (skalad)"


def render_risk_period_note(prices, summary):
    if prices.empty:
        st.warning("Inga gemensamma kursdagar finns i det valda analysintervallet.")
        return
    st.caption(f"Riskunderlag i SEK: {prices.index[0]:%Y-%m-%d}–{prices.index[-1]:%Y-%m-%d}, {summary['observations']} dagsavkastningar · Före avgifter och kontoskatt")
    explain("Om riskunderlaget", f"Års-Sharpe: {sharpe_display_annual(summary['sharpe_ratio'])}. Riskfri årsränta: {format_pct(st.session_state.risk_free_rate_pct)}. Nuvarande instrumentvikter används konstant genom historikfönstret. Likvid i kundläget räknas med avkastning noll. Måtten följer den sammansättningen och inte kundens verkliga historiska affärer.", key="risk_period_help")
    if not summary.get("metrics_valid", True):
        st.warning("Avkastning och riskmått visas som — när underlaget saknas, är ogiltigt eller omfattar färre än 20 dagsavkastningar. Inga riskvarningar beräknas från dessa värden.")
        return
    requested = get_risk_windows()[st.session_state.analysis_window]
    if requested and summary["observations"] < requested * .95:
        st.warning("Alla valda fonder har inte hela den begärda historiken. Riskmåtten använder bara deras gemensamma tillgängliga period, som visas ovan. Ingen historik skapas före fondstart.")
    if not summary["risk_valid"]:
        st.warning("Sharpe visas som — när det finns färre än 20 dagsavkastningar eller när volatiliteten är noll. Ett sådant värde går inte att jämföra på ett tillförlitligt sätt.")
    elif summary["observations"] < 252:
        st.caption("Underlaget är kortare än ett år. Ett annualiserat Sharpe-tal från en kort period kan variera kraftigt.")


def sharpe_display_annual(value):
    return format_decimal_sv(value) if np.isfinite(value) else "—"


def render_strategy_sharpe(results, account, future):
    with st.expander("Sharpe för strategierna · vald historik och horisont"):
        rows = []
        actual = None
        for mode, result in results.items():
            key = "isk" if account == "ISK" else "af"
            values = pd.DataFrame(result["history"][key], index=result["dates"])
            # A forecast's dates are in the future, so its complete scenario is
            # assessed. Historical estimates use the chosen observation window.
            if not future:
                values = select_risk_history(values, st.session_state.analysis_window,
                                             st.session_state.get("risk_custom_start"), st.session_state.get("risk_custom_end"))
            estimates = sharpe_from_values(values.to_numpy(), st.session_state.risk_free_rate_pct)
            finite = estimates[np.isfinite(estimates)]
            annual = float(np.median(finite)) if len(finite) else np.nan
            rows.append({"Strategi": mode, "Års-Sharpe": sharpe_display_annual(annual),
                         f"Sharpe · {st.session_state.risk_horizon_months} månader (skalad)": sharpe_display_annual(annual * horizon_factor(st.session_state.risk_horizon_months))})
            actual = values.index
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        if actual is not None and len(actual):
            st.caption(f"Beräkningsperiod: {actual[0]:%Y-%m-%d}–{actual[-1]:%Y-%m-%d}, {len(actual)-1} avkastningar. Underlaget är modellens nettokurva för {account}; valda avgifter, skatter och AF:s försäljningsläge påverkar måttet. Förändringen av startavgifter före första kurvpunkten ingår inte i Sharpe-avkastningarna.")
        st.caption("— betyder otillräckliga data, noll volatilitet eller en nettokurva som når noll/negativa värden. Framtidsvärden är medianen av Sharpe beräknad för varje enskild modellväg, inte Sharpe beräknad från mediankurvan." if future else "— betyder färre än 20 avkastningar, noll volatilitet eller en nettokurva som når noll/negativa värden.")
        st.caption("Skalningen till sparhorisonten är en approximation under antagande om stabila och okorrelerade avkastningar. Använd samma beräkningsperiod och samma skala för att jämföra strategier.")
