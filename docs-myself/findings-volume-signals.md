# Findings: Volume Signals — "Does Volume Help, or Is MA Just Wrong?"

Run 2026-09-19, freqtrade 2026.8. Scripts: `tools/volume_signal_study.py`,
`tools/vwma_falsification.py`, `tools/ma200_vs_vwma.py`, `tools/volume_vs_speed.py`.

---

## The question

> "我看到有说看量的,MA 可能不准?"

Reasonable instinct. MA, RSI and Bollinger are all **transformations of price** —
they carry no information price doesn't already contain. Volume is a second,
largely orthogonal dimension.

**Verdict: volume added nothing. But the investigation found something more
useful than a signal — it found the reason the earlier MA studies looked weak.**

---

## Step 1 — Five volume signal families

On 20 large-cap majors, 2019-01-01 → 2026-09-17 (7.7y), 10bps.
Baseline buy & hold: CAGR 37.35%, MaxDD -81.37%, Sharpe 0.81.

| Signal | avg exp | CAGR | MaxDD | Sharpe | vs flat control |
|---|---:|---:|---:|---:|---:|
| volume trend 10/30 | 71.8% | 50.47% | -75.55% | 0.98 | +0.173 |
| volume spike 2x | 51.5% | 38.66% | **-55.47%** | 0.97 | +0.166 |
| volume breakout | 53.8% | 35.01% | -51.27% | 0.91 | +0.105 |
| OBV trend 30 | 77.7% | 33.69% | -81.15% | 0.79 | -0.021 |
| **VWMA 50** | 76.5% | **53.97%** | -69.75% | **1.03** | **+0.218** |

Four of five beat the flat control. VWMA-50 looked like a genuine winner:
Sharpe 1.03 vs 0.81, and better than buy & hold on **16/20 pairs**.

Placebo (200 random draws, 5 families → Bonferroni p<0.01):
VWMA p=0.030 — **fails Bonferroni**, passes only the uncorrected 0.05.

---

## Step 2 — Falsification attempt

`tools/vwma_falsification.py` — 6/8 checks passed:

| Check | Result |
|---|---|
| beats flat control | ✅ PASS |
| beats buy & hold Sharpe | ✅ PASS |
| no look-ahead (1-bar shift) | ✅ PASS (1.03 → 1.06 → 1.05) |
| placebo p<0.05 | ✅ PASS |
| placebo p<0.01 | ✅ PASS |
| plateau not spike (std<0.15) | ✅ PASS (range 0.81–1.04, std 0.08) |
| consistent sub-periods (≥6/8) | ❌ FAIL (5/8) |
| sample > MinBTL | ❌ FAIL (7.7y vs 11.9y needed for N=50) |

**The decisive finding was the conditional test**, exactly as the handoff's H3
preregistration demanded ("「在已有 MA200 信息条件下提供增量信息」才是"):

> Within days where MA200 says risk-on: always-1.0 gives Sharpe **2.44**,
> VWMA-scaled gives **2.28**. **VWMA adds nothing on top of MA200.**

---

## Step 3 — Head-to-head exposed a confound

`tools/ma200_vs_vwma.py` compared VWMA-50 against MA200 and found VWMA better
(1.03 vs 0.82), and on days they disagreed **VWMA was "right" on both sides**:

| | n | mean next-day return |
|---|---:|---:|
| MA200 bull / VWMA bear | 437 | **-0.20%** |
| MA200 bear / VWMA bull | 470 | **+0.20%** |

That looks compelling — until you notice the **confound**: VWMA used a 50-day
window and MA200 a 200-day window. Two things differ at once:

* **window** — 50 vs 200 → **SPEED**
* **weighting** — volume vs equal → **VOLUME**

A faster MA is right at turning points *by construction*. So this comparison
proves nothing about volume.

---

## Step 4 — The decisive test: isolate volume from speed

`tools/volume_vs_speed.py` holds the **window fixed** and changes **only the
weighting**: SMA(N) vs VWMA(N).

| window | SMA (price only) | VWMA (volume-weighted) | ΔSharpe |
|---|---|---:|---:|
| 20 | 43.86% / -69.11% / SR 0.92 | 43.07% / -70.89% / SR 0.91 | -0.01 |
| 50 | 58.32% / -68.52% / SR **1.07** | 53.97% / -69.75% / SR 1.03 | -0.05 |
| 100 | 53.43% / -66.45% / SR 1.01 | 52.89% / -67.46% / SR 1.01 | -0.00 |
| 200 | 36.08% / -67.30% / SR 0.82 | 34.87% / -69.95% / SR 0.81 | -0.01 |

**Mean |ΔSharpe| = 0.017.** Paired bootstrap: no window shows a significant
volume effect (all CIs straddle zero, and the point estimates are *negative*).

For contrast, the **speed** effect is 10–15× larger (SMA50 vs SMA200: ΔSharpe
+0.255, CI [-0.01, +0.53]) — though still not significant at 7.7 years.

> **Conclusion: the apparent VWMA "edge" was SPEED (50 vs 200), not VOLUME.**
> Volume weighting adds nothing measurable over a plain SMA.

---

## Step 5 — SMA-50 alone is the real (and only) finding

`tools/sma50_verification.py` — plain price SMA, **no volume anywhere**:

| rule | avgExp | CAGR | MaxDD | Sharpe | ΔSharpe vs flat |
|---|---:|---:|---:|---:|---:|
| SMA-20 | 76.3% | 43.86% | -69.11% | 0.92 | +0.110 |
| **SMA-50** | 76.8% | **58.32%** | -68.52% | **1.07** | **+0.263** |
| SMA-100 | 76.4% | 53.43% | -66.45% | 1.01 | +0.207 |
| SMA-200 | 75.9% | 36.08% | -67.30% | 0.82 | +0.008 |

SMA-50 result:
- Placebo **p=0.005** — passes Bonferroni for 4 windows (p<0.0125)
- Paired bootstrap ΔSharpe **+0.257, CI [+0.02, +0.48]** — **the only candidate in
  this project whose CI excludes zero**
- Turnover 10.7x/yr; degrades gracefully under one-bar shift (no look-ahead)

**This is the first result across all five studies to clear the standard gates.**

---

## Step 6 — But out-of-sample splits the verdict

`tools/sma50_walkforward.py` — the window was chosen *after* seeing the grid,
so this gate is mandatory.

**Walk-forward (pick window in-sample, trade out-of-sample, roll forward):**

| fold | train ends | test | chosen window | IS SR | OOS SR |
|---|---|---|---:|---:|---:|
| 1 | 2020-02-06 | 2020-02→2021-03 | 20 | 1.49 | **2.64** |
| 2 | 2021-03-14 | 2021-03→2022-04 | 30 | 2.19 | 1.05 |
| 3 | 2022-04-20 | 2022-04→2023-05 | 30 | 1.80 | **-0.53** |
| 4 | 2023-05-27 | 2023-05→2024-07 | 50 | 1.35 | 1.32 |
| 5 | 2024-07-02 | 2024-07→2025-08 | 50 | 1.34 | 1.10 |
| 6 | 2025-08-08 | 2025-08→2026-09 | 50 | 1.30 | **-0.81** |

Stitched OOS Sharpe **0.94** vs buy & hold **0.75** → *holds up*.
But note the **chosen window drifts 20→30→50** and the last two folds go
negative. That is instability, not a stable edge.

**Anchored split (fit first half, freeze, test second half):**

| rule | CAGR | MaxDD | Sharpe |
|---|---:|---:|---:|
| frozen SMA-30 | 14.80% | -68.87% | 0.53 |
| buy & hold | 17.29% | -71.75% | **0.57** |
| flat control (same avg) | 16.94% | -59.38% | **0.57** |

**FAILS both**: the rule loses to buy & hold *and* to the flat control
out-of-sample. The window chosen on the first half was 30 — not 50.

> The two OOS methods **disagree**. Walk-forward says the edge survives;
> anchored split says it does not. When out-of-sample methods conflict, the
> honest reading is **not proven**, not "mostly works".

---

## Step 7 — Cross-asset replication appeared to rescue SMA-50

`tools/sma_cross_asset_wf.py` — run the *same* walk-forward protocol
independently on each of the 20 majors (pick window in-sample, freeze it, trade
out-of-sample, roll forward). This is the handoff's "跨资产复制 — 最强的防过拟合证据之一".

| | result |
|---|---|
| assets beating buy & hold OOS | **16/20** |
| mean ΔSharpe | +0.050 (median +0.046) |
| sign test | **p = 0.0059** |
| bootstrap 95% CI on mean ΔSharpe | **[+0.007, +0.088]** — excludes zero |
| better by year (portfolio) | 5/8 |

All three gates passed. This looked like the confirmation SMA-50 needed.

## Step 8 — …but the assets are not independent

`tools/correlation_adjusted_test.py`. Crypto majors move together. A sign test
assumes independent trials; these are not:

* **mean pairwise return correlation: ~0.7–0.8**
* **effective independent bets (participation ratio): ~2.6**
* effective N by eigenvalues > 1: **2.0**

> **20 assets behave like roughly 3 independent bets, not 20.**

Re-testing against a null that **preserves the real correlation structure**
(one common factor, zero skill, 400 draws):

| statistic | observed | null mean | null p95 | p-value |
|---|---:|---:|---:|---:|
| mean ΔSharpe across assets | +0.050 | -0.023 | +0.098 | **0.142** |
| assets better than buy & hold | 16 | 8.5 | 17.0 | **0.072** |

**Neither is significant.** The naive p=0.0059 collapses to p=0.142 once
correlation is respected.

> **"16/20" was largely ONE market regime counted many times.**

---

## Trial ledger — and what it implies

Every configuration tested on this dataset:

| study | trials |
|---|---:|
| MA200 exposure | 3 |
| momentum variants | 5 |
| momentum grid | 24 |
| drawdown rules | 5 |
| volume families | 5 |
| VWMA grid | 8 |
| funding families | 4 |
| funding sign test | 8 |
| SMA window grid | 8 |
| cross-asset walk-forward | 20 |
| **TOTAL** | **90** |

**MinBTL for N=90 at target Sharpe 0.84 ≈ 12.8 years. Available data: 7.7 years.**
→ **The sample is too short for this many trials.** Even a genuinely null
strategy would be expected to produce an apparently good configuration here.

---

## Final verdict on SMA-50

| gate | result |
|---|---|
| beats flat control (in-sample) | ✅ +0.263 |
| beats buy & hold (in-sample) | ✅ Sharpe 1.07 vs 0.81 |
| placebo p<0.005 | ✅ p=0.005 |
| paired bootstrap CI excludes zero | ✅ [+0.02, +0.48] |
| no look-ahead | ✅ graceful under 1-bar shift |
| parameter plateau | ✅ std 0.08 |
| walk-forward OOS | ✅ 0.94 vs 0.75 |
| anchored OOS | ❌ **0.53 vs 0.57 (fails)** |
| cross-asset OOS (naive) | ✅ 16/20, p=0.0059 |
| **cross-asset OOS (correlation-aware)** | ❌ **p=0.142 (fails)** |
| sample > MinBTL | ❌ **7.7y vs 12.8y needed** |

**SMA-50 does NOT pass.** Its apparent strength is explained by (a) the
conflicting OOS evidence and (b) the very small effective number of independent
bets in a crypto majors panel.

---

## The actually useful insight

Plain **SMA-50** — no volume at all — gets **Sharpe 1.07 vs buy & hold 0.81**,
with drawdown -68.5% vs -81.4%. That is better than the VWMA "winner" that
prompted this whole investigation.

So the earlier conclusion "MA doesn't help" was **too strong and partly an
artifact of window choice**. MA200 is a slow, lagging filter; a 50-day MA over
crypto's much faster cycle behaves differently. But see Step 6 — SMA-50's
superiority is **not out-of-sample stable**.

---

## What "MA 不准" actually means here

MA is not inaccurate — it is **lagging**, and the lag is tunable. The real
problems are the ones already documented:

1. **Drawdown stays ~-68%** no matter which MA you use. Price-only rules cannot
   see risk coming; they only react after it arrives.
2. **Statistical power is the binding constraint.** 7.7 years gives SE(Sharpe)
   ≈ 0.36. Distinguishing Sharpe 1.07 from 0.82 needs far more data — and the
   anchored OOS test suggests the difference may not exist at all.
3. **Volume, the one genuinely orthogonal input tested, contributes 0.017
   Sharpe** — indistinguishable from noise.

---

## Reproduce

```powershell
.\.venv\Scripts\python.exe tools\volume_signal_study.py    # 5 families
.\.venv\Scripts\python.exe tools\vwma_falsification.py     # 8 checks
.\.venv\Scripts\python.exe tools\ma200_vs_vwma.py          # head-to-head
.\.venv\Scripts\python.exe tools\volume_vs_speed.py        # DECISIVE: volume vs speed
.\.venv\Scripts\python.exe tools\sma50_verification.py     # flat control + placebo
.\.venv\Scripts\python.exe tools\sma50_walkforward.py      # OOS gate
```

## Bottom line

- ❌ **Volume does not help.** Mean effect 0.017 Sharpe, no window significant.
- ✅ **The instinct that "MA might be wrong" was productive** — it uncovered that
  the earlier MA200 result was partly a *window* artifact, and that plain SMA-50
  looked far better in-sample (Sharpe 1.07, placebo p=0.005).
- ❌ **But SMA-50 is NOT confirmed.** Walk-forward passes (0.94 vs 0.75);
  anchored split fails (0.53 vs 0.57). Cross-asset replication *looked* like
  rescue (16/20, p=0.0059) but **collapses to p=0.142** once the ~2.6 effective
  independent bets are accounted for.
- 🔑 **The bottleneck is statistical power, not ideas.** With 90 configurations
  tried on 7.7 years, MinBTL demands **12.8 years**. Any further signal search on
  this dataset hits the same wall.

## A transferable lesson

**Count effective independent bets, not nominal ones.** A 20-asset crypto panel
behaved like ~3 independent trials. Naive significance tests on correlated
panels (20 assets, 100 stocks, 500 pairs) systematically overstate evidence by
roughly √(N/N_eff). Measure it with the eigenvalue participation ratio before
trusting any "N of M assets confirmed it" claim.
