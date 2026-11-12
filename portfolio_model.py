"""Instrument identities, editable target rows and separate current holdings."""
from collections import Counter
from uuid import uuid4
import math
import pandas as pd
from avanza_funds import get_avanza_funds
from data import get_category_instrument_lookup, load_live_portfolio_template, load_live_watchlist_template


def instrument_catalog():
    catalog = {}
    for ticker, item in get_category_instrument_lookup().items():
        interest = item["category"] == "Räntefond"
        catalog[ticker] = dict(item, instrument_type="Fond/ETF", market="SE_ETF" if item["currency"] == "SEK" else "US",
                               fund_type="INTEREST_FUND" if interest else "EQUITY_FUND",
                               asset_type="Räntefond" if interest else "Aktiefond", risk_level=2. if interest else 5.)
    for fund in get_avanza_funds():
        kind = fund["fund_type"]
        catalog[fund["ticker"]] = dict(fund, instrument_type="Fond", market="FUND",
            asset_type="Räntefond" if kind == "INTEREST_FUND" else ("Aktiefond" if kind == "EQUITY_FUND" else "Blandfond"),
            risk_level=2. if kind == "INTEREST_FUND" else 5.)
    for stock in load_live_watchlist_template().to_dict("records"):
        catalog[stock["ticker"]] = dict(stock, name=stock["company_name"], category=stock["sector"],
            instrument_type="Aktie", asset_type="Aktiefond", market="SE" if stock["currency"] == "SEK" else "US",
            fund_type="STOCK", risk_level=6.)
    return catalog


def target_rows_for_profile(profile, selected_instruments=None):
    template = load_live_portfolio_template(selected_instruments)
    return [dict(id=uuid4().hex[:12], ticker=row["ticker"], label=row["name"],
                 weight=float(profile["target_weights"][row["category"]])) for row in template.to_dict("records")]


def initial_holdings(selected_instruments=None):
    return load_live_portfolio_template(selected_instruments).to_dict("records")


def resolved_targets(rows):
    catalog = instrument_catalog()
    chosen = [row for row in rows if row.get("ticker") in catalog]
    if len({row["ticker"] for row in chosen}) != len(chosen):
        raise ValueError("Samma instrument kan bara finnas en gång i målbilden.")
    return chosen


def build_portfolio_template(holdings, target_rows):
    catalog = instrument_catalog()
    targets = {row["ticker"]: row for row in resolved_targets(target_rows)}
    combined = {row["ticker"]: dict(row) for row in holdings}
    for ticker in targets:
        if ticker not in combined:
            combined[ticker] = dict(ticker=ticker, units=0., fallback_value_sek=0., fallback_last_review_value_sek=0.)
    rows = []
    for ticker, holding in combined.items():
        item = catalog[ticker]
        target = targets.get(ticker)
        label = (str(target.get("label", "")).strip() if target else holding.get("name", "")) or item["name"]
        row = dict(item, **{key: value for key, value in holding.items() if key not in {"name", "category"}})
        row.update(name=label, actual_name=item["name"], row_id=ticker, category=label,
                   instrument_category=item.get("category", ""), in_target=target is not None)
        rows.append(row)
    counts = Counter(row["name"] for row in rows)
    for row in rows:
        if counts[row["name"]] > 1:
            row["name"] = f"{row['name']} ({row['ticker']})"
        row["category"] = row["name"]
    return pd.DataFrame(rows)


def target_profile(rows, base_profile, profile_name, cash_target_pct=0.):
    chosen = resolved_targets(rows)
    total = sum(float(row["weight"]) for row in chosen)
    if any(not 0 <= float(row["weight"]) <= 100 for row in chosen):
        raise ValueError("Målvikter måste vara mellan 0 och 100 procent.")
    if not math.isfinite(cash_target_pct) or not 0 <= cash_target_pct <= 100:
        raise ValueError("Likvidmålet måste vara mellan 0 och 100 procent.")
    weights = {row["ticker"]: float(row["weight"]) / total * (100 - cash_target_pct) if total > 0 else 0. for row in chosen}
    catalog = instrument_catalog()
    equity = sum(weight for ticker, weight in weights.items() if catalog[ticker]["asset_type"] == "Aktiefond")
    equity_known = not any(weight > 0 and catalog[ticker]["asset_type"] == "Blandfond" for ticker, weight in weights.items())
    if not equity_known:
        equity = math.nan
    return dict(base_profile, target_weights=weights, equity_target=equity,
                equity_target_known=equity_known, cash_target_pct=float(cash_target_pct),
                raw_weight_total=total + cash_target_pct if total > 0 or cash_target_pct == 100 else 0., profile_name=profile_name)


def contribution_message(portfolio, contribution, amount):
    """New money only, compared with target gaps after adding that same money."""
    final_total = portfolio.value_sek.sum() + amount
    gaps = (final_total * portfolio.target_weight - portfolio.value_sek).clip(lower=0)
    needed = float(gaps.sum())
    used = float(contribution.cash_allocation.sum())
    share = min(used / needed, 1.) * 100 if needed > 0 else 0.
    sellers = portfolio.loc[portfolio.trade_value < -.01, "name"].tolist()
    return share, sellers
