"""Fund selection and visible facts, separate from price history."""
import pandas as pd
import streamlit as st
from avanza_funds import get_avanza_funds, CATALOG
from engine import format_decimal_sv


def filter_instruments(universe):
    choice = st.selectbox("Visa instrument i listan", ["Alla instrument", "Avanzas egna fonder", "Aktier", "Referens-ETF:er"], key="fund_filter")
    selected = set(st.session_state.get("mock_assets", []))
    if choice == "Avanzas egna fonder":
        mask = universe.ticker.str.startswith("AVANZA:")
    elif choice == "Aktier":
        mask = universe.instrument_type == "Aktie"
    elif choice == "Referens-ETF:er":
        mask = universe.instrument_type == "Fond/ETF"
    else:
        mask = pd.Series(True, index=universe.index)
    st.caption("24 egna Avanza-fonder · sök med fondnamn · tidigare val behålls vid filterbyte")
    return universe.loc[mask | universe.company_name.isin(selected), "company_name"].tolist()


def render_fund_facts(selected_names, universe=None):
    tickers = set(universe.loc[universe.company_name.isin(selected_names), "ticker"]) if universe is not None else set()
    selected = [fund for fund in get_avanza_funds() if fund["name"] in selected_names or fund["ticker"] in tickers]
    with st.expander("Avanzas egna fonder · fondfakta och kurskällor"):
        st.markdown(f"[Avanzas officiella fondutbud]({CATALOG['source']}) · 24 fonder och aktuella andelsklasser kontrollerade {CATALOG['verified_date']}.")
        st.caption("Alla 24 kan väljas i både Portföljkollens målbild och Testa din strategi. Fondnamn och egna visningsnamn är kopplade till samma fond-ID och ISIN.")
        if selected and len(selected) <= 6:
            for fund in selected:
                st.markdown(f"**{fund['name']}**  \nFondkostnad: **{format_decimal_sv(fund['total_fee_pct'])} %/år**, redan i NAV.  \nAndelsvaluta: {fund['currency']} · Fondstart: {fund['start_date']}  \nISIN: {fund['isin']} · [Faktablad]({fund['facts_url']})")
        else:
            rows = [{"Fond": fund["name"], "ISIN": fund["isin"], "Fondkostnad %/år": fund["total_fee_pct"],
                     "Valuta": fund["currency"], "Start": fund["start_date"], "Faktablad": fund["facts_url"]}
                    for fund in selected or get_avanza_funds()]
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", column_config={"Faktablad": st.column_config.LinkColumn("Faktablad", display_text="Läs faktablad")})
        st.caption("Fondkostnaden är Avanzas redovisade totala fondkostnad vid kontrolltillfället, inte ett extra courtage. Den är redan avdragen i verklig NAV-historik. Fondköp/-försäljningar i SEK har inget modellerat courtage eller valutaväxlingspåslag. Fondens egna valutaexponering ligger i NAV.")
        st.caption("Marknadsdata använder fondens egen dagliga NAV-serie, aldrig en omdöpt ETF. Exempeldata är däremot uttryckligen simulerade, inklusive för fonder med verkliga namn. Historik före fondstart skapas inte. En fond kan ha bytt namn eller placeringsinriktning under sin historik.")
        st.caption("Fondaffärer modelleras till vald kursdags NAV. Verkliga bryttider, okänd orderkurs, likviddagar och fördröjning mellan fondförsäljning och återköp ingår inte.")
