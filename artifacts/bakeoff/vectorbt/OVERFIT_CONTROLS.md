# vectorbt Accelerator Overfit Controls

Status: **BINDING FOR ALL VECTORBT RESEARCH**

vectorbt is a high-throughput hypothesis accelerator. It is not an approval,
execution, or portfolio-risk engine, and an in-sample winner is never evidence of
future profit.

## Required controls

1. Parameter spaces and selection procedures are declared before reading outcomes.
2. Every trial—including failures and weak results—is retained in the experiment
   ledger. Best-only exports are prohibited.
3. No trial is promoted from the sweep window. Selection requires development,
   validation, untouched holdout, walk-forward, regime, cost, and neighboring-
   parameter evidence.
4. The validation layer must apply the selected, predeclared multiple-testing method
   before a family can become eligible. G10 remains unpassed until that method is
   validated; raw trial count is always reported.
5. Survivors must reproduce in an event-driven engine with explicit order/fill,
   precision, fee, slippage, and missing-data semantics.
6. Cash, buy-and-hold, and simple baseline comparisons remain mandatory.
7. Search expansion after viewing results creates a new experiment population; it
   cannot be merged silently with the original family.
8. AI may propose hypotheses but cannot select, hide, or approve trials.

These controls deliberately trade apparent speed for trustworthy evidence. The
accelerator may falsify ideas quickly; it cannot certify them.
