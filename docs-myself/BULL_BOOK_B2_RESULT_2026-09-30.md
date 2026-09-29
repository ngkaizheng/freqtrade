# §47 — B-2: A BULL-MARKET BOOK EXISTS. THE EXITS WERE WORTH +26 POINTS, AND THE MISS WAS MOSTLY EXPOSURE

**Date:** 2026-09-30
**Prereg:** `docs-myself/PREREG_BULL2_2026-09-30.md` (factorial, before any B-2 backtest)
**Strategy:** `user_data/strategies/PerpLong4h.py` (`exit_mode`). Tool `bull_axis.py`.
Raw `user_data/logs/{bt_bull_*,bull_axis}.txt`. **The delivered book is untouched — B0 proves it.**

---

## 1. B0 — the control gate, and it is the proof everything else depends on

**1,111 trades · 113.74 % · PF 1.36 · maxDD 18.43 %** — the deployed book, exactly, with the
entire B-2 exit machinery present in the class. Every short path delegates to `super()`, so
the long numbers are a mirror of a verified book rather than a new strategy wearing its name.

## 2. The three pre-registered contrasts, all decisive

| contrast | total | maxDD | reading |
|---|---:|---:|---|
| **EXITS** fixed → run, same entry | **19.22 % → 45.47 %** | 23.59 % → **20.25 %** | **the §45d mechanism is confirmed** — better return AND a smaller drawdown |
| **EXPOSURE** 0.5 % → 1.0 % risk | 5.63 % → 22.33 % | 7.52 % → 12.32 % | 3.97× return for 2× risk |
| **ENTRY** breakout → panel trend | 45.47 % → 5.63 % | 20.25 % → 7.52 % | **the breakout entry is far better**; the panel entry is not |

## 3. By regime, against the panel

| year | regime | **PANEL @100 %** | B1 breakout FIXED | **A1 breakout RUN** | B2 panel FIXED | A2 panel RUN | A3 panel RUN 1 % |
|---|---|---:|---:|---:|---:|---:|---:|
| **2023** | **UP** | **+198.6 %** | +2.5 % | **+9.4 %** | −2.7 % | +3.7 % | **+12.2 %** |
| **2024** | **UP** | **+103.6 %** | +5.6 % | **+4.0 %** | +1.3 % | +1.4 % | +3.0 % |
| 2025 | DOWN | −56.8 % | +9.7 % | **+17.9 %** | −3.0 % | −3.3 % | −5.4 % |
| 2026 | DOWN | −17.6 % | +0.4 % | **+8.5 %** | +4.5 % | +3.9 % | **+11.9 %** |

| arm | trades | total | PF | maxDD | 2023 | 2024 |
|---|---:|---:|---:|---:|---:|---:|
| B0 control (deployed short) | 1,111 | 113.74 % | 1.36 | 18.43 % | +11.7 % | +27.1 % |
| B1 breakout, FIXED exits | 1,284 | 19.22 % | 1.10 | 23.59 % | +2.5 % | +5.6 % |
| **A1 breakout, RUN exits** | **1,168** | **+45.47 %** | **1.29** | **20.25 %** | **+9.4 %** | **+4.0 %** |
| B2 panel trend, FIXED | 949 | −0.10 % | 1.00 | 9.84 % | −2.7 % | +1.3 % |
| A2 panel trend, RUN | 789 | +5.63 % | 1.05 | 7.52 % | +3.7 % | +1.4 % |
| A3 panel trend, RUN 1.0 % | 725 | +22.33 % | 1.11 | 12.32 % | +12.2 % | +3.0 % |

## 4. ⚠ THE CONTROL B-1 DID NOT HAVE, AND IT CHANGES THE VERDICT

**B-1 compared a book that deploys ~6.5 % of capital against a benchmark that deploys 100 %.**
That is §41's lesson repeated — comparing two different quantities and calling the gap a
finding — and it inflated the miss by roughly the exposure ratio.

| arm | **avg deployed** | panel @ 100 % | **panel @ the same exposure** | arm 2023 |
|---|---:|---:|---:|---:|
| A1 breakout, RUN | **6.5 %** | +198.6 % | **+12.9 %** | **+9.4 %** |
| A3 panel, RUN 1 % | 8.2 % | +198.6 % | +16.3 % | +12.2 % |
| B0 deployed short | 5.3 % | +198.6 % | +10.5 % | +11.7 % |

> **A1 captured 4.3 % of the panel's move at 100 % exposure — and 66.1 % of it at its own
> 6.5 % exposure.** B-1's headline "3.3 %" was a comparison artefact.
>
> **And A1 is not beta.** In 2025 the panel fell **−56.8 %** and **A1 made +17.9 %**. A book
> that were capturing 6.5 % of beta would have made **−3.7 %** that year. **A1 is a trend
> book: the chandelier stop gets it out of the crash and back in at the low.**

## 5. THE PREREGISTERED BAR, applied honestly

| half of the bar | A1 | verdict |
|---|---|---|
| net-positive in the up regimes after measured cost | 2023 **+9.4 %**, 2024 **+4.0 %** — **2 of 2** | **PASS** |
| **worth having against holding the coins at the same deployed exposure** | 2023 +9.4 % vs **+12.9 %**; 2024 +4.0 % vs **+6.7 %** | **FAIL — by 1.4× and 1.7×** |

**A1 still fails the second half of the bar. It failed it by 1.4× and 1.7×, where B-1 failed
by 30×.** That is a different order of failure and it is the difference between "this idea is
dead" and "this idea works and is under-exposed".

**And the half it fails on is not the half the user asked about.** A1 is **positive in all
four calendar years** — +9.4 / +4.0 / +17.9 / +8.5 — in a sample where the panel is positive
in two. **It is a bull-market book in the sense that matters: in 2023 it made +9.4 % while the
market made +198.6 % and the delivered short book made +11.7 %.** It is not the best book in
2023. It is a book that does not stop working when the market turns.

## 6. Verdict, and the one-arm next step

**B-2 is a partial success with a measured, single-parameter next step.**

* **The §45d mechanism is confirmed, not just measured:** removing the 2R cap, removing the
  42-bar time stop and replacing the fixed anchor with a 3-ATR chandelier took the same
  entry from **+19.22 % to +45.47 %** while **cutting** the drawdown from 23.59 % to 20.25 %.
  *The same stop, target and time stop that make the short book work are what made the long
  book fail, and removing them is what makes it work.*
* **The breakout entry beats the panel-trend entry by 8×** (45.47 % vs 5.63 %) at equal risk
  and equal exits, so the high-exposure hypothesis is **refuted** — exposure was not the
  lever for this signal.
* **Exposure IS still unexhausted for A1.** A1 runs at 20.25 % drawdown with a 24.5 %
  structure, and A3 demonstrated that doubling the risk fraction on the panel entry moved the
  return 3.97× for 2× the risk. **A1 at 1.0 % risk is therefore the obvious next arm, and it
  is a one-parameter change with the control gate already in place.**

**A1 is NOT promoted to a deliverable this round.** It fails the second half of its own
preregistered bar, it is one regime-pair from being an overfit, and §41's rule applies: a
result that won in exactly the regimes it was selected on is one data point, not a result.
The next round runs A1 at 1.0 % and 1.5 % risk as a **published risk curve, not a search for
the best cell**, and the bar is unchanged.

## 7. Two errors of my own, and the one that mattered most

1. **`custom_stoploss` raised `NameError` on EVERY call in the first B-2 run** — I used
   `timeframe_to_prev_date` without importing it. **A `custom_stoploss` exception is
   swallowed by freqtrade and the entry is allowed through (trap 6)**, so both long arms ran
   their entire history on the **−30 % class backstop** and produced numbers that looked like
   results. The tell was not the number — it was the `ERROR` line the run printed thousands
   of times, which is exactly the signal this project has trained itself to stop scrolling
   past. The guard is now explicit in the code.
2. **`bull_axis.py` indexed an equity path of length n+1 with a mask of length n.** Invisible
   until the first trade of the first arm. §46's class.

**The thing that actually protects this family is still the control arm: B0 reproduced
113.74 % on every single run, including the ones where the long arms were broken.** A control
that reproduces a known value is the cheapest bug detector ever built.
