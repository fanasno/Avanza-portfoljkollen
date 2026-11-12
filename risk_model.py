"""Explicit observation window, SEK returns and separately chosen Sharpe horizon."""
import numpy as np
import pandas as pd
from engine import compute_historical_metrics

TRADING_DAYS = 252
MIN_OBSERVATIONS = 20


def get_risk_windows():
    return {"1 månad": 21, "3 månader": 63, "6 månader": 126, "1 år": 252,
            "3 år": 756, "5 år": 1260, "Egna datum": None}


def select_risk_history(prices, window="3 år", start=None, end=None):
    if prices.empty:
        return prices.copy()
    if window not in get_risk_windows():
        raise ValueError("Okänt historiskt analysfönster.")
    if window == "Egna datum":
        start = pd.Timestamp(start) if start is not None else prices.index[0]
        end = pd.Timestamp(end) if end is not None else prices.index[-1]
        if start > end:
            return prices.iloc[:0].copy()
        return prices.loc[(prices.index >= start) & (prices.index <= end)].copy()
    return prices.tail(get_risk_windows()[window] + 1).copy()


def horizon_factor(months):
    if not np.isfinite(months) or months <= 0:
        raise ValueError("Sparhorisonten måste vara positiv.")
    return np.sqrt(months / 12)


def sharpe_from_values(values, annual_risk_free_pct=2.):
    """Daily arithmetic excess returns; undefined/short estimates stay NaN.

    Annualization and horizon scaling assume stationary, uncorrelated returns.
    They are conventions, not a forecast or a guarantee over a holding period.
    """
    values = np.asarray(values, dtype=float)
    if values.ndim == 1:
        values = values[:, None]
    if not np.isfinite(annual_risk_free_pct) or annual_risk_free_pct <= -100:
        raise ValueError("Riskfri årsränta måste vara ändlig och större än -100 %.")
    paths = values.shape[1]
    invalid = (~np.isfinite(values).all(axis=0)) | (values <= 0).any(axis=0)
    if len(values) - 1 < MIN_OBSERVATIONS:
        return np.full(paths, np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        returns = values[1:] / values[:-1] - 1
        risk_free_daily = np.expm1(np.log1p(annual_risk_free_pct / 100) / TRADING_DAYS)
        vol = np.std(returns, axis=0, ddof=1)
        result = np.divide(np.mean(returns, axis=0) - risk_free_daily, vol,
                           out=np.full(paths, np.nan), where=vol > 1e-12) * np.sqrt(TRADING_DAYS)
    result[invalid] = np.nan
    return result


def portfolio_prices_sek(prices, portfolio):
    converted = {}
    for row in portfolio.to_dict("records"):
        ticker, currency = row["ticker"], row["currency"]
        if ticker not in prices:
            raise ValueError(f"Priser saknas för {ticker}.")
        if currency == "SEK":
            converted[ticker] = prices[ticker]
        else:
            fx = currency + "SEK=X"
            if fx not in prices:
                raise ValueError(f"Valutakurs saknas för {currency}/SEK.")
            converted[ticker] = prices[ticker] * prices[fx]
    common = pd.DataFrame(converted).ffill(limit=3).dropna()
    actual = prices.attrs.get("actual_last_dates", {})
    ends = [pd.Timestamp(actual[ticker]) for ticker in converted if ticker in actual]
    return common.loc[:min(ends)] if ends else common


def compute_risk_metrics(prices, weights, risk_free_rate_pct, cash_value=0.):
    observations = max(0, len(prices) - 1)
    metrics_valid = observations >= MIN_OBSERVATIONS and bool(
        np.isfinite(prices.to_numpy()).all() and (prices.to_numpy() > 0).all()
    )
    if not metrics_valid:
        assets, summary = compute_historical_metrics(prices.iloc[:0], weights, risk_free_rate_pct)
        assets = assets.reindex(range(len(prices.columns)))
        assets["ticker"] = prices.columns
        summary = {key: np.nan for key in summary}
        summary.update(risk_valid=False, metrics_valid=False, observations=observations, cash_value=cash_value)
        return assets, summary
    assets, summary = compute_historical_metrics(prices, weights, risk_free_rate_pct)
    # Keep original annual-return/volatility definitions, while converting the
    # editable annual risk-free rate to a matching daily rate for Sharpe.
    asset_sharpes = sharpe_from_values(prices.to_numpy(), risk_free_rate_pct)
    assets["sharpe_ratio"] = assets.ticker.map(dict(zip(prices.columns, asset_sharpes)))
    returns = prices.pct_change(fill_method=None).iloc[1:]
    weight_vector = pd.Series(weights).reindex(prices.columns).fillna(0.)
    weight_vector /= weight_vector.sum() + cash_value
    portfolio_returns = returns.mul(weight_vector, axis=1).sum(axis=1)
    values = np.r_[1., np.cumprod(1 + portfolio_returns.to_numpy())]
    sharpe = float(sharpe_from_values(values, risk_free_rate_pct)[0])
    if cash_value:
        summary.update(annual_return_pct=float(portfolio_returns.mean() * 252 * 100),
                       annual_volatility_pct=float(portfolio_returns.std() * np.sqrt(252) * 100),
                       max_drawdown_pct=float((values / np.maximum.accumulate(values) - 1).min() * 100))
    summary.update(sharpe_ratio=sharpe, risk_valid=bool(np.isfinite(sharpe)),
                   metrics_valid=True, observations=len(returns), cash_value=cash_value)
    return assets, summary
