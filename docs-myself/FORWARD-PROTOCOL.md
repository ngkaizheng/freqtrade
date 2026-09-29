# FORWARD VALIDATION PROTOCOL — PRE-REGISTERED

**Written:** 2026-09-19, before any forward observation beyond the single
founding record. **This file must not be edited to accommodate results.**

---

## Why this exists

Round 8 left the central question **unresolved**: whether SMA-50's window could
have been chosen in advance. Historical data cannot settle it, because the round-2
grid searched the entire 15-year series — **no period influenced no window choice**
(lesson L10).

A forward test with a **pre-committed** window is the only clean evidence
available. Not because more backtesting is bad, but because forward data is
independent of every past choice by construction.

This protocol exists so the result is judged by criteria fixed **now**, not by
criteria I invent once I see the outcome.

---

## Frozen specification (no changes permitted)

| item | value |
|---|---|
| asset | BTC/USD (Bitstamp) |
| rule | `Close > SMA(50)` → 100% exposure, else 50% |
| window | **50**, committed in advance, never searched |
| exposure band | 1.00 / 0.50 |
| timeframe | 1 daily candle, decision at candle close |
| cost assumption | 10 bps per rebalance |
| strategy file | `user_data/strategies/BTCSmaTrend.py` |
| config | `user_data/config_btcsma.json` |

**Any change to any row above invalidates the forward test** and restarts the
clock. This is the whole point: a pre-committed parameter is what makes forward
data clean.

---

## Two separate questions — do not conflate them

### Question A — IMPLEMENTATION (resolves in weeks)

> Does the deployed strategy behave exactly as the backtest says it should?

This is answerable quickly and is the primary near-term target.

| metric | expectation | source |
|---|---|---|
| signal parity | 100% match, every candle | `tools/forward_recorder.py` |
| exposure parity | actual within 0.25 units of target | same |
| rebalances per year | **~19** (NOT ~9 — that was turnover; lesson L8) | `tools/turnover_reconciliation.py` |
| cancelled-order rate | **0%** (was 24% before the guard fix) | `tools/dryrun_db_analysis.py` |
| realised cost | ≤ 10 bps per rebalance | recorded fills |
| restart state recovery | position correct after restart | manual + DB |

### Question B — STATISTICAL EDGE (does not resolve in any realistic window)

> Is the edge real?

**I must state this plainly: it cannot be settled here.**

Lo (2002): SE(annualised Sharpe) ≈ 1/√years. For the **paired** comparison used
here (rule vs matched flat), the requirement is **~10–20 years** (best estimate
~18y, including an autocorrelation variance inflation of 1.556).

*(Correction: earlier drafts of this protocol said "~271 years". That used the
formula for an ABSOLUTE Sharpe against zero, which is the wrong statistic for a
paired difference — see `findings-power-analysis.md`.)*

Therefore:

* **A profitable forward period does NOT confirm the edge.**
* **A losing forward period does NOT refute it.**
* Anyone (including me) who reads a few months of P&L as evidence is making
  exactly the error this project has documented six times.

What forward data **can** contribute to Question B is **mechanism persistence**
(see below), not a Sharpe estimate.

---

## Criterion 1 — IMPLEMENTATION FAILURE (hard, fast)

The strategy is judged **IMPLEMENTATION-INVALID** if **any** of:

| # | condition | checked by |
|---|---|---|
| 1a | signal parity mismatch on any candle | `forward_recorder` |
| 1b | exposure parity outside 0.25 units while an order is not pending | same |
| 1c | cancelled-order rate > 5% of orders | `dryrun_db_analysis` |
| 1d | realised cost > 2× the 10 bps assumption | fills |
| 1e | rebalance count outside 10–35/year (expected ~19) | recorder report |
| 1f | position incorrect after a restart | manual + DB |
| 1g | any duplicate order for the same rebalance | DB |

These are **diagnostic**, not statistical. They resolve in weeks. A failure here
means the *implementation* is wrong, not the idea — fix and restart the clock.

## Criterion 2 — MECHANISM FAILURE (medium)

The historical claim is that **crypto trends** — VR(20) ≈ 1.19 — and that this is
*why* the rule works, versus equities where VR(20) ≈ 0.84 and the rule fails 0/4
out-of-domain.

**Mechanism is contradicted** if forward VR(20) falls **below 1.0** on a
meaningful sample.

This is the one Question-B-adjacent claim that forward data CAN address, because
VR is a property of the return process rather than of the strategy. It is also
falsifiable in a way a Sharpe estimate is not.

Caveat: VR(20) on a short window is itself noisy. This criterion needs
**≥ 6 months** before it means anything, and a crossing must be **sustained**,
not a single reading.

## Criterion 3 — WHAT DOES *NOT* CONSTITUTE FAILURE

Explicitly, none of these invalidate the strategy:

* a losing month, quarter, or even year
* drawdown worse than the historical average drawdown
* Sharpe below the historical 1.45
* underperformance versus buy & hold over a short window

Crypto at ~75% annualised vol produces large swings routinely; 2022 saw −84%.
Reading any of the above as refutation is the error this protocol exists to
prevent.

---

## Success criteria — deliberately weak, because they must be honest

**Implementation pass** (achievable now):

* all of Criterion 1 satisfied over **≥ 90 days** and **≥ 4 rebalances**
  (4 rebalances at ~19/year is the minimum needed to observe the mechanism at all)
* Criterion 2 not triggered

**Evidence of durable edge: NOT CLAIMED.** Even a full year of clean forward data
would leave SE(Sharpe) ≈ 1.0. The honest deliverable is:

> "The implementation is faithful and the mechanism has not been contradicted."

That is a real result and it is the most this test can produce.

---

## Prohibited actions during the forward period

1. **No window changes** — not 30, not 60, not 100. Ever.
2. **No threshold or confirmation changes.**
3. **No adding indicators** to "improve" it while it runs.
4. **No stopping early because it is winning** (that is selection on the outcome).
5. **No stopping early because it is losing** unless Criterion 1 or 2 fires.
6. **No new strategy substituted in** on the basis of interim results.

If I want a new idea, it goes to the backlog and is tested separately, without
touching this record.

---

## Review cadence

| checkpoint | what is assessed |
|---|---|
| **daily** | `python tools/forward_recorder.py` — parity row appended |
| **weekly** | `--report`; Criterion 1 checks; turnover trajectory |
| **90 days** | first substantive review: Criterion 1 verdict, ≥4 rebalances expected |
| **180 days** | Criterion 2 (VR) becomes readable |
| **365 days** | full review; decision on whether to continue or close |

---

## What would change my mind

The honest failure modes, stated in advance:

1. **Parity mismatch** → implementation bug; find and fix it.
2. **Realised cost ≫ 10 bps** → the backtest economics were wrong; re-evaluate
   the whole edge, since cost sensitivity was a core assumption.
3. **Rebalance count far from ~19/year** → cadence differs live; the backtest
   misrepresents execution.
4. **Sustained VR(20) < 1** → the mechanism story is contradicted, and the
   strategy loses its only causal justification.
5. **Nothing at all** → also a valid outcome: the implementation is faithful and
   no conclusion about the edge is possible on this horizon. That is reported as
   such, not dressed up as either success or failure.

---

## Status log

| date | observation | note |
|---|---|---|
| 2026-09-19 | protocol written | 1 founding record; 90-day checkpoint ~2026-12-18 |

*Append entries only. Do not edit prior rows.*
