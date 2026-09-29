# E#10 — signal exits help the RETURN and do nothing for the DRAWDOWN

**Date:** 2026-09-26 · **Not pre-registered as a document.** See the caveat at
the end. · **Engine:** `e10_exit_horizon.py`

## The question this answered

E#9 tested a **price-based** trailing stop and found it carries no information.
E#7 tested a **signal-based** exit (flat when the trailing return turns
negative) at **126 days** and found it too slow to stop a drawdown.

**Nobody had tested the middle: 21–63 days.** That is where a usable exit should
live — long enough not to be a noise trigger, short enough to be flat before
the bottom.

## Part A — does the signal carry information?

| lookback | exits | fwd 20d | t | placebo | t | diff t | |
|---:|---:|---:|---:|---:|---:|---:|---|
| 21d | 116 | −0.10% | −0.07 | +2.51% | 1.71 | −1.27 | no signal |
| 42d | 64 | +0.77% | +0.36 | +1.49% | 0.93 | −0.27 | no signal |
| **63d** | 54 | **−5.48%** | **−2.59** | +1.19% | 0.42 | **−1.88** | **INFORMATION** |
| 126d | 39 | +0.42% | +0.17 | +0.01% | 0.00 | +0.12 | no signal |

**A 63-day trailing return turning negative IS followed by a fall** — the next
20 days average −5.48%, t = −2.59, and it beats a same-frequency placebo at
t = −1.88. That is a real exit signal, and it is in the gap E#9 and E#7 left
open.

## Part B — and it still does not control risk

| lookback | CAGR | max DD | Sharpe | turnover/yr |
|---:|---:|---:|---:|---:|
| 21d | +13.5% | **−74.7%** | 0.50 | 34.6 |
| **42d** | **+27.5%** | **−71.1%** | **0.73** | 19.0 |
| 63d | +12.7% | −63.7% | 0.48 | 16.0 |
| 126d | +2.5% | −84.1% | 0.28 | 11.4 |
| **buy-and-hold** | −5.0% | −83.6% | 0.30 | 0.0 |

> **The best exit in this family produces the best Sharpe measured in this
> project (0.73) and a −71% drawdown.** The signal improves what you earn. It
> does nothing for what you can survive.

This is the direct answer to "没有止损和赌博是一样的吧". **Yes — and a signal
exit is not the alternative.** It is a return improvement wearing the costume
of risk control.

Contrast the two mechanisms that have been tested:

| | Sharpe | max DD | what it fixes |
|---|---:|---:|---|
| buy-and-hold | 0.30 | −83.6% | — |
| **42d signal exit** | **0.73** | **−71.1%** | return |
| **20% vol target (E#8)** | 0.585 | **−33.4%** | **drawdown** |
| 42d exit + vol target | **untested** | untested | **the obvious candidate** |

## The obvious next step, and why I am not just running it

A signal exit for return and a volatility target for drawdown are complementary
mechanisms, and their combination is the natural candidate. It is also
**exactly the move that has contaminated every result in this series**: it would
be the 6th look at the same 200-symbol download, the 2nd at this exit family,
and the best cell would be selected from a grid I had already seen.

So it has to be **pre-registered, and confirmed forward** — and the forward
collector and depth archiver are both scheduled and running.

## Caveats that are not formalities

- **This file is not a pre-registration.** The four lookbacks were explored and
  63d and 42d came out of that exploration. Treat both as hypotheses.
- **The 63d Part A result is one of four tested**, and its t = −1.88 on the
  placebo difference would not survive a family correction.
- **A sixth look-ahead bug was caught in Part B.** The exposure used the signal
  computed from the close at *t* and multiplied it by the return that had already
  accrued to that close. It reported **+199.8% CAGR**. Shifting the decision by
  one bar gives the table above. That is the sixth implausible number in this
  project that was a bug.
- **Survivorship**: 50 currently-listed perpetuals across two enormous bull
  years, flattering every long-only result. Not correctable from public data.

## What is actually established here, narrowly

1. A 63-day trailing-return signal exit is followed by a fall
   (−5.48%, t = −2.59) and beats a placebo (t = −1.88). Exploratory.
2. **Signal exits improve Sharpe and return; they do not control drawdown.**
   The best of them still shows −71%.
3. **Volatility targeting is the only mechanism tested that controls drawdown**
   (−83.6% → −33.4%).
4. **Their combination is the untested candidate**, and it is a hypothesis, not
   a result.
