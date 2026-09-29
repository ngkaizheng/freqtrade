# PRE-REGISTRATION — the cost-admissible universe: a liquidity ladder, published whole

**Date frozen:** 2026-09-28, **before the ladder rungs are run.**
**Supersedes nothing.** `PREREG_104_FT_COSTS_2026-09-28.md` is unchanged; this is
a *different question* asked of the same frozen signal.

---

## 0. The observation, and the trap it carries

The frozen 4h short rule, same strategy code, same data source, measured cost:

| universe | @ measured_calm | @ measured_covid | pairs net-positive |
|---|---:|---:|---:|
| **24 liquid majors** | +75.0% | **+23.7%** | 62% |
| **104 perps (full panel)** | +36.4% | **−22.4%** | 42% |

The signal is identical. The only thing that changed is **which contracts were
allowed to be traded**, and the gap is entirely in the long tail.

`RESEARCH_STATE.md` §1b already measured why: Binance `bookDepth` shows the long
tail is **1–3 orders of magnitude thinner** than BTC (NEO $10.4k resting within
0.2% on a calm day vs BTC $43.3M), and §1c's law

```
cost_R = round_trip_bps / (stop_multiple x atr_pct x 1e4)
```

means a thin contract pays the **same bps** for a **wider stop**, so its cost in
units of risk is several times higher. The panel's gross edge is ~0.12–0.18R. At
12 bps the majors pay 0.03–0.09R. The long tail pays more than that.

> **⚠ THE TRAP, STATED BEFORE RUNNING.** The 24-symbol result was **already in
> hand** when this design was written, and it is the one rung that looks good.
> That makes "test liquidity rungs" a **post-hoc** design whose favourable end is
> already known. Three things are done about it, and they are the only things
> that can be done:
>
> 1. **The whole ladder is published.** Not the best rung.
> 2. **The rung is defined by a RANK on a measured liquidity proxy**, not by
>    whether that rung's P&L looked good.
> 3. **A pass here is a LEAD, never a confirmation.** See §5.
>
> The reason to run it at all is that the *mechanism* is measured independently
> of any backtest (§1b's depth data), and the deployable question — **"which of
> today's listed perps can be traded at a cost that leaves an edge?"** — has
> never been asked with a pre-registered answer.

## 1. Universe rule — frozen, mechanical, and not a P&L filter

Rank all 104 panel symbols by **median daily quote volume** over the panel
window, and take the top N. Quote volume is a property of the market, not of the
strategy's return, so this is a cost proxy, not a selection on outcome.

**Ladder: N ∈ {12, 24, 50, 104}.** All four rungs, same data, same code, same
costs, same 1x sizing. `max_open_trades` is **pinned per rung** so concurrency
never changes with the universe — `optimize_reports.py:577` silently applies
`min(max_open_trades, len(pairlist))`, and letting that float would make the
rungs differ in two ways at once.

**Not permitted:** dropping a symbol because its trades lost, re-weighting after
seeing results, or adding a symbol the panel rule did not admit.

## 2. Signal — frozen, unchanged

`PerpShort4h`: rvol(20) ≥ 2.0, 20-bar Donchian breakdown, low-volatility regime
filter (42 vs 365-bar median), stop **1.5 × ATR at the entry bar**, target 2R,
time stop 42 bars. **No parameter change.** The target-R question is closed
(`PERP_SHORT_4H_RESULT_2026-09-28.md` §5.1: with no profit target at all the
mean R is still −0.0065).

## 3. Costs — unchanged, still the measured ones

Fees 0.05%/side; slippage from `RESEARCH_STATE.md` §1b at 12.0 / 22.8 / 34.9 bps
round trip; funding charged by freqtrade from real per-symbol history.
**The engine's own no-slippage number is shown once, as its left edge, and is
never a headline.**

## 4. The gate — fixed now

| # | gate | threshold |
|---|---|---|
| L1 | the ladder is **monotone in the right direction** (cost per R rises as the universe widens) | a flat or noisy ladder means liquidity is not the mechanism, and the hypothesis is dead |
| L2 | at the smallest rung that clears G1's bar, dependence-adjusted t on net R @ measured_covid | **≥ 2.0** — the same bar, undeflated |
| L3 | mean R > 0 @ measured_covid at that rung | |
| L4 | ≥ 50% of that rung's symbols individually net-positive | |
| L5 | positive in ≥ 3 of 4 calendar years at that rung | |
| L6 | the rung is also positive at `measured_calm` | |

## 5. What this file does NOT license — read before believing a rung

- **A winning rung does not confirm the strategy.** The favourable end of this
  ladder was known before the design was written. Every rung is in-sample.
- **It does not reopen the 104-symbol failure.** If only the thin tail fails,
  the honest statement is *"the signal does not pay for the tail's spread"*,
  **not** *"the strategy works"**.
- **A liquidity filter is an EXECUTION constraint, not an edge.** It is
  published here as a statement about **how large a book this can carry**, which
  §1b caps separately at **$0.8M/day (0.2% band) to $3.9M/day (1% band)** for the
  thin side — and the ladder is a *proxy* for that, not a substitute for it.
- **The whole curve is the deliverable.** A single rung quoted alone is a
  maximum-over-4 selection and is forbidden.

## 6. Forbidden

- Quoting one rung.
- Changing the liquidity proxy, the rungs, or the ranking metric after the fact.
- Re-running with a different `max_open_trades` per rung than the one pinned here.
- Any hyperopt.
