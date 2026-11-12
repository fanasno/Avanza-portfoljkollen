"""Readable percentage returns and deduction details, including on a phone."""
from html import escape
import numpy as np
import streamlit as st
from result_reporting import PERCENTAGE_BASES, deduction_report


def percentage_text(value, signed=False, unit="%"):
    if value is None or not np.isfinite(value):
        return "—"
    rounded = round(float(value), 2)
    if rounded == 0:
        rounded = 0.
    number = format(rounded, "+.2f" if signed else ".2f").replace(".", ",")
    return f"{number} {unit}"


def render_percentage_breakdown(result, account, path, future):
    with st.expander("Vad försvinner i procent? · courtage, avgifter och skatt"):
        key = "cost_percentage_base_future" if future else "cost_percentage_base_history"
        base = st.selectbox("Räkna avdragens procent av", PERCENTAGE_BASES, key=key)
        report = deduction_report(result, account, path, base)
        if future:
            st.caption(f"Modellväg {path + 1}, närmast medianen för {account}. Varje kostnad och procenttal kommer från samma faktiska modellväg, som i avstämningen nedan. Delposterna är inte separata medianer.")
        if report["denominator"] is None:
            st.info("Det finns ingen positiv vinst före avdrag att räkna procent av. Kronbeloppen visas fortfarande. Välj startbeloppet eller slutvärdet före avdrag för en procentuell uppdelning.")
        else:
            amount = f'{report["denominator"]:,.2f}'.replace(",", " ").replace(".", ",")
            st.caption(f"Procentbas: {base.lower()} = {amount} kr. Procentsatserna visar hur stor del av denna summa som dras av; de är inte skattesatsen eller courtagets prislistesats.")
        html = []
        for index, row in enumerate(report["rows"]):
            money = f'{row["amount"]:,.2f}'.replace(",", " ").replace(".", ",") + " kr"
            total_class = " af-sale-total" if index == len(report["rows"]) - 1 else ""
            html.append(f'<div class="af-sale-row percentage-cost-row{total_class}"><span>{escape(row["label"])}</span><strong>{escape(money)}<small>{escape(percentage_text(row["percent"]))}</small></strong></div>')
        st.markdown('<div class="percentage-breakdown">' + "".join(html) + "</div>", unsafe_allow_html=True)
        st.caption("Positiva belopp är avdrag. Negativa belopp är en förbättring eller skattereduktion. Följdeffekten visar hur avgifter och ordergränser ändrar exponeringen och den fortsatta avkastningen.")
        st.caption("Fondavgifter som redan ingår i NAV ligger i kurserna även före valda avdrag och kan inte särredovisas här. Posten extra löpande avgift avser bara ett angivet tillägg utöver kursen.")
        st.markdown(f"Utveckling före avdrag **{percentage_text(report['gross_return'], signed=True)}** → netto **{percentage_text(report['net_return'], signed=True)}**. Påverkan på avkastningen: **{percentage_text(report['return_impact_pp'], signed=True, unit='procentenheter')}**.")
