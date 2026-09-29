# PRE-REGISTRATION — does within-bar sequencing carry information the 5m bar does not?

**Frozen: 2026-09-28, before the test script was written.** Author: agent session.
Part (c) of the open goal: "upgrade the data (tick-level OFI rather than kline
taker-buy)".

---

## 1. What the repo already measured, and what it did not

`PREREG_FACTOR_SCAN_2026-09-27` measured **bar-level** signed volume (CVD =
`2·taker_buy_quote_volume − quote_volume` over 12 bars), RVOL and VWAP deviation, both
directions, 20 percentile buckets, 120-test primary grid, 9 symbols × 3.47M bars:

- best gross edge anywhere: **2.47 bps**, against a **12.0 bps** calm round trip —
  **short by 5×**
- CVD specifically: **t_adj 0.54 long / −0.88 short** — no significant gross effect
- and the scan was **not underpowered**: the dispersion check below shows the MDE on
  that sample was far below 2.47 bps, so it would have detected it. **The line failed
  on effect size, not on sample.**

What was never tested: **the path of the bar, not its sum.** A 5m candle collapses five
one-minute moves into open/high/low/close/volume, discarding the order in which they
happened. The question here is whether that discarded order carries information.

## 2. The data upgrade actually available, and the limit of it

The goal asked for **tick-level OFI**. Two facts constrain what can be done, both
checked rather than assumed:

1. **True order-flow imbalance (Cont–Kuo–Stoikov) is NOT obtainable for these venues.**
   It requires L2 quote updates. Binance Vision publishes for spot `trades`, `aggTrades`,
   `bookDepth` (percentage bands) and `bookTicker` — **no L2 quote stream**. A tick-level
   OFI claim on this data would be a claim about a quantity that was never measured.
2. **Tick-level trades are too large to collect here.** `--dl-trades` exists, but a
   single pair-year is 10⁸ rows. The S3 mirror throttles to one file per 12 s, so a
   sample large enough to matter is hours of transfer for a question that can be
   answered more cheaply first.

**What IS already on disk: 1-minute candles**, 6 pairs × 2,628,367 bars, 2021-01-01 →
now (`user_data/data_leaderboard/*_USDT-1m.feather`). Each 5m bar therefore decomposes
into 5 one-minute sub-bars.

**This is a genuine upgrade over 5m and it costs no download. It is not tick-level, and
that is stated as a limit on the conclusion, not glossed.**

## 3. The statistic

For each 5m bar, from its five 1m children:

- **aggregate (control):** the signed volume over the whole bar, the statistic the repo
  already tested and found null.
- **path (treatment):** the **sign of the final 1m close-to-close move** — i.e. where in
  the bar the net move landed. Under a pure martingale this carries no information; if
  the market trends within bars, the final sub-move sign predicts continuation.

The treatment is deliberately simple. A richer path statistic would multiply the search
family for no gain in identifiability, and this repo's base rate says simple → null.

## 4. The test

Buckets of the path statistic (sign ∈ {−1, +1}), conditional forward return at
**15m** (3 bars) and **1h** (12 bars), minus the same pair's unconditional forward
return over the same window. Both directions of the conditioning are reported.

Significance: **block bootstrap on the time-sorted signal sequence**, block = 12,
20,000 reps. Pair-major concatenation is invalid and has already produced one false
positive in this project (t = 2.81 where the correct value is 2.08).

## 5. The bar — and it is ONE-SIDED, which is the point

The question is not "is there any effect". It is: **is the effect big enough to trade?**

- **CLOSE the line** if the **95% upper bound** of the lift at the best horizon is
  **below 12.0 bps** (the measured calm round trip). Below the cost hurdle there is
  nothing to deploy, whatever the t says.
- **CANDIDATE** only if the **95% lower bound** exceeds **12.0 bps** and the corrected
  bar is met.
- Anything between is reported as unresolved-with-the-interval-shown.

This design is what `AGENTS.md` §1a asks for: the test is capable of concluding, and the
conclusion it is capable of is a close, not a discovery. The power check
(`tools/leaderboard/ofi_power_check.py`) shows the available sample resolves a 12 bps
effect several times over, so "the data was too thin" will not be available as an
excuse — and equally, a null will be a real null.

## 6. Falsification, stated before running

- **A close closes the line.** It does not license trying aggTrades next, or a
  different path statistic, or a longer horizon set. This is the 92-hypothesis search
  that produced 0 survivors.
- **If the path statistic turns out significant and large**, that is a surprise against
  a strong prior, and it would license a pre-registration for the tick-level upgrade —
  not a deployment.

## 7. What this line would and would not settle

**Would settle:** whether intra-bar sequencing matters on this venue at 1-minute
resolution, and therefore whether the "upgrade the data" direction has any value at all.

**Would not settle:** true tick-level order flow, which remains unmeasured because the
data does not exist in the required form. If this closes, the honest statement is "no
upgrade to tick-level was attempted, and here is why the prerequisite is unmeasured",
not "tick-level order flow does not work".
