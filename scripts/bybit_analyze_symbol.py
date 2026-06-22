#!/usr/bin/env python3
"""
Read-only Bybit market analyzer for linear perpetual symbols.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from decimal import Decimal


DEFAULT_BASE_URL = "https://api-demo.bybit.com"
HTTP_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; trader-dev-bot/1.0)",
}

# Swing-trading timeframe set: 4h / daily / weekly trend alignment.
# Bybit kline intervals; "D" and "W" are daily and weekly candles.
INTERVALS = ["240", "D", "W"]
INTERVAL_LABELS = {"240": "4h", "D": "1d", "W": "1w"}
# Structure (swing high/low) timeframe used to derive stop-loss / take-profit.
STRUCTURE_INTERVAL = "D"


def normalize_symbol(symbol: str) -> str:
    return symbol.replace("/", "").replace("-", "").upper()


def public_get(base_url: str, path: str, params: dict[str, str]) -> dict:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(f"{base_url}{path}?{query}", headers=HTTP_HEADERS, method="GET")
    with urllib.request.urlopen(request, timeout=15) as response:
        data = json.loads(response.read().decode("utf-8"))
    if data.get("retCode") != 0:
        raise RuntimeError(json.dumps(data, indent=2))
    return data


def get_ticker(base_url: str, symbol: str) -> dict:
    data = public_get(base_url, "/v5/market/tickers", {"category": "linear", "symbol": symbol})
    return data["result"]["list"][0]


def get_closed_closes(base_url: str, symbol: str, interval: str, limit: int = 220) -> list[Decimal]:
    data = public_get(
        base_url,
        "/v5/market/kline",
        {"category": "linear", "symbol": symbol, "interval": interval, "limit": str(limit)},
    )
    rows = sorted(data["result"]["list"], key=lambda row: int(row[0]))
    return [Decimal(row[4]) for row in rows[:-1]]


def get_closed_candles(base_url: str, symbol: str, interval: str, limit: int = 80) -> list[dict[str, Decimal]]:
    data = public_get(
        base_url,
        "/v5/market/kline",
        {"category": "linear", "symbol": symbol, "interval": interval, "limit": str(limit)},
    )
    rows = sorted(data["result"]["list"], key=lambda row: int(row[0]))
    return [
        {
            "open": Decimal(row[1]),
            "high": Decimal(row[2]),
            "low": Decimal(row[3]),
            "close": Decimal(row[4]),
        }
        for row in rows[:-1]
    ]


def ema(values: list[Decimal], length: int) -> Decimal:
    multiplier = Decimal("2") / Decimal(length + 1)
    value = values[0]
    for price in values[1:]:
        value = (price - value) * multiplier + value
    return value


def rsi(values: list[Decimal], length: int = 14) -> Decimal:
    if len(values) <= length:
        raise RuntimeError("Not enough values for RSI")
    gains: list[Decimal] = []
    losses: list[Decimal] = []
    for previous, current in zip(values[-(length + 1) : -1], values[-length:]):
        change = current - previous
        gains.append(max(change, Decimal("0")))
        losses.append(abs(min(change, Decimal("0"))))
    avg_gain = sum(gains) / Decimal(length)
    avg_loss = sum(losses) / Decimal(length)
    if avg_loss == 0:
        return Decimal("100")
    relative_strength = avg_gain / avg_loss
    return Decimal("100") - (Decimal("100") / (Decimal("1") + relative_strength))


def local_levels(candles: list[dict[str, Decimal]], lookback: int = 20) -> tuple[Decimal, Decimal]:
    recent = candles[-lookback:]
    return max(candle["high"] for candle in recent), min(candle["low"] for candle in recent)


def timeframe_score(closes: list[Decimal]) -> tuple[int, Decimal, Decimal, Decimal]:
    fast = ema(closes[-80:], 21)
    slow = ema(closes[-160:], 55)
    momentum = rsi(closes)
    last = closes[-1]
    score = 0
    if last > fast:
        score += 1
    else:
        score -= 1
    if fast > slow:
        score += 1
    else:
        score -= 1
    if momentum >= Decimal("55"):
        score += 1
    elif momentum <= Decimal("45"):
        score -= 1
    return score, fast, slow, momentum


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze a Bybit linear perpetual symbol.")
    parser.add_argument("--symbol", default="BTC/USDT")
    args = parser.parse_args()

    symbol = normalize_symbol(args.symbol)
    base_url = (os.getenv("BYBIT_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    ticker = get_ticker(base_url, symbol)
    last_price = Decimal(ticker["lastPrice"])

    results = {}
    total_score = 0
    for interval in INTERVALS:
        closes = get_closed_closes(base_url, symbol, interval)
        score, fast, slow, momentum = timeframe_score(closes)
        total_score += score
        results[interval] = {
            "score": score,
            "last_close": closes[-1],
            "ema21": fast,
            "ema55": slow,
            "rsi14": momentum,
        }

    structure_candles = get_closed_candles(base_url, symbol, STRUCTURE_INTERVAL)
    local_high, local_low = local_levels(structure_candles)
    recommendation = "Buy" if total_score > 0 else "Sell"
    confidence = "strong" if abs(total_score) >= 6 else "moderate" if abs(total_score) >= 3 else "low"

    print(f"symbol: {symbol}")
    print(f"last_price: {last_price}")
    print(f"24h_change_pct: {ticker.get('price24hPcnt')}")
    print(f"local_high: {local_high}")
    print(f"local_low: {local_low}")
    print(f"total_score: {total_score}")
    print(f"recommendation: {recommendation}")
    print(f"confidence: {confidence}")
    for interval, data in results.items():
        print(
            f"{INTERVAL_LABELS.get(interval, interval)}: score={data['score']} close={data['last_close']} "
            f"ema21={data['ema21']:.8f} ema55={data['ema55']:.8f} rsi14={data['rsi14']:.2f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
