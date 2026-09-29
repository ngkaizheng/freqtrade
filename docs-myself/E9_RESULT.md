# E#9 — does a stop loss plus leverage work? **Part A fails, Part B must not be run**

**Date:** 2026-09-26
**Pre-registration:** `PREREGISTRATION_E9.md` · **Diagnostic:** `e9_stop_diagnostic.py`

---

## The question

> "如果我短期开杠杆，然后设置止盈止损，不就不会爆了吗？说到底还是要有策略不是吗"

The mechanical part is right: a stop does prevent the 1/L liquidation, because
you are flat before the move that would have triggered it. **That is not in
dispute. What is in dispute is whether the stop costs more than the liquidation
it prevents** — and that is measurable.

E#7 identified the real defect: its exit rule had a **126-day lookback**, so by
the time it went to cash the drawdown had already happened (2022 ratio 0.96x).
**The missing piece is exit speed.** The user's instinct points at exactly that.

## The trap, stated before running

The basket's daily volatility is **3.82%** (annualised 73%). So:

| stop | distance in standard deviations |
|---:|---:|
| 10% | 2.6σ |
| 20% | 5.2σ |
| 30% | 7.9σ |

A stop that fires on noise, immediately before the next rally, is a *cost*. And
leverage converts a cost into a permanent loss rather than a smaller one. That
is the mechanism to test, and the pre-registration made Part B conditional on
Part A so the test would happen before the strategy was built.

---

## Part A — is the stop information, or noise?

For each stop and cooldown: how many times it fires, and what the basket does
over the following 20 trading days, against a same-frequency random-day placebo.

| stop | cooldown | fires | fwd 20d mean | t | placebo mean | t | diff t |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 10% | 5d | 77 | −0.83% | −0.40 | +3.10% | +1.99 | −1.52 |
| 10% | 20d | 50 | −0.86% | −0.34 | −0.19% | −0.11 | −0.22 |
| 15% | 5d | 46 | −0.32% | −0.10 | −0.43% | −0.26 | +0.03 |
| 15% | 20d | 33 | −0.23% | −0.07 | −3.25% | −1.65 | +0.78 |
| 20% | 5d | 30 | −1.67% | −0.45 | +7.53% | +2.08 | **−1.77** |
| 20% | 20d | 28 | +3.54% | +0.91 | +0.62% | +0.25 | +0.64 |
| 30% | either | 11–15 | too few events | | | | |

**Gates: A1 (forward return reliably negative) and A2 (beats the placebo).**

| config | A1 | A2 |
|---|---|---|
| 10% / 5d | FAIL (−0.40) | FAIL (−1.52) |
| 10% / 20d | FAIL (−0.34) | FAIL (−0.22) |
| 15% / 5d | FAIL (−0.10) | FAIL (+0.03) |
| 15% / 20d | FAIL (−0.07) | FAIL (+0.78) |
| 20% / 5d | FAIL (−0.45) | **PASS (−1.77)** |
| 20% / 20d | FAIL (+0.91) | FAIL (+0.64) |

**PART A VERDICT: FAIL. Part B must not be run.**

**The stop carries no information.** A drawdown trigger is followed by a return
statistically indistinguishable from a random day, at every level and every
cooldown tested. The single configuration that beat its placebo on the
*difference* (20% / 5d) still fails on the *level*, and it is the product of
6 configurations — the multiple-testing exposure is already counted.

---

## What this means, precisely

**You are right that you need a strategy, and wrong that a stop plus leverage
supplies one.** The mechanism works exactly as described — you avoid the
liquidation — and that is precisely why it does not help:

- A stop you exit on costs you the re-entry.
- The re-entry price is worse because you exited on the way down.
- Leverage multiplies that permanent cost rather than the temporary one.

> **On this data, a trailing stop is indistinguishable from a random exit. Any
> strategy built on it is buying and selling at random, and leverage makes the
> fees from that randomness structural instead of incidental.**

This is the same lesson the project has now produced three ways: an information
coefficient is not an edge (E#4); a gross return is not a net return (Shark); a
significant t-statistic is not an edge (Phase C). **The thing that looks like
a strategy has to be measured as a portfolio, after every cost, and against a
placebo.**

---

## One diagnostic flaw, recorded

The first version of Part A used "wait for a new all-time high" as the re-entry
rule, and the stop fired **2–3 times in six years**. This basket makes new highs
so rarely that such a rule sits out of the market almost permanently.

That is a true and interesting fact about the basket, but it made the
diagnostic useless. The cooldown structure that Part B actually specifies
produces 28–77 events, which is enough to test. **A diagnostic has to measure
the structure the strategy will use, or it measures nothing.**

---

## The standing caveat, which is not a formality

E#3 through E#9 have all run on the same 200-symbol download with overlapping
universes, and E#8's "trend" base was a post-hoc variant of E#7's. **That is a
substantial search.** The pre-registration for E#9 says so in advance:
nothing in this file is a discovery, and the only thing that settles any of it
is a forward test on the data already being collected.

The forward collector and the depth archiver are both scheduled and running.
**That forward test — not another cell in this grid — is what would make any of
this real.**
