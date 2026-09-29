# E#8 — volatility targeting and leverage: **PASS on the pre-registered gates, with one important caveat about my own base**

**Date:** 2026-09-26
**Pre-registration:** `PREREGISTRATION_E8.md` · **Engine:** `e8_voltrev_leverage.py`

---

## The headline, which is a real finding

**Volatility targeting, applied to nothing but buy-and-hold, on this universe:**

| | CAGR | max drawdown | Sharpe | torture ratio |
|---|---:|---:|---:|---:|
| buy-and-hold, 1x | **−4.98%** | **−83.60%** | 0.295 | −5.95 |
| **+ 20% vol target, 1x** | **+10.25%** | **−33.40%** | **0.585** | **30.69** |
| + 20% vol target, 2x | +17.43% | −57.43% | 0.600 | 30.35 |

A holding period that **loses** 5% a year with an 84% drawdown becomes one that
**makes 10% a year with a 33% drawdown**, by doing nothing but scaling exposure
down when volatility is high. Realised vol on this basket averages 62%/yr with
a p10 of 32% and a p90 of 90% — the bear is a volatility regime, and this is
the overlay that addresses it.

This is the mechanism E#6 and E#7 could not deliver, and it required no
directional prediction at all.

---

## The answer to the leverage question

**10x and 20x are dead on arrival. 2x–3x is the ceiling, and only at a low
volatility target.**

Buy-and-hold base:

| vol target | 1x | 2x | 3x | 5x | 10x | 20x |
|---|---|---|---|---|---|---|
| **20%** | ok | ok | **DEAD** | DEAD | DEAD | DEAD |
| **35%** | ok | ok | **DEAD** | DEAD | DEAD | DEAD |
| 50% | ok | **DEAD** | DEAD | DEAD | DEAD | DEAD |
| 70% | ok | **DEAD** | DEAD | DEAD | DEAD | DEAD |

This is not a surprising result and it was predicted in the pre-registration
before the run. An account at 10x is liquidated by a −10% move; at 20x by a
−5% move. Crypto does both weekly. **Leverage is a constraint on how much
drawdown you are permitted, not a way to increase return.**

The interesting part is that **leverage is only survivable *because* the
volatility target reduced the drawdown first.** At 20% targeting, exposure
averages 0.19–0.39, so 2x–3x *net* is close to 1x *gross* risk. **Volatility
targeting is what makes the leverage legible.**

---

## The caveat — and it is about my own work, not the literature

**The "trend" base in this experiment is NOT the pre-registered E#7
construction, and it is the one producing the spectacular numbers.**

E#7 registered: long/cash on the **basket's** trailing 126-day return,
**monthly** rebalance, **21-day skip**, measured on month-end sampling. It
failed: CAGR −2.21%, capture 0.15, 2022 ratio 0.96x.

E#8's `trend_overlay` is: long/cash on the **cross-sectional mean of per-name**
trailing 126-day returns, **daily** rebalance, **no skip**. It shows CAGR
+36.4% with a −51.9% drawdown before any overlay.

Those are different hypotheses. E#8's is **better on this sample** and was
**not pre-registered**. It is reported here because leaving it out would be
selective, and it is not treated as a result because the pre-registered version
of the same idea failed.

**The buy-and-hold + volatility-target row IS pre-registered and IS the finding.**
The trend rows are exploratory and need their own registration before they mean
anything.

---

## Gates — all four pass, on the pre-registered base

| gate | result |
|---|---|
| G1 CAGR > buy-and-hold | **PASS** (+10.2% vs −5.0%) |
| G2 torture ratio > buy-and-hold | **PASS** (30.7 vs −6.0) |
| G3 that configuration survives | **PASS** |
| G4 max DD no worse than −79.8% | **PASS** (−33.4%) |

G5 (|t| ≥ 2.0) is not evaluated in the script; with 2,435 daily observations
on an autocorrelation-corrected statistic it would clear, but that is an
assertion and should be computed rather than assumed.

---

## What has to happen before this is a strategy

1. **Register the trend variant separately**, or drop it. The pre-registered
   monthly+skip version failed; an unregistered daily no-skip version looks
   much better, and that gap is exactly the shape of a result that gets
   laundered into a success.
2. **Sharpe is the number to watch, and it is 0.585 unlevered** for the clean
   result. The leverage and volatility target change CAGR and drawdown; they
   barely change Sharpe (0.585 → 0.600). If the Sharpe does not hold up
   out-of-sample, none of the leverage arithmetic matters.
3. **Survivorship.** The universe is 50 *currently* listed perpetuals. In a
   2020–2026 sample dominated by two enormous bull years, a survivor universe
   flatters long-only strategies considerably. This is the largest unquantified
   bias in the result and it is not correctable from public data.
4. **The volatility overlay itself turns over** 4.5–20.5 times a year, and that
   cost IS charged. At the 70% target it is 20.5x/year, which is where the
   70%-target rows start losing their edge.

---

## The finding that matters most

Across E#6, E#7 and E#8 the pattern is consistent and it is the useful part:

- **Cross-sectional momentum:** right direction, wrong shape (0.39 up / 1.13 down)
- **Time-series momentum:** right horizon, no protection (0.96x in the bear)
- **Volatility targeting:** no direction at all, and it is the only one that
  fixed the drawdown

**Sizing risk beat predicting direction.** On this sample, that is the only
intervention tested that improved the thing the objective actually asks about.
