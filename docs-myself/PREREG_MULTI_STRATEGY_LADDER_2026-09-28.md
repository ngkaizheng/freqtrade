# PRE-REGISTRATION — multi-strategy entry-lift test on the leaderboard field

**Frozen: 2026-09-28, BEFORE any of the strategies below was downloaded or run.**
Author: agent session, continuing the line opened in
`docs-myself/COMMUNITY_STRATEGY_REVIEW_2026-09-27.md`.

---

## 1. Why this exists, and what it is not

The previous session tested exactly **one** leaderboard strategy
(`NotAnotherSMAOffsetStrategy`) and found that its edge was in the entry while its
exit model spent it. The user is right that one strategy is not a survey of the field.

But testing more is **not** automatically more evidence. The leaderboard is itself a
maximum over 5,330 strategies, so its entrants are already survivors of a selection
procedure. Adding more leaderboard picks multiplies the selection count without adding
independent draws.

**Therefore the multiple-testing burden is fixed IN ADVANCE here, and it is the whole
point of this file.** N is declared, the correction is declared, and a strategy that
clears the corrected bar is worth deploying. A strategy that clears the uncorrected bar
is not.

## 2. N and the families — declared before download

**N = 6 strategies**, chosen to span **different mechanisms**, deliberately NOT to take
the top 6 rows (which are mostly clones of each other). Selection rule: pick the most
reproduced strategy from each distinct mechanism family visible in the public top 20.

| # | name | family | why included |
|---|---|---|---|
| S0 | `NotAnotherSMAOffsetStrategy` | EMA-offset dip-buy + RSI + EWO | already measured; kept as the **positive control** |
| S1 | `ElliotV8` | trailing-exit swing, long/short | different entry, same trailing exit pathology |
| S2 | `NASOSv6` | trailing-exit, 94% reported win | extreme win-rate claim to audit |
| S3 | `DivergenceStrategy` | RSI divergence | momentum-family, not dip-buy |
| S4 | `NowoIchimoku1hV2` | Ichimoku, 1h | trend-family on a different timeframe |
| S5 | one `E0V1E` variant | a clone of S0 | **deliberate negative control**: a known clone must NOT reproduce as independent evidence |

**S5 is the integrity check on the whole design.** If a clone of S0 passes the same bar
as S0, the bar is measuring lineage, not merit.

## 3. The measurement — entry only, which is what the last session learned

For each strategy, at each horizon h in {15m, 1h, 3h} expressed in its own timeframe:

```
lift = mean(forward return | entry signal) − mean(forward return | same pair, all bars)
```

Only `lift` is an edge. The baseline is drift and is subtracted.

- **Universe:** the 33 Binance spot pairs, data in `user_data/data_leaderboard/`.
- **Sample split:** 2021-01-01 → 2026-01-01 is IN-SAMPLE (this is the window every
  leaderboard rank was selected on). **2026-01-01 → now is the only admissible
  out-of-sample block.** A strategy that is impressive only in-sample has failed.
- **Cost:** 20 bps and 35 bps round trip, this repo's measured range (§1b).
  A lift that does not clear 35 bps has nothing to deploy.

## 4. The statistics, and the trap that has already been paid for twice

Significance is the **dependence-adjusted** statistic, and the one correct estimator
here is fixed now:

> **Block bootstrap over the signal sequence SORTED BY TIME**, block = 12 signals
> (one hour of overlapping holds), 20,000 resamples.

**Declared trap:** the previous session's first implementation concatenated the 33 pairs
**pair-major** and bootstrapped that. It is not a time-ordered series, the moving blocks
straddle unrelated instants, and it reported **t = 2.81 where the time-sorted version of
the identical quantity gives 2.08 and the traded portfolio gives 1.11**. Any implementation
that does not sort by time first is void.

The naive t is reported only to display the inflation.

## 5. The bar — fixed now, before any result

A strategy is a **SURVIVOR** only if, on the **out-of-sample block**, ALL of:

- **G1** best-horizon `lift` > **35 bps** (clears the worst measured cost)
- **G2** dependence-adjusted **t ≥ 2.0** at that horizon
- **G3** **p ≤ 0.05**
- **G4** the surviving horizon is not unique-and-lucky: the lift must stay positive at
  **both** neighbouring horizons (15m and 3h bracket 1h). A single-horizon spike is
  the signature of a search, not an effect.
- **G5** positive in **at least 2 of 3 calendar sub-blocks** of the OOS period
  (2026 H1 / 2026 H2 / the remainder) — guards against one lucky stretch.

## 6. The multiplicity correction — the point of the whole file

Searches performed: **6 strategies × 3 horizons = 18**, plus the 6 strategies' own
parameter sets as already published (each was selected by its author on data I have not
seen, so I do **not** re-select).

**The bar for a survivor is therefore raised to a family-wise level equivalent to
N_eff = 18**, i.e. a per-test significance equivalent to **Bonferroni-corrected
α = 0.05/18 = 0.00278**, which is **t ≥ 3.21** on a normal, and **≥ 2.9** after the
block bootstrap. I will report the bootstrap p-value and require **p ≤ 0.0028**.

**G2's raw t ≥ 2.0 is retained only as an intermediate diagnostic, not as a pass.**

## 7. Falsification, stated before running

- **If zero strategies clear the corrected bar** — which is this project's base rate
  (92 preregistered hypotheses, 0 survivors; three 5m families closed) — **that is the
  result, and it is reported plainly.** It does not trigger a new search.
- **If S5 (the clone control) clears the bar**, the whole test is void as designed and
  is reported as void.
- **If a strategy clears the corrected bar**, that is a **candidate**, not a deployment:
  it still owes a forward period on the traded portfolio, because the last session
  showed signal-level t = 2.08 can coexist with portfolio-level t = 1.11 when a slot cap
  selects the executed subset.

## 8. What I will NOT do

- I will not run a backtest per strategy and rank the backtests.
- I will not tune any strategy's parameters.
- I will not extend the family after seeing results. If a new promising family appears,
  it goes in a NEW pre-registration, not this one.
- `strategy-updater` will be run in an **isolated directory**. The last session's run
  rewrote 10 of this repository's research strategies despite `--strategy-path`
  (`strategyupdater.py:82` writes unconditionally), and all 10 were restored
  byte-identically from its backup. It will not be pointed at a shared tree again.
