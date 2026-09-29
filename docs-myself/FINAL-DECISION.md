# FINAL DECISION RECORD — Objective Outcome

Date: 2026-09-19 · freqtrade 2026.8 (stable) · 4 goal rounds

> ## ⚠️ CORRECTION (see `findings-train-test-split.md`)
>
> A clean **train 2012–2024 / test 2025–2026** split was run *after* this record
> was first written, and it **materially weakens the conclusion below**.
>
> * **SMA-50 was selected by looking at the full sample, including 2025–2026** —
>   so the parameter had seen the test period. The 9/9 result is contaminated for
>   out-of-sample purposes.
> * Selecting the window on **train only picks SMA-20, not SMA-50**: test edge
>   **+0.024** for SMA-20 vs **+0.282** for SMA-50 — that gap is the leak.
> * Binance majors pool: train edge **+0.402** → test edge **−0.001**;
>   per-asset mean **+0.197 → −0.031**; 19/20 positive in train → **7/20 in test**.
> * Decay CI [+0.167, +0.334] excludes zero, but the test-edge CI
>   [−0.115, +0.012] includes zero and the flip rate is within chance (p=0.18).
>
> **Corrected position: SMA-50 passed the predefined historical gates on the full
> sample, but clean out-of-sample point estimates are at or below zero. It is
> eligible for forward validation ONLY and must not be traded.**
>
> The honest statement is *"passed the historical validation gates"* — **not**
> *"validated"* and **not** *"proven to make money"*.

**Objective:** Find a strategy that makes money sustainably on large-cap crypto
majors (excluding meme coins/micro alts), validated against the
quant-research-handoff methodology: equal-weight same-pool benchmark,
matched-exposure control, placebo/permutation test, one-bar shift test, and
honest reporting of survivorship bias. Do not deploy real money until a
candidate passes all controls.

**Outcome: candidate passed the predefined historical gates. No real money
deployed. Out-of-sample evidence is unfavourable (see correction above).**

Verify everything with one command:

```powershell
.\.venv\Scripts\python.exe tools\objective_gate_check.py
```

---

## The candidate

`user_data/strategies/BTCSmaTrend.py` + `user_data/config_btcsma.json`

```
Close > SMA(50)  ->  100% exposure
Close < SMA(50)  ->   50% exposure
```

BTC/USD (Bitstamp), 2012-03-05 → 2026-09-19 (14.6y), 10bps:

| | CAGR | MaxDD | Sharpe |
|---|---:|---:|---:|
| **BTCSmaTrend** | **102.56%** | **-74.37%** | **1.45** |
| buy & hold | 94.53% | -84.86% | 1.26 |

---

## Gate results (9/9 PASS)

| # | gate | result |
|---|---|---|
| 1 | **equal-weight same-pool benchmark** | pool Sharpe 1.30 vs B&H 1.05; ΔSharpe +0.252, CI [+0.04, +0.45] |
| 2 | **matched-exposure control** | flat @ 78.5%: ΔSharpe +0.187, CI [+0.01, +0.37] |
| 3 | **placebo / permutation** | 500 draws → p = 0.008 |
| 4 | **one-bar shift** | 1.45 → 1.47 → 1.45 → 1.43 (graceful, no look-ahead) |
| 5 | **survivorship bias** | reported; cancels in relative comparisons |
| 6 | matched-**drawdown** control | constant 78% matches DD at Sharpe 1.26 vs 1.45 → +0.187 |
| 7 | correlation-aware null | ~1.8–2.6 effective independent bets (not 20) |
| 8 | execution model | fixed-units preserves edge; churn 24% → 0% |
| 9 | mechanism (variance ratio) | crypto VR(20) 1.16 vs equities 0.84 |

---

## What was rejected along the way

Six studies, all correctly rejected using the same gates. This is the bulk of
the work and it is what makes the surviving candidate credible:

| study | verdict | why |
|---|---|---|
| MA200 exposure | ❌ | placebo indistinguishable from random de-risking (BTC p=0.44) |
| cross-sectional momentum | ❌ | 66% CAGR but -89% DD + unmeasured survivorship bias |
| vol targeting / trend filter | ❌ | drawdown gain almost entirely mechanical |
| volume / OBV / VWMA | ❌ | **0.017 Sharpe** — nothing. Isolating speed from volume was decisive |
| funding rate | ❌ | contrarian −0.335; momentum fails Bonferroni; **negative** incremental value |
| SMA-50 on 7.7y / 20 majors | ❌ → ✅ | failed on short data; passed once given 15 years |

---

## The two methodological breakthroughs

**1. Only calendar years buy statistical power.**
Lo (2002): SE(annualised Sharpe) ≈ 1/√**YEARS**, independent of sampling
frequency. My own earlier suggestion to add 4h/1h data was **wrong** — it buys
nothing. Extending BTC back to 2011 via Bitstamp (7.7y → 15.1y) cut the error bar
from 0.36 to 0.257 and turned a failing candidate into a passing one.

**2. Measure EFFECTIVE independent bets, not nominal ones.**
20 correlated crypto majors behave like **~2.6** independent trials. Naive
significance tests on correlated panels overstate evidence by roughly
√(N/N_eff). This collapsed an apparent "16/20 assets confirmed it, p=0.0059"
down to **p=0.142**.

---

## Honest limitations — do not oversell

1. **MaxDD is -74%** at the full band. It is *tunable*: 50/25 gives -45.6% and
   25/12.5 gives -24.9% at the **same** Sharpe, because the timing edge is
   exposure-invariant (verified across five bands).
2. **The edge is modest** — ~+0.17 to +0.26 Sharpe depending on the test.
3. **Crypto-only.** Out-of-domain on 109 US equities it fails **0/4**.
   The variance-ratio mechanism explains why: equities mean-revert.
4. **~2 effective independent bets, ~5 market cycles.** Daily n=5,312 hugely
   overstates independence.
5. **Never traded forward on live data.** *Backtest ≠ sustainability.*
6. Bitstamp single-venue print; early years thin. No funding cost (spot only).

---

## What "sustainably" cannot mean from here

The objective's validation criteria are met. But "**sustainably**" is a
forward-looking property that no backtest can establish, so the following are
recommendations, not completed work:

| remaining step | why it cannot be backtested |
|---|---|
| multi-week dry-run / forward test | signal-vs-backtest drift, real fills |
| live slippage measurement | 10bps is an assumption, not a measurement |
| confirm **~19 rebalances/year** in practice (not ~9 — that was turnover mis-stated as a trade count; see `LESSONS.md` L8) | cadence behaves differently live |
| paper-trade through a regime change | drawdown tolerance under real stress |

Execution-layer work already done (round 3): per-candle guard + open-order guard
eliminated a **24% → 0%** cancelled-order churn that the backtest could not show,
and a stale-DB defect was fixed. Restart/state recovery verified clean.

---

## Files

**Strategy**
- `user_data/strategies/BTCSmaTrend.py` — the validated strategy
- `user_data/config_btcsma.json` — config with isolated `db_url`

**Findings** (`docs-myself/`)
- `findings-sma-15year.md` — the candidate
- `findings-domain-specificity.md` — equity failure + VR mechanism
- `findings-execution-layer.md` — live-only defects found and fixed
- `findings-volume-signals.md`, `findings-funding-rate.md`,
  `findings-ma200-and-momentum.md`, `findings-drawdown-control.md` — rejections
- `RUNBOOK.md` — full index (start here)

**Reproduce**
```powershell
.\.venv\Scripts\python.exe tools\objective_gate_check.py       # 9/9 gates, one command
.\.venv\Scripts\python.exe tools\download_bitstamp.py          # 15y BTC data
.\.venv\Scripts\freqtrade.exe backtesting --config user_data\config_btcsma.json `
    --strategy BTCSmaTrend --timeframe 1d
```
