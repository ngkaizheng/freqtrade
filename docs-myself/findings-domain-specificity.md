# Findings: Domain Specificity — SMA-50 Works on Crypto, Fails on Equities

Run 2026-09-19, freqtrade 2026.8. Scripts: `tools/equity_out_of_domain.py`,
`tools/trend_mechanism_test.py`, `tools/crypto_majors_replication.py`.

This round stress-tested the round-2/3 candidate the hardest way available:
apply the **frozen** rule to a completely different asset class.

---

## The test

Round 3 closed all five objective controls, but everything rested on crypto
(BTC 15y + a 5-coin Bitstamp pool). The handoff calls cross-market replication
"最强的防过拟合证据之一". So I ran the identical methodology on **109 US equities**
from the handoff's own data cache (2010–2026, 5bps — equities are cheaper).

**Rule frozen at SMA-50, exposure 50%/100%. No re-tuning.**

---

## Result: 0/4 gates — decisively fails on equities

| metric | equities (109 tickers) |
|---|---|
| beats buy & hold Sharpe | **22/109 (20%)** |
| beats flat control | **22/109 (20%)** |
| mean ΔSharpe vs flat | **-0.065** |
| median ΔSharpe vs flat | -0.062 |
| sign test p | **1.00** |
| drawdown improved | 104/109 (95%) |
| correlation-aware null p | **0.793** |
| portfolio bootstrap vs flat | ΔSharpe +0.001, **CI [-0.195, +0.181]** |

| gate | equities |
|---|---|
| per-ticker beats flat >50% | ❌ |
| mean ΔSharpe > 0 | ❌ |
| survives correlation-aware null | ❌ |
| portfolio bootstrap CI excludes 0 | ❌ |

**Drawdown still improves in 95% of tickers** — but Sharpe does not. So on
equities the rule reproduces the round-1 "mechanical" pattern exactly: it reduces
drawdown by holding less, and adds nothing else.

Side note: 109 equities carry only **~5.7 effective independent bets**
(mean pairwise correlation 0.373) — the round-2 lesson recurs even here.

---

## Mechanism: why the domain matters

If the rule works on crypto and not equities, there must be a difference in the
return-generating process. The relevant property for trend-following is
**return persistence**, measured by the variance ratio:

> VR(q) = Var(q-period return) / (q × Var(1-period return))
> VR > 1 ⇒ trending / persistent;  VR < 1 ⇒ mean-reverting

| q | crypto VR | equities VR | |
|---:|---:|---:|---|
| 2 | 0.964 | 0.948 | ~equal |
| 5 | **1.013** | **0.916** | crypto trends, equities revert |
| 10 | **1.092** | **0.870** | wider gap |
| 20 | **1.187** | **0.841** | crypto clearly persistent |

**This is the mechanism.** Crypto returns are positively persistent at
multi-week horizons (VR(20) = 1.19); equity returns mean-revert (VR(20) = 0.84).
A trend rule *must* lose on a mean-reverting process — it systematically buys
after rises and trims after falls, which is backwards when prices revert.

Return autocorrelation is uninformative at lag 1 for both (crypto -0.036,
equities -0.052); the difference only appears at longer horizons, which is why a
50-day SMA (not a 1-day rule) is the right instrument.

Per-series, trendiness does predict the edge, in the expected direction:
* crypto: mean VR(5) 1.013 → mean ΔSharpe **+0.078**
* equities: mean VR(5) 0.916 → mean ΔSharpe **-0.065**

---

## Within-domain replication (frozen rule, 20 Binance majors)

Same methodology, crypto cross-section, no per-fold tuning:

| metric | crypto majors |
|---|---|
| beats flat control | **16/20 (80%)** |
| mean ΔSharpe | **+0.094** |
| median ΔSharpe | +0.108 |
| drawdown improved | 19/20 |
| sign test p | **0.0059** |
| effective independent bets | **~2.6** |
| **correlation-aware null p** | **0.053** (borderline fail) |
| portfolio bootstrap | ΔSharpe +0.263, **CI [+0.025, +0.482]**, p=0.015 ✅ |

Domain comparison, identical methodology:

| domain | series | wins | mean ΔSharpe | corr-null p |
|---|---:|---:|---:|---:|
| **crypto majors** | 20 | 16 | **+0.094** | 0.053 |
| **US equities** | 109 | 22 | **-0.065** | 0.793 |

Note the split within crypto: the **cross-section** is borderline (p=0.053) but
the **equal-weight portfolio** passes (p=0.015). That is consistent — 20 majors
carry only ~2.6 independent bets, so the cross-sectional test has little power,
while the portfolio test uses the full time series.

---

## What this changes

**It bounds the claim.** SMA-50 is **domain-specific to crypto**, not a
universal law. It is not invalidated — the crypto evidence (BTC 15y, Bitstamp
pool, Binance majors portfolio) still passes its gates — but the equity failure
rules out the strongest form of the claim ("this is a general market phenomenon").

**It strengthens the mechanism story.** The rule is not a lucky pattern: it works
exactly where returns trend (VR > 1) and fails exactly where they revert
(VR < 1), and the per-series correlation between trendiness and edge has the
right sign. That is a causal story, not a curve-fit.

**It keeps the honest caveats.** MaxDD is still ~-70%; the edge is modest
(+0.09 to +0.26 Sharpe depending on test); crypto's effective independent bets
are small.

---

## Exposure scaling — making the edge survivable

The candidate's weakest point for "**sustainably**" is the -74% drawdown. Round 1
established that reducing exposure lowers drawdown *mechanically*; there it was a
criticism. Here it is useful: the validated component is the **relative (timing)**
edge, so scaling exposure uniformly should preserve it while shrinking drawdown.

`tools/exposure_scaling.py`:

| exposure band | avgExp | BTC CAGR | BTC MaxDD | BTC Sharpe | Δvs flat | pool MaxDD | pool Δvs flat |
|---|---:|---:|---:|---:|---:|---:|---:|
| 100%/50% | 78.5% | 102.56% | -74.37% | 1.45 | +0.187 | -68.52% | +0.263 |
| 75%/37.5% | 58.9% | 76.38% | -61.93% | 1.45 | +0.187 | -56.71% | +0.263 |
| 50%/25% | 39.3% | 49.65% | -45.55% | 1.45 | +0.187 | -41.64% | +0.263 |
| 40%/20% | 31.4% | 39.15% | -37.81% | 1.45 | +0.187 | -34.60% | +0.263 |
| 25%/12.5% | 19.6% | 23.84% | -24.91% | 1.45 | +0.187 | -22.87% | +0.263 |

**The edge is exactly constant across every band** (+0.187 BTC, +0.263 pool) while
drawdown scales down proportionally, and Sharpe is unchanged at 1.45 / 1.07.

That is a clean confirmation of the interpretation: **the timing signal carries
the information; position size only scales risk and return.** It also gives a
practical risk dial — a 50/25 band delivers -46% instead of -74% at a Sharpe of
1.45.

**It does not make the strategy "safe."** It is still a directional crypto
position and the drawdown is inherent to the asset. This is risk budgeting, not
new alpha.

---

## Updated status of the candidate

| test | result |
|---|---|
| BTC 15y, all 6 gates | ✅ pass |
| Bitstamp 5-coin pool (equal-weight, objective's control) | ✅ pass (p=0.003) |
| Binance 20-major portfolio | ✅ pass (p=0.015) |
| Binance 20-major cross-section | ⚠️ borderline (p=0.053, ~2.6 effective bets) |
| Matched-drawdown / execution-model | ✅ survive |
| Execution defects (churn, stale DB) | ✅ found and fixed |
| **Out-of-domain: US equities** | ❌ **fails 0/4 — not universal** |
| Mechanism (variance ratio) | ✅ explains why crypto works and equities do not |
| Exposure scaling | ✅ edge constant across all bands; drawdown is a tunable risk dial |

## Reproduce

```powershell
.\.venv\Scripts\python.exe tools\equity_out_of_domain.py     # 109 equities, 0/4
.\.venv\Scripts\python.exe tools\trend_mechanism_test.py     # VR mechanism
.\.venv\Scripts\python.exe tools\crypto_majors_replication.py # 20 majors
.\.venv\Scripts\python.exe tools\exposure_scaling.py         # risk dial
```
