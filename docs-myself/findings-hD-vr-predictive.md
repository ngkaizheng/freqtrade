# Findings: H-D — Is VR(20) Predictive of Out-of-Sample Trend Edge?

Run 2026-09-19. Script: `tools/hD_vr_predictive.py`. Pre-registration is in the
script header, written **before** the test.

**Verdict: NOT SUPPORTED (3/4 predictions, the strict one failed).**

---

## Why this hypothesis existed

Round 4 found a mechanism, not just a pattern:

| | VR(20) | meaning |
|---|---:|---|
| crypto | 1.19 | positively persistent (trending) |
| US equities | 0.84 | mean-reverting |

The SMA rule works on crypto and fails 0-for-4 on equities, failing exactly where
VR < 1. If persistence is genuinely the mechanism, it should have a **second
testable implication that does not involve moving averages**: in-sample VR should
**predict** out-of-sample trend edge, on assets the rule has never traded.

That would be genuinely useful — a way to choose *which* assets to trade without
mining their returns. So it was worth a clean test.

## Pre-registered predictions (fixed before running)

| # | prediction | required |
|---|---|---|
| P1 | top VR tercile beats bottom tercile OOS | diff > 0 |
| P2 | Spearman ρ(IS VR, OOS edge) | ρ > 0 |
| P3 | pooled OLS slope, bootstrap CI | lower bound > 0 |
| P4 | **control**: effect absent in equities | not (diff>0 and CI>0) |

Falsification rule fixed in advance: **any of P1–P3 failing ⇒ H-D not supported.**
No parameter changes after seeing results.

---

## Results

**Crypto majors** (IS ≤ 2022-12-31, OOS ≥ 2023-01-01, VR q=20, SMA-50, 10bps):
20 assets, only 6 per tercile.

| | value |
|---|---:|
| bottom tercile mean OOS edge | **−0.132** |
| top tercile mean OOS edge | **−0.060** |
| difference (top − bottom) | **+0.073** |
| Spearman ρ | **+0.135** |
| OLS slope | +0.126, CI **[−0.618, +1.055]** |

| prediction | result |
|---|---|
| P1 (top > bottom) | **SUPPORTED** (+0.073) |
| P2 (ρ > 0) | **SUPPORTED** (+0.135) |
| P3 (slope CI excludes 0) | ❌ **FAILED** ([−0.618, +1.055]) |

**P4 control — US equities** (109 assets, mean IS VR 0.824):

| | value |
|---|---:|
| top − bottom | **−0.005** |
| Spearman ρ | −0.055 |
| OLS slope | −0.025, CI [−0.206, +0.187] |
| **P4** | ✅ **SUPPORTED** — no effect where the mechanism is absent |

---

## Verdict: NOT SUPPORTED

**3/4.** The direction is right and the control is clean, but the strict
statistical prediction failed. Per the pre-registration this is a **failure**,
recorded as such — **not** re-tuned, not re-scoped, not retried with a different
window or tercile count.

### What it does and does not tell us

**Does tell us:**
* The *sign* of the relationship is as the mechanism predicts (+, in both P1 and P2)
* The control behaves correctly — equities, where VR < 1, show essentially zero
  relationship (−0.005, ρ −0.055). The mechanism story is not contradicted.
* VR is **not** a usable asset-selection tool at this sample size.

**Does not tell us:**
* That the VR mechanism is wrong. P1/P2/P4 all point the same way as predicted.
* That a larger sample would not resolve it. With 6 assets per tercile the test
  is drastically underpowered — the same power problem that has dogged every
  round of this project.

**The honest reading:** weak directional evidence for the mechanism, **no
statistical evidence** that VR can be used predictively. The correct action is to
report it and move on, which is what the pre-registration required.

---

## What I deliberately did NOT do

* Did not try q = 5, 10, 60 to find a significant slope
* Did not use quartiles or halves instead of terciles
* Did not restrict to a sub-period where it "works"
* Did not add assets to enlarge terciles
* Did not re-describe the failure as a success

Each of those is exactly the metric-mining this project has spent five rounds
identifying and rejecting in other people's work. Doing it here would be the same
error with the same mechanism (L5 in `LESSONS.md`).

---

## Trial ledger update

| round | trials |
|---|---:|
| 1–4 | 140 |
| 5 | 10 |
| **6 (this)** | **4 (P1–P4, pre-registered)** |
| **total** | **~154** |

Pre-registration means P1–P4 count as 4 trials, not as "one hypothesis" — being
explicit about that is the point.

---

## Consequence for the project

H-D joins the list of closed hypotheses. The VR finding remains a valid
**explanation** of why the SMA rule is crypto-specific (it correctly predicted the
equity failure out-of-domain), but it is **not** a predictive tool.

This does not change the status of the candidate:

> **BTCSmaTrend passed the historical gates but clean out-of-sample point
> estimates are at or below zero. Eligible for forward validation only. Must not
> be traded.**

The active work remains **implementation parity** (weeks to resolve), not further
signal search.

## Reproduce

```powershell
.\.venv\Scripts\python.exe tools\hD_vr_predictive.py
```
