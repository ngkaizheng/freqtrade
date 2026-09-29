# §48 — B-3: THE PRE-REGISTERED PREDICTION WAS WRONG, THE CHANDELIER IS THE LEVER, AND THE BEST CELL SITS ON THE EDGE OF THE RANGE

**Date:** 2026-09-30 · **Prereg:** `docs-myself/PREREG_BULL3_2026-09-30.md` (before any B-3 run)
**Tool:** `bull_axis.py` · **Raw:** `user_data/logs/{bt_bull_*,bull_axis}.txt` · **B0 gate: 113.74 % ✓**

---

## 1. Both self-consistency checks passed before any arm was read

* **B0 control: 1,111 trades / 113.74 % / PF 1.36 / maxDD 18.43 %** — the deployed book.
* **R2 reproduced B-2's A1 exactly: 1,168 trades / +45.47 % / PF 1.29 / 20.25 %.** Two
  separate runs, identical. The machine did not move between them.

## 2. Curve R — the risk fraction, published whole

| risk | trades | **total** | PF | maxDD | deployed | 2023 | 2024 | **capture 2023** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.25 % | 1,288 | +32.07 % | 1.39 | 13.02 % | 3.3 % | +4.5 % | +1.8 % | 67.8 % |
| 0.50 % | 1,168 | +45.47 % | 1.29 | 20.25 % | 6.5 % | +9.4 % | +4.0 % | **72.9 %** |
| **1.00 %** | 910 | **+61.96 %** | 1.25 | 23.44 % | 12.0 % | +11.6 % | +7.2 % | **48.9 %** |
| 1.50 % | 792 | +50.74 % | 1.16 | 31.45 % | 16.4 % | +19.8 % | +5.3 % | 60.8 % |

> **⚠ MY PRE-REGISTERED PREDICTION WAS: "the capture ratio is roughly INVARIANT to risk,
> because doubling the risk doubles the arm AND its matched-exposure benchmark."**
> **It is FALSE.** Capture runs 67.8 → 72.9 → **48.9** → 60.8, a **24 pp spread**, and the
> arm with the **best total (+61.96 %) has the WORST capture (48.9 %)**.
>
> **So the risk axis does not close the gap — and saying so is the useful part.** Stating a
> prediction in advance, watching it fail, and reporting that it failed is what separates a
> curve from a search.

## 3. Curve C — the chandelier width, and it is the live axis

| chandelier | trades | **total** | PF | maxDD | 2023 | 2024 | **capture 2023** | **capture 2024** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2.0 | 1,293 | +15.81 % | 1.13 | 17.31 % | **−1.7 %** | **−1.7 %** | **−13.0 %** | −25.2 % |
| 3.0 | 1,168 | +45.47 % | 1.29 | 20.25 % | +9.4 % | +4.0 % | 72.9 % | 59.2 % |
| 4.0 | 1,107 | +32.48 % | 1.19 | 22.88 % | +9.3 % | +11.1 % | 72.9 % | 166.7 % |
| **6.0** | 1,039 | **+71.38 %** | 1.31 | 28.17 % | **+31.4 %** | **+23.8 %** | **245.5 %** | **357.3 %** |

**C4 beats buy-and-hold at matched exposure by 2.5× in 2023 and 3.6× in 2024** — the first
arm in this project to pass the **second half** of the preregistered bar.

## 4. ⚠ AND IT IS AN ARTEFACT UNTIL PROVEN OTHERWISE, ON THREE COUNTS

**It is the boundary cell.** 6.0 is the largest chandelier tested. **§20c's rule applies
verbatim: a best value at the edge of the range is not a peak, it is a direction.**

**The curve is non-monotone**: 15.81 → 45.47 → **32.48** → 71.38. A monotone climb would be
interpretable; a curve that goes down at 4.0 and then up at 6.0 is noise plus signal, and
**the only way to tell them apart is to extend the range** — which is exactly the test that
has not been run.

**The mechanism is suspicious in a specific way.** A 6-ATR chandelier is a very loose stop.
With a breakout entry and a loose stop, the trade is converging on **buy-and-hold with a
crash exit** — which is the very thing the matched-exposure benchmark already measures. Its
2025 result is the tell: **the panel fell −56.8 % and C4 made exactly 0.0 %**, while C2
(A1) made +17.9 % and the deployed short book made more. **A loose chandelier rides the
crash down, and buys its 2023 number by staying long, not by timing.**

## 5. ⚠ THE OBJECTIVE IS MOSTLY ANSWERED BY SOMETHING ALREADY DELIVERED

| arm | deployed | 2023 | 2024 | **capture 2023** | **capture 2024** |
|---|---:|---:|---:|---:|---:|
| **B0 — the deployed SHORT book** | **5.3 %** | +11.7 % | +27.1 % | **110.8 %** | **492.7 %** |
| C4 — the new long book | 6.4 % | +31.4 % | +23.8 % | 245.5 % | 357.3 % |

> **The delivered short book ALREADY passes both halves of the preregistered bar**: it is
> net-positive in 2 of 2 up regimes, and it beats holding the coins **at the same deployed
> exposure** in both — 110.8 % and 492.7 % of the matched-exposure benchmark.
>
> **The premise "the delivered book is bad in bull markets" is wrong in the form that
> matters.** It captures little of the upside, and it is *short*, so it is a poor way to
> hold a bull market. It is not a losing one, and at matched exposure it is a better one.

**So the honest answer to the user's request is two-part, and both parts are measured:**
1. **A bull-market book that beats matched-exposure buy-and-hold exists, and you already
   have one — it is the delivered short book.**
2. **A long book can do it better in the up years** (C4: +31.4 % / +23.8 %) **but pays for
   it in the down years** (2025: 0.0 % against A1's +17.9 % and the panel's −56.8 %), and
   **its best cell is on the edge of the range and has not been shown to be a peak.**

## 6. Verdict and the one next step

**B-3 closes the RISK axis** — the pre-registered prediction that it would close the gap is
refuted, and capture is non-monotone in risk.
**B-3 leaves the CHANDELIER axis open at exactly the wrong place** — the best cell is the
boundary cell on a non-monotone curve.

> **The next run is one thing: extend the chandelier to 8.0, 10.0 and 12.0, same risk, same
> entry, B0 as the gate, the whole curve published.** If capture climbs and then flattens
> toward 100 % — the buy-and-hold asymptote — **C4's "edge" was never an edge and the family
> is answered**. If it peaks and falls, 6.0 is real and can be promoted.

**A1/C4 is NOT promoted this round.** A best value at the boundary of a non-monotone curve,
on two regimes, with a mechanism that reduces to buy-and-hold, is not a deliverable — it is
the next experiment.

## 7. Errors of my own this round

* **`bull_axis.py` had a syntax error** in the prediction line (an unterminated f-string
  across a conditional), which made the run exit 1 after the backtests were already done.
  Caught by reading the log rather than the exit code alone.
* **The prediction itself is the larger lesson.** I wrote down what I expected and it was
  wrong. **That is recorded as a refutation, not quietly re-derived after the fact** — which
  is the whole reason the preregistration exists.
