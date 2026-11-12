"""Transparent fee, strategy and ISK/AF comparison controls for the prototype."""
from dataclasses import asdict
from html import escape
import hashlib
import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from help_ui import explain
from engine import format_sek, format_pct, format_decimal_sv, simulate_contribution
from risk_model import select_risk_history, portfolio_prices_sek
from risk_ui import render_strategy_sharpe
from result_reporting import development_percent
from percentage_ui import percentage_text, render_percentage_breakdown
from cost_model import (
    Settings, CLASSES, MARKETS, SOURCES, VERIFIED_DATE, MODES, COMPONENTS,
    default_terms, instrument_terms, order_costs, cost_total, buy_with_budget,
    price_inputs, historical_inputs, bootstrap_inputs, simulate_paths,
    representative_path, audit_rows, af_capital_tax, StartOrderWindow,
)


def render_cost_settings(universe):
    defaults = {
        "cost_include": True, "cost_tax": True, "cost_liquidate": True, "cost_af_sale_view": True,
        "cost_fx": .25, "cost_min_order": 0, "cost_other_allowance": 0,
        "cost_future_isk": 1.065, "cost_loss_credit": False,
        "cost_start_eligible": False, "cost_other_avanza": 0, "cost_start_history_data": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    with st.container(border=True, key="cost-settings"):
        st.markdown("### Kostnader och kontoskatt")
        explain("Om avgifter och skatt", "Kryssrutorna styr vilka valbara avdrag som ingår i jämförelserna. Öppna beräkningsdetaljerna för varje post. Fondavgifter som redan ligger i NAV/kursen är redan inräknade och dras inte av igen. I kundläget hämtas kontotypen från valt demo- eller importkonto.", key="cost_controls_help")
        left, right = st.columns(2)
        left.checkbox("Räkna med courtage och valda avgifter", key="cost_include")
        right.checkbox("Räkna med beräknad ISK-/AF-skatt", key="cost_tax")
        left.selectbox("Courtageklass", CLASSES, key="cost_class", disabled=not st.session_state.cost_include)
        right.selectbox("Kontotyp för huvudresultatet", ["ISK", "AF"], key="cost_account", disabled=not st.session_state.cost_tax or st.session_state.get("workspace_mode") == "Mitt konto · demo")
        if st.session_state.cost_account == "AF":
            st.checkbox("AF: visa netto om jag sålde vid varje datum", key="cost_af_sale_view", disabled=not st.session_state.cost_tax,
                        help="Varje punkt visar värdet efter en tänkt försäljning, säljavgifter och beräknad AF-skatt. Försäljningen ändrar inte den fortsatta strategin. Avmarkerat visas bara skatt på redan realiserade vinster och löpande skatteposter.")
        st.checkbox("Sälj och ta ut kapitalet vid slutdatum", key="cost_liquidate",
                    help="Räknar med avslutande säljordrar och realiserar AF-vinster. Avmarkerat behålls innehaven. Om AF:s försäljningsvy är vald visar AF-nettot ändå tänkta säljavgifter och beräknad skatt vid varje datum.")
        with st.expander("Avgifter, skatteutrymme och övriga antaganden"):
            a, b = st.columns(2)
            a.number_input("Växlingspåslag per riktning (%)", min_value=0.0, max_value=5.0, step=.025, format="%.3f", key="cost_fx")
            b.number_input("Minsta rebalanseringsorder (kr)", min_value=0, max_value=1000000, step=100, key="cost_min_order")
            a.number_input("Grundnivå använd av annat sparande (kr/år)", min_value=0, max_value=10000000, step=10000, key="cost_other_allowance",
                           help="Reservera den del av den gemensamma grundnivån som används av ditt övriga ISK/KF/PEPP-sparande. Samma antagande används varje år.")
            b.number_input("Antagen ISK-skatt för 2027 och senare (%)", min_value=.375, max_value=5.0, step=.025, format="%.3f", key="cost_future_isk")
            st.caption("Inkomstår 2026: 1,065 % på kapitalunderlaget över tillgänglig grundnivå, högst 300 000 kr. För 2025 är grundnivån 150 000 kr. Äldre år använder sina fastställda skattesatser. 2027 och senare är ett antagande, inte en fastställd skattesats.")
            st.checkbox("Räkna med möjlig skattereduktion vid underskott", key="cost_loss_credit",
                        help="Förutsätter tillräcklig annan slutlig skatt att reducera. Modellen använder 70 % av kvarvarande aktieförlust, och 30/21 % skattereduktion vid kapitalunderskott. Andra kapitalposter ingår inte.")
            if st.session_state.cost_class == "Start":
                st.checkbox("Jag uppfyller Start-villkoren, har aldrig haft 50 000 kr hos Avanza och har inte förlorat Start tidigare", key="cost_start_eligible")
                st.number_input("Övrigt sparande hos Avanza (kr)", min_value=0, max_value=100000000, step=1000, key="cost_other_avanza")
                st.markdown("**Tidigare gratisaffärer · datum och antal**")
                previous = pd.DataFrame(st.session_state.cost_start_history_data, columns=["Datum", "Antal gratisaffärer"])
                previous["Datum"] = pd.to_datetime(previous["Datum"])
                previous["Antal gratisaffärer"] = pd.to_numeric(previous["Antal gratisaffärer"])
                edited_history = st.data_editor(previous, key="_start_history_editor", num_rows="dynamic", hide_index=True, width="stretch",
                    column_config={"Datum": st.column_config.DateColumn("Datum", required=True),
                                   "Antal gratisaffärer": st.column_config.NumberColumn("Antal gratisaffärer", min_value=0, step=1, required=True)})
                dated_history = []
                for day, count in edited_history.itertuples(index=False, name=None):
                    if pd.isna(day) and pd.isna(count):
                        continue
                    if pd.isna(day) or pd.isna(count) or not np.isfinite(count) or count < 0 or int(count) != count:
                        st.warning("Ange ett giltigt datum och ett helt antal gratisaffärer på varje rad.")
                        st.stop()
                    dated_history.append({"Datum": pd.Timestamp(day).date(), "Antal gratisaffärer": int(count)})
                st.session_state.cost_start_history_data = dated_history
                st.caption("Tom historik betyder att inga gratisaffärer antas före modellstart. Endast rader före respektive beräknings startdatum används. Affärer äldre än tolv månader lämnar räkningsperioden.")
                st.caption("Start gäller aktier på Stockholmsbörsen. Övrig handel följer Mini. Modellen räknar högst 500 gratisaffärer under en rullande tolvmånadersperiod. Nästa sådan affär inom perioden följer Mini och avslutar Start permanent. När samlat Avanza-värde når 50 000 kr upphör Start också permanent. Samma villkor används i historiska scenarier.")

        saved = st.session_state.get("cost_terms_data", {})
        rows = []
        for row in universe.to_dict("records"):
            t = default_terms(row)
            t.update(saved.get(row["ticker"], {}))
            rows.append({"Instrument": row["company_name"], "Ticker": row["ticker"],
                         "Marknad": MARKETS[t["market"]][0], "Fond/ETF": t["fund"], "Räntefond": t["interest_fund"],
                         "Spread %": t["spread"] * 100, "Extra avgift %/år": t["annual_extra"] * 100,
                         "Utdelning %/år": t["dividend_yield"] * 100,
                         "Källskatt kvar %": t["withholding"] * 100,
                         "Köpskatt %": t["buy_tax"] * 100, "Extra kr/order": t["fixed_extra"]})
        with st.expander("Antaganden per instrument · spread, utdelning och extra avgifter"):
            st.caption("0 betyder att posten antas vara noll i modellen, inte att en faktisk nollkostnad har verifierats. Fondens redan kursinbakade avgift ska inte dras av igen. Ange endast ett extra värdeavdrag utöver kursen.")
            st.caption("Utdelning är ett antaget bruttoårsbelopp som delas ut jämnt över tiden. Den läggs inte till avkastningen igen: justerade kurser innehåller redan återinvestering. Separata återinvesteringsordrar och deras courtage ingår inte. Källskatt kvar avser den del av utdelningen som inte återfås eller avräknas; eventuell återbetalningstid modelleras inte.")
            cols = {
                name: st.column_config.NumberColumn(name, min_value=0.0, max_value=maximum, step=.01, format="%.3f", required=True)
                for name, maximum in [("Spread %", 10.), ("Extra avgift %/år", 20.), ("Utdelning %/år", 30.), ("Källskatt kvar %", 35.), ("Köpskatt %", 10.), ("Extra kr/order", 10000.)]
            }
            signature = "_".join(universe.ticker.astype(str))
            edited = st.data_editor(pd.DataFrame(rows), key="_cost_terms_editor_" + signature,
                                    hide_index=True, width="stretch", column_config=cols,
                                    disabled=["Instrument", "Ticker", "Marknad", "Fond/ETF", "Räntefond"])
            terms = {}
            for base_row, edited_row in zip(universe.to_dict("records"), edited.to_dict("records")):
                t = default_terms(base_row)
                for label, key in [("Spread %", "spread"), ("Extra avgift %/år", "annual_extra"), ("Utdelning %/år", "dividend_yield"), ("Källskatt kvar %", "withholding"), ("Köpskatt %", "buy_tax")]:
                    value = edited_row[label]
                    t[key] = 0.0 if pd.isna(value) else float(value) / 100
                value = edited_row["Extra kr/order"]
                t["fixed_extra"] = 0.0 if pd.isna(value) else float(value)
                terms[base_row["ticker"]] = t
            st.session_state.cost_terms_data = terms
        with st.expander(f"Prislista och skatteregler · kontrollerat {VERIFIED_DATE}"):
            table = []
            for name in CLASSES:
                i = CLASSES.index(name) if name != "Start" else 0
                se_rate, se_min = MARKETS["SE"][2][i]
                us_rate, us_min = MARKETS["US"][2][i]
                table.append({"Klass": name, "Svenska aktier": "0 kr när villkoren uppfylls" if name == "Start" else f"{format_pct(se_rate * 100)}, minst {format_sek(se_min)}",
                              "USA · aktier och ETF": f"{format_pct(us_rate * 100)}, minst {us_min:g} USD"})
            st.dataframe(pd.DataFrame(table), hide_index=True, width="stretch")
            st.write("Fast Pris gäller 99 kr för svenska aktier; svensknoterade ETF:er har i stället 0,045 %, minst 99 kr. Vanliga fonder har normalt inget onlinecourtage. Brummerundantag, andra marknadsplatser och administrativa avgifter framgår av prislistan.")
            st.write("Avanzas kontoavgifter för ISK och AF är 0 kr enligt kontoprislistan. Det är separat från instrumentens fondavgifter och övriga handelskostnader.")
            st.write("Modellen omfattar ordinarie onlinehandel i valda aktier, referens-ETF:er och vanliga fonder, inklusive Avanzas egna fonder. Instrumentets marknadsplats och fondtyp styr avgifter och skatt. Private Banking/Pro, telefonorder, belåning och derivat ingår inte. Amerikanska referens-ETF:ers köpbarhet hos Avanza är inte verifierad.")
            for label, url in SOURCES.items():
                st.markdown(f"[{label}]({url})")
            st.caption(f"Courtage och förvalt växlingspåslag bygger på prislistan kontrollerad {VERIFIED_DATE}. Tabellen uppdateras inte automatiskt. Spread, produktspecifika extraavgifter, utdelningar och ej återfådd källskatt behöver anges ovan för att ingå. Fondavgifter som redan ligger i NAV kan inte kryssas bort och dras inte av en gång till. Eventuell avgiftsåterbetalning för Start modelleras inte.")
        st.caption(f"Prislista kontrollerad {VERIFIED_DATE} · samma prisantagande används i historiken")
    return Settings(
        include_costs=st.session_state.cost_include, include_tax=st.session_state.cost_tax,
        brokerage_class=st.session_state.cost_class, account=st.session_state.cost_account,
        fx_rate=st.session_state.cost_fx / 100, liquidate=st.session_state.cost_liquidate,
        af_sale_view=st.session_state.cost_af_sale_view,
        min_rebalance=float(st.session_state.cost_min_order),
        allowance_used_elsewhere=float(st.session_state.cost_other_allowance),
        future_isk_rate=st.session_state.cost_future_isk / 100,
        include_loss_credit=st.session_state.cost_loss_credit,
        start_eligible=st.session_state.get("cost_start_eligible", False),
        other_avanza_assets=float(st.session_state.get("cost_other_avanza", 0)),
        previous_free_order_history=tuple((str(row["Datum"]), int(row["Antal gratisaffärer"])) for row in st.session_state.cost_start_history_data), terms=terms,
    )


@st.cache_data(ttl=1800, max_entries=3, show_spinner=False, hash_funcs={
    pd.DatetimeIndex: lambda index: index.asi8.tobytes(),
    np.ndarray: lambda array: hashlib.sha256(str(array.shape).encode() + array.dtype.str.encode() + array.tobytes()).hexdigest(),
    Settings: lambda settings: json.dumps(asdict(settings), sort_keys=True),
})
def comparison(inputs, terms, weights, amount, settings):
    return {mode: simulate_paths(**inputs, terms=terms, weights=weights, amount=amount, mode=mode, settings=settings,
                                 record=inputs["returns"].shape[1] == 1) for mode in MODES}


def _money(value):
    return f"{float(value):,.2f}".replace(",", " ").replace(".", ",") + " kr"


def _money_frame(frame):
    result = frame.copy()
    for name in result.columns:
        if pd.api.types.is_numeric_dtype(result[name]) and name != "År":
            result[name] = result[name].map(_money)
    return result


def render_af_sale_preview(result, settings, future, path):
    with st.expander("AF · om jag sålde vid valt datum", expanded=False):
        dates = result["dates"]
        chosen = st.date_input("Datum för tänkt försäljning", value=dates[-1].date(),
                               min_value=dates[0].date(), max_value=dates[-1].date(),
                               key="af_sale_date_future" if future else "af_sale_date_history")
        index = int(dates.searchsorted(pd.Timestamp(chosen), side="right") - 1)
        date = dates[index]
        history = result["history"]
        realized_tax = history["af_tax_realized"][index, path]
        sale_tax = history["af_tax_if_sold"][index, path] - realized_tax
        rows = [
            ("Värde efter redan genomförda handelsavgifter", history["after_costs"][index, path]),
            ("Säljavgifter om kvarvarande innehav såldes", -history["af_sale_costs"][index, path]),
            ("Redan realiserad och löpande AF-skatt", -realized_tax),
            ("Ytterligare AF-skatt vid tänkt försäljning", -sale_tax),
            ("Kvar efter försäljning och all beräknad AF-skatt", history["af_if_sold"][index, path]),
        ]
        st.caption(f"Beräkningsdatum: {date:%Y-%m-%d}. Helger använder föregående tillgängliga kursdag. Varje datum är ett eget försäljningsscenario; ingen försäljning görs i den fortsatta simuleringen.")
        if future:
            st.caption(f"Visar modellväg {path + 1}, samma faktiska väg som i avstämningen nedan. Beloppen är ett framtidsscenario, inte en prognos för en bestämd kursdag eller separata medianer.")
        breakdown = "".join(
            f'<div class="af-sale-row percentage-cost-row{(" af-sale-total" if i == len(rows) - 1 else "")}"><span>{escape(label)}</span><strong>{escape(_money(value))}<small>{escape(percentage_text(float(development_percent(value, result["initial_amount"])) if i in (0, len(rows)-1) else value / result["initial_amount"] * 100, signed=True))}{" utveckling" if i in (0, len(rows)-1) else " av startbeloppet"}</small></strong></div>'
            for i, (label, value) in enumerate(rows)
        )
        st.markdown(f'<div class="af-sale-breakdown">{breakdown}</div>', unsafe_allow_html=True)
        st.write(f"Ytterligare vinst/förlust efter säljavgifter: {_money(history['af_sale_gain'][index, path])}. Skatten använder omkostnadsbelopp i SEK och kvittning mot samma års redan realiserade resultat.")
        if index == len(dates) - 1 and settings.liquidate:
            st.caption("Vid slutdatum har innehaven redan sålts enligt ditt avslutsval. Säljavgifter ingår därför i värdet och vinstskatten i redan realiserad AF-skatt; de dras inte av igen.")
        if not settings.af_sale_view:
            st.caption("Huvudkurvan visar bara redan realiserad skatt. Slå på AF:s försäljningsläge ovan för att använda nettot vid tänkt försäljning även i kurvan och strategijämförelsen.")


def render_result(results, selected, inputs, terms, weights, amount, settings, future=False):
    result = results[selected]
    key = "isk" if settings.account == "ISK" else "af"
    final = result["history"][key][-1]
    median = float(np.median(final))
    qualifier = "efter valda avgifter och skatt" if settings.include_tax else "efter valda avgifter · skatt avstängd"
    if settings.account == "AF" and settings.include_tax:
        qualifier += " vid tänkt försäljning" if settings.af_sale_view else " på redan realiserade och löpande poster"
    if future:
        st.info(f"Medianutfallet {qualifier} är {format_sek(median)}, en utveckling på {percentage_text(float(development_percent(median, amount)), signed=True)} sedan start. I 80 % av modellvägarna ligger slutvärdet mellan {format_sek(np.percentile(final, 10))} och {format_sek(np.percentile(final, 90))}. Kontotyp: {settings.account}.")
    else:
        st.success(f"Med {format_sek(amount)} vid start är slutvärdet {format_sek(median)} {qualifier} ({format_decimal_sv((median / amount - 1) * 100, signed=True)} %). Kontotyp: {settings.account}.")
    metrics = st.columns(4 if settings.include_tax else 2)
    metric_rows = [("Före valda avdrag", "gross"), ("Efter valda avgifter", "after_costs")]
    if settings.include_tax:
        metric_rows += [("Efter skatt · ISK", "isk"), ("AF · om såld" if settings.af_sale_view else "AF · realiserat", "af")]
    for column, (label, line) in zip(metrics, metric_rows):
        value = float(np.median(result["history"][line][-1]))
        column.metric(label, format_sek(value), delta=f"{percentage_text(float(development_percent(value, amount)), signed=True)} sedan start",
                      delta_color="off", delta_arrow="off")
    impact = (median - float(np.median(result["history"]["gross"][-1]))) / amount * 100
    st.markdown(f"**Påverkan av valda avdrag och följdeffekter · {settings.account}: {percentage_text(impact, signed=True, unit='procentenheter')}**.")
    if future:
        st.caption("Påverkan ovan är skillnaden mellan medianutfallen före avdrag och efter valda avdrag. Detaljuppdelningen visar en enda faktisk modellväg och kan därför ha andra belopp.")
    explain("Så räknas nettot", "Alla belopp och omkostnadsbelopp räknas i SEK med prisseriens valutakurser. Skatt reserveras i nettovärdet och antas betalas utanför portföljen. Inga extra försäljningar för att finansiera skatten antas.\n\n" + ("AF:s försäljningsvy räknar med en tänkt försäljning vid varje datum, inklusive säljavgifter och skatt på kvarvarande vinst. Värderingen ändrar inte strategins innehav." if settings.af_sale_view else "AF:s realiserade läge drar endast av skatt på redan realiserade och löpande poster. Latent vinstskatt ingår inte."), key="net_result_help_future" if future else "net_result_help_history")
    if settings.include_tax:
        st.caption(f"Nettovy: {settings.account}" + (" · om såld" if settings.account == "AF" and settings.af_sale_view else ""))
    if settings.include_tax and np.all(np.abs(result["tax_isk"]) < .000001):
        st.caption("ISK-skatt: 0 kr · underlaget ryms inom tillgänglig grundnivå")
    if any(item["assumed"] for item in result["annual"].values()):
        st.warning(f"För 2027 och senare används din antagna ISK-skatt {format_pct(settings.future_isk_rate * 100)} och antagen oförändrad grundnivå. Dessa framtida regler är inte fastställda per 3 november 2026.")
    if (result["initial_values"][0] <= .000001).any():
        st.warning("Alla valda instrument ryms inte inom startbeloppet efter minimiavgifterna. Mindre köp hoppas över; se orderlistan för den fördelning som faktiskt kan genomföras.")
    if settings.include_tax and any(t["dividend_yield"] == 0 for t in terms):
        st.caption("Utdelningshistorik är inte hämtad. Med 0 i antagen utdelning separeras ingen utdelningsskatt under innehavstiden; totalavkastningens vinst beskattas vid AF-försäljning. Ange utdelningsantaganden för att jämföra löpande skatt och latent skatt bättre.")

    unit_key = "cost_result_view_future" if future else "cost_result_view_history"
    unit = st.radio("Visa utvecklingen som", ["Procent (%)", "Kronor (kr)"], horizontal=True, key=unit_key)
    percent_view = unit == "Procent (%)"
    st.caption("Utveckling räknas från hela startbeloppet, även vid första kurvpunkten. Köpavgifter och eventuell tänkt säljavgift kan därför ge en negativ utveckling redan vid start. Måttet är periodens sammanlagda utveckling, inte avkastning per år.")
    chart = go.Figure()
    colors = {"gross": "#A6B6AE", "after_costs": "#256774", "isk": "#008568", "af": "#BC9050"}
    labels = {"gross": "Före avdrag", "after_costs": "Efter avgifter", "isk": "Netto ISK", "af": "AF om såld" if settings.af_sale_view else "AF realiserat"}
    for line in ["gross", "after_costs"] + (["isk", "af"] if settings.include_tax else []):
        kronor = np.median(result["history"][line], axis=1)
        percentages = development_percent(kronor, amount)
        y = percentages if percent_view else kronor
        extra_data = [kronor, percentages]
        extra_hover = ""
        if line == "af" and not future and settings.af_sale_view:
            extra_data += [result["history"]["af_tax_if_sold"][:, 0], result["history"]["af_sale_costs"][:, 0]]
            extra_hover = "<br>Total AF-skatt: %{customdata[2]:,.2f} kr<br>Ytterligare säljavgifter: %{customdata[3]:,.2f} kr"
        chart.add_trace(go.Scatter(x=result["dates"], y=y, name=labels[line], line=dict(color=colors[line], width=2.6 if line == key else 1.6),
                                  customdata=np.column_stack(extra_data), hovertemplate="%{x|%Y-%m-%d}<br>Värde: %{customdata[0]:,.2f} kr<br>Utveckling: %{customdata[1]:+.2f} %" + extra_hover + "<extra>%{fullData.name}</extra>"))
    if future:
        upper = np.percentile(result["history"][key], 90, axis=1)
        lower = np.percentile(result["history"][key], 10, axis=1)
        chart.add_trace(go.Scatter(x=result["dates"], y=development_percent(upper, amount) if percent_view else upper, line=dict(width=0), showlegend=False, hoverinfo="skip"))
        band_color = "rgba(0,133,104,.10)" if settings.account == "ISK" else "rgba(188,144,80,.12)"
        chart.add_trace(go.Scatter(x=result["dates"], y=development_percent(lower, amount) if percent_view else lower, line=dict(width=0), fill="tonexty", fillcolor=band_color, name=f"P10–P90 {settings.account}", hoverinfo="skip"))
    if percent_view:
        chart.add_hline(y=0, line_width=1, line_dash="dot", line_color="#B6C4BC")
    chart.update_layout(height=390, margin=dict(l=10, r=10, t=65, b=30), legend=dict(orientation="h", y=1.02, yanchor="bottom", traceorder="normal", font=dict(size=10)),
                        font=dict(family="DM Sans, Arial, sans-serif", size=11), separators=", ", yaxis_title="Utveckling sedan start (%)" if percent_view else "Värde i SEK",
                        yaxis=dict(ticksuffix=" %" if percent_view else ""),
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(chart, width="stretch", config={"displayModeBar": False}, key="net_chart_future" if future else "net_chart_history")
    render_strategy_sharpe(results, settings.account, future)
    st.markdown("#### Jämför strategier med samma underlag")
    rows = []
    for mode, item in results.items():
        def table_value(line):
            value = float(np.median(item["history"][line][-1]))
            return percentage_text(float(development_percent(value, amount)), signed=True) if percent_view else _money(value)
        row = {"Strategi": mode, "Före valda avdrag": table_value("gross"), "Efter avgifter": table_value("after_costs")}
        if settings.include_tax:
            row.update({"Efter skatt · ISK": table_value("isk"), "AF · om såld" if settings.af_sale_view else "AF · realiserat": table_value("af")})
        row["Avdragens påverkan · p.p."] = percentage_text((float(np.median(item["history"][key][-1])) - float(np.median(item["history"]["gross"][-1]))) / amount * 100, signed=True, unit="p.p.")
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption("Procentkolumnerna visar sammanlagd utveckling från startbeloppet. p.p. betyder procentenheter och jämför före avdrag med nettot för vald kontotyp.")
    if future:
        st.caption("Tabellen visar medianer, beräknade separat från samma 1 000 slumpvägar. Skillnaden mellan två medianer är inte medianen av varje kostnadspost. Nedan stämmer vi därför av en enda faktisk modellväg.")
    representative = representative_path(result, settings.account) if future else 0
    render_percentage_breakdown(result, settings.account, representative, future)
    if settings.account == "AF" and settings.include_tax:
        render_af_sale_preview(result, settings, future, representative)
    with st.expander("Så räknas nettovärdet · kostnad för kostnad", expanded=False):
        if future:
            st.caption(f"Modellväg {representative + 1} av 1 000, närmast medianen för {settings.account}. Samma väg används för samtliga poster i avstämningen.")
        audit = pd.DataFrame(audit_rows(result, settings.account, representative), columns=["Post", "Belopp"])
        audit["Belopp"] = audit["Belopp"].map(_money)
        st.dataframe(audit, hide_index=True, width="stretch")
        exit_text = (
            "Avslutande säljordrar och deras avgifter ingår."
            if settings.liquidate else (
                "Innehaven behålls i strategin. AF-nettot i försäljningsvyn inkluderar tänkta säljavgifter och beräknad skatt. De tänkta orderna ingår inte i orderantalet."
                if settings.include_tax and settings.af_sale_view else
                "Innehaven behålls; inga avslutande säljordrar eller tänkta säljavgifter räknas av i den valda nettovyn."
            )
        )
        st.write(f"Antal köp- och säljordrar: {int(result['orders'][representative])}. Prislista kontrollerad {VERIFIED_DATE}. {exit_text}")
        if result["external_exit_cash"][representative] > .01:
            st.warning(f"För att genomföra avvecklingen i denna modellväg krävs {format_sek(result['external_exit_cash'][representative])} extra kontanter eftersom avgifterna överstiger försäljningslikviden.")
        if not settings.liquidate:
            st.write(f"Orealiserad vinst/förlust på AF före tänkta säljavgifter: {format_sek(result['latent_gain'][representative])}. " + ("AF-nettot inkluderar säljavgifter och ytterligare skatt som om innehaven såldes vid slutdatum; dessa är separata från genomförda order och realiserad skatt." if settings.af_sale_view and settings.include_tax else "Ingår inte som realiserad vinstskatt i kurvan."))
        annual_rows = []
        for year, item in result["annual"].items():
            p = representative
            annual_rows.append({"År": year, "ISK kapitalunderlag": item["capital_base"][p],
                                "Tillgänglig grundnivå": item["allowance"], "ISK-skatt": item["isk"][p],
                                "AF realiserat · aktier/aktiefonder": item["equity_gains"][p],
                                "AF realiserat · räntefonder": item["interest_gains"][p],
                                "Antagen utdelning": item["dividends"][p], "Fondvärde 1 januari": item["fund_opening"][p],
                                "AF-skatt · realiserat och löpande": item["af"][p], "Ej återfådd källskatt": item["withholding"][p]})
        st.dataframe(_money_frame(pd.DataFrame(annual_rows)), hide_index=True, width="stretch")
        if settings.af_sale_view and settings.include_tax:
            st.caption("Årstabellen visar genomförd handel och löpande skatt. Ytterligare skatt vid tänkt AF-försäljning redovisas separat ovan och räknas in i AF-nettot.")
        if not settings.include_tax:
            st.caption("Skattebeloppen ovan är en separat upplysning. Skatt är avstängd och dras inte av från kurvor eller slutvärden.")
        st.caption("ISK = (kvartalsvärden + insättningar)/4, därefter årets grundnivå och skattesats. Startbeloppet räknas som en ny insättning; inget konto antas finnas före start, och inga ytterligare insättningar antas. Avslut innebär uttag. AF använder genomsnittligt omkostnadsbelopp inklusive köpavgifter och säljer med avdrag för säljavgifter. Fond-/ETF-schablon är 0,12 % av fondvärdet vid årets ingång före personliga kvittningar. Andra kapitalinkomster, räntor och personliga avdrag ingår inte.")
        st.caption("Rebalansering säljer övervikt när försäljningslikviden täcker avgiften och fördelar nettolikviden till undervikt. Köpavgifter ryms inom kassan. Därför kan slutvikterna avvika lite från målvikterna. Jämförelsen före avdrag använder idealisk rebalansering; följdeffekten omfattar också vald ordergräns.")

    with st.expander("Orderlista för valt resultat"):
        audit_result = result
        if future:
            single = dict(inputs, returns=inputs["returns"][:, representative:representative + 1, :],
                          fx_returns=inputs["fx_returns"][:, representative:representative + 1, :])
            audit_result = simulate_paths(**single, terms=terms, weights=weights, amount=amount,
                                          mode=selected, settings=settings, record=True)
        ledger = audit_result["ledger"]
        st.dataframe(_money_frame(ledger), hide_index=True, width="stretch")
        st.download_button("Ladda ner orderlista (CSV)", ledger.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                           file_name="strategi-orderlista.csv", mime="text/csv", key="orders_future_csv" if future else "orders_history_csv")


def run_simulation(universe, prices, selected_assets, weights, amount, selected_mode, settings, start_date=None, end_date=None):
    selected = universe.loc[universe.company_name.isin(selected_assets)].copy()
    if selected.empty:
        st.info("Välj minst ett instrument för att köra simuleringen.")
        return
    vector = np.array([weights.get(name, 0) for name in selected.company_name], dtype=float)
    mask = vector > 0
    selected, vector = selected.loc[mask].copy(), vector[mask]
    if selected.empty:
        st.info("Välj minst ett instrument med positiv vikt.")
        return
    try:
        sek, fx, terms = price_inputs(selected, prices, settings)
        if end_date is None:
            sek = sek.loc[sek.index >= pd.Timestamp(start_date)]
            fx = fx.reindex(sek.index)
            if len(sek) < 2:
                raise ValueError("Välj ett giltigt startdatum med minst två prisdagar.")
            inputs = historical_inputs(sek, fx)
            st.caption(f"Historisk jämförelse i SEK: {sek.index[0]:%Y-%m-%d}–{sek.index[-1]:%Y-%m-%d}, {len(sek)-1} gemensamma dagsavkastningar. Strategierna använder periodens kursrörelser; ingen framtida genomsnittsavkastning uppskattas.")
            if sek.index[0] > pd.Timestamp(start_date):
                st.info("Alla instrument har inte kurser från det valda startdatumet. Jämförelsen börjar vid deras första gemensamma tillgängliga kursdag.")
            with st.expander("Prishistorik för valda instrument"):
                coverage = []
                for row in selected.to_dict("records"):
                    ticker = row["ticker"]
                    last = pd.Timestamp(prices.attrs.get("actual_last_dates", {}).get(ticker, prices[ticker].last_valid_index()))
                    series = prices[ticker].loc[:last].dropna()
                    coverage.append({"Instrument": row["company_name"], "Ticker/fond-ID": ticker,
                        "Första kursdag": str(series.index[0].date()), "Senast rapporterade kursdag": str(last.date()),
                        "Kursobservationer": "—" if ticker == "__cash__" else str(prices.attrs.get("actual_observations", {}).get(ticker, len(series))),
                        "Källa": "Likvid i SEK · 0 % antagen ränta" if ticker == "__cash__" else ("Simulerade exempeldata" if prices.attrs.get("is_example") else ("Avanza NAV" if ticker.startswith("AVANZA:") else "Yahoo Finance"))})
                st.dataframe(pd.DataFrame(coverage), hide_index=True, width="stretch")
        else:
            training = select_risk_history(sek, st.session_state.analysis_window,
                                           st.session_state.get("risk_custom_start"), st.session_state.get("risk_custom_end"))
            training_fx = fx.reindex(training.index)
            inputs = bootstrap_inputs(sek, fx, end_date, training_sek=training, training_fx=training_fx)
            st.caption(f"Framtidsscenariots historik: {training.index[0]:%Y-%m-%d}–{training.index[-1]:%Y-%m-%d}, {len(training)-1} dagsavkastningar i SEK. Scenariot börjar vid senaste gemensamma kursdag {sek.index[-1]:%Y-%m-%d}.")
            if len(training) < 253:
                st.caption("Historikunderlaget är kortare än ett år. Scenarier och riskmått kan därför vara särskilt känsliga för vald period.")
        with st.spinner("Räknar strategier, avgifter och kontoskatt…"):
            results = comparison(inputs, terms, vector, int(amount), settings)
        render_result(results, selected_mode, inputs, terms, vector, int(amount), settings, future=end_date is not None)
    except ValueError as error:
        st.warning(str(error))


def render_trade_costs(portfolio, trade_plan, prices, settings):
    st.markdown("#### Kostnad för föreslagen omviktning")
    universe = portfolio.copy()
    universe["company_name"] = universe["name"]
    if "instrument_type" not in universe:
        universe["instrument_type"] = "Fond/ETF"
    terms = instrument_terms(universe, settings)
    terms = [dict(t, currency=str(portfolio.iloc[i].get("currency", "USD"))) for i, t in enumerate(terms)]
    amounts = np.maximum(portfolio.trade_value.to_numpy(), 0)[None, :]
    sold = np.maximum(-portfolio.trade_value.to_numpy(), 0)[None, :]
    planned = portfolio.ticker.isin(trade_plan.ticker).to_numpy()[None, :]
    amounts, sold = np.where(planned, amounts, 0), np.where(planned, sold, 0)
    fx = np.array([1.0 if MARKETS[t["market"]][1] == "SEK" else float(prices[MARKETS[t["market"]][1] + "SEK=X"].dropna().iloc[-1]) for t in terms])[None, :]
    valuation_date = portfolio_prices_sek(prices, portfolio).index[-1]
    start_window = StartOrderWindow(settings, valuation_date, portfolio.value_sek.sum())
    sells = order_costs(sold, fx, terms, settings, "Sälj", start_window.permission(valuation_date))
    start_window.record(valuation_date, sold, terms)
    buys = order_costs(amounts, fx, terms, settings, "Köp", start_window.permission(valuation_date))
    parts = {key: buys[key] + sells[key] for key in COMPONENTS}
    total = float(cost_total(parts).sum())
    shown = pd.DataFrame({"Instrument": portfolio.name, "Orderbelopp": (amounts + sold)[0],
                          "Courtage": parts["courtage"][0], "Växling": parts["fx"][0],
                          "Spread": parts["spread"][0], "Övrigt": parts["other"][0]})
    st.dataframe(_money_frame(shown.loc[shown.Orderbelopp > .01]), hide_index=True, width="stretch")
    st.caption(f"Handelsavgifter för de oförändrade orderbeloppen: {format_sek(total)}. De kräver motsvarande likvid utöver köpbeloppen. Strategisimulatorn minskar i stället köpen så att avgifterna ryms inom kapitalet.")
    if settings.include_tax:
        st.caption("ISK har ingen separat vinstskatt vid omviktning. Löpande ISK-skatt och AF-skatt över en vald period jämförs i Testa din strategi. Tidigare anskaffningsvärden är inte kända för denna exempelportfölj.")
        if settings.account == "AF":
            with st.expander("Uppskatta AF-skatt på försäljningarna · ange omkostnadsbelopp"):
                default = pd.DataFrame({"Instrument": portfolio.name, "Värde nu": portfolio.value_sek,
                                        "Omkostnadsbelopp": portfolio.value_sek})
                edited = st.data_editor(default, disabled=["Instrument", "Värde nu"], hide_index=True, width="stretch",
                                        key="_af_basis_editor", column_config={"Omkostnadsbelopp": st.column_config.NumberColumn(min_value=0, format="%.2f")})
                st.caption("Förvalet antar nyanskaffning till dagens värde. Ändra till dina verkliga omkostnadsbelopp inklusive köpavgifter för en relevant uppskattning.")
                basis = edited.Omkostnadsbelopp.to_numpy()
                released = basis * np.divide(sold[0], portfolio.value_sek.to_numpy(), out=np.zeros(len(basis)), where=portfolio.value_sek.to_numpy() > 0)
                gains = sold[0] - cost_total(sells)[0] - released
                interest = np.array([t["interest_fund"] for t in terms])
                tax = float(af_capital_tax(gains[~interest].sum(), gains[interest].sum(), loss_credit=settings.include_loss_credit))
                st.write(f"Uppskattad AF-skatt/skattereduktion för dessa försäljningar: **{format_sek(tax)}**. Andra affärer och kapitalposter under året ingår inte.")


def contribution_after_costs(portfolio, amount, prices, settings):
    scenario = simulate_contribution(portfolio, amount)
    universe = portfolio.copy()
    universe["company_name"] = universe["name"]
    if "instrument_type" not in universe:
        universe["instrument_type"] = "Fond/ETF"
    terms = instrument_terms(universe, settings)
    fx = np.array([1.0 if MARKETS[t["market"]][1] == "SEK" else float(prices[MARKETS[t["market"]][1] + "SEK=X"].dropna().iloc[-1]) for t in terms])[None, :]
    valuation_date = portfolio_prices_sek(prices, portfolio).index[-1]
    start_window = StartOrderWindow(settings, valuation_date, portfolio.value_sek.sum() + amount)
    orders, parts, cash = buy_with_budget(np.array([amount]), scenario.cash_allocation.to_numpy(), fx, terms, settings, start_window.permission(valuation_date))
    scenario["cash_allocation"] = orders[0]
    scenario["value_after_cash"] = scenario.value_sek + scenario.cash_allocation
    denominator = scenario.value_after_cash.sum() + cash[0]
    scenario["weight_after_cash_pct"] = scenario.value_after_cash / denominator * 100
    scenario["remaining_gap_pct"] = scenario.target_weight_pct - scenario.weight_after_cash_pct
    scenario.attrs["fees"] = float(cost_total(parts).sum())
    scenario.attrs["uninvested_cash"] = float(cash[0])
    return scenario
