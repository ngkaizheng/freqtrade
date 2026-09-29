# E#3 — cross-sectional trend on a wide perpetual universe: **FAIL**

**Date:** 2026-09-26
**Pre-registration:** `PREREGISTRATION_E3.md` (written before any result)
**Engine:** `e3_backtest.py` · **Diagnosis:** `e3_diagnose.py`
**Result:** `e3_result.json`

## Verdict

**FAIL, 1 of 8 pre-registered gates.** On the universe actually tested, the
construction loses money after costs, and it loses for a structural reason
rather than a marginal one.

## A near-miss that was a bug, and what it cost to find

The first run passed **8/8** with an annualised net Sharpe of **+5.85**. That
number is not a result; it is a symptom. The paper this implements reports a
Sharpe of roughly 1.3–1.9, so a 4x-better result from a simpler construction
should have been treated as evidence of a defect before it was treated as
success.

**The defect:** the signal formed at the close of week `i` was being paired
with `rets[i]`, the return from week `i-1` to week `i` — a week that had
already happened. One full week of look-ahead. In a crypto market that trends
within a week, the names that just rose keep rising, so the bug converted
ordinary trend continuation into a spectacular fake.

The fix is `rets[i+1]`. The regression test is a **truncation test** now
baked into `e3_backtest.py::causality_check`, which rebuilds the signal on a
truncated panel and asserts the shared weeks are bit-identical. Look-ahead by
inspection is not detectable here; by truncation it is.

| | with the look-ahead | without it |
|---|---:|---:|
| mean net per rebalance | +0.0504% | **−0.0171%** |
| annualised net Sharpe | +5.85 | **−0.038** |
| gates passed | 8/8 | **1/8** |

## The result, honestly

| measure | value |
|---|---:|
| rebalances | 292 (5.62 years) |
| mean gross per rebalance | **+0.0319%** |
| mean cost | +0.0489% (turnover 0.306) |
| **mean net per rebalance** | **−0.0171%** |
| gross annualised Sharpe | −0.041 |
| Newey-West t | −0.083 |
| dependence-adjusted t | −0.088 |
| positive-symbol fraction | 0.477 |
| largest symbol profit share | 2.006 (i.e. one name against a negative total) |

Gates: G1 fail, G2 fail, G3 fail, G4 fail, G5 fail, G6 fail, G6b fail,
G7 pass.

## Why — measured, not guessed

`e3_diagnose.py` asks which of the many differences between this experiment
and the source paper is responsible.

**1. The signal has no rank power at all.** Spearman IC of the formation
return against the *next* week's return, over the panel:

| formation | mean IC | t |
|---:|---:|---:|
| 3 weeks | +0.0056 | 0.44 |
| 6 weeks | −0.0073 | −0.57 |
| 12 weeks | +0.0112 | 0.91 |
| 24 weeks | +0.0055 | 0.42 |

Every horizon is indistinguishable from zero. A trend construction cannot pay
when the ranking carries no information.

**2. It is not the sample period.** The paper's window is Apr 2015 – May 2022.
Splitting at 2022:

| era | mean IC | t | weeks |
|---|---:|---:|---:|
| pre-2022 | −0.0106 | −0.38 | 81 |
| 2022+ | +0.0081 | +0.56 | 243 |

Both null. The paper's era is not the explanation.

**3. Cost is not the binding constraint — the gross signal is.** The cost model
is correct: 0.16% round trip per name, 0.306 mean turnover, 0.049% per
rebalance. The paper's gross is 3.40%/week, ~70x its cost. E#3's gross is
0.032%/week, ~0.65x its cost. No turnover reduction or execution cleverness
rescues a construction whose gross edge is below its own cost. Only a
different signal can.

**4. The universe is probably the largest remaining suspect — and it was a
design choice, not an accident.** E#3 selected the **oldest-listed**
perpetuals, because that maximises usable history. The source paper's Panel B
is the **largest and most liquid** coins, and it states the effect
"originates mainly from the biggest and most liquid cryptocurrencies."
**E#3 therefore tested the universe in which the paper reports the effect to
be weakest.**

That is a mis-specified test, not a failed hypothesis. But it is **not** fixed
by re-running E#3: changing the universe after seeing a FAIL is precisely the
rescue `PREREGISTRATION_E3.md` forbids. It is prior information for a
successor.

**5. The construction is not the paper's factor.** The paper's CTREND is an
elastic-net aggregate over many technical indicators, price *and* volume,
across horizons. E#3's primary specification is a plain average of four
trailing-return percentile ranks — price only. It is a weak relative of the
published factor, and it was registered as such.

## What this does and does not establish

**Does:** simple trailing-return cross-sectional momentum, quintile
long/short, weekly, on the oldest-listed perpetual universe over 2020–2026, has
no measurable net edge at this cost. The gate that caught it was the one the
audit identified as missing — G6, cross-symbol consistency, plus G6b, symbol
profit concentration, which flagged a largest-symbol share of 2.006.

**Does not:** say anything about CTREND itself, about a liquid universe, or
about the paper's full construction. Three specific things were different from
the hypothesis being tested, and each was identified by reading the source
rather than by trying variants.

## The stopping rule was honoured

`PREREGISTRATION_E3.md`: *"run once; if it fails, report the null. Do not
rescue."* E#3 ran once, as registered, and failed. The one change made after
the first run was a **bug fix** (the look-ahead), not a parameter change, and
the first run's result was discarded rather than reported — a bug-fixed number
is the only number, and reporting the buggy one as a finding would have been
the worst outcome of this experiment.

## The lesson worth keeping

A Sharpe of 5.85 should have been read as a defect, not a discovery. The
project now has three examples of that shape: the `holdout PF = 0.796` survivor
that passed a broken gate, the `ACCOUNT` factor that cleared t > 3.0 and died
under 3-bar delay, and this. **An implausibly good number in this project has
so far always been a bug.**
