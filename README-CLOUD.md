# Cloud Automation

This repo runs a daily strong-signal **alert** on GitHub Actions. It is
signal-only and never places orders.

The workflow is:

```text
.github/workflows/bybit-daily-strong-signal.yml
```

## What It Does

Every day near `09:30 America/New_York`, the workflow runs:

```bash
python3 scripts/bybit_signal.py --symbol BTC/USDT --margin 25 --leverage 5 \
    --tp-sl-mode structure --structure-interval 60 --ny-time 09:30 --ny-window-minutes 45
```

The script:

- checks the BTC/USDT signal from public market data
- builds a suggested entry / stop-loss / take-profit plan when `confidence: strong`
- emails the signal (and emails a failure notice if a run errors out)
- appends the result to `SIGNAL-LOG.md`
- uploads `SIGNAL-LOG.md` as a workflow artifact

No orders are placed. Acting on a signal is a manual decision.

## Required GitHub Secrets

Email delivery (set these to receive alerts):

```text
SMTP_HOST
SMTP_PORT
SMTP_USERNAME
SMTP_PASSWORD
SMTP_USE_TLS
EMAIL_FROM
EMAIL_TO
```

Market data (optional):

```text
BYBIT_BASE_URL          # https://api-demo.bybit.com or https://api.bybit.com
BYBIT_MARKET_BASE_URL   # optional explicit public market-data source
```

When `BYBIT_BASE_URL` is demo, public market data defaults to
`https://api.bybit.com` because GitHub-hosted runners may receive `403
Forbidden` from the demo public market-data endpoint. If Bybit public market
data is also blocked, the signal check falls back to Binance / Binance.US public
market data. No API keys are needed — only public endpoints are used.

## Publish To GitHub

If this folder is not yet a Git repository:

```bash
git init
git add .
git commit -m "Add Bybit daily strong-signal alerts"
git branch -M main
git remote add origin git@github.com:YOUR_USER/YOUR_REPO.git
git push -u origin main
```

Then open the GitHub repository:

1. Go to Settings -> Secrets and variables -> Actions.
2. Add the SMTP secrets above (and optionally `BYBIT_BASE_URL`).
3. Go to Actions -> Bybit Daily Strong Signal.
4. Run manually once and confirm the email arrives.
5. Inspect the workflow logs and `signal-log` artifact.

## Manual Cloud Run

The workflow supports manual inputs:

- `symbol`, default `BTC/USDT`
- `margin`, default `25` (sizes the suggested plan only)
- `leverage`, default `5` (sizes the suggested plan only)
- `ny_time`, default `09:30`
- `enforce_time_window`, default `false` for manual runs

Manual runs ignore the New York time window unless `enforce_time_window=true`,
so they produce a signal immediately. Scheduled runs enforce the configured
window.
