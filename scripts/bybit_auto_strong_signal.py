#!/usr/bin/env python3
"""
Daily strong-signal automation for Bybit linear perpetuals.

The automation is intentionally narrow:
- analyze a symbol with the local read-only signal logic
- continue only when confidence is strong
- use the analyzer recommendation as the order side
- re-enter/add only when an existing position is the same side
- skip opposite-side existing positions unless explicitly allowed
- dry-run unless --execute is passed
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import bybit_analyze_symbol as analyzer
import bybit_demo_open_ethusdt as order


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


def order_link_id(prefix: str, symbol: str, ny_time: str | None) -> str:
    now = datetime.now(ZoneInfo("America/New_York"))
    safe_time = re.sub(r"[^0-9]", "", ny_time or "manual") or "manual"
    raw = f"{prefix}-{symbol}-{now:%Y%m%d}-{safe_time}"
    safe = re.sub(r"[^A-Za-z0-9_-]", "-", raw)
    if len(safe) <= 36:
        return safe
    digest = hashlib.sha1(safe.encode("utf-8")).hexdigest()[:8]
    return f"{safe[:27]}-{digest}"


def run_signal(base_url: str, symbol: str) -> dict[str, object]:
    ticker = analyzer.get_ticker(base_url, symbol)
    last_price = Decimal(ticker["lastPrice"])

    results: dict[str, dict[str, Decimal | int]] = {}
    total_score = 0
    for interval in ["15", "60", "240"]:
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

    candles_15m = analyzer.get_closed_candles(base_url, symbol, "15")
    local_high, local_low = analyzer.local_levels(candles_15m)
    recommendation = "Buy" if total_score > 0 else "Sell"
    confidence = "strong" if abs(total_score) >= 6 else "moderate" if abs(total_score) >= 3 else "low"

    return {
        "market_source": base_url,
        "symbol": symbol,
        "last_price": last_price,
        "24h_change_pct": ticker.get("price24hPcnt"),
        "15m_local_high": local_high,
        "15m_local_low": local_low,
        "total_score": total_score,
        "recommendation": recommendation,
        "confidence": confidence,
        "timeframes": results,
    }


def binance_interval(bybit_interval: str) -> str:
    return {
        "15": "15m",
        "60": "1h",
        "240": "4h",
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
    for interval in ["15", "60", "240"]:
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

    candles_15m = binance_closed_candles(base_url, symbol, "15")
    local_high, local_low = analyzer.local_levels(candles_15m)
    recommendation = "Buy" if total_score > 0 else "Sell"
    confidence = "strong" if abs(total_score) >= 6 else "moderate" if abs(total_score) >= 3 else "low"

    return {
        "market_source": base_url,
        "symbol": symbol,
        "last_price": last_price,
        "24h_change_pct": ticker.get("priceChangePercent"),
        "15m_local_high": local_high,
        "15m_local_low": local_low,
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


def print_signal(signal: dict[str, object]) -> None:
    print(f"market_source: {signal.get('market_source', 'unknown')}")
    print(f"symbol: {signal['symbol']}")
    print(f"last_price: {signal['last_price']}")
    print(f"24h_change_pct: {signal['24h_change_pct']}")
    print(f"15m_local_high: {signal['15m_local_high']}")
    print(f"15m_local_low: {signal['15m_local_low']}")
    print(f"total_score: {signal['total_score']}")
    print(f"recommendation: {signal['recommendation']}")
    print(f"confidence: {signal['confidence']}")
    timeframes = signal["timeframes"]
    assert isinstance(timeframes, dict)
    for interval, data in timeframes.items():
        assert isinstance(data, dict)
        print(
            f"{interval}m: score={data['score']} close={data['last_close']} "
            f"ema21={data['ema21']:.8f} ema55={data['ema55']:.8f} rsi14={data['rsi14']:.2f}"
        )


def get_position(base_url: str, symbol: str, api_key: str, api_secret: str) -> dict[str, object]:
    response = order.signed_request(
        base_url,
        "GET",
        "/v5/position/list",
        api_key,
        api_secret,
        {"category": "linear", "symbol": symbol},
    )
    order.require_ok(response, "Get current position")
    rows = response["result"]["list"]
    active_rows = [row for row in rows if Decimal(row.get("size", "0")) > 0]
    if not active_rows:
        return {"has_position": False, "side": None, "size": Decimal("0")}

    row = active_rows[0]
    return {
        "has_position": True,
        "side": row.get("side"),
        "size": Decimal(row.get("size", "0")),
        "entry_price": Decimal(row.get("avgPrice") or "0"),
    }


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


def append_log(
    path: str,
    signal: dict[str, object],
    plan: dict[str, Decimal | str] | None,
    user_action: str,
    reason: str,
    result: dict[str, object] | None,
) -> None:
    now = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S %Z")
    timeframes = signal["timeframes"]
    assert isinstance(timeframes, dict)
    rr = reward_risk(plan) if plan else None
    side = plan["side"] if plan else signal["recommendation"]

    lines = [
        "",
        f"## {now} - {signal['symbol']} automation",
        "",
        f"- date_time: {now}",
        f"- symbol: {signal['symbol']}",
        f"- analyzer_recommendation: {signal['recommendation']}",
        f"- confidence: {signal['confidence']}",
        f"- 15m_score: {timeframes['15']['score']}",
        f"- 60m_score: {timeframes['60']['score']}",
        f"- 240m_score: {timeframes['240']['score']}",
        f"- side_considered: {side}",
        f"- entry_reference: {decimal_text(plan['entry_reference']) if plan else 'N/A'}",
        f"- stop_loss: {decimal_text(plan['stop_loss']) if plan else 'N/A'}",
        f"- take_profit: {decimal_text(plan['take_profit']) if plan else 'N/A'}",
        f"- reward_risk: {rr.quantize(Decimal('0.01')) if rr is not None else 'N/A'}",
        f"- margin_usdt: {decimal_text(plan['margin_usdt']) if plan else 'N/A'}",
        f"- leverage: {decimal_text(plan['leverage']) if plan else 'N/A'}",
        f"- qty: {decimal_text(plan['qty']) if plan else 'N/A'}",
        f"- user_action: {user_action}",
        f"- signal_comment: Automated daily New York time check. Only confidence=strong is eligible.",
        f"- reason: {reason}",
        "- result_r_multiple: pending" if user_action.startswith("executed") else "- result_r_multiple: N/A",
    ]
    if result:
        order_id = result.get("result", {}).get("orderId") if isinstance(result.get("result"), dict) else None
        if order_id:
            lines.append(f"- bybit_order_id: {order_id}")
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def create_order(
    base_url: str,
    api_key: str,
    api_secret: str,
    plan: dict[str, Decimal | str],
    skip_margin_mode: bool,
    skip_leverage: bool,
    order_link_id_value: str,
) -> dict[str, object]:
    order_payload = {
        "category": "linear",
        "symbol": str(plan["symbol"]),
        "side": str(plan["side"]),
        "orderType": "Market",
        "qty": order.decimal_str(Decimal(str(plan["qty"]))),
        "orderLinkId": order_link_id_value,
        "positionIdx": 0,
        "takeProfit": order.decimal_str(Decimal(str(plan["take_profit"]))),
        "stopLoss": order.decimal_str(Decimal(str(plan["stop_loss"]))),
        "tpTriggerBy": "MarkPrice",
        "slTriggerBy": "MarkPrice",
    }

    if not skip_margin_mode:
        response = order.signed_request(
            base_url,
            "POST",
            "/v5/account/set-margin-mode",
            api_key,
            api_secret,
            {"setMarginMode": "REGULAR_MARGIN"},
        )
        order.require_ok(response, "Set cross margin mode")
        print("Set cross margin mode: OK")

    if not skip_leverage:
        leverage_value = order.decimal_str(Decimal(str(plan["leverage"])))
        response = order.signed_request(
            base_url,
            "POST",
            "/v5/position/set-leverage",
            api_key,
            api_secret,
            {
                "category": "linear",
                "symbol": str(plan["symbol"]),
                "buyLeverage": leverage_value,
                "sellLeverage": leverage_value,
            },
        )
        order.require_ok(response, "Set leverage")
        print("Set leverage: OK")

    response = order.signed_request(
        base_url,
        "POST",
        "/v5/order/create",
        api_key,
        api_secret,
        order_payload,
    )
    order.require_ok(response, "Create market order")
    return response


def build_fallback_plan(
    signal: dict[str, object],
    side: str,
    margin: Decimal,
    leverage: Decimal,
) -> dict[str, Decimal | str]:
    entry = Decimal(str(signal["last_price"]))
    local_high = Decimal(str(signal["15m_local_high"]))
    local_low = Decimal(str(signal["15m_local_low"]))
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a strong-signal Bybit automation check.")
    parser.add_argument("--execute", action="store_true", help="Place the eligible order.")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--margin", type=Decimal, default=Decimal("25"))
    parser.add_argument("--leverage", type=Decimal, default=Decimal("5"))
    parser.add_argument("--tp-sl-mode", choices=["pnl", "structure"], default="structure")
    parser.add_argument("--structure-interval", default="60")
    parser.add_argument("--stop-loss-pnl-pct", type=Decimal, default=Decimal("50"))
    parser.add_argument("--take-profit-pnl-pct", type=Decimal, default=Decimal("150"))
    parser.add_argument("--ny-time", help="Only run inside this America/New_York HH:MM time window.")
    parser.add_argument("--ny-window-minutes", type=int, default=45)
    parser.add_argument("--allow-opposite-position-reentry", action="store_true")
    parser.add_argument("--skip-margin-mode", action="store_true")
    parser.add_argument("--skip-leverage", action="store_true")
    parser.add_argument("--order-link-prefix", default="auto")
    parser.add_argument("--log-file", default="SIGNAL-LOG.md")
    parser.add_argument("--no-log", action="store_true")
    args = parser.parse_args()

    order.load_dotenv()
    trade_base_url = validate_base_url(os.getenv("BYBIT_BASE_URL") or DEFAULT_BASE_URL)
    market_base_url = resolve_market_base_url(trade_base_url)
    api_key = os.getenv("BYBIT_DEMO_API_KEY") or os.getenv("BYBIT_API_KEY", "")
    api_secret = os.getenv("BYBIT_DEMO_API_SECRET") or os.getenv("BYBIT_API_SECRET", "")
    symbol = analyzer.normalize_symbol(args.symbol)
    print(f"trade_base_url: {trade_base_url}")
    print(f"market_base_url: {market_base_url}")

    if args.ny_time:
        allowed, ny_now = ny_time_allowed(args.ny_time, args.ny_window_minutes)
        print(f"New York time: {ny_now}")
        if not allowed:
            print(f"Outside --ny-time {args.ny_time} +/- {args.ny_window_minutes} minutes. No action.")
            return 0

    signal = run_signal_with_fallback(market_base_url, symbol)
    print_signal(signal)

    if signal["confidence"] != "strong":
        reason = f"confidence is {signal['confidence']}; required strong"
        print(f"No order plan created: {reason}.")
        if not args.no_log:
            append_log(args.log_file, signal, None, "signal", reason, None)
        return 0

    side = str(signal["recommendation"])
    if args.execute:
        if not api_key or not api_secret:
            raise RuntimeError("Execution requires Bybit API credentials in .env or environment variables.")

        position = get_position(trade_base_url, symbol, api_key, api_secret)
        print(f"current_position: {position}")
        if position["has_position"] and position["side"] != side and not args.allow_opposite_position_reentry:
            reason = f"existing {position['side']} position conflicts with strong {side} signal"
            print(f"No order plan created: {reason}.")
            if not args.no_log:
                append_log(args.log_file, signal, None, "signal", reason, None)
            return 0
    else:
        print("current_position: skipped for dry-run; signed Bybit credentials are not used unless --execute is set")

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
        plan = order.build_plan(plan_args, market_base_url)
    except Exception as exc:
        if args.execute:
            raise
        print(f"plan_fallback: Bybit public planning data failed; using signal local levels for dry-run only: {exc}")
        plan = build_fallback_plan(signal, side, args.margin, args.leverage)
    order_link_id_value = order_link_id(args.order_link_prefix, symbol, args.ny_time)
    print(f"Bybit {order.environment_label(trade_base_url)} {plan['symbol']} automation plan")
    for key, value in plan.items():
        print(f"{key}: {value}")
    print(f"order_link_id: {order_link_id_value}")
    rr = reward_risk(plan)
    print(f"reward_risk: {rr.quantize(Decimal('0.01')) if rr is not None else 'invalid'}")

    if not args.execute:
        reason = "strong signal dry-run; add --execute to place the eligible order"
        print(reason)
        if not args.no_log:
            append_log(args.log_file, signal, plan, "dry-run", reason, None)
        return 0

    response = create_order(
        trade_base_url,
        api_key,
        api_secret,
        plan,
        args.skip_margin_mode,
        args.skip_leverage,
        order_link_id_value,
    )
    print("Create market order: OK")
    print(json.dumps(response, indent=2))
    if not args.no_log:
        append_log(args.log_file, signal, plan, f"executed {order.environment_label(trade_base_url)}", "strong signal automation executed", response)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
