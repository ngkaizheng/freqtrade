# ML exit model — CLOSED. Pre-registered, run, failed all four gates.

**Date:** 2026-09-28
**Pre-registration:** `PREREG_ML_EXIT_2026-09-28.md` (frozen before the script existed)
**Implementation:** `tools/leaderboard/ml_exit.py`
**Verdict: ML LINE CLOSED FOR THIS ENTRY.**

---

## 1. What was actually asked

Not "can ML find alpha". The previous session's decomposition found the entry has a real
out-of-sample lift and the **exit model destroys it**, and that a fixed 1h hold recovers
+51% of the damage. So the question was the narrow, well-posed one:

> given that the entry fires, can a model choose the exit better than a fixed 1h hold?

Registered **expecting failure**, with three priors already pointing down (Fayez
Junior's ranker with IC +0.0243 → net Sharpe **−2.91**; Bailey et al. 2016 *JC* on a
**random walk**, PBO 55%; freqtrade's own `continual_learning` overfitting warning).
FreqAI is not installed in this checkout and is a wrapper over libraries that are
present, so the walk-forward-with-purging was implemented directly — which also made
label construction and the purge auditable.

## 2. Setup

- **Population:** every `enter_long` signal of the control strategy, 33 Binance spot pairs.
  **6,880 training** signals (2021-2025) → **443 test** signals (2026, disjoint in time
  from both the training set and the window the strategy was selected on).
- **Label:** the excess of the **oracle best exit inside 3h** over the realised 1h
  return. A model can only score above baseline by capturing something the fixed hold
  misses. Truncated tail rows dropped so no label is partial.
- **Features:** ~24 causal features (multi-horizon returns and volume changes, distance
  to EMA 9/21/50/200, RSI 4/14/20, EWO, rolling vol 12/36, time-of-day sin/cos). All
  from data at or before the signal bar.
- **Model:** LightGBM regressor, 300 trees, depth 4, lr 0.05, fixed seed. No random
  split, no shuffling — both would leak the overlapping-horizon structure.

## 3. Results

| horizon | baseline (1h) | model | improvement | t_BLOCK | p | distinct actions | M1 | M2 |
|---|---:|---:|---:|---:|---:|---:|:-:|:-:|
| 12 (1h) | +48.30 bps | +48.30 | 0.00 | — | 1.000 | 1 | ✗ | ✗ |
| 24 (2h) | +48.30 | +61.64 | +13.34 | 0.90 | 0.445 | 1 | ✗ | ✗ |
| 36 (3h) | +48.30 | +23.36 | **−24.94** | −1.49 | 0.548 | 1 | ✗ | ✗ |

**M1 (improvement > 20 bps): 0/3. M2 (p ≤ 0.05): 0/3. M3 (≥2 of 3): FAIL.
M4 (≥3 distinct chosen actions): FAIL — per-horizon distinct = [1, 1, 1].**

**ML LINE CLOSED FOR THIS ENTRY.**

## 4. The two numbers that explain it better than the verdict does

```
baseline 1h hold on 2026 signals        +48.30 bps
ORACLE best exit within 3h              +143.23 bps   -> headroom +94.93 bps
ORACLE headroom measured in TRAINING     +248.67 bps
```

**The oracle headroom itself collapsed 62% out of sample** (248.67 → 94.93 bps) before
any model was fitted. The *achievable* advantage of a perfect exit is far smaller in
2026 than in 2021–2025. A model can at best capture the smaller number; this one
captured 13 bps of the 95 at 2h and went **negative at 3h**.

That is a stronger statement than "the model was bad". **The thing being modelled is
itself regime-dependent, and it is more regime-dependent than the model is flexible.**

`distinct = 1` at every horizon is the other tell: the fitted model emits a single
action, i.e. it is a constant-1h-hold rule wearing a gradient-boosting hat. M4 exists
precisely to catch that, and it fired.

## 5. What this does and does not license

**Closed:** ML as an *exit improver* for this entry. Per the prereg's falsification
clause, this does **not** license trying XGBoost next, a deeper net, a different label,
or a different horizon set. That is the 92-hypothesis search that produced 0 survivors.

**Still true and not affected by this failure:**

- The **entry lift stands on its own** (+48.02 bps, t_block 2.08, p = 0.523 — real at
  the signal level, not clearing its pre-registered bar).
- The **`LeaderboardEntry1hHold` improvement stands** (+51% per trade over the upstream
  exit) because it is a *measurement* — exit at the horizon where the lift was measured —
  not a model.
- Market making is closed separately, by arithmetic rather than by experiment
  (`MARKET_MAKING_ARITHMETIC_2026-09-28.md`): spread 0.80 bps against 20 bps of
  round-trip fees on spot, 0.11 bps against 4 bps on perps.

**A note on the four ways this session produced wrong-but-confident output**, all in the
repo's own §3 family and all caught rather than shipped:

1. The `distinct`/M4 line crashed on a `(443,)` vs `(3,)` broadcast — fixed and re-run.
2. A `.values` call on a numpy bool array.
3. A pandas boolean mask silently voiding the long-only control in the causality gate
   (earlier this session).
4. The pair-major block bootstrap that reported t = 2.81 instead of 2.08.

None were caught by reading the code. All four produced or nearly produced a normal-
looking table.
