"""Reviewed Avanza fund identities. AVANZA: IDs are internal keys, not Yahoo tickers."""
import json
from pathlib import Path

CATALOG = json.loads(Path(__file__).with_suffix(".json").read_text(encoding="utf-8"))
FUNDS = {fund["ticker"]: fund for fund in CATALOG["funds"]}


def get_avanza_funds():
    return [dict(fund) for fund in FUNDS.values()]


def get_avanza_fund(ticker):
    return FUNDS.get(ticker)
