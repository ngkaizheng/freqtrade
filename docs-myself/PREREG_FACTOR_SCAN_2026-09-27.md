# PRE-REGISTRATION — Stage 0: cost-aware factor discovery scan (5m)

**Frozen: 2026-09-27, before any Stage 0 number was produced.**
Written because AGENTS.md §1 requires the decision and its evidence to be
recorded *before* the work, and because the previous session's own funding-filter
lead had to be retired for lack of a pre-written pass/fail rule.

---

## 0. Why this exists

The project has no cell that has cleared a significance bar in two independent
engines. The 4h short-breakout line is stopped. The proposed direction is
5m microstructure, and the reason it is not obviously dead is a cost identity,
not a signal:

```
cost_R = round_trip_bps / (stop_multiple × atr_pct × 10000)
```

Measured on local data: 5m BTC `atr_pct` = 0.1675% → **cost_R = 0.597R** at 10 bps
round trip; 1m BTC → **1.650R**. At 1m the strategy must produce more than its own
stop distance in gross edge per trade merely to break even.

**This document fixes the gate BEFORE the scan, so the scan cannot be tuned.**

---

## 0b. AMENDMENT 1 — made after the first aggregate number printed, before any curve

**Disclosure.** The scan's very first printed line before crashing on a format
error was: `--- rvol --- best bucket 19 (p95-100), mean -0.5490R`. That is the
**only** result observed before this amendment. No bucket table, no window, no
liquidity split, and no other factor had printed.

**What was wrong and is now fixed.** §2 defined `fwd_R` as a *long* forward
return only. The entire project line is a **short**-side hypothesis (the 4h rule
shorts; the OI quadrant result carries its drift in the price-**down** quadrants).
Scanning only the long direction would have declared the strongest volume factor
a failure when it is in fact negative, i.e. a short signal.

**Amendment, frozen now:**

1. **Both directions are tested.** For each factor and bucket the scan reports
   `net_R` (long) and `net_R_short` = −`net_R` (short). A factor advances in
   whichever direction is monotone-signed; **both are reported either way.**
2. **The primary grid is therefore 3 factors × 2 directions × 20 buckets =
   120 tests**, not 60. The deflated threshold must be recomputed for 120.
3. This doubles the search space. That cost is accepted knowingly and is exactly
   why §5 requires *all four* criteria rather than a high t.

## 0c. AMENDMENT 2 — the risk unit produces outliers that must be shown, not hidden

Observed while implementing §3 (not a result, a distributional property of the
data): dividing by the *instantaneous* ATR makes both `fwd_R` and `cost_R` scale
as 1/`atr_pct`, so near-zero-ATR bars produce values in the tens of R in both
directions. On this sample `cost_R` spans **0.010R to 23.887R**.

**Amendment:**

- The primary gate stays as specified (instantaneous ATR).
- Two robustness variants are reported alongside and the decision is only
  `ADVANCE` if it survives: (a) `net_R` winsorised at ±5R, (b) the risk unit
  replaced by the trailing 1-day (288-bar) **median** ATR, which is what a
  practitioner would actually size with.
- **A verdict that flips between variants is reported as `FRAGILE`, not ADVANCE.**

| | |
|---|---|
| Source | `shark_data/klines/*_5m.csv.gz` |
| Symbols | **9** — BTC, ETH, SOL, BNB, XRP, DOGE, ADA, AVAX, LINK |
| Window | 2023-01-01 → 2026-08-31, 385,632 bars/symbol |
| Columns | OHLCV + `quote_volume`, `trades`, **`taker_buy_quote_volume`**, `taker_sell_volume` |

**CVD is computed, not downloaded:** `delta_quote = 2·taker_buy_quote_volume − quote_volume`.

> **⚠ SCOPE LIMIT, FROZEN IN ADVANCE.** The requested Top20/Mid50/Tail30
> liquidity stratification is **NOT POSSIBLE** — only 9 symbols exist at 5m
> locally. The scan therefore reports a coarse **Top3/Mid3/Tail3** split ranked by
> median quote volume, **and that is explicitly not the requested
> stratification.** Producing the real one requires downloading 5m history for
> ~100 symbols, which is a separate, larger job. Any conclusion drawn here is
> conditional on a 9-name universe.

---

## 2. Factors (three, fixed, no others)

All are causal: computed from bar `t` and its history only.

| name | definition |
|---|---|
| `rvol` | `volume / SMA(volume, 20)` — current bar included, matching the shark engine |
| `cvd_press` | `Σ_{n=12} delta_quote / Σ_{n=12} quote_volume` — dimensionless taker-buy share minus 0.5 over the last hour, bounded [−1, +1] |
| `vwap_dev` | `(close − VWAP₂₀) / ATR₁₄` where `VWAP₂₀ = Σ quote_volume / Σ volume` over 20 bars — position of price vs its own recent VWAP, in stop units |

`stop_multiple = 1.0`, `ATR` = Wilder 14 on close, the same definition used in
`phase2_cost_by_timeframe.csv`.

**The scan is UNIVARIATE.** No interactions, no composites, no thresholds. The
joint grid is explicitly out of scope for Stage 0.

---

## 3. The gate (this is the whole point, and it is PER BAR)

```
atr_pct(t)   = ATR₁₄(t) / close(t)                       # causal
cost_R(t)    = round_trip_bps / (1.0 × atr_pct(t) × 10000)   # per bar, dynamic
required_R(t) = cost_R(t) × 1.3                          # safety factor, FROZEN
net_R(t)     = fwd_R(t) − cost_R(t)
```

`fwd_R(t) = (close(t+12)/close(t) − 1) / atr_pct(t)` — forward return over 12
bars (1 hour) expressed in stop units, using the **entry bar's** ATR.

Round-trip cost is reported at **all four measured regimes** from
`COST_MEASUREMENT_2026-09-27.md`, not one number:

| regime | round trip |
|---|---|
| calm | 12.0 bps |
| long-tail cascade | 15.6 bps |
| volatile | 22.8 bps |
| COVID | 34.9 bps |

> **A FIXED cost gate is a statistical error and this prereg forbids it.**
> The previous proposal used "gross > 0.78R" from a median ATR%. ATR ranges
> across this sample by more than an order of magnitude, so a constant gate
> misclassifies high-volatility bars as failures and low-volatility bars as
> passes. The gate is `cost_R(t) × 1.3`, recomputed on every bar.

**Multiple testing.** The deflated bar in this repo (S7) was written for 41,472
trials. The primary grid here is **3 factors × 20 buckets = 60 tests**. Symbol
splits, liquidity buckets and time windows are **diagnostics, not the primary
grid**, and are reported as such. The deflated threshold must be recomputed for
**60** trials, not 41,472.

---

## 4. Statistics — IAT is mandatory from line one

Forward returns over 12 bars overlap: adjacent observations share 11 of 12
bars, so **IAT ≥ 12 by construction**. A naive t on 385,632 bars is inflated by
roughly √12 ≈ 3.5×.

Every t reported by this scan is `t_naive / sqrt(IAT)` using the repository's own
`tools/widepanel/run_wide.py::dependence_t`, on the series **sorted by timestamp
and the sort asserted**. IAT is reported next to every t. **A naive t is never
reported as the headline.**

---

## 5. Pre-registered decision rule (frozen before the run)

For a factor to advance to Stage 1 it must satisfy **ALL FOUR**, at the **calm**
12.0 bps cost regime unless stated:

1. **Curve, not threshold.** The net-R-vs-percentile curve is monotone-signed
   over the top 20% of buckets (tail buckets all one sign, no sign flip inside
   the tail). A curve that peaks in the middle and reverts is a **fail**.
2. **Size.** Mean net R in the best tail bucket ≥ `1.3 × cost_R` at 12.0 bps.
3. **Consistency.** Same sign in **≥ 2 of 3** time windows
   (2023–24 / 2025 / 2026) **and** in **≥ 2 of 3** liquidity buckets.
4. **Significance.** IAT-corrected t ≥ 2.0 in the pooled tail bucket, **and**
   t ≥ 1.5 in each surviving time window.

**Anything not meeting all four is recorded as a NULL and the line is closed.
No parameter adjustment, no re-scanning, no "but at horizon 24…"**

### What this scan explicitly CANNOT establish

- It is a **forward-return factor study, not a strategy.** No entries, no exits,
  no stops, no sizing, no overlapping-position accounting.
- It cannot produce a tradable return. Overlapping 12-bar forward returns
  double-count capital.
- Even a factor passing all four is a **lead**, not a result, and inherits the
  same 60-trial deflation.
- The 9-symbol universe cannot support a liquidity-stratified conclusion.

---

## 6. What would falsify the direction outright

If **all three factors fail** the size test (criterion 2) at the **calm** 12.0 bps
regime, the 5m microstructure direction is closed for this project: it would
mean no measured microstructure factor on this data produces a gross edge larger
than its own round-trip cost, and §1c's `cost_R` law then has no escape except a
stop so wide the strategy is no longer intraday.

**That outcome is a valid and useful result and must be reported as one.**
