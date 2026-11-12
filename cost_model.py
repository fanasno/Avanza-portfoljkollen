"""Cash-funded trading costs and Swedish account-tax estimates.

Prices: Avanza's ordinary online stock/ETF tariffs, checked 2026-11-03.
Tax is a separate liability paid outside the portfolio; it is not reinvested
or financed with imaginary tax-triggered sales. See COSTS_AND_TAX.md.
"""
from dataclasses import dataclass, field
from collections import deque
import numpy as np
import pandas as pd

VERIFIED_DATE = "2026-11-03"
SOURCES = {
    "Courtageklasser": "https://www.avanza.se/konton-lan-prislista/prislista/courtageklasser.html",
    "Handel i Sverige": "https://www.avanza.se/konton-lan-prislista/prislista/handel-sverige.html",
    "Utlandshandel och växling": "https://www.avanza.se/konton-lan-prislista/prislista/handel-utland.html",
    "Kontoavgifter": "https://www.avanza.se/konton-lan-prislista/prislista/kontoavgifter.html",
    "ISK 2026": "https://www.skatteverket.se/privat/skatter/beloppochprocent/2026.4.1522bf3f19aea8075ba21.html",
    "ISK tidigare år": "https://www.skatteverket.se/investeringssparkonto",
    "ISK kapitalunderlag": "https://www.skatteverket.se/privat/skattevardepappeinvesteringssparkontoisk/raknautschablonintakt.4.7eada0316ed67d72823b57.html",
    "Fonder på AF": "https://www.skatteverket.se/privat/skatter/vardepapper/omovrigavardepapper/fonder.4.19b9f599116a9e8ef36800010782.html",
    "Förlustkvittning": "https://www.skatteverket.se/privat/etjansterochblanketter/svarpavanligafragor/vardepapper/privatvardepapperfaq/kanjagkvittavinstmotforlustnarjagharsaltvardepapper.5.2b543913a42158acf800015357.html",
    "Utländsk räntefond": "https://www4.skatteverket.se/rattsligvagledning/edition/2026.14/2818.html",
}
CLASSES = ("Mini", "Small", "Medium", "Fast Pris", "Start")
# Each tuple is (percentage as a fraction, minimum in the market's currency).
SE = ((.0025, 1), (.0015, 39), (.00069, 69), (0, 99))
FOREIGN = ((.0025, 1), (.0015, 6), (.00089, 8), (.00079, 12))
MARKETS = {
    "SE": ("Stockholmsbörsen · aktier", "SEK", SE),
    "SE_FN": ("First North · aktier", "SEK", SE),
    "SE_ETF": ("Sverige · ETF", "SEK", (SE[0], SE[1], SE[2], (.00045, 99))),
    "SE_NGM": ("NGM / Nordic MTF / PepMarket", "SEK", ((.0025, 19), SE[1], SE[2], (.00045, 99))),
    "SE_SPOT": ("Spotlight", "SEK", ((.0025, 19), (.0015, 59), SE[2], (.00045, 99))),
    "SE_BQ": ("beQuoted", "SEK", ((.0025, 119), (.0015, 119), (.00069, 119), (.00045, 119))),
    "US": ("USA · aktier och ETF", "USD", FOREIGN),
    "CA": ("Kanada", "CAD", ((.0025, 1), (.0015, 7), (.00089, 10), (.00079, 15))),
    "DK": ("Danmark · aktier", "DKK", SE),
    "DK_ETF": ("Danmark · övriga värdepapper", "DKK", ((.0025, 19), SE[1], SE[2], (.00045, 99))),
    "NO": ("Norge · noterade aktier", "NOK", SE),
    "NO_ETF": ("Norge · övriga värdepapper", "NOK", ((.0025, 19), (.0025, 39), SE[2], (.0003, 99))),
    "FI": ("Finland · aktier", "EUR", ((.0025, .95), (.0015, 4.95), (.00069, 7.95), (0, 10.95))),
    "FI_ETF": ("Finland · övriga värdepapper", "EUR", ((.0025, 1.95), (.0025, 4.95), (.00069, 7.95), (.00045, 10.95))),
    "EU": ("Tyskland / Euronext · aktier och ETF", "EUR", FOREIGN),
    "CH": ("Schweiz · aktier", "CHF", FOREIGN),
    "GB": ("Storbritannien", "GBP", FOREIGN),
    "FUND": ("Vanlig fond · standardpris online", "SEK", ((0, 0),) * 4),
}
ISK_RATES = {2020: .00375, 2021: .00375, 2022: .00375, 2023: .00882, 2024: .01086, 2025: .00888, 2026: .01065}
COMPONENTS = ("courtage", "fx", "spread", "other", "ongoing")
MODES = ("Buy and hold", "Månadsvis rebalansering", "Kvartalsvis rebalansering")


@dataclass
class Settings:
    include_costs: bool = True
    include_tax: bool = True
    brokerage_class: str = "Mini"
    account: str = "ISK"
    fx_rate: float = .0025
    liquidate: bool = True
    af_sale_view: bool = True
    min_rebalance: float = 0.0
    allowance_used_elsewhere: float = 0.0
    future_isk_rate: float = .01065
    include_loss_credit: bool = False
    start_eligible: bool = False
    other_avanza_assets: float = 0.0
    previous_free_order_history: tuple = ()
    terms: dict = field(default_factory=dict)


class StartOrderWindow:
    """Dated Start allowance per path; a lost entitlement never returns.

    The window is (date - 12 calendar months, date]. At most 500 orders are
    free; attempting another qualifying order in that window switches to Mini.
    Hypothetical exits query permission without recording an actual order.
    """
    def __init__(self, settings, date, wealth, paths=1):
        self.enabled = settings.brokerage_class == "Start"
        self.eligible = np.full(paths, settings.start_eligible, dtype=bool)
        self.count = np.zeros(paths, dtype=int)
        self.events = deque()
        self.other_assets = settings.other_avanza_assets
        history = []
        for day, count in settings.previous_free_order_history:
            day = pd.Timestamp(day)
            if pd.isna(day) or not np.isfinite(count) or count < 0 or int(count) != count:
                raise ValueError("Tidigare gratisaffärer behöver ett giltigt datum och ett helt antal som är minst noll.")
            day = day.tz_localize(None).normalize()
            if day < pd.Timestamp(date):
                history.append((day, int(count)))
        for day, count in sorted(history):
            self._expire(day)
            self.count += count
            self.events.append((day, np.full(paths, count, dtype=int)))
            self.eligible &= self.count <= 500
        self._expire(date)
        self.update_wealth(wealth)

    def _expire(self, date):
        cutoff = pd.Timestamp(date) - pd.DateOffset(months=12)
        while self.events and self.events[0][0] <= cutoff:
            self.count -= self.events.popleft()[1]

    def update_wealth(self, wealth):
        self.eligible &= np.asarray(wealth) + self.other_assets < 50000

    def permission(self, date):
        self._expire(date)
        return self.eligible.copy(), np.maximum(500 - self.count, 0)

    def record(self, date, amounts, terms):
        if not self.enabled:
            return
        self._expire(date)
        qualifying = np.array([term["market"] == "SE" and not term["fund"] for term in terms])
        attempted = ((np.asarray(amounts) > .000001) & qualifying).sum(axis=1)
        free = np.where(self.eligible, np.minimum(attempted, np.maximum(500 - self.count, 0)), 0)
        self.eligible &= self.count + attempted <= 500
        self.count += free
        if free.any():
            self.events.append((pd.Timestamp(date), free.copy()))


def tax_rule(year, settings):
    rate = ISK_RATES.get(year, settings.future_isk_rate)
    allowance = 300000.0 if year >= 2026 else (150000.0 if year == 2025 else 0.0)
    available = max(0.0, allowance - settings.allowance_used_elsewhere)
    return rate, available, year not in ISK_RATES


def af_capital_tax(equity_net, interest_net=0.0, dividends=0.0, fund_opening=0.0, loss_credit=False):
    """Same-year netting; residual equity losses 70%, interest-fund losses 100%.

    Other private capital income/deductions are excluded. Optional deficit
    credit assumes sufficient other final income tax to use the credit.
    """
    eq = np.asarray(equity_net, dtype=float)
    income = np.maximum(eq, 0) - .7 * np.maximum(-eq, 0) + interest_net + dividends + .004 * fund_opening
    positive = .3 * np.maximum(income, 0)
    deficit = np.maximum(-income, 0)
    potential_credit = .3 * np.minimum(deficit, 100000) + .21 * np.maximum(deficit - 100000, 0)
    return positive - (potential_credit if loss_credit else 0.0)


def default_terms(row):
    ticker = str(row["ticker"])
    fund = "ETF" in str(row.get("instrument_type", "")) or "fond" in str(row.get("instrument_type", "")).lower()
    currency = str(row.get("currency", "SEK" if ticker.endswith(".ST") else "USD"))
    market = "FUND" if str(row.get("instrument_type", "")) == "Fond" else ("SE_ETF" if currency == "SEK" and fund else ("SE" if currency == "SEK" else "US"))
    if row.get("market") in MARKETS:
        market = row["market"]
    return dict(market=market, currency=currency, fund=fund, is_cash=ticker == "__cash__",
                interest_fund=row.get("fund_type") == "INTEREST_FUND" or ticker in {"BND", "AGG", "SCHZ"}, spread=0.0,
                annual_extra=0.0, dividend_yield=0.0, withholding=0.0,
                buy_tax=0.0, fixed_extra=0.0)


def instrument_terms(universe, settings):
    terms = []
    for row in universe.to_dict("records"):
        term = default_terms(row)
        term.update(settings.terms.get(row["ticker"], {}))
        term.update(ticker=row["ticker"], name=row["company_name"])
        if term["market"] not in MARKETS:
            raise ValueError("Okänd marknadsplats: " + str(term["market"]))
        terms.append(term)
    return terms


def price_inputs(universe, prices, settings):
    """Convert adjusted prices AND minimum-fee currencies to SEK, with no look-ahead fill."""
    terms = instrument_terms(universe, settings)
    stock_prices, fx = {}, {}
    for term in terms:
        ticker, currency = term["ticker"], term["currency"]
        if ticker not in prices:
            raise ValueError(f"Prishistorik saknas för {ticker}.")
        if currency == "SEK":
            conversion = pd.Series(1.0, index=prices.index)
        else:
            fx_ticker = currency + "SEK=X"
            if fx_ticker not in prices:
                raise ValueError(f"Valutakurs saknas för {currency}/SEK.")
            conversion = prices[fx_ticker].ffill()
        stock_prices[ticker] = prices[ticker] * conversion
        fee_currency = MARKETS[term["market"]][1]
        fee_fx_ticker = fee_currency + "SEK=X"
        if fee_currency == "SEK":
            fx[ticker] = pd.Series(1.0, index=prices.index)
        elif fee_fx_ticker in prices:
            fx[ticker] = prices[fee_fx_ticker].ffill()
        else:
            raise ValueError(f"Minimicourtagets valutakurs saknas för {fee_currency}/SEK.")
    sek = pd.DataFrame(stock_prices).replace([np.inf, -np.inf], np.nan).dropna()
    actual_dates = prices.attrs.get("actual_last_dates", {})
    last_dates = [pd.Timestamp(actual_dates[t["ticker"]]) for t in terms if t["ticker"] in actual_dates]
    if last_dates:
        sek = sek.loc[:min(last_dates)]
    fee_fx = pd.DataFrame(fx).reindex(sek.index).dropna()
    sek = sek.reindex(fee_fx.index)
    if len(sek) < 2 or (sek <= 0).any().any() or (fee_fx <= 0).any().any():
        raise ValueError("För kort eller ogiltig pris-/valutahistorik för jämförelsen.")
    return sek, fee_fx, terms


def order_costs(amounts, fee_fx, terms, settings, side, start_available=None):
    """Arrays (paths, instruments); one order per instrument, direction and date."""
    amount = np.maximum(np.asarray(amounts, dtype=float), 0)
    if amount.ndim == 1:
        amount = amount[None, :]
    n = amount.shape[0]
    result = {component: np.zeros_like(amount) for component in COMPONENTS}
    if not settings.include_costs:
        return result
    if settings.brokerage_class not in CLASSES:
        raise ValueError("Okänd courtageklass.")
    class_index = CLASSES.index(settings.brokerage_class) if settings.brokerage_class != "Start" else 0
    if isinstance(start_available, tuple):
        available, slots = start_available
    else:
        if settings.brokerage_class == "Start" and settings.previous_free_order_history:
            raise ValueError("Daterad Start-historik kräver en beräkningsdag för courtageberäkningen.")
        available, slots = (settings.start_eligible if start_available is None else start_available), 500
    available = np.broadcast_to(np.asarray(available), (n,))
    slots = np.broadcast_to(np.asarray(slots), (n,))
    free_candidates = np.array([t["market"] == "SE" and not t["fund"] for t in terms])
    free_orders = available[:, None] & (((amount > .000001) & free_candidates).cumsum(axis=1) <= slots[:, None])
    fx = np.broadcast_to(np.asarray(fee_fx), amount.shape)
    for i, term in enumerate(terms):
        rate, minimum = MARKETS[term["market"]][2][class_index]
        active = amount[:, i] > .000001
        commission = np.maximum(rate * amount[:, i], minimum * fx[:, i])
        if settings.brokerage_class == "Start" and term["market"] == "SE" and not term["fund"]:
            commission = np.where(free_orders[:, i], 0.0, commission)
        result["courtage"][:, i] = np.where(active, np.round(commission, 2), 0)
        fx_base = amount[:, i] + result["courtage"][:, i] if side == "Köp" else np.maximum(amount[:, i] - result["courtage"][:, i], 0)
        result["fx"][:, i] = np.where(active, fx_base * settings.fx_rate if term["currency"] != "SEK" else 0, 0)
        # User supplies the full bid/ask spread; each direction incurs half.
        result["spread"][:, i] = np.where(active, amount[:, i] * term["spread"] / 2, 0)
        result["other"][:, i] = np.where(active, term["fixed_extra"] + (amount[:, i] * term["buy_tax"] if side == "Köp" else 0), 0)
    return result


def cost_total(parts):
    return sum(parts.values())


def buy_with_budget(budget, weights, fee_fx, terms, settings, start_available=None, minimum=0.0):
    """Buy orders include all fees within the actual cash budget; never inject money."""
    budget = np.atleast_1d(np.maximum(budget, 0)).astype(float)
    weights = np.broadcast_to(np.asarray(weights, dtype=float), (len(budget), len(terms))).copy()
    weights = np.maximum(weights, 0)
    # Remove an unfundable smallest order until the remaining orders fit.
    for _ in range(len(terms) + 1):
        totals = weights.sum(axis=1)
        ratios = np.divide(weights, totals[:, None], out=np.zeros_like(weights), where=totals[:, None] > 0)
        minimum_orders = np.where(weights > 0, max(minimum, .00001), 0)
        minimum_cost = cost_total(order_costs(minimum_orders, fee_fx, terms, settings, "Köp", start_available)).sum(axis=1)
        invalid = (minimum_cost + minimum_orders.sum(axis=1) > budget + 1e-9) & (totals > 0)
        if not invalid.any():
            break
        smallest = np.where(weights > 0, weights, np.inf).argmin(axis=1)
        weights[np.flatnonzero(invalid), smallest[invalid]] = 0
    totals = weights.sum(axis=1)
    ratios = np.divide(weights, totals[:, None], out=np.zeros_like(weights), where=totals[:, None] > 0)
    full_orders = budget[:, None] * ratios
    full_parts = order_costs(full_orders, fee_fx, terms, settings, "Köp", start_available)
    if not cost_total(full_parts).any() and minimum == 0:
        return full_orders, full_parts, budget - full_orders.sum(axis=1)
    lo, hi = np.zeros(len(budget)), budget.copy()
    for _ in range(36):
        mid = (lo + hi) / 2
        orders = mid[:, None] * ratios
        expense = cost_total(order_costs(orders, fee_fx, terms, settings, "Köp", start_available)).sum(axis=1)
        fits = mid + expense <= budget
        lo, hi = np.where(fits, mid, lo), np.where(fits, hi, mid)
    orders = lo[:, None] * ratios
    parts = order_costs(orders, fee_fx, terms, settings, "Köp", start_available)
    # An optional rebalance threshold also applies to the resulting purchase, not just its target gap.
    if minimum > 0:
        orders = np.where(orders >= minimum, orders, 0)
        parts = order_costs(orders, fee_fx, terms, settings, "Köp", start_available)
    remaining = budget - orders.sum(axis=1) - cost_total(parts).sum(axis=1)
    return orders, parts, np.maximum(remaining, 0)


def _new_year(paths):
    return {key: np.zeros(paths) for key in ("quarter_sum", "deposits", "equity_gains", "interest_gains", "dividends", "fund_opening", "withholding")}


def annual_taxes(years, settings):
    isk_total = None
    af_total = None
    detail = {}
    for year, values in sorted(years.items()):
        rate, allowance, assumed = tax_rule(year, settings)
        base = (values["quarter_sum"] + values["deposits"]) / 4
        isk = np.maximum(base - allowance, 0) * rate
        af = af_capital_tax(values["equity_gains"], values["interest_gains"], values["dividends"], values["fund_opening"], settings.include_loss_credit)
        detail[year] = dict(values, capital_base=base, allowance=allowance, rate=rate, assumed=assumed,
                            isk=isk + values["withholding"], af=af + values["withholding"])
        isk_total = detail[year]["isk"].copy() if isk_total is None else isk_total + detail[year]["isk"]
        af_total = detail[year]["af"].copy() if af_total is None else af_total + detail[year]["af"]
    return isk_total, af_total, detail


def simulate_paths(dates, returns, initial_fee_fx, fx_returns, terms, weights, amount, mode, settings, record=False):
    """A single history or many Monte Carlo paths, with shared random draws across strategies.

    Prices are adjusted total-return series in SEK. Optional distribution yields
    split that total return for AF cost-basis/tax estimation, not extra return.
    Taxes are liabilities outside the portfolio. Ordinary fees are cash-funded.
    """
    dates = pd.DatetimeIndex(dates).tz_localize(None).normalize()
    r = np.asarray(returns, dtype=float)
    if r.ndim == 2:
        r = r[:, None, :]
    if len(dates) != len(r) + 1 or not np.isfinite(r).all() or (r <= -1).any():
        raise ValueError("Ogiltiga avkastningsserier eller datum.")
    if not np.isfinite(amount) or amount <= 0 or mode not in MODES:
        raise ValueError("Beloppet måste vara positivt och strategin giltig.")
    paths, assets = r.shape[1:]
    w = np.asarray(weights, dtype=float)
    if len(w) != assets or not np.isfinite(w).all() or (w < 0).any() or w.sum() <= 0:
        raise ValueError("Minst en positiv målvikt behövs.")
    if not dates.is_monotonic_increasing or dates.has_duplicates:
        raise ValueError("Datum måste vara unika och i stigande ordning.")
    for term in terms:
        rates = [term[key] for key in ("spread", "annual_extra", "dividend_yield", "withholding", "buy_tax", "fixed_extra")]
        if not np.isfinite(rates).all() or min(rates) < 0:
            raise ValueError("Kontrollera avgiftsantagandena; endast ändliga, icke-negativa tal stöds.")
    w = w / w.sum()
    fee_fx = np.broadcast_to(np.asarray(initial_fee_fx, dtype=float), (paths, assets)).copy()
    fr = np.asarray(fx_returns, dtype=float)
    if fr.ndim == 2:
        fr = fr[:, None, :]
    if fr.shape != r.shape or not np.isfinite(fr).all() or (fr <= -1).any():
        raise ValueError("Valutaserien stämmer inte med prisserien.")
    start_window = StartOrderWindow(settings, dates[0], amount, paths)
    components = {key: np.zeros(paths) for key in COMPONENTS}
    orders_count = np.zeros(paths, dtype=int)
    ledger = []

    def start_permission(date):
        return start_window.permission(date)

    def add_orders(date, side, quantities, parts, gains=None):
        active = (quantities > .000001) & np.array([not term.get("is_cash", False) for term in terms])
        orders_count[:] += active.sum(axis=1)
        start_window.record(date, quantities, terms)
        for key in COMPONENTS:
            components[key] += parts[key].sum(axis=1)
        if record:
            for i, term in enumerate(terms):
                if active[0, i]:
                    ledger.append(dict(Datum=str(date.date()), Instrument=term["name"], Ticker=term["ticker"],
                                       Åtgärd=side, Orderbelopp=float(quantities[0, i]),
                                       Courtage=float(parts["courtage"][0, i]), Växling=float(parts["fx"][0, i]),
                                       Spread=float(parts["spread"][0, i]), Övrigt=float(parts["other"][0, i]),
                                       Vinst_AF=float(gains[0, i]) if gains is not None else 0.0))

    values, initial_parts, cash = buy_with_budget(np.full(paths, amount), w, fee_fx, terms, settings, start_permission(dates[0]))
    initial_values = values.copy()
    basis = values + cost_total(initial_parts)
    add_orders(dates[0], "Köp", values, initial_parts)
    gross_values = np.broadcast_to(amount * w, (paths, assets)).copy()
    fund_mask = np.array([t["fund"] for t in terms])
    interest_mask = np.array([t["interest_fund"] for t in terms])
    dividend_yield = np.array([t["dividend_yield"] for t in terms])
    withholding = np.array([t["withholding"] for t in terms])
    annual_extra = np.array([t["annual_extra"] for t in terms])
    years = {int(dates[0].year): _new_year(paths)}
    years[dates[0].year]["deposits"] += amount
    history = {key: np.zeros((len(dates), paths)) for key in (
        "gross", "after_costs", "isk", "af", "af_realized", "af_if_sold",
        "af_tax_realized", "af_tax_if_sold", "af_sale_costs", "af_sale_gain",
    )}
    cumulative_costs = np.zeros((len(dates), paths))
    period_code = "M" if mode == MODES[1] else "Q"
    periods = dates.to_period(period_code)
    rebalance_dates = {i for i in range(len(dates) - 1) if periods[i] != periods[i + 1]} if mode != MODES[0] else set()

    def reserve_at_index(index):
        isk, af, annual = annual_taxes(years, settings)
        wealth = values.sum(axis=1) + cash
        # Each date is an independent hypothetical exit. It must not change the
        # holdings, average basis, realized gains or remaining free Start orders.
        sale_parts = order_costs(values, fee_fx, terms, settings, "Sälj", start_permission(dates[index]))
        sale_costs = cost_total(sale_parts)
        sale_gains = values - sale_costs - basis
        year = int(dates[index].year)
        current = years[year]
        current_af_if_sold = af_capital_tax(
            current["equity_gains"] + sale_gains[:, ~interest_mask].sum(axis=1),
            current["interest_gains"] + sale_gains[:, interest_mask].sum(axis=1),
            current["dividends"], current["fund_opening"], settings.include_loss_credit,
        ) + current["withholding"]
        # Only this year's liability changes; a sale cannot offset earlier years.
        af_if_sold = af - annual[year]["af"] + current_af_if_sold
        history["gross"][index] = gross_values.sum(axis=1)
        history["after_costs"][index] = wealth
        history["isk"][index] = wealth - (isk if settings.include_tax else 0)
        history["af_realized"][index] = wealth - (af if settings.include_tax else 0)
        history["af_if_sold"][index] = wealth - sale_costs.sum(axis=1) - (af_if_sold if settings.include_tax else 0)
        history["af"][index] = history["af_if_sold" if settings.include_tax and settings.af_sale_view else "af_realized"][index]
        history["af_tax_realized"][index] = af
        history["af_tax_if_sold"][index] = af_if_sold
        history["af_sale_costs"][index] = sale_costs.sum(axis=1)
        history["af_sale_gain"][index] = sale_gains.sum(axis=1)
        cumulative_costs[index] = sum(components.values())

    def sell(date, quantities, year):
        nonlocal values, basis, cash
        parts = order_costs(quantities, fee_fx, terms, settings, "Sälj", start_permission(date))
        ratio = np.divide(quantities, values, out=np.zeros_like(values), where=values > 0)
        released_basis = basis * ratio
        gains = quantities - cost_total(parts) - released_basis
        basis = np.maximum(basis - released_basis, 0)
        values = np.maximum(values - quantities, 0)
        cash += (quantities - cost_total(parts)).sum(axis=1)
        years[year]["equity_gains"] += gains[:, ~interest_mask].sum(axis=1)
        years[year]["interest_gains"] += gains[:, interest_mask].sum(axis=1)
        add_orders(date, "Sälj", quantities, parts, gains)

    reserve_at_index(0)
    for index in range(1, len(dates)):
        date, previous = dates[index], dates[index - 1]
        year = int(date.year)
        if year not in years:
            years[year] = _new_year(paths)
        if date.year != previous.year:
            years[year]["fund_opening"] += values[:, fund_mask].sum(axis=1)
        if date.to_period("Q") != previous.to_period("Q"):
            years[year]["quarter_sum"] += values.sum(axis=1) + cash
        day_fraction = (date - previous).days / 365.25
        assumed_dividends = values * dividend_yield * day_fraction
        years[year]["dividends"] += assumed_dividends.sum(axis=1)
        years[year]["withholding"] += (assumed_dividends * withholding).sum(axis=1)
        # Gross total-return data already reinvests distributions. Book their assumed
        # reinvestment once, so dividends are not taxed again as the same capital gain.
        basis += assumed_dividends
        values *= 1 + r[index - 1]
        gross_values *= 1 + r[index - 1]
        fee_fx *= 1 + fr[index - 1]
        if settings.include_costs:
            ongoing = values * (1 - np.exp(-annual_extra * day_fraction))
            values -= ongoing
            components["ongoing"] += ongoing.sum(axis=1)
            # An assumed foreign distribution is converted once to SEK. Reinvestment
            # fees are not silently invented for a vendor's adjusted-price series.
            foreign = np.array([t["currency"] != "SEK" for t in terms])
            dividend_fx = assumed_dividends * foreign * settings.fx_rate
            values = np.maximum(values - dividend_fx, 0)
            components["fx"] += dividend_fx.sum(axis=1)
        start_window.update_wealth(values.sum(axis=1) + cash)
        if index in rebalance_dates:
            target = (values.sum(axis=1) + cash)[:, None] * w
            selling = np.maximum(values - target, 0)
            selling = np.where(selling >= settings.min_rebalance, selling, 0)
            selling_cost = cost_total(order_costs(selling, fee_fx, terms, settings, "Sälj", start_permission(date)))
            selling = np.where(selling > selling_cost + .000001, selling, 0)
            sell(date, selling, year)
            gaps = np.maximum(target - values, 0)
            gaps = np.where(gaps >= settings.min_rebalance, gaps, 0)
            bought, parts, cash = buy_with_budget(cash, gaps, fee_fx, terms, settings, start_permission(date), settings.min_rebalance)
            values += bought
            basis += bought + cost_total(parts)
            add_orders(date, "Köp", bought, parts)
            gross_values = gross_values.sum(axis=1)[:, None] * w
        if index == len(dates) - 1 and settings.liquidate:
            sell(date, values.copy(), year)
        reserve_at_index(index)
    isk, af, annual = annual_taxes(years, settings)
    latent_gain = values.sum(axis=1) - basis.sum(axis=1)
    af_sale_parts = order_costs(values, fee_fx, terms, settings, "Sälj", start_permission(dates[-1]))
    return dict(dates=dates, history=history, components=components, cumulative_costs=cumulative_costs,
                tax_isk=isk, tax_af=af, annual=annual, orders=orders_count, ledger=pd.DataFrame(ledger),
                af_sale_parts={key: part.sum(axis=1) for key, part in af_sale_parts.items()},
                final_values=values, final_basis=basis, cash=cash, latent_gain=latent_gain,
                external_exit_cash=np.maximum(-cash, 0), start_remaining=start_window.eligible.copy(),
                initial_amount=amount, initial_values=initial_values, mode=mode, settings=settings)


def historical_inputs(sek_prices, fee_fx):
    return dict(dates=sek_prices.index, returns=sek_prices.pct_change().iloc[1:].to_numpy()[:, None, :],
                initial_fee_fx=fee_fx.iloc[0].to_numpy(),
                fx_returns=fee_fx.pct_change().iloc[1:].to_numpy()[:, None, :])


def bootstrap_inputs(sek_prices, fee_fx, end_date, paths=1000, block_size=10, training_sek=None, training_fx=None):
    training_sek = sek_prices if training_sek is None else training_sek
    training_fx = fee_fx if training_fx is None else training_fx
    combined = pd.concat({"prices": training_sek.pct_change(fill_method=None), "fx": training_fx.pct_change(fill_method=None)}, axis=1).dropna()
    start = pd.Timestamp(sek_prices.index[-1]).normalize()
    future = pd.bdate_range(start + pd.offsets.BDay(1), pd.Timestamp(end_date))
    if len(combined) < 2 or len(future) == 0:
        raise ValueError("För kort historik eller ogiltigt framtidsdatum.")
    source = combined.to_numpy(dtype=float)
    block_size = min(block_size, len(source))
    blocks = (len(future) + block_size - 1) // block_size
    rng = np.random.default_rng(42)
    starts = rng.integers(0, len(source) - block_size + 1, size=(paths, blocks))
    positions = (starts[:, :, None] + np.arange(block_size)).reshape(paths, -1)[:, :len(future)]
    sampled = source[positions].transpose(1, 0, 2)
    count = len(sek_prices.columns)
    return dict(dates=future.insert(0, start), returns=sampled[:, :, :count],
                initial_fee_fx=fee_fx.iloc[-1].to_numpy(), fx_returns=sampled[:, :, count:])


def representative_path(result, account):
    key = "isk" if account == "ISK" else "af"
    ends = result["history"][key][-1]
    return int(np.argmin(np.abs(ends - np.median(ends))))


def audit_rows(result, account, path=0):
    end = result["history"]
    gross, after = float(end["gross"][-1, path]), float(end["after_costs"][-1, path])
    total_fees = sum(float(v[path]) for v in result["components"].values())
    rows = [("Värde före valda avgifter och skatt", gross)]
    rows += [("Avanzas kontoavgift · ISK/AF", 0.0)]
    labels = {"courtage": "Courtage", "fx": "Valutaväxling", "spread": "Antagen köp-/säljspread", "other": "Övriga angivna handelsavgifter / köpskatt", "ongoing": "Extra löpande avgift utöver kursen"}
    rows += [(labels[key], -float(result["components"][key][path])) for key in COMPONENTS]
    rows += [("Följdeffekt av avgifter på exponering och avkastning", -(gross - after - total_fees))]
    preview = account == "AF" and result["settings"].include_tax and result["settings"].af_sale_view
    if preview:
        rows += [(f"Om såld nu · {labels[key].lower()}", -float(result["af_sale_parts"][key][path])) for key in COMPONENTS if key != "ongoing"]
    tax = float(result["tax_isk" if account == "ISK" else "tax_af"][path]) if result["settings"].include_tax else 0.0
    rows += [(f"Reserverad skatt · {account}", -tax)]
    if preview:
        rows += [("Ytterligare AF-skatt om kvarvarande innehav såldes", -float(end["af_tax_if_sold"][-1, path] - end["af_tax_realized"][-1, path]))]
    net = float(end["isk" if account == "ISK" else "af"][-1, path])
    rows += [("Nettovärde efter valda avdrag", net)]
    return rows
