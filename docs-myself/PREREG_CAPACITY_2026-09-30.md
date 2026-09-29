# PREREG — C-1: THE CAPACITY AXIS, THE ONLY ONE LEFT THAT CHANGES WHAT THE USER SHOULD DO

**Written:** 2026-09-30, before any book was walked.
**Data:** `shark_data/costs/depth_cache/*.parquet` — **real L2 depth**, already on disk.
**Tool:** `tools/perp_short/capacity.py`.

---

## 1. Why this axis and not another

Every other axis is closed by measurement: universe width (§20b, N≈25–200 positive),
risk level (§28, 0.5 % is the peak), horizon in **both** directions (§18 faster, §41
slower), signal quality and weighting (§25, §34), cross-sectional class (§17), cost law
(§39, §40), execution assumption (§16b: 0 gaps in 334 stop exits).

**Capacity is the one axis whose measured number changes a DECISION the user makes** — how
much money to put in. And it has never been measured.

## 2. What is there, and why none of it answers the question

**`shark_data/costs/impact_by_size.csv` looks like the capacity answer. It is not one.**

384 rows. Grouping by `one_way_bps`: **261 rows are exactly `100.0` and 50 rows are exactly
`20.0`.** Those are constants, not measurements — and a table that says "the cost is 100 bps
whether you trade $1,000 or $500,000" says capacity is infinite in one direction and
meaningless in the other. It is 384 rows whose *appearance* is a size-vs-impact curve.

**Where the deployed numbers come from is a different file.** `cost_regimes.csv` gives
12.0 / 15.6 / 22.8 / 34.9 bps, and those come from `realised_cost_<date>.csv` — aggTrades.
**A round trip measured against realised trades has no size attached to it.** The 12.0 bps is
a cost *per unit of notional at whatever participation that measurement implied*, and the
participation is not recorded, so **the number cannot be turned into a capacity**.

## 3. What C-1 measures

Walk the **real order book** in `depth_cache/` — actual L2 depth by percentage band, twelve
symbols, five dated regimes including the COVID crash.

For each snapshot, for each order size `S`, consume the book outward and compute the
**VWAP slippage against the mid**, separately for a buy and a sell. Round trip = entry +
exit. This is a real impact curve, not a constant, and it is the standard construction.

## 4. Pre-registered decisions

**C0 — the book must be reconstructible.** If a snapshot's bands do not form a monotone,
two-sided book, it is dropped and the drop rate is **printed**. A tool that silently drops
half its snapshots and reports a clean curve is §34c's error.

**C1 — the capacity number.** Join the measured impact curve to the **deployed book's own
gross edge per trade**, which is measured (§41: **0.1538 R** on 1,111 trades, at
4h ATR% 2.953 %).

> **Capacity = the order size at which the round-trip impact equals the book's gross edge
> per trade**, converted to bps of notional. Above it, more money makes the strategy lose
> money. **This is the number that tells the user how much to put in, and it has never
> been computed.**

**C2 — the participation cross-check.** Impact is really a function of *participation rate*,
not dollars. Both are reported, and the book is located on both axes. **If the answer differs
by more than 2× depending on which axis is used, both are published and the disagreement is
reported** — not resolved by picking one.

**C3 — the actual deployed book, for scale.** The book trades ~3 concurrent positions of
~4.7 % of a 10,000 USDT account at 1×. Its notional and its participation rate are computed
from the 1,111 real trades, not estimated. **The question is not "is capacity large" but
"by how many orders of magnitude is the deployed book below it."**

**C4 — KILL RULE.** If fewer than 12 of the 60 symbol-days yield a usable book, C-1 reports
**BLOCKED** and no capacity number is published.

**C5 — WHAT THIS DOES NOT AUTHORISE.** A capacity number is **not** a licence to run at
that size. The measured impact curve is a static-book approximation taken from five dated
snapshots; it contains **no** queue position, **no** adverse selection, **no** funding
change, and **no** correlation between the strategy's own orders and the market state it
trades. A capacity estimate is an upper bound on a quantity that has only been bounded from
below before now. **It is published with that stated, and it does not change the deployed
`risk_per_trade`.**

## 5. What would make me wrong

* **The snapshots are sparse** (~2,856 per symbol-day, about one every 6 minutes). A
  10-minute impact cost measured on 6-minute snapshots is optimistic. Reported, not
  corrected by a fudge factor.
* **Depth is not liquidity.** Touching 1 % of the book does not mean filling 1 % of it in a
  market that is moving. This is the single largest limit and it is why C5 exists.
* The book could be **so deep relative to the edge** that capacity is effectively unbounded
  on these symbols, in which case the honest answer is "capacity does not bind at any
  plausible retail size, and the binding constraint is elsewhere" — and §31 already says
  where that is.

## 6. Where this leaves the delivered book either way

The deployed configuration does not change. `risk_per_trade: 0.005`, `max_stake_frac: 0.25`,
`perp_leverage: 1.0`, N=40, 4h. **This round adds a number the user did not have; it does
not move a setting.**
