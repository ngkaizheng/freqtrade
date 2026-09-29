# Gate 0 Feasibility Screen: Bitcoin Options Volatility Risk Premium

**Date:** 2026-09-28
**Status:** PRELIMINARY — based on published evidence, not a full text review
**No strategy line opened, no backtest run, no data downloaded**

---

## 1. The Candidate Mechanism

**Source:** Almeida, Grith, Miftachov & Wang (2025), "Risk Premia in the Bitcoin Market," arXiv:2410.15195v2. Princeton/Erasmus/Humboldt/SWUFE. ⚠ PREPRINT — NOT PEER REVIEWED.

**Mechanism:** Bitcoin options implied volatility (IV) systematically exceeds realized volatility (RV). The volatility risk premium (VRP) is the difference between IV and RV. Selling IV and buying RV harvests the VRP.

**Published claim:** Bitcoin BVRP averages **14%/yr** (vs ~2% for S&P 500), using 5.4M Deribit transactions (2017-2022).

**Why this is genuinely new:** Options are a different instrument from all closed lines (which are all spot/perp based). The cost structure is different (3 bps/side on Deribit vs 12-35 bps on Binance perps). The mechanism is different (sell IV / buy RV, not directional price prediction).

---

## 2. Gate 0 Screen

### 2a. Power

**Effect size:** VRP = 14%/yr (Almeida et al. 2025)

**Required sample size:** The VRP is a mean, not a cross-sectional effect. The required sample size depends on the standard deviation of the VRP and the desired power. Without the standard deviation, we cannot compute the required sample size.

**What we can say:**
- The VRP is 14%/yr, which is a large effect
- The VRP is measured on 5.4M Deribit transactions (2017-2022)
- The VRP is statistically significant (the paper is published as a preprint)

**What we cannot say:**
- Whether the VRP is stable across market regimes
- Whether the VRP survives proper multiple-testing correction
- Whether the VRP is robust to the methodological issues identified in the literature

### 2b. Cost

**Deribit options fees:** 3 bps/side standard tier (6 bps round trip)

**Bid-ask spread:** The dominant cost, not the fees. Cayo Largo (2026) measured the spread at ~4 points per straddle trade vs a mark edge of ~0.8 points — **5× the edge**.

**Cayo Largo (2026) — the decisive finding:** A long-vol signal that made **+21% at mark lost -87% at real bid/ask fills** (26 trades). The spread cost 5× the edge. *"A vol-point edge is the profit of a perfectly hedged, cost-free position. It is not what a straddle you buy and sell returns."*

**Current VRP status:** As of Sept 2026, BTC IV (DVOL 30d) = 36.3% vs RV (HV30) = 41.5% — **NEGATIVE spread of -5.2 vol pts**. The VRP has compressed/inverted for BTC. ETH shows +5.2 vol pts.

### 2c. Data Availability

**Free:**
- DVOL daily index (CryptoDataDownload)
- Deribit API (public/get_historical_volatility)
- Tardis.dev monthly samples

**Paid:**
- CryptoStruct (€1/chain-day, tick+L2+greeks)
- Tardis.dev full history (since 2019-03-30)
- CryptoDataDownload Plus+

### 2d. Methodological Concerns

1. **The VRP is currently inverted for BTC** (IV < RV as of Sept 2026). This means the VRP is negative for BTC, which would make a short-vol strategy unprofitable.
2. **The only profitable backtest has look-ahead bias** (Deribit weekend vol, +154.8% over 5.3 years, but the weekend pattern was discovered on the same period used for the backtest).
3. **The only honest cost analysis shows vol edges don't survive real fills** (Cayo Largo 2026: +21% at mark → -87% at real fills).
4. **The VRP is measured on 2017-2022 data**, which is a different period from the project's data (2023-2026).
5. **The VRP is a preprint, not peer-reviewed.**

---

## 3. Preliminary Verdict

### 3a. The VRP exists but is currently inverted for BTC

The VRP is 14%/yr (Almeida et al. 2025), but as of Sept 2026, BTC IV (36.3%) < RV (41.5%) — a **negative spread of -5.2 vol pts**. This means the VRP is negative for BTC, which would make a short-vol strategy unprofitable.

### 3b. The cost of harvesting the VRP is unknown but likely high

The Cayo Largo (2026) finding suggests that the bid-ask spread is the dominant cost, and it is 5× the edge. This would make the VRP unprofitable at any rebalancing frequency.

### 3c. The evidence for a tradeable edge after costs is weak

- The only profitable backtest has look-ahead bias
- The only honest cost analysis shows vol edges don't survive real fills
- The VRP is currently inverted for BTC
- The VRP is a preprint, not peer-reviewed

**Verdict: NOT FEASIBLE at this time.** The VRP is currently inverted for BTC, and the only honest cost analysis shows vol edges don't survive real fills. The line is not closed (it could become feasible if the VRP re-emerges), but it is not actionable now.

---

## 4. Comparison with the Project's Own Findings

The project has consistently found that:
- Short-horizon strategies (5m, 1h) are not tradeable after costs
- The 4h short breakout has a gross edge of +0.131R but a net edge of only +0.043R (t=1.21)
- The 5m factor scan found a best gross edge of 2.47 bps vs 12.0 bps cost (5× too small)
- The Kim & Hansen (2026) paper found a lagged-flow component of 5-6 bps vs 35 bps cost (6-7× too small)
- The Kitron & Wengrowicz (2026) paper found a gross edge of 1.3 bps vs 5 bps cost (4× too small)
- The seesaw effect (Jia et al. 2023) has a net return of 0.07-0.08 bps vs 12-35 bps cost (150-500× too small)

**The VRP fits a different pattern:** the effect size is large (14%/yr), but the cost of harvesting it is unknown and likely high. The Cayo Largo finding suggests that the cost is 5× the edge, which would make it unprofitable. But this is a single finding, and it may not generalize.

---

## 5. Recommended Next Steps

1. **VRP: NOT FEASIBLE at this time.** The VRP is currently inverted for BTC, and the only honest cost analysis shows vol edges don't survive real fills. The line is not closed (it could become feasible if the VRP re-emerges), but it is not actionable now.
2. **Continue scouting for genuinely new mechanisms.** The project's own pattern suggests the prior for a cost-surviving edge is low.
3. **Monitor the VRP.** If the VRP re-emerges for BTC (IV > RV), the line could be re-opened with a proper Gate 0 screen.

**The honest conclusion:** The VRP is a large effect (14%/yr) but the cost of harvesting it is unknown and likely high. The only honest cost analysis shows vol edges don't survive real fills. The VRP is currently inverted for BTC. **The line is not actionable now.**
