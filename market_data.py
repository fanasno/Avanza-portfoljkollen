"""Explicit example data and the original Yahoo Finance market data path."""
import hashlib
import json
from io import StringIO
from uuid import uuid4
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
import requests
from concurrent.futures import ThreadPoolExecutor
from avanza_funds import get_avanza_fund

# Keep Yahoo's timezone/cookie databases within this portable project.
yf.set_tz_cache_location(str(Path(__file__).resolve().parent / ".cache" / "yfinance"))
PRICE_CACHE = Path(__file__).resolve().parent / ".cache" / "prices"


class PriceDataError(ValueError):
    """Real prices are unavailable; callers must not substitute invented history."""


def _validate_prices(prices, tickers):
    if prices.empty or not set(tickers).issubset(prices.columns) or not isinstance(prices.index, pd.DatetimeIndex):
        raise ValueError("Ofullständig prishistorik.")
    if not prices.index.is_monotonic_increasing or prices.index.has_duplicates:
        raise ValueError("Ogiltiga kursdatum.")
    for ticker in tickers:
        values = prices[ticker].dropna()
        if len(values) < 2 or not np.isfinite(values).all() or (values <= 0).any():
            raise ValueError(f"Verklig prishistorik saknas eller är ogiltig för {ticker}.")


def _cache_path(ticker, period):
    return PRICE_CACHE / (hashlib.sha256(f"v1:{ticker}:{period}".encode()).hexdigest() + ".json")


def _save_real_prices(prices, tickers, period):
    PRICE_CACHE.mkdir(parents=True, exist_ok=True)
    for ticker in tickers:
        series = prices[[ticker]].dropna()
        payload = dict(version=1, ticker=ticker, period=period, is_example=False,
                       source="Avanza NAV" if get_avanza_fund(ticker) else "Yahoo Finance",
                       fetched_at=pd.Timestamp.now(tz="UTC").isoformat(),
                       prices=series.to_json(orient="split", date_format="iso"))
        path = _cache_path(ticker, period)
        temporary = path.with_suffix(f".{uuid4().hex}.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)


def _load_real_prices(tickers, period):
    frames, sources, fetched = [], set(), []
    try:
        for ticker in tickers:
            payload = json.loads(_cache_path(ticker, period).read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return None
            expected_source = "Avanza NAV" if get_avanza_fund(ticker) else "Yahoo Finance"
            if (payload.get("version") != 1 or payload.get("is_example") is not False
                    or payload.get("ticker") != ticker or payload.get("period") != period
                    or payload.get("source") != expected_source):
                return None
            frame = pd.read_json(StringIO(payload["prices"]), orient="split")
            frame.index = pd.to_datetime(frame.index).tz_localize(None)
            _validate_prices(frame, (ticker,))
            frames.append(frame)
            sources.add(expected_source)
            fetched.append(payload["fetched_at"])
        prices = pd.concat(frames, axis=1).sort_index()
        _validate_prices(prices, tickers)
        actual = {ticker: str(prices[ticker].last_valid_index().date()) for ticker in tickers}
        observations = {ticker: int(prices[ticker].notna().sum()) for ticker in tickers}
        prices = prices.ffill(limit=3)
        source = "Avanza NAV + Yahoo Finance" if len(sources) > 1 else next(iter(sources))
        prices.attrs.update(source=source, is_example=False, fallback=False, cached=True,
                            fetched_at=min(fetched), actual_last_dates=actual, actual_observations=observations)
        return prices
    except (OSError, ValueError, KeyError, TypeError):
        return None


def make_example_history(tickers: tuple[str, ...]) -> pd.DataFrame:
    """Stable, synthetic prices. Never represent these as historical market prices."""
    dates = pd.bdate_range(end="2026-11-02", periods=1261)
    market = np.random.default_rng(125).normal(0.0003, 0.008, len(dates))
    prices = {}
    for ticker in tickers:
        seed = int.from_bytes(hashlib.sha256(ticker.encode()).digest()[:4], "little")
        rng = np.random.default_rng(seed)
        if ticker.endswith("=X"):
            returns = rng.normal(0.0, 0.002, len(dates))
            start = 10.0
        elif ticker in {"BND", "AGG", "SCHZ"} or (get_avanza_fund(ticker) or {}).get("fund_type") == "INTEREST_FUND":
            returns = rng.normal(0.00008, 0.0025, len(dates)) + market * 0.08
            start = 80.0
        else:
            beta = 1.25 if ticker in {"XLK", "VGT", "IYW", "AAPL", "MSFT", "NVDA"} else 0.8
            returns = market * beta + rng.normal(0.00007, 0.004, len(dates))
            start = 100.0
        fund = get_avanza_fund(ticker)
        if fund:
            returns -= fund["total_fee_pct"] / 100 / 252
        prices[ticker] = pd.Series(start * np.cumprod(1 + returns), index=dates)
        if fund:
            prices[ticker] = prices[ticker].where(dates >= pd.Timestamp(fund["start_date"]))
    result = pd.DataFrame(prices, index=dates)
    result.attrs.update(source="Simulerade exempeldata", is_example=True, fallback=False)
    return result


def parse_avanza_nav(payload):
    """raw=true is required: the default y values are percentage development."""
    points = payload.get("dataSerie", [])
    if not points:
        return pd.Series(dtype=float)
    index = pd.to_datetime([p["x"] for p in points], unit="ms", utc=True).tz_convert("Europe/Stockholm").tz_localize(None).normalize()
    series = pd.Series([p["y"] for p in points], index=index, dtype=float).sort_index()
    series = series[~series.index.duplicated(keep="last")]
    if not np.isfinite(series).all() or (series <= 0).any():
        raise ValueError("Ogiltig NAV-serie från Avanza.")
    if len(series) > 4 and np.median(np.diff(series.index).astype("timedelta64[D]").astype(float)) > 3:
        raise ValueError("Fondkällan gav glesa kurspunkter; de får inte räknas som dagliga avkastningar.")
    return series


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_avanza_nav(ticker, period="5y"):
    fund = get_avanza_fund(ticker)
    if fund is None:
        raise ValueError("Okänd Avanza-fond.")
    end = pd.Timestamp.now(tz="Europe/Stockholm").normalize().tz_localize(None)
    start = max(end - pd.DateOffset(years=int(period[:-1]) if period.endswith("y") else 5), pd.Timestamp(fund["start_date"]))
    chunks = []
    # Long chart requests are downsampled to weeks. Short original date intervals
    # retain daily NAV, so never manufacture daily returns from weekly points.
    while start < end:
        stop = min(start + pd.Timedelta(days=364), end)
        url = f'https://www.avanza.se/_api/fund-guide/chart/{fund["orderbook_id"]}/{start:%Y-%m-%d}/{stop:%Y-%m-%d}'
        response = requests.get(url, params={"raw": "true"}, timeout=15)
        response.raise_for_status()
        payload = response.json()
        if str(payload.get("id")) != fund["orderbook_id"]:
            raise ValueError("Fondkurvan avser ett annat fond-ID.")
        chunks.append(parse_avanza_nav(payload))
        start = stop
    series = pd.concat(chunks).sort_index() if chunks else pd.Series(dtype=float)
    series = series[~series.index.duplicated(keep="last")]
    if len(series) < 2:
        raise ValueError("För kort fondhistorik.")
    series.name = ticker
    return series


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_price_history(
    tickers: tuple[str, ...], period: str = "5y", mode: str = "Marknadsdata"
) -> pd.DataFrame:
    if not tickers:
        return pd.DataFrame()
    if mode == "Exempeldata":
        return make_example_history(tickers)
    if mode != "Marknadsdata":
        raise ValueError("Okänd datakälla.")
    try:
        native = tuple(ticker for ticker in tickers if not get_avanza_fund(ticker))
        funds = tuple(ticker for ticker in tickers if get_avanza_fund(ticker))
        frames = []
        if native:
            raw = yf.download(tickers=list(native), period=period, interval="1d", auto_adjust=True,
                              progress=False, threads=True, timeout=8)
            if raw.empty:
                raise ValueError("No price history")
            close = raw["Close"]
            if isinstance(close, pd.Series):
                close = close.to_frame(name=native[0])
            close.columns = [str(column) for column in close.columns]
            frames.append(close)
        if funds:
            with ThreadPoolExecutor(max_workers=4) as executor:
                frames.append(pd.concat(list(executor.map(lambda ticker: fetch_avanza_nav(ticker, period), funds)), axis=1))
        close = pd.concat(frames, axis=1).sort_index().dropna(how="all")
        close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
        _validate_prices(close, tickers)
        actual_dates = {ticker: str(close[ticker].dropna().index[-1].date()) for ticker in tickers}
        observations = {ticker: int(close[ticker].notna().sum()) for ticker in tickers}
        raw_prices = close[list(tickers)].copy()
        close = close[list(tickers)].ffill(limit=3).copy()
        source = "Avanza NAV + Yahoo Finance" if funds and native else ("Avanza NAV" if funds else "Yahoo Finance")
        close.attrs.update(source=source, is_example=False, fallback=False, cached=False,
                           fetched_at=pd.Timestamp.now(tz="UTC").isoformat(), actual_last_dates=actual_dates,
                           actual_observations=observations)
        try:
            _save_real_prices(raw_prices, tickers, period)
        except OSError:
            pass  # Valid market data remains usable when disk caching is unavailable.
        return close
    except Exception as error:
        cached = _load_real_prices(tickers, period)
        if cached is not None:
            return cached
        raise PriceDataError("Verklig prisdata kunde inte hämtas och komplett verifierad historik saknas i cachen. "
                             "Försök igen eller ändra instrumentvalet. Inga simulerade kurser används som ersättning.") from error

