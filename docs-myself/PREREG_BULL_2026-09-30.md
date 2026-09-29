# PREREG — B-1: THE BULL-MARKET BOOK

**Written:** 2026-09-30, before any bull-market backtest was run.
**Strategy:** `user_data/strategies/PerpLong4h.py`. **Tool:** the freqtrade CLI, as always.

---

## 1. The objective, and the two things that are already closed

The delivered book is short-only and its whole weakness is bull markets. The objective is a
**complement**: a book that profits when the market rises.

**Two long variants of the delivered signal are already measured and already closed, and
this preregistration does not pretend otherwise:**

* `PerpShort4h.py:239-242`, in the source: *"SHORT ONLY. The long leg is net-negative in all
  12 cells of the wide panel and all 3 cost regimes (WIDE_PANEL_RESULT.md §3)."*
* `PerpShort4hSwitch` added a regime-switched long leg and produced **−44.5 % in 2023** —
  the year the panel rose **+198.6 %** — worse than the bleed it was built to fix.

**So "flip the side" is a closed question.** What is NOT closed is whether a long book on the
deployed universe is viable *at all* once it carries the delivered risk architecture.

## 2. Gate 0 was run first: the regime calendar (`regime_calendar.py`)

| year | panel, equal-weight long |
|---|---:|
| **2023** | **+198.6 %** |
| **2024** | **+103.6 %** |
| 2025 | −56.8 % |
| 2026 (to Aug 31) | −17.6 % |

**2 of 4 years up; 8 of 15 quarters up. Panel peak-to-trough −80.4 %; 4-year buy-and-hold
+116.5 %; the panel made money on 51.7 % of 4h bars.**

> **The experiment CAN conclude.** Two up years and eight up quarters is enough to tell a
> book that profits in up regimes from one that does not, **provided the verdict is judged
> on the up regimes alone and the down regimes are published beside it.**

**The bar is fixed before any strategy is written, and it is not a bar this project chose:**

> **A bull-market book must be net-positive in the UP regimes after the measured round trip
> (12–35 bps), and its worst drawdown must beat buy-and-hold's −80.4 %.** The panel's
> median up year is **+151.1 %**; a book that returns +12 % in 2023 has *failed* even though
> it "made money", because the user could have held the coins.

## 3. The arms, all in one pre-registered set

| arm | `side` | what it is | why it is here |
|---|---|---|---|
| **B0** | `off` | **CONTROL** — the delivered short book | **must reproduce 113.74 % exactly** |
| **B1** | `long` | long mirror of the frozen breakout | measures the long leg *on the deployed universe*, which the 12-cell null did not |
| **B2** | `panel` | long the market above its own 365-bar extreme | the simplest possible bull-market book |
| B1c / B2c | as above, `breaker_max_dd` = 0.35 | the same with the breaker nearly off | **the breaker is the untested part** |

**B0 is the gate.** If the control does not reproduce the deployed book to 0.05 pp, no other
arm may be read — the harness is wrong, not the strategy.

**Everything else is inherited and must not vary:** N=40 liquidity-ordered, `risk_per_trade`
0.005, `atr_stop` 4.0, 4h, 24 slots, 1× leverage, same dates. **Only `side` and
`breaker_max_dd` change.**

## 4. The breaker, stated as the thing actually under test

`PerpShort4hDeploy` **ships with a drawdown circuit breaker at `breaker_max_dd` and the
project has never measured what it does on either side.** It is in the delivered file. The
long book is the regime where it should matter most, because the panel pays an **−80.4 %**
round trip.

> **So B1c/B2c are not "another arm". They are the measurement of a component that is
> already in production and unmeasured.** If the breaker does nothing, that is a finding
> about the delivered book and it is published here.

## 5. Pre-registered decisions

**B0** control reproduces 113.74 % → otherwise the run is void.
**B1** net-positive in the up regimes after cost? and does it beat buy-and-hold's
+151.1 % median up year, or merely clear zero?
**B2** same, for the simplest possible bull-market book.
**BC** breaker on vs off, at 0.20 and 0.35, on whichever long arm is alive.
**BD — PUBLICATION RULE.** **The full grid is published whatever it says.** No cell is chosen
after the fact. If one arm wins it is reported as one point on a curve, together with the
regime it won in — and §41's rule applies: *a coarse arm that only worked in one regime is
one data point, not a result.*

**BE — KILL.** If B1 and B2 both fail the up-regime test, **the "long breakout or long
buy-and-hold on this universe" family is closed**, and the next round must go to a
different mechanism rather than re-tune these.

## 6. What this does NOT do

* **It does not touch the delivered book.** `PerpShort4hDeploy` and
  `config_perp_forward_dry.json` are not modified. This is a new file and new configs.
* **It does not claim a bull book exists.** Two arms on one universe is a Gate 0 for a
  family, not a search.
* **It does not reopen anything closed by measurement.** The 12-cell long-leg null and the
  switch's −44.5 % in 2023 stand, and are the reason B1 exists only on the *deployed*
  universe rather than the wide panel.
