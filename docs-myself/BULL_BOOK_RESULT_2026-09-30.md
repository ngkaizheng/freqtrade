# §45 — B-1: THE FIRST POSITIVE LONG RESULT, AND IT FAILS THE BAR BY TWO ORDERS OF MAGNITUDE

**Date:** 2026-09-30
**Prereg:** `docs-myself/PREREG_BULL_2026-09-30.md` (before any bull backtest)
**Gate 0:** `docs-myself/REGIME_CALENDAR_2026-09-30.md` via `tools/perp_short/regime_calendar.py`
**Strategy:** `user_data/strategies/PerpLong4h.py` (new). Tool `tools/perp_short/bull_axis.py`.
Raw `user_data/logs/{regime_calendar,bt_bull_*,bull_axis}.txt`. **The delivered book is untouched.**

---

## 1. Gate 0 first: the experiment CAN conclude

| year | panel, equal-weight long |
|---|---:|
| **2023** | **+198.6 %** |
| **2024** | **+103.6 %** |
| 2025 | −56.8 % |
| 2026 (to Aug 31) | −17.6 % |

**2 of 4 years up, 8 of 15 quarters up.** Panel peak-to-trough **−80.4 %**, 4-year
buy-and-hold **+116.5 %**, and the panel made money on **51.7 % of 4h bars**.

> Buy-and-hold this universe is a **bad trade**: +116.5 % with an −80.4 % round trip. That
> is the opportunity a bull-market book is being measured against, and it is a real one.

**The bar, fixed in the preregistration before any of these backtests ran:** net-positive in
the up regimes after measured cost, **and worth having against simply holding the coins.**
The panel's median up year is **+151.1 %**.

## 2. What was already closed before I wrote anything

* `PerpShort4h.py:239-242`, **in the source**: *"SHORT ONLY. The long leg is net-negative in
  all 12 cells of the wide panel and all 3 cost regimes."*
* `PerpShort4hSwitch` added a regime-switched long leg and printed **−44.5 % in 2023**, the
  year the panel rose +198.6 %.

**So "flip the side" was a closed question, and B-1 exists only to test it on the *deployed*
universe with the delivered risk architecture — not as a fresh idea.**

## 3. B0 — the control gate, and it earned its place twice

The first run of the control arm returned **+2.89 % on 166 trades** against the deployed
book's **+113.74 % on 1,111**. Per the preregistration the run was void. The cause was in
my file, and it was three silent short-only constructions in the parent:

| # | parent code | what it does on a LONG |
|---|---|---|
| 1 | `_anchor_stop_price` returns `open + atr_stop·atr` | the stop is ABOVE entry — the wrong side |
| 2 | `custom_stoploss` guards `if ratio <= 0: return None` | for a long the ratio is negative **by construction**, so the guard always fires and the long runs on the **−30 % class backstop instead of 4×ATR** — a ~6× wider risk unit, silently |
| 3 | `custom_exit` acts only `if risk > 0`, with `risk = stop − open` | for a long risk is negative, so **the 2R target never fires on a long at all** |

Plus a fourth, mine: overriding `custom_exit` with `if trade.is_short: return None`
suppressed the parent's 2R target **and** its 42-bar time stop, which is what collapsed the
control to 166 trades.

**After the side-aware rewrite, B0 reproduces the deployed book exactly: 1,111 trades,
113.74 %, PF 1.36, maxDD 18.43 %.** Every short path delegates to `super()`, so the mirror is
a mirror and not a rewrite — and that is the only evidence that the long numbers mean
anything.

## 4. The results, decomposed by regime against the panel

| year | regime | **PANEL** | **B1 long mirror** | B1c breaker 0.35 | B2 panel trend |
|---|---|---:|---:|---:|---:|
| **2023** | **UP** | **+198.6 %** | **+2.5 %** | +2.5 % | −2.7 % |
| **2024** | **UP** | **+103.6 %** | **+5.6 %** | +5.6 % | +1.3 % |
| 2025 | DOWN | −56.8 % | +9.7 % | +9.7 % | −3.0 % |
| 2026 | DOWN | −17.6 % | +0.4 % | −2.4 % | +4.5 % |

| arm | trades | total | PF | maxDD |
|---|---:|---:|---:|---:|
| B0 control (deployed short) | 1,111 | 113.74 % | 1.36 | 18.43 % |
| **B1 long mirror, breaker 0.20** | 1,284 | **+19.22 %** | 1.10 | 23.59 % |
| B1c long mirror, breaker 0.35 | 1,305 | +15.95 % | 1.08 | 25.67 % |
| B2 panel trend | 949 | −0.10 % | 1.00 | 9.84 % |

> **B1 is positive in 2 of 2 up regimes. It is the first positive long result this project
> has produced. And it captures 3.3 % of the panel's move — 1 % in 2023, 5 % in 2024.**
>
> **It clears the first half of the preregistered bar and fails the second by two orders of
> magnitude.** A book that returns +2.5 % in a year the market rose 198.6 % has not solved
> the problem the user asked about, and reporting it as "it makes money in bull markets"
> would be true and useless.

## 5. ⚠ THE PREMISE OF THE OBJECTIVE IS WEAKER THAN EXPECTED

**The delivered SHORT book also makes money in bull markets:**

| year | panel | **deployed short book (B0)** | B1 long |
|---|---:|---:|---:|
| 2023 | +198.6 % | **+11.7 %** | +2.5 % |
| 2024 | +103.6 % | **+27.1 %** | +5.6 % |

**The short book is a BETTER bull-market book than the long mirror of its own signal — 4.7×
better in 2023 and 4.8× better in 2024.** The premise "the delivered book bleeds in bull
markets" is true in the sense that it captures almost none of the upside, and **false in
the sense that it still profits in both up years.** That is a more useful statement for the
user than "it loses in bull markets", and it is a measured one.

## 6. The mechanism, which is the round's real finding

B1's exit mix: **1,437 of 1,284 trades exit through the stop, with a mean duration of about
1 day 8 hours; the 42-bar time stop fires on ~37 trades and those win 70 % of the time at a
mean +19 %.** So:

* **the 2R target essentially never fires on a long**, and
* **the 4×ATR stop cuts the average long after ~32 hours.**

> **The frozen architecture is a MEAN-REVERSION architecture.** It assumes the move is fast
> and reverses, which is what crypto drawdowns do and what crypto rallies do **not** — a
> rally trends for weeks, so a 4×ATR stop at 32 hours exits before the trend can pay, and
> the book re-enters, pays the cost again, and grinds. **The same stop, target and time-stop
> that make the short book work are what make the long book fail.**

**This also explains B2**: long the panel above its own 365-bar extreme is a textbook trend
book with **9.84 % maxDD** and **−0.10 % return** — near-perfect risk control and no return,
for exactly the same reason.

## 7. The breaker: measured for the first time, on either side

`breaker_max_dd` **ships enabled in the delivered book and has never been measured.**

| setting | B1 total | B1 maxDD | trades |
|---|---:|---:|---:|
| **0.20** | **+19.22 %** | **23.59 %** | 1,284 |
| 0.35 | +15.95 % | 25.67 % | 1,305 |

**On the long side the breaker improves the return by 3.27 pp AND cuts the drawdown by
2.08 pp.** It is a real component, not decoration, and this is the first evidence either way.

**B2 never reached the threshold** — its own maxDD is 9.84 %, far below both settings — which
is why B2 and B2c are bit-identical, and why a low-drawdown strategy should be expected to
find the breaker inert.

## 8. Verdict, and the next question this raises

**B-1: the family "long, using the short book's risk architecture" is CLOSED by the
preregistered kill rule BE.** Both arms fail the bar; B1 survives it only on the letter.

**But B-1 produced a mechanism, and the mechanism says exactly what to try next — which is
the first time in this project that a null has handed over a specific, cheap next step:**

> **A bull-market book needs a different EXIT architecture, not a different entry.**
> The 2R target caps winners and the 4×ATR stop cuts trends at ~32 hours. A long book
> needs to be allowed to run — a trailing stop, or no profit target at all, with the
> existing breaker for the drawdown control the architecture already has.

That is the next round's pre-registered question, and it is cheap: it changes two exit
parameters and reuses everything else, including the B0 control gate that has now caught
two separate classes of defect.

**What is NOT closed by this round:** whether a bull-market book is possible on this
universe at all. Only the specific architecture is closed.

## 9. Two errors of my own, recorded because both looked fine

1. **`bull_axis.py` reported the wrong archives.** It selected the first archive matching an
   arm's tag; the broken first run and the fixed second run share a tag, so it printed the
   OLD numbers — B0 as 166 trades / +2.89 % when the run that passed the gate printed
   1,111 / +113.74 %. **Selecting a run by the tag it was given instead of by which is
   newest is §34c's error for the third time.**
2. **The same file printed a fraction with a `%` suffix**, rendering 2023's +198.6 % as
   "2.0%" — small enough to read as a bad result rather than as a formatting bug. §16d's
   class again.

**Both were caught by checking the control arm against the deployed number that was already
known. A control that reproduces a known value is the cheapest bug detector ever built**, and
this project now has two of them in this one round.
