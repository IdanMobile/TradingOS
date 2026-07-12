# Reproduction status -- SRC-PINE2 (Pine Supertrend strategy)

**Status: SPECIFIED_AND_IMPLEMENTED; NOT_INDEPENDENTLY_REPRODUCED.**

Justification: the canonical evaluator implements TradingView's published
ATR/RMA, recursive bands, and inverted direction-sign convention with a
deterministic local transition test. It is not labeled reproduced because an
independent TradingView Strategy Tester known-answer sequence is not retained.
Spec validates (`VALID_WITH_AMBIGUITIES`).
