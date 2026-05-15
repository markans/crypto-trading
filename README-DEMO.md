# Bybit Demo API Order Runbook

Use this guide when `.env` contains **Bybit Demo Trading** API credentials.

The order script is symbol-agnostic:

```bash
python3 scripts/bybit_demo_open_ethusdt.py
```

Despite the filename, it works for any Bybit V5 linear perpetual symbol, such as `BTCUSDT`, `ETHUSDT`, `DOGEUSDT`, `SOLUSDT`, or any other supported `*USDT` linear contract.

Use Bybit symbol format without a slash:

```text
BTC/USDT -> BTCUSDT
ETH/USDT -> ETHUSDT
DOGE/USDT -> DOGEUSDT
```

## Demo `.env`

Your current `.env` is intended for demo use.

Use the demo endpoint:

```bash
BYBIT_BASE_URL=https://api-demo.bybit.com
BYBIT_API_KEY=your_demo_api_key
BYBIT_API_SECRET=your_demo_api_secret
```

The script also accepts demo-specific variable names:

```bash
BYBIT_BASE_URL=https://api-demo.bybit.com
BYBIT_DEMO_API_KEY=your_demo_api_key
BYBIT_DEMO_API_SECRET=your_demo_api_secret
```

Do not commit `.env`.

## What The Script Does

The script:

1. Reads `.env`.
2. Uses `BYBIT_BASE_URL` to decide which Bybit API endpoint to call.
3. Fetches ticker price for the requested symbol.
4. Fetches symbol filters such as quantity step, minimum order quantity, and tick size.
5. Calculates notional size from margin and leverage.
6. Rounds quantity and prices to valid Bybit increments.
7. Optionally sets cross margin mode.
8. Optionally sets leverage.
9. Places a market order with attached stop loss and take profit when `--execute` is present.

Without `--execute`, it only prints a dry-run order plan.

## Required Command Pattern

Always dry-run first:

```bash
python3 scripts/bybit_demo_open_ethusdt.py --symbol SYMBOL --side Buy --margin 200 --leverage 50 --tp-sl-mode structure --structure-interval 60
```

Then execute only after the dry-run plan is correct:

```bash
python3 scripts/bybit_demo_open_ethusdt.py --symbol SYMBOL --side Buy --margin 200 --leverage 50 --tp-sl-mode structure --structure-interval 60 --execute
```

Replace:

```text
SYMBOL -> Bybit linear symbol, for example SOLUSDT
Buy    -> Buy or Sell
200    -> margin in USDT
50     -> leverage
60     -> structure timeframe in minutes (1 hour)
```

## Generic Buy Example

Request:

```text
Symbol: any supported Bybit linear symbol
Side: Buy
Margin mode: Cross
Margin: 200 USDT
Leverage: 50x
Order type: Market
Stop loss: local low
Take profit: local high
```

Dry-run:

```bash
python3 scripts/bybit_demo_open_ethusdt.py --symbol SYMBOL --side Buy --margin 200 --leverage 50 --tp-sl-mode structure --structure-interval 60
```

Execute:

```bash
python3 scripts/bybit_demo_open_ethusdt.py --symbol SYMBOL --side Buy --margin 200 --leverage 50 --tp-sl-mode structure --structure-interval 60 --execute
```

For a `Buy`, the script requires:

```text
stop_loss < entry_reference < take_profit
```

## Generic Sell Example

Request:

```text
Symbol: any supported Bybit linear symbol
Side: Sell
Margin mode: Cross
Margin: 200 USDT
Leverage: 50x
Order type: Market
Stop loss: local high
Take profit: local low
```

Dry-run:

```bash
python3 scripts/bybit_demo_open_ethusdt.py --symbol SYMBOL --side Sell --margin 200 --leverage 50 --tp-sl-mode structure --structure-interval 60
```

Execute:

```bash
python3 scripts/bybit_demo_open_ethusdt.py --symbol SYMBOL --side Sell --margin 200 --leverage 50 --tp-sl-mode structure --structure-interval 60 --execute
```

For a `Sell`, the script requires:

```text
take_profit < entry_reference < stop_loss
```

## Local High / Local Low Mode

Use:

```bash
--tp-sl-mode structure --structure-interval 60
```

The script fetches recent closed candles and derives pivot levels.

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

If structure is invalid, the script stops before placing the order.

## Fixed PnL Mode

Use this when you want stop loss and take profit based on leveraged PnL percentages:

```bash
python3 scripts/bybit_demo_open_ethusdt.py --symbol SYMBOL --side Buy --margin 200 --leverage 50 --tp-sl-mode pnl --stop-loss-pnl-pct 50 --take-profit-pnl-pct 150
```

At `50x` leverage:

```text
-50% PnL ~= 1% adverse price move
+150% PnL ~= 3% favorable price move
```

## Full Demo Workflow

1. Confirm `.env` points to demo.

```bash
awk -F= '/^[A-Za-z_][A-Za-z0-9_]*=/ {print $1 "=<set>"}' .env
```

Expected keys:

```text
BYBIT_BASE_URL=<set>
BYBIT_API_KEY=<set>
BYBIT_API_SECRET=<set>
```

Or:

```text
BYBIT_BASE_URL=<set>
BYBIT_DEMO_API_KEY=<set>
BYBIT_DEMO_API_SECRET=<set>
```

2. Use `https://api-demo.bybit.com` for demo.

3. Run a dry-run with the exact symbol, side, margin, leverage, and TP/SL mode.

4. Check the printed plan:

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

5. Execute only after the dry-run values look correct.

6. Save the returned `orderId` from the output.

## Common Bybit Demo Errors

### Missing Credentials

```text
Set BYBIT_DEMO_API_KEY/BYBIT_DEMO_API_SECRET or BYBIT_API_KEY/BYBIT_API_SECRET in .env before --execute.
```

Fix: add valid demo credentials to `.env`.

### `110043 leverage not modified`

```text
retCode: 110043
retMsg: leverage not modified
```

Meaning: leverage is already set to the requested value.

Fix: rerun the same command with:

```bash
--skip-leverage
```

Example:

```bash
python3 scripts/bybit_demo_open_ethusdt.py --symbol SYMBOL --side Buy --margin 200 --leverage 50 --tp-sl-mode structure --structure-interval 60 --skip-leverage --execute
```

### Invalid Structure

```text
Invalid long structure
Invalid short structure
```

Meaning: the local high or local low did not produce valid TP/SL levels for the requested side.

Fix options:

1. Wait for cleaner structure.
2. Try a wider timeframe, such as `--structure-interval 240`.
3. Use `--tp-sl-mode pnl`.

## Read-Only Market Analyzer

Use this before deciding direction:

```bash
python3 scripts/bybit_analyze_symbol.py --symbol SYMBOL
```

It prints:

- last price
- 24h change
- recent 15m local high
- recent 15m local low
- 15m, 1h, and 4h EMA/RSI scores
- simple Buy/Sell bias
- confidence level

This analyzer does not place orders.

## Demo Notes

- Demo Trading uses `https://api-demo.bybit.com`.
- Demo API credentials are separate from live API credentials.
- Demo fills and liquidity may differ from live trading.
- Market orders can fill away from `entry_reference`.
- Always dry-run first.
