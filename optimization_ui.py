"""Historical objectives, explicit bounds, validation and apply-to-targets."""
from uuid import uuid4
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from optimization_model import (OBJECTIVES, MODES, Formula, optimize_portfolio, curve_factory,
                                curve_metrics, input_fingerprint, WEIGHT_CONDITIONS, weight_condition_bounds)
from risk_model import portfolio_prices_sek, select_risk_history
from portfolio_model import instrument_catalog
from cost_model import price_inputs, historical_inputs, simulate_paths
from help_ui import explain
from engine import format_decimal_sv, format_pct, format_sek


def _apply():
    result = st.session_state.opt_result
    old = {row["ticker"]: row for row in st.session_state.portfolio_targets if row.get("ticker")}
    catalog = instrument_catalog()
    rows = []
    for ticker, weight in zip(result["columns"], result["weights"]):
        if ticker == "__cash__" or weight <= 1e-10 and ticker not in result["selected"]:
            continue
        row = dict(old.get(ticker, dict(id=uuid4().hex[:12], ticker=ticker, label=result["names"].get(ticker, catalog[ticker]["name"]))))
        row["weight"] = float(weight * 100)
        rows.append(row)
        for field in ("label", "ticker", "weight"):
            st.session_state[f"goal_{field}_{row['id']}"] = row[field]
    total = sum(row["weight"] for row in rows)
    cash_target = next((float(weight * 100) for ticker, weight in zip(result["columns"], result["weights"]) if ticker == "__cash__"), 0.)
    if total <= 0 and cash_target < 100 - 1e-6:
        st.toast("Ingen positiv instrumentvikt kan föras över.")
        return
    if st.session_state.get("workspace_mode") == "Mitt konto · demo":
        st.session_state.account_target_cash_pct = cash_target
    st.session_state.portfolio_targets = rows
    st.session_state.selected_profile = "Egen profil"
    st.session_state.opt_applied_notice = True
    st.toast("Fördelningen överförd till målvikterna. Nuvarande innehav är oförändrade.")


def _net_value(weights, raw, universe, amount, settings, mode, security_ids):
    positive = weights > 1e-10
    chosen = universe.set_index("ticker").loc[list(np.asarray(security_ids)[positive])].reset_index()
    sek, fx, terms = price_inputs(chosen, raw, settings)
    outcome = simulate_paths(**historical_inputs(sek, fx), terms=terms, weights=weights[positive],
                             amount=amount, mode=mode, settings=settings)
    key = "isk" if settings.account == "ISK" else "af"
    return float(outcome["history"][key][-1, 0])


def render_optimizer(portfolio, prices, universe, settings):
    with st.expander("Hitta en historisk fördelning", expanded=False):
        st.caption("Sökperiod först · senare validering separat · optimering före valbara avgifter och kontoskatt")
        explain("Så fungerar optimeringen", "Verktyget söker vikter för hela portföljen bland valda instrument. Risk, avkastning och samvariation räknas från samma värdekurva och rebalanseringsregel. Resultatet är den bästa fördelning sökningen hittade inom dina viktgränser, inte ett löfte om framtida avkastning eller ett bevis på globalt optimum.\n\nMinst 252 dagsavkastningar krävs i sökperioden och 63 i den senare valideringen. Det är ett datakrav för funktionen, inte en garanti för tillförlitlighet. De senare kurserna används aldrig för att välja vikter. Upprepade ändringar efter att du sett valideringen kan ändå ge överanpassning.\n\nOptimeringen är före valbara avgifter och kontoskatt. Nettot visas separat som ett hypotetiskt nystartat sparande i valideringsperioden. Det är inte kontots faktiska historiska resultat. Cash antas ha noll avkastning och visas som likvid i kundläget.", key="opt_help")
        names = portfolio.set_index("ticker")["name"].to_dict()
        options = portfolio.ticker.tolist()
        if "opt_selected" not in st.session_state:
            st.session_state.opt_selected = portfolio.loc[portfolio.in_target, "ticker"].tolist()
        st.session_state.opt_selected = [ticker for ticker in st.session_state.opt_selected if ticker in options]
        selected = st.multiselect("Instrument som får ingå", options, format_func=lambda ticker: names[ticker], key="opt_selected")
        left, right = st.columns(2)
        objective = left.selectbox("Vad vill du optimera?", OBJECTIVES, key="opt_objective")
        mode = right.selectbox("Rebalansering i sökning och validering", MODES, key="opt_mode")
        window = left.selectbox("Historik för sökning och validering", ["3 år", "5 år", "Egna datum"], key="opt_window")
        st.session_state.setdefault("opt_train_share", 70)
        train_share = right.slider("Andel till sökperiod (%)", min_value=50, max_value=80, step=5, key="opt_train_share") / 100
        start, end = None, None
        if window == "Egna datum":
            st.session_state.setdefault("opt_start", prices.index[max(0, len(prices)-757)].date())
            st.session_state.setdefault("opt_end", prices.index[-1].date())
            start = left.date_input("Optimering från", key="opt_start")
            end = right.date_input("Optimering till", key="opt_end")
        target = 0.
        if objective in ("Sortino", "Egen formel"):
            st.session_state.setdefault("opt_sortino_target", 0.)
            target = st.number_input("Målavkastning för Sortino · % per år", min_value=-5., max_value=30., step=.5, key="opt_sortino_target")
        formula = ""
        if objective == "Egen formel":
            st.session_state.setdefault("opt_formula", "CAGR - 0.5 * MaxDrawdown")
            formula = st.text_input("Din målfunktion · högre värde är bättre", key="opt_formula")
            explain("Mått och enheter i formeln", "Tillåtna mått: **Sharpe**, **CAGR**, **Sortino**, **MaxDrawdown**, **Volatilitet**. Använd tal, +, -, *, / och parenteser.\n\nCAGR och Volatilitet är årliga procenttal: 8 betyder 8 %. MaxDrawdown är en positiv procentuell förlust under perioden. Sharpe och Sortino är kvoter. Formeln `CAGR - 0.5 * MaxDrawdown` ger tillväxt ett positivt bidrag och straffar stora nedgångar. Blandar du kvoter och procenttal behöver du välja skalningen medvetet. Funktioner och programkod ingår inte i formelspråket.")
        if not selected:
            st.info("Välj minst ett instrument för att söka en fördelning.")
            return
        existing = portfolio.set_index("ticker")
        initial_rows = [{"Instrument": names[ticker], "Villkor": "max", "Vikt (%)": 100.} for ticker in selected]
        st.caption("min: minst · =: exakt · max: högst · Andel av hela portföljen")
        limits = st.data_editor(pd.DataFrame(initial_rows), hide_index=True, width="stretch", disabled=["Instrument"],
            key="opt_conditions_v2_" + st.session_state.get("account_active_context", "learn") + "_" + "_".join(selected), column_config={
                "Villkor": st.column_config.SelectboxColumn(options=WEIGHT_CONDITIONS, required=True,
                    help="min anger en lägsta vikt, = en exakt vikt och max en högsta vikt. max 100 % lämnar instrumentet fritt."),
                "Vikt (%)": st.column_config.NumberColumn(min_value=0., max_value=100., step=1., required=True,
                    help="Procent av hela portföljen. Exempel: min 20 % tillåter 20–100 %; max 30 % tillåter 0–30 %.")})
        try:
            selected_lower, selected_upper = weight_condition_bounds(limits["Villkor"], limits["Vikt (%)"])
        except ValueError as error:
            st.warning(str(error))
            return
        held = portfolio.loc[portfolio.value_sek > 0, "ticker"].tolist()
        all_ids = list(dict.fromkeys(selected + held))
        frame = portfolio_prices_sek(prices, portfolio.loc[portfolio.ticker.isin(all_ids)])
        frame = select_risk_history(frame.reindex(columns=all_ids), window, start, end)
        cash = float(portfolio.attrs.get("cash_value", 0.))
        account_mode = st.session_state.get("workspace_mode") == "Mitt konto · demo"
        new_deposit = float(st.session_state.get("account_new_deposit", 0.)) if account_mode else 0.
        cash += new_deposit
        if cash > 0:
            frame["__cash__"] = 1.
            names["__cash__"] = "Likvida medel · SEK"
        columns = list(frame.columns)
        value_total = float(portfolio.value_sek.sum() + cash)
        current = np.array([cash / value_total if ticker == "__cash__" else float(existing.loc[ticker, "value_sek"]) / value_total for ticker in columns])
        lower, upper = np.zeros(len(columns)), np.zeros(len(columns))
        for ticker, minimum, maximum in zip(selected, selected_lower, selected_upper):
            i = columns.index(ticker)
            lower[i], upper[i] = minimum, maximum
        if account_mode and not st.session_state.account_allow_sales:
            st.caption("Försäljningar är avstängda · befintliga innehav utanför urvalet behålls låsta i beräkningen")
            for i, ticker in enumerate(columns):
                if ticker == "__cash__":
                    continue
                lower[i] = max(lower[i], current[i])
                if ticker not in selected:
                    upper[i] = max(upper[i], current[i])
        if cash > 0 and account_mode and not st.session_state.account_use_cash:
            i = columns.index("__cash__")
            lower[i] = upper[i] = (cash - new_deposit) / value_total
        config = dict(selected=selected, columns=columns, lower=lower.tolist(), upper=upper.tolist(), objective=objective,
                      formula=formula, mode=mode, risk_free=float(st.session_state.risk_free_rate_pct), target=target,
                      share=train_share, context=st.session_state.get("account_active_context", "learn"),
                      current=current.tolist(), names=[names[ticker] for ticker in columns])
        fingerprint = input_fingerprint(frame, config)
        if st.button("Beräkna fördelning", type="primary", key="opt_run"):
            try:
                with st.spinner("Söker vikter och prövar dem på senare historik…"):
                    result = optimize_portfolio(frame, lower, upper, initial=current, objective=objective, formula=formula,
                        mode=mode, risk_free_pct=config["risk_free"], target_pct=target, train_share=train_share)
                result.update(columns=columns, selected=selected, names=names, fingerprint=fingerprint, current=current)
                st.session_state.opt_result = result
            except ValueError as error:
                st.session_state.pop("opt_result", None)
                st.error(str(error))
        result = st.session_state.get("opt_result")
        if result is None:
            return
        if result["fingerprint"] != fingerprint:
            st.info("Villkor eller prisunderlag har ändrats. Beräkna fördelningen igen innan den används.")
            return
        st.markdown("**Bästa funna fördelning i sökperioden**")
        st.caption(f"Mål: {objective} · sökpoäng {format_decimal_sv(result['score'])} · högre poäng är bättre")
        weights_table = pd.DataFrame({"Instrument": [result["names"][ticker] for ticker in columns],
                                      "Beräknad vikt": [format_pct(weight * 100) for weight in result["weights"]]})
        st.dataframe(weights_table, hide_index=True, width="stretch")
        train, validation = result["train"], result["validation"]
        st.caption(f"Sökperiod: {train.index[0]:%Y-%m-%d}–{train.index[-1]:%Y-%m-%d} · {len(train)-1} avkastningar. Validering: {validation.index[0]:%Y-%m-%d}–{validation.index[-1]:%Y-%m-%d} · {len(validation)-1} avkastningar.")
        equal = np.array([1. / len(selected) if ticker in selected else 0. for ticker in columns])
        curves = {"Beräknad fördelning": result["weights"], "Nuvarande fördelning": current, "Likaviktad jämförelse": equal}
        table, figure = [], go.Figure()
        validation_raw = prices.reindex(validation.index).copy()
        if "__cash__" in columns:
            validation_raw["__cash__"] = 1.
        net_universe = universe.copy()
        if "__cash__" in columns:
            net_universe = pd.concat([net_universe, pd.DataFrame([dict(ticker="__cash__", company_name="Likvida medel", currency="SEK", instrument_type="Likvid", market="FUND")])], ignore_index=True)
        for label, weights in curves.items():
            values = curve_factory(validation, mode)(weights)
            metrics = curve_metrics(values, validation.index, config["risk_free"], target)
            train_metrics = curve_metrics(curve_factory(train, mode)(weights), train.index, config["risk_free"], target)
            def objective_value(data):
                try:
                    return Formula(formula).evaluate(data) if objective == "Egen formel" else (-data["MaxDrawdown"] if objective == "Lägsta max drawdown" else data[objective])
                except ValueError:
                    return np.nan
            training_score, validation_score = objective_value(train_metrics), objective_value(metrics)
            row = {"Fördelning": label,
                   "Sökpoäng": format_decimal_sv(training_score) if np.isfinite(training_score) else "—",
                   "Valideringspoäng": format_decimal_sv(validation_score) if np.isfinite(validation_score) else "—"}
            for metric in ("Sharpe", "CAGR", "Sortino", "MaxDrawdown"):
                row[f"Validering · {metric}"] = format_decimal_sv(metrics[metric]) + (" %" if metric in ("CAGR", "MaxDrawdown") else "") if np.isfinite(metrics[metric]) else "—"
            row["Validering · utveckling"] = format_pct(metrics["Utveckling"])
            try:
                net = _net_value(weights, validation_raw.reindex(columns=list(dict.fromkeys(columns + [c for c in prices.columns if c.endswith('=X')]))),
                                 net_universe, value_total, settings, mode, columns)
                row[f"Netto · {settings.account}"] = format_sek(net)
            except ValueError:
                row[f"Netto · {settings.account}"] = "Underlag saknas"
            table.append(row)
            figure.add_trace(go.Scatter(x=validation.index, y=(values - 1) * 100, name=label))
        table_frame = pd.DataFrame(table)
        st.dataframe(table_frame[["Fördelning", "Sökpoäng", "Valideringspoäng", "Validering · utveckling", f"Netto · {settings.account}"]], hide_index=True, width="stretch")
        with st.expander("Alla historiska mått"):
            st.dataframe(table_frame, hide_index=True, width="stretch")
            st.caption("Jämförelseportföljerna kan ligga utanför optimeringens viktgränser. Det är bara den beräknade fördelningen som måste uppfylla sökvillkoren.")
        figure.update_layout(height=310, margin=dict(l=0, r=0, t=15, b=0), yaxis_title="Utveckling i valideringen (%)", legend=dict(orientation="h"))
        st.plotly_chart(figure, width="stretch", key="opt_validation_chart")
        st.caption("Valideringen visar senare historik. Nettokolumnen är ett separat scenario med valda avgifter och skatter; den styr inte optimeringen.")
        st.button("Använd som målvikter", key="opt_apply", on_click=_apply)
