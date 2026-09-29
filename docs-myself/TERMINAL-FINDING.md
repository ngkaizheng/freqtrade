# TERMINAL FINDING — No Strategy Survives

Date: 2026-09-19 · freqtrade 2026.8 · 5 goal rounds (13 lessons)

---

## The determination

> **No strategy in this project's search survives to the standard the project set
> for itself.**

The goal states: *"Accept and report 'no strategy survives' as a valid terminal
outcome if the evidence supports it."* The evidence supports it.

This is a **finding, not a failure to find something.** Six hypotheses were
rejected with stated reasons; the one surviving candidate was not abandoned on
intuition but failed a **pre-specified** statistical bar; and the mechanism behind
its apparent success is understood and quantified.

---

## What was searched

| # | hypothesis | verdict | reason |
|---|---|---|---|
| 1 | MA200 exposure management | ❌ | placebo indistinguishable from random de-risking (BTC p=0.435) |
| 2 | Cross-sectional momentum (47 pairs) | ❌ | 66% CAGR but −89% drawdown + unmeasured survivorship bias |
| 3 | Vol targeting / trend filter | ❌ | drawdown gain almost entirely mechanical |
| 4 | Volume / OBV / VWMA | ❌ | **0.017 Sharpe** — nothing; apparent edge was *speed*, not volume |
| 5 | Funding rate | ❌ | contrarian −0.335 ΔSharpe; momentum fails Bonferroni; negative incremental |
| 6 | **SMA-50 exposure (BTC, 15y)** | ❌ **terminal** | fails selection-aware tests (below) |
| 7 | H-D: VR predictive | ❌ | P3 failed — pre-registered, not re-tuned |
| 8 | H-E ensemble / H-F parameter-free | ❌ | no positive OOS edge; degenerate |

Also tested and rejected as *domains*, not strategies: crypto majors cross-section,
US equities (0/4 out-of-domain), Binance tokenized stocks (mechanism absent).

---

## Why the final candidate failed

SMA-50 (`Close > SMA(50)` → 100%, else 50%) had real strengths: Sharpe 1.451 vs
1.266 buy & hold, drawdown −74% vs −85%, placebo p=0.002, and a **temporally
stable** edge (jackknife +0.154…+0.237).

It failed on **selection**:

| test | result |
|---|---|
| Deflated Sharpe, full ledger (N=176) | **0.9435** < 0.95 required |
| MinBTL at N=176 | needs **15.5y**, have **14.6y** → SHORT |
| Reality check, BTC (both metrics) | p = **0.072 / 0.076** |
| Reality check, pool | p = **0.086 / 0.040** (latter fails Bonferroni 0.0125) |
| Clean train-only selection | positive OOS edge in **0/6** BTC splits |
| Train/test split | BTC **+0.024**, pool **−0.001** |
| Ensemble / parameter-free | no positive OOS edge; degenerate |

**8 independent tests, none favouring the candidate.**

### The single most important measurement

Ignoring selection: p ≈ **0.012–0.020**.
Pricing selection: p ≈ **0.040–0.086**.

> **The grid search inflated the apparent significance by roughly 4–6×.**

That is the quantified cost of searching — measured on my own work rather than on
someone else's.

---

## What was actually learned

The rejection list is the deliverable. Each rejection has a mechanism:

* **Trend rules need return persistence.** Crypto: VR(20) = 1.19 (trending).
  Equities: 0.84 (mean-reverting) — which is *why* the same rule fails 0/4
  out-of-domain. The mechanism **correctly predicted** an out-of-domain failure.
* **Volume carries no incremental information** over price. Isolating window from
  weighting reduced the apparent effect to 0.017 Sharpe.
* **Funding rate is not a tradable signal** in either direction.
* **Drawdown reduction is largely mechanical** — holding less achieves it without
  a signal. Verified: the timing edge is exposure-invariant across five bands.
* **CAGR can be manufactured; drawdown cannot be timed away.**
* **Selection is the dominant confound**, not noise. It inflated p by 4–6× here.

---

## The methodological result (most transferable)

The most valuable output is the **lessons ledger** (`LESSONS.md`) — 13 documented
errors, each with the rule that prevents recurrence. Highlights:

| | error | rule |
|---|---|---|
| L1 | added sampling frequency for power | only calendar years buy power (Lo 2002) |
| L3 | compared two rules differing in two ways | vary one thing at a time |
| L4 | counted 20 assets as 20 trials | count **effective** bets (~2.6) |
| **L5** | **selected the parameter on the full sample** | **freeze the split before selecting** |
| L8 | reported turnover as a trade count | reconcile related metrics arithmetically |
| L9 | over-read one split as a general law | repeat across splits, report the range |
| L10 | built a holdout that wasn't independent | ask what it is independent *of* — at selection |
| L11 | blamed the checker for my harness bug | suspect the harness first |
| L12 | quoted the wrong statistic's power figure | state which statistic applies |
| **L13** | **polished a quantity that changed no decision** | **establish order of magnitude, then stop** |

**L5 is the central one.** I identified selection bias in six other studies before
committing it myself in the seventh — then caught it only because the user asked
whether I had run a clean split.

### Two measured surprises

1. **Effective independent bets.** 20 correlated crypto majors ≈ **2.6** trials.
   109 US equities ≈ **5.7**. Nominal counts overstate evidence by ~√(N/N_eff).
2. **The selection penalty is 4–6×**, measured directly.

---

## What is NOT claimed

* Not claimed: the edge is exactly zero. The claim is that the evidence cannot
  distinguish it from what searching produces.
* Not claimed: the VR mechanism is wrong. It is supported and made a correct
  out-of-domain prediction.
* Not claimed: the strategy loses money. Its absolute 14.6-year Sharpe was 1.451
  with better drawdown than buy & hold — but that is largely **mechanical** (less
  exposure), available without any signal.

---

## Status of artifacts

**Not deployed. No real money.** The dry-run instance holds one paper trade; the
forward protocol is frozen with its criterion checker verified (6/6 self-test)
and currently reports **INSUFFICIENT_DATA** (1 day).

The forward test remains valid *as an implementation check* — it resolves in
weeks and needs no power argument. It cannot settle the edge (needs ~10–20 years;
see `findings-power-analysis.md`).

| artifact | purpose |
|---|---|
| `LESSONS.md` | 13 errors + 17 standing rules — **read before new research** |
| `findings-terminal-test.md` | the decisive DSR + reality-check results |
| `FORWARD-PROTOCOL.md` | frozen protocol with failure criteria |
| `RUNBOOK.md` | full index of all 20 findings docs |
| `tools/objective_gate_check.py` | replays the historical gates |
| `tools/reality_check_generalized.py` | the selection-aware test |

---

## If work resumes, what would be different

Stated so a future attempt does not repeat this search:

1. **Pre-register before touching data** — window, horizon, metric, and
   falsification criteria.
2. **Use a data environment with real statistical power.** 14.6 years of daily
   crypto cannot resolve a +0.17 Sharpe paired edge (~10–20y needed). The
   handoff's SPY (33.6y) is a better-powered setting for equity risk questions.
3. **Count trials continuously** and compute MinBTL **before** running the grid.
4. **Fail fast.** If a candidate does not beat its matched control out-of-sample
   on the first clean split, stop rather than probing variations.
5. **Treat "no edge" as the default hypothesis**, not the disappointing one.

---

## Reproduce the terminal result

```powershell
.\.venv\Scripts\python.exe tools\deflated_sharpe_decisive.py
.\.venv\Scripts\python.exe tools\reality_check_generalized.py
.\.venv\Scripts\python.exe tools\objective_gate_check.py
```
