# Cloud Automation

This repo is ready to run the daily strong-signal bot on GitHub Actions.

The workflow is:

```text
.github/workflows/bybit-daily-strong-signal.yml
```

## What It Does

Every day near `09:30 America/New_York`, the workflow runs:

```bash
python3 scripts/bybit_auto_strong_signal.py --symbol BTC/USDT --margin 25 --leverage 5 --tp-sl-mode structure --structure-interval 60 --ny-time 09:30 --ny-window-minutes 45 --execute
```

The script:

- checks the BTC/USDT signal
- continues only when `confidence: strong`
- uses the analyzer recommendation as the order side
- adds/re-enters if the current position is the same side
- skips if an opposite-side position already exists
- sends a deterministic `orderLinkId` per symbol/New York date/time to reduce duplicate scheduled order risk
- uploads `SIGNAL-LOG.md` as a workflow artifact

## Required GitHub Secrets

Set these in the GitHub repository:

```text
BYBIT_BASE_URL
BYBIT_API_KEY
BYBIT_API_SECRET
```

Optional:

```text
BYBIT_MARKET_BASE_URL
```

When `BYBIT_BASE_URL` is demo, public market data defaults to
`https://api.bybit.com` because GitHub-hosted runners may receive `403
Forbidden` from the demo public market-data endpoint. Orders still use
`BYBIT_BASE_URL`. If Bybit public market data is also blocked, dry-run signal
checks fall back to Binance/Binance.US public market data. Execution still uses
Bybit only.

For demo:

```text
BYBIT_BASE_URL=https://api-demo.bybit.com
```

For live:

```text
BYBIT_BASE_URL=https://api.bybit.com
```

Use demo first. Live credentials place real orders when the scheduled workflow
finds a strong signal.

## Publish To GitHub

This folder is not currently a Git repository. To enable cloud automation:

```bash
git init
git add .
git commit -m "Add Bybit daily strong-signal cloud automation"
git branch -M main
git remote add origin git@github.com:YOUR_USER/YOUR_REPO.git
git push -u origin main
```

Then open the GitHub repository:

1. Go to Settings -> Secrets and variables -> Actions.
2. Add `BYBIT_BASE_URL`, `BYBIT_API_KEY`, and `BYBIT_API_SECRET`.
3. Go to Actions -> Bybit Daily Strong Signal.
4. Run manually once with `execute=false`.
5. Inspect the workflow logs and `signal-log` artifact.
6. Use scheduled execution only after the dry-run behavior is correct.

Scheduled runs execute eligible strong signals. Keep `BYBIT_BASE_URL` pointed at
`https://api-demo.bybit.com` until demo logs prove the behavior is acceptable.

## Manual Cloud Run

The workflow supports manual inputs:

- `symbol`, default `BTC/USDT`
- `margin`, default `25`
- `leverage`, default `5`
- `ny_time`, default `09:30`
- `enforce_time_window`, default `false` for manual runs
- `execute`, default `false`

Manual runs default to dry-run and run immediately. Scheduled runs use
`--execute` and enforce the configured New York time window.
