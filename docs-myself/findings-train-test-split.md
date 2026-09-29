# Findings: Train 2012–2024 / Test 2025–2026 — A Correction

Run 2026-09-19. Scripts: `tools/train_test_2025_2026.py`,
`tools/decay_significance.py`.

**This document corrects `FINAL-DECISION.md`.** A clean train/test split was
requested and, to my knowledge, I had never run one as a strict parameter-freezing
test. Running it materially weakens the case for the candidate.

---

## First, an honest disclosure about a real leak

I never ran a clean "select on train, freeze, evaluate on test" split. The
walk-forward folds I ran *did* cover 2025–2026, but more importantly:

> **SMA-50 was itself chosen by looking at the FULL sample — including
> 2025–2026.** It emerged as the best window on Binance 2019–2026 in round 1 and
> was confirmed as the grid peak over the full 15-year Bitstamp series in round 2.

So the parameter had seen the test period even though the *evaluation* had not.
The 9/9 gate result is therefore **contaminated for this specific question**. The
correct experiment selects the window on train data only — which is what I ran.

---

## A. BTC/USD: train 2012–2024 → test 2025–2026

Selecting the window on train only picked **SMA-20**, not SMA-50.

| | value |
|---|---|
| train 2012-03-05 → 2024-12-31 | 12.8y, selected **SMA-20**, train edge **+0.195** |
| test 2025-01-01 → 2026-09-19 | 1.7y, SE **0.76** |
| **frozen SMA-20 rule Sharpe** | **0.04** (CAGR −3.54%, MaxDD −37.67%) |
| flat (same exposure) | 0.02 |
| buy & hold | 0.02 (CAGR −8.33%, MaxDD −53.08%) |
| **test edge vs flat** | **+0.024** — essentially zero |
| *[contaminated]* SMA-50 | Sharpe 0.30, edge **+0.282** |

Note the gap: the honest selection (SMA-20) scores +0.024 while the
test-informed selection (SMA-50) scores +0.282. That gap is itself evidence that
the window choice absorbed test-period information.

## B. Binance majors: train 2019–2023 → test 2024–2026

| metric | train | test |
|---|---:|---:|
| 20-major pool edge vs flat | **+0.402** | **−0.001** |
| per-asset mean edge vs flat | **+0.197** | **−0.031** |
| assets with positive edge | 19/20 | **7/20** |
| rule beats B&H on Sharpe | — | 7/20 |

13 of 20 train-positive assets produced a negative test edge.

## C. US equities (control): train 2011–2024 → test 2025–2026

| metric | train | test |
|---|---:|---:|
| mean edge (109 tickers) | +0.017 | **−0.139** |
| positive test edge | — | 26/109 (24%) |

Consistent with the round-4 out-of-domain failure.

---

## Is the decay statistically real?

`tools/decay_significance.py`. This is the part that matters most, and it is
genuinely ambiguous:

| question | result |
|---|---|
| mean test edge CI (cross-asset bootstrap) | [−0.115, **+0.012**] → **includes 0** |
| mean decay (train − test) | **+0.248**, CI [+0.167, +0.334] → **excludes 0** |
| sign flips | 12/19, binomial p = **0.180** → within chance |

So the point estimates decay substantially and the decay CI excludes zero — but
that test is **optimistic**, because it resamples assets as if independent when
the panel has only ~2.6 effective bets (round-2 lesson). The flip rate alone is
within chance.

The defensible statement is neither "the edge is gone" nor "the edge is fine":

> **The 2024–2026 window is too short to confirm or refute the edge. The point
> estimates are consistent with both mild decay and noise.**

---

## The central problem this exposes

To detect an edge of **+0.17 Sharpe** at 80% power / 95% confidence requires
roughly **10–20 years** of daily data for the paired comparison (see
`findings-power-analysis.md`; an earlier version of this doc said ~271 years,
which used the wrong statistic). Even +0.5 Sharpe absolute needs ~31 years.

This does not improve with more searching:

| sample | SE(Sharpe) | what it can resolve |
|---|---:|---|
| 15.1y (BTC Bitstamp) | 0.26 | the only reason round 2 passed |
| 2.7y (2024–2026 test) | 0.61 | almost nothing |
| 1.7y (2025–2026 test) | 0.76 | almost nothing |

**A modest-Sharpe daily strategy cannot be confirmed on any realistic sample.**
That was always true; the clean split makes it concrete.

---

## What this changes

| claim | before | now |
|---|---|---|
| "SMA-50 passes 9/9 gates" | asserted | **still true on the full sample, but the window choice had seen the test period** |
| "eligible for forward validation" | yes | **yes, but with materially less confidence** |
| "candidate validated" | asserted in FINAL-DECISION | **demoted to: passed historical gates, OOS point estimates unfavourable** |
| "the edge is real" | not claimed | **still not claimed — and now with a documented reason for doubt** |

**The candidate is not refuted, but it has not earned trust.** A candidate whose
every out-of-sample point estimate is worse than in-sample should be treated as
suspect until forward data says otherwise — not deployed.

## The corrected position

> **SMA-50 passed the predefined historical validation gates on the full sample,
> but a clean train/test split (select on train, freeze, test on 2025–2026)
> produces test edges at or below zero, and the window had seen the test period.
> The rule is eligible for forward validation only, and must not be traded.**

This is the statement I should have written in `FINAL-DECISION.md`.

## Reproduce

```powershell
.\.venv\Scripts\python.exe tools\train_test_2025_2026.py   # the split
.\.venv\Scripts\python.exe tools\decay_significance.py     # is the decay real?
```
