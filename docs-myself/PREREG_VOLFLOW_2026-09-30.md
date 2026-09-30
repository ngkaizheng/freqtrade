# PREREG — F-1: DO VOLUME FLOW OR VOLATILITY CARRY INFORMATION THE BOOKS DO NOT ALREADY HAVE?

**Written:** 2026-09-30, before any volume or volatility feature was computed.
**Instrument:** `oi_signal_test.py`'s `ic_and_t`, **validated in §42** (null 4.3 %, NW/naive
0.411, power 74 % at IC≈0.04, look-ahead 0 violations on real data).
**Why now:** §42's control table promoted this from a guess. `dVol_4` — the change in kline
volume — scored **t = +7.65, IC = +0.0188**, the second strongest predictor measured
anywhere in this project, and it is **not in the closed registry**: entry #11 closed
*taker* flow for the absence of L1/L2 data, which is a different data type.

---

## 1. The question, and why "which feature has the biggest t" is NOT it

The existing books are both price/volume trend books. The short book is essentially 4h
momentum (`mom_4` scored t = −8.85 in §42, independently confirming it). **So a new feature
that merely predicts returns is worthless to us. The only useful question is whether it adds
information to momentum.**

§42 answered that for OI by comparing |t|. **This round does it properly**, with an
incremental test:

> **Gate B regresses the forward return on the CONTROL and the CANDIDATE together, and tests
> the CANDIDATE's coefficient.** If the control is 4h momentum, a significant candidate
> coefficient is a direct answer to "does this add anything on top of momentum?"

A feature can have a large univariate |t| and a zero incremental coefficient — that is
exactly what "the same information wearing a different feed" looks like, and §42's Gate 3 was
built for it. **Gate B is the sharper version.**

## 2. The arms — one pre-registered feature set, published whole

**CONTROLS (already measured in §42, re-used unchanged):** `mom_4`, `dVol_4`.

**CANDIDATES — volume flow (F):**

| feature | what it is |
|---|---|
| `dVol_1`, `dVol_12` | volume change at two more horizons |
| `vol_z` | log volume, z-scored on its own trailing 6 months |
| `obv_slope` | slope of on-balance-volume over 12 bars |
| `vol_x_sign` | volume change × sign of the return — **volume confirms direction?** |
| `amihud` | \|return\| / dollar volume — the classical illiquidity measure |
| `vol_trend` | volume / its own 20-bar mean |

**CANDIDATES — volatility (D):**

| feature | what it is |
|---|---|
| `rv42` | 42-bar realised volatility, level |
| `rv_expand` | RV42 / RV42 forty-two bars ago — **expansion vs contraction** |
| `vol_of_vol` | stdev of RV42 over 42 bars |
| `gk_vol` | **Garman-Klass** range volatility — uses high/low, which price-only vol does not |
| `rv_x_ret` | realised vol × return — **volatility-conditioned momentum** |

**Horizons:** 4h / 12h / 24h forward, as in §42.

## 3. Pre-registered gates

**Gate A — is there anything?** |IC| ≥ 0.02 **and** |NW-t| ≥ 2.5, the same bar as §42 and
**unchanged**.

**Gate B — the decisive one.** For every candidate, regress `fwd_h` on
`[mom_4, dVol_4, candidate]` and take the candidate's **incremental** coefficient with a
Newey-West t.
> **PASS needs: the best candidate's incremental |NW-t| ≥ 2.5 AND its incremental |partial
> correlation| ≥ 0.01.** The partial correlation is required so that a large t on a
> near-collinear feature cannot pass on scale alone.

**Gate C — the same power honesty as §42's appendix A.3.** If Gate B fails while the
candidate's *univariate* |IC| is below ~0.08, the result is **INCONCLUSIVE (insufficient
power)**, not a negative. The same measured power curve applies and is not re-derived.

**Gate D — the bar is not moved after the fact**, and **the whole table is published**,
every feature × every horizon, whether or not anything passes. §41's rule: a curve, not a
selected cell.

## 4. Kill rule

**If no candidate passes Gate B**, the honest reading is that **kline volume and volatility
carry nothing the two existing trend books do not already have**, and both Tier 2 items
**F and D close on a measurement**. That is a real result: it says the *entire* 4h
price/volume/volatility feature space is exhausted for this universe, and the next round
must go to a mechanism with a different information source — not another transform of the
same bars.

## 5. What this round is NOT

* **Not a backtest.** Gate A/B are feature-layer statistics. If something passes, the
  strategy comes next, in Freqtrade, through the full chain: backtest → realistic cost →
  `lookahead-analysis` → `recursive-analysis` → OOS → stress → correlation (daily r < 0.30
  against both books) → holdout.
* **Not a re-run of the OI line.** Different features, same instrument, same controls.
* **The holdout stays frozen.** The final holdout was consumed 2026-09-26 and cannot be
  reused; everything here is inside the development window.
