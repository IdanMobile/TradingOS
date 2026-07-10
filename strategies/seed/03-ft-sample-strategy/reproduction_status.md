# Reproduction status -- SRC-FT1 (freqtrade SampleStrategy)

**Status: NOT_REPRODUCED (deferred).**

Justification: the 20-bar Bollinger warm-up never completes against this
project's 16-bar frozen micro fixture (`fixtures/micro/bars.csv`) -- there is
no bar in the fixture where a signal could fire, so a reproduction run would
assert nothing. Spec validates (`VALID_WITH_AMBIGUITIES`, 2 ambiguities, both
justified above). Deferred to a future ingestion pass with a longer fixture,
or to whichever S2 validation task needs a mean-reversion-family internal
baseline.
