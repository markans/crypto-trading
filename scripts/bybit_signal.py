#!/usr/bin/env python3
"""
Daily strong-signal generator for Bybit linear perpetuals.

This is signal-only. It:
- analyzes a symbol with the local read-only signal logic
- builds a suggested entry / stop-loss / take-profit plan
- prints the signal, appends it to a markdown log, and emails it

It never places orders. Acting on a signal is a manual decision.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import bybit_analyze_symbol as analyzer
import bybit_signal_plan as plan_builder
import notify_email


DEFAULT_BASE_URL = "https://api-demo.bybit.com"
LIVE_BASE_URL = "https://api.bybit.com"
BINANCE_BASE_URLS = [
    "https://api.binance.com",
    "https://api.binance.us",
]
ALLOWED_BASE_URLS = {
    "https://api-demo.bybit.com",
    LIVE_BASE_URL,
}
CONFIDENCE_RANK = {"low": 0, "moderate": 1, "strong": 2}

COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"
# Symbols that rank high by market cap but are not useful as USDT perps:
# stablecoins, wrapped/staked assets, and exchange tokens without a liquid perp.
STABLE_OR_WRAPPED = {
    "USDT", "USDC", "DAI", "FDUSD", "TUSD", "BUSD", "USDE", "USDS", "USD1",
    "PYUSD", "USDD", "GUSD", "WBTC", "WETH", "WBETH", "WSTETH", "STETH",
    "WEETH", "RETH", "CBETH", "SUSDE", "LEO", "BSC-USD",
}
# Fallback list (top market-cap perps) used only if CoinGecko is unreachable.
DEFAULT_TOP_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT",
    "ADAUSDT", "TRXUSDT", "LINKUSDT", "AVAXUSDT", "XLMUSDT", "BCHUSDT",
    "HBARUSDT", "LTCUSDT", "DOTUSDT", "SUIUSDT", "UNIUSDT", "NEARUSDT",
    "AAVEUSDT", "APTUSDT",
]


def decimal_text(value: Decimal | str) -> str:
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    return str(value)


def validate_base_url(base_url: str) -> str:
    normalized = base_url.strip().strip('"').strip("'")
    if "=" in normalized:
        key, value = normalized.split("=", 1)
        if key.strip() == "BYBIT_BASE_URL":
            normalized = value.strip().strip('"').strip("'")
    normalized = normalized.rstrip("/")
    if normalized not in ALLOWED_BASE_URLS:
        allowed = ", ".join(sorted(ALLOWED_BASE_URLS))
        raise RuntimeError(
            f"BYBIT_BASE_URL must be only the URL value, one of: {allowed}. "
            "Example secret value: https://api-demo.bybit.com"
        )
    return normalized


def resolve_market_base_url(trade_base_url: str) -> str:
    configured = os.getenv("BYBIT_MARKET_BASE_URL")
    if configured:
        return validate_base_url(configured)
    if "api-demo.bybit.com" in trade_base_url:
        return LIVE_BASE_URL
    return trade_base_url


def public_json(base_url: str, path: str, params: dict[str, str]) -> dict | list:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{base_url}{path}?{query}",
        headers=analyzer.HTTP_HEADERS,
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_top_marketcap_candidates(count: int) -> list[str]:
    """Return USDT-perp symbol candidates ordered by market cap.

    Pulls more than `count` so stablecoins/wrapped tokens and any symbols that
    lack a tradeable perp can be filtered out downstream while still leaving
    enough names to reach `count`. Falls back to a static list if CoinGecko is
    unreachable.
    """
    per_page = count + 30
    url = (
        f"{COINGECKO_MARKETS_URL}?vs_currency=usd&order=market_cap_desc"
        f"&per_page={per_page}&page=1&sparkline=false"
    )
    request = urllib.request.Request(url, headers=analyzer.HTTP_HEADERS, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        print(f"top_marketcap_fallback: CoinGecko unavailable ({exc}); using static list")
        return list(DEFAULT_TOP_SYMBOLS)

    if not isinstance(data, list):
        print(f"top_marketcap_fallback: unexpected CoinGecko response; using static list")
        return list(DEFAULT_TOP_SYMBOLS)

    candidates: list[str] = []
    for coin in data:
        symbol = str(coin.get("symbol", "")).upper()
        if not symbol or symbol in STABLE_OR_WRAPPED:
            continue
        candidates.append(f"{symbol}USDT")
    return candidates or list(DEFAULT_TOP_SYMBOLS)


def ny_time_allowed(target: str, window_minutes: int, now: datetime | None = None) -> tuple[bool, str]:
    current = now or datetime.now(ZoneInfo("America/New_York"))
    try:
        target_hour, target_minute = [int(part) for part in target.split(":", 1)]
    except ValueError as exc:
        raise RuntimeError("--ny-time must use HH:MM format, for example 09:30") from exc

    target_minutes = target_hour * 60 + target_minute
    current_minutes = current.hour * 60 + current.minute
    delta = abs(current_minutes - target_minutes)
    delta = min(delta, (24 * 60) - delta)
    return delta <= window_minutes, current.strftime("%Y-%m-%d %H:%M:%S %Z")


def run_signal(base_url: str, symbol: str) -> dict[str, object]:
    ticker = analyzer.get_ticker(base_url, symbol)
    last_price = Decimal(ticker["lastPrice"])

    results: dict[str, dict[str, Decimal | int]] = {}
    total_score = 0
    for interval in analyzer.INTERVALS:
        closes = analyzer.get_closed_closes(base_url, symbol, interval)
        score, fast, slow, momentum = analyzer.timeframe_score(closes)
        total_score += score
        results[interval] = {
            "score": score,
            "last_close": closes[-1],
            "ema21": fast,
            "ema55": slow,
            "rsi14": momentum,
        }

    structure_candles = analyzer.get_closed_candles(base_url, symbol, analyzer.STRUCTURE_INTERVAL)
    local_high, local_low = analyzer.local_levels(structure_candles)
    recommendation = "Buy" if total_score > 0 else "Sell"
    confidence = "strong" if abs(total_score) >= 6 else "moderate" if abs(total_score) >= 3 else "low"

    return {
        "market_source": base_url,
        "symbol": symbol,
        "last_price": last_price,
        "24h_change_pct": ticker.get("price24hPcnt"),
        "local_high": local_high,
        "local_low": local_low,
        "total_score": total_score,
        "recommendation": recommendation,
        "confidence": confidence,
        "timeframes": results,
    }


def binance_interval(bybit_interval: str) -> str:
    return {
        "240": "4h",
        "D": "1d",
        "W": "1w",
    }.get(bybit_interval, bybit_interval)


def binance_klines(base_url: str, symbol: str, interval: str, limit: int) -> list[list[object]]:
    data = public_json(
        base_url,
        "/api/v3/klines",
        {"symbol": symbol, "interval": binance_interval(interval), "limit": str(limit)},
    )
    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected Binance kline response: {data}")
    return data


def binance_closed_closes(base_url: str, symbol: str, interval: str, limit: int = 220) -> list[Decimal]:
    rows = binance_klines(base_url, symbol, interval, limit)
    return [Decimal(str(row[4])) for row in rows[:-1]]


def binance_closed_candles(base_url: str, symbol: str, interval: str, limit: int = 80) -> list[dict[str, Decimal]]:
    rows = binance_klines(base_url, symbol, interval, limit)
    return [
        {
            "open": Decimal(str(row[1])),
            "high": Decimal(str(row[2])),
            "low": Decimal(str(row[3])),
            "close": Decimal(str(row[4])),
        }
        for row in rows[:-1]
    ]


def run_binance_signal(base_url: str, symbol: str) -> dict[str, object]:
    ticker = public_json(base_url, "/api/v3/ticker/24hr", {"symbol": symbol})
    if not isinstance(ticker, dict):
        raise RuntimeError(f"Unexpected Binance ticker response: {ticker}")
    last_price = Decimal(str(ticker["lastPrice"]))

    results: dict[str, dict[str, Decimal | int]] = {}
    total_score = 0
    for interval in analyzer.INTERVALS:
        closes = binance_closed_closes(base_url, symbol, interval)
        score, fast, slow, momentum = analyzer.timeframe_score(closes)
        total_score += score
        results[interval] = {
            "score": score,
            "last_close": closes[-1],
            "ema21": fast,
            "ema55": slow,
            "rsi14": momentum,
        }

    structure_candles = binance_closed_candles(base_url, symbol, analyzer.STRUCTURE_INTERVAL)
    local_high, local_low = analyzer.local_levels(structure_candles)
    recommendation = "Buy" if total_score > 0 else "Sell"
    confidence = "strong" if abs(total_score) >= 6 else "moderate" if abs(total_score) >= 3 else "low"

    return {
        "market_source": base_url,
        "symbol": symbol,
        "last_price": last_price,
        "24h_change_pct": ticker.get("priceChangePercent"),
        "local_high": local_high,
        "local_low": local_low,
        "total_score": total_score,
        "recommendation": recommendation,
        "confidence": confidence,
        "timeframes": results,
    }


def run_signal_with_fallback(base_url: str, symbol: str) -> dict[str, object]:
    errors: list[str] = []
    try:
        return run_signal(base_url, symbol)
    except Exception as exc:
        errors.append(f"{base_url}: {exc}")

    for fallback_url in BINANCE_BASE_URLS:
        try:
            signal = run_binance_signal(fallback_url, symbol)
            print("market_data_fallback: Bybit public market data failed; using Binance public market data")
            print("market_data_errors:")
            for error in errors:
                print(f"- {error}")
            return signal
        except Exception as exc:
            errors.append(f"{fallback_url}: {exc}")

    raise RuntimeError("All market-data sources failed:\n" + "\n".join(f"- {error}" for error in errors))


def signal_lines(signal: dict[str, object]) -> list[str]:
    lines = [
        f"market_source: {signal.get('market_source', 'unknown')}",
        f"symbol: {signal['symbol']}",
        f"last_price: {signal['last_price']}",
        f"24h_change_pct: {signal['24h_change_pct']}",
        f"local_high: {signal['local_high']}",
        f"local_low: {signal['local_low']}",
        f"total_score: {signal['total_score']}",
        f"recommendation: {signal['recommendation']}",
        f"confidence: {signal['confidence']}",
    ]
    timeframes = signal["timeframes"]
    assert isinstance(timeframes, dict)
    for interval, data in timeframes.items():
        assert isinstance(data, dict)
        label = analyzer.INTERVAL_LABELS.get(interval, interval)
        lines.append(
            f"{label}: score={data['score']} close={data['last_close']} "
            f"ema21={data['ema21']:.8f} ema55={data['ema55']:.8f} rsi14={data['rsi14']:.2f}"
        )
    return lines


def print_signal(signal: dict[str, object]) -> None:
    for line in signal_lines(signal):
        print(line)


def reward_risk(plan: dict[str, Decimal | str]) -> Decimal | None:
    entry = Decimal(str(plan["entry_reference"]))
    stop_loss = Decimal(str(plan["stop_loss"]))
    take_profit = Decimal(str(plan["take_profit"]))
    if plan["side"] == "Buy":
        risk = entry - stop_loss
        reward = take_profit - entry
    else:
        risk = stop_loss - entry
        reward = entry - take_profit
    if risk <= 0:
        return None
    return reward / risk


def plan_lines(plan: dict[str, Decimal | str]) -> list[str]:
    lines = [f"{key}: {value}" for key, value in plan.items()]
    rr = reward_risk(plan)
    lines.append(f"reward_risk: {rr.quantize(Decimal('0.01')) if rr is not None else 'invalid'}")
    return lines


def email_signal(
    signal: dict[str, object],
    plan: dict[str, Decimal | str] | None,
    reason: str,
) -> None:
    symbol = signal["symbol"]
    recommendation = signal["recommendation"]
    confidence = signal["confidence"]
    now = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M %Z")
    subject = f"[Signal] {symbol} {recommendation} ({confidence}) - {now}"

    body_lines = [f"Trading signal - {now}", "", *signal_lines(signal), "", f"note: {reason}"]
    if plan:
        body_lines += ["", "Suggested plan (manual action required, no order placed):", *plan_lines(plan)]
    body_lines += ["", "This is an alert only. No order was placed."]
    notify_email.send_email(subject, "\n".join(body_lines))


def email_digest(
    results: list[dict[str, object]],
    failures: list[tuple[str, str]],
    min_rank: int,
) -> bool:
    """Send one summary email for a multi-symbol scan. Returns True if sent."""
    qualifying = [r for r in results if CONFIDENCE_RANK[str(r["confidence"])] >= min_rank]
    if not qualifying:
        return False

    now = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M %Z")
    strong = [r for r in qualifying if r["confidence"] == "strong"]
    subject = f"[Swing] {len(qualifying)} signal(s), {len(strong)} strong - {now}"

    body_lines = [f"Daily swing scan - {now}", f"{len(results)} symbols analyzed.", ""]
    for result in qualifying:
        signal = result["signal"]
        assert isinstance(signal, dict)
        plan = result["plan"]
        body_lines.append(
            f"{signal['symbol']}: {signal['recommendation']} ({signal['confidence']}) "
            f"total_score={signal['total_score']} last_price={signal['last_price']}"
        )
        if isinstance(plan, dict):
            rr = reward_risk(plan)
            body_lines.append(
                f"  plan: entry={decimal_text(plan['entry_reference'])} "
                f"SL={decimal_text(plan['stop_loss'])} TP={decimal_text(plan['take_profit'])} "
                f"qty={decimal_text(plan['qty'])} "
                f"reward_risk={rr.quantize(Decimal('0.01')) if rr is not None else 'invalid'}"
            )
        body_lines.append("")

    if failures:
        body_lines.append("Skipped (no data / not tradeable):")
        body_lines += [f"- {symbol}: {error}" for symbol, error in failures]
        body_lines.append("")

    body_lines.append("This is an alert only. No order was placed.")
    notify_email.send_email(subject, "\n".join(body_lines))
    return True


def email_failure(symbol: str, error: str) -> None:
    now = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M %Z")
    subject = f"[Signal FAILED] {symbol} - {now}"
    body = f"The signal run failed at {now}.\n\nsymbol: {symbol}\nerror: {error}\n"
    notify_email.send_email(subject, body)


def append_log(
    path: str,
    signal: dict[str, object],
    plan: dict[str, Decimal | str] | None,
    reason: str,
) -> None:
    now = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S %Z")
    timeframes = signal["timeframes"]
    assert isinstance(timeframes, dict)
    rr = reward_risk(plan) if plan else None
    side = plan["side"] if plan else signal["recommendation"]

    lines = [
        "",
        f"## {now} - {signal['symbol']} signal",
        "",
        f"- date_time: {now}",
        f"- symbol: {signal['symbol']}",
        f"- analyzer_recommendation: {signal['recommendation']}",
        f"- confidence: {signal['confidence']}",
        f"- 4h_score: {timeframes['240']['score']}",
        f"- 1d_score: {timeframes['D']['score']}",
        f"- 1w_score: {timeframes['W']['score']}",
        f"- side_considered: {side}",
        f"- entry_reference: {decimal_text(plan['entry_reference']) if plan else 'N/A'}",
        f"- stop_loss: {decimal_text(plan['stop_loss']) if plan else 'N/A'}",
        f"- take_profit: {decimal_text(plan['take_profit']) if plan else 'N/A'}",
        f"- reward_risk: {rr.quantize(Decimal('0.01')) if rr is not None else 'N/A'}",
        f"- margin_usdt: {decimal_text(plan['margin_usdt']) if plan else 'N/A'}",
        f"- leverage: {decimal_text(plan['leverage']) if plan else 'N/A'}",
        f"- qty: {decimal_text(plan['qty']) if plan else 'N/A'}",
        f"- signal_comment: Automated daily swing check after the daily close. No order is placed; act manually.",
        f"- reason: {reason}",
        "- result_r_multiple: N/A",
    ]
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def build_fallback_plan(
    signal: dict[str, object],
    side: str,
    margin: Decimal,
    leverage: Decimal,
) -> dict[str, Decimal | str]:
    entry = Decimal(str(signal["last_price"]))
    local_high = Decimal(str(signal["local_high"]))
    local_low = Decimal(str(signal["local_low"]))
    notional = margin * leverage
    qty = (notional / entry).quantize(Decimal("0.001"))

    if side == "Buy":
        stop_loss = local_low if local_low < entry else entry * Decimal("0.99")
        take_profit = local_high if local_high > entry else entry * Decimal("1.01")
    else:
        stop_loss = local_high if local_high > entry else entry * Decimal("1.01")
        take_profit = local_low if local_low < entry else entry * Decimal("0.99")

    return {
        "symbol": str(signal["symbol"]),
        "side": side,
        "margin_mode": "REGULAR_MARGIN (Cross)",
        "margin_usdt": margin,
        "leverage": leverage,
        "notional_usdt": notional,
        "entry_reference": entry,
        "qty": qty,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "target_source": f"{signal.get('market_source', 'fallback')} local high/low fallback",
    }


def process_symbol(
    args: argparse.Namespace,
    market_base_url: str,
    symbol: str,
) -> dict[str, object]:
    """Analyze one symbol, build a plan for strong signals, and log it."""
    signal = run_signal_with_fallback(market_base_url, symbol)
    print_signal(signal)

    confidence = str(signal["confidence"])
    plan: dict[str, Decimal | str] | None = None

    if confidence == "strong":
        side = str(signal["recommendation"])
        plan_args = SimpleNamespace(
            symbol=symbol,
            side=side,
            margin=args.margin,
            leverage=args.leverage,
            tp_sl_mode=args.tp_sl_mode,
            structure_interval=args.structure_interval,
            stop_loss_pnl_pct=args.stop_loss_pnl_pct,
            take_profit_pnl_pct=args.take_profit_pnl_pct,
            entry_price=None,
        )
        try:
            plan = plan_builder.build_plan(plan_args, market_base_url)
        except Exception as exc:
            print(f"plan_fallback: Bybit public planning data failed; using signal local levels: {exc}")
            plan = build_fallback_plan(signal, side, args.margin, args.leverage)

        print(f"Bybit {plan_builder.environment_label(market_base_url)} {plan['symbol']} suggested plan")
        for line in plan_lines(plan):
            print(line)
        reason = "strong signal; suggested plan below. Act manually if you choose to trade."
    else:
        reason = f"confidence is {confidence}; suggested plan is only built for strong signals"
        print(f"No plan built: {reason}.")

    if not args.no_log:
        append_log(args.log_file, signal, plan, reason)

    return {"signal": signal, "plan": plan, "reason": reason, "confidence": confidence}


def resolve_symbols(args: argparse.Namespace, count: int | None) -> list[str]:
    if count:
        return fetch_top_marketcap_candidates(count)
    if args.symbols:
        return [analyzer.normalize_symbol(part) for part in args.symbols.split(",") if part.strip()]
    return [analyzer.normalize_symbol(args.symbol)]


def run(args: argparse.Namespace) -> int:
    plan_builder.load_dotenv()
    market_base_url = resolve_market_base_url(
        validate_base_url(os.getenv("BYBIT_BASE_URL") or DEFAULT_BASE_URL)
    )
    print(f"market_base_url: {market_base_url}")

    if args.ny_time:
        allowed, ny_now = ny_time_allowed(args.ny_time, args.ny_window_minutes)
        print(f"New York time: {ny_now}")
        if not allowed:
            print(f"Outside --ny-time {args.ny_time} +/- {args.ny_window_minutes} minutes. No action.")
            return 0

    top_count = args.top_marketcap
    candidates = resolve_symbols(args, top_count)
    single_mode = top_count is None and len(candidates) == 1
    if top_count:
        print(f"top_marketcap: scanning up to {top_count} tradeable symbols by market cap")

    min_rank = CONFIDENCE_RANK[args.email_min_confidence]
    results: list[dict[str, object]] = []
    failures: list[tuple[str, str]] = []

    for symbol in candidates:
        symbol = analyzer.normalize_symbol(symbol)
        print(f"\n=== {symbol} ===")
        try:
            results.append(process_symbol(args, market_base_url, symbol))
        except Exception as exc:
            print(f"skip {symbol}: {exc}")
            failures.append((symbol, str(exc)))
            continue
        if top_count and len(results) >= top_count:
            break

    if args.no_email:
        return 0

    if single_mode and results:
        result = results[0]
        signal = result["signal"]
        assert isinstance(signal, dict)
        plan = result["plan"]
        if CONFIDENCE_RANK[str(result["confidence"])] >= min_rank:
            email_signal(
                signal,
                plan if isinstance(plan, dict) else None,
                str(result["reason"]),
            )
    elif not single_mode:
        sent = email_digest(results, failures, min_rank)
        if not sent:
            print("No signals at or above the email threshold; no digest email sent.")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a strong-signal alert for a Bybit symbol (no trading).")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--symbols", help="Comma-separated symbols to scan (overrides --symbol).")
    parser.add_argument(
        "--top-marketcap",
        type=int,
        help="Scan the top N tradeable USDT-perp symbols by market cap (overrides --symbol/--symbols).",
    )
    parser.add_argument("--margin", type=Decimal, default=Decimal("25"))
    parser.add_argument("--leverage", type=Decimal, default=Decimal("5"))
    parser.add_argument("--tp-sl-mode", choices=["pnl", "structure"], default="structure")
    parser.add_argument("--structure-interval", default="D")
    parser.add_argument("--stop-loss-pnl-pct", type=Decimal, default=Decimal("50"))
    parser.add_argument("--take-profit-pnl-pct", type=Decimal, default=Decimal("150"))
    parser.add_argument("--ny-time", help="Only run inside this America/New_York HH:MM time window.")
    parser.add_argument("--ny-window-minutes", type=int, default=45)
    parser.add_argument("--log-file", default="SIGNAL-LOG.md")
    parser.add_argument("--no-log", action="store_true")
    parser.add_argument("--no-email", action="store_true", help="Do not send any email notification.")
    parser.add_argument(
        "--email-min-confidence",
        choices=["low", "moderate", "strong"],
        default="strong",
        help="Only email signals at or above this confidence (default strong).",
    )
    args = parser.parse_args()

    if args.top_marketcap:
        failure_label = f"top-{args.top_marketcap} market-cap scan"
    elif args.symbols:
        failure_label = "multi-symbol scan"
    else:
        failure_label = analyzer.normalize_symbol(args.symbol)
    try:
        return run(args)
    except Exception as exc:
        if not args.no_email:
            email_failure(failure_label, str(exc))
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
