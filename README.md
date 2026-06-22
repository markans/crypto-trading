# Trader.dev Bybit Signal Generator

This repo generates **trading signals** for Bybit linear perpetuals. It is
signal-only: it reads public market data, scores the trend, and reports a
recommendation plus a suggested entry / stop-loss / take-profit plan. **It never
places orders.** Acting on a signal is always a manual decision.

## Scripts

```bash
# Read-only analyzer: prints recommendation, confidence, EMA/RSI scores.
python3 scripts/bybit_analyze_symbol.py --symbol BTC/USDT

# Signal generator: analyzer + suggested plan + log + email notification.
python3 scripts/bybit_signal.py --symbol BTC/USDT --margin 25 --leverage 5 \
    --tp-sl-mode structure --structure-interval 60

# Suggested plan only (entry/SL/TP for a chosen side, no orders).
python3 scripts/bybit_signal_plan.py --symbol BTC/USDT --side Buy \
    --margin 25 --leverage 5 --tp-sl-mode structure --structure-interval 60
```

Symbols can be entered with or without a slash; they are normalized before use
(`BTC/USDT` -> `BTCUSDT`).

The `--margin` and `--leverage` values are used only to size the suggested plan
(quantity and PnL-based targets). No funds are committed and no API credentials
are required, because only public market-data endpoints are used.

## Signal Output

`bybit_signal.py` builds a suggested plan only when `confidence: strong`. For
weaker signals it still reports the recommendation and logs/emails the summary,
but no plan is produced. Each run:

- prints the signal to the console
- appends a record to `SIGNAL-LOG.md`
- emails the signal when email is configured (see below)

## Email Notifications

Set SMTP variables in `.env` (see [.env.example](.env.example)) to receive
signal alerts by email:

```text
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=you@example.com
SMTP_PASSWORD=your_app_password
SMTP_USE_TLS=true
EMAIL_FROM=you@example.com
EMAIL_TO=you@example.com
```

Email is best-effort: if SMTP is not configured, the run still prints and logs
the signal and simply skips the email. By default only `strong` signals are
emailed (`--email-min-confidence low|moderate|strong`), and a failure email is
sent if a run errors out. Use `--no-email` to disable email entirely.

For Gmail, use an [App Password](https://support.google.com/accounts/answer/185833),
not your account password.

## Market Data

- Demo public endpoint: `https://api-demo.bybit.com`
- Live public endpoint: `https://api.bybit.com`
- If Bybit public data is blocked, the signal generator falls back to Binance /
  Binance.US public market data.

`BYBIT_BASE_URL` selects the public data source. Because only public endpoints
are used, demo and live differ only in the price feed, not in any trading
behavior.

## Cloud Automation

For the daily scheduled signal via GitHub Actions, see
[README-CLOUD.md](README-CLOUD.md).
