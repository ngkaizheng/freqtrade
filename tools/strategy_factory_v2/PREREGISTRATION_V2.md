# Strategy Factory V2 — frozen pre-registration

**Spec version: `2026-09-26-v2-regime-derivatives`**

This document is written **before any V2 conditional-return result exists**. It
is the contract that the Phase C/D code must match. Result-driven changes
require a new spec version and a new run directory; they never edit this file or
rewrite an earlier run.

Its machine-readable mirror is
[`../strategy_factory_v2/spec.py`](../strategy_factory_v2/spec.py) and
[`hypotheses.py`](../strategy_factory_v2/hypotheses.py). If the two ever
disagree, that is a bug — fix the code to match this document and bump the
version.

---

## 0. What V2 is for

> Identify economically interpretable crypto market conditions that demonstrate
> statistically meaningful, cost-adjusted, out-of-sample edge and survive
> forward testing.

V2 is **not** looking for the strategy with the best historical return. It
optimises for **robustness**. "No survivors" is a valid and complete result.
Nothing in this system may manufacture a winner.

The V1 MVP (`tools/strategy_factory/`, run `full-mvp-20260925`) executed 400
configurations across 4 price-only families and produced **zero survivors**. V2
does not modify, re-run or reinterpret that result.

---

## 1. Isolation rules

| Rule | Enforcement |
|---|---|
| `freqtrade/` core is never modified | V2 imports nothing from it |
| `tools/strategy_factory/` (V1) is never modified | V2 is a separate package |
| `user_data/strategy_factory_runs/full-mvp-20260925/` is never touched | V2 writes only under `.../v2/` |
| Market data is never modified | Audits are read-only; a test asserts source bytes and mtime are unchanged |
| V2 never imports V2 through the V1 package alias | separate top-level package |

V2 **reuses** (imports, never modifies): `CostScenario` from
`tools.strategy_factory.models` and the statistical functions in
`tools.strategy_factory.validation` (`probabilistic_sharpe`,
`deflated_sharpe`, `white_reality_check`, `monte_carlo_equity`,
`effective_trial_count`, `make_folds`, `filter_trades`).

---

## 2. Environment facts (recorded, not assumed)

These were measured, not inferred, and they constrain what is testable.

| Fact | Consequence |
|---|---|
| `pytest` is **not installed** in `.venv` | Tests run under `tools.strategy_factory_v2._testrunner`. No result may be reported as "pytest passed". |
| There is **no network access** | No dataset can be downloaded; no dependency can be installed. |
| Python 3.11.9, pandas 3.0.5, numpy 2.4.6 | pandas 3 removed the `'m'` minute offset alias; V2 uses explicit `'min'`. |
| Funding is **8-hourly**, not 1-hourly | Funding features are built on the event stream, not on a 1h grid. |
| No `open_interest`, `taker_buy/sell_volume`, `index_price` on disk | 32 of 92 hypotheses are **BLOCKED**. |

---

## 3. Preregistered parameters

No value below may be changed after results are inspected. The plan explicitly
forbids a generic parameter optimiser; V2 contains none, and running a grid
such as `EMA 19/20/21/22` and selecting the best profit factor is forbidden.

### 3.1 Timeframes

| Role | Values | Why |
|---|---|---|
| Discovery cross-product | `15m`, `1h` | a 5m bar closes exactly on the 00:00/08:00/16:00 funding settlements, so a 5m grid aliases the funding event stream |
| Confirmation (survivors only) | `5m` | evaluated after screening, not across the full cross-product |
| Execution simulation | `1m` | never used for alpha discovery |
| Optional, if data appears | `30m`, `4h` | not present on disk today |

Sizing the cross-product to two timeframes keeps the registry inside the plan's
50–100 band. This was decided **before** any result, and is the kind of decision
that would be impossible to make honestly afterwards.

### 3.2 Feature windows

| Feature | Windows |
|---|---|
| Returns | 1, 3, 6, 12, 24, 48 bars |
| ATR | 14, 30, 60 |
| Realised volatility | 30, 60, 120 |
| EMA | 20, 50, 100, 200 |
| Open interest | 30, 60, 120, 288 bars |
| Taker flow | 5, 15, 30, 60 bars |
| VWAP / range / rolling high-low | 48 bars |
| Percentile window | 288 bars |
| Funding warm-up | 30 settlements (10 days at 8h) |

### 3.3 Forward horizons

6, 12, 24, 48 and 96 bars, plus MAE and MFE over the same windows. Horizons are
undefined on the final bars of a frame by construction — there is no future to
measure, and a test asserts it.

---

## 4. Regime definitions

All cut points are percentiles on the symbol's **own trailing** distribution,
except the trend, which is classified on an already-normalised score.

| Regime | States | Rule |
|---|---|---|
| Trend | `STRONG_DOWN`, `WEAK_DOWN`, `NEUTRAL`, `WEAK_UP`, `STRONG_UP` | normalised score against cuts `(-1.0, -0.25, 0.25, 1.0)` |
| Volatility | `LOW_VOL`, `NORMAL_VOL`, `HIGH_VOL`, `EXTREME_VOL` | percentile cuts `20 / 80 / 95` |
| Liquidity | `LOW_LIQUIDITY`, `NORMAL_LIQUIDITY`, `HIGH_LIQUIDITY` | volume percentile cuts `20 / 80` |
| Open interest | `OI_LOW`, `OI_NORMAL`, `OI_HIGH`, `OI_EXTREME` | percentile cuts `20 / 80 / 95` |
| Funding | `FUNDING_NEG_EXTREME`, `FUNDING_NEG`, `FUNDING_NEUTRAL`, `FUNDING_POS`, `FUNDING_POS_EXTREME` | percentile cuts `5 / 25 / 75 / 95` |

### 4.1 Why the trend is the exception

The trend score is a volatility-normalised blend (equal weight) of the 24-bar
move and the 50/200 EMA spread. It is already dimensionless, so absolute cuts
are meaningful and need no per-symbol calibration.

A trailing percentile would actively misclassify a sustained trend: a slowly
rising trend makes its own recent history look ordinary, so it sits near the
50th percentile of its own tail. Measured on real BTC data, a market whose score
averaged **+3.3 standard deviations** was labelled bullish on only **29%** of
bars — a raging bull market classified as `NEUTRAL`. Percentiles remain correct
for raw-unit quantities (open interest, funding, volume) where cross-symbol
comparability is the goal.

### 4.2 `UNKNOWN` is a real state

Where a regime's input does not exist — no open-interest file, for example — the
state is `UNKNOWN` for every bar. It is **never** defaulted to a middle bucket.
A missing feed that silently reports `OI_NORMAL` would let an absent dataset
look like a measured market state.

---

## 5. Data policy

| Rule | Enforcement |
|---|---|
| Funding is an event, not an accrual | Charged only at observed settlements; `adverse_payer`, credits ignored |
| Funding is never forward-filled | The event stream is returned un-filled; `funding_rate_last` is a step function of the last published rate and is named accordingly |
| Missing data is never invented | Absent inputs produce NaN features and a `False` availability flag |
| Basis needs a real index price | A mark-versus-perpetual spread is **not** accepted as a substitute |
| Stale source files are audited, not repaired | Cross-timeframe and funding cross-source disagreements are reported with counts and max spread |
| OI contraction is not called a liquidation | Without a liquidation feed, the family is named for what it measures |

**Funding source selection** (fixed now, before results): if several funding
files exist for a symbol, take the one with the most settlement events, breaking
ties by path. All candidates are audited and cross-compared regardless.

---

## 6. Causality contract

Two independent proofs run before any hypothesis may be evaluated, and the audit
fails loudly if either does.

1. **Structural availability** — `feature_timestamp <= decision_timestamp` for
   every column. A bar labelled `08:00` on a 5m grid is actionable at `08:05`;
   features are stamped at the close, not the label.

2. **Future-mutation invariance** — destroy every input from some cut index
   onward (reverse the price segment, add noise, rewrite future funding, OI,
   taker, index and the reference asset) and rebuild. Every value strictly
   before the cut must be bit-identical. The mutation changes the *shape* of
   the future, not its scale: a uniform rescale leaves returns, realised
   volatility and MA spreads invariant and would make the proof vacuous.

Plus an independent recomputation of the cross-asset join against a plain
`merge_asof`, because a join that is wrong positionally rather than temporally
survives future-mutation testing.

Each probe has a **negative control** in the test suite that injects a real
lookahead — a centred rolling window, a one-bar cross-asset lag, a reference
labelled from the future — and asserts the probe catches it. A probe that
cannot fail is not evidence.

---

## 7. Hypothesis registry

**92 hypotheses across the 15 families the plan specifies** (H1–H15), each
registered for both its long reading and its short mirror, because the plan
requires both directions to be researched and forbids assuming whether a
condition is continuation or exhaustion.

Every hypothesis carries: `hypothesis_id`, `family`, `economic_reason`,
`features`, `required_fields`, `timeframe`, `entry_definition`,
`exit_definition`, `thresholds`, `expected_direction`, `condition`,
`invalidation`, `preregistered`.

The economic reason is written **before** results. Conditions are declarative
text, not editable predicates.

### 7.1 Data-dependency gating

Every hypothesis declares the fields it needs. A hypothesis whose fields are
absent is reported `BLOCKED`. It is never approximated with a proxy, never
silently dropped, and never quietly re-scoped to a weaker question.

`price` is required unconditionally: every V2 hypothesis is a statement about a
forward return, so a basis extreme with no price series has nothing to measure.

**On the data available today: 60 testable, 32 BLOCKED.**

| Blocked family | Missing input |
|---|---|
| H1, H2, H5, H7 | `open_interest` |
| H6 | `open_interest`, `taker_buy_volume`, `taker_sell_volume` |
| H10 | `index_price` |

---

## 8. Execution and cost model

| Rule | Value |
|---|---|
| Signal | at candle close |
| Entry | next bar open |
| Same-bar stop vs target | **stop first** |
| Gap through stop | fills at the realistic gap price |
| Leverage | **1x** — a strategy must show positive expectancy at 1x first |
| Base cost | 5 bps fee + 1 bp slippage, per side |
| Stress cost | 10 bps fee + 3 bp slippage, per side |
| Robustness cost | 2x base |
| Funding | charged at observed events, adverse payer only, credits ignored |

Costs are never tuned to make a hypothesis pass.

---

## 9. Walk-forward design

| Parameter | Value |
|---|---|
| Train | 365 days |
| Validation | 90 days |
| Step | 90 days |
| Embargo | 4 hours |
| Minimum folds | 15 |
| Final holdout | 90 days, reserved before the experiment and never inspected for tuning |

The OOS period is never used for parameter selection. Trades crossing a fold
boundary are excluded from both adjacent windows. Selection happens on training
metrics only.

---

## 10. Statistical tests

| Test | Setting |
|---|---|
| Resamples | 2000 (a change must be recorded in the manifest with its reason) |
| Block bootstrap | circular, 7 days |
| Deflated Sharpe Ratio | participation-ratio effective trial count |
| Reality Check | block-bootstrap max-statistic, joint across candidates |
| Random seed | 20260926 |
| Multiple testing | hypothesis count, positive count and survivor count are all reported |

---

## 11. Sample and survivor criteria

**Minimum sample:** 200 total observations; 200 OOS trades for trade-based
strategies. Below that the verdict is `INSUFFICIENT_SAMPLE` and the hypothesis
is never ranked.

**A hypothesis becomes a survivor only if ALL of these hold:**

- OOS expectancy > 0
- stress-cost expectancy > 0
- 2x-cost expectancy > 0
- base profit factor > 1.05
- stress profit factor > 1.00
- minimum OOS sample met
- positive expectancy in ≥ 60% of OOS folds
- Deflated Sharpe Ratio > 0
- Reality Check p < 0.05
- no single fold contributes > 35% of total OOS profit

These may not be loosened after seeing results.

**Verdicts** are exactly: `PASS`, `FAIL`, `INSUFFICIENT_SAMPLE`,
`PROMISING_BUT_UNVERIFIED`. There is deliberately no "best" verdict and no
overall best-strategy ranking.

A survivor is a **RESEARCH SURVIVOR** until forward-tested. It never
automatically means a profitable live strategy.

---

## 12. Anti-overfitting rules

| Forbidden | Enforcement |
|---|---|
| A generic parameter optimiser | none exists in the code |
| Run → change threshold → rerun → keep the better | a changed hypothesis needs a NEW id and a new spec version |
| OOS used for parameter selection | selection is train-only |
| Final holdout used for tuning | reserved before the experiment |
| Costs tuned to pass | fixed in §8 |
| Manual winner selection, cherry-picking | single deterministic rule, no discretionary path |
| Forcing survivors | zero survivors is a valid result |
| Reporting a positive-PnL strategy without a hypothesis | §0 |

The registry size is asserted by a test. Adding a hypothesis after results
exist is how preregistration silently becomes post-hoc, so the count is frozen
at 92 for this spec version.

---

## 13. Forward validation

Minimum 30 days; 60–90 preferred depending on signal frequency. No live capital
at this stage. Kill-switch thresholds are documented in advance, not improvised
mid-run.

---

## 14. Reproducibility

Every run records `spec_version`, `random_seed`, `data_fingerprint`,
`data_hash` (per source file), `source_hash` and `code_version` in
`manifest.json`. Given the same data, spec version and seed, the result is
reproducible.

---

## 15. Phase status

| Phase | Scope | Status |
|---|---|---|
| A | Canonical data, audit, funding/OI/mark/index/taker/basis normalisation | **complete** |
| B | Feature engine, regime engine, causality and leakage tests | **complete** |
| C | Conditional return engine, baseline comparison, hypothesis evaluation | **not started — gated** |
| D | Walk-forward, cost stress, DSR, Reality Check, multiple testing | **not started** |
| E | Survivor extraction, strategy conversion, paper trading | **not started** |

Phase C may not begin until the data audit has been reviewed and the missing
derivatives inputs have been either acquired or formally accepted as a
permanent limitation on the registry.

---

## 16. Interpreting the result

V2 is successful even with **zero survivors**, provided that the data is
correct, the features are causal, the experiments are reproducible, the
hypotheses are properly tested and false positives are rejected.

The system always prefers:

> **NO TRADE** over **FALSE POSITIVE**
