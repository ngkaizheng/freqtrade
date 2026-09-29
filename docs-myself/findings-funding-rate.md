# Findings: Funding Rate — The Orthogonal Source Also Fails

Run 2026-09-19, freqtrade 2026.8. Scripts: `tools/download_funding.py`,
`tools/funding_signal_study.py`, `tools/funding_sign_test.py`.
Read alongside `findings-volume-signals.md`.

---

## Why funding rate was the right thing to test

Every input tested so far was **price-derived**: MA, VWMA, OBV, momentum, and
the vol-targeting variants. Volume was the one orthogonal input tried, and it
contributed **0.017 Sharpe** — nothing.

Funding rate is different in kind. It is a **real payment** between longs and
shorts on perpetual futures, set by the exchange to tether the perp to spot:

* **positive** → longs pay shorts (crowded long / bullish positioning)
* **negative** → shorts pay longs (crowded short / bearish positioning)

It is not computed from price and it is not the price. This was the last
genuinely independent information source available for free.

## Data acquired

`tools/download_funding.py` → `user_data/data/binance_funding/*-funding.feather`

20/20 majors, ~7,300 settlement records each (8h intervals), 2019-09 → 2026-09.
Coverage after daily aggregation: **96%** of pair-days.

Funding is persistently **positive** across majors — longs pay shorts on average:

| pair | mean 8h rate | annualised |
|---|---:|---:|
| XRP | +0.000133 | +14.61% |
| LTC | +0.000135 | +14.81% |
| AAVE | +0.000130 | +14.27% |
| BTC | +0.000106 | +11.57% |
| ETH | +0.000126 | +13.80% |
| BNB | -0.000001 | -0.06% |
| SOL | +0.000002 | +0.19% |

Baseline (2020-01-01 → 2026-09-17, 6.7y, 10bps): buy & hold CAGR 40.53%,
MaxDD -81.37%, Sharpe 0.84. SE(Sharpe) ≈ 0.39.

---

## Result 1 — Contrarian funding is decisively refuted

The natural hypothesis: crowded positioning means the crowd is wrong, so
de-risk when funding is high.

| signal | avgExp | CAGR | Sharpe | vs flat control |
|---|---:|---:|---:|---:|
| level: contrarian | 76.4% | 8.43% | 0.44 | **-0.394** |
| pct90: contrarian | 49.3% | 12.41% | 0.49 | **-0.353** |
| trend: contrarian | 49.3% | 10.18% | 0.47 | **-0.363** |
| extreme: contrarian | 87.4% | 19.45% | 0.61 | **-0.229** |

**Every contrarian variant is worse than a flat position of the same average
exposure.** Mean ΔSharpe **-0.335**. Per-asset: only 6/20 pairs beat buy & hold.

Placebo p-values 0.55–0.95 — the rules sit **inside** the random distribution,
and below its centre.

---

## Result 2 — The sign is the other way, but still not significant

Testing momentum (high funding → keep holding) instead:

| signal | avgExp | CAGR | Sharpe | vs flat |
|---|---:|---:|---:|---:|
| level: momentum | 23.6% | 33.28% | **0.98** | +0.142 |
| pct90: momentum | 50.7% | 31.05% | 0.84 | -0.002 |
| extreme: momentum | 89.4% | 25.97% | 0.69 | -0.150 |
| trend: momentum | 50.7% | 21.57% | 0.64 | -0.194 |

Direction summary: **CONTRARIAN mean ΔSharpe -0.335, MOMENTUM mean -0.051.**
Momentum is clearly the better reading — but only one of four variants beats the
flat control, and its value is small.

Full gates on the best variant (`level: momentum`, Sharpe 0.98):

| gate | result |
|---|---|
| placebo p(Sharpe) | 0.045 — **fails Bonferroni** (8 signals → p<0.00625) |
| paired bootstrap ΔSharpe | +0.140, **CI [-0.45, +0.72]** — straddles zero |
| negative control (shuffled funding) | real 0.98 vs shuffled mean 0.61, p95 0.88, **p=0.010** |

The negative control is interesting: shuffling the funding series destroys most
of the effect (p=0.010), suggesting *some* real information is present. But it
does not survive the multiple-comparison correction and its confidence interval
is enormously wide.

---

## Result 3 — The decisive test: incremental value over SMA-50

The handoff's actual demand is **incremental information conditional on what we
already have**, not low correlation:

| rule | avgExp | CAGR | MaxDD | Sharpe |
|---|---:|---:|---:|---:|
| **SMA-50 alone** | 76.1% | **57.98%** | -68.52% | **1.07** |
| funding momentum (rescaled) | 45.2% | 29.42% | -69.69% | 0.77 |
| min(SMA-50, funding) | 41.7% | 30.97% | -61.67% | 0.82 |

**Within SMA-50 risk-ON days (n=1281):**
* always 1.0 → Sharpe **4.00**
* funding-scaled → Sharpe **2.95**

> **Funding adds nothing on top of a plain SMA-50 — it actively subtracts.**

Adding funding to SMA-50 *lowers* Sharpe from 1.07 to 0.82. This is the same
pattern as volume (0.017 Sharpe) and MA200 (adds nothing).

---

## Verdict

❌ **Funding rate is refuted as a trading signal.**

* Contrarian direction: decisively negative (-0.335 mean ΔSharpe)
* Momentum direction: weakly positive (+0.142) but fails Bonferroni and its CI
  straddles zero
* Incremental over SMA-50: **negative** — it subtracts value

There is weak evidence that funding carries *some* information (the shuffle
control gives p=0.010), but nothing that survives the project's standard gates.

---

## The pattern across all six studies

| input | type | result |
|---|---|---|
| MA200 | price-derived | placebo indistinguishable |
| momentum | price-derived | beats random but -89% DD, survivorship bias |
| vol targeting / trend | price-derived | mechanical only |
| volume / OBV / VWMA | **orthogonal** | 0.017 Sharpe — nothing |
| **funding rate** | **orthogonal** | **negative incremental value** |
| SMA-50 | price-derived | **best candidate, but OOS splits** |

**Two independent orthogonal information sources have now been tested and both
failed.** That is meaningful evidence that the problem is not "we haven't found
the right input yet."

The binding constraint remains **statistical power**: 6.7 years gives
SE(Sharpe) ≈ 0.39. Every CI in this study straddles zero not necessarily because
the effects are zero, but because the data cannot resolve them.

---

## Honest status against the goal

The goal — "find a strategy that makes money sustainably" — is **not achieved**.
No candidate has passed all controls:

| candidate | status |
|---|---|
| SMA-50 | in-sample strong (Sharpe 1.07, placebo p=0.005, CI excludes zero) but **anchored OOS fails** |
| momentum | fails on drawdown (-89%) and unmeasured survivorship bias |
| funding | refuted |
| volume | refuted |

**Do not deploy real money.** The next lever is not another signal — it is
either more data (statistical power) or accepting that this dataset cannot
validate a strategy.

## Reproduce

```powershell
.\.venv\Scripts\python.exe tools\download_funding.py       # ~2 min, 20 pairs
.\.venv\Scripts\python.exe tools\funding_signal_study.py   # contrarian families
.\.venv\Scripts\python.exe tools\funding_sign_test.py      # both directions + gates
```
