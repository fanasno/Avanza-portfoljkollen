"""Explicit customer-mode demo. All account data stays in the session."""
from copy import deepcopy
from io import StringIO
import json
import numpy as np
import pandas as pd
import streamlit as st
from account_model import demo_accounts, account_targets, parse_holdings_csv, preview_orders
from portfolio_model import instrument_catalog
from engine import format_sek, format_pct
from help_ui import explain

CONTEXT_KEYS = ("portfolio_holdings", "portfolio_targets", "profile_name", "selected_profile", "risk_appetite",
    "analysis_window", "risk_free_rate_pct", "min_portfolio_sharpe", "max_portfolio_volatility", "max_drawdown_tolerance",
    "concentration_threshold", "equity_buffer", "category_gap_threshold", "top_three_threshold", "minimum_trade_size",
    "cost_account", "cost_class", "account_cash", "account_allow_sales", "account_use_cash", "account_new_deposit", "account_target_cash_pct")


def _key():
    return "learn" if st.session_state.get("workspace_mode", "Lär dig mer") == "Lär dig mer" else st.session_state.get("account_selected", "demo_isk")


def _activate():
    old = st.session_state.get("account_active_context", "learn")
    storage = st.session_state.setdefault("account_contexts", {})
    storage[old] = {key: deepcopy(st.session_state[key]) for key in CONTEXT_KEYS if key in st.session_state}
    current = _key()
    if current in storage:
        for key, value in storage[current].items():
            st.session_state[key] = deepcopy(value)
    elif current != "learn":
        account = st.session_state.account_catalog[current]
        st.session_state.portfolio_holdings = deepcopy(account["holdings"])
        st.session_state.portfolio_targets = account_targets(account)
        st.session_state.profile_name = account["name"]
        st.session_state.selected_profile = "Egen profil"
        st.session_state.cost_account = account["account"]
        st.session_state.cost_class = account["brokerage"]
        st.session_state.account_cash = account["cash"]
        st.session_state.account_allow_sales = True
        st.session_state.account_use_cash = True
        st.session_state.account_new_deposit = 0.
        st.session_state.account_target_cash_pct = 0.
    else:
        st.session_state.account_cash = 0.
    for row in st.session_state.get("portfolio_targets", []):
        for field in ("label", "ticker", "weight"):
            st.session_state[f"goal_{field}_{row['id']}"] = row[field]
    st.session_state.account_active_context = current
    st.session_state.pop("opt_result", None)
    st.session_state.pop("opt_selected", None)
    st.session_state.pop("account_plan", None)


def _save_goal():
    st.session_state.setdefault("account_saved_goals", {})[_key()] = dict(rows=deepcopy(st.session_state.portfolio_targets), cash=st.session_state.account_target_cash_pct)
    st.toast("Målbilden sparad för kontot i den här sessionen.")


def _restore_goal():
    saved = st.session_state.account_saved_goals[_key()]
    rows = deepcopy(saved["rows"])
    st.session_state.account_target_cash_pct = saved["cash"]
    st.session_state.portfolio_targets = rows
    st.session_state.selected_profile = "Egen profil"
    for row in rows:
        for field in ("label", "ticker", "weight"):
            st.session_state[f"goal_{field}_{row['id']}"] = row[field]
    st.session_state.pop("opt_result", None)


def _import_account():
    try:
        upload = st.session_state.account_import_file
        imported = parse_holdings_csv(upload.getvalue(), account=st.session_state.account_import_kind,
                                      cash=st.session_state.account_import_cash)
        st.session_state.account_catalog["imported"] = imported
        st.session_state.setdefault("account_contexts", {}).pop("imported", None)
        st.session_state.account_selected = "imported"
        # Replacing an already selected imported account must not restore its old snapshot.
        if st.session_state.get("account_active_context") == "imported":
            st.session_state.account_active_context = "imported_previous"
        _activate()
        st.session_state.account_import_notice = "Innehaven är inlästa i den här sessionen."
    except (ValueError, UnicodeError) as error:
        st.session_state.account_import_notice = str(error)


def render_account_context():
    if "account_catalog" not in st.session_state:
        st.session_state.account_catalog = demo_accounts()
    st.session_state.setdefault("workspace_mode", "Lär dig mer")
    st.session_state.setdefault("account_selected", "demo_isk")
    st.session_state.setdefault("account_active_context", "learn")
    if st.session_state.account_active_context != _key():
        _activate()
    st.selectbox("Miljö", ["Lär dig mer", "Mitt konto · demo"], key="workspace_mode", on_change=_activate,
                 help="Samma verktyg med en utbildningsportfölj eller ett demokonto/importerade innehav. Ingen bankinloggning ingår.")
    if st.session_state.workspace_mode != "Mitt konto · demo":
        return False
    accounts = st.session_state.account_catalog
    st.selectbox("Konto", list(accounts), format_func=lambda key: accounts[key]["name"],
                 key="account_selected", on_change=_activate)
    account = accounts[st.session_state.account_selected]
    st.caption(f"{account['source']} · {st.session_state.get('cost_account', account['account'])} · Mål och innehav hålls separata per konto i den här sessionen.")
    a, b = st.columns(2)
    a.number_input("Tillgänglig likvid (SEK)", min_value=0., max_value=100000000., step=1000., key="account_cash")
    a.number_input("Ny insättning i förslaget (SEK)", min_value=0., max_value=100000000., step=1000., key="account_new_deposit")
    b.checkbox("Använd likviden för köp", key="account_use_cash")
    b.checkbox("Tillåt försäljningar", key="account_allow_sales")
    b.number_input("Mål för likvid (%)", min_value=0., max_value=100., step=1., key="account_target_cash_pct",
                   help="Denna del av målbilden hålls som likvid. Instrumentvikterna fördelar återstoden.")
    explain("Om kundläget", "Det här är en demonstration av ett tänkt inloggat kundflöde. Demo- eller importerade positioner värderas med vald prisdata. Likvid ingår i kontovärde, vikter och risk med antagen avkastning 0 %. Inga affärer skickas.\n\nMål och importerade innehav stannar i den aktuella sessionen och sparas inte i den gemensamma priscachen. En verklig kontokoppling kräver Avanzas kundmiljö. Spara målbilden i sessionen eller ladda ner den för att behålla en kopia.", key="account_help")
    with st.expander("Importera egna innehav · CSV"):
        upload = st.file_uploader("Innehavsfil", type=["csv"], key="account_import_file")
        c, d = st.columns(2)
        kind = c.selectbox("Kontotyp för import", ["ISK", "AF"], key="account_import_kind")
        st.session_state.setdefault("account_import_cash", 0.)
        cash = d.number_input("Likvid för import (SEK)", min_value=0., step=1000., key="account_import_cash")
        st.download_button("Hämta exempelfil", "instrument;antal;omkostnadsbelopp\nAVANZA:41567;100;30000\nINVE-B.ST;50;12000\n", file_name="exempel-innehav.csv", mime="text/csv", key="account_example_csv")
        explain("Filformat och integritet", "Kolumner: **instrument** (fond-ID, ticker, ISIN eller exakt katalognamn), **antal** och valfritt **omkostnadsbelopp** i SEK. Komma kan användas som decimaltecken i semikolonseparerad CSV. Beloppen värderas om med prisdatan i verktyget. Bara instrument i demokatalogen stöds. AF:s försäljningsskatt kräver omkostnadsbelopp för sålda innehav.")
        st.button("Läs in innehav", key="account_import_apply", disabled=upload is None, on_click=_import_account)
        if st.session_state.get("account_import_notice"):
            st.info(st.session_state.account_import_notice)
    return True


def render_account_actions(portfolio, prices, settings):
    st.subheader("Din målbild på kontot")
    left, right = st.columns(2)
    left.button("Spara målbild för kontot", key="account_save_goal", on_click=_save_goal)
    right.button("Återställ sparad målbild", key="account_restore_goal", on_click=_restore_goal,
                 disabled=_key() not in st.session_state.get("account_saved_goals", {}))
    goal = dict(version=1, account_label=st.session_state.profile_name, cash_target_pct=st.session_state.account_target_cash_pct,
                targets=[{key: row[key] for key in ("ticker", "label", "weight")} for row in st.session_state.portfolio_targets if row.get("ticker")])
    st.download_button("Ladda ner målbild", json.dumps(goal, ensure_ascii=False, indent=2), file_name="min-malbild.json", mime="application/json", key="account_download_goal")
    if sum(row.get("weight", 0) for row in st.session_state.portfolio_targets if row.get("ticker")) <= 0 and st.session_state.account_target_cash_pct < 100:
        st.info("Välj positiva målvikter innan ett affärsförslag kan beräknas.")
        return
    with st.expander("Granska affärsförslag", expanded=True):
        plan = preview_orders(portfolio, prices, settings, cash=float(st.session_state.account_cash),
                              allow_sales=st.session_state.account_allow_sales, use_cash=st.session_state.account_use_cash,
                              new_deposit=float(st.session_state.account_new_deposit))
        if plan["orders"].empty:
            st.info("Inga finansierade affärer föreslås med de valda villkoren.")
        else:
            shown = plan["orders"].copy()
            for column in ("Modellbelopp", "Valda avgifter"):
                shown[column] = shown[column].map(format_sek)
            st.dataframe(shown, hide_index=True, width="stretch")
        a, b, c = st.columns(3)
        a.metric("Valda omställningsavgifter", format_sek(plan["fees"]))
        b.metric("Likvid efter förslaget", format_sek(plan["cash"]))
        tax_label = "Beräknad AF-skatt på försäljning" if settings.account == "AF" else "Skatt på försäljning · ISK"
        tax_value = "Avstängd" if not settings.include_tax else "Underlag saknas" if plan["tax"] is None else format_sek(plan["tax"])
        c.metric(tax_label, tax_value)
        if plan["tax"] is None:
            st.warning("Omkostnadsbelopp saknas för sålda innehav. AF-skatten kan därför inte beräknas.")
        compare = pd.DataFrame({"Instrument": portfolio.name, "Nuvarande vikt": portfolio.current_weight_pct,
            "Målvikt": portfolio.target_weight_pct, "Vikt efter finansierade affärer": plan["after"] / plan["after_total"] * 100})
        compare = pd.concat([compare, pd.DataFrame([{"Instrument": "Likvida medel", "Nuvarande vikt": float(st.session_state.account_cash) / (float(portfolio.value_sek.sum()) + float(st.session_state.account_cash)) * 100,
            "Målvikt": float(st.session_state.account_target_cash_pct), "Vikt efter finansierade affärer": plan["cash"] / plan["after_total"] * 100}])], ignore_index=True)
        for column in compare.columns[1:]:
            compare[column] = compare[column].map(format_pct)
        st.dataframe(compare, hide_index=True, width="stretch")
        st.caption("Modellförslag · inga affärer skickas · valda skattebelopp antas betalas utanför kontot")
        explain("Om affärsförslaget", "Försäljningar och tillgänglig likvid finansierar köp inklusive valda handelsavgifter. Utan försäljningar fördelas bara tillåten likvid. Avgifter och likvidbegränsningar kan ge andra slutvikter än målvikterna.\n\nBeloppen är modellbelopp. Bankens handelsflöde behöver hantera hela aktier, fonders bryttider, okänd NAV och likviddagar. AF-skatt är en uppskattning för dessa försäljningar utifrån angivna omkostnadsbelopp; andra kapitalposter ingår inte. ISK:s löpande skatt jämförs som scenario i strategisimulatorn.")
        st.download_button("Ladda ner affärsförslag", plan["orders"].to_csv(index=False, sep=";", decimal=","),
                           file_name="affarsforslag.csv", mime="text/csv", key="account_download_orders")
