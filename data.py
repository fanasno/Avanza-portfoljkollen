"""Instrument templates and currency conversions retained from the SAVR prototype."""
import numpy as np
import pandas as pd
from market_data import fetch_price_history
from avanza_funds import get_avanza_funds


def get_category_instrument_catalog() -> dict[str, list[dict]]:
    catalog = {
        "Globalfond": [
            {"ticker": "VT", "name": "Vanguard Total World Stock ETF", "currency": "USD"},
            {"ticker": "ACWI", "name": "iShares MSCI ACWI ETF", "currency": "USD"},
            {"ticker": "URTH", "name": "iShares MSCI World ETF", "currency": "USD"},
        ],
        "Sverigefond": [
            {"ticker": "EWD", "name": "iShares MSCI Sweden ETF", "currency": "USD"},
            {"ticker": "FLSW", "name": "Franklin FTSE Sweden ETF", "currency": "USD"},
        ],
        "Teknikfond": [
            {"ticker": "XLK", "name": "Technology Select Sector SPDR Fund", "currency": "USD"},
            {"ticker": "VGT", "name": "Vanguard Information Technology ETF", "currency": "USD"},
            {"ticker": "IYW", "name": "iShares U.S. Technology ETF", "currency": "USD"},
        ],
        "Tillväxtmarknad": [
            {"ticker": "IEMG", "name": "iShares Core MSCI Emerging Markets ETF", "currency": "USD"},
            {"ticker": "VWO", "name": "Vanguard FTSE Emerging Markets ETF", "currency": "USD"},
            {"ticker": "EEM", "name": "iShares MSCI Emerging Markets ETF", "currency": "USD"},
        ],
        "Småbolagsfond": [
            {"ticker": "IWM", "name": "iShares Russell 2000 ETF", "currency": "USD"},
            {"ticker": "VB", "name": "Vanguard Small-Cap ETF", "currency": "USD"},
            {"ticker": "SCHA", "name": "Schwab U.S. Small-Cap ETF", "currency": "USD"},
        ],
        "Räntefond": [
            {"ticker": "BND", "name": "Vanguard Total Bond Market ETF", "currency": "USD"},
            {"ticker": "AGG", "name": "iShares Core U.S. Aggregate Bond ETF", "currency": "USD"},
            {"ticker": "SCHZ", "name": "Schwab U.S. Aggregate Bond ETF", "currency": "USD"},
        ],
    }
    for fund in get_avanza_funds():
        if fund["category"] in catalog:
            catalog[fund["category"]].append(fund)
    return catalog



def get_default_category_instrument_map() -> dict[str, str]:
    return {
        category: options[0]["ticker"] for category, options in get_category_instrument_catalog().items()
    }



def get_category_instrument_lookup() -> dict[str, dict]:
    lookup = {}
    for category, options in get_category_instrument_catalog().items():
        for option in options:
            lookup[option["ticker"]] = {**option, "category": category}
    return lookup



def get_portfolio_category_blueprint() -> list[dict]:
    return [
        {
            "category": "Teknikfond",
            "fallback_value_sek": 165000,
            "fallback_last_review_value_sek": 150000,
            "asset_type": "Aktiefond",
            "risk_level": 6.7,
        },
        {
            "category": "Globalfond",
            "fallback_value_sek": 150000,
            "fallback_last_review_value_sek": 147000,
            "asset_type": "Aktiefond",
            "risk_level": 4.1,
        },
        {
            "category": "Sverigefond",
            "fallback_value_sek": 55000,
            "fallback_last_review_value_sek": 56000,
            "asset_type": "Aktiefond",
            "risk_level": 5.1,
        },
        {
            "category": "Tillväxtmarknad",
            "fallback_value_sek": 40000,
            "fallback_last_review_value_sek": 38000,
            "asset_type": "Aktiefond",
            "risk_level": 6.0,
        },
        {
            "category": "Småbolagsfond",
            "fallback_value_sek": 30000,
            "fallback_last_review_value_sek": 28000,
            "asset_type": "Aktiefond",
            "risk_level": 6.3,
        },
        {
            "category": "Räntefond",
            "fallback_value_sek": 20000,
            "fallback_last_review_value_sek": 22000,
            "asset_type": "Räntefond",
            "risk_level": 1.8,
        },
    ]



def get_category_instrument_label(ticker: str) -> str:
    instrument = get_category_instrument_lookup().get(ticker)
    if instrument is None:
        return ticker
    if instrument.get("orderbook_id"):
        return f"{instrument['name']} · {instrument['currency']}"
    return f"{instrument['name']} ({ticker})"



def load_live_portfolio_template(selected_instruments: dict[str, str] | None = None) -> pd.DataFrame:
    selected_instruments = selected_instruments or get_default_category_instrument_map()
    instrument_lookup = get_category_instrument_lookup()
    default_map = get_default_category_instrument_map()
    data = []
    for blueprint in get_portfolio_category_blueprint():
        category = blueprint["category"]
        ticker = selected_instruments.get(category, default_map[category])
        instrument = instrument_lookup.get(ticker, instrument_lookup[default_map[category]])
        data.append(
            {
                "name": instrument["name"],
                "ticker": instrument["ticker"],
                "units": np.nan,
                "currency": instrument["currency"],
                "fallback_value_sek": blueprint["fallback_value_sek"],
                "fallback_last_review_value_sek": blueprint["fallback_last_review_value_sek"],
                "category": category,
                "asset_type": blueprint["asset_type"],
                "risk_level": blueprint["risk_level"],
                "market": "FUND" if instrument.get("orderbook_id") else ("SE_ETF" if instrument["currency"] == "SEK" else "US"),
                "fund_type": instrument.get("fund_type", "INTEREST_FUND" if category == "Räntefond" else "EQUITY_FUND"),
            }
        )
    return pd.DataFrame(data)



def load_live_watchlist_template() -> pd.DataFrame:
    data = [
        {
            "company_name": "Apple",
            "ticker": "AAPL",
            "units": 22,
            "currency": "USD",
            "sector": "Teknik",
            "fallback_position_value_sek": 45500,
        },
        {
            "company_name": "Microsoft",
            "ticker": "MSFT",
            "units": 12,
            "currency": "USD",
            "sector": "Teknik",
            "fallback_position_value_sek": 38200,
        },
        {
            "company_name": "NVIDIA",
            "ticker": "NVDA",
            "units": 32,
            "currency": "USD",
            "sector": "Halvledare",
            "fallback_position_value_sek": 52100,
        },
        {
            "company_name": "Investor B",
            "ticker": "INVE-B.ST",
            "units": 120,
            "currency": "SEK",
            "sector": "Investmentbolag",
            "fallback_position_value_sek": 28400,
        },
        {
            "company_name": "Volvo B",
            "ticker": "VOLV-B.ST",
            "units": 85,
            "currency": "SEK",
            "sector": "Industri",
            "fallback_position_value_sek": 21600,
        },
    ]
    return pd.DataFrame(data)



def get_currency_fx_ticker(currency: str) -> str | None:
    currency = str(currency).upper()
    if currency == "SEK":
        return None
    return f"{currency}SEK=X"



def get_fx_tickers(currencies: list[str]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                fx_ticker
                for currency in currencies
                if (fx_ticker := get_currency_fx_ticker(currency)) is not None
            }
        )
    )



def get_latest_series_value(series: pd.Series, fallback: float = np.nan) -> float:
    clean = series.dropna()
    if clean.empty:
        return float(fallback)
    return float(clean.iloc[-1])



def get_reference_series_value(series: pd.Series, trading_days: int, fallback: float = np.nan) -> float:
    clean = series.dropna()
    if clean.empty:
        return float(fallback)
    if len(clean) <= trading_days:
        return float(clean.iloc[0])
    return float(clean.iloc[-(trading_days + 1)])



def convert_market_value_to_sek(
    units: float,
    price_series: pd.Series,
    fx_series: pd.Series | None,
    fallback_current: float,
    fallback_reference: float,
    reference_days: int = 21,
) -> tuple[float, float]:
    current_price = get_latest_series_value(price_series, np.nan)
    reference_price = get_reference_series_value(price_series, reference_days, np.nan)
    current_fx = 1.0 if fx_series is None else get_latest_series_value(fx_series, np.nan)
    reference_fx = (
        1.0 if fx_series is None else get_reference_series_value(fx_series, reference_days, np.nan)
    )
    if np.isnan(current_price) or np.isnan(current_fx):
        return float(fallback_current), float(fallback_reference)
    if np.isnan(reference_price) or np.isnan(reference_fx):
        reference_value = float(fallback_reference)
    else:
        reference_value = float(units * reference_price * reference_fx)
    current_value = float(units * current_price * current_fx)
    return current_value, reference_value



def derive_units_from_fallback_values(
    price_series: pd.Series,
    fx_series: pd.Series | None,
    fallback_current: float,
    fallback_reference: float,
    reference_days: int = 21,
) -> float:
    current_price = get_latest_series_value(price_series, np.nan)
    reference_price = get_reference_series_value(price_series, reference_days, np.nan)
    current_fx = 1.0 if fx_series is None else get_latest_series_value(fx_series, np.nan)
    reference_fx = (
        1.0 if fx_series is None else get_reference_series_value(fx_series, reference_days, np.nan)
    )

    if not np.isnan(reference_price) and not np.isnan(reference_fx):
        reference_denominator = reference_price * reference_fx
        if reference_denominator:
            return float(fallback_reference / reference_denominator)

    if not np.isnan(current_price) and not np.isnan(current_fx):
        current_denominator = current_price * current_fx
        if current_denominator:
            return float(fallback_current / current_denominator)

    return np.nan



def build_live_portfolio_values(portfolio_template: pd.DataFrame, price_history: pd.DataFrame) -> pd.DataFrame:
    portfolio = portfolio_template.copy()
    current_values = []
    reference_values = []
    data_sources = []
    resolved_units = []
    for _, row in portfolio.iterrows():
        price_series = price_history[row["ticker"]] if row["ticker"] in price_history.columns else pd.Series(dtype=float)
        fx_ticker = get_currency_fx_ticker(row["currency"])
        fx_series = price_history[fx_ticker] if fx_ticker and fx_ticker in price_history.columns else None
        units = float(row["units"]) if pd.notna(row["units"]) else np.nan
        if np.isnan(units) or units <= 0:
            units = derive_units_from_fallback_values(
                price_series=price_series,
                fx_series=fx_series,
                fallback_current=float(row["fallback_value_sek"]),
                fallback_reference=float(row["fallback_last_review_value_sek"]),
            )
        if np.isnan(units) or units <= 0:
            current_value = float(row["fallback_value_sek"])
            reference_value = float(row["fallback_last_review_value_sek"])
        else:
            current_value, reference_value = convert_market_value_to_sek(
                units=units,
                price_series=price_series,
                fx_series=fx_series,
                fallback_current=float(row["fallback_value_sek"]),
                fallback_reference=float(row["fallback_last_review_value_sek"]),
            )
        current_values.append(current_value)
        reference_values.append(reference_value)
        data_sources.append("Marknadsdata" if not price_series.dropna().empty else "Beräknat värde")
        resolved_units.append(units if not np.isnan(units) else 0.0)
    portfolio["value_sek"] = current_values
    portfolio["last_review_value_sek"] = reference_values
    portfolio["data_source"] = data_sources
    portfolio["units"] = resolved_units
    return portfolio



def build_live_watchlist_values(watchlist_template: pd.DataFrame, price_history: pd.DataFrame) -> pd.DataFrame:
    watchlist = watchlist_template.copy()
    position_values = []
    current_prices = []
    data_sources = []
    for _, row in watchlist.iterrows():
        price_series = price_history[row["ticker"]] if row["ticker"] in price_history.columns else pd.Series(dtype=float)
        fx_ticker = get_currency_fx_ticker(row["currency"])
        fx_series = price_history[fx_ticker] if fx_ticker and fx_ticker in price_history.columns else None
        current_value, _ = convert_market_value_to_sek(
            units=float(row["units"]),
            price_series=price_series,
            fx_series=fx_series,
            fallback_current=float(row["fallback_position_value_sek"]),
            fallback_reference=float(row["fallback_position_value_sek"]),
        )
        current_prices.append(get_latest_series_value(price_series, np.nan))
        position_values.append(current_value)
        data_sources.append("Marknadsdata" if not price_series.dropna().empty else "Beräknat värde")
    watchlist["position_value_sek"] = position_values
    watchlist["latest_market_price"] = current_prices
    watchlist["data_source"] = data_sources
    return watchlist



def build_yfinance_instrument_universe(
    portfolio: pd.DataFrame, watchlist: pd.DataFrame
) -> pd.DataFrame:
    portfolio_view = portfolio[
        ["name", "ticker", "category", "value_sek", "data_source", "currency"]
    ].copy()
    if "actual_name" in portfolio:
        portfolio_view["name"] = portfolio["actual_name"]
    portfolio_view = portfolio_view.rename(
        columns={
            "name": "company_name",
            "category": "sector",
            "value_sek": "position_value_sek",
        }
    )
    portfolio_view["instrument_type"] = "Fond/ETF"
    if "instrument_type" in portfolio:
        portfolio_view["instrument_type"] = portfolio["instrument_type"]

    watchlist_view = watchlist[
        ["company_name", "ticker", "sector", "position_value_sek", "data_source", "currency"]
    ].copy()
    watchlist_view["instrument_type"] = "Aktie"

    catalog_rows = []
    for ticker, option in get_category_instrument_lookup().items():
        if not ticker.startswith("AVANZA:"):
            catalog_rows.append(dict(company_name=option["name"], ticker=ticker, sector=option["category"],
                                     currency=option["currency"], instrument_type="Fond/ETF", position_value_sek=0., data_source="Referensinstrument"))
    for fund in get_avanza_funds():
        catalog_rows.append(dict(company_name=fund["name"], ticker=fund["ticker"], sector=fund["category"] or "Bland-/branschfond",
                                 currency=fund["currency"], instrument_type="Fond", market="FUND", fund_type=fund["fund_type"],
                                 isin=fund["isin"], fund_fee_pct=fund["total_fee_pct"], position_value_sek=0., data_source="Avanza Fonder"))
    # Catalog metadata wins for real funds, including the fund/ETF distinction.
    catalog_frame = pd.DataFrame(catalog_rows).set_index("ticker")
    positions = pd.concat([watchlist_view, portfolio_view], ignore_index=True).drop_duplicates("ticker").set_index("ticker")
    combined = positions.combine_first(catalog_frame).reset_index()
    real_funds = combined.ticker.str.startswith("AVANZA:")
    combined.loc[real_funds, "instrument_type"] = "Fond"
    combined = combined.sort_values(
        ["instrument_type", "company_name"], ascending=[True, True]
    )
    return combined.reset_index(drop=True)



def ensure_price_history_for_tickers(
    price_history: pd.DataFrame, tickers: list[str], period: str = "5y"
) -> pd.DataFrame:
    requested_tickers = list(dict.fromkeys(tickers))
    if not requested_tickers:
        return pd.DataFrame()

    missing_tickers = [
        ticker
        for ticker in requested_tickers
        if ticker not in price_history.columns or price_history[ticker].dropna().empty
    ]
    if not missing_tickers:
        return price_history[requested_tickers].copy()

    refreshed_history = fetch_price_history(tuple(missing_tickers), period=period)
    combined_history = pd.concat([price_history, refreshed_history], axis=1)
    combined_history = combined_history.loc[:, ~combined_history.columns.duplicated(keep="last")]
    available_tickers = [ticker for ticker in requested_tickers if ticker in combined_history.columns]
    if not available_tickers:
        return pd.DataFrame()
    return combined_history[available_tickers].copy()



def slice_price_history(prices: pd.DataFrame, trading_days: int) -> pd.DataFrame:
    if prices.empty:
        return prices
    if len(prices) <= trading_days:
        return prices.dropna(how="all")
    return prices.iloc[-trading_days:].dropna(how="all")



def get_interval_price(series: pd.Series, trading_days: int) -> float:
    clean = series.dropna()
    if clean.empty:
        return np.nan
    if len(clean) <= trading_days:
        return float(clean.iloc[0])
    return float(clean.iloc[-(trading_days + 1)])



