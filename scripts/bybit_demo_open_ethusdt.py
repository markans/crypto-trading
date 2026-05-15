#!/usr/bin/env python3
"""
Open a Bybit linear perpetual position.

Dry-run is the default. Pass --execute to send signed Bybit requests.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, ROUND_DOWN


DEFAULT_BASE_URL = "https://api-demo.bybit.com"
RECV_WINDOW = "5000"


def normalize_symbol(symbol: str) -> str:
    return symbol.replace("/", "").replace("-", "").upper()


def load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def decimal_down(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        return value
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def decimal_str(value: Decimal) -> str:
    return format(value.normalize(), "f")


def environment_label(base_url: str) -> str:
    if "api-demo.bybit.com" in base_url:
        return "demo"
    if "api.bybit.com" in base_url:
        return "live"
    return base_url


def public_get(base_url: str, path: str, params: dict[str, str]) -> dict:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(f"{base_url}{path}?{query}", method="GET")
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def signed_request(
    base_url: str,
    method: str,
    path: str,
    api_key: str,
    api_secret: str,
    payload: dict[str, str] | None = None,
) -> dict:
    payload = payload or {}
    timestamp = str(int(time.time() * 1000))

    if method == "GET":
        body_or_query = urllib.parse.urlencode(payload)
        url = f"{base_url}{path}?{body_or_query}" if body_or_query else f"{base_url}{path}"
        body_bytes = None
    else:
        body_or_query = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        url = f"{base_url}{path}"
        body_bytes = body_or_query.encode("utf-8")

    sign_payload = f"{timestamp}{api_key}{RECV_WINDOW}{body_or_query}"
    signature = hmac.new(
        api_secret.encode("utf-8"),
        sign_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-BAPI-API-KEY": api_key,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": RECV_WINDOW,
        "X-BAPI-SIGN": signature,
    }

    request = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {path}: {body}") from exc


def require_ok(response: dict, action: str) -> None:
    if response.get("retCode") == 0:
        return
    raise RuntimeError(f"{action} failed: {json.dumps(response, indent=2)}")


def get_last_price(base_url: str, symbol: str) -> Decimal:
    response = public_get(base_url, "/v5/market/tickers", {"category": "linear", "symbol": symbol})
    require_ok(response, "Get ticker")
    return Decimal(response["result"]["list"][0]["lastPrice"])


def get_filters(base_url: str, symbol: str) -> tuple[Decimal, Decimal, Decimal]:
    response = public_get(
        base_url,
        "/v5/market/instruments-info",
        {"category": "linear", "symbol": symbol},
    )
    require_ok(response, "Get instruments info")
    instrument = response["result"]["list"][0]
    lot = instrument["lotSizeFilter"]
    price = instrument["priceFilter"]
    return (
        Decimal(lot["qtyStep"]),
        Decimal(lot["minOrderQty"]),
        Decimal(price["tickSize"]),
    )


def get_closed_klines(base_url: str, symbol: str, interval: str, limit: int = 50) -> list[dict[str, Decimal]]:
    response = public_get(
        base_url,
        "/v5/market/kline",
        {
            "category": "linear",
            "symbol": symbol,
            "interval": interval,
            "limit": str(limit),
        },
    )
    require_ok(response, "Get klines")
    rows = sorted(response["result"]["list"], key=lambda row: int(row[0]))
    closed_rows = rows[:-1]
    return [
        {
            "start": Decimal(row[0]),
            "open": Decimal(row[1]),
            "high": Decimal(row[2]),
            "low": Decimal(row[3]),
            "close": Decimal(row[4]),
        }
        for row in closed_rows
    ]


def structure_targets(
    base_url: str,
    symbol: str,
    side: str,
    entry: Decimal,
    tick_size: Decimal,
    interval: str,
) -> tuple[Decimal, Decimal, str]:
    candles = get_closed_klines(base_url, symbol, interval)
    if len(candles) < 7:
        raise RuntimeError(f"Not enough {interval}m candles to derive structure targets")

    pivot_highs: list[Decimal] = []
    pivot_lows: list[Decimal] = []
    for index in range(2, len(candles) - 2):
        current = candles[index]
        left = candles[index - 2 : index]
        right = candles[index + 1 : index + 3]
        if all(current["high"] > candle["high"] for candle in left + right):
            pivot_highs.append(current["high"])
        if all(current["low"] < candle["low"] for candle in left + right):
            pivot_lows.append(current["low"])

    if side == "Sell":
        stop_candidates = [price for price in reversed(pivot_highs) if price > entry]
        target_candidates = [price for price in reversed(pivot_lows) if price < entry]
        stop_loss = stop_candidates[0] if stop_candidates else max(candle["high"] for candle in candles[-20:])
        take_profit = target_candidates[0] if target_candidates else min(candle["low"] for candle in candles[-20:])
        stop_loss = decimal_down(stop_loss, tick_size)
        take_profit = decimal_down(take_profit, tick_size)
        if stop_loss <= entry or take_profit >= entry:
            raise RuntimeError(
                f"Invalid short structure: entry={entry}, stop_loss={stop_loss}, take_profit={take_profit}"
            )
        return stop_loss, take_profit, f"{interval}m swing high SL / swing low TP"

    stop_candidates = [price for price in reversed(pivot_lows) if price < entry]
    target_candidates = [price for price in reversed(pivot_highs) if price > entry]
    stop_loss = stop_candidates[0] if stop_candidates else min(candle["low"] for candle in candles[-20:])
    take_profit = target_candidates[0] if target_candidates else max(candle["high"] for candle in candles[-20:])
    stop_loss = decimal_down(stop_loss, tick_size)
    take_profit = decimal_down(take_profit, tick_size)
    if stop_loss >= entry or take_profit <= entry:
        raise RuntimeError(
            f"Invalid long structure: entry={entry}, stop_loss={stop_loss}, take_profit={take_profit}"
        )
    return stop_loss, take_profit, f"{interval}m swing low SL / swing high TP"


def build_plan(args: argparse.Namespace, base_url: str) -> dict[str, Decimal | str]:
    symbol = normalize_symbol(args.symbol)
    entry = Decimal(args.entry_price) if args.entry_price else get_last_price(base_url, symbol)
    qty_step, min_qty, tick_size = get_filters(base_url, symbol)

    leverage = Decimal(str(args.leverage))
    margin = Decimal(str(args.margin))
    notional = margin * leverage
    qty = decimal_down(notional / entry, qty_step)
    if qty < min_qty:
        raise RuntimeError(f"Calculated qty {qty} is below minimum order qty {min_qty}")

    if args.tp_sl_mode == "structure":
        stop_loss, take_profit, target_source = structure_targets(
            base_url,
            symbol,
            args.side,
            entry,
            tick_size,
            args.structure_interval,
        )
    else:
        sl_move = Decimal(str(args.stop_loss_pnl_pct)) / Decimal("100") / leverage
        tp_move = Decimal(str(args.take_profit_pnl_pct)) / Decimal("100") / leverage

        if args.side == "Buy":
            stop_loss = decimal_down(entry * (Decimal("1") - sl_move), tick_size)
            take_profit = decimal_down(entry * (Decimal("1") + tp_move), tick_size)
        else:
            stop_loss = decimal_down(entry * (Decimal("1") + sl_move), tick_size)
            take_profit = decimal_down(entry * (Decimal("1") - tp_move), tick_size)
        target_source = "PnL percentage"

    return {
        "symbol": symbol,
        "side": args.side,
        "margin_mode": "REGULAR_MARGIN (Cross)",
        "margin_usdt": margin,
        "leverage": leverage,
        "notional_usdt": notional,
        "entry_reference": entry,
        "qty": qty,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "target_source": target_source,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Open a Bybit linear perpetual position.")
    parser.add_argument("--execute", action="store_true", help="Send the order to the configured Bybit endpoint.")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--side", choices=["Buy", "Sell"], default="Buy")
    parser.add_argument("--margin", type=Decimal, default=Decimal("100"))
    parser.add_argument("--leverage", type=Decimal, default=Decimal("50"))
    parser.add_argument("--stop-loss-pnl-pct", type=Decimal, default=Decimal("50"))
    parser.add_argument("--take-profit-pnl-pct", type=Decimal, default=Decimal("150"))
    parser.add_argument("--tp-sl-mode", choices=["pnl", "structure"], default="pnl")
    parser.add_argument("--structure-interval", default="15")
    parser.add_argument("--entry-price", help="Optional reference price; otherwise fetched from Bybit.")
    parser.add_argument("--skip-margin-mode", action="store_true")
    parser.add_argument("--skip-leverage", action="store_true")
    args = parser.parse_args()

    load_dotenv()

    base_url = os.getenv("BYBIT_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    api_key = os.getenv("BYBIT_DEMO_API_KEY") or os.getenv("BYBIT_API_KEY", "")
    api_secret = os.getenv("BYBIT_DEMO_API_SECRET") or os.getenv("BYBIT_API_SECRET", "")

    plan = build_plan(args, base_url)
    order_payload = {
        "category": "linear",
        "symbol": str(plan["symbol"]),
        "side": str(plan["side"]),
        "orderType": "Market",
        "qty": decimal_str(plan["qty"]),
        "positionIdx": 0,
        "takeProfit": decimal_str(plan["take_profit"]),
        "stopLoss": decimal_str(plan["stop_loss"]),
        "tpTriggerBy": "MarkPrice",
        "slTriggerBy": "MarkPrice",
    }

    print(f"Bybit {environment_label(base_url)} {plan['symbol']} plan")
    for key, value in plan.items():
        print(f"{key}: {value}")
    print("order_payload:")
    print(json.dumps(order_payload, indent=2))

    if not args.execute:
        print(f"\nDry run only. Add --execute to place this on Bybit {environment_label(base_url)}.")
        return 0

    if not api_key or not api_secret:
        raise RuntimeError(
            "Set BYBIT_DEMO_API_KEY/BYBIT_DEMO_API_SECRET or "
            "BYBIT_API_KEY/BYBIT_API_SECRET in .env before --execute."
        )

    if not args.skip_margin_mode:
        margin_response = signed_request(
            base_url,
            "POST",
            "/v5/account/set-margin-mode",
            api_key,
            api_secret,
            {"setMarginMode": "REGULAR_MARGIN"},
        )
        require_ok(margin_response, "Set cross margin mode")
        print("Set cross margin mode: OK")

    if not args.skip_leverage:
        leverage_value = decimal_str(plan["leverage"])
        leverage_response = signed_request(
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
        require_ok(leverage_response, "Set leverage")
        print("Set leverage: OK")

    order_response = signed_request(
        base_url,
        "POST",
        "/v5/order/create",
        api_key,
        api_secret,
        order_payload,
    )
    require_ok(order_response, "Create market order")
    print("Create market order: OK")
    print(json.dumps(order_response, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
