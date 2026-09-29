# Findings: Fragility, and the Selection Problem at Parameter Level

Run 2026-09-19. Scripts: `tools/fragility_analysis.py`,
`tools/reconciliation_jackknife_vs_oos.py`, `tools/rho_stability.py`.

**Two results, one of which corrected me mid-round.**

---

## Part 1 — The edge is NOT fragile (I expected the opposite)

`tools/fragility_analysis.py`. Rule frozen at SMA-50 / 50%–100%, metric is
Sharpe(rule) − Sharpe(flat at matched exposure). Diagnostic only.

**BTC/USD, 15y — full-sample edge +0.187**

Leave-one-year-out (drop each year in turn):

| dropped | edge | Δ |
|---|---:|---:|
| none (baseline) | **+0.187** | — |
| 2013 (best) | +0.237 | +0.051 |
| 2012 (worst) | +0.154 | −0.033 |
| 2017 | +0.169 | −0.017 |
| 2022 | +0.171 | −0.016 |

**Range +0.154 … +0.237 — never close to zero.** Era split: pre-2019 **+0.156**,
2019+ **+0.240**. Bootstrap CI **[+0.011, +0.369]**, p(≤0) = 0.018.

Profit concentration: top 10 days = 28.2% of excess, top 50 = 91.3%. For daily
crypto returns that is **reasonably distributed**, not a few-lucky-days artifact.

**20-major pool, 7.7y — full-sample edge +0.263**

Jackknife range **+0.140 … +0.340**, CI **[+0.030, +0.476]**, p(≤0) = 0.014.

**So I was wrong to assume fragility.** The edge is stable across time for a
fixed window. This is worth stating plainly because I predicted the opposite.

---

## Part 2 — Then why does it fail out-of-sample?

`tools/reconciliation_jackknife_vs_oos.py` separates the two questions:

| | question | answer |
|---|---|---|
| **jackknife** | given window = SMA-50, is the edge spread across years? | **YES** |
| **train/test** | can the window be *chosen* in advance? | **weakly** |

The jackknife **fixes the window and varies the years**. The split **varies the
window**. A rule can be stable in time yet have a parameter that cannot be chosen
without hindsight.

On the 20-major pool with one split (train ≤2023, test ≥2024):

| window | train edge | test edge | train rank | test rank |
|---|---:|---:|---:|---:|
| 10 | +0.057 | +0.003 | 7 | 2 |
| 20 | +0.207 | −0.039 | 5 | 6 |
| 30 | +0.359 | −0.127 | 2 | 8 |
| **50** | **+0.402** | **−0.027** | **1** | 5 |
| 75 | +0.307 | −0.101 | 3 | 7 |
| 100 | +0.268 | −0.019 | 4 | 4 |
| 150 | +0.205 | −0.019 | 6 | 3 |
| 200 | +0.018 | +0.045 | 8 | 1 |

The train-best window (SMA-50, train +0.402) delivered **−0.027** out-of-sample.
The test-best was SMA-200, which had the *worst* train score. Spearman ρ = −0.810.

---

## Part 3 — I over-claimed, and the check caught it

ρ = −0.810 on 8 windows looked like "in-sample selection is *actively harmful*."
I said as much in the previous script's output and in conversation.

`tools/rho_stability.py` repeated the exercise across **6 independent splits**:

**BTC/USD**

| split | ρ | train-best | its test edge |
|---|---:|---|---:|
| 2020-01 | −0.500 | SMA-20 | −0.004 |
| 2021-01 | +0.095 | SMA-20 | −0.167 |
| 2022-01 | −1.000 | SMA-10 | −0.205 |
| 2023-01 | −0.714 | SMA-20 | −0.536 |
| 2024-01 | +0.810 | SMA-20 | −0.076 |
| 2025-01 | +0.405 | SMA-20 | −0.044 |

mean ρ **−0.151**, range **−1.000 … +0.810**, negative in only **3/6**

**20-major pool**

mean ρ **+0.226**, range **−0.762 … +0.833**, negative in **2/6**

**ρ is NOT stably negative.** My "actively anti-predicts" claim was an
over-reading of one split — the same error class as L3 (concluding from a single
comparison) and L6 (letting a striking number stand in for a conclusion).

### What IS stable

| | BTC | pool |
|---|---:|---:|
| splits where train-best window gave a **positive** test edge | **0/6** | 4/6 |
| mean train-best test edge | **−0.172** | +0.044 |
| mean test-best (oracle) edge | +0.152 | +0.173 |

On BTC, **the in-sample-best window never once produced a positive out-of-sample
edge** across six splits. That is the durable finding — not the sign of ρ.

---

## The reconciliation

Both statements are true and they are about different things:

1. **The rule is temporally stable for a fixed window.** Jackknife and era splits
   confirm this; it is not a lucky-period artifact.
2. **Its one free parameter cannot be chosen in advance.** Selection does not
   transfer: train-best is not reliably test-good, and on BTC it was
   consistently test-bad. The oracle gap (train-best −0.172 vs oracle +0.152 on
   BTC) is the price of having to choose without hindsight.

This is **lesson L5 restated at the parameter level**: an in-sample plateau does
not imply its members transfer out-of-sample.

---

## Consequence for the candidate

**Status unchanged, but for a sharper reason.**

> BTCSmaTrend is temporally stable and passed the historical gates, **but its
> SMA-50 choice cannot be justified out-of-sample**. Eligible for forward
> validation only; must not be traded.

Two concrete implications for the forward test:

1. **The window must be pre-committed and not searched.** Any forward tuning of
   the window re-introduces exactly the problem documented here.
2. **A parameter-free variant would be strictly better** if one exists, since it
   removes the unselectable parameter entirely. That is a legitimate next
   question — but it must be pre-registered, and it must not be a disguised grid
   search.

---

## Trial ledger

| round | trials |
|---|---:|
| 1–5 | 150 |
| 6 (H-D) | 4 |
| **7 (this: fragility, reconciliation, ρ stability)** | **~10** |
| **total** | **~164** |

---

## Reproduce

```powershell
.\.venv\Scripts\python.exe tools\fragility_analysis.py
.\.venv\Scripts\python.exe tools\reconciliation_jackknife_vs_oos.py
.\.venv\Scripts\python.exe tools\rho_stability.py
```
