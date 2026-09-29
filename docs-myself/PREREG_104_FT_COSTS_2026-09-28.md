# PRE-REGISTRATION — the 104-perp panel inside freqtrade, with costs

**Date frozen:** 2026-09-28, **before the 104-symbol freqtrade run produced any
number.**
**Supersedes nothing.** This is the cross-engine validation
(`PREREG_WIDE_PANEL_2026-09-27.md` §7) done properly: that file asked for the
frozen rule on "a held-out subset of the same symbols", and §7 was satisfied on
24 symbols. This runs the **full frozen 104** through `freqtrade backtesting`
and applies the repo's **measured** costs, which the shark engine's flat-bps
assumption could not.

---

## 0. Why the 24-symbol run cannot settle it, and what this run can

The 24-symbol liquid-major subset was run first (`tools/perp_short/r_stats.py`).
Its result, recorded here so it cannot be quietly dropped:

| cost regime | mean R | t naive | t by-timestamp | t by-week |
|---|---:|---:|---:|---:|
| engine default (5bps, no slippage) | +0.187 | 1.28 | 0.50 | 1.26 |
| measured calm (+12.0 bps) | +0.106 | 0.92 | 0.09 | 0.92 |
| measured volatile (+22.8 bps) | +0.070 | 0.60 | **−0.27** | 0.60 |
| measured COVID (+34.9 bps) | +0.028 | 0.24 | **−0.67** | 0.24 |

**G1 fails in every cell.** But this is **not** a refutation of the panel claim.
The panel was 104 symbols including the long tail; this is the 24 majors. The
repo has already learned this lesson once — the `funding_high` cell cleared
t_adj 2.4059 on the 104-symbol panel and then **failed to cross-validate on the
same 24 symbols** (t_adj 1.22, and the control was *better*). Both directions of
that lesson are registered here: **a subset cannot confirm a panel, and cannot
refute one either.**

## 1. Universe — unchanged, 104 symbols

Exactly `PREREG_WIDE_PANEL_2026-09-27.md` §1: Binance USD-M USDT perps with
`onboardDate <= 2023-01-01` and status TRADING at download time, minus
`BTCDOMUSDT`. **No widening.** Widening the universe after seeing that a
narrower one missed significance is precisely the multiple-testing error this
apparatus exists to detect, and the panel document's own §6 forbids it.

## 2. Signal — unchanged, frozen

`PerpShort4h` implements the frozen rule: rvol(20) >= 2.0, 20-bar Donchian
breakdown, low-volatility regime filter, stop 1.5 x ATR **at the entry bar**,
target 2R, time stop 42 bars. **No parameter change. No timeframe change.**

### The one change from the cross-validation reference, and why it is a FIX

`ShortBreakout4h` resolved the entry-bar ATR with a fallback to
`df["atr"].iloc[0]` — the **oldest** bar. On the entry candle the analysed frame
has not yet been extended to the entry bar, so the lookup misses and the
fallback fires, returning an ATR from months earlier. Measured on BTC
2023-12-25: 304.28 returned against a true 484.94. The stop was then set at
+456.43 instead of +727.41, and because freqtrade only ever **tightens** a stop
(`trade_model.py:886-893`, "stop losses only walk up, never down"), the
too-tight stop could never be undone.

This is a **bug fix, not a tuning knob**: the frozen rule says 1.5 x ATR at
entry, and the old code did not compute that. Both the old and the new code are
kept and both are run, so the effect is measured rather than asserted.

## 3. Costs — per-symbol where it matters, and disclosed

1. **Fees** 0.05%/side (Binance USD-M taker), inside every R.
2. **Slippage**: the engine has **none** (`docs/backtesting.md:562`). Applied in
   post-processing from the export, as a full round trip split across the two
   legs, at the §1b **measured** values: 12.0 (calm), 15.6 (cascade), 22.8
   (volatile), 34.9 (COVID) bps.
3. **Funding**: charged by freqtrade itself from the real per-symbol history
   taken from the export, not re-modelled.
4. ⚠ **Mark price is APPROXIMATED** by resampling each symbol's 4h klines to 1h.
   This is safe **at 1x only**: the mark price feeds the *liquidation* price,
   and at 1x liquidation sits ~100% away while the stop is ~3.6% away, so the
   trade is always closed by the stop long before liquidation. **Any run at
   leverage > 1x must not use this data** — there the mark price is load-bearing
   and an approximation would fabricate a liquidation.

## 4. The gate — fixed now, before the run

Statistic: **dependence-adjusted t on per-trade net R**, with the integrated
autocorrelation time reported beside it. Three treatments, all pre-registered,
all reported, no choosing between them afterwards:

| treatment | what it is | why it exists |
|---|---|---|
| naive | t over all trades | the number a naive backtest implies |
| **by-timestamp** | average trades sharing an `open_date`, t over timestamps | the panel used this; 72% of trades share a timestamp and the cross-sectional mean has **beta = 1.000**, so 20 simultaneous shorts are not 20 votes |
| by-week | weekly summed R | coarsest, most conservative |

**PASS requires ALL of:**

| # | gate | threshold |
|---|---|---|
| G1 | dependence-adjusted t on net R >= 2.0, at **measured_covid** (34.9 bps) | the cost the engine cannot avoid |
| G1b | the same at measured_calm | an edge that needs the calm regime is a regime bet, not an edge |
| G2 | mean R > 0 at measured_covid | |
| G3 | per-symbol consistency: >= 50% of symbols individually net-positive | the gate §3.3 said was missing when a survivor was "three symbols out-earning a fourth" |
| G4 | drop the single best symbol, mean R still > 0 | the aggregate must not be carried by one name |
| G5 | same sign in >= 3 of 4 chronological splits (2023 / 2024 / 2025 / 2026) | |
| G6 | the ATR-stop fix does not REVERSE the sign vs the reference implementation | a fix that helps one regime and wrecks another is a bug, not a fix |

**Falsification.** If G1 or G1b or G2 fails, the line is **closed** and reported
plainly. The shark panel's t_adj 1.8746 is the prior; this run either reproduces
it (cross-engine confirmation) or does not (and the honest reading is that a
2-significant-digit shortfall is not a robust edge).

## 5. Forbidden

- Widening or narrowing the universe after this document is frozen.
- Choosing among the three dependence treatments, or quoting only the one that
  reaches 2.0. **All three are reported.**
- Quoting `engine_default` (no slippage) as a headline. It is shown once, as the
  engine's own left edge, and never as a result.
- Any parameter change in response to the outcome.
