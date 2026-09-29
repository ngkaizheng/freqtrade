# PRE-REGISTRATION — the venue cost lever: is the 515-universe failure Binance's?

**Date frozen:** 2026-09-29, **before any Bybit candle is downloaded.**

---

## 0. What the Binance work actually established, and what it left as a lever

Everything about the recent result is a **cost** story:

- the strategy is positive on the most liquid 50 of 515 perps and **−33.1% on all
  515**; widening the universe monotonically destroys mean R (0.2954 → −0.4855);
- `cost_R = bps/(stop_mult × atr_pct × 1e4)` predicts the ordering, and the
  ladder's monotone shape is that prediction;
- the market-neutralised excess is **negative at every rung that clears t ≥ 2.0**,
  so there is no cross-sectional edge to preserve — it is a timing overlay whose
  only asset is that it is cheap to run.

**Every one of those measurements is a measurement of Binance.** The venue has
never been varied. It is the last major axis untouched, and it is a *pure cost
lever*: same signal, same rule, different order book, different fee schedule,
different listing universe. That is the independence `RESEARCH_GOAL.md` §2.G
requires after a failure — not a re-parameterisation of a closed line.

## 1. Hypothesis

**H.** The 515-universe failure is a cost failure of **Binance's** long tail, not
a property of the signal. A venue whose USDT perps have a different liquidity
profile will show the effect at a **wider** rung, or not at all.

**H_null (the honest alternative).** Perpetual futures liquidity is arbitraged
across venues — the funding rates correlate at 0.74 and Bybit's effective spread
is within 2–10x of Binance's on the same contract (He et al. 2026, arXiv:2212.06888
v7). **If the tails are the same tail everywhere, the venue changes nothing and
the Binance result generalises.**

**⚠ H_null is the more likely outcome and is written down first on purpose.**

## 2. The test, fixed now

| # | criterion | what decides it |
|---|---|---|
| **V1** | measure the **cost per unit of risk** on each venue for the same symbols: `cost_R = round_trip_bps / (4.0 × atr_pct × 1e4)` with the venue's own taker fee and a spread estimate from its own candles | If Bybit's cost_R is materially lower on the tail, H has a mechanism |
| **V2** | run the **frozen rule, unchanged**, on Bybit's top-N by the same liquidity proxy | the only comparison that is not a re-tune |
| **V3** | the ladder on Bybit: N ∈ {25, 50, 100, 200, 400} | same shape test as the Binance ladder, so the two are comparable |
| **V4** | **at what rung does t ≥ 2.0 hold on Bybit, and is that rung WIDER than on Binance?** | The whole hypothesis in one number |
| **V5** | the by-timestamp t and the market-neutralised excess on Bybit | so the Bybit book is not judged by a different standard than the Binance one |

**If V4 shows the same or a narrower rung, the venue line is CLOSED and the
Binance result is confirmed as a property of the market, not of the exchange.**

## 3. Data — feasibility was established BEFORE this file

`tools/perp_short/venue_probe.py` and `venue_paging.py`:

- **OKX**: 478 live USDT SWAPs, but `history-candles` returns 100 bars/page and
  needs ~76 more pages per symbol to reach 2023-01-01 (~28 s/symbol).
- **Bybit**: 818 USDT linear instruments, `kline` returns 1000 bars/page and
  reaches 2024-01-03 after 6 pages — **2 more pages to 2023-01-01** (~6 s/symbol).
  **Bybit is therefore the chosen venue**, on measured feasibility, not preference.

## 4. Known asymmetry, stated before running

**Bybit's standard taker fee is 5.5 bps/side against Binance's 5.0**, so Bybit is
*more* expensive per trade in fees. Any improvement therefore has to come from
spread and depth, not from the fee schedule. **If Bybit loses on V1, that is the
answer and H is dead.**

**Also not comparable: the listing universe.** Bybit listed most alt perps later
than Binance, so a 2023-2026 Bybit panel is a different set of contracts. That is
part of what is being measured, and it is also why the cohort decomposition (how
much survives) is run again on Bybit rather than assumed.

## 5. Forbidden

- Tuning the signal, stop, target, time stop or filter for Bybit. The rule is
  frozen and the comparison is worthless if the rule moves.
- Quoting Bybit without the Binance numbers beside it.
- Quoting a Bybit rung's naive t without its by-timestamp t and its
  market-neutralised excess, after V5.
- Dropping Bybit symbols that 404. They are recorded and counted, never silently
  removed.
