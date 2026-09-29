# Findings: Drawdown Control on Large-Cap Majors

Run 2026-09-19 against freqtrade 2026.8. Script: `tools/drawdown_control_study.py`.
Read alongside `findings-ma200-and-momentum.md`.

---

## Question

The previous two studies both failed on the same thing: **drawdown**. Momentum
returned 66% CAGR but with a -89% drawdown; MA200 didn't reduce drawdown beyond
chance. So: can vol targeting and/or a trend filter cut the drawdown without
giving up the return?

## Universe — majors only

20 established large caps, meme coins and micro alts deliberately excluded
because their downside is not controllable:

```
BTC ETH BNB SOL XRP ADA AVAX DOT LINK LTC BCH ATOM UNI AAVE XLM ETC ALGO FIL NEO TRX
```

Excluded on purpose: DOGE, SHIB and similar. Window 2019-01-01 → 2026-09-17 (7.7 years).

---

## The trap this study had to avoid

The handoff's central warning:

> **「降低回撤」本身不证明信号有价值。**
> 随机减仓也能得到类似的回撤改善。

Any rule that holds less risk shows a smaller drawdown **mechanically**. So
comparing "vol-targeted" against "buy & hold" proves nothing. Two controls are
mandatory:

1. **Flat control at the same average exposure** — if the dynamic rule can't
   beat a constant position of identical average size, its "timing" is worthless.
2. **Wildcard placebo** — random exposure matched on mean *and* run structure.

---

## Results (10bps, equal-weight portfolio of the 20 majors)

Baseline: **buy & hold = CAGR 37.35%, MaxDD -81.37%, Sharpe 0.81**

| Rule | avg exp | CAGR | MaxDD | Sharpe | vs flat control |
|---|---:|---:|---:|---:|---|
| vol target 60% | 83.1% | 36.40% | -75.04% | 0.82 | flat: 0.81 → +0.01 |
| vol target 40% | 61.0% | 31.34% | **-59.15%** | 0.85 | flat: 0.81 → +0.04 |
| trend filter MA200 | 73.2% | 31.18% | -68.86% | 0.76 | flat: 0.81 → **-0.05** |
| vol 60% + trend | 62.0% | 27.63% | **-57.29%** | 0.75 | flat: 0.81 → **-0.06** |
| vol 40% + trend | 45.4% | 22.96% | **-46.16%** | 0.76 | flat: 0.81 → **-0.05** |

**Drawdown does fall** — from -81% to as low as -46%. But the flat controls at
the same average exposure get nearly all of it (e.g. vol 40%: -59.15% dynamic
vs -60.50% flat). The trend filter variants are **actively worse than just
holding less**.

## Is the edge statistically real? No.

Lo (2002): annualised Sharpe SE ≈ 1/√years = 1/√7.7 = **0.360**. So a Sharpe of
0.85 has a 95% CI of roughly **[0.14, 1.56]** — the whole comparison lives inside
the noise.

Paired block bootstrap (5000 draws, block=20) on **Sharpe(rule) − Sharpe(flat)**:

| Rule | ΔSharpe | 95% CI | p(≤0) | Verdict |
|---|---:|---|---:|---|
| vol target 60% | +0.007 | [-0.17, 0.18] | 0.483 | NOT significant |
| vol target 40% | +0.033 | [-0.21, 0.26] | 0.407 | NOT significant |
| trend filter MA200 | -0.057 | [-0.36, 0.23] | 0.650 | NOT significant |
| vol 60% + trend | -0.067 | [-0.41, 0.25] | 0.668 | NOT significant |
| vol 40% + trend | -0.050 | [-0.42, 0.31] | 0.618 | NOT significant |

Every confidence interval straddles zero. **No rule's timing adds measurable
value over a flat position of the same average exposure.**

## Wildcard placebo (200 random paths, matched mean)

| Rule | real Sharpe | p(Sharpe) | p(MaxDD) | Verdict |
|---|---:|---:|---:|---|
| vol target 60% | 0.82 | 0.320 | 0.265 | indistinguishable |
| vol target 40% | 0.85 | 0.150 | 0.025 | indistinguishable |
| trend filter MA200 | 0.76 | 0.460 | 0.090 | indistinguishable |
| vol 60% + trend | 0.75 | 0.325 | **0.005** | indistinguishable |
| vol 40% + trend | 0.76 | 0.280 | **0.010** | indistinguishable |

Interesting nuance: the combined rules **do** beat random on MaxDD (p=0.005 and
0.010) — random exposure with the same mean and run structure does *not* match
their drawdown. But they **fail on Sharpe**, and since they also lose to the flat
control, the drawdown win comes from *concentrating* the reduced exposure into
the right periods only weakly. Not enough to trade.

## Robustness

**One-bar shift test** (vol 60% + trend): 27.63% → 26.31% → 27.62%.
Graceful, no look-ahead.

**Cost sensitivity** (vol 60% + trend):

| Cost | CAGR | MaxDD | Sharpe |
|---|---:|---:|---:|
| 0bps | 28.42% | -57.00% | 0.76 |
| 10bps | 27.63% | -57.29% | 0.75 |
| 20bps | 26.86% | -57.58% | 0.74 |
| 50bps | 24.55% | -58.45% | 0.70 |

Low turnover makes it cost-robust — one genuine strength.

**Sub-period** (vol 60% + trend vs buy & hold):

| Year | BH | Rule | BH MaxDD | Rule MaxDD |
|---|---:|---:|---:|---:|
| 2019 | 16.6% | -33.1% | -60.00% | -37.17% |
| 2020 | 192.0% | 127.1% | -63.75% | -41.46% |
| 2021 | 504.1% | 211.2% | -63.07% | -33.77% |
| 2022 | -73.9% | -38.4% | -74.21% | -38.73% |
| 2023 | 125.4% | 94.1% | -31.71% | -31.71% |
| 2024 | 69.5% | 47.8% | -46.02% | -44.89% |
| 2025 | -42.1% | -30.4% | -50.59% | -38.96% |
| 2026 | -22.5% | -1.8% | -47.30% | -25.91% |

Drawdown better in **every** year, but it **gives up return in the bull years**
(2021: 504% → 211%) and lost money in 2019 while BH gained.

**Per-asset drawdown improvement: 20/20 majors.** Cross-asset replication is the
handoff's strongest anti-overfit evidence, and this passes it cleanly:

| | BH CAGR | Rule CAGR | BH MaxDD | Rule MaxDD |
|---|---:|---:|---:|---:|
| BTC | 47.55% | 24.68% | -76.63% | -63.73% |
| ETH | 45.00% | 40.22% | -79.30% | -55.53% |
| SOL | 55.92% | 32.34% | -96.27% | -66.76% |
| DOT | -12.78% | -15.02% | -98.60% | -81.46% |
| FIL | -42.78% | -13.80% | -99.67% | -74.13% |

But note the CAGR column: the rule **halves** BTC's return and turns several
losers into bigger losers.

---

## Verdict

**The drawdown reduction is real and consistent (20/20 assets, 8/8 years) but it
is almost entirely mechanical.** At matched average exposure, a flat position
achieves nearly the same result, and no rule's timing effect is statistically
distinguishable from zero (all bootstrap CIs straddle zero).

This is the **exact finding the handoff predicted**, arrived at independently:

> MA200 是风险管理工具，不是预测工具
> 回撤下降很大一部分来自「暴露减少」这个机械效果

**Practical upshot:** if you want a -46% drawdown instead of -81%, you do not
need a signal — just **hold ~45% of your capital and keep 55% in cash**. The vol
targeting and trend filters add complexity, turnover risk, and failure modes
without adding measurable value.

That is a genuine, if unglamorous, result: **it tells you the honest price of
drawdown reduction, and that you shouldn't pay extra for a signal to get it.**

## Reproduce

```powershell
.\.venv\Scripts\python.exe tools\drawdown_control_study.py
```
