# PRE-REGISTRATION — can a walk-forward ML model improve the EXIT?

**Frozen: 2026-09-28, before the script was written and before any model was fit.**
Author: agent session.

---

## 1. The question, and why it is narrow on purpose

The previous session decomposed the leaderboard strategy and found:

- the **entry** has a real out-of-sample conditional lift (+48.02 bps, 1h, t_block 2.08),
- the **upstream exit model destroys it** (90 of 120 exits lost money, −37.48%),
- a **fixed 1h hold** recovers +51% of that damage (per-trade +0.320% → +0.483%).

So the open question is not "can ML find alpha". It is: **given that the entry fires,
can a model choose the exit better than a fixed 1h hold?**

That is a well-posed supervised problem with a clear metric, it is exactly where the
leak was found, and it does not re-open the alpha search.

## 2. Prior probability — stated against, and it is strong

This test is registered **expecting failure**. Three independent lines already bear on
it and all three point down:

1. **Fayez Junior (SSRN 6701738):** an XGBoost ranker with rank IC **+0.0243 (t = 3.55)**
   returned **net Sharpe −2.91 and −95.6% max drawdown.** A significant IC alongside a
   losing book is the expected shape of an overfit ranker (§3.6).
2. **Bailey, Borwein, López de Prado & Zhu 2016 (*JC*, peer-reviewed):** on a
   **random walk**, an 8,800-node grid produced IS Sharpe 1.27 / PSR 2.83 with
   **PBO 55%** and ~53% of out-of-sample Sharpes negative.
3. **freqtrade's own docs:** `continual_learning` *"has a high probability of
   overfitting / getting stuck in local minima while the market moves away from your
   model"*, and it is offered *"primarily for experimental purposes"*.

Additionally, Freqle **excludes ML/FreqAI strategies from its own 5,330-strategy
League** for lack of compute, so there is no leaderboard evidence either way.

**FreqAI itself is not installed in this checkout** and is a wrapper around libraries
that are present (sklearn 1.7.2, lightgbm 4.6.0, xgboost 3.1.1, catboost 1.2.8,
torch 2.9.1+cpu). Its methodological contribution — walk-forward retraining with label
purging — is implemented directly here so that label construction and the purge are
auditable rather than hidden behind a config.

## 3. Design, frozen

- **Population:** every `enter_long` signal of the control strategy
  (`NotAnotherSMAOffsetStrategy`, converted to v3), all 33 Binance spot pairs.
- **Label:** for each signal, `argmax` over the next **36 bars (3h)** of the *achievable*
  exit return, minus the realised return at a fixed **12 bars (1h)**. The label is
  therefore **the excess of the best possible exit over the fixed 1h hold** — a model
  can only score above the baseline by capturing something the 1h hold misses.
  Labels are computed only from bars **strictly after** the signal bar, and the final
  `horizon` bars of the sample are dropped so no label is truncated.
- **Features (all causal, all from data at or before the signal bar):** return over
  1/3/6/12/36 bars, the same for volume, ATR-normalised close, distance to EMA 9/21/50/200,
  RSI 4/14/20, EWO(50,200), rolling volatility at 12/36 bars, hour-of-day sin/cos, and
  the pair's own trailing 1h return.
- **Model:** LightGBM regressor, 300 trees, depth 4, learning rate 0.05, fixed seed.
  Chosen over deep learning because the sample is small and the claim under test is
  about the exit rule, not the model class.
- **Split — walk-forward, not random:** train on **2021-01-01 → 2026-01-01** signals,
  predict on **2026-01-01 → now** signals. The test set is disjoint in time from the
  training set and from the window on which the strategy was selected. **There is no
  random split and no shuffling, because both would leak the overlapping-horizon
  structure that the previous session already got wrong twice.**

## 4. The bar, frozen

The model is a **successor** only if, on the 2026 out-of-sample signals, ALL of:

- **M1** mean realised exit return under the model's choice **exceeds** the fixed-1h
  baseline by a margin that survives costs: the per-signal improvement must exceed
  **20 bps** (calm) — the bar is set at the *calm* end, not the COVID end, because
  35 bps would be too generous.
- **M2** the improvement is significant at **p ≤ 0.05** under a **block bootstrap on the
  time-sorted signal sequence** (block = 12 signals, 20,000 reps) — the estimator whose
  validity cost the previous session one false positive.
- **M3** **G4 analogue:** the model must beat the 1h baseline at **2 of 3** horizons
  measured ({1h, 2h, 3h} evaluation), not at exactly one.
- **M4** the model must not be a constant: the distribution of its chosen exit times must
  have at least 3 distinct values. A model that emits one number is a disguised
  constant-1h rule and does not count.

## 5. Falsification, stated before running

- **If the model does not clear M1–M4, that is the result and it closes the ML line for
  this entry.** It does not license trying XGBoost next, or a deeper net, or a different
  label — that is exactly the 92-hypothesis search that produced 0 survivors.
- If it clears M1–M2 but not M3–M4, it is reported as **a partial that failed its own
  robustness gate**, in those words.
- **A significant in-sample fit is not evidence and will not be reported as a result.**

## 6. Runtime note

33 pairs × 1825 days of 5m data with ~200-bar warmup. Feature build and label
construction are pure pandas/numpy over ~15.8M bars; the fit itself is seconds. Expected
wall time is minutes, not hours, and no GPU is required.
