# Bybit Live API Order Runbook

Use this guide only when `.env` contains **Bybit Live** API credentials.

The same order script is used for demo and live:

```bash
python3 scripts/bybit_demo_open_ethusdt.py
```

The script is symbol-agnostic and supports any Bybit V5 linear perpetual symbol that your account can trade.

Use Bybit symbol format without a slash:

```text
BTC/USDT -> BTCUSDT
ETH/USDT -> ETHUSDT
SOL/USDT -> SOLUSDT
DOGE/USDT -> DOGEUSDT
```

## Live `.env`

For live trading, replace the demo `.env` values with live values.

Use the live endpoint:

```bash
BYBIT_BASE_URL=https://api.bybit.com
BYBIT_API_KEY=your_live_api_key
BYBIT_API_SECRET=your_live_api_secret
```

Do not use demo keys with the live endpoint.

Do not use live keys with the demo endpoint.

Do not commit `.env`.

## Live Safety Checklist

Before any live `--execute` command:

1. Confirm `BYBIT_BASE_URL=https://api.bybit.com`.
2. Confirm the API key is a live Bybit key.
3. Confirm the symbol is correct and has no slash.
4. Confirm the side is correct: `Buy` or `Sell`.
5. Confirm margin and leverage are intentional.
6. Run a dry-run first.
7. Check quantity, stop loss, and take profit.
8. Only then add `--execute`.

Live orders use real funds. High leverage can liquidate quickly.

## What The Script Does

The script:

1. Reads `.env`.
2. Uses `BYBIT_BASE_URL` to select live or demo.
3. Fetches current ticker price.
4. Fetches instrument filters for the symbol.
5. Calculates position size from margin and leverage.
6. Rounds quantity and TP/SL prices to valid increments.
7. Sets cross margin mode unless skipped.
8. Sets leverage unless skipped.
9. Places a market order with attached take-profit and stop-loss when `--execute` is passed.

Without `--execute`, no order is placed.

## Required Live Workflow

1. Confirm `.env` key names without printing secret values.

```bash
awk -F= '/^[A-Za-z_][A-Za-z0-9_]*=/ {print $1 "=<set>"}' .env
```

Expected:

```text
BYBIT_BASE_URL=<set>
BYBIT_API_KEY=<set>
BYBIT_API_SECRET=<set>
```

2. Confirm live endpoint manually in `.env`.

```text
BYBIT_BASE_URL=https://api.bybit.com
```

3. Run a dry-run.

```bash
python3 scripts/bybit_demo_open_ethusdt.py --symbol SYMBOL --side Buy --margin 200 --leverage 50 --tp-sl-mode structure --structure-interval 15
```

4. Review the printed plan.

Important fields:

```text
symbol
side
margin_usdt
leverage
notional_usdt
entry_reference
qty
stop_loss
take_profit
target_source
```

5. Confirm TP/SL direction.

For `Buy`:

```text
stop_loss < entry_reference < take_profit
```

For `Sell`:

```text
take_profit < entry_reference < stop_loss
```

6. Execute.

```bash
python3 scripts/bybit_demo_open_ethusdt.py --symbol SYMBOL --side Buy --margin 200 --leverage 50 --tp-sl-mode structure --structure-interval 15 --execute
```

7. Save the returned `orderId`.

Successful response format:

```json
{
  "retCode": 0,
  "retMsg": "OK",
  "result": {
    "orderId": "example-order-id",
    "orderLinkId": ""
  }
}
```

## Generic Live Buy Command

Use this for a long with stop loss at local low and take profit at local high.

Dry-run:

```bash
python3 scripts/bybit_demo_open_ethusdt.py --symbol SYMBOL --side Buy --margin 200 --leverage 50 --tp-sl-mode structure --structure-interval 15
```

Execute:

```bash
python3 scripts/bybit_demo_open_ethusdt.py --symbol SYMBOL --side Buy --margin 200 --leverage 50 --tp-sl-mode structure --structure-interval 15 --execute
```

If leverage is already set:

```bash
python3 scripts/bybit_demo_open_ethusdt.py --symbol SYMBOL --side Buy --margin 200 --leverage 50 --tp-sl-mode structure --structure-interval 15 --skip-leverage --execute
```

## Generic Live Sell Command

Use this for a short with stop loss at local high and take profit at local low.

Dry-run:

```bash
python3 scripts/bybit_demo_open_ethusdt.py --symbol SYMBOL --side Sell --margin 200 --leverage 50 --tp-sl-mode structure --structure-interval 15
```

Execute:

```bash
python3 scripts/bybit_demo_open_ethusdt.py --symbol SYMBOL --side Sell --margin 200 --leverage 50 --tp-sl-mode structure --structure-interval 15 --execute
```

If leverage is already set:

```bash
python3 scripts/bybit_demo_open_ethusdt.py --symbol SYMBOL --side Sell --margin 200 --leverage 50 --tp-sl-mode structure --structure-interval 15 --skip-leverage --execute
```

## Local High / Local Low Mode

Use:

```bash
--tp-sl-mode structure --structure-interval 15
```

The script uses recent closed candles to derive local structure.

For `Buy`:

```text
Stop loss = recent swing low below entry
Take profit = recent swing high above entry
```

For `Sell`:

```text
Stop loss = recent swing high above entry
Take profit = recent swing low below entry
```

The script stops before order placement if the derived levels are invalid.

## Fixed PnL Mode

Use:

```bash
--tp-sl-mode pnl --stop-loss-pnl-pct 50 --take-profit-pnl-pct 150
```

Example dry-run:

```bash
python3 scripts/bybit_demo_open_ethusdt.py --symbol SYMBOL --side Buy --margin 200 --leverage 50 --tp-sl-mode pnl --stop-loss-pnl-pct 50 --take-profit-pnl-pct 150
```

At `50x` leverage:

```text
-50% PnL ~= 1% adverse price move
+150% PnL ~= 3% favorable price move
```

## Optional Flags

### `--symbol`

Bybit linear perpetual symbol, uppercase and without slash.

```bash
--symbol SYMBOL
```

### `--side`

Allowed values:

```text
Buy
Sell
```

### `--margin`

Margin amount in USDT.

```bash
--margin 200
```

### `--leverage`

Requested leverage.

```bash
--leverage 50
```

### `--structure-interval`

Timeframe used for local highs/lows.

```bash
--structure-interval 15
--structure-interval 60
--structure-interval 240
```

### `--skip-leverage`

Use when Bybit returns:

```text
retCode: 110043
retMsg: leverage not modified
```

### `--skip-margin-mode`

Use only if the account is already in the intended margin mode.

## Read-Only Market Analyzer

Run this before live placement if you need a quick market read:

```bash
python3 scripts/bybit_analyze_symbol.py --symbol SYMBOL
```

It does not place orders.

## Live Troubleshooting

### Missing Credentials

```text
Set BYBIT_DEMO_API_KEY/BYBIT_DEMO_API_SECRET or BYBIT_API_KEY/BYBIT_API_SECRET in .env before --execute.
```

Fix: set `BYBIT_API_KEY` and `BYBIT_API_SECRET` to live credentials.

### Wrong Endpoint

If live orders are expected but output says:

```text
Bybit demo SYMBOL plan
```

Then `.env` is still using:

```text
BYBIT_BASE_URL=https://api-demo.bybit.com
```

Change it to:

```text
BYBIT_BASE_URL=https://api.bybit.com
```

### `110043 leverage not modified`

Meaning: leverage is already set to the requested value.

Fix:

```bash
--skip-leverage
```

### Invalid Structure

Meaning: the local high/local low did not produce valid levels for the selected side.

Fix options:

1. Wait for cleaner structure.
2. Try `--structure-interval 60`.
3. Use `--tp-sl-mode pnl`.

### API Access Or Region Error

Bybit API requests can fail because of API permissions, IP restrictions, endpoint mismatch, or regional restrictions.

Check:

1. API key has trade permission.
2. API key is for the same environment as `BYBIT_BASE_URL`.
3. Account has enough USDT balance.
4. Symbol is tradeable in your account.
5. IP restrictions allow this machine.

## Official Bybit References

- V5 integration guide: `https://bybit-exchange.github.io/docs/v5/guide`
- Demo trading service: `https://bybit-exchange.github.io/docs/v5/demo`
- Place order: `https://bybit-exchange.github.io/docs/v5/order/create-order`
- Set leverage: `https://bybit-exchange.github.io/docs/v5/position/leverage`

## Live Notes

- Live orders use real funds.
- Market orders can fill away from `entry_reference`.
- Cross margin can use more account equity than the visible margin estimate.
- High leverage has narrow error tolerance.
- Always dry-run first.
- Keep a record of `orderId` for every live execution.
