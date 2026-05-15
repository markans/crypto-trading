# Trader.dev Bybit API Runbooks

Use these runbooks for placing Bybit linear perpetual orders through the local Python scripts.

The order script is:

```bash
python3 scripts/bybit_demo_open_ethusdt.py
```

Despite the filename, the script is symbol-agnostic. It supports any Bybit V5 linear perpetual symbol your account can trade, such as `BTC/USDT`, `ETH/USDT`, `SOL/USDT`, or `DOGE/USDT`.

Symbols can be entered with or without a slash. The scripts normalize them before calling Bybit:

```text
BTC/USDT -> BTCUSDT
ETH/USDT -> ETHUSDT
SOL/USDT -> SOLUSDT
```

## Choose The Correct Runbook

For the current demo setup:

[README-DEMO.md](README-DEMO.md)

For live API placement after replacing `.env` with live credentials:

[README-LIVE.md](README-LIVE.md)

For GitHub Actions cloud automation:

[README-CLOUD.md](README-CLOUD.md)

## Important

- `.env` controls whether the script uses demo or live.
- Demo endpoint: `https://api-demo.bybit.com`
- Live endpoint: `https://api.bybit.com`
- The script performs a dry-run unless `--execute` is passed.
- Always dry-run first and inspect `symbol`, `side`, `qty`, `stop_loss`, and `take_profit`.

## Daily Strong-Signal Automation

The daily automation script is:

```bash
python3 scripts/bybit_auto_strong_signal.py
```

It runs the local signal analyzer first and continues only when:

```text
confidence: strong
```

When eligible, it uses the analyzer recommendation as the order side. If there is
already a same-side position, it re-enters/adds another order. If there is an
opposite-side position, it skips by default to avoid accidentally reducing or
flipping a one-way position.

Dry-run:

```bash
python3 scripts/bybit_auto_strong_signal.py --symbol BTC/USDT --margin 25 --leverage 5 --tp-sl-mode structure --structure-interval 60
```

Execute:

```bash
python3 scripts/bybit_auto_strong_signal.py --symbol BTC/USDT --margin 25 --leverage 5 --tp-sl-mode structure --structure-interval 60 --execute
```

Run only near 9:30 AM New York time:

```bash
python3 scripts/bybit_auto_strong_signal.py --symbol BTC/USDT --margin 25 --leverage 5 --tp-sl-mode structure --structure-interval 60 --ny-time 09:30 --ny-window-minutes 45 --execute
```

The GitHub Actions workflow at
`.github/workflows/bybit-daily-strong-signal.yml` schedules this every day for
9:30 AM America/New_York. GitHub cron uses UTC, so the workflow schedules both
EST and EDT equivalents and the script skips whichever run is outside the New
York time window. Each workflow run uploads `SIGNAL-LOG.md` as an artifact.
