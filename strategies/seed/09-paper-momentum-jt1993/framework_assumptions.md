# Framework assumptions -- SRC-PAPER1

- The paper's cross-sectional decile-ranking mechanism has no equivalent in this project's single-instrument canonical spec; approximated as a same-instrument trailing-return sign rule (see ambiguities.md) -- the single largest fidelity gap in this seed batch.
- No fee/slippage/rebalance-cost model is asserted (the paper studies gross returns before frictions in its main tables; this project's canonical spec leaves costs to the engine/backtest-run layer regardless).
- Monthly rebalance cadence collapsed to continuous per-bar evaluation, consistent with this project's bar-driven execution model.
