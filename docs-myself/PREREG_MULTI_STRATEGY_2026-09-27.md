# PRE-REGISTRATION — multi-strategy test on the only data with power

**Date frozen:** 2026-09-27, **before any of the three strategies was run.**
**Author:** agent session, at the user's request ("再写几个合适的 strategy 试试看").

This file exists so that the rules and the bar are fixed *before* the numbers
are seen. `AGENTS.md` §3 requires it. If a result is reported later, it is
reported against what is written here.

---

## 1. The question

The user asked: *"没有一个策略可以在牛市还是熊市赚钱吗?"* — must there really be
no strategy that makes money in a bull market **and** in a bear market?

That is a fair challenge and it deserves a direct answer, not a refusal.
This pre-registration tests the three most standard, literature-backed answers.

## 2. Data — and why this universe and no other

**Universe: BTC/USD, Bitstamp, daily, 2011-08-18 → 2026-09-19 (15.1 years, 5,512 bars).**

This is the *only* dataset in the repository with enough calendar time for a
verdict. Measured 2026-09-27 (`tmp_bt/power_check.py`, Lo 2002 `SE(SR)=1/√years`):

| candidate universe | common window | min detectable Sharpe at t=2 |
|---|---:|---:|
| 26 Binance perps (BTC…TIA) | 2.9y | 1.17 |
| 19 Binance perps (≤2020-10) | 5.9y | 0.82 |
| 5 Bitstamp spot (BTC,XRP,LTC,ETH,BCH) | 8.8y | 0.67 |
| **BTC/USD Bitstamp** | **15.1y** | **0.52** |

**Bar on data is therefore: a Sharpe below 0.52 cannot be detected here at all.**
That limitation is accepted up front and will be repeated in the result.

Adding coins does not help: 26 majors measured **0.593 mean pairwise
correlation ⇒ 1.64 effective independent bets**. Breadth is not power.

## 3. The three strategies — exact rules, frozen

All three are **long/flat** (Bitstamp is spot, so no shorting). All three apply
the **same volatility overlay**, whose two parameters are taken from the
project's own E#8 pre-registration and are **NOT tuned here**:

- `target_vol = 0.20` (annualised) — E#8's cell
- `vol_lookback = 30` (days) — E#8's cell
- exposure `f = min(1.0, target_vol / realised_vol)`
- `realised_vol` is read from the **previous completed bar** (`iloc[-2]`), never
  the forming bar. This defect (using `vol[t]` on `r_t`) was found in this repo
  twice — E#8 and E#11 — and is the reason this line is explicit.
- rebalancing only when the target differs by **>10% of equity**, to avoid fee churn

| # | name | entry | exit | family |
|---|---|---|---|---|
| **S1** | `VolTargetHold` | always in market | never | no direction at all (E#8 mechanism) |
| **S2** | `TrendVolTarget` | `close > SMA(200)` | `close < SMA(200)` | time-series trend filter |
| **S3** | `DonchianVolTarget` | `close > 55d high` | `close < 20d low` | classic breakout (Turtle) |

SMA-200 and Donchian 55/20 are the conventional published parameters and are
**not** chosen from this data. No parameter search of any kind will be run.

## 4. The bar — fixed now

A strategy "passes" only if **all** hold on the full 15.1y:

1. **Sharpe ≥ 0.95** — the project's standard edge bar (E#6/E#7 used 0.75–0.95).
2. **Max drawdown strictly better than buy-and-hold over the same window.**
3. **Positive CAGR.**

**Falsification:** if all three fail, the answer to the user's question is "no,
not on this data", and that will be stated plainly rather than softened.

## 5. What will be reported — all of it

- **All three** strategies, pass or fail. No best-of selection.
- **Per-calendar-year returns** for each, plus buy-and-hold, so bull and bear
  behaviour is visible rather than summarised into one number.
- **The dispersion** across the three. Per `AGENTS.md` §3, if one looks good I
  will report the spread and explicitly ask whether it is distinguishable from
  luck given a 0.52 detection floor — not promote the winner.
- Cost: freqtrade's default fee. Rebalancing turnover will be reported.

## 6. Known traps carried in from the project record

- Vol targeting's drawdown gain was judged **"almost entirely mechanical"**
  (`FINAL-DECISION.md`). Expected, and it does not by itself count as an edge.
- **Cederburg et al. (JFE 2020)**: vol-managed portfolios "do not systematically
  outperform" out of sample. This is a prior *against* S1/S2.
- `BTCSmaTrend` already passed historical gates here and had **out-of-sample
  point estimates at or below zero**. S2 is close to that family; a good
  full-sample number here would NOT overturn that.
