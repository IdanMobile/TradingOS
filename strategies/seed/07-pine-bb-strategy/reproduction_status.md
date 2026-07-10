# Reproduction status -- SRC-PINE1 (Pine Bollinger Bands strategy)

**Status: NOT_REPRODUCED (deferred).**

Justification: same 20-bar Bollinger warm-up limitation as SRC-FT1 -- the
16-bar frozen micro fixture never reaches warm-up, so no bar exists where a
signal could fire. Spec validates (`VALID_WITH_AMBIGUITIES`). Deferred to a
future pass with a longer fixture.
