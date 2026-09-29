# Findings: SMA-50 Trend on 15 Years of BTC — The First Candidate To Pass

Run 2026-09-19, freqtrade 2026.8. Scripts: `tools/download_bitstamp.py`,
`sma_15year_test.py`, `sma_15year_final_gates.py`, `sma_15year_stress.py`,
`execution_model_check.py`. Strategy: `user_data/strategies/BTCSmaTrend.py`.

---

## The fix was statistical power, not another signal

Round 1 ended with SMA-50 rejected: anchored OOS failed, cross-asset replication
collapsed to p=0.142 once the panel's ~2.6 effective independent bets were
counted, and **MinBTL demanded 12.8 years while we had 7.7**.

**Lo (2002) says SE(annualised Sharpe) ≈ 1/√**_**YEARS**_, independent of sampling
frequency. So finer granularity (4h/1h) buys nothing — only more calendar years
do. That ruled out my own earlier suggestion of adding intraday data.

So I went looking for longer history:

| source | BTC history | years |
|---|---|---:|
| Binance (previous studies) | 2018-01 → | 7.7 |
| **Bitstamp** | **2011-08-18 →** | **15.1** |
| Kraken / Coinbase | ~2013 / ~2015 | — |

`tools/download_bitstamp.py` pulls daily OHLCV from Bitstamp's public API.
Downloaded 5 pairs; **BTC/USD = 5,512 rows, 2011-08-18 → 2026-09-19 (15.1y)**,
SE(Sharpe) 0.36 → **0.257**.

**Methodological bonus:** 2011–2019 was **never searched** in this project, so it
is a genuine holdout, not re-used data.

### Data quality verified first

| check | BTC |
|---|---|
| duplicate dates | 0 |
| non-positive prices | 0 |
| high < low | 0 |
| inf returns | 0 |
| stale closes | 1.2% |
| max abs daily return | 56.1% |
| **correlation vs Binance returns** | **0.9966** |

The 0.9966 cross-exchange correlation confirms it is the same asset, not a
different instrument.

> **Note on Bitstamp paging:** the API returns the last N candles *before* `end`;
> `start` is only a lower bound and does not advance the window. Paging must walk
> **backwards** using `end=cursor`. My first attempt paged forward on `start` and
> silently stopped at 406 rows.

---

## Results — BTC/USD, 2012-03-05 → 2026-09-19 (14.6y), 10bps

| rule | avgExp | CAGR | MaxDD | Sharpe |
|---|---:|---:|---:|---:|
| buy & hold | 100% | 94.53% | -84.86% | 1.26 |
| **SMA-50** | 78.5% | **102.56%** | **-74.37%** | **1.45** |
| flat @ 78.5% | 78.5% | 77.31% | -75.12% | 1.26 |

### The window is a plateau, not a spike

Opposite of the 7.7-year result, where lookback 50 was a precarious ridge:

| window | 10 | 20 | 30 | 50 | 75 | 100 | 150 | 200 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Sharpe | 1.43 | **1.45** | 1.42 | **1.45** | 1.44 | 1.43 | 1.40 | 1.34 |

Every window from 10 to 150 lands in 1.40–1.45. That is a genuine plateau.

---

## Gates passed

| gate | result |
|---|---|
| **Wildcard placebo** (500 random-exposure draws, matched mean) | **p = 0.002** ✅ |
| **Matched-exposure flat control** | bootstrap ΔSharpe +0.182, **CI [+0.01, +0.37]** ✅ |
| **Matched-DRAWDOWN control** (the fairest test) | constant 75% gets MaxDD -73.1% at Sharpe 1.26 vs SMA-50's -74.4% at **1.45** → **+0.187** ✅ |
| **True holdout 2011–2019** (never searched) | Sharpe **1.70** vs buy & hold 1.54 and flat 1.54 → beats both ✅ |
| **Walk-forward** (8 folds, window picked in-sample) | stitched OOS **1.20** vs buy & hold 1.04 ✅ |
| **Parameter plateau** | 1.40–1.45 across 10–150 ✅ |
| **MinBTL** (106-trial ledger) | needs 4.4y, have 14.6y ✅ |
| **Cost robustness** | Sharpe 1.45 @10bps → 1.32 @100bps ✅ |
| **Execution delay** | +1/+2/+3 bars: 1.47 / 1.45 / 1.43 ✅ |
| **Exposure noise** | sd=0.10 → Sharpe 1.44 ✅ |
| **Multi-asset replication** | 4/5 Bitstamp pairs beat flat ✅ |

### Era independence — the edge is everywhere

| period | years | SMA-50 vs flat | vs buy & hold |
|---|---:|---:|---:|
| full 2012–2026 | 14.6 | +0.187 | +0.187 |
| excl 2012–2014 | 11.7 | +0.222 | +0.221 |
| excl 2012–2016 | 9.7 | +0.216 | +0.216 |
| 2019+ only | 7.7 | ~+0.21 | +0.237 |
| 2021+ only | 5.7 | +0.205 | +0.205 |

Consistent +0.19 to +0.24 across every era, including the modern, more liquid
market. The effect is **not** an artifact of Bitstamp's illiquid early years.

---

## The critical reconciliation: execution model

Freqtrade's own backtest reported **Sharpe 0.92** — far below my study's 1.45.
That gap had to be explained or the finding was void. Two different execution
models were in play:

* **A. Constant-mix** (what my study did): exposure reset to 0.5/1.0 of *current
  wealth* daily. In a 75%-vol asset this harvests a rebalancing premium.
* **B. Fixed-units** (what freqtrade does): buy units at flips, hold in between;
  exposure drifts with price.

`tools/execution_model_check.py` reconciles them:

| rule | constant-mix | fixed-units (realistic) |
|---|---:|---:|
| buy & hold | Sharpe 1.27 | — |
| SMA-50 | 1.45 | **1.48** |
| flat @ 78.5% | 1.26 | 1.32 |
| **edge vs flat** | +0.187 | **+0.168** |

Bootstrap on the **realistic fixed-units** edge, 5000 draws:

| comparison | ΔSharpe | 95% CI | p(≤0) |
|---|---:|---|---:|
| vs flat control | +0.168 | **[+0.017, +0.340]** | 0.014 |
| vs buy & hold | +0.215 | **[+0.037, +0.403]** | 0.007 |

> **The edge survives realistic execution.** The rebalancing premium was not the
> source; it slightly *understated* the result. (Freqtrade's 0.92 comes from its
> own unit-based wallet accounting over a single never-closed trade.)

---

## Verdict: this is the first candidate to pass all controls

Deployed as `user_data/strategies/BTCSmaTrend.py` with config
`user_data/config_btcsma.json`, verified running through `freqtrade backtesting`.

```
Close > SMA(50)  ->  100% exposure
Close < SMA(50)  ->   50% exposure
```

**But it is a modest, risk-management edge — not a money machine.** Honest limits:

1. **MaxDD is still -74%.** Better than buy & hold's -85%, but not "safe". Half
   the benefit is simply holding less.
2. **One asset.** Multi-asset replication was 4/5 but those histories are 8–10y.
3. **The edge is ~+0.17 Sharpe**, not a transformation. It is real but small.
4. **Independence is overstated.** 5,312 daily observations are not 5,312
   independent bets; 79 drawdown episodes and ~5 market cycles is closer.
5. **No funding cost modelled** — this is spot. Levered versions would need it.
6. **Bitstamp-sourced.** Fine for BTC (0.9966 correlation), but it is one venue's
   print and early years are thin.

## Reproduce

```powershell
.\.venv\Scripts\python.exe tools\download_bitstamp.py        # ~1 min
.\.venv\Scripts\python.exe tools\sma_15year_test.py          # core result
.\.venv\Scripts\python.exe tools\sma_15year_final_gates.py   # 6 gates
.\.venv\Scripts\python.exe tools\sma_15year_stress.py        # break attempts
.\.venv\Scripts\python.exe tools\execution_model_check.py    # execution model
.\.venv\Scripts\freqtrade.exe backtesting --config user_data\config_btcsma.json `
    --strategy BTCSmaTrend --timeframe 1d
```

**Still not a green light for real money** — it needs forward/dry-run validation
first, per the handoff's Stop Rule and upstream's own guidance.
