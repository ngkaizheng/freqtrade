# The cost premise, measured across regimes — 2026-09-27

**Headline: the cost premise has now been examined in stress, and it does not
decide anything.** The 12–18 bps round trip was measured once, on a calm day,
and never in a regime that mattered. It is not a constant. But neither live line
turns on it: E#4 dies on the signal, and E#6 survives a 2.7× cost increase.

**Also new, and the one gap §1 named:** the first measurement of order-book
depth on the **long tail**, and the first *historical* depth at all (2023-01
onward), where the previous measurement was a single live snapshot of majors.

**Scripts:** `tools/cost/measure_impact.py`,
`tools/cost/cost_regime_sensitivity.py`,
`tools/cross_section/probe_depth_availability.py`,
`tools/cross_section/measure_cost.py`
**Tests:** `tests/tools/test_cost_impact.py` — suite now **256/256**
**Data:** `shark_data/costs/`

---

## 1. What was already known, and what this adds

`RESEARCH_STATE.md` §1 records the existing cost measurement: live Binance
depth, 2026-09-26, **19 of 20 symbols, majors only** — and states plainly that
**"no long-tail cost was ever measured."** §8 point (7) adds that the median is
the wrong aggregate for an equal-weight book, which pays the **mean**.

| | before | this work |
|---|---|---|
| depth data | 1 live snapshot, majors | **2023-01 → present, 12 symbols incl. long tail** |
| depth regime | calm only | includes **2024-08-05 cascade** |
| spread cost | 1 calm day | **4 regimes: 12.0 / 15.6 / 22.8 / 34.9 bps** |
| long tail | never measured | **measured, 6 long-tail names** |

---

## 2. Spread cost by regime

Roll effective spread on `aggTrades`, 8 of today's top perps, one day per
regime. Round trip = 2 × spread + 2 × 5 bps taker.

| date | context | median RT | range | median Roll r² |
|---|---|---:|---|---:|
| 2026-09-20 | calm | **12.0 bps** | 10.4–18.0 | 0.40 |
| 2024-08-05 | long-tail cascade | **15.6 bps** | 13.2–19.3 | 0.32 |
| 2025-10-10 | volatile | **22.8 bps** | 14.7–28.1 | 0.32 |
| 2020-03-12 | COVID crash | **34.9 bps** | 27.4–57.1 | 0.32 |

**The spread across regimes is 2.9×.** The project's 12–18 bps constant is the
**calm-day** number used as a constant.

### The word "conservative" has to go

It was already wrong for the calm case — 12.0 measured against an 18 bps ceiling
is not a margin of safety, it is a coincidence. In every stressed regime it is
simply false. **`12–18 bps` should be read as "a calm day's cost", never as a
bound.**

### A correction I have to make to my own first pass

An earlier draft of this work placed these numbers against Arefev's "~59 bps" and
concluded the measurement landed between the two, closer to the null.

**That comparison is void and the conclusion was inverted.** Per §8 point (8),
the 59 bps figure is fabricated by dividing Arefev's cost by *Fieberg's*
turnover, and the units are category-confused — Arefev's 40 bps/week is
all-in and weekly, this project's 3.1 bps is per-rebalance, book-only, pre-fee.
Like-for-like, the project's own all-in is *more* pessimistic than Arefev's, not
5× less. The claim that the literature disagrees with this project by 3–5× on
cost is **inverted**, and the comparison is not repeated.

---

## 3. Market impact from historical depth

### The data, and how its existence was established

Binance Vision publishes `bookDepth` for USD-M perpetuals —
`timestamp, percentage, depth, notional` at 30-second intervals, cumulative USD
size at each of ±0.2/1/2/3/4/5% from mid.

**Availability: 2023-01-01 → present. 2022-12-31 is a confirmed 404.** Verified
by `tools/cross_section/probe_depth_availability.py`.

That window covers the back **55%** of the E#4 panel — including 2023–24, when
its gross edge was real. **Depth cannot cover 2020–2022**, so every impact
statement here is scoped to the modern era and says so.

### The method, and the assumption that must not be forgotten

Crossing cost for size N, in bps of mid:
`100 × Σ(consumed_i × pct_i) / Σ consumed_i`. It is mid-price-free, so no kline
join can introduce a timestamp mismatch.

**The limitation, and it is visible in the output.** bookDepth reports fixed
percentage buckets, so the distribution *within* the innermost bucket is
unobserved. An order smaller than that bucket is priced by an assumption, and
the assumption overstates cost. The artefact is a **flat floor of exactly 40.0
bps round trip (2 × 0.2%) across every symbol** in the impact table — that floor
is the assumption, **not a measurement**. Consuming half of a bucket still costs
the bucket's full offset; there is no interpolation within it. The table must
not be read below the innermost band. This is pinned by
`test_impact_inside_the_first_level_is_that_whole_level`.

The headline numbers below therefore use **USD depth, which is directly observed
and needs no assumption at all.**

### Measured depth — and the long tail, which §1 says was never measured

Median USD resting within the band, thin side:

| | 2026-09-20 (0.2% band) | 2023–2026 median (1% band) |
|---|---:|---:|
| NEOUSDT | $10,420 | $251,867 |
| ALGOUSDT | $17,366 | $383,944 |
| ATOMUSDT | $41,608 | $520,840 |
| ETCUSDT | $59,770 | $803,328 |
| FILUSDT | $115,575 | $862,040 |
| LINKUSDT | $242,706 | $1,986,180 |
| XLMUSDT | $276,347 | $530,335 |
| DOGEUSDT | $822,432 | $2,768,532 |
| BTCUSDT | $43,295,732 | $93,509,401 |

The long tail is **one to three orders of magnitude thinner than BTC**, and
NEOUSDT holds roughly **$10k within 0.2% of mid**. Any equal-weight book that
holds a thin name is capped by it, not by its median member.

**The 0.2% level is a recent addition to the feed** — only the 2026 file carries
it. The two columns are different resolutions and **must never be averaged**.

### Impact is small at any book size a test would use

Even granting the entire 16 bps impact budget to the thinnest long-tail name,
the implied cap on gross book notional is **$0.8M/day** (0.2% band) to
**$3.9M/day** (1% band). Two different vintages and resolutions agreeing on a
~$14M/day median is a useful consistency check.

**E#6's universe is the top 50 by volume** — the deepest names measured — so
this is the friendliest available case for the impact assumption, and the
honest one to quote for E#6 specifically.

---

## 4. What this does to each verdict

### E#6 (the live line): unchanged, and the conclusion is favourable

| regime | all-in | E#6 net/yr |
|---|---:|---:|
| calm | 12.0 bps | +15.8% |
| long-tail cascade | 15.6 bps | +15.3% |
| volatile | 22.8 bps | +14.2% |
| COVID crash | 34.9 bps | **+12.3%** |

The most expensive regime measured is **2.7×** the 13.1 bps headline assumption
and E#6 still earns +12.3%/yr. `E6_RESULT.md` already published the frontier out
to 48.0 bps in **book size**; this extends it into **time**, and it does not flip
either.

**E#6's failure is not a cost failure, and now demonstrably so.** What it fails
on is G4 (Sharpe 0.735 vs 0.95) and G3 (t_adj 1.50 vs 2.0) — sample and
significance. The decay (2025 +0.030, 2026 −0.133) remains the live concern.

### E#4: already closed, and this work does not reopen it

**This work initially got E#4 wrong and the error is recorded below.** Its first
pass computed "impact headroom" against the published `0.274%/day` gross and
`26.6 bps` breakeven. **Both were voided by the 2026-09-26 adversarial review**
(§1, §8): they come from a Gaussian map `3.51 × |IC| × sigma` that overstates
the realised portfolio return by 17–90×. The real decile long-short earns
+0.0059 to +0.0160%/day against a ~1.6 bps breakeven. **`e4_impact_headroom.py`
was deleted rather than corrected**, because "impact headroom for E#4" is not a
question any live line is asking.

The conclusion is unchanged and was right for the right reason: **the binding
constraint on E#4 is the signal, not cost.**

### The closed lines harden, which is expected

- **Carry** (§3.17) closes on an *excess* of −0.88 to −1.56 %/yr, not on a cost
  threshold. A higher cost does not change it.
- **SHARK-07** (§3.11) has a best conditional excess of **+4.4 bps against a
  12–18 bps cost**. At 22.8–34.9 bps that margin is 2–3× worse. The line stays
  closed and its collection stop condition stays met, so **collection should
  continue**.
- **5m / 4h breakout** closed on friction of 0.75R and 0.088R against gross
  0.131R / t=3.71. A 2–3× cost increase makes both worse, never better.

### The honest summary

> The cost premise is the input `START_HERE.md` §3.2 called "the single
> least-examined load-bearing input". It has now been examined, across four
> regimes, on the long tail, with a real depth term. **It turns out not to be
> load-bearing for any live line.** That is a real result, and it is a null.

---

## 5. Limits of this work

- **2020-03-12 is a different market, not today's tail.** Only 4 of 8 symbols
  had a tape, so the figure rests on BTC/ETH/ZEC/XRP — today's top names that
  happened to exist in 2020, a survivorship selection inside a small sample. He
  et al. measure perp spreads 48–73% narrower post-2022. **Do not carry 34.9 bps
  forward as a present-day expectation.**
- **Single days, not distributions.** One observation per regime. A backtest
  trades on every day, so the number that matters is a turnover-weighted mixture
  — and the weighting is a modelling choice the reader has to see, not one this
  report makes silently.
- **Roll's assumptions weaken exactly where this matters.** r² falls from 0.40
  (calm) to 0.32 (crash): most of the return variance on the stressed tapes is
  not the bid-ask bounce the estimator is built on.
- **Depth during a cascade is unmeasured, and that is where it would matter.**
  A standing 30-second snapshot says nothing about the book during a liquidation
  cascade. A snapshot of the book is evidence about the book, not about fills.
- **Realised fills and partial-fill frequency are not measured at all.**
- **No impact term is included in the §2 spread table**; §3 supplies it for the
  modern era only.

---

## 6. Traps paid for on this task

Four silent failures, all producing confident wrong output rather than an error.

1. **S3 answers rate-limited clients with `NoSuchKey` 404, not 429.** A URL that
   returns 200 on one request returns 404 on the next five, then 200 after a
   ~90 s pause. An availability scan trusting the first response **reported that
   no order-book depth data exists anywhere** — the single most consequential
   false negative available on this task. `probe_depth_availability.py` now
   carries a positive control, requires two spaced 404s, and re-checks the
   control at the end. *Same shape as §3.10, where reading the wrong response key
   made a successful empty response look like "no data available".*
2. **A renderer mapping a string state through a boolean lookup.** The grid
   compared a state string against `True`, never true, so "present" and "absent"
   both rendered absent — a confident table of uniform absence printed while the
   same run's control probe said present. A self-consistency assertion now fails
   the run. *This is §3's `&=`-from-all-False family.*
3. **Per-side row dropping breaks alignment.** Dropping ragged snapshots
   independently per side left 2879 ask rows against 2831 bid rows that no longer
   referred to the same instants. Both sides are now intersected on their common
   complete snapshots first.
4. **"Worst regime" computed with `min()`**, which selected the *calm* day as
   the stress case — understating the cost range 2.9× and reporting a 0.9×
   "stress" multiplier where the truth is 2.7×. Nothing errors; the number is
   quietly wrong in the reassuring direction.

Also fixed: `measure_cost.py` walked backwards off the requested date when a tape
was missing, so a stress-date measurement could silently blend in calm sessions.
It now records the date actually used and flags the drift.

---

## 7. Recommended next actions

1. **Stop describing 12–18 bps as conservative or as a bound.** It is a calm-day
   measurement. Any cost-based backtest should carry a stress case at 22–35 bps.
2. **E#6 remains the live line and remains un-confirmed.** Its blockers are
   sample size and decay, not cost. Do not re-open the cost argument.
3. **Keep collecting.** The liquidation collector is now scheduled daily
   (`shark-liquidation-collect`, 08:30, 12h run) and the forward and depth
   collectors are live. All three are the only source of data that cannot be
   recovered later.
4. **Consider adding `bookDepth` to the forward collector.** It is the only
   public record of what the book looked like *while a signal was firing*, and
   therefore the only way to answer the cascade question.
