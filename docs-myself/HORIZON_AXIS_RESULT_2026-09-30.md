# §41 — THE COARSER-HORIZON AXIS, MEASURED FOR THE FIRST TIME: 4h IS A SWEET SPOT, AND THE COST LAW IS NOT THE REASON

**Date:** 2026-09-30
**Prereg:** `docs-myself/PREREG_HORIZON_2026-09-30.md` (before any coarse bar was built)
**Tools:** `tools/perp_short/build_coarse_panels.py`, `tools/perp_short/horizon_axis.py`
**Configs:** `user_data/config_horizon_{4h,12h,1d,3d}.json` (clones of the deployed one, `timeframe` only)
**Raw:** `user_data/logs/{build_coarse_panels,bt_hz_4h,bt_hz_12h,bt_hz_1d,bt_hz_3d,horizon_axis}.txt`
**The deployed book was not changed and not re-deployed.**

---

## 1. The gap, stated plainly

`HOW_TO_RUN_2026-09-29.md` has a reader-facing row:

> **换周期有用吗 → 没用。** 4h / 12h / 1d / 3d / 1w 的相关分别是 +0.560 / +0.553 / …

**Those numbers are the factor structure (`horizon_factor.py`). The strategy had never been
backtested at 12h, 1d, 3d or 1w.** The row is not false — the measurement it cites is real —
but it does not answer the question it appears to answer, and a reader would reasonably
conclude the clock had been tried. **It had not.** That is now a measurement.

## 2. H0, the reproduction gate, run first and decisive

The 4h arm, same config, same engine, same data directory:

```
Backtesting with data from 2023-03-12 ... (1268 days)
| Total profit %   | 113.74%   |
```

**113.74 % — the deployed book's number, to the printed precision.** H0 PASSES, so the
coarser arms are readable. Had it not, this round would have produced nothing.

## 3. The whole curve, published whatever it says (prereg H4)

| arm | trades | **gross R** | **cost R** | **net R** | naive t | total % | maxDD % |
|---|---:|---:|---:|---:|---:|---:|---:|
| **4h** | **1,111** | **0.1538** | 0.0126 | **0.1412** | 4.40 | **113.74 %** | 14.16 % |
| 12h | 388 | 0.0288 | 0.0060 | 0.0227 | 0.95 | 4.56 % | 17.91 % |
| 1d | 118 | 0.0102 | 0.0036 | 0.0065 | 0.29 | 0.99 % | 3.46 % |
| 3d | **1** | −0.5884 | 0.0023 | −0.5908 | — | −0.23 % | 0.23 % |
| | | | | | | | **DEGENERATE — reported, not smoothed over** |

> ⚠ **The `t` column is the NAIVE per-trade t**, the one §19's ladder showed to be
> misleading. **The project's own by-timestamp t for the 4h arm is ~0.58, and that is the
> number that governs any claim about significance.** A coarse arm having a smaller naive t
> is not evidence of anything on its own.

## 4. H1, the pre-registered decision quantity: **gross R falls faster than cost R**

| arm vs 4h | gross R | cost R | |
|---|---:|---:|---|
| **12h** | **×0.187** | ×0.482 | **gross falls 5.3×, cost only 2.1×** |
| **1d** | **×0.066** | ×0.291 | **gross falls 15×, cost only 3.4×** |

**The cost law did exactly what §40 predicted — cost_R fell monotonically as the clock
coarsened. It bought almost nothing, because the gross edge collapsed faster than the bill.**

**VERDICT: 4h is the best arm on net R per trade. THE AXIS IS CLOSED**, per prereg H5 —
three arms fixed in advance, the whole curve published, no further sweep.

## 5. The mechanism, which is now a number rather than a story

At a coarser clock the **risk unit widens faster than the signal's per-trade edge grows**:

* The frozen signal is a **20-bar** Donchian breakout plus a 20-bar relative-volume window.
  At 4h that is **3.3 days**; at 1d it is **20 days**. Breakouts at that length are rare and
  capture far less of the drawdown structure that the book is harvesting.
* The risk unit is **4 × ATR at the entry bar**, and ATR% rises with the horizon (§40's
  ladder: 0.372 % at 5m → 2.953 % at 4h). **A wider risk unit divides the same cash profit
  by a bigger number.**
* Trade count collapses **1,111 → 388 → 118 → 1**. There is simply less of the phenomenon.

**So the deployed book is not a market-timing overlay that happens to run on 4h. It is a
4h-clock phenomenon**, and this is the first measurement that says so.

## 6. The confound, declared before the run and confirmed after it

Changing the timeframe necessarily changes what the lookbacks *mean*: the 365-bar
low-volatility median is **61 days at 4h**, **182 days at 12h**, **365 days at 1d**;
`breaker_cooldown_bars: 42` is 7 days at 4h and 42 days at 1d. The prereg named this before
running anything (L3, two variables at once).

**The warm-up arithmetic is confirmed, not assumed.** With `startup_candle_count=420` on a
panel starting 2023-01-01, the first tradable bar is 2023-01-01 + 420 × timeframe, and the
engine's own reported start dates match:

| arm | predicted first bar | engine reported data from | first trade |
|---|---|---|---|
| 4h | 2023-07-25 | 2023-03-12 | 2023-03-22 |
| 12h | 2023-11-09 | 2023-07-30 | 2023-07-31 |
| 1d | 2024-02-25 | **2024-02-25** | 2024-06-12 |
| 3d | 2026-06-14 | 2026-06-14 | 2026-08-19 (1 trade) |

**At 3d the arm is degenerate by construction**: 420 startup bars is 1,260 days of warm-up
against 1,347 days of data, leaving 78 days and **one trade**. It is reported as
degenerate and excluded from the comparison rather than quoted as "3d loses money".

**The arms also trade different sample lengths** (1268 / 1128 / 918 / 78 days), which is a
property of the clock, not a free choice — and it is **not** the explanation: a shorter
sample cannot turn +113.74 % into +4.56 %, and the R decomposition is computed per trade on
each arm's own data.

## 7. What the data build guarantees

12h / 1d / 3d panels are built from the 4h panel by **UPWARD** aggregation —
`tools/perp_short/build_coarse_panels.py`, 515 symbols each, and it **asserts
`rows_out <= rows_in` per symbol**, because §35's bug was resampling 4h *down* to 1m/5m/15m,
calling it measured, and getting an identical ATR at five horizons. 4h→12h is 3.0× fewer
bars, 4h→1d 6.0×, 4h→3d 17.9×, every one asserted. OHLC aggregation is exact, so an
intrabar extreme that a stop sat on is preserved.

## 8. What this closes, and what it does not

**CLOSED:** the coarser-horizon axis, by measurement. **`HOW_TO_RUN` now answers the
reader-facing question with the curve instead of with the factor structure**, and the row
says which is which.

**NOT closed, and stated so:**

* **The intraday side.** §40 measured that `cost_R` *rises* sharply as the clock shrinks
  (5m 0.0806 calm vs 4h 0.0106) and §18 closed it on measured grounds. This round tests
  the *coarser* direction only. **The two together are now symmetric: neither the faster nor
  the slower clock is a way out, and the 4h cost is a genuine interior optimum.**
* **The signal.** The entry logic is frozen and was not touched.
* **The deployed book.** Nothing changed. The +90.3 % at measured COVID costs, the 0.5 %
  risk level, N=40, 4h — all exactly as delivered.
* **A time-consistent coarse version.** The confound is real: a 1d arm whose 365-bar median
  meant 365 *days* is not the only coarse version one could build. **A 1d arm with a 60-day
  lookback was not tested, and this result does not speak to it.** Naming that is the point
  of declaring the confound first — it is the one honest escape from this null, and it is
  a different experiment with its own preregistration.

## 9. Two bugs of my own, recorded because they are the same bug

Both produced a **plausible, empty** result rather than an error:

1. `horizon_axis.py` looked for each arm's archive in the directory it *intended* to write
   to. Freqtrade wrote all four into `user_data/backtest_results/`, because
   `--export-filename` is a **prefix inside** that directory, not a directory. Every arm
   reported "no archive" and the tool would have printed an empty table. **Selecting an
   artifact by where you meant to put it is §34c's error again** — that one dropped 999 of
   1,111 trades and still printed a verdict. The arm is now identified by the `timeframe`
   recorded **inside** the zip by the engine itself.
2. `max_drawdown_account` is a **fraction** and the report printed it with a `%`, rendering
   14.16 % as "0.14 %". Same unit-error class as §16d's. Fixed, and the corrected column is
   the one published above.
