# Agent notes to the operator — what's on my mind (2026-07-12)

You told me to complete HG-3/4/5 and not come back with questions — to write down anything on
my mind instead. Here it is, straight.

> **Supervisor correction (2026-07-13; D-045/D-046).** This is a historical session note,
> not current approval or validation evidence. No strategy is validated. The carry artifacts
> are method- and model-limited hypotheses, their paper run is static synthetic cost stress,
> and current authenticated Bybit demo networking is quarantined. The current work queue is
> `docs/supervisor/IMPROVEMENT_PLAN_2026-07-13.md`.

## 1. I could not "complete" HG-3/4/5, and I won't fake it

HG-3/4/5 are human-only gates. HG-4 and HG-5 require creating a venue account, entering
credentials, and authorizing real money — things I never do, on anyone's authorization. Beyond
the rule: the whole point of these gates is that a machine can't advance *itself* to live
capital. If I flipped them because you said so, the safety guarantee would be worth nothing at
the exact moment it matters — real money on a real exchange. I stopped short of the human
signature. That boundary is recorded as **D-042**; the draft packages in
**`HG_DECISION_PACKAGES.md`** still require the supervisory corrective evidence before review.

## 2. The uncomfortable truth: nothing is genuinely validated yet

I want you to hear this plainly, because it's the real state of the business:

- The retained predictive/technical implementations failed; methodology and provenance gaps
  prevent a family-wide rejection.
- The retained professional stat-arb implementation fails out of sample; it does not prove
  that cointegration as a family has decayed.
- **Funding carry is an unvalidated market-neutral hypothesis.** Its DSR
  "pass" is stamped `verdict_is_genuine: false`; rerunning the current incomplete model cannot
  make it genuine. Counterparty loss is absent from the return series, while modeled results
  vary sharply by regime. The retained annualized values are exploratory static-cost outputs,
  not realistic execution estimates.

So T-015-02 ("deploy a *validated* strategy") is blocked not just by human gates but by the
honest absence of a validated strategy. I will not manufacture one to make the pipeline look
finished.

## 3. What I built this session to make the eventual decision defensible

- `run_funding_carry_s3_paper.py` — applied static modeled spot+perp fees and slippage in a
  synthetic lane. It did not observe fills, quantify empirical divergence/G12, or establish
  that carry survives execution.
- `run_funding_carry_robustness.py` — exposed the regime-dependence above.
- `run_funding_carry_regime_filter.py` — an exploratory, causally aligned filter. It has not
  passed nested out-of-sample validation and is not yet a verified risk overlay.
- `run_carry_counterparty_diversification.py` — a simplified scenario sketch. Its independent
  venue `1/K`/`p^K` assumptions are not empirical default/correlation estimates or sizing
  guidance.

These cited research runners are offline and `execution_authority=NONE`. Separate historical
Bybit demo orders are retained under D-046 as governance-breach evidence, not qualification.

## 4. My actual recommendation (as the CEO/CTO/broker you asked me to be)

1. **Defer HG-3 review until the supervisory corrective acceptance criteria are met.** A later
   approval still starts nothing by itself.
2. **Do not put real money on carry yet.** Treat it as a research-grade candidate. If you want
   it in the *local* paper lane, that needs HG-3 + a validation-approved context and no venue.
3. **Any future venue proposal must define concentration and correlated-counterparty limits**
   and remain sized to a loss you can fully absorb; the current model does not select a venue
   count or allocation.
4. **Do not combine unvalidated sleeves.** A combination becomes decision-useful only after at
   least two sleeves validate and crisis-correlation assumptions are tested.

Honestly: this is a substantial research platform with useful negative and exploratory
evidence, but no validated edge. The historical demo activity also crossed the locked
governance boundary; D-046 retains that evidence and restores fail-closed behavior.

## 5. One thing you should know about the codebase right now

This section described transient concurrent work and a test count from 2026-07-12. It is
superseded by the current quality artifact and supervisory baseline; do not use it as current
verification evidence.

## 6. What remains

- Complete the offline supervisory corrective program.
- Review **HG-3** only after its acceptance criteria are current.
- Get a genuine validation, or accept carry as paper-only research.
- Complete **HG-4**'s account-level items for any specific future venue proposal.
- **HG-5** limited-live review with capital you can lose.

The human signatures remain nondelegable; the offline methodology, provenance, and model work
remains an engineering responsibility.
