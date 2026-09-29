# PRE-REGISTRATION — walk-forward test of the SELECTION PROCESS, not of the strategy

**Date frozen:** 2026-09-28, **before the split is run.**
**This project has no untouched holdout and cannot get one** — the panel is
2023-01 to 2026-08 and every bar of it has been seen. So this does not create
out-of-sample data. **What it does test is the one decision that is still
suspect: which N on the liquidity ladder.**

---

## 0. The remaining objection, stated exactly

`LADDER_SHAPE_RESULT_2026-09-28.md` answered the "is t=2.25 a selected spike"
objection: the curve is smooth, adjacent rungs correlate at 1.000, and N=50 is
not a local maximum. **But every rung was chosen with the whole sample in view.**
The shape test shows the *curve* is real. It cannot show that the *point picked
off the curve* is the one a practitioner would have picked in real time.

That is the last unexamined decision, and it is testable without new data.

## 1. The design

| period | bars | role |
|---|---|---|
| **DEVELOPMENT** | 2023-01-01 → 2024-12-31 | the ONLY data any choice may use |
| **OOS** | 2025-01-01 → 2026-08-31 | evaluated once, after the choice is frozen |

**The choice rule, frozen now, and deliberately naive:**

> Run the frozen strategy on the DEVELOPMENT period at every rung of the ladder,
> take the rung with the **highest naive t on net R at measured_covid costs**,
> and use that N for the OOS period. No other rule may be applied, and the
> development-period ranking may not be adjusted after seeing the OOS result.

**This is committed to in advance, including the possibility that it picks a
different N from 50 and that the OOS result is negative.** The prereg explicitly
forbids re-deriving the rule after seeing which N comes out.

Two things are reported, and only these two:
1. **Which N the development data picks** (this is the output; it is not the
   answer, it is the question)
2. **What that N does on OOS**, at the same four cost regimes, in R and in account
   terms, with the same dependence treatments

## 2. The gates

| # | gate | threshold |
|---|---|---|
| **W1** | **selection stability**: the N the development data picks is the N the full sample picks (**N=50**), OR within one ladder step of it | if the choice moves a lot with the window, the choice is window-dependent and N=50 should not be trusted as "the" setting |
| **W2** | **OOS sign**: the chosen N's mean R on OOS at measured_covid is **> 0** | the strategy must at least not invert out of sample |
| **W3** | **OOS t**: the naive t on OOS at measured_covid is **>= 1.0** | deliberately half the 2.0 bar, because a 44-month OOS window is much smaller than 44 months of development and §1a's power rule applies |
| **W4** | **OOS vs full-sample honesty**: the OOS return is reported next to the full-sample return, and if it is materially worse, that is stated as the finding | |

> **W3's bar is a power bar, not a laxity.** 22 months of OOS is roughly half the
> development window, so the standard error is ~1.4x larger; t=2.0 on the full
> sample corresponds to t≈1.4 at this OOS length, and 1.0 is the bar a
> genuinely-robust effect should still clear.

## 3. What each outcome means, written out BEFORE running

- **W1-W3 all pass** → the selection is stable and the effect carries forward.
  **This would be the first genuinely out-of-sample evidence this project has
  produced.** It would still not make it alpha, because
  `LADDER_SHAPE_RESULT` established the market-neutralised excess is negative —
  it would make it a **timing tool whose parameter was not chosen by hindsight**.
- **W1 fails, W2 passes** → the choice is window-dependent; the strategy works but
  the setting is not stable, and N=50 should be described as *an* operating point
  rather than *the* one.
- **W2 fails** → the effect does not carry forward at all, and the ladder result
  is in-sample. **This is the outcome the honest reading most expects**, because
  the strategy is regime-dependent and the OOS window (2025-2026) is precisely
  the falling-market half.
- **W2 and W3 both fail while W1 passes** → the N is stable and the effect is
  regime luck. That is a clean, publishable negative.

## 4. Forbidden

- Changing the choice rule after seeing which N it picks.
- Looking at the OOS period before the development ranking is written down.
- Quoting the full-sample N=50 result in the same sentence as an OOS number
  without both.
- Adding rungs, changing the signal, the stop, the target, the costs, or the
  universe. Everything stays frozen.
