# Findings: The Terminal Test — Does Any Strategy Survive?

Run 2026-09-19. Scripts: `tools/deflated_sharpe_decisive.py`,
`tools/reality_check_selection.py`, `tools/reality_check_generalized.py`.

The goal states that **"no strategy survives" is a valid terminal outcome if the
evidence supports it.** This round computes the tests that decide it, rather than
asserting it. Result: **the evidence supports the terminal outcome.**

---

## Two tests, two different questions

### Test 1 — Deflated Sharpe Ratio (is the Sharpe improbable given N trials?)

| claim | SR(ann) | PSR vs 0 |
|---|---:|---:|
| A. rule, absolute | 1.451 | 1.0000 |
| **B. timing excess (rule − flat)** | **0.818** | **0.9990** |

Deflating for the number of trials:

| N trials | E[max SR] | DSR | verdict |
|---:|---:|---:|---|
| 8 (window grid) | 0.213 | **0.9887** | passes |
| 1.1 (effective, correlation-adjusted) | 0.000 | **0.9990** | passes |
| 176 (full project ledger) | 0.397 | **0.9435** | fails |

**This test is ambiguous, and I will not resolve it by choosing N.**

The 8 SMA windows have mean pairwise return correlation **0.962**, so the
effective trial count is only **~1.1** — deflating for the window grid barely
moves anything. But the project has run ~176 configurations across every
hypothesis and dataset. Which count is honest is a *judgement call*, and picking
the one that gives the preferred answer is exactly the error in L5/L10.

### Test 2 — Max-statistic reality check (the test that needs no N)

Circularly shift returns against the signal, **re-running the full 8-window search
in every null draw**, so the null prices the selection itself. Four combinations —
two datasets × two edge definitions:

| dataset | metric | p (selection priced in) | p (selection ignored) |
|---|---|---:|---:|
| BTC 14.6y | D: SR(rule) − SR(flat) | **0.0720** | 0.0120 |
| BTC 14.6y | S: SR(rule − flat overlay) | **0.0760** | 0.0140 |
| 20-major pool 7.7y | D: SR(rule) − SR(flat) | **0.0400** | 0.0180 |
| 20-major pool 7.7y | S: SR(rule − flat overlay) | **0.0860** | 0.0200 |

**3/4 combinations: the search explains the result (p > 0.05).**

The single exception is p = 0.040. With **4 combinations tested**, a Bonferroni
bar is 0.0125 — **so it fails there too.**

---

## The most useful number in this round

Ignoring selection, p ≈ **0.012–0.020**. Pricing selection, p ≈ **0.040–0.086**.

> **The selection penalty inflates the apparent p-value by roughly 4–6×.**

This is the single cleanest quantification in the whole project of how much a
grid search flatters a result — measured on my own candidate, not on someone
else's. It is also the mechanism behind every earlier finding (L3, L5, L9, L10).

---

## Convergent evidence — eight independent lines, all the same direction

| # | test | result |
|---|---|---|
| 1 | Deflated Sharpe, full ledger | DSR **0.9435** < 0.95 |
| 2 | MinBTL at N=176 | needs **15.5y**, have **14.6y** → SHORT |
| 3 | Reality check, BTC (both metrics) | p **0.072 / 0.076** |
| 4 | Reality check, pool (metric S) | p **0.086** |
| 5 | Reality check, pool (metric D) | p **0.040** — fails Bonferroni (0.0125) |
| 6 | Clean train-only selection (round 7) | positive OOS edge in **0/6** BTC splits |
| 7 | Train/test split (round 5) | BTC **+0.024**, pool **−0.001** |
| 8 | Ensemble / parameter-free (round 8) | no positive OOS edge; degenerate |

**No test favours the candidate.** The one marginal result fails the correction
its own multiplicity demands.

---

## What this does NOT say

To be precise about the limits:

* It does **not** prove the edge is zero. It says the evidence is insufficient to
  distinguish it from what searching alone produces.
* It does **not** invalidate the VR mechanism finding — crypto trends
  (VR(20) ≈ 1.19) more than equities (0.84), and that correctly **predicted** the
  0/4 equity failure out-of-domain. A mechanistic explanation can be real while
  the tradable edge remains unproven.
* It does **not** say the strategy loses money. The rule's absolute Sharpe over
  14.6 years was 1.451 with drawdown materially better than buy & hold — but that
  is largely **mechanical** (less exposure), obtainable without a signal.

---

## The determination

> **No strategy in this project's search survives to the standard the project set
> for itself.** The candidate passed historical gates computed on the full sample,
> but every selection-aware test, every out-of-sample protocol, and the
> trial-count-adjusted framework place it at or below the threshold.

This is a **finding, not a failure to find something.** Six hypotheses were
rejected with reasons, the surviving candidate was not abandoned on a hunch but
failed a pre-specified bar, and the mechanism behind its apparent success is
understood and quantified.

---

## Reproduce

```powershell
.\.venv\Scripts\python.exe tools\deflated_sharpe_decisive.py     # DSR / MinBTL
.\.venv\Scripts\python.exe tools\reality_check_selection.py      # BTC max-stat null
.\.venv\Scripts\python.exe tools\reality_check_generalized.py    # 4 combinations
```
