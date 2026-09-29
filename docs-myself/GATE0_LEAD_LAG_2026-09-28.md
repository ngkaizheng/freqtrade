# Gate 0 Feasibility Screen: Cross-Asset Lead-Lag Mechanisms

**Date:** 2026-09-28
**Status:** UPDATED — full text of Jia et al. (2023) obtained via r.jina.ai proxy; Guo et al. (2024) still behind paywall
**No strategy line opened, no backtest run, no data downloaded**

---

## 1. The Two Candidate Mechanisms

### 1a. Seesaw Effect (Negative Lead-Lag) — FULL TEXT OBTAINED

**Source:** Jia, Wu, Yan & Liu (2023), "A seesaw effect in the cryptocurrency market," *Journal of Empirical Finance* 74, peer-reviewed. DOI: 10.1016/j.jempfin.2023.101428

**Mechanism:** Large coins (BTC, ETH, XRP, LTC, EOS) **negatively** predict small coins. The "seesaw effect" — when large coins go up, small coins tend to go down. Small coins rarely predict large coins.

**Trading strategy:** LASSO-based strategy that sorts coins on the information spillover measure (SO) into quintile portfolios. Buy top quintile, short bottom quintile.

**Sample period:** January 1, 2018 to July 30, 2021

**Data:** Transaction data from Bitfinex and Huobi

**Gross return:** 5-6 bps per 5-minute return

**Net return (after transaction costs):** 0.07-0.08 bps per 5-minute return (73.58% to 84.10% annualized on Bitfinex; 21.02% to 94.61% on Huobi)

**Cost structure:**
- Spot market: 20-40 bps/side → "completely unprofitable"
- Futures market: 2 bps maker / 4 bps taker on Huobi → "significantly profitable"

**Mechanism:** Limits-to-arbitrage (LTA) channel, not risk-based. Profitability is more pronounced for cryptocurrencies with high LTA measures (volatility, bid-ask spread, TED spread exposure). The strategy requires "relatively sophisticated and fast machine learning methods" and "efficiently integrated and automated algorithms."

### 1b. 10-Minute Cross-Cryptocurrency Predictability — FULL TEXT NOT OBTAINED

**Source:** Guo, Sang, Tu & Wang (2024), "Cross-cryptocurrency return predictability," *Journal of Economic Dynamics and Control* 163, peer-reviewed. DOI: 10.1016/j.jedc.2024.104863

**Mechanism:** Lagged returns of other cryptocurrencies serve as significant predictors of focal cryptocurrencies **up to ten minutes**. Consistent with the spillover effect mechanism: common shocks + limited attention → slow information diffusion.

**Published claim:** A long-short portfolio generates "sizable return out-of-sample after accounting for transaction costs."

**What the abstract does NOT tell us:**
- Specific effect size (bps per trade)
- Specific cost assumptions
- Sample period
- Number of trades
- Sharpe ratio or other risk-adjusted return

---

## 2. Gate 0 Screen

### 2a. Seesaw Effect — NOT FEASIBLE on Binance

**The critical finding:** The net return is **0.07-0.08 bps per 5-minute return**. This is **150-500× smaller** than the project's measured 12-35 bps round-trip cost on Binance.

**Cost comparison:**
| venue | cost per side | cost per round trip (long-short) | net return per 5 min | feasible? |
|---|---|---|---|---|
| Huobi futures (paper) | 2-4 bps | 4-8 bps | 0.07-0.08 bps | YES (barely) |
| Binance (project measured) | 6-17.5 bps | 12-35 bps | 0.07-0.08 bps | **NO** |

**The paper's own cost structure explains why:** On Huobi futures, the cost is 2-4 bps/side, which is 3-9× lower than Binance's 6-17.5 bps/side. The paper explicitly states that on the spot market (20-40 bps/side), the strategy is "completely unprofitable." Binance's cost is 3-9× higher than Huobi futures, so the strategy would be **unprofitable on Binance**.

**Additional concerns:**
1. The net return (0.07-0.08 bps per 5 min) is extremely small — even a small increase in cost would make it negative
2. The strategy requires "sophisticated and fast machine learning methods" and "automated algorithms" — barriers to implementation
3. The sample period (2018-2021) is different from the project's data (2023-2026)
4. The effect may be regime-dependent (the paper finds it's "almost constant across booms and busts," but this is a single sample)
5. The paper uses LASSO, which is a machine learning method — the project's own experience with ML/FreqAI is negative

**Verdict: NOT FEASIBLE on Binance with the project's measured costs.**

### 2b. 10-Minute Cross-Predictability — STILL INCONCLUSIVE

**The full text is still behind a paywall.** The abstract claims "sizable return" after costs, but without specific numbers, we cannot verify this claim.

**What we know:**
- The horizon is 10 minutes, which is very short
- The project's own experience with short-horizon strategies is negative (5m and 1h are both closed)
- The project's measured cost at 5m is 0.285-0.485R per trade, which is very high
- The 10-minute horizon would have a similar cost structure to 5m

**What we cannot say:**
- Whether the effect size is large enough to clear the project's measured cost
- Whether the effect is stable across market regimes
- Whether the effect survives proper multiple-testing correction

**Verdict: INCONCLUSIVE — cannot determine without the full text.**

---

## 3. Comparison with the Project's Own Findings

The project has consistently found that:
- Short-horizon strategies (5m, 1h) are not tradeable after costs
- The 4h short breakout has a gross edge of +0.131R but a net edge of only +0.043R (t=1.21)
- The 5m factor scan found a best gross edge of 2.47 bps vs 12.0 bps cost (5× too small)
- The Kim & Hansen (2026) paper found a lagged-flow component of 5-6 bps vs 35 bps cost (6-7× too small)
- The Kitron & Wengrowicz (2026) paper found a gross edge of 1.3 bps vs 5 bps cost (4× too small)

**The seesaw effect fits this pattern exactly:** the net return (0.07-0.08 bps per 5 min) is 150-500× smaller than the project's measured cost (12-35 bps per round trip). This is the same "too small to trade" pattern that has killed every other line in this project.

---

## 4. Updated Verdict

### 4a. Seesaw Effect — NOT FEASIBLE

The full text of the paper reveals that the net return is 0.07-0.08 bps per 5-minute return, which is 150-500× smaller than the project's measured 12-35 bps round-trip cost on Binance. The paper's cost structure (2-4 bps/side on Huobi futures) is 3-9× lower than Binance's. **The strategy is not feasible on Binance with the project's measured costs.**

### 4b. 10-Minute Cross-Predictability — STILL INCONCLUSIVE

The full text is still behind a paywall. The abstract claims "sizable return" after costs, but without specific numbers, we cannot verify this claim. The 10-minute horizon is very short and the project's own experience with short-horizon strategies is negative.

---

## 5. Recommended Next Steps

1. **Seesaw effect: STOP.** The full text reveals the net return is 150-500× too small. This line is closed.
2. **10-minute cross-predictability: attempt to obtain the full text** through r.jina.ai or other means.
3. **If the full text is obtained:** extract the specific effect size and compare with the project's measured cost.
4. **If the effect size is >35 bps:** preregister a test.
5. **If the effect size is <35 bps:** stop and continue scouting.

**The honest conclusion:** The seesaw effect, the most promising new mechanism found in the scouting pass, is **not feasible on Binance** with the project's measured costs. This is consistent with the project's own pattern: most published crypto effects are too small to trade after costs.
