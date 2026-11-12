"""Original portfolio and simulation calculations, independent of the UI."""
import numpy as np
import pandas as pd
from data import ensure_price_history_for_tickers, get_interval_price


def format_sek(value: float) -> str:
    return f"{value:,.0f} kr".replace(",", " ")



def format_decimal_sv(value: float, decimals: int = 2, signed: bool = False) -> str:
    numeric_value = round(float(value), decimals)
    template = f"{{:{'+' if signed else ''}.{decimals}f}}"
    formatted = template.format(numeric_value)
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    if formatted in {"-0", "-0.0", "-0.00"}:
        formatted = "0"
    return formatted.replace(".", ",")



def format_pct(value: float) -> str:
    return f"{format_decimal_sv(value)} %"



def format_signed_pct(value: float) -> str:
    formatted = format_decimal_sv(value, signed=True)
    if formatted == "0":
        formatted = "+0"
    return f"{formatted} %"



def format_date_sv(timestamp: pd.Timestamp) -> str:
    month_names = {
        1: "jan",
        2: "feb",
        3: "mar",
        4: "apr",
        5: "maj",
        6: "jun",
        7: "jul",
        8: "aug",
        9: "sep",
        10: "okt",
        11: "nov",
        12: "dec",
    }
    ts = pd.Timestamp(timestamp)
    return f"{ts.day} {month_names[ts.month]} {ts.year}"



def map_volatility_to_risk_level(volatility_pct: float) -> float:
    if pd.isna(volatility_pct):
        return np.nan
    buckets = [4, 8, 12, 18, 24, 30]
    for index, threshold in enumerate(buckets, start=1):
        if volatility_pct <= threshold:
            return float(index)
    return 7.0



def get_risk_profiles() -> dict:
    return {
        "Försiktig": {
            "description": "Lägre svängningar, högre andel räntor och fokus på stabilitet.",
            "risk_appetite": 3,
            "equity_target": 50,
            "max_single_holding": 30,
            "min_portfolio_sharpe": 0.65,
            "max_portfolio_volatility": 12.0,
            "max_drawdown_tolerance": 16.0,
            "equity_buffer": 2,
            "category_gap_threshold": 4,
            "top_three_threshold": 65,
            "minimum_trade_size": 1000,
            "target_weights": {
                "Globalfond": 25,
                "Sverigefond": 10,
                "Teknikfond": 5,
                "Tillväxtmarknad": 5,
                "Småbolagsfond": 5,
                "Räntefond": 50,
            },
        },
        "Balanserad": {
            "description": "En jämn mix av tillväxt och trygghet, med bred aktiespridning.",
            "risk_appetite": 6,
            "equity_target": 80,
            "max_single_holding": 35,
            "min_portfolio_sharpe": 0.50,
            "max_portfolio_volatility": 18.0,
            "max_drawdown_tolerance": 27.0,
            "equity_buffer": 5,
            "category_gap_threshold": 7,
            "top_three_threshold": 75,
            "minimum_trade_size": 1000,
            "target_weights": {
                "Globalfond": 35,
                "Sverigefond": 15,
                "Teknikfond": 10,
                "Tillväxtmarknad": 10,
                "Småbolagsfond": 10,
                "Räntefond": 20,
            },
        },
        "Aggressiv": {
            "description": "Hög tillväxtambition med större aktieandel och plats för tematiska innehav.",
            "risk_appetite": 8,
            "equity_target": 90,
            "max_single_holding": 40,
            "min_portfolio_sharpe": 0.35,
            "max_portfolio_volatility": 26.0,
            "max_drawdown_tolerance": 40.0,
            "equity_buffer": 8,
            "category_gap_threshold": 10,
            "top_three_threshold": 85,
            "minimum_trade_size": 1500,
            "target_weights": {
                "Globalfond": 35,
                "Sverigefond": 15,
                "Teknikfond": 15,
                "Tillväxtmarknad": 15,
                "Småbolagsfond": 10,
                "Räntefond": 10,
            },
        },
    }



def get_notification_intervals() -> dict:
    return {
        "Veckovis": {
            "reference_text": "förra veckan",
            "offset": pd.DateOffset(weeks=1),
            "trading_days": 5,
        },
        "Månadsvis": {
            "reference_text": "förra månaden",
            "offset": pd.DateOffset(months=1),
            "trading_days": 21,
        },
        "Kvartalsvis": {
            "reference_text": "förra kvartalet",
            "offset": pd.DateOffset(months=3),
            "trading_days": 63,
        },
        "Var 6:e månad": {
            "reference_text": "för sex månader sedan",
            "offset": pd.DateOffset(months=6),
            "trading_days": 126,
        },
        "Årligen": {
            "reference_text": "för ett år sedan",
            "offset": pd.DateOffset(years=1),
            "trading_days": 252,
        },
    }



def get_mock_backtest_intervals() -> dict:
    return {
        "1 vecka bakåt": {
            "reference_text": "för 1 vecka sedan",
            "trading_days": 5,
        },
        "1 månad bakåt": {
            "reference_text": "för 1 månad sedan",
            "trading_days": 21,
        },
        "1 kvartal bakåt": {
            "reference_text": "för 1 kvartal sedan",
            "trading_days": 63,
        },
        "6 månader bakåt": {
            "reference_text": "för 6 månader sedan",
            "trading_days": 126,
        },
        "1 år bakåt": {
            "reference_text": "för 1 år sedan",
            "trading_days": 252,
        },
    }



def get_mock_future_horizons() -> dict:
    return {
        "1 månad framåt": {
            "label": "nästa månad",
            "trading_days": 21,
        },
        "3 månader framåt": {
            "label": "nästa kvartal",
            "trading_days": 63,
        },
        "6 månader framåt": {
            "label": "kommande 6 månader",
            "trading_days": 126,
        },
    }



def get_mock_rebalance_modes() -> dict:
    return {
        "Buy and hold": {
            "period_code": None,
            "short_label": "buy and hold",
            "description": "Startvikterna sätts en gång och får sedan driva fritt med marknaden.",
        },
        "Månadsvis rebalansering": {
            "period_code": "M",
            "short_label": "månadsvis rebalansering",
            "description": "Portföljen återställs mot målvikterna vid slutet av varje månad.",
        },
        "Kvartalsvis rebalansering": {
            "period_code": "Q",
            "short_label": "kvartalsvis rebalansering",
            "description": "Portföljen återställs mot målvikterna vid slutet av varje kvartal.",
        },
    }



def get_analysis_windows() -> dict:
    return {
        "1 år": {"trading_days": 252},
        "3 år": {"trading_days": 756},
        "5 år": {"trading_days": 1260},
    }



def get_risk_preference_defaults(risk_appetite: int) -> dict:
    return {
        "max_portfolio_volatility": round(6 + risk_appetite * 2.2, 1),
        "min_portfolio_sharpe": round(0.8 - risk_appetite * 0.05, 2),
        "max_drawdown_tolerance": round(6 + risk_appetite * 3.5, 1),
    }



def parse_sv_date_input(date_text: str) -> pd.Timestamp | None:
    cleaned = "".join(character for character in date_text.strip() if character.isdigit())
    if len(cleaned) != 8:
        return None
    try:
        return pd.to_datetime(cleaned, format="%d%m%Y").normalize()
    except ValueError:
        return None



def resolve_input_date(calendar_value, manual_text: str) -> tuple[pd.Timestamp | None, bool]:
    manual_text = manual_text.strip()
    if manual_text:
        parsed = parse_sv_date_input(manual_text)
        if parsed is not None:
            return parsed, True
        if calendar_value is None:
            return None, False
        return pd.Timestamp(calendar_value).normalize(), False
    if calendar_value is None:
        return None, True
    return pd.Timestamp(calendar_value).normalize(), True



def get_risk_questionnaire() -> list[dict]:
    return [
        {
            "key": "risk_q_horizon",
            "question": "När tror du att pengarna kan behövas?",
            "weight": 25,
            "options": [
                {"label": "Inom 1-2 år", "score": 0.10},
                {"label": "Om 3-5 år", "score": 0.40},
                {"label": "Om 5-10 år", "score": 0.70},
                {"label": "Om mer än 10 år", "score": 1.00},
            ],
        },
        {
            "key": "risk_q_drawdown",
            "question": "Hur skulle du sannolikt reagera om portföljen faller 20 %?",
            "weight": 30,
            "options": [
                {"label": "Säljer för att minska risken", "score": 0.05},
                {"label": "Minskar lite och avvaktar", "score": 0.35},
                {"label": "Behåller och väntar ut", "score": 0.70},
                {"label": "Ökar om läget känns rätt", "score": 1.00},
            ],
        },
        {
            "key": "risk_q_goal",
            "question": "Vilket mål är viktigast med sparandet?",
            "weight": 15,
            "options": [
                {"label": "Skydda kapitalet", "score": 0.10},
                {"label": "Jämn balans mellan trygghet och tillväxt", "score": 0.55},
                {"label": "Hög långsiktig tillväxt", "score": 1.00},
            ],
        },
        {
            "key": "risk_q_experience",
            "question": "Hur van är du vid fonder, aktier och marknadssvängningar?",
            "weight": 15,
            "options": [
                {"label": "Ny inom sparande", "score": 0.15},
                {"label": "Lite erfarenhet", "score": 0.45},
                {"label": "God erfarenhet", "score": 0.75},
                {"label": "Mycket erfarenhet", "score": 1.00},
            ],
        },
        {
            "key": "risk_q_liquidity",
            "question": "Hur stort är behovet av att kunna använda pengarna snabbt?",
            "weight": 15,
            "options": [
                {"label": "Stort behov av snabb tillgång", "score": 0.10},
                {"label": "Viss flexibilitet behövs", "score": 0.40},
                {"label": "Litet behov på kort sikt", "score": 0.75},
                {"label": "Nästan inget behov alls", "score": 1.00},
            ],
        },
    ]



def calculate_drawdown(return_series: pd.Series) -> float:
    if return_series.empty:
        return 0.0
    cumulative = (1 + return_series).cumprod()
    drawdown = cumulative / cumulative.cummax() - 1
    return float(drawdown.min() * 100)



def compute_historical_metrics(
    price_history: pd.DataFrame,
    weights: dict,
    risk_free_rate_pct: float,
) -> tuple[pd.DataFrame, dict]:
    if price_history.empty:
        empty_cols = [
            "ticker",
            "annual_return_pct",
            "annual_volatility_pct",
            "sharpe_ratio",
            "max_drawdown_pct",
            "trailing_1m_pct",
        ]
        return pd.DataFrame(columns=empty_cols), {
            "annual_return_pct": 0.0,
            "annual_volatility_pct": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown_pct": 0.0,
        }

    returns = price_history.pct_change().dropna(how="all")
    annual_return = returns.mean() * 252 * 100
    annual_vol = returns.std() * np.sqrt(252) * 100
    risk_free_rate = risk_free_rate_pct
    sharpe = (annual_return - risk_free_rate) / annual_vol.replace(0, np.nan)
    max_drawdown = returns.apply(calculate_drawdown)
    trailing_1m = price_history.apply(
        lambda series: (series.dropna().iloc[-1] / get_interval_price(series, 21) - 1) * 100
        if not series.dropna().empty
        else 0.0
    )

    asset_metrics = pd.DataFrame(
        {
            "ticker": annual_return.index,
            "annual_return_pct": annual_return.values,
            "annual_volatility_pct": annual_vol.values,
            "sharpe_ratio": sharpe.fillna(0).values,
            "max_drawdown_pct": max_drawdown.values,
            "trailing_1m_pct": trailing_1m.values,
        }
    )

    usable_tickers = [ticker for ticker in weights if ticker in returns.columns]
    if not usable_tickers:
        portfolio_summary = {
            "annual_return_pct": 0.0,
            "annual_volatility_pct": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown_pct": 0.0,
        }
        return asset_metrics, portfolio_summary

    normalized_weights = pd.Series(weights, dtype=float)
    normalized_weights = normalized_weights[usable_tickers]
    normalized_weights = normalized_weights / normalized_weights.sum()
    portfolio_returns = returns[usable_tickers].mul(normalized_weights, axis=1).sum(axis=1)
    portfolio_annual_return = float(portfolio_returns.mean() * 252 * 100)
    portfolio_annual_vol = float(portfolio_returns.std() * np.sqrt(252) * 100)
    portfolio_sharpe = (
        (portfolio_annual_return - risk_free_rate) / portfolio_annual_vol
        if portfolio_annual_vol
        else 0.0
    )
    portfolio_max_drawdown = calculate_drawdown(portfolio_returns)

    portfolio_summary = {
        "annual_return_pct": portfolio_annual_return,
        "annual_volatility_pct": portfolio_annual_vol,
        "sharpe_ratio": portfolio_sharpe,
        "max_drawdown_pct": portfolio_max_drawdown,
    }
    return asset_metrics, portfolio_summary



def normalize_target_weights(raw_weights: dict) -> tuple[dict, float]:
    total = float(sum(raw_weights.values()))
    if total <= 0:
        equal_weight = 100 / len(raw_weights)
        return {category: equal_weight for category in raw_weights}, total

    normalized = {
        category: (weight / total) * 100 for category, weight in raw_weights.items()
    }
    return normalized, total



def build_personal_profile(profile_name: str, raw_weights: dict, max_single_holding: int) -> dict:
    normalized_weights, raw_total = normalize_target_weights(raw_weights)
    equity_target = sum(
        weight for category, weight in normalized_weights.items() if category != "Räntefond"
    )
    return {
        "description": "Personlig målprofil baserad på egna viktmål och egna varningsgränser.",
        "equity_target": equity_target,
        "max_single_holding": max_single_holding,
        "target_weights": normalized_weights,
        "raw_weight_total": raw_total,
        "profile_name": profile_name,
    }



def prepare_portfolio(
    portfolio: pd.DataFrame, profile: dict, asset_market_metrics: pd.DataFrame | None = None
) -> pd.DataFrame:
    df = portfolio.copy()
    total_value = df["value_sek"].sum() + float(portfolio.attrs.get("cash_value", 0.))
    previous_total = df["last_review_value_sek"].sum() + float(portfolio.attrs.get("cash_value", 0.))

    # Koppla varje innehav till en enkel målportfölj så att vi kan räkna ut gap i både vikt och kronor.
    df["current_weight"] = df["value_sek"] / total_value
    df["current_weight_pct"] = df["current_weight"] * 100
    df["last_review_weight_pct"] = df["last_review_value_sek"] / previous_total * 100
    df["weight_change_since_review_pct"] = (
        df["current_weight_pct"] - df["last_review_weight_pct"]
    )
    df["value_change_since_review_pct"] = (
        (df["value_sek"] / df["last_review_value_sek"]) - 1
    ) * 100
    target_key = "row_id" if "row_id" in df else "category"
    df["target_weight_pct"] = df[target_key].map(profile["target_weights"]).fillna(0)
    df["target_weight"] = df["target_weight_pct"] / 100
    df["target_value"] = total_value * df["target_weight"]
    df["trade_value"] = df["target_value"] - df["value_sek"]
    df["weight_gap_pct"] = df["target_weight_pct"] - df["current_weight_pct"]
    df["risk_contribution"] = df["current_weight"] * df["risk_level"]
    df["trade_action"] = df["trade_value"].apply(
        lambda x: "Köp" if x > 0 else ("Sälj" if x < 0 else "Behåll")
    )

    if asset_market_metrics is not None and not asset_market_metrics.empty:
        df = df.merge(asset_market_metrics, how="left", on="ticker")
    else:
        df["annual_return_pct"] = np.nan
        df["annual_volatility_pct"] = np.nan
        df["sharpe_ratio"] = np.nan
        df["max_drawdown_pct"] = np.nan
        df["trailing_1m_pct"] = np.nan

    df["risk_level"] = df["annual_volatility_pct"].apply(map_volatility_to_risk_level).fillna(df["risk_level"])
    df["risk_contribution"] = df["current_weight"] * df["risk_level"]
    df["weighted_sharpe_contribution"] = df["current_weight"] * df["sharpe_ratio"]
    return df



def calculate_metrics(df: pd.DataFrame, profile: dict, market_summary: dict) -> dict:
    cash = float(market_summary.get("cash_value", 0.))
    total_value = df["value_sek"].sum() + cash
    largest = df.sort_values("current_weight_pct", ascending=False).iloc[0]
    equity_exposure = (
        df.loc[df["asset_type"] == "Aktiefond", "value_sek"].sum() / total_value * 100
    )
    portfolio_risk = (df["current_weight"] * df["risk_level"]).sum()
    risk_score = round(portfolio_risk / 7 * 100)
    hhi = round(((df["current_weight"] ** 2).sum() + (cash / total_value) ** 2) * 10000)
    target_risk = round(
        (
            df["target_weight"]
            * df["risk_level"]
        ).sum()
        / 7
        * 100
    )
    top_three_share = sum(sorted(df["current_weight_pct"].tolist() + [cash / total_value * 100], reverse=True)[:3])
    return {
        "total_value": total_value,
        "largest_name": "Likvida medel" if cash > largest["value_sek"] else largest["name"],
        "largest_weight_pct": cash / total_value * 100 if cash > largest["value_sek"] else largest["current_weight_pct"],
        "equity_exposure": equity_exposure,
        "risk_score": risk_score,
        "target_risk_score": target_risk,
        "hhi": hhi,
        "top_three_share": top_three_share,
        "equity_gap": equity_exposure - profile["equity_target"],
        "portfolio_sharpe": market_summary["sharpe_ratio"],
        "portfolio_volatility_pct": market_summary["annual_volatility_pct"],
        "portfolio_return_pct": market_summary["annual_return_pct"],
        "portfolio_max_drawdown_pct": market_summary["max_drawdown_pct"],
    }



def detect_imbalances(
    df: pd.DataFrame, profile_name: str, profile: dict, settings: dict
) -> list:
    metrics = calculate_metrics(df, profile, settings["market_summary"])
    insights = []
    threshold = settings["concentration_threshold"]
    equity_buffer = settings["equity_buffer"]
    category_gap_threshold = settings["category_gap_threshold"]
    min_portfolio_sharpe = settings["min_portfolio_sharpe"]
    max_portfolio_volatility = settings["max_portfolio_volatility"]
    max_drawdown_tolerance = settings["max_drawdown_tolerance"]
    sharpe_scale = settings.get("sharpe_scale", 1.0)
    sharpe_basis = settings.get("sharpe_basis_label", "årsbasis")

    largest = df.sort_values("current_weight_pct", ascending=False).iloc[0]
    if largest["current_weight_pct"] > threshold:
        insights.append(
            {
                "tone": "warning",
                "title": f"Din valda gräns för {largest['name']} är passerad",
                "body": (
                    f"Innehavet står för {format_pct(largest['current_weight_pct'])} av portföljen. "
                    f"Det är över din egen gräns på {threshold} %. Om du vill följa din profil "
                    "kan det vara ett bra tillfälle att se över vikten."
                ),
            }
        )

    if metrics["equity_gap"] > equity_buffer:
        insights.append(
            {
                "tone": "warning",
                "title": "Aktieandelen ligger över din valda profil",
                "body": (
                    f"Portföljen ligger på {format_pct(metrics['equity_exposure'])} aktier, "
                    f"medan profilen {profile_name} är satt till cirka {format_pct(profile['equity_target'])}."
                ),
            }
        )

    if metrics["portfolio_sharpe"] < min_portfolio_sharpe:
        insights.append(
            {
                "tone": "warning",
                "title": "Den historiska Sharpekvoten är under din målnivå",
                "body": (
                    f"Portföljens historiska Sharpe · {sharpe_basis} är {format_decimal_sv(metrics['portfolio_sharpe'] * sharpe_scale)} "
                    f"mot ditt mål på {format_decimal_sv(min_portfolio_sharpe * sharpe_scale)} på samma skala."
                ),
            }
        )

    if metrics["portfolio_volatility_pct"] > max_portfolio_volatility:
        insights.append(
            {
                "tone": "warning",
                "title": "Portföljen svänger mer än din valda risknivå tillåter",
                "body": (
                    f"Historisk volatilitet på årsbasis är {format_pct(metrics['portfolio_volatility_pct'])}, "
                    f"vilket är över ditt tak på {format_pct(max_portfolio_volatility)}."
                ),
            }
        )

    if abs(metrics["portfolio_max_drawdown_pct"]) > max_drawdown_tolerance:
        insights.append(
            {
                "tone": "warning",
                "title": "Historisk nedgång är högre än din tolerans",
                "body": (
                    f"Portföljens största historiska fall är {format_pct(abs(metrics['portfolio_max_drawdown_pct']))}, "
                    f"mot din gräns på {format_pct(max_drawdown_tolerance)}."
                ),
            }
        )

    overweight = df.sort_values("weight_gap_pct").iloc[0]
    if overweight["weight_gap_pct"] < -category_gap_threshold:
        insights.append(
            {
                "tone": "warning",
                "title": f"Din målvikt för {overweight['category']} överskrids",
                "body": (
                    f"Nuvarande vikt är {format_pct(overweight['current_weight_pct'])}, "
                    f"medan din målvikt är {format_pct(overweight['target_weight_pct'])}. "
                    "Portföljen avviker därmed från den fördelning du har valt."
                ),
            }
        )

    underweight = df.sort_values("weight_gap_pct", ascending=False).iloc[0]
    if underweight["weight_gap_pct"] > category_gap_threshold:
        insights.append(
            {
                "tone": "info",
                "title": f"Din målvikt för {underweight['category']} underskrids",
                "body": (
                    f"Nuvarande vikt är {format_pct(underweight['current_weight_pct'])}, "
                    f"medan din målvikt är {format_pct(underweight['target_weight_pct'])}. "
                    "Det innebär att portföljen just nu ligger under din valda fördelning."
                ),
            }
        )

    weak_sharpe = df.sort_values("sharpe_ratio").iloc[0]
    if weak_sharpe["sharpe_ratio"] < min_portfolio_sharpe and weak_sharpe["current_weight_pct"] > 8:
        insights.append(
            {
                "tone": "info",
                "title": f"{weak_sharpe['name']} ligger under dina riskmål historiskt",
                "body": (
                    f"Innehavet har en historisk Sharpe · {sharpe_basis} på {format_decimal_sv(weak_sharpe['sharpe_ratio'] * sharpe_scale)} "
                    f"och väger {format_pct(weak_sharpe['current_weight_pct'])} i portföljen."
                ),
            }
        )

    if not insights:
        valid = settings["market_summary"].get("metrics_valid", True)
        insights.append(
            {
                "tone": "success" if valid else "info",
                "title": "Portföljen ligger nära dina valda nivåer" if valid else "Viktfördelningen ligger nära dina mål",
                "body": (
                    "Nuvarande fördelning ligger nära dina mål och de tillgängliga historiska riskmåtten håller sig inom dina valda ramar."
                    if valid else "Nuvarande fördelning ligger nära dina mål. Historiska riskmått saknar tillräckligt underlag."
                ),
            }
        )

    return insights



def build_trade_plan(df: pd.DataFrame, minimum_trade_size: int) -> pd.DataFrame:
    plan = df.copy()
    plan["trade_amount"] = plan["trade_value"].abs()
    plan = plan.loc[plan["trade_amount"] >= minimum_trade_size].copy()
    plan["action_text"] = plan.apply(
        lambda row: f"{row['trade_action']} {format_sek(row['trade_amount'])}", axis=1
    )
    return plan.sort_values("trade_amount", ascending=False)



def build_mock_allocation(
    watchlist: pd.DataFrame, selected_assets: list, fake_amount: int, raw_weights: dict
) -> tuple[pd.DataFrame, dict]:
    if not selected_assets:
        return pd.DataFrame(), {"raw_weight_total": 0.0, "fake_amount": fake_amount}

    weights, raw_total = normalize_target_weights(
        {asset: raw_weights.get(asset, 0.0) for asset in selected_assets}
    )
    df = watchlist.loc[watchlist["company_name"].isin(selected_assets)].copy()
    df["allocation_pct"] = df["company_name"].map(weights)
    df["investment_amount"] = fake_amount * df["allocation_pct"] / 100
    return df, {"raw_weight_total": raw_total, "fake_amount": fake_amount}



def get_rebalance_dates(index: pd.DatetimeIndex, rebalance_mode: str) -> set[pd.Timestamp]:
    period_code = get_mock_rebalance_modes()[rebalance_mode]["period_code"]
    if period_code is None or len(index) < 3:
        return set()

    grouped_period_ends = index.to_series().groupby(index.to_period(period_code)).last().tolist()
    if len(grouped_period_ends) <= 1:
        return set()
    return {pd.Timestamp(date) for date in grouped_period_ends[:-1]}



def simulate_historical_rebalanced_values(
    history: pd.DataFrame, initial_values: pd.Series, rebalance_mode: str
) -> tuple[pd.Series, pd.Series, int]:
    ordered_history = history.copy()
    if ordered_history.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float), 0

    target_weights = (initial_values / initial_values.sum()).reindex(ordered_history.columns).fillna(0.0)
    entry_prices = ordered_history.iloc[0]
    current_units = (initial_values.reindex(ordered_history.columns).fillna(0.0) / entry_prices).to_numpy(dtype=float)
    rebalance_dates = get_rebalance_dates(ordered_history.index, rebalance_mode)
    portfolio_values = []

    for date, prices in ordered_history.iterrows():
        price_vector = prices.to_numpy(dtype=float)
        current_values = current_units * price_vector
        portfolio_values.append(float(current_values.sum()))
        if pd.Timestamp(date) in rebalance_dates:
            total_value = float(current_values.sum())
            target_values = total_value * target_weights.to_numpy(dtype=float)
            current_units = np.divide(
                target_values,
                price_vector,
                out=np.zeros_like(target_values, dtype=float),
                where=price_vector != 0,
            )

    final_values = pd.Series(current_units * ordered_history.iloc[-1].to_numpy(dtype=float), index=ordered_history.columns)
    portfolio_history = pd.Series(portfolio_values, index=ordered_history.index)
    return portfolio_history, final_values, len(rebalance_dates)



def simulate_future_portfolio_paths(
    sampled_returns: np.ndarray,
    future_dates: pd.DatetimeIndex,
    initial_values: np.ndarray,
    rebalance_mode: str,
) -> tuple[np.ndarray, np.ndarray, int]:
    target_weights = initial_values / initial_values.sum()
    current_values = initial_values.astype(float).copy()
    portfolio_values = np.zeros(len(future_dates), dtype=float)
    rebalance_dates = get_rebalance_dates(future_dates, rebalance_mode)

    for day_index, date in enumerate(future_dates):
        current_values = current_values * (1 + sampled_returns[day_index])
        portfolio_values[day_index] = current_values.sum()
        if pd.Timestamp(date) in rebalance_dates:
            current_values = current_values.sum() * target_weights

    return portfolio_values, current_values, len(rebalance_dates)



def simulate_mock_backtest(
    watchlist: pd.DataFrame,
    price_history: pd.DataFrame,
    selected_assets: list,
    fake_amount: int,
    raw_weights: dict,
    interval_name: str | None = None,
    custom_start_date: pd.Timestamp | None = None,
    rebalance_mode: str = "Buy and hold",
) -> tuple[pd.DataFrame, dict]:
    df, allocation_meta = build_mock_allocation(
        watchlist, selected_assets, fake_amount, raw_weights
    )
    if df.empty:
        return df, allocation_meta

    simulation_history = ensure_price_history_for_tickers(
        price_history, df["ticker"].tolist(), period="5y"
    )
    tickers = [ticker for ticker in df["ticker"].tolist() if ticker in simulation_history.columns]
    if not tickers:
        return pd.DataFrame(), allocation_meta
    history = simulation_history[tickers].dropna(how="all").ffill()
    history = history.dropna(axis=1, how="all")
    if history.empty:
        return pd.DataFrame(), allocation_meta

    if custom_start_date is not None:
        custom_start_date = pd.Timestamp(custom_start_date).normalize()
        valid_dates = history.index[history.index >= custom_start_date]
        if len(valid_dates) < 2:
            return pd.DataFrame(), allocation_meta
        actual_start_date = pd.Timestamp(valid_dates[0])
        history = history.loc[actual_start_date:].ffill().dropna()
        reference_text = f"från {format_date_sv(actual_start_date)}"
        interval_label = format_date_sv(actual_start_date)
    else:
        interval = get_mock_backtest_intervals()[interval_name]
        start_index = max(0, len(history) - interval["trading_days"] - 1)
        history = history.iloc[start_index:].dropna(how="all")
        history = history.ffill().dropna()
        if history.empty:
            return pd.DataFrame(), allocation_meta
        actual_start_date = pd.Timestamp(history.index[0])
        reference_text = interval["reference_text"]
        interval_label = interval_name

    ticker_weights = df.set_index("ticker")["investment_amount"].reindex(history.columns).fillna(0.0)
    entry_prices = history.iloc[0]
    portfolio_history, final_values, rebalance_count = simulate_historical_rebalanced_values(
        history, ticker_weights, rebalance_mode
    )

    df = df.set_index("ticker").loc[history.columns].rename_axis("ticker").reset_index()
    df["entry_price"] = df["ticker"].map(entry_prices.to_dict())
    df["current_price"] = df["ticker"].map(history.iloc[-1].to_dict())
    df["units_bought"] = df["investment_amount"] / df["entry_price"]
    df["value_today"] = df["ticker"].map(final_values.to_dict())
    df["profit_loss"] = df["value_today"] - df["investment_amount"]
    df["return_pct"] = (df["value_today"] / df["investment_amount"] - 1) * 100

    invested = df["investment_amount"].sum()
    current_value = df["value_today"].sum()
    profit_loss = current_value - invested
    summary = {
        **allocation_meta,
        "interval_name": interval_label,
        "reference_text": reference_text,
        "actual_start_date": actual_start_date,
        "invested_amount": invested,
        "current_value": current_value,
        "profit_loss": profit_loss,
        "return_pct": (current_value / invested - 1) * 100 if invested else 0.0,
        "history_series": portfolio_history,
        "rebalance_mode": rebalance_mode,
        "rebalance_mode_label": get_mock_rebalance_modes()[rebalance_mode]["short_label"],
        "rebalance_count": rebalance_count,
    }
    return df.sort_values("return_pct", ascending=False), summary



def simulate_mock_future(
    watchlist: pd.DataFrame,
    price_history: pd.DataFrame,
    selected_assets: list,
    fake_amount: int,
    raw_weights: dict,
    horizon_name: str | None = None,
    custom_end_date: pd.Timestamp | None = None,
    simulations: int = 1000,
    block_size: int = 10,
    rebalance_mode: str = "Buy and hold",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    df, allocation_meta = build_mock_allocation(
        watchlist, selected_assets, fake_amount, raw_weights
    )
    if df.empty:
        return df, pd.DataFrame(), pd.DataFrame(), allocation_meta

    simulation_history = ensure_price_history_for_tickers(
        price_history, df["ticker"].tolist(), period="5y"
    )
    tickers = [ticker for ticker in df["ticker"].tolist() if ticker in simulation_history.columns]
    if not tickers:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), allocation_meta
    history = simulation_history[tickers].dropna(how="all").ffill().dropna()
    if history.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), allocation_meta

    returns = history.pct_change().dropna()
    if returns.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), allocation_meta

    last_history_date = pd.Timestamp(history.index[-1]).normalize()
    if custom_end_date is not None:
        custom_end_date = pd.Timestamp(custom_end_date).normalize()
        if custom_end_date <= last_history_date:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), allocation_meta
        future_dates = pd.bdate_range(last_history_date + pd.offsets.BDay(1), custom_end_date)
        label = f"fram till {format_date_sv(future_dates[-1])}" if len(future_dates) else "valt slutdatum"
        horizon_label = format_date_sv(custom_end_date)
    else:
        horizon = get_mock_future_horizons()[horizon_name]
        future_dates = pd.bdate_range(
            last_history_date + pd.offsets.BDay(1), periods=horizon["trading_days"]
        )
        label = horizon["label"]
        horizon_label = horizon_name

    horizon_days = len(future_dates)
    if horizon_days == 0:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), allocation_meta

    df = df.set_index("ticker").loc[history.columns].rename_axis("ticker").reset_index()
    ordered_returns = returns[df["ticker"].tolist()].copy()
    if ordered_returns.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), allocation_meta

    returns_matrix = ordered_returns.to_numpy(dtype=float)
    block_size = min(max(5, block_size), len(returns_matrix))
    max_start_index = len(returns_matrix) - block_size + 1
    if max_start_index <= 0:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), allocation_meta

    rng = np.random.default_rng(42)
    initial_values = df["investment_amount"].to_numpy(dtype=float)
    portfolio_paths = np.zeros((horizon_days, simulations), dtype=float)
    asset_final_returns = np.zeros((len(initial_values), simulations), dtype=float)
    rebalance_counts = []

    for simulation_index in range(simulations):
        sampled_blocks = []
        sampled_days = 0
        while sampled_days < horizon_days:
            start_index = int(rng.integers(0, max_start_index))
            block = returns_matrix[start_index : start_index + block_size]
            sampled_blocks.append(block)
            sampled_days += len(block)

        sampled_returns = np.vstack(sampled_blocks)[:horizon_days]
        simulated_portfolio_values, final_asset_values, rebalance_count = simulate_future_portfolio_paths(
            sampled_returns,
            future_dates,
            initial_values,
            rebalance_mode,
        )
        portfolio_paths[:, simulation_index] = simulated_portfolio_values
        asset_final_returns[:, simulation_index] = (final_asset_values / initial_values) - 1
        rebalance_counts.append(rebalance_count)

    final_values = portfolio_paths[-1]
    path_df = pd.DataFrame(
        {
            "date": future_dates,
            "p10": np.percentile(portfolio_paths, 10, axis=1),
            "median": np.percentile(portfolio_paths, 50, axis=1),
            "p90": np.percentile(portfolio_paths, 90, axis=1),
        }
    )

    df["Nedre spann (P10)"] = np.percentile(asset_final_returns, 10, axis=1) * 100
    df["Median (P50)"] = np.percentile(asset_final_returns, 50, axis=1) * 100
    df["Övre spann (P90)"] = np.percentile(asset_final_returns, 90, axis=1) * 100

    summary_df = pd.DataFrame(
        [
            {
                "scenario": "Nedre spann (P10)",
                "future_value": np.percentile(final_values, 10),
                "return_pct": (np.percentile(final_values, 10) / fake_amount - 1) * 100 if fake_amount else 0.0,
            },
            {
                "scenario": "Median (P50)",
                "future_value": np.percentile(final_values, 50),
                "return_pct": (np.percentile(final_values, 50) / fake_amount - 1) * 100 if fake_amount else 0.0,
            },
            {
                "scenario": "Övre spann (P90)",
                "future_value": np.percentile(final_values, 90),
                "return_pct": (np.percentile(final_values, 90) / fake_amount - 1) * 100 if fake_amount else 0.0,
            },
        ]
    )
    summary = {
        **allocation_meta,
        "horizon_name": horizon_label,
        "label": label,
        "median_value": np.percentile(final_values, 50),
        "median_return_pct": (np.percentile(final_values, 50) / fake_amount - 1) * 100 if fake_amount else 0.0,
        "p10_value": np.percentile(final_values, 10),
        "p90_value": np.percentile(final_values, 90),
        "probability_positive_pct": float((final_values > fake_amount).mean() * 100),
        "probability_loss_10_pct": float((final_values < fake_amount * 0.9).mean() * 100),
        "simulations": simulations,
        "block_size": block_size,
        "rebalance_mode": rebalance_mode,
        "rebalance_mode_label": get_mock_rebalance_modes()[rebalance_mode]["short_label"],
        "rebalance_count": int(np.median(rebalance_counts)) if rebalance_counts else 0,
    }
    return df, summary_df, path_df, summary



def build_watch_notifications(
    watchlist: pd.DataFrame, price_history: pd.DataFrame, selected_assets: list, interval_name: str
) -> pd.DataFrame:
    interval = get_notification_intervals()[interval_name]
    watch_df = watchlist.loc[watchlist["company_name"].isin(selected_assets)].copy()

    if watch_df.empty:
        return watch_df

    watch_df["base_price"] = watch_df["ticker"].map(
        lambda ticker: get_interval_price(price_history[ticker], interval["trading_days"])
        if ticker in price_history.columns
        else np.nan
    )
    watch_df["current_price"] = watch_df["ticker"].map(
        lambda ticker: float(price_history[ticker].dropna().iloc[-1]) if ticker in price_history.columns and not price_history[ticker].dropna().empty else np.nan
    )
    watch_df = watch_df.dropna(subset=["base_price", "current_price"]).copy()
    if watch_df.empty:
        return watch_df

    watch_df["change_pct"] = ((watch_df["current_price"] / watch_df["base_price"]) - 1) * 100
    watch_df["direction"] = watch_df["change_pct"].apply(
        lambda x: "ökat" if x >= 0 else "minskat"
    )
    watch_df["next_send_at"] = pd.Timestamp.today().normalize() + interval["offset"]
    watch_df["notification_text"] = watch_df.apply(
        lambda row: (
            f"{row['company_name']} har {row['direction']} med "
            f"{format_pct(abs(row['change_pct']))} sedan {interval['reference_text']}."
        ),
        axis=1,
    )
    return watch_df.sort_values("change_pct", ascending=False)



def build_rebalance_notification(
    df: pd.DataFrame, trade_plan: pd.DataFrame, profile_name: str, interval_name: str,
    category_gap_threshold: float = 0.0,
) -> dict:
    interval = get_notification_intervals()[interval_name]
    today = pd.Timestamp.today().normalize()
    next_send_at = today + interval["offset"]

    over = df.loc[df["weight_gap_pct"] < -category_gap_threshold - 1e-9].sort_values("weight_gap_pct")
    under = df.loc[df["weight_gap_pct"] > category_gap_threshold + 1e-9].sort_values("weight_gap_pct", ascending=False)
    if over.empty and under.empty:
        text = "Portföljen ligger inom dina valda viktgränser."
        return {"title": "Portföljen ligger inom viktgränserna", "body": text,
                "short_text": text, "next_send_at": next_send_at}

    deviations = []
    for rows, direction in ((over, "över"), (under, "under")):
        if not rows.empty:
            row = rows.iloc[0]
            deviations.append(
                f"{row['category']} ligger {format_decimal_sv(abs(row['weight_gap_pct']))} procentenheter {direction} mål"
            )
    drift_text = "; ".join(deviations) + "."
    available_changes = df.dropna(subset=["trailing_1m_pct"])
    change_text = ""
    if not available_changes.empty:
        biggest_change = available_changes.loc[available_changes["trailing_1m_pct"].abs().idxmax()]
        change_text = (
            f"Under den senaste månaden har {biggest_change['name']} rört sig "
            f"{format_signed_pct(biggest_change['trailing_1m_pct'])}. "
        )

    sell_row = trade_plan.loc[trade_plan["trade_action"] == "Sälj"].head(1)
    buy_rows = trade_plan.loc[trade_plan["trade_action"] == "Köp"].head(2)

    actions = []
    if not sell_row.empty:
        actions.append(
            f"sälj {sell_row.iloc[0]['name']} för {format_sek(sell_row.iloc[0]['trade_amount'])}"
        )
    for _, row in buy_rows.iterrows():
        actions.append(f"öka {row['name']} med {format_sek(row['trade_amount'])}")

    action_text = (
        f"För profilen {profile_name} visar affärsförslaget: {', '.join(actions[:3])}."
        if actions else "Inga affärer föreslås med din valda gräns för minsta affär."
    )
    short_text = "Portföljen avviker från dina valda viktgränser. " + drift_text
    body = (
        f"Nu är det dags för {interval_name.lower()} översyn. "
        f"{change_text}{drift_text} {action_text}"
    )
    return {
        "title": "Portföljen avviker från viktgränserna",
        "body": body,
        "short_text": short_text,
        "next_send_at": next_send_at,
    }



def simulate_contribution(df: pd.DataFrame, extra_contribution: int) -> pd.DataFrame:
    scenario = df.copy()
    total_after = scenario["value_sek"].sum() + extra_contribution
    scenario["target_after_cash"] = total_after * scenario["target_weight"]
    scenario["cash_gap"] = (scenario["target_after_cash"] - scenario["value_sek"]).clip(lower=0)

    # Nytt kapital går först till det som ligger under målvikten, så att säljbehovet minskar.
    if extra_contribution <= 0:
        scenario["cash_allocation"] = 0.0
    elif scenario["cash_gap"].sum() >= extra_contribution:
        scenario["cash_allocation"] = (
            extra_contribution * scenario["cash_gap"] / scenario["cash_gap"].sum()
        )
    else:
        remaining = extra_contribution - scenario["cash_gap"].sum()
        scenario["cash_allocation"] = scenario["cash_gap"] + (remaining * scenario["target_weight"])

    scenario["value_after_cash"] = scenario["value_sek"] + scenario["cash_allocation"]
    scenario["weight_after_cash_pct"] = scenario["value_after_cash"] / total_after * 100
    scenario["remaining_gap_pct"] = (
        scenario["target_weight_pct"] - scenario["weight_after_cash_pct"]
    )
    return scenario



