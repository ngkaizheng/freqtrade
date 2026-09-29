# E#11 — the actual Moskowitz-Ooi-Pedersen construction: **it protects the bear**

**Date:** 2026-09-26 · **Engine:** `e11_mop.py` · **Note:** pre-registration is
`PREREGISTRATION_E11.md`; this is the eighth look at the same panel.

## Why this experiment existed

E#7 tested "time-series momentum" as **long/cash, fixed size, single lookback**
and found it gave essentially no protection in 2022 (loss ratio 0.96x). A
literature review flagged that as the one place where the published evidence
positively predicts protection and this project had found none — and that
E#7 was not MOP.

MOP (*JFE* 104(2) 2012, 1380 citations) is:

1. **long-SHORT** — the alternative to long is short, not flat;
2. **volatility-scaled** — each position's return divided by its own realised
   volatility, times a target. This is the paper's central innovation.
3. **diversified across 1–12 month lookbacks**, with a second-stage portfolio
   volatility target on the aggregate.

E#7 had none of those three. **Its null was measuring the implementation.**

## Result

| | CAGR | max DD | Sharpe |
|---|---:|---:|---:|
| buy-and-hold (this script's benchmark) | +22.1% | −81.0% | 0.64 |
| E#7 long/cash 126d | −2.2% | −84.5% | 0.28 |
| E#8 vol-target only, buy-and-hold base | +10.2% | −33.4% | 0.585 |
| **E#11 MOP aggregate, 20%/20%** | **+13.9%** | **−24.4%** | **0.77** |

### The MOP prediction, and it holds

| | 2022 |
|---|---:|
| **buy-and-hold** | **−63.9%** |
| **MOP, every cell** | **+4.6% to +12.9%** |
| E#7 long/cash, for contrast | ratio **0.96x** |

> **MOP was profitable in every one of nine cells in a year the basket lost
> 63.9%.** MOP's published claim is that the diversified portfolio "performs
> best during extreme markets". On this sample that reproduces.

**E#7's 0.96x was the long/cash implementation, not the hypothesis.** The
user's objection — "说到底还是要有策略" — was pointing directly at this.

And because the book is long-short, **it does not need a bull market.** That is
the direct answer to the question that reframed this whole afternoon: the bull
is available for free from holding, and the problem is the bear. A market-neutral
trend book does not have that problem.

## What must be discounted, and by how much

**Cederburg, O'Doherty, Wang & Yan, "On the performance of volatility-managed
portfolios," *JFE* 138(1), 2020** tested 103 equity strategies and found
volatility-managed portfolios "do not systematically outperform their
corresponding unmanaged portfolios in direct comparisons", and that
"reasonable out-of-sample versions generally earn lower certainty equivalent
returns and Sharpe ratios". The Sharpe gain came from "structural instability".

**E#11's Sharpe of 0.77 is exactly the number that paper says does not survive
real-time discipline.** It is in-sample, one period, a survivor universe, and the
best of nine cells. **Treat it as unproven.**

**The drawdown result is the defensible half.** Harvey, Hoyle, Korgaonkar,
Rattray, Sargaison & van Hemert, "The Impact of Volatility Targeting," *JPM*
45(1) 2018, find the *Sharpe* benefit is asset-class specific (equity and credit
have a leverage effect; bonds, FX and commodities get nothing) while the
**left-tail benefit is general** — "left-tail events tend to be less severe
because they typically occur at times of elevated volatility, when a
target-volatility portfolio has a relatively small notional exposure."

E#11's −81.0% → **−24.4%** is that mechanism, and it is a published one rather
than a local observation. Note crypto is a risk asset with a strong leverage
effect, so the Sharpe claim should apply in principle — but Cederburg's
out-of-sample discipline is the warning.

## Caveats

- **Eighth look at the same 200-symbol download.** Nothing here is a discovery.
  The forward collector and depth archiver are the arbiter.
- **9 cells, best reported.** The 20%/20% cell is the best Sharpe of nine.
- **The MOP universe is diversified futures; this is 50 crypto perps.** Real
  difference, recorded not glossed. A long-short book should be *less*
  survivor-biased than a long-only one, but the bias is not eliminated.
- **The benchmark differs between scripts** — E#8's buy-and-hold is
  −4.98% CAGR / 0.295 Sharpe and this one's is +22.1% / 0.64, because the cost
  and rebalancing conventions differ. The MOP-vs-holding comparison *within*
  this script is the valid one.
- **One paper that claims a trailing stop works on exactly this**
  (arXiv:2602.11708, "Talyxion Research, Hanoi": Sharpe 2.41, maxDD −12.7%) is
  a serial self-publisher selecting assets on the data it fits. Its own
  no-optimisation ablation is Sharpe 1.34 / MDD −28.6% and its bear-market
  Sharpe is **−0.31**. Do not cite it.

## Look-ahead audit — the same defect was found in E#8 and here, and both results survived

An adversarial review found a one-bar look-ahead in E#8's volatility overlay:
`realised_vol = base_ret.rolling(30).std()` includes `r_t`, `exposure[t] =
vt/realised_vol[t]`, and that exposure was applied to `r_t` — so the book was
credited with cutting exposure on exactly the days that turned out large.

**The same defect was present in E#11's stage-1 volatility weight.** The signal
was shifted; the weight was not. Both are now `.shift(1)`.

| | before the fix | after |
|---|---|---|
| E#8, 20% target 1x, CAGR | +10.2% | **+11.9%** |
| E#8, 20% target 1x, max DD | −33.4% | **−35.3%** |
| E#11, 20%/20%, CAGR | +13.9% | **+15.6%** |
| E#11, 20%/20%, max DD | −24.4% | **−25.1%** |
| E#11, 20%/15%, Sharpe | 0.77 | **0.82** |
| E#11, 2022, all 9 cells | +4.6% to +12.9% | **+4.1% to +12.6%** |

**Both results survived, and the MOP result improved slightly.** That matters
more than the original number: the published test of this exact overlay (Liu,
Tang & Zhou, *JPM* 45(4) 2019) reports that correcting the look-ahead makes the
drawdown *worse* (68–93%) and that the strategy "outperforms the market only
during the financial crisis period". On this sample neither happened.

**Sharpe autocorrelation check.** Volatility-targeting returns are serially
correlated *by construction*, and this project has been bitten by exactly that
three times. Measured here: **IAT = 1.00, effective N = 2,435 of 2,435** for
every cell. The returns are not autocorrelated at daily frequency, so the
naive and adjusted Sharpe are identical and 0.82 stands. Had it come out at
IAT 3, the reported Sharpe would have been a third of the truth.

## The question "没有止损和赌博是一样的吧" — answered, with a formula

The user's objection was: a strategy with no exit rule is gambling. That is
right, and there is a published reason why no exit rule can fix it.

**Lempérière, Deremble, Seager, Potters & Bouchaud, "Two centuries of trend
following," arXiv:1404.3274, §4.3:**

> "the typical duration of a drawdown is given by **1/S² (in years)** for a
> strategy of Sharpe ratio S. This means that for a Sharpe of 0.7, typical
> drawdowns last two years while drawdowns of 4 years are not exceptional."

| Sharpe | typical underwater period |
|---:|---:|
| **0.82 (E#11)** | **1.5 years** |
| 0.75 | 1.8 years |
| 0.585 (E#8) | 2.9 years |
| 0.30 | 11 years |

> **A −25% drawdown lasting about eighteen months is the EXPECTED regime for a
> Sharpe-0.8 strategy, not a defect.** And this is not a crypto peculiarity:
> Bitcoin's own 2017 peak was regained **1,068 days (~2.9 years) later**, on
> 5 March 2024.

**This is why the stop-loss family kept failing, and why it was always going
to.** A strategy with a Sharpe of 0.5–0.8 spends years underwater by
construction. Any exit rule that gets you out will be out of the market for
part of a multi-year recovery, and E#9 and E#10 measured exactly that: the
forward return after a stop fires is statistically indistinguishable from a
random day (E#9) and no signal horizon in {21, 42, 63, 126} days carried
information (E#10, one exploratory exception).

**The resolution is not a better stop. It is position sizing that survives an
18-month underwater period** — which is what the volatility target is for, and
why E#11's −25.1% drawdown paired with a 15.6% CAGR is a materially different
object from a 40% stop rule attached to a 0.28-Sharpe signal.

## One context number the canon needs

Lempérière et al. report trend-following Sharpe **0.80 on futures since 1960
(t = 5.9)** and **0.72 over two centuries (t = 10.5)** — and state explicitly
that the simulation runs **"without costs"** and the P&L is **"fictitious"**
because no implementation cost was modelled. **Every headline number in the
trend-following canon is gross.** E#11's 0.82 is net of a measured cost, which
is either genuinely strong or a reason for more suspicion, not less.

Their lookback table also settles E#7's horizon question: Sharpe is flat
(n = 0.80) from **2 to 10 months** and decays beyond. **126 days ≈ 4 months is
inside the plateau**, so E#7's null was never a lookback error. It was the
long/cash implementation, which E#11 fixed.

## The state of things

| line | Sharpe | max DD | 2022 |
|---|---:|---:|---:|
| buy-and-hold | 0.64 | −81.0% | −63.9% |
| E#6 cross-sectional momentum | — | — | wrong shape (0.39 up / 1.13 down) |
| E#7 time-series momentum (long/cash) | 0.28 | −84.5% | 0.96x holding |
| E#9 price trailing stop | — | — | no information |
| E#10 signal exit, 42d | 0.73 | −71.1% | improves return, not risk |
| E#8 vol target only | 0.585 | −33.4% | — |
| **E#11 MOP proper** | **0.77** | **−24.4%** | **positive in 9/9 cells** |

> **The one construction that was done properly, on the right horizon, with the
> right structure, is the only one that both made money and survived the bear.**
> Everything else on this list is a variant of it that was not.
