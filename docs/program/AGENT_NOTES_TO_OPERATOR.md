# Agent notes to the operator — what's on my mind (2026-07-12)

You told me to complete HG-3/4/5 and not come back with questions — to write down anything on
my mind instead. Here it is, straight.

## 1. I could not "complete" HG-3/4/5, and I won't fake it

HG-3/4/5 are human-only gates. HG-4 and HG-5 require creating a venue account, entering
credentials, and authorizing real money — things I never do, on anyone's authorization. Beyond
the rule: the whole point of these gates is that a machine can't advance *itself* to live
capital. If I flipped them because you said so, the safety guarantee would be worth nothing at
the exact moment it matters — real money on a real exchange. So I did everything up to your
signature and stopped there. That's not me dodging work; it's the one place where doing the job
right means not doing it for you. This is recorded as **D-042**, and the ready-to-sign packages
are in **`HG_DECISION_PACKAGES.md`**.

## 2. The uncomfortable truth: nothing is genuinely validated yet

I want you to hear this plainly, because it's the real state of the business:

- Every predictive/technical strategy is rigorously dead (DSR ~0.7, fragile).
- Professional stat-arb fails out-of-sample (DSR 0.0088) — cointegration decays.
- **Funding carry is the only real edge**, and it's genuinely market-neutral. But its DSR
  "pass" is stamped `verdict_is_genuine: false`, and no amount of computing changes that,
  because:
  - Its killer risk (exchange counterparty default — FTX/LUNA) is a one-shot tail that is
    simply **absent from the historical data**. A backtest cannot validate away a risk it
    cannot see.
  - Its headline 8.4%/yr is **mostly the 2021 bull** (+42.6%); in the 2022 bear it lost
    (−3.8%), and in 2023–26 it made ~+3.7%.

So T-015-02 ("deploy a *validated* strategy") is blocked not just by human gates but by the
honest absence of a validated strategy. I will not manufacture one to make the pipeline look
finished.

## 3. What I built this session to make the eventual decision defensible

- `run_funding_carry_s3_paper.py` — drove carry through the S3 paper lane with realistic
  per-leg execution (spot+perp, taker+slippage). Net ~8.4%/yr; it survives execution.
- `run_funding_carry_robustness.py` — exposed the regime-dependence above.
- `run_funding_carry_regime_filter.py` — a causal (no-lookahead) universe-funding deploy gate
  that lifts the 2022 bear from −3.8% to −0.7%/yr while holding full-period 8.4%. A genuine
  risk overlay, not a date filter.
- `run_carry_counterparty_diversification.py` — the important one for your decision: a single
  venue is an unrecoverable −100% tail; **≥3 venues with per-venue caps** turns it into a
  recoverable ~1/K loss and shrinks total wipeout to p^K. Diversification doesn't raise the
  average return — it removes the catastrophe. That is the crux of HG-4.

All of this is `execution_authority=NONE`, no venue, no orders, thresholds untouched.

## 4. My actual recommendation (as the CEO/CTO/broker you asked me to be)

1. **Grant HG-3.** It's safe and starts nothing by itself.
2. **Do not put real money on carry yet.** Treat it as a research-grade candidate. If you want
   it in the *local* paper lane, that needs HG-3 + a validation-approved context and no venue.
3. **When you do go live, go multi-venue and capped from day one** — never a single exchange,
   never a size you can't fully lose. The counterparty tail, not the market, is what ends this
   strategy.
4. **Keep looking for a second uncorrelated sleeve.** Carry alone is one edge with one dominant
   risk; the risk-parity combination only becomes real with ≥2 validated sleeves.

Honestly: this is a promising, disciplined research program with one real but modest edge — not
a "back up the truck" signal. The value so far is that we know *exactly* what's real and what
isn't, and we never crossed a line to get there.

## 5. One thing you should know about the codebase right now

While I worked, another process (you, or another agent/session) was actively developing
`src/tios/services/paper/` and the dashboard in parallel. I finished the paper module's missing
`_activation_payload` when you asked, but I've deliberately stayed out of the rest of that
concurrent work — e.g. a dashboard "TradingView market monitor" test
(`test_dashboard_includes_read_only_tradingview_market_monitor`) is currently red because its
feature is half-built by that other process. Implementing it myself would collide with them and
is unrelated to HG-3/4/5. **My own work is green (534 tests);** that one red test is the other
stream's WIP. If that stream is yours, finish the market-monitor HTML in `dashboard.html`'s
generator; if you want me to take it over, tell me and I'll do it cleanly.

## 6. What remains — and it's only yours

- Sign **HG-3** (safe now).
- Get a genuine validation, or accept carry as paper-only research.
- Complete **HG-4**'s ten account-level items for ≥3 venues.
- **HG-5** limited-live review with capital you can lose.

I've done everything up to each of those signatures. The rest is, correctly, yours.
