# Funding / Basis Carry — is the carry bigger than the cost of harvesting it?

> ## ⚠ CORRECTION 2026-09-26 (later the same day) — the funding switch is back ON
>
> §3 and §7 quote a trailing-12-month gross carry of **+0.36%/yr** and conclude
> the trade is off. That figure was correct when written and is now **stale**.
> Measured live against Binance across 23 majors and 500 recent settlements:
>
> | window | gross carry annualised |
> |---|---:|
> | trailing 30d | **+3.84%/yr** |
> | trailing 90d | **+3.23%/yr** |
> | trailing 365d | **+1.52%/yr** |
>
> **All three clear this report's own triggers** (3.60%/yr monthly, 1.20%/yr
> quarterly). `RESEARCH_STATE.md` §2a had already been updated to "the §2 switch
> is now ON on the short horizon"; §3 and §7 here were quoting the superseded
> number. Corrected.
>
> **What does not change:** the decomposition in §9. Live pooled median
> funding is +0.0033%/8h and only **21.6%** of settlements sit at Binance's
> administered component (against 39.7% historically), so the **excess is
> −0.85%/yr** — independently reproduced by the adversarial review at −0.85/yr
> against this repository's −0.88/yr. The *gross payment* is flowing again;
> the part of it that was ever a return rather than a financing charge is
> still negative.
>
> So the honest position is **"right for the wrong reason"**: the switch
> re-armed, but what is behind it is smaller than the switch implies.

---

**Date:** 2026-09-26
**Reproduce:** `.venv\Scripts\python.exe tools\carry\carry_analysis.py`
**Verdict: the mechanism is real, and the current level is regime-dependent —
see the correction above.**

---

## The setup

Hedged carry: long spot, short perp, same notional. Direction-neutral. The
short leg **receives** funding when the rate is positive. Data is the 20-symbol
funding stream already on disk (`user_data/data/binance_funding/`), 6,493 fully
common 8h settlements spanning **5.92 years** (2020-10-16 → 2026-09-19).

Cost model, conservative public taker with no BNB discount:

| leg | fee | |
|---|---|---|
| spot taker | 0.10% | 0.15% to establish |
| perp taker | 0.05% | 0.15% to close |
| | | **0.30% round trip** |

---

## 1. The carry is real

Mean settlement **+0.0086%**, median **+0.0100%**, positive **74.3%** of the
time. Per symbol, annualised gross carry over the full sample:

| best | | worst | |
|---|---:|---|---:|
| LINK | **+14.52%** | BNB | **+0.66%** |
| UNI | +14.52% | TRX | +1.63% |
| AAVE | +14.29% | BCH | +2.34% |
| LTC | +13.56% | SOL | +3.68% |
| ETH | +12.33% | … | |
| BTC | +11.16% | | |
| | | **median symbol** | **+11.68%** |

**0 of 20 symbols have a negative annualised carry.** Equal-weighted across all
20, gross carry is **+7.96%/yr** and a single 0.30% round trip is repaid after
**14 days**.

So the mechanism is not a mirage. It genuinely pays, and it pays on every symbol
tested.

---

## 2. It only works at low turnover

| re-establishment | cost/yr | net/yr |
|---|---:|---:|
| never (one entry) | 0.00% | **+7.96%** |
| quarterly | 1.20% | +6.76% |
| monthly | 3.60% | +4.36% |
| fortnightly | 7.80% | +0.16% |
| weekly | 15.60% | **−7.64%** |
| daily | 109.50% | −101.54% |

This is a **hold-the-position trade, not a trading strategy.** Anything that
re-establishes more than monthly destroys it.

A selection rule — hold only while the trailing 21-settlement mean funding is
positive, stand flat otherwise — gives mean net **+5.58%/yr**, worst year
**−7.03%**, and **3 negative years out of 7**. It helps relative to always-on,
but it does not rescue the recent period.

---

## 3. The number that decides it: the carry available *right now*

| year | equal-weight gross carry |
|---|---:|
| 2021 | **+38.29%** |
| 2022 | **−2.38%** |
| 2023 | +5.26% |
| 2024 | +10.66% |
| 2025 | +1.91% |
| 2026 YTD | **−0.27%** |

Rolling 365-day carry has been **negative since 2026-02** and has sat near zero
throughout 2025.

```
MOST RECENT 365 DAYS, gross carry   :  +0.36%
  net at quarterly re-establishment :  -0.84%/yr
  net at monthly re-establishment   :  -3.24%/yr
```

**Running this today loses money.** The headline +7.96%/yr is an artefact of
2021, when long positioning was crowded to an extreme and funding paid +38% in
a single year. That regime has not returned.

This is exactly what He, Manela, Ross & von Wachter (arXiv:2212.06888)
predicted for perpetual mispricing: it *"dimish[es] over time."* The arithmetic
confirms it without needing their model.

---

## 4. Why this is a regime trade, not an edge

Funding is a **consequence of crowding**. The trade pays precisely when
positioning is crowded — which is also when the market is most fragile. So:

- Funding high → you get paid → but that is when a violent unwind is likelier.
- Funding low → you are not paid → but the market is calmer.

There is no setting of this trade that is good in both regimes. It is a
**measurable switch**, not a persistent return stream.

---

## 5. What this is actually worth

Not a strategy. A **switch that can be checked cheaply and often**.

The break-even thresholds, stated once so they can be monitored:

| discipline | needs gross carry above |
|---|---:|
| quarterly re-establish | **+1.20%/yr** |
| monthly re-establish | **+3.60%/yr** |
| currently available | **+0.36%/yr** |

So the trade switches on when the trailing-30-day equal-weight funding
annualises above ~3.6% (monthly discipline) or ~1.2% (quarterly). It is
currently roughly 10x and 3x below those thresholds respectively.

That check costs one number, computed monthly, from data already on disk. It
tells you when the mechanism is worth deploying and when it is not — which is
something this project did not have before.

---

## 6. The basis leg — also measured, and also not viable

The funding leg above is only half of a cash-and-carry. The other half is the
basis: if the perp trades at a premium to its index and that premium converges,
the short-perp leg earns it regardless of funding. This was listed as
unmeasured in the first version of this report. It is now measured.

Script: `tools/carry/basis_leg.py`. Data: `binance_v2/canonical/`
mark_price and index_price at 1h, 5 perpetuals, 2020-02 → 2026-08.

**The hypothesis I started with was wrong.** I assumed a persistent positive
premium — perp longs paying for leverage, shorts supplying it. The data says
otherwise:

| symbol | mean basis | median | p05 | p95 | % bars premium |
|---|---:|---:|---:|---:|---:|
| BNBUSDT | +0.0 bps | +0.0 | −11.2 | +10.5 | 48.9 |
| BTCUSDT | −1.5 bps | −3.6 | −5.8 | +9.1 | 24.9 |
| ETHUSDT | −1.1 bps | −3.4 | −6.1 | +10.1 | 28.0 |
| SOLUSDT | −2.8 bps | −3.6 | −8.8 | +11.9 | 28.5 |
| XRPUSDT | −1.1 bps | −3.5 | −7.7 | +12.4 | 29.4 |

**Mean basis across all five is −1.3 bps** — a small *discount*, and the basis
is at a premium only 25–29% of the time on the majors. The dispersion is
bigger than the level.

It is also **persistent** (mean lag-1 day autocorrelation **+0.52**), so it is
a slow-moving level, not an oscillation to be harvested. Trading it is a
directional bet that the basis falls, not a convergence trade.

A percentile rule — short when basis is above a trailing-1-year percentile,
close at the median — is net negative at **every** entry threshold:

| entry percentile | cycles | net per cycle | net/yr |
|---:|---:|---:|---:|
| 50 | 22,759 | −27.1 bps | −207.8% |
| 70 | 9,227 | −25.2 bps | −78.9% |
| 80 | 4,974 | −23.7 bps | −40.1% |
| 90 | 1,883 | −20.3 bps | −13.0% |
| 95 | 957 | −16.1 bps | **−5.2%** |

The 30 bps round trip exceeds the convergence captured at every threshold, and
the more selective the entry the more of the move is already gone. Today the
available entry edge is **8.7 bps against a 30 bps cost**.

## 7. Conclusion after both legs

Both components of the carry trade are measured and both are currently
unprofitable:

| leg | trailing 12m / current | threshold | verdict |
|---|---:|---:|---|
| funding | +0.36%/yr | 3.60%/yr | **OFF** |
| basis | 8.7 bps entry edge | 30 bps | **OFF** |

Neither is a rounding error away from viable. The funding leg is ~10x short of
its threshold and the basis leg ~3.5x short. The mechanism is real in
aggregate (+7.96%/yr over 5.9 years) and that history is dominated by 2021;
neither leg is worth harvesting at today's levels.

**What is not established here:** the basis figure uses mark/index rather than
traded perp/spot prices, so it is a fair-value premium proxy rather than the
exact executable spread; and it covers 5 symbols against the funding data's 20,
because mark/index is only available for the `binance_v2` set.

---

## 8. Drawdown — the omission that mattered

The first version of this report gave **no drawdown for the carry book at
all**. That was a material error, not a formatting one, and it was pointed out
by the parallel session working on the literature review. A hedged carry
position is direction-neutral, which makes it *look* risk-free; the risk it
actually carries is tail-shaped and serial:

- funding is **forfeited on an early close** (no accrual if you are out before
  the settlement);
- the payment is **capped by the venue** while the liability on the short leg is
  not — a bounded premium against an unbounded obligation;
- a delta-neutral book still loses on margin and on basis, and spot and
  USDⓈ-M are **separate margin systems** (only Portfolio Margin nets them).

Measured on the cumulative equal-weight daily funding stream:

| | value |
|---|---:|
| worst drawdown, equal-weight | **−3.58%** (on 2023-01-07) |
| **longest underwater stretch** | **569 days** |
| final cumulative | +55.71% over 2,165 days |

Worst drawdown per symbol on the same accumulation:

| symbol | max drawdown |
|---|---:|
| FILUSDT | **−32.45%** |
| BNBUSDT | **−30.82%** |
| BCHUSDT | −24.47% |
| TRXUSDT | −23.40% |
| SOLUSDT | −21.90% |
| ATOMUSDT | −16.81% |
| BTCUSDT (best) | −0.41% |

Two things follow. First, diversification works far better on the downside than
on the upside: equal-weight caps the drawdown at −3.58% where the worst single
name reached −32.45%. Second, **569 consecutive days underwater on a trade whose
entire gross edge is 7.96%/yr is a different product from what §3 describes.**

The single-symbol figures are close to He, Manela, Ross & von Wachter
(arXiv:2212.06888 v7, Table 6), who replicate this exact long-spot/short-perp
book on Binance and report **BNB −5.14%/yr, Sharpe −0.66, max drawdown
−33.61%**. This report's independent BNB drawdown is −30.82%.

**Any carry result quoted without a drawdown should be treated as
incomplete**, including the earlier versions of this one.

---

## 9. The gross figure is not a return you can keep

The +7.96%/yr headline in §1 is the **gross** funding payment. It is not
harvestable excess. The parallel literature review in
`docs-myself/CARRY_LIT_REVIEW_2026-09-26.md` and §3.17 of
`RESEARCH_STATE.md` decompose it against Binance's administered interest
component and find the **excess is about −1.5%/yr**, negative for 9 of 20
symbols, with BTC's excess at roughly +0.2%/yr — i.e. zero.

That is a stronger statement against the trade than anything in this report,
because it is arithmetic rather than a significance test, and because it holds
over the full 5.9-year sample rather than only the last 12 months. The
mechanism is real and the payment is real; what the decomposition removes is
the part of it that was ever a return rather than a financing charge.

**Read this report's sections 1–4 as describing the gross payment stream, and
§3.17 as describing what is left for the trader.**

---

## 10. What this is actually worth

**Do not deploy carry now.** The current funding level does not cover the cost
of harvesting it.

**Do start monitoring it.** Add the trailing-30-day equal-weight funding
annualisation to a monthly check against the 3.6% / 1.2% thresholds. This is a
genuine, low-cost decision aid, and it is the first artefact in this project
that says "the mechanism is real, here is exactly when it pays, and we are not
in that condition."
