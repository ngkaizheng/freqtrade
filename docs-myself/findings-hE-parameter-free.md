# Findings: H-E / H-F — Removing the Un-selectable Parameter

Run 2026-09-19. Scripts: `tools/hE_parameter_free.py` (pre-registered),
`tools/selection_contamination_test.py`. Pre-registration is in the first script's
header, written before results.

**Outcome: split verdict. H-E passes on BTC, fails on the pool. H-F is
degenerate — and one of my two predictions about it was wrong.**

---

## Motivation (from round 7)

Round 7 established: the SMA edge is **temporally stable for a fixed window**,
but the **window cannot be chosen out-of-sample** (BTC: in-sample-best window
gave a positive OOS edge in **0/6** splits). So the binding problem is the
**selection step**, not the signal. That suggests two structural fixes.

---

## H-E — Ensemble (no selection at all)

```
exposure_t = mean over w in {10,20,30,50,75,100,150,200} of
             [ 1.0 if close_t > SMA_w else 0.5 ]
```

Nothing is selected, so nothing can be overfit *by* selection.

| | BTC | pool |
|---|---:|---:|
| mean exposure | 0.784 | 0.763 |
| full-sample edge | +0.179 | +0.164 |
| **E1** jackknife range | **+0.155 … +0.192** ✅ | **+0.092 … +0.213** ✅ |
| **E2** OOS mean edge | **+0.027** (4/6 positive) ✅ | **−0.033** (1/6 positive) ❌ |
| **E3** beats mean single window | +0.027 vs +0.017 ✅ | −0.033 vs −0.036 ✅ |
| **E4** OOS CI excludes 0 | [−0.066, +0.318] ❌ | [−0.122, +0.312] ❌ |
| **H-E** | **3/4** | **2/4** |

Per the pre-registration, H-E required **E1 AND E2**. BTC passes; **the pool
fails**. So H-E is **not supported** as a general result.

Note E1 is the strongest part: ensembling removes the window-selection problem
and produces a *stable* edge in both datasets. But stability in-sample did not
translate to a positive out-of-sample edge on the pool.

## H-F — Expanding mean (truly parameter-free)

```
exposure_t = 1.0 if close_t > mean(close_0 .. close_{t-1}) else 0.5
```

No window, no threshold. **I predicted in advance it would degenerate**:

| prediction | BTC | pool |
|---|---|---|
| F1 mean exposure > 0.95 | ✅ 0.978 **CONFIRMED** | ❌ 0.920 **REFUTED** |
| F2 \|edge\| < 0.05 | ✅ −0.024 **CONFIRMED** | ✅ −0.047 **CONFIRMED** |

**My F1 prediction was wrong on the pool** (0.920, not >0.95). Recorded.

The substantive result holds on both: **the edge is ~zero or negative**. Removing
the parameter removed the signal with it. "Parameter-free" is not free.

---

## The tension this created, and my attempt to resolve it

The ensemble (+0.027 BTC) looked **worse** than SMA-50 (+0.160 BTC) out-of-sample.
If SMA-50 genuinely transfers better, my whole "the window cannot be chosen"
thesis collapses.

`tools/selection_contamination_test.py` ranked all 8 windows by OOS edge per split:

| dataset | SMA-50 mean OOS rank | range | best OOS in |
|---|---:|---|---:|
| BTC | **1.8 / 8** | 1–5 | **4/6 splits** |
| pool | 3.3 / 8 | 1–8 | 2/6 splits |

**On BTC this does not support the contamination story.** SMA-50 ranks
consistently high out-of-sample — 1st in four of six splits.

### But the rank test is itself contaminated, and I have to say so

The test periods (2020, 2021, … 2025 onward) are **subsets of the full sample**
that SMA-50 was selected on. A window chosen with knowledge of the whole series
will tend to look good in subsets of it **mechanically**. So this test **cannot**
separate "50 happens to be a good window" from "50 was chosen on data containing
these periods."

**Therefore it neither confirms nor refutes the contamination argument.** I am
not going to use it as support for my thesis, and I am not going to dismiss the
BTC result either.

### Why a clean discrimination is unavailable here

A genuinely clean test needs a period that influenced **no** window choice. For
BTC, the round-2 grid searched the **entire** 15-year Bitstamp series, so no such
period exists. The only clean evidence I have is round 7's protocol (select on
train only, test on held-out):

* BTC: train-only selection picks **SMA-20**, and the train-best window gave a
  positive OOS edge in **0/6** splits
* pool: train-only selection picks **SMA-50**, test edge **−0.027**

Both are consistent with "selection does not transfer," and neither involves
looking at the test period. **That remains the cleanest evidence, and it favors
the thesis.**

### Honest bottom line on the tension

* The contaminated rank test shows BTC's SMA-50 looking good OOS — a **genuine
  caveat I cannot dismiss**.
* The clean train-only protocol shows selection failing to transfer.
* These are not reconcilable on this data. **I am leaving it unresolved rather
  than picking the answer I prefer.**

---

## Verdict

| | result |
|---|---|
| **H-E ensemble** | ❌ **not supported** (BTC 3/4, pool 2/4; E2 failed on the pool) |
| **H-F expanding mean** | ❌ **degenerate** — edge ≈ 0 or negative on both |
| Contamination question | **unresolved** — clean test not possible on this data |

**Neither fix rescues the strategy.** Ensembling gives stability without a
positive out-of-sample edge; going parameter-free removes the signal.

---

## Consequence for the candidate

Unchanged in substance, and now with a clearer boundary:

> BTCSmaTrend passed the historical gates. Its edge is temporally stable for a
> fixed window. **Whether its window can be chosen in advance is unresolved** —
> the clean protocol says no, a contaminated rank test says yes on BTC.
> **Eligible for forward validation only. Must not be traded.**

The forward test remains the only way to settle it, which is exactly why it
matters: a **pre-committed** SMA-50, run forward, would produce genuinely clean
evidence that no amount of historical slicing can produce.

---

## Trial ledger

| round | trials |
|---|---:|
| 1–6 | 164 |
| **7 (this: H-E 4 predictions × 2 datasets, H-F 2 × 2)** | **12** |
| **total** | **~176** |

---

## Reproduce

```powershell
.\.venv\Scripts\python.exe tools\hE_parameter_free.py
.\.venv\Scripts\python.exe tools\selection_contamination_test.py
```
