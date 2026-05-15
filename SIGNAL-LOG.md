# Signal Log

## 2026-05-15 07:14:30 PST - MNTUSDT

- date_time: 2026-05-15 07:14:30 PST
- symbol: MNTUSDT
- analyzer_recommendation: Buy
- confidence: strong
- 15m_score: 3
- 60m_score: 3
- 240m_score: 3
- side_considered: Buy commentary only
- entry_reference: 0.69640
- stop_loss: 0.686 15m local low / invalidation reference
- take_profit: 0.7039 15m local high / nearby resistance reference
- reward_risk: 0.72 using local high and local low references
- margin_usdt: N/A
- leverage: N/A
- qty: N/A
- user_action: signal
- signal_comment: Live public Bybit analyzer showed bullish alignment across 15m, 60m, and 240m, with strong confidence. The setup is extended on the 60m RSI and local reward/risk to the 15m high is below 1.5:1.
- reason: Read-only signal request. No order command was run.
- result_r_multiple: N/A

## 2026-05-15 07:16:22 PST - MNTUSDT executed demo order

- date_time: 2026-05-15 07:16:22 PST
- symbol: MNTUSDT
- analyzer_recommendation: Buy
- confidence: strong
- 15m_score: 3
- 60m_score: 3
- 240m_score: 3
- side_considered: Buy
- entry_reference: 0.69730
- stop_loss: 0.61610
- take_profit: 0.69980
- reward_risk: 0.03
- margin_usdt: 100
- leverage: 20
- qty: 2868.2
- user_action: executed demo
- signal_comment: User requested a market Buy using Cross margin, 100 USDT margin, and 20x leverage. The order script used 1h structure for stop loss and take profit, set cross margin mode and leverage successfully, then created the market order on the configured demo endpoint. Reward/risk is low because the 1h swing-high take-profit reference is close to entry compared with the deeper 1h support stop.
- reason: Explicit user instruction to open/place the trade. Command included --execute.
- result_r_multiple: pending
- bybit_order_id: 8540fb0a-dd59-4af7-84e9-9f33d1b457af
