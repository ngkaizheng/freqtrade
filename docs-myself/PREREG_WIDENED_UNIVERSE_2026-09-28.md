# PRE-REGISTRATION — the coins the panel never saw: is this tradeable in 2026?

**Date frozen:** 2026-09-28, **before a single new kline is downloaded.**
**This is a GENERALISATION test on independent instruments, not a re-tune of the
same data** — the distinction `RESEARCH_GOAL.md` §2.G requires after a failure.

---

## 0. The question

The delivered book (`PerpShort4hDeploy`) was measured on **104 perps that
existed before 2023-01 and are still listed in 2026**. A user starting today can
trade **527**. The other **422 — 66 listed in 2023, 94 in 2024, 210 in 2025, 52
in 2026 — have never been touched by any number in this project.**

That is the largest unquantified bias in the whole repository, and it is
**not** the abstract survivorship caveat the state file has been carrying
("§3.8, unfixable from public data"). Part of it **is** fixable, and this is the
fix: the *delisted* coins are permanently unobservable, but the *newly listed*
ones are not, and they are 80% of what a user can actually trade.

**The literature makes this a first-order question, not a footnote:**

- **Grobys, Sandretto & Äijö (2026)**, *Finance Research Letters* 109602,
  **peer reviewed**: *"The survivor cryptocurrency momentum portfolio does not
  generate significant payoffs… Significant payoffs documented for momentum
  strategies are an artefact of coins that are only temporarily accessible for
  trading."*
- **Nefedov (2026)**, SSRN 7350238, on **137** Binance USD-M perps: naive
  Sharpe inflates **3.6×**, and the gap is attributed mainly to **friction**.

So the sharpest version of the question is not "does it work on more coins". It
is: **how much of the +52.4% belongs to coins that had already survived three
years?**

## 1. Universes — frozen, and the cohorts are defined BEFORE any result

The symbol list is taken from Binance's own `exchangeInfo` by RULE, never by
result: `contractType == PERPETUAL`, `status == TRADING`, `quoteAsset == USDT`,
`BTCDOMUSDT` excluded (an index, not a crypto price). **Counted 2026-09-28:
527 symbols.**

| cohort | definition | n (counted before download) |
|---|---|---:|
| **A — the panel** | onboarded ≤ 2023-01-01 | 105 |
| **B — 2023** | onboarded in calendar 2023 | 66 |
| **C — 2024** | onboarded in calendar 2024 | 94 |
| **D — 2025** | onboarded in calendar 2025 | 210 |
| **E — 2026** | onboarded in calendar 2026 | 52 |
| **ALL** | every symbol above | 527 |

Cohorts B–E are the **independent test set**: none of them contributed a single
trade to any number ever reported in this project. Cohort A is the **replication
arm** — it must reproduce the delivered book, and if it does not, nothing in B–E
is interpretable.

**A symbol whose download 404s is DROPPED and the drop is reported with its
reason.** A symbol with fewer than `startup_candle_count` (420 = 70 days) of
history after its listing is **REPORTED, NOT DROPPED** — dropping it would
silently remove exactly the newest coins, which is the cohort under test.

## 2. Signal — frozen, byte-identical

`PerpShort4hDeploy`: rvol(20) ≥ 2.0, 20-bar Donchian, low-volatility regime
filter, **4.0 × ATR stop anchored at the entry bar**, **2R target**, **42-bar
time stop**, 1x, 1% risk per trade, 24 slots, the drawdown circuit breaker.
**No parameter, threshold, window or universe override is varied within a cohort.**

## 3. Costs — unchanged, still the measured ones

Fees 0.05%/side; funding charged by freqtrade from real per-symbol history;
slippage at the §1b **measured** 12.0 / 22.8 / 34.9 bps round trip. `gross` and
`engine_default` are shown as the curve's left edge, never as a headline.

**⚠ A cost asymmetry that this test will expose and that must not be quietly
averaged: a coin listed in 2026-08 has two weeks of history.** It can generate
almost no trades, and its few trades carry the same 35 bps as a major's. The
per-cohort trade COUNT is therefore reported next to every per-cohort return, and
a cohort with fewer than 30 trades is labelled **INCONCLUSIVE**, not "positive".

## 4. The gate — fixed now

| # | gate | threshold |
|---|---|---|
| **U0** | **cohort A REPLICATES the delivered book** | mean net R at measured_covid within **25%** of the delivered +0.1213. If A does not reproduce, stop — the new cohorts are uninterpretable |
| U1 | **cohorts B–E are not catastrophically negative** | mean R at measured_covid > **0** in aggregate across B–E |
| U2 | **generality, not just survival** | B–E mean R is not worse than cohort A by more than **50%** — i.e. the signal is not a survivor-only artifact |
| U3 | **ALL-527 at measured_covid stays positive** | net expectancy > 0 |
| U4 | **the tradable-universe verdict** | report the return and trade count on ALL 527, since that is what a 2026 user can actually trade |

**U2 is the gate this design exists for.** U1 and U3 can both pass while the
signal is a survivor artifact, and U4 is a deployment statement rather than a
scientific one.

## 5. What a pass would NOT mean

- **The delisted coins remain permanently unobservable.** The universe is still
  "listed today", so **every number here is still an upper bound** and the
  survivorship correction remains **incomplete** — this test *reduces* the bias,
  it does not remove it. A strategy that would have lost on the ~40% of Binance
  perps that have been delisted since 2023 is not measured by this.
- **Cohort E (2026) cannot conclude.** 52 symbols with at most 9 months and a
  70-day warm-up is reported, not judged.
- **Nothing here changes the significance verdict.** The delivered book's
  t = −0.15 on the strictest measure. A wider universe may raise t through more
  trades; **it cannot manufacture an effect that the control test showed is
  market beta.**

## 6. Forbidden

- Changing any parameter because a cohort performs badly.
- Dropping a cohort from the ALL figure because it is negative.
- Quoting ALL-527 without cohort A's replication and the per-cohort trade counts.
- Presenting this as removing survivorship bias. It reduces it.
