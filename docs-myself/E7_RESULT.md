# E#7 — time-series momentum at its canonical horizon, net long: **FAIL, 1/7**

**Date:** 2026-09-26
**Pre-registration:** `PREREGISTRATION_E7.md` · **Engine:** `e7_timeseries.py`

## Why this experiment was run at all

The stated objective is "make money in a bull market". E#6 established that a
dollar-neutral cross-sectional book cannot serve it: capture **0.39** of the
upside in +105.7% years and **1.13** of the downside in −12.2% years. That is
a property of the construction, not of the signal.

Serving the objective needs a **net long** position whose edge is the market's
**direction**. The canonical construction for that is time-series momentum
(Moskowitz, Ooi & Pedersen, JFE 2012, 1–12 month horizon).

**Every backtest in this repository had been at 5m, 1h or 4h. Daily, weekly and
monthly had never been run.** The project's own notes recorded the reason and
never acted on it: *"classic time-series momentum spans 1–12 months, so the
prior for a 4h edge is lower."*

## Result — primary, pre-committed: long/cash, 126-day lookback

| measure | value | gate |
|---|---:|---|
| net CAGR | **−2.21%** | **FAIL** |
| annualised | +24.6% | |
| Sharpe | +0.33 | **FAIL** (needs 0.75) |
| Newey-West t | +0.65 | **FAIL** (needs 2.0) |
| max drawdown | −84.5% | **FAIL** (buy-and-hold is −79.8%) |
| **bull capture, 2023–24** | **15%** | **FAIL** (needs 50%) |
| **2022 loss vs holding** | **0.96×** | **FAIL** (needs ≥1.0) |
| rebase names in book | 0 | pass |

**VERDICT: FAIL, 1/7.** Neither the 63-day nor the 252-day lookback clears
the bar either (63d: Sharpe 0.79, t 1.54, max DD −72.7%, but 2024 was −19.6%
against buy-and-hold's +111.4%).

## The finding that answers the question behind it

**The bull-market profit is not the missing thing. It is already free.**

| | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|---:|---:|
| **buy-and-hold** | +10.2% | +39.6% | **−70.5%** | **+106.2%** | **+111.4%** | −6.4% | −10.9% |
| E#7 long/cash 126d | — | +343% | −67.8% | +25.9% | +6.8% | −39.8% | −23.5% |

Buy-and-hold captures the entire bull and loses it all in the bear. CAGR +7.90%
with a **−79.8%** drawdown.

> **The problem this project actually has is not "make money in a bull market".
> It is "stop losing 70% when the market turns".** The bull is solved by
> holding.

And the two canonical answers to *that* have now both been tested here and both
failed:

- **Cross-sectional momentum (E#6):** capture 0.39 up, 1.13 down. Wrong shape.
- **Time-series momentum (E#7):** capture 0.15 up, **0.96 in the bear** — it
  lost essentially exactly as much as simply holding through 2022.

**Trend following did not protect the 2022 drawdown on this venue.** That is
the single most important negative here, because it is the standard remedy and
this is, to the project's knowledge, the first time it has been tested on these
instruments at its own horizon.

## What has NOT been tested for this specific problem

Direction prediction is the wrong tool. The bear is a **volatility** regime, and
a net-long book does not need to predict it to survive it — it needs to *size*
down into it. **Volatility targeting on a long position** (scale exposure by
inverse realised volatility, with no directional signal at all) is untested in
this repository, is the cheapest experiment remaining, and attacks the actual
failure mode rather than a proxy for it.

That is a reprioritisation of the goal, not a new hypothesis family, and it
would need its own pre-registration.

## Caveats, stated before the result is believed

- One universe (50 liquid names), one construction, three lookbacks, one cost
  snapshot. The cost model has no impact term.
- 6.6 years contains roughly 12–18 independent monthly holding periods. Enough
  to detect a large effect, not to characterise a small one.
- McLean & Pontiff's 58% post-publication decline applies, and is larger for
  stronger in-sample signals.
- The 63-day variant came closest (Sharpe 0.79, t 1.54) and still failed; it is
  reported here rather than promoted, and the primary was fixed in advance.

## The bug this experiment produced on its first run

The first run reported **+1945% CAGR with a −0.02% drawdown**, then **+1021%
for 2021** when the weights were fixed. Two faults:

1. Weights were built from the **return** series (`longs / len(longs)`) and then
   multiplied by the return again — a sum of squared returns.
2. The holding window was a fixed 22 days while rebalancing monthly, so
   consecutive windows **overlapped** and every year was triple-counted.

Both were caught because the numbers were impossible, not because the code
flagged them. **This is the fifth time in this project that an implausible
number has turned out to be a bug rather than a discovery.**
