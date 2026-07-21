# B2 Real Loss Attribution

Date: 2026-07-21

Mode: retained offline backtest evidence; no tuning, holdout access expansion, or orders

## Hard evidence

- Round trips analyzed: **1407**
- Profitable / losing / breakeven: **242 / 1165 / 0**
- Gross P&L: **-165.9356942000000000 USDT**
- Recorded fees: **2813.09721472 USDT**
- Net P&L: **-2979.0329089200000000 USDT**
- Gross-positive trades turned negative by fees: **329**

Classification: **STRATEGY_WEAKNESS**

Recommendation: **REJECT_WITHOUT_RESCUE**

The zero-fee aggregate remains **-165.9356942000000000 USDT**, so fees are
severe but do not rescue the underlying development/holdout weakness. Existing validation
also records zero positive walk-forward windows, all neighboring variants negative, and
benchmark underperformance. The correct improvement is rejection, not a post-hoc V2.

The no-trade counterfactual avoids **2979.0329089200000000 USDT**
of modeled loss, but it is diagnostic only and is not reported as trading profit.
