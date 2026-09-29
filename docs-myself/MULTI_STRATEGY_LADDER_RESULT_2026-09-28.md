# Multi-strategy ladder — result and verdict

**Date:** 2026-09-28
**Pre-registration:** `docs-myself/PREREG_MULTI_STRATEGY_LADDER_2026-09-28.md`,
**frozen before any of these strategies was downloaded.**
**Harness:** `tools/leaderboard/ladder.py` (causality gate → entry lift → pre-registered bar).

---

## 0. VERDICT

**SURVIVORS: 0 of 3.** Two of the three are structurally broken — one cannot run at all
on a current engine, one peeks 100 bars into the future. The third is causal and has a
real out-of-sample effect, but **it does not clear the bar that was fixed before the
run**, and neither does the positive control.

**The user was right that one strategy is not a survey. Testing more is the right
instinct. What makes it informative is not the count — it is that the correction is
declared in advance, so that a survivor would mean something.**

| # | strategy | leaderboard rank | causality gate | OOS lift @ best horizon | verdict |
|---|---|---:|---|---|---|
| S0 | `NotAnotherSMAOffsetStrategy` | 10/12/20/31 | **PASS** 6/6 | +48.02 bps, t=2.08, **p=0.523** | **fails the pre-registered bar** |
| S1 | `ElliotV8_original` | 14/15 | **DEAD** — v2 file | not computed, by design | **void** |
| S2 | `DivergenceStrategy` | 02 | **LOOKAHEAD** — ARB, ATOM | not computed, by design | **void** |

Pre-registered bar: family-wise **α = 0.05/18 = 0.00278** (6 strategies × 3 horizons).

---

## 1. S1 `ElliotV8_original` — a leaderboard top-15 entry that cannot run

`INTERFACE_VERSION = 2`, writes the `buy`/`sell` columns, defines `populate_buy_trend`.
A v3 engine reads only `enter_long`/`enter_short` from `populate_entry_trend`, which
this file does not define, so the inherited no-op runs and **the strategy produces zero
trades with no error**.

This is not a marginal implementation detail. It is the **same trap already recorded for
`NotAnotherSMAOffsetStrategy`**, which is also v2 — and that one is ranked **four times**
in the public top 20. **Two of the top-15 entries I sampled cannot run unmodified on a
current freqtrade.** Their leaderboard numbers were produced by a conversion step
(Freqle's FAQ documents an automatic `strategy-updater` pass) that the published file
does not reflect.

The gate labelled this `DEAD` rather than `PASS with zero signals`, deliberately: a
strategy that cannot trade is not a strategy with no edge, and reporting it as the
latter would be the exact "silent dead signal" failure this repo keeps hitting.

## 2. S2 `DivergenceStrategy` — leaderboard #2, with a 100-bar lookahead

```python
for pivot in pivots:
    if pivot + self.maxbars < len(dataframe):          # maxbars = 100
        if dataframe['rsi'].iloc[pivot] > dataframe['rsi'].iloc[pivot + self.maxbars]:
            dataframe.loc[dataframe.index[pivot], 'enter_long'] = 1
```

**The entry is placed at bar `pivot` using an RSI reading from bar `pivot + 100`.** The
trade is opened in the past, 100 hours earlier, conditional on information from the
future. This is the textbook definition, and it is invisible to inspection unless you
look for it — the code reads like a divergence test.

The truncation gate caught it on 2 of 6 sampled pairs (ARB, ATOM); the other 4 happened
not to have a qualifying pivot in the shared region. **Because the gate runs BEFORE the
lift measurement, no lift is printed for this strategy at all.** A naive evaluation
would have reported a spectacular number — that is precisely why the gate was ordered
first.

Freqle's own FAQ documents the static checks that flag `argrelextrema`-style leaks and
explicitly says a strategy failing lookahead "**leaves the League entirely**". A
leaderboard **#2** entry does not leave. Either the leak is variant-specific and
escapes their lint, or the sweep is stale. Either way, the ranking is not evidence.

## 3. S0, the control — real effect, and it does not clear the bar

Causality **PASS on 6/6 pairs**. Out-of-sample (2026-01-01 → now), 33 pairs, 443
signals, block bootstrap on the **time-sorted** sequence:

| horizon | n | lift | t_BLOCK | p | after 35 bps | passes? |
|---|---:|---:|---:|---:|---:|---|
| 15m | 443 | +29.02 bps | 1.86 | 0.533 | −5.98 | no |
| **1h** | 443 | **+48.02 bps** | **2.08** | **0.523** | **+13.02** | **no** |
| 3h | 443 | +22.59 bps | 0.92 | 0.542 | −12.41 | no |

**The effect is real at the signal level and survives the worst measured cost — and it
still fails.** p = 0.523 against a required 0.00278. The raw t of 2.08 is the number
that looked encouraging in the previous session; under the correction that had to be
applied because I said I would test more, it is not enough.

Note the asymmetry that makes this a real finding rather than a technicality: **the
signal-level test has 443 observations and still misses the corrected bar, while the
traded portfolio has 120 and lands at p = 0.138.** Neither the effect's existence nor
its deployability is in doubt; its *size relative to the selection that produced it* is.

## 4. A structural finding about the field: it is lineages, not strategies

`ElliotV8_original` and `NotAnotherSMAOffsetStrategy` are **the same file template from
the same author (`@Rallipanos`)**. Both are: EMA-offset dip-buy + RSI fast/slow +
EWO(50,200) + a `reduce(|)` pair of entry conditions + trailing stop. They differ by
one hyperopt default (`ewo_low` −20.988 vs −19.988) and their stoploss (−0.35 vs −0.32).

**So the public top 20 is not 20 strategies. It is a handful of lineages, each cloned
across many repos** — which is exactly what the byte-identical rows already showed. My
S5 in the pre-registration was to be an explicit clone control; the lineage check found
the clone relationship *before* I had to run it.

**Consequence for "test more of the top 20":** the top 20 contains perhaps 3–5 distinct
mechanisms, and testing more rows of it is close to re-testing the same thing while
inflating the multiple-testing count. **The `btc_regime_filter` (2,873 of 5,330) and the
`@Rallipanos` SMA-offset stack are the two dominant lineages**, and the first is already
closed in this repo by Hurst/Ooi/Pedersen 2017 (*JPM*).

## 5. On "improve the popular ones"

That instinct produced the one real, reproducible gain of this session, and it is worth
keeping — with its ceiling stated:

`LeaderboardEntry1hHold` keeps S0's entry byte-for-byte and replaces its exit with the
horizon at which the lift was **measured** (1h, not tuned). Out-of-sample:

| | upstream exit model | 1h hold | change |
|---|---:|---:|---:|
| per-trade | +0.320% | **+0.483%** | **+51%** |
| total | +3.84% | **+5.79%** | **+51%** |
| max drawdown | 2.70% | **2.59%** | better |
| portfolio t_block | 1.043 | 1.110 | still not significant |

**+51% on a base that is not significant is still not significant.** Improving the
mechanics of a strategy does not manufacture the evidence that the strategy has an
edge. It is worth doing — it is how the leak was found, and the method generalises to
any strategy — but it is an engineering gain, not a validation.

## 6. What is now settled

- **Testing more of the leaderboard is not the missing piece.** The barrier is not
  sample-of-strategies, it is that the effect (t ≈ 2.1) is smaller than the selection
  that produced it (5,330 strong). Adding rows cannot fix that; only more *time* can.
- **The field contains at least one top-2 entry with a 100-bar lookahead and two top-15
  entries that cannot execute.** Any decision that cites "the community says X works"
  should be re-checked against a causality gate first.
- **The correct next measurement is not another strategy — it is more calendar.** At the
  observed ~161 signals/yr, clearing the corrected bar on the portfolio series needs
  roughly **4+ years** of forward data, and ~12 years at the signal level.
