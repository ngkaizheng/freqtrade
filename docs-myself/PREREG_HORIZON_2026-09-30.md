# PREREG — H-1: THE COARSER-HORIZON AXIS, WHICH HAS NEVER BEEN BACKTESTED

**Written:** 2026-09-30, before any 12h/1d bar was built and before any backtest was run.
**Motivation:** §40 measured the horizon cost law for the first time, and §39 corrected it.

---

## 1. The gap this closes, stated honestly

`HOW_TO_RUN_2026-09-29.md` has a reader-facing row:

> **换周期有用吗 → 没用。** 4h / 12h / 1d / 3d / 1w 的相关分别是 +0.560 / +0.553 / …，有效下注数 2.9 / 2.9 / 3.0 / 3.0 / 3.1

**Those numbers are the FACTOR STRUCTURE (`horizon_factor.py`), not this strategy's P&L.**
The strategy has never been backtested at 12h, 1d, 3d or 1w. **A reader reasonably reads
that row as "we tried it and it didn't work". We did not try it.** The row is not false —
the measurement it cites is real — but it does not answer the question it appears to answer,
and that is being fixed rather than left.

## 2. Why this is a REOPENING and not a dead fruit

§5b forbids "re-running a closed line with different parameters, timeframes or symbols
hoping for a better number". Three conditions are met for a legitimate reopening:

1. **It was never actually run.** A closed line requires a measurement. There is none.
2. **A new reason, measured after the horizon was waved off.** §40 measured the cost law:
   `cost_R` falls monotonically as the horizon coarsens — **4h 0.0106 · 1h 0.0223 · 5m
   0.0806** (calm). §39 then corrected the 1h/4h figure. **The cost side of the trade is
   now measured rather than guessed, and it points at a horizon nobody tested.**
3. **The mechanism is a specific, falsifiable quantity, not a hope.**
   `net R per trade = gross R − cost R`. At a coarser horizon the risk unit (4×ATR) is
   wider, so **both terms shrink**. Which one shrinks faster is an empirical question with
   a number attached, and it decides the axis.

## 3. THE CONFOUND, DECLARED BEFORE THE RUN

**Changing the timeframe necessarily changes what the lookbacks MEAN.** The frozen signal
uses a 20-bar Donchian, a 20-bar relative-volume window and a **365-bar** low-volatility
median. At 4h, 365 bars ≈ **61 days**. At 1d, 365 bars ≈ **365 days**. At 12h, 365 bars
≈ **182 days**.

> **This experiment therefore tests "the same strategy on a coarser clock", NOT "the same
> strategy with the same lookback expressed in time".** Anyone quoting a 1d result as
> evidence about 4h-with-a-60-day-lookback is misreading it. `AGG_LESSONS.md` L3 — two
> variables changed at once — is invoked deliberately and named here rather than discovered
> afterwards.

A second consequence: `startup_candle_count` must be raised at coarse horizons or the
indicator window is truncated at the left edge and the early bars are computed on a
shorter history than the later ones. The count is set to **the largest lookback used**, and
any symbol whose available history is shorter than that is **reported, not silently dropped**.

## 4. Pre-registered decisions

**H0 — REPRODUCTION GATE, run first and decisive.** The **4h arm must reproduce the deployed
book's engine total to within 0.05 pp** (113.70 % at 10,000). Freqtrade is run unchanged,
same config, same data directory.
> **If the 4h arm does not reproduce, no coarser arm may be read.** This is the gate that
> `cost_reprice.py` already enforces for cost, applied to the pipeline itself.

**H1 — the decision quantity.** For each horizon, using the same per-trade R unit
(`stake × 4 × ATR(entry)/entry`, `risk_unit.py`) and the same regime costs
(12.0 / 34.9 bps round trip):

| quantity | what decides it |
|---|---|
| **gross R per trade** | falls as the clock coarsens (wider risk unit) |
| **cost R per trade** | falls too, by the measured cost law |
| **net R per trade** | **the ratio. If cost falls faster, the axis opens.** |
| trades, total return at COVID cost, maxDD | the deployment question |

**H2 — the honest null.** §15c-3 measured the factor structure at 12h/1d/3d/1w and it is
one factor at every horizon, so **a coarser book will not become alpha.** If net R per
trade is flat or worse, the axis closes and the answer to `HOW_TO_RUN` becomes *measured*
rather than *inferred*.

**H3 — market-neutralised excess at each horizon**, by regression on the equal-weight
factor, using the machinery `xsect_screen.py` already has. This is reported because the
user's objective is cash return, but **alpha and cash return are different claims** and the
page must not conflate them.

**H4 — publication rule.** **The full curve is published, every horizon, whatever it says.**
No cell is selected after the fact, and if one horizon wins it is reported as one point on
a curve, not as the answer.

**H5 — KILL / STOP RULE.** At most **three** coarser arms (12h, 1d, 3d). If none beats
4h on net R per trade, **the axis is closed and not revisited** — a further sweep would be
§5b's dead fruit, not research.

## 5. What this does NOT authorise

* **It does not change the deployed book** unless a coarser arm wins on H1 *and* survives
  H0. The deployed 4h book stays until then.
* **It does not re-open the signal.** The entry logic is frozen; only the clock moves.
* **It is not a search over parameters.** Three arms, fixed in advance, curve published.

## 6. What would make me wrong

* Net R per trade could fall faster than cost R at coarse horizons, closing the axis — the
  likely outcome, and a valid result.
* The 365-bar lookback confound could make a coarse arm look bad for a reason that has
  nothing to do with the clock. **The confound is why H2's null is stated as "not alpha"
  rather than "not profitable"** — a coarse arm that merely fails is not evidence that a
  time-consistent coarse version would fail.
* The 3d arm may be dominated by the sample's single bull year (2023, +8.3 % at 4h), which
  at 3d is ~120 bars of history. **Reported, not smoothed over.**
