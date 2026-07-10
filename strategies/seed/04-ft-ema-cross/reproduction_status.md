# Reproduction status -- SRC-FT2 (freqtrade EMA cross)

**Status: NOT_REPRODUCED (deferred).**

Justification: this project has no true EMA primitive yet (see
framework_assumptions.md); reproducing this item faithfully would require
either adding a real EMA implementation or accepting the SMA-approximation
ambiguity as the tested behavior, which would spot-check the approximation
rather than the source. Deferred until a real EMA primitive exists or the
approximation is explicitly accepted as in-scope by a reviewer. Spec
validates (`VALID_WITH_AMBIGUITIES`).
