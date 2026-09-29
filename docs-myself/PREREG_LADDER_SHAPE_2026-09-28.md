# PRE-REGISTRATION — is the t = 2.25 a spike, or the end of a curve?

**Date frozen:** 2026-09-28, **before any of these rungs is run.**
**This is a REFINEMENT of `PREREG_LIQUIDITY_ON_515_2026-09-28.md`, not a new
hypothesis.** The signal, the costs, the sizing and the cohort decomposition are
all unchanged. Only the ladder gets denser.

---

## 0. The objection this file exists to answer

`LIQ515_RESULT_2026-09-28.md` produced the project's first t ≥ 2.0: **N=50,
mean R +0.2128, naive t = 2.25, +89.9% at measured COVID costs.**

And immediately undercut it, correctly, six ways. The sharpest of those is
selection: **it is the best of four rungs, against a bar this project has never
search-deflated.** The supporting evidence looked like this:

| N | mean R (COVID) | naive t |
|---|---:|---:|
| 50 | +0.2128 | **2.25** |
| 100 | +0.1558 | 1.89 |
| 200 | +0.0833 | 1.17 |
| 515 | −0.4855 | −3.62 |

**Read as a shape, that is a MONOTONE DECAY driven by cost, not a spike.** A
selected maximum looks like a bump with low neighbours on both sides. This looks
like a gradient whose end happens to land near the bar.

**That reading is a hypothesis, and it is testable, and the test is cheap — the
data is already on disk.**

## 1. The test

A denser ladder over the SAME construction, same ranking, same everything:

```
N ∈ {25, 40, 50, 60, 75, 100, 125, 150, 200, 300, 515}
```

**The question is not "which N is best". It is whether `t(N)` is a smooth
function of N, or whether N=50 sits on a local bump.**

| # | criterion | what it means |
|---|---|---|
| **S1** | `meanR(N)` is **monotone non-increasing in N** (i.e. non-decreasing as N narrows) | the cost mechanism produces a smooth gradient |
| **S2** | N=50 is **not a local maximum** — at least one adjacent rung (40 or 60) has a t at least as large, or the curve is smooth through it | a selected cell has low neighbours on BOTH sides |
| **S3** | the curve does **not** oscillate: no rung more than one step away beats N=50 by more than the rung-to-rung noise | a genuine selection artifact oscillates |
| **S4** | report the **rank correlation** of the per-trade R series across neighbouring rungs | the rungs are NESTED, so if they are highly correlated the effective number of independent tests is near 1, and the multiple-testing penalty is small — **but this must be MEASURED, not assumed** |

**S4 is the one that decides whether selection matters at all here.** The rungs
are nested subsets, not independent bets. A nested family is a much weaker
multiple-testing problem than four independent trials, and the honest way to say
so is to measure the correlation rather than assert the nesting.

## 2. What is decided by what

- **S1 and S2 both pass** → the N=50 number is on a real cost gradient, and the
  "best of four" objection is much weaker than it looked. The honest description
  becomes "the edge is a function of tradability, and N≈50 is where the cost
  curve crosses the bar" rather than "a cell was selected".
- **S2 fails** (N=50 is an isolated local max) → the t=2.25 is a selection
  artifact, the first crossing of the bar in this project was luck, and the
  project should say so and move on.

**Either outcome is publishable. What is NOT publishable is a quote of +89.9% /
t=2.25 without the curve.**

## 3. Also run, and reported either way

**The market-neutralised excess for the rungs.** `LIQ515_RESULT` listed "the
market-neutralised excess is unchanged and still indistinguishable from zero" as
caveat 6, on the grounds that the round did not redo it. **This round does**,
for the top rungs, because a rung that is a short book on a falling panel could
plausibly be worse, not better, once neutralised — and the project should not
carry a claim it has not checked.

## 4. Forbidden

- Quoting any single rung without the full curve.
- Quoting t without saying whether it is naive, by-timestamp, or by-week.
- Adding a rung outside the frozen list because one of these looks bad.
- Adjusting the signal, the stop, the target, the costs or the universe.
- Presenting S1–S4 passing as "validated". They are checks on a selection
  artifact, not out-of-sample evidence. This project has no untouched holdout.
