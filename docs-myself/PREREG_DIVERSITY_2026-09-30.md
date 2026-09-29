# PREREG — D-1: ARE THE TWO BOOKS ACTUALLY COMPLEMENTARY, OR IS THE COMPLIMENT A STORY?

**Written:** 2026-09-30, before the combination was computed.

---

## 1. What has been claimed and what has been measured

§49 measured, separately, that the deployed **short** book and the new **long** book
(chandelier 8.0) behave differently by year: 2023 short +11.7 % / long +28.1 %; 2025 short
positive / long −9.5 %.

**That is a table of two annual numbers. It is not a measurement of complementarity.**

**The deliverable's central claim is that these are two books that eat opposite regimes.**
If that is wrong — if their returns move together — then the "complement" is a story, the
user gets one bet instead of two, and the whole rationale for shipping a second strategy
collapses. **This is the one claim in the new objective that has not been tested.**

## 2. What will be measured

**D1 — the return correlation, at three frequencies.** Daily and monthly return series for
each book from its own archive, plus the **sign agreement of monthly returns**, which is the
statistic that actually answers "do they lose money in the same months".

**D2 — the combined book.** Capital split 50/50, each book keeping its own 0.5 % risk
fraction and its own stop architecture. **Construction and its check:** both books are
risk-sized as a fraction of equity and their returns are near-linear in size, so the
combined daily return is the **equal-weighted average of the two daily returns**. **That
approximation is asserted in advance and must be validated, not assumed** — see D4.

**D3 — the comparison that decides.** Combined book versus each book alone on total return,
CAGR, **Sharpe**, and maxDD, plus the by-year table. The claim is:

> **If the combined Sharpe exceeds BOTH single-book Sharpes, the books are complementary
> and the claim is supported. If it lands between them, the "complement" was a story over a
> two-row annual table and must be retracted.**

**Sharpe is the right statistic here, not total return**, because total return is bought with
risk and the question is whether the combination is *better per unit of risk*.

## 4. The check on the check (D4) — stated because the combination is a construction

The 50/50 combination above is **arithmetic, not a backtest.** Before its numbers are
believed, the tool must verify that the arithmetic is sound:

* the two daily series must be aligned on **calendar dates**, and the report prints the
  number of days in the overlap;
* **if the overlap is short, every correlation on it is reported as short-sample and no
  verdict is claimed from it**;
* and — the important one — **the combined curve is a real, stated construction, so its
  Sharpe is a derived number, not an engine output.** That is printed every time. A derived
  Sharpe compared against an engine Sharpe is §41's error unless both are on the same basis,
  so **the single-book Sharpes in the comparison are ALSO recomputed from the same daily
  series**, and the engine's own numbers are printed beside them as a cross-check.

## 5. Kill rule

**If the daily overlap is under 60 % of either book's trading days, no complementarity
verdict is published** and the tool reports the overlap instead. A correlation on a short
overlap is a number, not a finding.

## 6. What this does NOT do

* **Does not re-tune either book.** No parameter moves in this round.
* **Does not re-open the chandelier.** §49's limit stands: the parameter was selected on
  n = 2 up regimes and the two regimes disagree about the optimum.
* **Does not claim the combined book is deliverable.** It is a measurement of a claim; if it
  works, the combined configuration is a *candidate*, and shipping it is a separate decision
  with its own config.
