# Ambiguities -- SRC-FT1 (freqtrade SampleStrategy)

1. Exact indicator set/thresholds have varied across freqtrade template-generator versions; this spec reproduces the long-standing (BB(20,2) + RSI(14)<30) shape, not one pinned commit.
2. Exit convention (mid-band vs upper-band) is not uniquely fixed across freqtrade doc revisions; mid-band chosen.
3. Exact file/commit unverified in this pass (no fetch tool used) -- reviewer to confirm before code reuse.
4. `startup_candle_count` real freqtrade strategies declare varies per author; the 20-bar Bollinger warm-up is a lower bound implied by the indicator itself, not a source-declared constant.
