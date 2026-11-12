"""Editable instrument cards within the existing target-weight layout."""
from uuid import uuid4
import streamlit as st
from portfolio_model import instrument_catalog, initial_holdings, target_rows_for_profile
from help_ui import explain


def ensure_portfolio_state(profile, legacy_instruments=None):
    if "portfolio_holdings" not in st.session_state:
        st.session_state.portfolio_holdings = initial_holdings(legacy_instruments)
    if "portfolio_targets" not in st.session_state:
        st.session_state.portfolio_targets = target_rows_for_profile(profile, legacy_instruments)


def reset_targets(profile):
    st.session_state.portfolio_targets = target_rows_for_profile(profile)


def _change(row_id, field):
    catalog = instrument_catalog()
    for row in st.session_state.portfolio_targets:
        if row["id"] != row_id:
            continue
        key = f"goal_{field}_{row_id}"
        value = st.session_state[key]
        if field == "ticker":
            if any(other["id"] != row_id and other.get("ticker") == value for other in st.session_state.portfolio_targets):
                st.session_state[key] = row.get("ticker")
                st.session_state.portfolio_editor_notice = "Instrumentet finns redan i målbilden. Ändra vikten på den befintliga raden."
                return
            old_name = catalog.get(row.get("ticker"), {}).get("name", "")
            if not str(row.get("label", "")).strip() or row["label"] == old_name:
                row["label"] = catalog[value]["name"]
                st.session_state[f"goal_label_{row_id}"] = row["label"]
        row[field] = value
        st.session_state.selected_profile = "Egen profil"
        return


def _add():
    st.session_state.portfolio_targets.append(dict(id=uuid4().hex[:12], ticker=None, label="", weight=0.))
    st.session_state.selected_profile = "Egen profil"


def _remove(row_id):
    row = next(row for row in st.session_state.portfolio_targets if row["id"] == row_id)
    for holding in st.session_state.portfolio_holdings:
        if holding["ticker"] == row.get("ticker") and str(row.get("label", "")).strip():
            holding["name"] = row["label"].strip()
    st.session_state.portfolio_targets = [row for row in st.session_state.portfolio_targets if row["id"] != row_id]
    st.session_state.selected_profile = "Egen profil"


def render_target_editor():
    catalog = instrument_catalog()
    explain("Om målvikterna", "Välj instrument, ge varje rad ett eget namn och sätt målvikt. Egna ändringar aktiverar Egen profil. Instrumentets identitet och prisdata följer med när namnet ändras. Borttagna mål med befintligt kapital finns kvar i nuläget med målvikt noll.", key="target_editor_help")
    if st.session_state.get("portfolio_editor_notice"):
        st.info(st.session_state.pop("portfolio_editor_notice"))
    cols = st.columns(2, gap="large")
    for i, row in enumerate(st.session_state.portfolio_targets):
        row_id = row["id"]
        with cols[i % 2], st.container(border=True):
            for field in ("label", "ticker", "weight"):
                key = f"goal_{field}_{row_id}"
                if key not in st.session_state:
                    st.session_state[key] = row[field]
            st.text_input("Namn i din målbild", key=f"goal_label_{row_id}", placeholder="Ditt namn på innehavet",
                          on_change=_change, args=(row_id, "label"))
            st.selectbox("Instrument", options=list(catalog), index=None, placeholder="Sök och välj instrument",
                         format_func=lambda ticker: f"{catalog[ticker]['name']} · {ticker}",
                         key=f"goal_ticker_{row_id}", on_change=_change, args=(row_id, "ticker"))
            a, b = st.columns([3, 1])
            a.number_input("Målvikt (%)", min_value=0., max_value=100., step=1., key=f"goal_weight_{row_id}",
                           on_change=_change, args=(row_id, "weight"))
            b.button("Ta bort", key=f"goal_remove_{row_id}", on_click=_remove, args=(row_id,), help="Tar bort instrumentet ur målbilden. Befintligt innehav behålls i nuläget och får målvikt noll.")
    st.button("＋ Lägg till instrument", key="goal_add", on_click=_add)
    selected = [row for row in st.session_state.portfolio_targets if row.get("ticker")]
    total = sum(row["weight"] for row in selected)
    cash_target = float(st.session_state.get("account_target_cash_pct", 0.)) if st.session_state.get("workspace_mode") == "Mitt konto · demo" else 0.
    st.caption(f"Instrumentvikter: {total:g} % · Likvidmål: {cash_target:g} %. Instrumenten fördelar återstående {100-cash_target:g} % av målbilden." if cash_target else f"Summa valda målvikter: {total:g} %. Positiva målvikter normaliseras till 100 % i analysen.")
    if (not selected or total <= 0) and cash_target < 100:
        st.info("Välj minst ett instrument med positiv målvikt för ett affärsförslag. Nuläget finns kvar.")
