# PREREG — B-2: A BULL-MARKET BOOK NEEDS A DIFFERENT EXIT ARCHITECTURE, NOT A DIFFERENT ENTRY

**Written:** 2026-09-30, before any B-2 backtest. Follows `PREREG_BULL_2026-09-30.md` (B-1).

---

## 1. What B-1 measured, and the one sentence it handed over

B-1's long mirror of the frozen signal was **positive in 2 of 2 up regimes** — the first
positive long result this project has produced — and **captured 3.3 % of the panel's move**.
The mechanism was measured, not guessed:

* **1,437 of 1,284 long trades left through the stop at a mean duration of ~1 day 8 hours.**
* **The 42-bar time stop fired on ~37 trades and those won 70 % at a mean +19 %.**
* **The 2R target never fired on a long at all.**

> **"A bull-market book needs a different EXIT architecture, not a different ENTRY."**
> The 2R target caps the winner and the 4×ATR stop cuts a trend at ~32 hours. A rally
> trends for weeks; a mean-reversion architecture cannot hold one.

## 2. The second mechanism, which B-1 did not measure and this round must

**B-1 deploys very little capital, and the comparison in §45b was not made at matched
exposure.** At 0.5 % risk a position is `0.005 / (4 × 2.95 %) ≈ 4.2 %` of equity, and §30
measured average concurrency at ~3, so **gross exposure is ~12 %.** The panel's +198.6 % is
at **100 %** exposure.

> **So "B1 returned +2.5 % against the panel's +198.6 %" overstates the miss by roughly the
> exposure ratio.** This round measures the deployed fraction and reports a **matched-
> exposure benchmark**, because a comparison at 12 % against a comparison at 100 % is §41's
> lesson repeated: **compare the same quantity, or you manufacture a finding.**

`AGG_LESSONS.md` L3 — two variables at once — is why this is a **factorial** and not a
single arm.

## 3. The arms, all pre-registered, all published (B-1's BD rule)

| arm | entry | exits | risk | what it isolates |
|---|---|---|---|---|
| **B0** | control (`side=off`) | deployed | 0.5 % | **the gate — must reproduce 113.74 %** |
| **A1** | long breakout mirror | **run** (chandelier 3.0, no 2R, no time stop) | 0.5 % | **the exit effect alone**, at B-1's exposure |
| **A2** | panel trend | **run** | 0.5 % | the exit effect at a **high-exposure** entry |
| **A3** | panel trend | **run** | **1.0 %** | the **exposure** effect, doubling the risk fraction |

A1 vs B-1 is the clean exit comparison. A2 vs A3 is the clean exposure comparison. A1 vs A2
is the entry comparison at equal risk. **Three contrasts, one grid, no cell chosen after.**

## 4. Pre-registered decisions

**B0** reproduces 113.74 % → otherwise void.
**A1** beats B-1's +19.22 % ⇒ the exit hypothesis is supported. If A1 does not beat B-1, the
mechanism is wrong even though it was measured, and that is reported.
**A2** is the bull-market candidate: it is the only arm whose entry can hold many positions
at once, so it is the only one that can be compared to the panel at matched exposure.
**A3** tells exposure apart from signal.

**THE BAR, unchanged from B-1 and fixed before these arms exist:**
> net-positive in the up regimes after measured cost, **and worth having against holding the
> coins at the same deployed exposure.** Panel: 2023 **+198.6 %**, 2024 **+103.6 %** at 100 %
> exposure; median up year **+151.1 %**.

**MATCHED-EXPOSURE BENCHMARK.** Buy-and-hold the panel scaled by each arm's measured average
deployed fraction. Computed and published beside the raw panel number, both.

**PUBLICATION.** The whole grid, whatever it says. If one arm wins it is one point on a
curve, reported with the regime it won in.

**KILL.** If A1, A2 and A3 all fail the bar, **"long entry + long-run exits" is closed** and
the next mechanism must be something other than the exit architecture.

## 5. What this does NOT do

* **Does not touch the delivered book.** `exit_mode` defaults to `"fixed"` and every short
  path delegates to `super()`, so **B0 is the proof and it is the same proof as B-1's.**
* **Does not re-tune the entry.** A1 and A2 use entries already measured; the panel-trend
  entry is a *higher-exposure* version of one, not a new signal.
* **Does not claim a bull book exists yet.** This is the second round of a family.
