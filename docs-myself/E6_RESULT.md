# E#6 — momentum on the liquid universe: FAIL, 5/8, and the closest anything has come

**Date:** 2026-09-26
**Pre-registration:** `PREREGISTRATION_E6.md` (written before any number)
**Engine:** `e6_liquid_momentum.py` · **Result:** `e6_result.json`

## Why this cell had never been run

E#3 tested momentum on the 200 **oldest-listed** perps and found **no rank
power at all**. Fieberg et al. state their effect "originates mainly from the
biggest and most liquid cryptocurrencies." E#3 therefore tested the universe
where the published effect is reported to be *weakest*, and quoting its FAIL
as evidence about liquid coins would have been wrong.

E#6 is the same construction on the universe where the paper claims the effect
is strongest **and** where `measure_cost.py` measured the cheapest round trip.
The universe is fixed by cost, not by the signal.

## Result

| measure | value | gate |
|---|---:|---|
| mean gross per rebalance | **+0.3397%** | |
| mean cost ($10k/name, 13.1 bps all-in) | +0.0387% | |
| **mean net per rebalance** | **+0.3009%** | G1 pass |
| **annualised net return** | **+15.6%** | |
| **annualised net Sharpe** | **+0.735** | **G4 FAIL** (needs 0.95) |
| Newey-West t / dependence-adjusted t | **+1.504** (IAT 1.00) | **G3 FAIL** (needs 2.0) |
| max drawdown | −29.2% | |
| positive-year fraction | 0.75 (3 of 4) | G5 pass |
| positive-symbol fraction | **0.560** | **G6 FAIL** (needs 0.60) |
| largest symbol profit share | 0.251 | G6b pass |

**VERDICT: FAIL, 5/8.** Net positive at base cost and at 2x cost, but the
statistical and cross-symbol gates fail.

## The cost frontier is published, not selected

| per name | all-in cost | annualised net | Sharpe | t_adj |
|---:|---:|---:|---:|---:|
| **$10,000** (pre-committed headline) | 13.1 bps | **+15.6%** | +0.74 | +1.50 |
| $50,000 | 17.7 bps | +14.9% | +0.70 | +1.44 |
| $250,000 | 28.4 bps | +13.3% | +0.62 | +1.28 |
| $1,000,000 | 48.0 bps | +10.3% | +0.48 | +0.99 |

The strategy is **not cost-bound** — the decision does not flip with book size,
because the gross edge (0.34%/week) is large relative to even a 48 bps
round trip. That is a genuine difference from E#4, where cost was the binding
constraint. **Whatever E#6 fails on, it is not cost.**

## Two things this establishes

**1. The structural story holds.** E#3's trend construction had **zero** rank
power on the long tail. E#6, the *same construction* on liquid perps, has a
gross of **+0.34%/week**. Momentum is real in liquid coins and absent in the
long tail, which is what Fieberg et al. report and what
`SIGNAL_VS_COST.md` predicted. **The direction and the venue class of the
published result reproduce here; the magnitude does not.**

**2. It has decayed to nothing.** By year:

| year | net sum | mean |
|---|---:|---:|
| 2023 | +0.355 | +0.0085 |
| 2024 | +0.293 | +0.0056 |
| 2025 | +0.030 | +0.0006 |
| 2026 (35 wks) | **−0.133** | **−0.0038** |

The last two years average roughly zero and 2026 is negative. This is the
McLean & Pontiff decay showing up in a sample that starts *after* the
publication, and it is consistent with the funding-carry result, where the
mechanism was also live in 2021–2024 and switched off afterwards.

## The regime check, which makes it worse

Before reporting the year table it should have been checked against the regime
each year was in. Compounding the weekly net returns:

| year | E#6 gross | E#6 net | BTC | equal-weight basket |
|---|---:|---:|---:|---:|
| 2023 | +43.2% | **+40.9%** | +154.8% | +105.7% |
| 2024 | +33.4% | **+30.7%** | +111.5% | +111.7% |
| 2025 | +1.8% | **−0.02%** | −7.4% | −4.9% |
| 2026 | −12.2% | **−13.5%** | −11.5% | −12.2% |

**In 2025 the construction did what its shape promises.** A long-momentum book
shorts a fifth of the universe, so in a down market it should fall less than the
basket: it lost 0.02% against the basket's 4.9%. That is the theory working.

**In 2023 it did the opposite.** The basket rose 105.7% and E#6 captured
**40.9%** — a capture ratio of 0.39. In 2026 the basket fell 12.2% and E#6 fell
13.5%, an amplification of 1.13.

> **Capture 0.39 on the way up, 1.13 on the way down.** That is a structurally
> bad payoff, and it is a property of the *construction* rather than of the
> sample. A dollar-neutral cross-sectional book is a bet on dispersion, not on
> direction: it earns the cross-sectional spread and forgoes the market move. In
> a year when dispersion is a small fraction of the market's direction — which is
> what 2023 and 2024 in this sample were — it captures a fraction of the upside
> and still carries the short leg's losses.

This is the opposite of the hypothesis that prompted the check ("BTC is in a
bull market, so a correct momentum strategy should be profiting"). The data
says the strategy is *structurally weakest* in exactly that regime.

It also does not rescue the idea. A net-long version would capture the market
move instead of the spread, at which point the momentum signal is no longer the
thing being traded and the cost model changes completely.

## Why it does not clear the bar

Three possibilities, and this experiment cannot separate them:

- **Not enough data.** The top-50-by-volume universe only has 206 weeks of
  common history (2022-09 onward). The paper has seven years on spot. At
  t = 1.50 against a 2.00 requirement, a longer sample could go either way.
- **Price-only is a weak relative of the published factor.** CTREND is an
  elastic-net aggregate over many price *and* volume indicators. E#6 is a
  four-horizon average of price-return ranks, and it was registered that way on
  purpose — so this is a lower bound on what the construction can do, not a
  test of the paper.
- **It is genuinely decayed.** The year table is the strongest evidence for
  this, and a 2022 start gives only two years of the regime that mattered.

**What it does not say:** it does not refute Fieberg et al. Different venue,
different instrument, different period, different construction. A null here is
a statement about *this* configuration on *this* sample.

## The honest summary

| | E#3 (long tail) | E#4 (reversal) | E#6 (liquid momentum) |
|---|---|---|---|
| gross | ~0 / negative | +0.274%/day | **+0.340%/wk** |
| statistically significant | no | **yes, p≈6.7e-4** | no, t=1.50 |
| net after measured cost | negative | negative in the only affordable universe | **+15.6%/yr** |
| passed gates | 2/8 | exploratory | **5/8** |

**E#6 is the first configuration in this project that is profitable after
measured costs at a book size anyone would actually trade. It does not clear
its own statistical bar, and the last two years of it are flat to negative.**

That is worth a forward test rather than a conclusion, and it is worth
pre-registering one — but it is not a strategy yet, and reporting it as one
would repeat the pattern this project has now hit three times.
