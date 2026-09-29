# §46 — GATE 0 FOR THE BULL-MARKET BOOK: HOW MANY BULL REGIMES EXIST, AND WHAT THE BAR IS

**Date:** 2026-09-30 · **Tool:** `tools/perp_short/regime_calendar.py` · **Raw:** `user_data/logs/regime_calendar.txt`
**Run before any bull-market strategy was written** (`AGENTS.md` 1a: check the experiment can conclude).

---

## 1. The measurement

Deployed 40-symbol universe, equal-weight, long-only, 4h panel, 2023-01-01 → 2026-08-31,
8,033 bars.

| year | panel return |
|---|---:|
| **2023** | **+198.6 %** |
| **2024** | **+103.6 %** |
| 2025 | −56.8 % |
| 2026 (to Aug 31) | −17.6 % |

| | |
|---|---:|
| **years up** | **2 of 4** (2023, 2024) |
| **quarters up** | **8 of 15** (53 %) |
| longest unbroken run of up quarters | 2 (~0.5 y) |
| **panel peak-to-trough drawdown** | **−80.4 %** |
| **panel 4-year buy-and-hold** | **+116.5 %** |
| 4h bars where the panel made money | **51.7 %** |
| 4h bars above the panel's own trailing 6-month mean | 52.2 % |

## 2. Why this is the right first thing to measure, not a formality

The project's entire record rests on **one** bull year. A long book tested on one bull year
is **n = 1 on bull markets**, which is a sample, not a measurement.

**The answer is better than the worst case: 2 up years and 8 up quarters.** That is enough to
tell a book that profits in up regimes from one that does not — **provided the verdict is
judged on the up regimes alone and the down regimes are published beside it.** A book that
worked only because the sample happened to be kind is still visible in this table.

## 3. The two things this table settles that nothing else had

**(a) Buy-and-hold this universe is a bad trade.** **+116.5 % over four years with an −80.4 %
peak-to-trough.** That is the real opportunity: a book that captures the +198.6 % upside year
while avoiding most of the round trip would beat both holding the coins and the delivered
short book, which returned +113.74 % — the same total, from the other side.

**(b) The bar.** The panel's median up year is **+151.1 %**. It is fixed here, before any
strategy is written, and it is not a bar this project chose:

> **A bull-market book must be net-positive in the up regimes after the measured round trip
> (12–35 bps), and must be worth having against the alternative of holding the coins.**

This is the criterion the closed `trend following` entry was judged against in the *old*
objective, and it is why B-1's re-opening in §45 is legitimate: **the objective changed, and
with it the criterion.** The old null is not overturned; it is re-tested against a bar that
matches the new question.
