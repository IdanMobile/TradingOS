# Reproduction status -- SRC-PAPER1 (Jegadeesh & Titman 1993 momentum)

**Status: NOT_REPRODUCED (not applicable).**

Justification: there is nothing in the source to reproduce a RESULT
against -- the paper reports cross-sectional portfolio returns over decades
of US equity data, not a per-bar rule this project's fixture could ever
replicate. What was extracted is the directional rule shape (trailing
return > 0 -> long), which is testable for internal consistency
(`validate_yaml` -> `VALID_WITH_AMBIGUITIES`) but not "reproduction" of the
paper's own result in any meaningful sense. Recorded honestly rather than
claiming a reproduction that would not mean what it appears to mean.
