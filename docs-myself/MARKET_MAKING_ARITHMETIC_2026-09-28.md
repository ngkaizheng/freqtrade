# Market making / liquidity provision — CLOSED BY ARITHMETIC, no backtest run

**Date:** 2026-09-28
**Status:** closed. Not a backtest, not a null result — **an arithmetic impossibility
at this venue's fee schedule**, settled in minutes with numbers this repository had
already measured.

---

## 1. Why this line was worth opening

It is the only class this project never tested whose return is **mechanical rather
than predictive**: a market maker earns the spread by supplying liquidity, and does not
need to forecast direction. That makes it structurally different from every line
closed so far (trend, momentum, reversal, breakout, microstructure factors, carry),
all of which were inference problems that ran out of statistical power.

It is also directly supported by this repo's own findings, which is why it was worth
the check rather than being dismissed:

- **§1a: cross-sectional reversal is a liquidity-provision premium.** Spearman
  **−0.0381, t = −8.03**, surviving block bootstrap (−4.06), Newey-West (−4.06),
  winsorising (−4.06) and dropping extremes (−4.93). It is real at the signal level and
  it fails only at the portfolio level.
- **§1a: "the signal is a liquidity-provision premium, and a liquidity-provision premium
  is largest exactly where liquidity is scarcest"** — the premium's size and its
  harvestability are inversely related, and on this venue the trade-off fails at both
  ends.
- **§1b: the book is measured.** Binance Vision `bookDepth`, 2023-01-01 → present, with
  USD depth at ±0.2/1/2/3/4/5% and a measured impact table. The long tail is 1–3 orders
  of magnitude thinner than BTC.

So the mechanism is real, the cost of harvesting it is measured, and the missing
ingredient was the fee schedule. Which is the whole answer.

## 2. The arithmetic

A market maker's gross revenue per completed round trip is **the spread**. The cost is
**fees on both legs plus market impact**. Every input below was already measured in
this repository.

| input | value | source |
|---|---:|---|
| quoted spread, median (spot) | **0.80 bps** | §1a, live Binance 2026-09-26 |
| quoted spread, observed range | **0.01 – 5.40 bps** | §1 cost measurement |
| effective spread, median (BTC perp) | **0.11 bps** | He et al. v7 §4.4 (48–73% narrower post-2022) |
| effective spread, 2020-03-12 (COVID) | 5.95 bps | He et al. v7 §4.4 |
| spot maker fee, VIP0 | 0.100%/side = **10 bps** | §2a(d) |
| spot maker fee, with BNB −25% | 0.075%/side = 7.5 bps | §2a(d) |
| USDⓈ-M maker fee, VIP0 | 0.0200%/side = **2 bps** | §2a(d) |
| USDⓈ-M maker fee, with BNB −10% | 0.0180%/side = 1.8 bps | §2a(d) |
| measured round-trip book cost, calm | 12.0 bps | §1b |
| measured round-trip book cost, COVID | 34.9 bps | §1b |

### Spot

```
revenue per round trip   = spread          =  0.80 bps   (median)
fee per round trip       = 2 x 10 bps      = 20.00 bps   (VIP0, BNB off)
net                      = 0.80 - 20.00   = -19.20 bps
```

**At the best observed spread in the whole sample (5.40 bps): `5.40 − 20.00 = −14.60 bps`.**
With BNB on: `5.40 − 15.00 = −9.60 bps`. There is no spread in the measured
distribution at which spot market making pays for itself at VIP0.

### USDⓈ-M perpetuals

```
revenue per round trip   = effective spread =  0.11 bps   (median, post-2022)
fee per round trip       = 2 x 2 bps       =  4.00 bps
net                      = 0.11 - 4.00    =  -3.89 bps
```

The **only** spread in the entire record at which perp market making is nominally
positive is the 2020-03-12 COVID figure: `5.95 − 4.00 = +1.95 bps` — and that is before
adverse selection, which is precisely the condition under which a market maker is
adversely selected hardest. **A regime that makes the arithmetic work is the same
regime that destroys the strategy.** The edge cannot be harvested where it exists.

## 3. The break-even condition, stated once

For market making to be viable on this venue, the maker fee must fall below the
spread:

| venue | required maker fee | actual VIP0 | required VIP tier |
|---|---:|---:|---|
| Binance spot | **< 0.0080%/side** | 0.100% | 12.5× lower than VIP0 |
| Binance USDⓈ-M | **< 0.0011%/side** | 0.0200% | 18× lower than VIP0 |

Neither is reachable by a retail account, and the §2a(v) note already records the
direction of travel: **Binance restricted retail leverage itself** (>5x unavailable to
regular users' futures sub-accounts since 2025-08-12; >20x unavailable in a new
account's first 30 days since 2025-12-07).

## 4. Why this closes the line rather than deferring it

Three reasons, in order of weight:

1. **The binding input is a published fee schedule, not a measurement.** Unlike every
   other line in this project, the conclusion does not depend on a backtest, a sample,
   a significance test, or a power calculation. It is `spread − fees`, both known.
   Running a backtest could not change it, and pretending otherwise would be spending
   compute to re-derive a subtraction.
2. **It explains the §1a null that previously had no economic mechanism.** E#4's
   reversal signal is real (t = −8.03) and dies at the portfolio level. This is why:
   the only way to harvest a liquidity-provision premium on this venue is to *be* a
   market maker, and the market maker's fee is 25× its revenue.
3. **It retires the last structurally-different class.** Everything else the project
   closed was an inference problem that ran out of power. This one was an economics
   problem that was never viable.

## 5. What would reopen it

Exactly one thing, and it is not a backtest: **a fee schedule where the maker fee is
below the median effective spread** — a negative or near-zero maker fee, a maker rebate
large enough to flip the sign, or a venue whose spread is an order of magnitude wider
than Binance's. This is a check against a published fee schedule, not research.

**Do not** respond to this closure by testing a grid, a DCA ladder, or a "passive"
variant on Binance spot. §1's `unlimited_dca` and `dca_capital_fiction` artifact flags
on the leaderboard already show what that class produces: DCA at Binance's fee schedule
pays 20 bps per round trip to hold a position that the signal is not selecting, and it
loses the fee on every add.
