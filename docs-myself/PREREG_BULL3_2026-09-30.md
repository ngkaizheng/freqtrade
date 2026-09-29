# PREREG — B-3: THE RISK CURVE AND THE CHANDELIER CURVE FOR A1 (both published whole)

**Written:** 2026-09-30, before any B-3 backtest. Follows `PREREG_BULL2_2026-09-30.md` (B-2).

---

## 1. What B-2 settled, and the one number that decides this round

A1 = the frozen breakout entry, **run exits** (3-ATR chandelier, no 2R cap, no time stop),
breaker at 0.20. **+45.47 % over 3.67 y, PF 1.29, maxDD 20.25 %, 1,168 trades, positive in
all four calendar years, and positive in 2 of 2 up regimes.**

**And the reason it misses the bar is a RATIO, not a level:**

| | value |
|---|---:|
| A1 2023 | +9.4 % |
| panel at A1's own 6.5 % exposure | **+12.9 %** |
| **capture ratio** | **66.1 %** (not 3.3 %) |

## 2. ⚠ WHAT A RISK SWEEP CANNOT DO, STATED BEFORE RUNNING IT

**The bar is a ratio, and a ratio is roughly invariant to the thing this round varies.**

Doubling `risk_per_trade` doubles A1's exposure *and* doubles the matched-exposure
benchmark, because the benchmark is defined as `panel × A1's own deployed fraction`. So:

> **PREDICTION: the risk curve moves absolute dollars and the capture ratio roughly does not
> move with it.** If the capture ratio is flat across 0.25 %→1.5 %, then **no risk setting
> closes the gap**, and the honest conclusion is that **the entry, not the exposure, is what
> has to improve** — which is a different and much more specific next question than "run it
> bigger".

This is a falsifiable prediction and it is worth stating because the alternative — sweeping
risk and reporting the best total — is exactly the multiple-testing move this project exists
to detect.

**There is one channel that could break the invariance, and it is named in advance:**
compounding, and the **breaker**, which sits at 0.20. A1's drawdown at 0.5 % is already
20.25 %, so **at 1.5 % the drawdown should scale toward ~60 % and the breaker should start
firing** — which changes the trade set, not just the size. Whether that helps or hurts is
the measurement.

## 3. The arms — two published curves, no cell chosen

**Curve R — risk fraction** (entry and chandelier fixed at B-2's values):

| arm | `risk_per_trade` |
|---|---:|
| R1 | 0.25 % |
| R2 | **0.50 %** (= B-2's A1, re-run in the same batch as a self-consistency check) |
| R3 | 1.00 % |
| R4 | 1.50 % |

**Curve C — chandelier width** (risk fixed at 0.50 %):

| arm | `chandelier_atr` |
|---|---:|
| C1 | 2.0 |
| C2 | **3.0** (= A1) |
| C3 | 4.0 |
| C4 | 6.0 |

**B0 control** as always: **must reproduce 113.74 %**, and it is the proof that the new code
is not touching the short path.

**R2 and C2 are the SAME arm** (0.5 %, 3.0). It is run once and reported once, and it doubles
as a **reproduction of B-2's A1** — if the two disagree, one of the two runs is wrong and
that is reported rather than averaged.

## 4. Pre-registered decisions

**B0** reproduces 113.74 % → otherwise void.
**R2/C2 reproduce B-2's A1** (+45.47 %, 1,168 trades, 20.25 % maxDD) → a mismatch voids the
batch, because it means the machine or the data moved between runs.
**The capture ratio is the decision quantity at every rung of both curves**, not the total.
**Both curves are published whole**, in full, whatever they say.
**If the capture ratio is flat in risk** (the prediction), the axis "run it bigger" closes
and the next question is the entry. **If the capture ratio rises with risk**, the mechanism
is compounding or the breaker, and it is named.

**THE BAR IS UNCHANGED:** net-positive in the up regimes after measured cost, **and worth
having against holding the coins at the same deployed exposure** (panel: 2023 **+198.6 %**,
2024 **+103.6 %** at 100 %).

## 5. What this does NOT do

* **Does not touch the delivered book.** `exit_mode` still defaults to `"fixed"`, every
  short path still delegates to `super()`, and **B0 is the proof on every run.**
* **Does not promote A1 to a deliverable.** The bar is a ratio and the ratio is what is
  being measured; a curve is not a selection.
* **Does not search.** Two one-parameter curves, seven runs, everything published.
