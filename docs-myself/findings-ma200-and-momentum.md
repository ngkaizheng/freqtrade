# Findings: MA200 Exposure & Crypto Cross-Sectional Momentum

Run on 2026-09-19 against **freqtrade 2026.8** (branch `stable`, `9f10e357a`).
Methodology follows `quant-research-handoff/`. Scripts in `tools/`.

**Follow-up:** `findings-drawdown-control.md` tests whether vol targeting or a
trend filter can fix the drawdown problem both studies ran into. Verdict there:
also negative — the reduction is mechanical.

Index of all studies: `RUNBOOK.md` → "Findings & studies index".

---

## TL;DR

| Study | Verdict | Why |
|---|---|---|
| **MA200 exposure** (BTC/ETH/XRP) | ❌ Not supported | Drawdown did improve 3/3, but the **placebo test cannot distinguish it from random de-risking** |
| **Cross-sectional momentum** (47 pairs) | ⚠️ Promising but unusable | Genuinely beats random selection (p<0.001) and has **no look-ahead** — but **-89% drawdown** and **unquantified survivorship bias** make it untradeable as-is |

---

## 1. MA200 exposure management

Spec: `quant-research-handoff/strategy/MA200Exposure-SPEC.md`

```
Close > MA200  ->  100% exposure
Close < MA200  ->   50% exposure
```

Strategy: `user_data/strategies/MA200Exposure.py`
Config: `user_data/config_ma200.json`
Study: `tools/ma200_exposure_study.py`

### Results (2018–2026, 10bps costs)

| Pair | Buy & hold CAGR | Rule CAGR | BH MaxDD | Rule MaxDD |
|---|---:|---:|---:|---:|
| BTC/USDT | 32.92% | 36.90% | -76.63% | -67.77% |
| ETH/USDT | 22.42% | 37.52% | -82.52% | -68.21% |
| XRP/USDT | 13.44% | 9.20% | -83.24% | -82.26% |

Drawdown improved **3/3** (handoff found 7/8 on equity ETFs).

### The placebo kills it

200 circular shifts of the exposure series — this preserves the exact
**frequency and run-length structure** while destroying alignment with returns:

| Pair | Random shifts beating the real rule on DD | Verdict |
|---|---:|---|
| BTC | 43.5% | indistinguishable (coin flip) |
| ETH | 12.0% | indistinguishable |
| XRP | 94.0% | **worse than random** |

> **"降低回撤"本身不证明信号有价值。** — handoff README

BTC's 43.5% is the damning one: random de-risking matches the "signal".
Per the handoff's Stop Rule (placebo cannot distinguish → not for production),
**rejected**.

### Secondary findings

- Crypto is much worse than equities for this rule: drawdowns of -68% to -83%
  vs the handoff's -30% on SPY. MA200's ~16-day lag costs far more in a market
  that moves several times faster.
- Cost-insensitive (0–20bps barely moves it) because turnover is low — the
  rule's one genuine strength.

---

## 2. Cross-sectional momentum

Study: `tools/crypto_momentum_study.py`
Universe: **47 Binance USDT pairs**, 2019-01-01 → 2026-09-17 (7.7 years)

This follows the handoff's single most important lesson
(`DECISIONS.md` 阶段 0):

> 与 SPY 比较是**假的测试**（池子偏差）→ 必须用等权同池

So every variant is measured against an **equal-weight portfolio of the same
pool over the same window** — not against BTC.

### Headline (10bps, weekly rebalance)

| Variant | CAGR | MaxDD | Sharpe | Turnover/yr |
|---|---:|---:|---:|---:|
| equal-weight (all 47) | 34.64% | -87.02% | 0.79 | 0.3x |
| **momentum 30d top5** | **66.69%** | -89.49% | **1.02** | 39.6x |
| momentum 90d top5 | 37.78% | -89.75% | 0.82 | 20.1x |
| momentum 180d top5 | 18.59% | -91.37% | 0.64 | 15.9x |
| momentum 90d top10 | 30.89% | -87.73% | 0.75 | 18.0x |

### Placebo — it survives (200 random K-of-N draws)

With 5 variants tested, Bonferroni threshold is p < 0.01:

| Variant | Real CAGR | Random p95 | p-value | Verdict |
|---|---:|---:|---:|---|
| momentum 30d top5 | 66.69% | 40.16% | **0.000** | ✅ passes |
| momentum 90d top5 | 37.78% | 32.03% | 0.025 | fails Bonferroni |
| momentum 180d top5 | 18.59% | 25.79% | 0.115 | indistinguishable |
| momentum 90d top10 | 30.89% | 28.36% | 0.030 | fails Bonferroni |

Random top5 mean CAGR is only **12.17%** vs momentum's 66.69%.

### Robustness

**One-bar shift test** (the handoff's most valuable single diagnostic):

| Extra lag | CAGR |
|---|---:|
| 0 (as designed) | 66.69% |
| 1 | 49.11% |
| 2 | 44.70% |

Degrades **gracefully** — this is NOT a look-ahead artifact. A look-ahead bug
would collapse or flip sign.

**Parameter plateau** (CAGR @10bps): broadly positive across all 24
lookback×K combinations, no isolated spike — but a clear cliff between
lookback 30 (66.7%) and lookback 45 (44.1%). Less "plateau", more "ridge".

**Sub-period stability** — momentum beat equal-weight in **6/8 years**:

| Year | Equal-weight | Momentum | Won? |
|---|---:|---:|:--:|
| 2019 | 17.7% | 50.9% | ✅ |
| 2020 | 250.0% | 452.5% | ✅ |
| 2021 | 929.3% | 1026.3% | ✅ |
| 2022 | -80.4% | -84.9% | ❌ |
| 2023 | 104.4% | 142.9% | ✅ |
| 2024 | 44.3% | 56.0% | ✅ |
| 2025 | -58.7% | 9.7% | ✅ |
| 2026 | -23.9% | -30.3% | ❌ |

---

## 3. Why momentum is still NOT tradeable

### a) Survivorship bias — unquantified and severe

The universe is pairs **listed on Binance today**. Everything that delisted or
went to zero is silently absent — LUNA, FTT and similar are simply not in the
panel. The handoff measured this at **+1.78% CAGR / +0.141 Sharpe** on equities
and called risk-end distortion *worse* than return-end.

**Momentum selects recent winners, making it exactly the rule most exposed to
this bias.** Every CAGR above is an upper bound; the true figure is unknown.
Fixing it needs point-in-time delisting data, which Binance's public mirror
does not provide.

### b) The drawdown is unsurvivable

**-89% across every variant.** The handoff's MA200 rule was rejected for
failing to reduce drawdown; momentum here doesn't reduce it at all. A -89%
drawdown means 10,000 → 1,100. No one holds through that.

### c) Turnover and real crypto costs

39.6x/year turnover is enormous. This study used 10bps, but altcoin
spread+slippage is realistically **20–50bps** (handoff §4.2 puts small-cap
equities at 5–15bps spread; illiquid alts are worse). At 50bps:

| Variant | CAGR @50bps |
|---|---:|
| equal-weight | 34.45% |
| momentum 30d top5 | 42.27% |

Still ahead, but the margin shrinks from 32pp to 8pp — and 50bps may be
optimistic for the smaller alts momentum actually selects.

### d) Equal-weight is the honest baseline to beat

**Buying all 47 pairs equally returns 34.64% CAGR with 0.3x turnover and no
signal at all.** Most of momentum's apparent edge must be measured against
*that*, not against BTC.

---

## 4. Reproduce

```powershell
# MA200 exposure + placebo
.\.venv\Scripts\python.exe tools\ma200_exposure_study.py

# Cross-sectional momentum + placebo + robustness
.\.venv\Scripts\python.exe tools\crypto_momentum_study.py

# The MA200 strategy as a real freqtrade backtest
.\.venv\Scripts\freqtrade.exe backtesting --config user_data\config_ma200.json `
    --strategy MA200Exposure --timeframe 1d
```

Note: the Freqtrade backtest of `MA200Exposure` reports **1 trade / 63 orders** —
Freqtrade's trade-level accounting is a poor fit for a "resize, never close"
rule, which is why the study script uses its own equity engine.

## 5. Data

Daily OHLCV for 47 Binance USDT pairs, 2018–2026, in `user_data/data/binance/*-1d.feather`.
Downloaded via the `data-api.binance.vision` mirror (`user_data/config_binance_vision.json`).

```powershell
.\.venv\Scripts\freqtrade.exe download-data --config user_data\config_binance_vision.json `
    --timeframes 1d --timerange 20190101- --pairs BTC/USDT ETH/USDT ...
```

## 6. What to do next

Per the handoff's Stop Rule — after a failed hypothesis, **stop searching for
signals** and move to execution, cost, and forward validation:

1. **Do not run either of these with real money.**
2. If continuing momentum research, the only meaningful next step is
   **point-in-time universe data** (delisted coins). Without it, the result
   cannot be trusted regardless of how good it looks.
3. The genuinely promising direction is **drawdown control**, not more signals:
   -89% is the binding constraint, not CAGR.
