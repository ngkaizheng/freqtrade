# PRE-REGISTRATION — the 2R target is the binding constraint, and that is a testable claim

**Date frozen:** 2026-09-28, **before any run of this design produced a number.**

---

## 0. What prompted this, stated as a trap

This design was written **after reading a result**. The 104-symbol run
(`docs-myself/PERP_SHORT_4H_RESULT_2026-09-28.md`) showed a short-only book
losing money while the same book of assets fell a median of **−80.9%**. The
obvious reading is that the exit caps the winners. Naming the losing exit is
exactly what this repository's exit-family study did, and the rule written down
there was: *"naming the losing exits invites a fix, and making that fix now is
selection, so it is recorded as a pre-registration question and NOT acted on."*

**So it is recorded here and not acted on — until now, with the gate fixed below.**

This is a **post-hoc hypothesis**. That is stated, not hidden, and §4 carries
the consequence.

## 1. Hypothesis

The frozen rule takes profit at **2R**. On a universe whose members fall 80% over
the sample, a 2R cap cannot capture a −80% move: the winner is closed at 3% while
the asset then goes to −80%. The edge may be present in the ENTRY and destroyed
by the EXIT.

This is the same structural claim the exit-family study made about 5m
(`EXIT_FAMILY_RESULT_2026-09-27.md`), where changing the exit alone moved gross
by **6.1×** — and where the same study also proved the exit is not always the
binding constraint. Both outcomes are possible and both are worth measuring.

## 2. What is frozen, and what varies

**Frozen (unchanged, and the run MUST NOT be compared to the baseline as if it
changed):** entry signal, rvol(20) >= 2.0, 20-bar Donchian, low-volatility regime
filter, stop 1.5 x ATR at the entry bar, time stop 42 bars, the low-vol filter's
windows, and every universe rule.

**Varies — one parameter, a published frontier, NOT a chosen cell:**

    target_r in {1.5, 2.0, 3.0, 5.0, 10.0, none}

`none` means no profit target at all: the trade exits on the stop or the
42-bar time stop. It is the extreme that most directly tests the hypothesis.

**The whole curve is published. Choosing a point on it and reporting that point
is forbidden** — that is the maximum-of-N construction this repository exists to
avoid, and it is why the 24-symbol, 104-symbol, engine and post-processing
estimates are all shown side by side rather than the best one.

## 3. The gate — fixed now

| # | gate | threshold |
|---|---|---|
| H1 | **the frontier is monotone-ish or has a clear interior maximum** | a flat or noisy curve means the target does not matter and the hypothesis is dead |
| H2 | at the best cell, dependence-adjusted t on net R at **measured_covid** | **>= 2.0** — unchanged from G1, no deflation for the search |
| H3 | mean R > 0 at measured_covid at the best cell | |
| H4 | >= 50% of symbols individually positive | unchanged from G3 |
| H5 | positive in >= 3 of 4 chronological splits | unchanged from G5 |
| H6 | **the same cell is also positive at engine_default** | a cell that only works when slippage is assumed away is not a result |

> **H2 carries the search penalty deliberately.** Six cells is a small search
> next to the project's 41,472, but the bar is NOT deflated. If the frontier
> needs deflation to clear 2.0, that is a FAIL, and it is reported as one.

## 4. What this file does NOT license, stated plainly

- **A winning frontier does not confirm the strategy.** The hypothesis was
  generated from this sample, so any cell that wins is in-sample by
  construction. A pass here is a *lead*, and the only thing that confirms it is
  a forward period this design cannot provide.
- **It does not reopen the 104-symbol G1 failure.** If the frontier shows the
  2R cell failing and a longer target passing, the correct reading is *"the exit
  was masking a signal that was previously measured as too weak"*, not *"the
  strategy now passes"*.
- **No second parameter moves in the same run.** If target_R turns out to
  matter, the stop width and the time stop are NOT re-tuned on the same sample.

## 5. Forbidden

- Quoting a single cell without the full curve.
- Quoting `engine_default` as a headline (it may only appear as H6's check).
- Changing the universe, the timeframe, the entry, or the stop in this design.
- Any hyperopt.
