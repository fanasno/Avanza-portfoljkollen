"""Read-only demo/import account adapters and cash-funded order previews."""
from io import StringIO
from uuid import uuid4
import numpy as np
import pandas as pd
from portfolio_model import instrument_catalog
from cost_model import instrument_terms, price_inputs, order_costs, cost_total, buy_with_budget, StartOrderWindow, af_capital_tax


def holding(ticker, units, basis=None):
    item = instrument_catalog()[ticker]
    return dict(item, ticker=ticker, units=float(units), fallback_value_sek=0., fallback_last_review_value_sek=0.,
                cost_basis_sek=np.nan if basis is None else float(basis))


def demo_accounts():
    return {
        "demo_isk": dict(id="demo_isk", name="Mitt långsiktiga sparande · Demo-ISK", account="ISK", brokerage="Mini", cash=5000.,
            source="Demokonto · inget bankkonto anslutet", holdings=[holding("AVANZA:41567", 500, 150000), holding("AVANZA:878733", 200, 18000)]),
        "demo_af": dict(id="demo_af", name="Min aktieportfölj · Demo-AF", account="AF", brokerage="Mini", cash=10000.,
            source="Demokonto · inget bankkonto anslutet", holdings=[holding("INVE-B.ST", 100, 22000), holding("VOLV-B.ST", 100, 23000)]),
    }


def account_targets(account):
    count = len(account["holdings"])
    return [dict(id=uuid4().hex[:12], ticker=row["ticker"], label=row["name"], weight=100. / count)
            for row in account["holdings"]]


def _number(value):
    if isinstance(value, str):
        value = value.replace("\u00a0", "").replace(" ", "").replace(",", ".")
    result = float(value)
    if not np.isfinite(result):
        raise ValueError("Belopp och antal måste vara ändliga tal.")
    return result


def parse_holdings_csv(content, account="ISK", cash=0., brokerage="Mini"):
    if isinstance(content, bytes):
        if len(content) > 1_000_000:
            raise ValueError("Innehavsfilen får vara högst 1 MB.")
        content = content.decode("utf-8-sig")
    if account not in ("ISK", "AF") or not np.isfinite(cash) or cash < 0:
        raise ValueError("Välj ISK eller AF och en likvid som är minst noll.")
    try:
        frame = pd.read_csv(StringIO(content), sep=None, engine="python", dtype=str).fillna("")
    except Exception as error:
        raise ValueError("Filen kunde inte läsas. Använd CSV med kolumnerna instrument, antal och valfritt omkostnadsbelopp.") from error
    frame.columns = [str(column).strip().casefold() for column in frame.columns]
    identifier = next((key for key in ("instrument", "ticker", "isin", "namn") if key in frame), None)
    if identifier is None or "antal" not in frame or not 1 <= len(frame) <= 100:
        raise ValueError("Filen behöver 1–100 rader samt instrument/ticker/ISIN och antal.")
    catalog = instrument_catalog()
    lookup = {}
    for ticker, item in catalog.items():
        for key in (ticker, item["name"], item.get("isin", "")):
            if key:
                lookup[str(key).strip().casefold()] = ticker
    positions = {}
    for index, record in frame.iterrows():
        ticker = lookup.get(record[identifier].strip().casefold())
        if ticker is None:
            raise ValueError(f"Rad {index + 2}: instrumentet finns inte i demokatalogen. Ange ett känt fond-ID, ticker, ISIN eller fondnamn.")
        try:
            units = _number(record["antal"])
            basis = _number(record["omkostnadsbelopp"]) if record.get("omkostnadsbelopp", "").strip() else None
        except (ValueError, TypeError) as error:
            raise ValueError(f"Rad {index + 2}: kontrollera antal och omkostnadsbelopp.") from error
        if units <= 0 or basis is not None and basis < 0:
            raise ValueError(f"Rad {index + 2}: antal måste vara positivt och omkostnadsbelopp minst noll.")
        if ticker in positions:
            previous = positions[ticker]
            previous["units"] += units
            previous["cost_basis_sek"] = (previous["cost_basis_sek"] + basis
                if basis is not None and np.isfinite(previous["cost_basis_sek"]) else np.nan)
        else:
            positions[ticker] = holding(ticker, units, basis)
    return dict(id="imported", name="Importerad portfölj", account=account, brokerage=brokerage, cash=float(cash),
                source="Importerade innehav · inget bankkonto anslutet", holdings=list(positions.values()))


def preview_orders(portfolio, prices, settings, cash=0., allow_sales=True, use_cash=True, new_deposit=0.):
    if not np.isfinite(cash + new_deposit) or min(cash, new_deposit) < 0:
        raise ValueError("Likviden måste vara minst noll.")
    universe = portfolio.copy()
    universe["company_name"] = universe["name"]
    _, fx, terms = price_inputs(universe, prices, settings)
    # Fee currencies, not security currencies, determine minimum-commission FX.
    fee_fx = fx.iloc[-1].to_numpy()[None, :]
    date = fx.index[-1]
    current = portfolio.value_sek.to_numpy(dtype=float)
    total_cash = cash + new_deposit
    targets = portfolio.target_weight.to_numpy(dtype=float) * (current.sum() + total_cash)
    window = StartOrderWindow(settings, date, current.sum() + total_cash)
    selling = np.maximum(current - targets, 0) if allow_sales else np.zeros(len(current))
    sale_parts = order_costs(selling[None, :], fee_fx, terms, settings, "Sälj", window.permission(date))
    selling = np.where(selling > cost_total(sale_parts)[0] + .01, selling, 0.)
    sale_parts = order_costs(selling[None, :], fee_fx, terms, settings, "Sälj", window.permission(date))
    window.record(date, selling[None, :], terms)
    cash_used = (cash if use_cash else 0.) + new_deposit
    budget = cash_used + float((selling - cost_total(sale_parts)[0]).sum())
    remaining = current - selling
    gaps = np.maximum(targets - remaining, 0)
    gap_costs = float(cost_total(order_costs(gaps[None, :], fee_fx, terms, settings, "Köp", window.permission(date))).sum())
    buy_budget = min(max(budget, 0), float(gaps.sum()) + gap_costs)
    bought, buy_parts, leftover = buy_with_budget(np.array([buy_budget]), gaps, fee_fx, terms, settings, window.permission(date))
    after = remaining + bought[0]
    final_cash = float(leftover[0] + total_cash - cash_used + budget - buy_budget)
    fees = float(cost_total(sale_parts).sum() + cost_total(buy_parts).sum())
    tax = 0.
    known = True
    if settings.include_tax and settings.account == "AF" and selling.any():
        basis = portfolio.get("cost_basis_sek", pd.Series(np.nan, index=portfolio.index)).to_numpy(dtype=float)
        known = bool(np.isfinite(basis[selling > 0]).all())
        if known:
            released = np.divide(selling, current, out=np.zeros_like(selling), where=current > 0) * np.nan_to_num(basis)
            gains = selling - cost_total(sale_parts)[0] - released
            interest = np.array([term["interest_fund"] for term in terms])
            tax = float(af_capital_tax(gains[~interest].sum(), gains[interest].sum(), loss_credit=settings.include_loss_credit))
        else:
            tax = None
    actions = []
    for i, row in enumerate(portfolio.to_dict("records")):
        for side, amount, parts in (("Sälj", selling[i], sale_parts), ("Köp", bought[0, i], buy_parts)):
            if amount > .01:
                actions.append({"Instrument": row["name"], "Ticker/fond-ID": row["ticker"], "Åtgärd": side,
                                "Modellbelopp": float(amount), "Valda avgifter": float(cost_total(parts)[0, i])})
    return dict(orders=pd.DataFrame(actions, columns=["Instrument", "Ticker/fond-ID", "Åtgärd", "Modellbelopp", "Valda avgifter"]),
                after=after, cash=final_cash, fees=fees, tax=tax, tax_known=known,
                before_total=float(current.sum() + total_cash), after_total=float(after.sum() + final_cash))
