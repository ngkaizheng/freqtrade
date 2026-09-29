# §42 — CAPACITY: THE LOOKING-SILVER-LIKE TABLE WAS A RESOLUTION FLOOR, AND THE REAL ANSWER NEEDS NO BOOK

**Date:** 2026-09-30
**Prereg:** `docs-myself/PREREG_CAPACITY_2026-09-30.md`
**Tool:** `tools/perp_short/capacity.py` (new). Raw: `user_data/logs/capacity.txt`
**The deployed book is unchanged.** This round adds a number; it does not move a setting.

---

## 1. What I set out to measure, and what was already there

C-1 was the last axis whose number changes a decision the user makes: **how much money can
this book hold before market impact eats the edge?** The repo appeared to have the answer.

**`shark_data/costs/impact_by_size.csv`: 384 rows, twelve symbols, five regimes, columns
`size_usd … one_way_bps, round_trip_bps`.** It looks exactly like a capacity curve.

It is not one. Grouping all 384 rows by `one_way_bps`: **261 rows are exactly `100.0`, 50 are
exactly `20.0`.** 311 of 384 rows are one of two constants.

## 2. The root cause, and it is worse than "mostly constants"

The depth cache is `shark_data/costs/depth_cache/` — 60 files, 31 MB, 12 symbols × 5 dates.
One snapshot of `BTCUSDT_20230101`:

| band | −5% | −4% | −3% | −2% | **−1%** | **+1%** | +2% | +3% | +4% | +5% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| notional | 2.72e8 | 2.52e8 | 2.21e8 | 1.63e8 | **7.24e7** | **7.52e7** | 1.61e8 | 2.15e8 | 2.38e8 | 2.89e8 |

**Exactly ten bands, ±1 % to ±5 % from the mid. The finest observation is 1 % away from the
mid — 48.8 bps on BTC, 156.6 bps on ALGO.**

> **Therefore the `100.0` in 261 rows of `impact_by_size.csv` is not a measurement. It is the
> ±1 % band distance.** A table whose headline number is its own resolution floor is a
> constant wearing a curve's clothes, and it would tell a reader that capacity is unlimited.

**And my own tool independently reproduced the same floor** — 91.61 bps at $1,000 *and at*
$5,000,000, with a "capacity" of $1,000. **Two implementations hitting the identical number
is this project's most reliable tell**, and here it was pointing at the data, not the code.

**The fix is a gate, not a better walk.** `capacity.py` now measures the nearest quoted level
against the mid **before drawing any curve**, and refuses to publish a capacity if the feed is
coarser than 5 bps. On this data it returns **BLOCKED, exit 3**, and says so in those words.

## 3. But the capacity question does not need a book — and the answer is decisive

The delivered cost of **12.0 bps** (§4) was decomposed long ago, in
`shark_data/costs/realised_cost_<date>.csv`, and the decomposition is resolution-free:

| date | regime | **roll/spread bps (median)** | taker fee | round trip |
|---|---|---:|---:|---:|
| 2026-09-20 | calm | **1.02** (0.21–4.01) | 5.0/leg | 10.4–12.8 |
| 2025-10-10 | volatile | 6.42 (2.36–9.06) | 5.0/leg | — |
| 2024-08-05 | cascade | 2.80 (1.61–4.65) | 5.0/leg | — |
| 2020-03-12 | COVID | **12.47** (8.71–23.57) | 5.0/leg | — |

**Ten of the twelve calm bps are the taker fee, which is independent of size.** The
size-dependent part is ~2 bps.

Now put it against the edge. §41 measured the deployed book's gross at **0.1538 R per
trade** on 1,111 trades; one R is `stake × 4 × ATR(2.953 %)`, so:

```
gross edge            = 0.1538 x 4 x 0.02953 x 1e4  =  182 bps of notional per trade
fixed part of the bill (taker fee)                  =   10 bps
IMPACT BUDGET                                        =  172 bps of notional per trade
```

And the measured spread+roll at **aggregate market volume** in the calm regime is **1.02 bps**.

> **To make size-dependent impact reach 172 bps, an order would have to consume roughly
> 168× the market's own aggregate flow in that bar. That is not an order anyone can place.**
>
> **CAPACITY DOES NOT BIND FOR THIS BOOK AT ANY PLAUSIBLE SIZE** — retail, family office, or
> small institutional. Even in the COVID regime, where the measured roll component is 12.47 bps,
> the edge is 182 bps.

**So the constraint on this book is not the market's liquidity. It is the two constraints
§31 already measured, and neither is about the market:** the 24-slot cap at low risk and free
balance at high risk. **Both are fractions of your own equity, so neither scales away with
capital** — and that is the practical meaning of this round: *adding money to this book does
not run into the exchange. It runs into your own position-count and free-balance limits, which
are set by the config and which you control.*

## 4. What else C-1 produced, measured from the 1,111 real trades

| | |
|---|---:|
| position size, median | **$733** |
| position size, p95 | **$1,834** |
| holding period, median | **168 h (7 days)** |
| **gross notional turned per day** | **≈ $651** |

A $10,000 account at 0.5 % risk with a 4×ATR stop turns **about $650 of notional a day**. The
user did not have this number before, and it is the honest scale of the delivered book: it is
a small book by construction, and its edge is a timing overlay on a few positions, not a flow.

## 5. ⚠ A PUBLISHED NUMBER IS CORRECTED

`docs-myself/CLOSED_FAMILIES.json` carried, in the *execution algorithms* entry:

> "the repo's own measured impact budget caps gross notional at $0.8M–3.9M/day"

**That number cannot have come from this repository's depth data, and the reason is now
measured: a dataset whose finest observation is 48.8–156.6 bps cannot produce a capacity
figure at all.** The entry has been rewritten to say what is actually true — the book turns
**$651/day**, and the cost is 10 bps of flat fee plus ~1–12 bps of spread — and the
unsubstantiated $0.8M–3.9M/day claim is removed rather than left standing, because a
machine-enforced registry entry is a rule and a rule built on an unmeasured number is worse
than no rule.

**Its conclusion is unchanged and still correct** — execution algos are *not applicable* at
this size — but it now rests on a measurement.

## 6. New trap

**25. ⚠ A TABLE WHOSE HEADLINE NUMBER IS ITS OWN RESOLUTION FLOOR IS NOT A MEASUREMENT.**
`impact_by_size.csv` has 384 rows, twelve symbols and five regimes, and looks like a curve.
Its most common value, 100.0 bps, is **the distance from the mid to the innermost band the
feed happens to publish**. *Ask what the most common value in a derived table is, and what
would make it the most common value.* A capacity table is the worst place for this, because
the failure direction is "capacity looks unlimited".

**The general form, and it is the same shape as §38d's extrapolation:** *a number is not a
measurement of the market until you have checked what about the data would produce it
regardless of the market.*

## 7. What this does NOT establish

* **It is not a licence to run larger.** The impact relationship used here is measured at
  **aggregate market volume**; extrapolating a square-root impact law 168× beyond the
  measured range is an extrapolation, and it is stated as one. §5b forbids assuming a
  monotone law holds where it has not been measured, and this is exactly that boundary.
* **It does not measure the deployed book's own fills.** The book has never traded live —
  the forward collector is running with 0 trades, as expected at 0.19 expected signals per
  0.12 days. Everything here is from backtest fills and a separate cost measurement.
* **It does not touch the strategy, config, risk level, universe or position count.**
  `risk_per_trade: 0.005`, `max_stake_frac: 0.25`, `perp_leverage: 1.0`, N=40, 4h — unchanged.

## 8. Verdict

* **The capacity axis is answered**, and the answer is *capacity is not the binding
  constraint* — by a margin of ~170×, and by a decomposition that needs no order book.
* **The book-walk is BLOCKED on data resolution** and now says so instead of publishing
  $1,000.
* **A published capacity claim in the enforced registry is corrected**, because it was
  unsupported.
* **The binding constraints are the user's own config**: 24 slots and free balance (§31),
  both scale-invariant with capital, both fully under the user's control.
