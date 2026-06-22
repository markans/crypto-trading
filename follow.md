# Build a 24/7 Crypto Trading Bot With Codex + Bybit

> Educational purposes only.  
> Not financial advice.

---

# Step 1 — Install Codex

Download and install Codex on your computer.

Resources:
- https://openai.com/codex/
- https://developers.openai.com/codex

After installation:

1. Open Codex
2. Switch to the **Code** workspace
3. Create a new project folder:

```bash
crypto-trading
```

4. Open the folder inside Codex

---

# Step 2 — Connect to the Bybit API

We need real-time Bitcoin market data.

Inside Codex, use this prompt:

```text
Build a crypto trading bot for Bitcoin.

Connect to the Bybit API and retrieve:
- 1-minute candles
- 15-minute candles
- 1-hour candles
- 1-day candles

Use historical and live market data.
```

Codex will:
- Find the API documentation
- Connect to Bybit
- Pull market data automatically

---

# Step 3 — Create the Trading Strategy

Use a strategy that combines:

- RSI
- MACD
- Moving averages
- Bollinger Bands
- Trend following
- News sentiment analysis

Risk management rules:

- Maximum 1% risk per trade
- Minimum 1:2 risk/reward ratio
- Mandatory stop-losses

Prompt example:

```text
Create a mid-term Bitcoin trading strategy using:

- RSI
- MACD
- Moving averages
- Bollinger Bands
- Trend confirmation
- Risk management

Rules:
- Max 1% risk per trade
- Minimum 1:2 risk/reward
- Always use stop-losses
```

---

# Step 4 — Improve the Strategy With Codex

Ask Codex to optimize the strategy.

```text
Analyze this trading strategy and suggest improvements for:
- entry conditions
- stop-losses
- volatility handling
- trend filtering
```

Codex may recommend:
- ATR stop-losses
- Better trend filters
- Reduced false entries
- Improved trade timing

---

# Step 5 — Add AI News Analysis

Add crypto news sentiment analysis.

Prompt:

```text
Scrape crypto news daily and analyze whether the sentiment is:
- bullish
- bearish
- neutral

Use the results to influence trading decisions.
```

This prevents trading against major market events.

---

# Step 6 — Generate the Trading Bot

Now instruct Codex to build the complete system.

```text
Build the complete trading bot using:
- Bybit API
- technical indicators
- news sentiment analysis
- risk management

Verify that everything works correctly.
```

Codex will generate:
- Bot logic
- Strategy engine
- API integrations
- Risk controls

---

# Step 7 — Configure API Keys

## OpenAI API Key

Create an OpenAI API key for AI analysis.

Then tell Codex:

```text
Configure this OpenAI API key for AI news analysis.
```

---

## Bybit API Key

Inside Bybit:

1. Open API Management
2. Create a new API key
3. Enable trading permissions
4. Copy the credentials

Then paste them into Codex:

```text
Connect this bot to my Bybit account using these API keys.
```

---

# Step 8 — Test With Paper Trading

Never start with real money.

Enable paper trading first.

Prompt:

```text
Run the bot in paper trading mode and simulate trades without using real money.
```

Example result:

```text
No entry detected.
Indicators did not meet conditions.
```

This confirms the strategy is functioning correctly.

---

# Step 9 — Automate the Bot

We want the bot to run automatically.

Prompt:

```text
Turn this into an automated cloud routine that runs every 10 minutes.

Requirements:
- Check market conditions
- Analyze indicators
- Analyze news sentiment
- Send a trading signal (recommendation + suggested plan) by email
- Never place orders automatically; acting on a signal stays manual
```

---

# Step 10 — Deploy With GitHub Actions

Deploy the bot to the cloud.

Prompt:

```text
Deploy this trading bot using GitHub Actions.

Requirements:
- Create a private repository
- Store secrets securely
- Run every 10 minutes
- Email the signal from the cloud (no automatic order placement)
```

Codex will:
- Create the GitHub workflow
- Configure automation
- Upload the project
- Secure API secrets

---

# Recommended Safety Guardrails

Always implement:

- 1% maximum risk per trade
- Stop-losses
- Daily loss limits
- Position size limits
- API key restrictions
- Paper trading before live deployment

---

# Final Result

You now have a 24/7 crypto trading signal bot that:

1. Pulls Bitcoin data from Bybit
2. Analyzes indicators
3. Reads crypto news sentiment
4. Produces a trading signal with a suggested plan
5. Emails the signal to you (you decide whether to trade)
6. Runs continuously in the cloud