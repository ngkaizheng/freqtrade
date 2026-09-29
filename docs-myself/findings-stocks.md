# Findings: Binance Tokenized Stocks — Data Available, Mechanism Absent

Run 2026-09-19. Scripts: `tools/probe_binance_stocks.py`,
`tools/stock_data_audit.py`, `tools/stock_tickers_test.py`.

**Answer to "can Binance get these?" — yes. But moving to stocks removes the
mechanism that makes the strategy work.**

---

## 1. Binance does list them — as `TRADIFI_PERPETUAL`

`tools/probe_binance_stocks.py` scanned exchangeInfo. Spot has **0** stock
instruments; **USDT-M futures has 199 `TRADIFI_PERPETUAL` contracts**, including
every ticker you named.

| ticker | symbol | first day | days | last-day quote volume |
|---|---|---|---:|---:|
| TSLA | TSLAUSDT | 2026-01-28 | 234 | 3.5M |
| INTC | INTCUSDT | 2026-02-02 | 229 | 6.2M |
| AMZN | AMZNUSDT | 2026-02-09 | 222 | 0.9M |
| META | METAUSDT | 2026-03-26 | 177 | 4.9M |
| NVDA | NVDAUSDT | 2026-03-26 | 177 | 8.5M |
| GOOGL | GOOGLUSDT | 2026-03-26 | 177 | 6.6M |
| SPY | SPYUSDT | 2026-04-06 | 166 | 14.5M |
| QQQ | QQQUSDT | 2026-04-06 | 166 | 15.3M |
| AAPL | AAPLUSDT | 2026-04-06 | 166 | 3.7M |
| MU | MUUSDT | 2026-04-07 | 165 | 37.3M |
| **SNDK** | SNDKUSDT | 2026-04-07 | 165 | **134.2M** |
| AVGO | AVGOUSDT | 2026-04-20 | 152 | 2.3M |
| MSFT | MSFTUSDT | 2026-04-20 | 152 | 1.4M |
| AMD | AMDUSDT | 2026-05-06 | 136 | 3.2M |
| QCOM | QCOMUSDT | 2026-05-06 | 136 | 1.1M |
| **SPCX** | SPCXUSDT | 2026-05-21 | 121 | 21.1M |
| NFLX | NFLXUSDT | 2026-06-09 | 102 | 0.6M |

**But the history is only 3–8 months.** SE(Sharpe) at 0.7 years ≈ **1.2** — a
backtest on the perps alone is statistically meaningless. That is a real
limitation of the *execution venue*, not of the research.

For research, 15 of your 17 tickers are already in the handoff cache with
**~16.7 years** of daily data. Only **SNDK and SPCX** have no long history
(SNDK is a recent SanDisk spin-off; SPCX has no local file).

---

## 2. What a `TRADIFI_PERPETUAL` actually is

These are **not shares**. They are perpetual futures tracking the equity, which
changes the risk in ways that matter for your stated goal ("less risk than
crypto"):

* **Leverage** — margin product; liquidation is possible
* **Funding** — periodic payment between longs and shorts. A spot shareholder
  pays nothing; over months this is a real drag and it is **absent from every
  equity backtest**
* **24/7 trading vs US session** — the perp moves when the stock cannot, and can
  diverge around earnings and halts
* **Counterparty/jurisdictional risk** — a Binance product, not a brokerage
* **No track record** — months old, so execution quality and funding behaviour
  are unvalidated

**Your premise is half right:** the *underlying* is genuinely lower risk (equity
vol ~15–20% vs crypto ~75%). But the *perp wrapper* reintroduces leverage,
funding and counterparty risk. **A spot brokerage account would be lower risk
than a Binance perp for the same underlying.**

---

## 3. The decisive test — I already knew the answer and re-verified it

Round 4 tested this exact rule on 109 US equities and it **failed 0/4**. So
rather than assume, I tested **your specific tickers** with pre-registered
predictions:

| ticker | VR(20) | edge vs flat | rule SR | BH SR | rule DD | BH DD |
|---|---:|---:|---:|---:|---:|---:|
| NFLX | 1.093 | **+0.052** | 0.86 | 0.81 | -55% | -82% |
| TSLA | 1.069 | -0.009 | 0.86 | 0.87 | -58% | -74% |
| INTC | 0.984 | -0.049 | 0.46 | 0.51 | -70% | -71% |
| AMD | 0.984 | +0.018 | 0.72 | 0.70 | -70% | -84% |
| QCOM | 0.946 | +0.001 | 0.48 | 0.48 | -42% | -45% |
| NVDA | 0.909 | +0.009 | 1.06 | 1.05 | -49% | -66% |
| MU | 0.891 | +0.008 | 0.79 | 0.78 | -64% | -74% |
| AAPL | 0.880 | -0.030 | 0.95 | 0.98 | -30% | -44% |
| META | 0.859 | -0.021 | 0.68 | 0.70 | -65% | -77% |
| GOOGL | 0.841 | -0.041 | 0.76 | 0.80 | -41% | -44% |
| AMZN | 0.824 | -0.034 | 0.79 | 0.82 | -49% | -56% |
| AVGO | 0.734 | **-0.211** | 0.85 | 1.06 | -35% | -48% |
| MSFT | 0.728 | -0.093 | 0.74 | 0.83 | -26% | -37% |

| | value |
|---|---|
| mean VR(20) | **0.903** |
| mean edge vs matched flat | **-0.031** |
| beats flat control | **5/13** |
| beats buy & hold Sharpe | **5/13** |
| **drawdown improved** | **13/13** |

### Pre-registered predictions

| # | prediction | result |
|---|---|---|
| Q1 | your tickers more trendy than broad universe | ✅ 0.903 vs 0.834 |
| Q2 | their edge less negative than broad | ✅ -0.031 vs -0.067 |
| Q3 | still below crypto | ✅ 0.903 vs **1.025** |

**All three confirmed.** Your instinct was directionally right on *both* counts:
these names are trendier than the average stock **and** still below crypto — and
that ordering exactly predicts the edge.

---

## 4. The honest conclusion

**Moving to stocks does not rescue the strategy — it removes the mechanism.**

| universe | mean VR(20) | mean edge vs flat | beats flat |
|---|---:|---:|---:|
| crypto majors | **1.025** | **+0.094** | 16/20 |
| your tickers | 0.903 | **-0.031** | 5/13 |
| broad equities | 0.834 | -0.067 | — |

The SMA rule needs **VR > 1** (positive persistence). Your tickers sit at
**0.903** — better than the broad market, still below the threshold. So the rule
is at best neutral on them, and **0.031 Sharpe worse than simply holding less**.

**What stocks DO give you:** drawdown improved in **13/13** names (e.g. NFLX
-82% → -55%, AMD -84% → -70%). That is the same *mechanical* benefit identified
in round 1 — real, but obtainable by just holding less, with no signal.

---

## 5. What is actually worth pursuing on stocks

Your real goal is **lower risk**, and there is one equity result in this project
with genuine evidence behind it — and it is not the SMA rule:

> **The handoff's own validated finding:** MA200 exposure management on SPY,
> **33.6 years**, drawdown **-55.19% → -30.13%**, in 7 of 8 markets.
> Its explicit framing: *this is a RISK-MANAGEMENT rule, not an alpha signal.*

That has 33.6 years of data (vs our 15.1 max), a validated mechanism, and it
targets risk rather than return. It is also **honest about being mechanical** —
the handoff proved via 200 permutations that random de-risking achieves similar
drawdown reduction.

If lower risk is the goal, the productive question is not "which stock tickers
trend?" but:

> **"What exposure policy keeps the drawdown survivable, and is it cheap to
> implement?"** — where the answer may simply be *hold less*, honestly labelled.

---

## 6. Recommendation

1. **Don't conclude stocks are safer for this strategy** — the edge is gone there.
2. If you want stock exposure specifically, **don't use Binance perps for a
   buy-and-hold-style exposure rule**: funding plus leverage plus counterparty
   risk is a worse wrapper than spot. And 3–8 months of perp history cannot
   validate anything.
3. If the goal is lower risk, test the **handoff's MA200 policy on SPY** with its
   33.6 years, and judge it as risk management — not as a return strategy.
4. `SNDK` and `SPCX` have no long history locally; I have not tested them
   beyond the 3–5 month Binance perp data, which is too short to use.

## Reproduce

```powershell
.\.venv\Scripts\python.exe tools\probe_binance_stocks.py   # what exists
.\.venv\Scripts\python.exe tools\stock_data_audit.py       # history vs execution
.\.venv\Scripts\python.exe tools\stock_tickers_test.py     # your tickers, mechanism
```
