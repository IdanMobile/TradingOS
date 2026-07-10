# Reproduction status -- SRC-HB2 (Hummingbot pmm_simple)

**Status: NOT_REPRODUCED (not applicable).**

Justification: there is no discrete entry/exit signal in this item's own
canonical spec to check bar-by-bar (see ambiguities.md) -- a "reproduction"
would only be checking that `always_in_market: true` holds trivially on every
bar, which asserts nothing about the controller's real behavior (continuous
bid/ask quoting, inventory skew, spread management). Recorded here as the
seed batch's example of a source whose semantics could not be faithfully
canonicalized within this project's current spec schema at all -- a schema
finding, not a deferred-for-effort item like the others.
