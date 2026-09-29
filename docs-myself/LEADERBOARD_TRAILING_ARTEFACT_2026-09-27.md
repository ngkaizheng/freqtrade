# Leaderboard strategy — the fee frontier and the trailing-stop artefact

**Date:** 2026-09-27
**Object under test:** `NotAnotherSMAOffsetStrategy`
(`davidzr/freqtrade-strategies`, SHA `4d2d11e0`), the most-cloned entry in the
freqle.org public top 20 (ranks 10, 12, 20, 31).
**Harness:** Freqle's published sandbox config, reproduced exactly — spot, 5m,
33 Binance pairs, 1,000 USDT wallet, 10 slots of 100 USDT,
`--timerange 20210101-20260101`, `--cache none`, **no `--timeframe-detail`**.
**Data:** `user_data/data_leaderboard/`, 15,829,580 bars, 33/33 pairs.

> **Registered prediction (before any run):** the gross-vs-net curve **starts at or
> below zero at zero cost**, as both prior 5m implementations did.
> **THIS PREDICTION WAS WRONG AND IS RECORDED AS WRONG.** See §1.

---

## 1. Result at near-zero cost — the prediction is falsified

`--fee 0.000001`, 33 pairs, 1825 days, peak 119 MB:

| metric | value |
|---|---|
| Trades | **2,777** |
| Total profit | **+3,516.82 USDT (+351.68%)** |
| Avg profit/trade | **+1.27%** |
| Win rate | 78.1% (2,170 W / 607 L) |
| Max drawdown (closed trades) | 2.55% (108.72 USDT) |
| Max drawdown (wallet) | 3.02% |
| Sharpe (daily wallet) | **3.90** |
| Avg duration | 0:55:00 |
| Max consecutive losses | 10 |

**The curve does not start at or below zero. It starts at +351.68%.** The registered
prediction is falsified and must not be quietly restated.

---

## 2. Why +351.68% is still an artefact — and this is the actual finding

The exit-reason decomposition is the whole answer:

| Exit reason | Exits | Avg profit % | Total USDT | Win% | Avg duration |
|---|---:|---:|---:|---:|---:|
| **trailing_stop_loss** | **849** | **+3.07** | **+2,607.19** | **100.0** | **0:11:00** |
| roi | 170 | +4.48 | +761.40 | 96.5 | 1:20:00 |
| exit_signal | 1,752 | +0.20 | +358.05 | 66.0 | 1:15:00 |
| stop_loss | 6 | −34.99 | −209.83 | 0.0 | 0:22:00 |
| **TOTAL** | **2,777** | **+1.27** | **+3,516.82** | **78.1** | 0:55:00 |

**849 of 2,777 trades (30.6%) exit through `trailing_stop_loss` with a literal 100%
win rate, after a median hold of 11 minutes on a 5-minute timeframe.**

**A trailing stop cannot be 100% profitable.** The cause is in the engine's own
assumptions, `docs/backtesting.md:574-579`:

> - *"Trailing Stoploss is only adjusted if it's **below the candle's low** (otherwise
>   it would be triggered)"*
> - *"**High happens first - adjusting stoploss**"*
> - *"Low uses the adjusted stoploss (so exits with large high-low difference are
>   backtested correctly)"*

Inside every 5-minute candle the engine is permitted to assume price **first rallies to
the high, ratchets the stop up, and only then falls to trigger it**. A trailing exit
therefore cannot occur without a favourable intra-candle excursion having already
happened. The 100% win rate is that assumption, printed.

### 2.1 How much survives if the trailing path is removed

Dropping the 849 `trailing_stop_loss` trades leaves **1,928 trades and +909.63 USDT
(+90.96% over 5 years)** instead of 2,777 trades and +351.68%. That is the size of the
artefact: **roughly three quarters of the headline return.** The residual is still not
clean, because the 170 `roi` exits inherit the sibling assumption at
`docs/backtesting.md:567-568` — *"Exits are never 'below the candle', so a ROI of 2% may
result in an exit at 2.4%"* — and show a 96.5% win rate.

**So 96% of the trades that make money, and essentially all of the return, sit on the two
most optimistic assumptions in the simulator.**

### 2.2 The audited site says this itself, then ranks it first

Freqle's own FAQ, in its "Where backtests cut corners" section:

> *"freqtrade's own docs call trailing-stop backtests optimistic, because **within one
> candle it assumes price reached the high (ratcheting the trail up) before reversing to
> trigger. That's a best-case path, so the whole equity curve rests on the least
> reliable part of the simulator.**"*

and then:

> *"`--timeframe-detail` — re-evaluating those callbacks on a finer timeframe while
> keeping the main one for entries — **Freqle doesn't currently enable this**, for every
> check, League included."*

**The site states that the engine's trailing assumption is its least reliable input, that
it does not mitigate it, and ranks a strategy whose return is 76% trailing exits at #1
in a field of 5,330.**

---

## 3. Why the fee frontier is the wrong instrument for this strategy

A gross-vs-net sweep would answer "can it pay 20 bps?" — and at 2,777 trades × 100 USDT
over 5 years, turnover is only ~278× over the window, so the fee drag is small relative to
a +351% gross. **The cost was never this strategy's problem. The intra-candle ordering
is.** Recording that here so the sweep is not mistaken for the decisive test.

The decisive test is `--timeframe-detail`, which forces the trailing logic to be evaluated
on finer candles and removes most of the room to assume a favourable ordering. Results in
§4.

---

## 4. Correction to my own pre-run explanation

I first wrote that the faithful run needed ~20 GB because *"the strategy computes 150 EMA
columns per pair (2 × `range(5,80)`) and uses exactly two."* **That was wrong.**
`freqtrade/strategy/parameters.py:210-222` — the `range` property returns a **1-item**
list outside hyperopt mode: *"Returns a List with 1 item (`value`) in 'non-hyperopt' mode,
**to avoid calculating 100ds of indicators**"*. Measured: a slimmed copy produced
**18 columns / 5.8 MB, byte-for-byte the same as upstream.** The upstream file is already
memory-frugal. The real consumer is simply 15.8M bars held simultaneously. The slim copy
was built on the false premise and deleted once the measurement contradicted it.

**Two further toolchain notes, recorded because both cost time:**

- The 4 GB cap wrapper (`tools/leaderboard/run_capped.ps1`) polls `WorkingSet64` of a
  **`pwsh` wrapper process**, but Python runs as its child, so the reported peak
  (119 MB) is the wrapper's, not the interpreter's. **The cap did not actually bind the
  Python process.** A Job Object hard cap would fix this but `SetInformationJobObject`
  returns "The parameter is incorrect" on this host.
- Backtests need retries: a transient `RequestTimeout` on Binance `exchangeInfo` kills the
  run with "Could not load markets".
