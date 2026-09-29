# PRE-REGISTRATION — size by coincidence, the last measured mechanism not yet used

**Date frozen:** 2026-09-29, **before any run of this design.**

---

## 0. The mechanism, and why it is not a parameter tweak

`tools/perp_short/market_check.py` measured, on 515 perps, the equal-weight
panel's forward 42-bar return at every bar the panel produced a signal:

| symbols signalling together | bars | forward panel return | t |
|---|---:|---:|---:|
| 1 | 409 | −1.465% | −3.26 |
| 2 | 121 | −1.928% | −2.27 |
| 3–4 | 93 | −1.950% | −1.99 |
| 5–7 | 62 | −2.645% | −2.14 |
| 8–12 | 41 | −1.583% | −1.20 |
| **13+** | **117** | **−4.678%** | **−4.61** |

**The 13+ bucket's market move is roughly three times every other bucket's, and
it is the only one whose t is past −4.** This is a *market* fact, measured
independently of any strategy P&L, and it is observable LIVE (count the symbols
that signalled on this bar) — unlike the panel forward return itself, which is
why the 13+ figure has never been actionable until now.

**What has been used so far:** the stop multiple, the target, the time stop, the
universe, the liquidity band. **What has never been used: the size.**

**And the size is the one dimension the project's own cost law already argues
about.** The book's problem is not that it trades badly; it is that a fixed 1%
per trade is taken 18 times at once during a cascade.

## 1. Design — sizing only, one distributional threshold

```
if (number of symbols signalling on this bar) >= Q:
    size = 1.0 x base risk
else:
    size = 0.5 x base risk
```

**`Q` is set from the DISTRIBUTION, not from performance:** Q = the 85th percentile
of the per-bar coincidence count over the panel, which is 13. **It is not searched,
and it is not chosen because that rung scored best** — the mechanism table above
is what argues for scaling at the top of the distribution, and the percentile is
the operational definition of "the top of the distribution".

**Total portfolio risk is held constant across the design**: the base risk is
reduced so that the average position size matches the unsized book, so this is a
*redistribution* of risk, not a change in leverage. Otherwise the comparison is
confounded with size and proves nothing.

**Everything else frozen:** the signal, the 4.0×ATR entry-bar stop, the 2R target,
the 42-bar time stop, the universe, the liquidity band, the costs, the
circuit breaker, and the dev/OOS split.

## 2. The gate, fixed now

| # | criterion | what decides it |
|---|---|---|
| **C-1** | **coherence**: at the sizing split, the forward panel return of the 13+ bars is materially larger in magnitude than the rest | re-checks the mechanism on this exact universe, rather than trusting a table from a different pair set |
| **C-2** | **OOS sign preserved**: the sized book has mean R > 0 on 2025-2026 at measured_covid | a sizing rule that flips the sign out of sample is worse than no rule |
| **C-3** | **risk is genuinely redistributed, not added**: the sized book's PEAK CONCURRENT EXPOSURE is no larger than the unsized book's | if it is larger, the comparison is a leverage change |
| **C-4** | **it actually helps the thing that hurts**: the sized book's **maximum drawdown** is at least **20% lower** at the same total risk | a rule that does not reduce the drawdown has not addressed the problem |
| **C-5** | mean R on OOS is not worse than the unsized book's by more than 25% | a pure risk cut that also cuts the edge is a bad trade |

**If C-4 fails, the design is rejected even if mean R improves** — the stated
problem is the drawdown, and a rule that leaves it alone has not solved it.

## 3. What a pass would and would not mean

- **It would not make this alpha.** The market-neutralised excess is negative and
  this rule does not touch it; it is still a timing overlay.
- **It is a risk control, and risk controls are easier to validate than edges** —
  a lower drawdown is a directly observable outcome, not a t-statistic.
- **Q is a distributional cutoff, which is the most defensible kind of threshold
  available here, but it was chosen after the mechanism table was seen.** The
  walk-forward split is what tests whether it carries.
- **Passing C-2..C-5 out of sample would be the first genuinely out-of-sample
  PASS in this project.** No claim is made beyond that.

## 4. Forbidden

- Searching Q. It is the 85th percentile, fixed here, before the run.
- Changing the base risk and the cap so the sized book has more total risk.
- Quoting the full-sample number without the OOS one beside it.
- Presenting a lower drawdown as a higher expected return.
