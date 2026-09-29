# PRE-REGISTRATION — can a cost constraint recover the book, and would it just be survivorship again?

**Date frozen:** 2026-09-28, **before any widened-universe backtest is run.**
**Runs after the diagnostic in `tools/perp_short/liq_overlap.py`, which is part
of this preregistration's evidence base.**

---

## 0. The situation this has to answer

`WIDENED_UNIVERSE_RESULT_2026-09-28.md` located the failure precisely:

| | gross PF | COVID PF | verdict |
|---|---:|---:|---|
| cohort A (104, 2023 survivors) | 1.25 | **1.10** | survives cost |
| cohort BCDE (411, never tested) | 1.08 | **1.01** | cost eats the whole edge |
| all 515 (tradable today) | 1.05 | **0.95** | negative |

**So the signal's gross edge is real on both cohorts and COST is what separates
them.** That is a mechanism, and the `cost_R` law plus the cohort comparison both
point the same way. The obvious repair is therefore an execution constraint: trade
only where the signal survives cost.

**But the diagnostic kills the naive version of that idea before it is built.**

`liq_overlap.py`, cohort composition of the most liquid slice of 515:

| top N by median quote volume | cohort A | A share |
|---|---:|---:|
| 12 | 7 | 58.3% |
| 50 | 26 | **52.0%** |
| 100 | 43 | 43.0% |
| 200 | 75 | 37.5% |
| 515 | 104 | 20.2% |

Cohort A's median liquidity rank is **114**; B/C are 206/214 and D/E 336/346.

**A liquidity filter on 515 is roughly half a survivorship filter.** It would
re-import exactly the bias the last round measured, declared unfixable, and
retracted the deployment verdict over. **Building it and reporting the headline
without the decomposition would be a way of getting the retracted +52.4% back
without saying so.** That is the specific failure this prereg exists to prevent.

**So the question is not "does a liquidity filter make money". It is: when it
does, is the non-survivor part of the book carrying it, or is the survivor part?**

## 1. Universes — a published ladder, never a selected cell

Rank all 515 by **median quote volume** (a market property, not a result) and
take the top N ∈ {50, 100, 200, 515}. `max_open_trades` pinned at 24.
**The whole ladder is reported. Picking a rung is forbidden.**

## 2. Signal — frozen, byte-identical to `PerpShort4hDeploy`

rvol(20) ≥ 2.0, 20-bar Donchian, low-vol filter, **4.0 × ATR stop at the entry
bar**, **2R target**, **42-bar time stop**, 1x, 1% risk, 24 slots, circuit
breaker, measured costs 12.0 / 22.8 / 34.9 bps. **Nothing varies but N.**

## 3. THE GATE — fixed now, and it is about decomposition, not the headline

| # | gate | threshold |
|---|---|---|
| **L0** | **replication** | the 515 cell reproduces `WIDENED_UNIVERSE_RESULT` exactly. If it does not, stop |
| **L1** | some rung is net-positive at measured_covid | mean R > 0 |
| **L2** | **THE DECISIVE ONE: within the chosen rung, the NON-cohort-A trades are themselves net-positive at measured_covid** | mean R(non-A) > 0. **If only the cohort-A portion is positive, the liquidity filter is a survivorship filter and the ladder is rejected regardless of its headline** |
| **L3** | the rung's cohort-A share is below **60%** | above that it is mostly a survivorship filter, whatever the P&L says |
| **L4** | ≥ 3 of 4 calendar years positive | |
| **L5** | mean R is monotone improving as N falls (the mechanism says it should be) | a non-monotone curve means cost is not the mechanism |

**L2 is the gate this design exists for, and it is a trap: the obvious reading
of any liquidity ladder is "the top rung made money", and that reading is exactly
what is not being asked.** The question is *which coins* made it.

## 4. What a pass would NOT mean

- **It would not remove survivorship bias.** The universe would still be "listed
  today". The delisted ~40% of Binance perps remain unobservable, and a
  liquidity filter makes the surviving bias *harder* to see, not smaller.
  **Every number remains an upper bound.**
- **It would not revalidate the edge.** Market-neutralised excess is still
  indistinguishable from zero, and the widened-universe result is not undone.
- **L5 being satisfied is a consistency check, not a discovery.**
- **This is an extension of the closed liquidity ladder, not a new hypothesis**,
  and it is legitimate only because the failure it addresses was *measured this
  session* and the diagnosis it is built on is a *cost* mechanism with two
  independent supports. A third sweep of the same parameter on the same data
  would be forbidden; this is one sweep on a **new universe**, with a
  **decomposition gate the old ladder did not have**.

## 5. Forbidden

- Quoting a single rung.
- Quoting a rung's headline without its cohort-A share AND its non-A mean R.
- Tuning anything because a rung performed badly.
- Calling a passing result "removing survivorship bias".
