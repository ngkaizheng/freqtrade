# R7 Resolved: the 22x Phase C / Phase D gap, and what it uncovered

**Date:** 2026-09-26
**Status:** root cause found, reproduced bit-exactly, code defects fixed
**Reproduction:** `tmp_r7/` (scratch, disposable)

---

## 1. The answer

Two stages measured the **identical per-signal quantity on the identical
signals** — same mask, same `fwd_ret_12`, same `side=-1`, same
`net_return(..., BASE_COST, 12, funding_rate_last)`, same 5 symbols, same
horizon. They differed **only in which signals entered the mean**.

`discovery_engine.evaluate_hypothesis` keeps a signal only if its
`decision_time` falls inside a walk-forward validation window
(`discovery_engine.py:316`). `make_folds` sets
`validation_start = frame_start + train_days` with `train_days = 365`, so the
**first 365 days of development are burned as training and never evaluated.**

`phase_d.candidate_returns` has no fold filter and uses every signal in the
frame.

For `H13_BTC_FILTER_1H_STRONG_UP_SHORT` the fold windows cover
2021-01-31 → 2025-10-07, which drops **540 of 994 signals (54.3%)** — of which
**470 are in calendar 2020 and lose −0.0073 each**.

| | in-fold | out-of-fold |
|---|---:|---:|
| n | 454 | 540 |
| mean net | **+0.006330** | **−0.004788** |
| gross | +0.007133 | −0.003752 |

Including the losers collapses +0.006330 → +0.000290. **Ratio 21.85x.**

The control (`STRONG_DOWN_SHORT`) looks consistent across stages only because
its excluded slice is *positive* (+0.0025). Same mechanism, not
sign-destroying.

### Reproduction, bit-exact

| quantity | recomputed | artifact |
|---|---|---|
| UP_SHORT in-fold n / mean | 454 / 0.006329756915488981 | 454 / 0.00632975691548898 |
| UP_SHORT full-region n / mean | 994 / 0.00028969381381600866 | 994 / 0.00028969381381600866 |
| DOWN_SHORT in-fold n / mean | 11453 / 0.004255774293781077 | 11453 / 0.004255774293781077 |
| DOWN_SHORT full-region n / mean | 13310 / 0.00400761436286811 | 13310 / 0.00400761436286811 |

The pipeline already knew: `trial_ledger.jsonl` records
`sample_count: 454, matched_bars: 994` for this id, and `matched_bars` was
never used in any gate, statistic or report field.

---

## 2. The finding that matters more than the 22x

**`multiple_testing.json` predates the code that claims to write it.**

The artifact's per-hypothesis rows contain only
`hypothesis_id, family, sample_count, mean_return, t_stat, p_raw,
p_bh_adjusted, p_bh_significant` — no IAT, no effective N, no `logic_hash`. The
current `phase_c.multiple_testing_analysis` writes all of those and *requires*
`dependence_checked` before setting `p_bh_significant`. So **the IAT deflation
was never applied to these results.**

On the actual 454-sample:

| | on disk | recomputed |
|---|---:|---:|
| IAT | — | **6.5261** |
| effective N | — | **69.57** (not 454) |
| t | 5.0669 | **1.9834** |
| p | 2.02e-07 | **0.02366** |

Re-running Benjamini–Hochberg over the real 88 p-values with the deflated value
substituted gives an adjusted p well above 0.05. **`gate_multiple_testing_adjusted`
would have been False and UP_SHORT would not have survived Phase C at all.**

The control survives: deflated t = 3.613 (IAT 8.071, eff N 1419).

**So the correct survivor count is 1, not 2** — and one of the two "holdout
deaths" was decided by a candidate that the R1 fix, applied at the time, would
already have eliminated at the screening stage.

---

## 3. Three code defects, all now fixed

| # | defect | fix |
|---|---|---|
| D1 | `discovery_engine` silently discarded out-of-fold signals and reported the survivors as `sample_count`. The discarded signals entered no statistic **and** failed the preregistered "200 total observations" test — counted nowhere. | `matched_signals_total`, `in_fold_signals`, `out_of_fold_signals`, `out_of_fold_fraction`, `out_of_fold_expectancy` now recorded per hypothesis. |
| D2 | `discovery.py:147` trimmed `region="development"` to **`validation_end`**, not `development_end`. The holdout guard only refuses timestamps ≥ `holdout_start`, so it passed silently. Consequence: Phase C fold 18 lay **entirely inside the validation region**, and Phase D's `validation_n=3` for UP_SHORT is **bit-identical to Phase C fold 18**. The validation sample was already inside the discovery statistic. | Trim to `development_end`. |
| D3 | `discovery_engine:420` `"enough_folds": len(valid_folds) >= 3` against a preregistered `min_folds: 15`. | `len(folds) >= WALK_FORWARD_V2.min_folds`. |

Tests: `tests/tools/test_strategy_factory_v2_calibration_fixes.py`, 14 tests
covering R1/R4/R5/R7. Suite **243/243**.

---

## 4. Systemic findings — the same defects touched all 88 hypotheses

- **Fold-restriction is universal.** The headline/full-region ratio ranges
  **0.457 → 0.974** across all 88, and all 88 headlines reconstruct from their
  fold rows to <1e-16. Worst affected: H13 1H STRONG_UP_SHORT (0.457),
  H3_FUNDING_EXTREME_1H_P95 and 15M_P95 (0.489), H13 15M STRONG_UP_SHORT (0.632).
- **Single-fold dependence.** Fold 0 (2021-01-31 → 2021-05-01, the alt-coin
  peak) alone supplies >35% of fold P&L for **25 of 88** hypotheses, and
  **9 of 88 change sign** when fold 0 alone is removed — including
  `H3_FUNDING_EXTREME_1H_P95_SHORT` (+0.006926 → −0.005278) and
  `H12_CROSS_ASSET_DIVERGENCE_1H_LONG` (+0.000008 → −0.002133).
  The `max_single_fold_profit_share` gate caught most, but not the two H13
  survivors.
- **`positive_fold_fraction` drops zero-trade folds.** UP_SHORT scores 11/15 =
  0.733; over all 19 folds it is 11/19 = 0.579 and **would fail** the 0.60
  gate. The preregistration says "≥60% of OOS folds" and does not say whether
  empty folds count; the implementation excluded them from both numerator and
  denominator, which is the choice that passes.
- **Year tables omit the year the headline includes.** `phase_d.DIAGNOSTIC_YEARS
  = 2021..2025`, so the 470 losing 2020 signals are in `development_n` but
  absent from the year diagnostics. Phase C's `yearly_pnl` is keyed by
  fold-start year, so it has no 2020 key at all and reports
  `positive_year_fraction = 1.0` from a sample that structurally cannot contain
  2020.
- **Annualisation is hard-coded to 15m** (`discovery_engine:142,144`,
  `sqrt(365*24*60/15) = 187.19`) for every timeframe, inflating 1h Sharpe by
  ~2x. Shared by both stages, so not the cause of the gap, but neither Sharpe
  is interpretable as reported.
- **Preregistered rule unimplemented:** §9 "trades crossing a fold boundary are
  excluded from both adjacent windows". `in_window` tests only `decision_time`.
  Measured impact for both H13 candidates: **0 crossing signals** — the rule is
  unimplemented but cannot be shown to have mattered here.

---

## 5. What was not determined

Whether the Phase C run-time source applied IAT deflation and simply failed to
serialise the fields, or never applied it. The artifact proves the *file* lacks
them and that its `p_bh_significant` is inconsistent with the current
`phase_c.py` logic; it does not prove what executed. Settling it needs the
Phase C stdout log or an archived copy of `phase_c.py` as of 07:33 on
2026-09-26. `tools/` is untracked in git, so there is no history to arbitrate.

**The recomputed IAT of 6.5261 is the number that would have been used.**

---

## 6. Consequence for the record

Phase E already read the holdout for both candidates (UP_SHORT 27 signals at
−0.00155; DOWN_SHORT 2,655 at −0.00232), so **no live decision was damaged** —
the two-stage design did its job at the last gate.

But the E#1 headline numbers for the other 87 hypotheses, and all 17
`p_bh_significant` marks, rest on the same fold-restricted sample and the same
un-deflated p-values. The correct reading of E#1 is:

> One candidate had a real, dependence-corrected development effect
> (`STRONG_DOWN_SHORT`, deflated t = 3.61). It failed the holdout. The other
> survivor should not have been one.

That is a **cleaner and more defensible** negative than the one originally
reported, and it is the version to carry forward.
