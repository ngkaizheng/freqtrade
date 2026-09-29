# E#4 — CORRECTED. The information coefficient was real; the trade was not.

**Date:** 2026-09-26
**Supersedes:** the earlier version of this file, which reported a 0.274%/day
gross edge and a 26.6 bps breakeven. **Both were wrong by 17–90×.**
**Verification:** `verify_claim1.py` · **Adversary:** `RESEARCH_STATE.md` change log

---

## The correction

The earlier version computed the tradeable edge as

```
3.51 × |IC| × σ_cs   =   3.51 × 0.0195 × 4.02%  =  0.274%/day
```

That identity is exact for jointly normal returns with a *linear* signal. This
panel is fat-tailed and the signal is a *rank*. **The formula was reporting what
a Gaussian theory says the edge should be, not what the portfolio earns.**

Measured, the actual equal-weight decile long-short earns:

| | value |
|---|---:|
| **mean gross per day** | **+0.00591%** |
| **t** | **+0.14** |
| annualised gross | +2.16% |
| **cumulative gross** | **−26.1%** |
| max drawdown | −52.1% |
| mean turnover | 1.03 |
| **breakeven round trip** | **~0.6 bps/day** |

**The formula overstated the edge by 90.5×.** The reported breakeven of 26.6 bps
was really **0.6 bps**, against a **measured** book cost of **3.6 bps mean**
(median 2.7) at $10k per name before fees, and 10 bps of VIP0 taker fee.

> **The binding constraint is the signal, not execution cost.** The earlier
> version of this file said the opposite, and `SIGNAL_VS_COST.md` repeated it.

## The two statistics, and the gap between them

| | value | t |
|---|---:|---:|
| **Spearman** rank IC | **−0.03812** | **−8.03** |
| Pearson IC | −0.01825 | −3.62 |
| **decile long-short portfolio** | **+0.00591%/day** | **+0.14** |

Two further corrections of fact:

- The earlier file called these "Spearman" and quoted the Pearson number. The
  true Spearman is **−0.03812, t = −8.03** — roughly double.
- The reported p ≈ 6.7e-4 is a **one-sided** p on a best-of-nine selection.
  The two-sided corrected value is **1.36e-3**. Still significant; the wrong
  tail was used.

**A rank correlation of −0.038 with t = −8.03 is one of the strongest
cross-sectional relationships measured anywhere in this project. It converts
into a portfolio return with t = 0.14 and a cumulative loss of 26%.**

That gap is the finding. It is the same error as E#3's "IC is significant but
the book loses money", and it is the error AGENTS.md §3 has warned about since
the beginning — *"report in units of risk (R), not cash"* — which this file
violated while quoting the rule.

## By year: it was never there

| year | mean gross/day | t |
|---|---:|---:|
| 2020 | −0.0010% | −0.46 |
| 2021 | −0.0005% | −0.34 |
| 2022 | +0.0013% | 1.40 |
| 2023 | +0.0005% | 0.84 |
| 2024 | −0.0002% | −0.29 |
| 2025 | −0.0003% | −0.36 |
| 2026 | +0.0001% | 0.13 |

**Four of seven years negative; no year reaches |t| = 1.5.** The edge was never
present at the portfolio level in any year, in either direction. The 2020–2021
sign flip is the momentum side, and it is the same coin on the other face.

## The mechanism is not new, and I did not cite the source

Zaremba, Bilgin, Long, Mercik & Szczygielski, *"Up or down? Short-term
reversal, momentum, and liquidity effects in cryptocurrency markets,"*
**International Review of Financial Analysis 81:101908 (2021)**,
doi 10.1016/j.irfa.2021.101908. Peer-reviewed, ~45 citations. Verbatim:

> *"We argue that the daily reversals result from the illiquidity of the vast
> majority of traded cryptocurrencies. In consequence, the pattern is
> cross-sectionally dependent on liquidity, and the handful of largest and most
> tradeable coins exhibit daily momentum rather than a reversal."*

That is the "liquidity provision premium" story in `SIGNAL_VS_COST.md`,
five years early and already recorded in this project's own §3.27(a). The
earlier file cited Fieberg and Arefev and presented the mechanism as a
contribution. **It was not new, and not cited.**

Dobrynskaya (J. AI 2023, doi 10.3905/jai.2023.1.189) dates the
momentum→reversal switch at roughly one month, so the canonical crypto reversal
horizon is a *month* and the 1-day version is specifically the liquidity
artefact — which is consistent with a portfolio-level edge that does not
survive contact with a book.

## What survives of the earlier claim, and what does not

**Does not survive:**
- 0.274%/day gross — **withdrawn**, 90.5× overstated
- 26.6 bps breakeven — **withdrawn**, really ~0.6 bps
- "the binding constraint is execution cost, not the signal" — **inverted**
- the whole E#4 cost table (12/16/18/26.6/35 bps → +54.8% to −31.7%/yr) — **void**
- "Spearman IC −0.0195" — mislabelled; the Pearson value was used
- the "liquidity provision premium" as a contribution — it is Zaremba et al.

**Survives:**
- **A rank IC of −0.038 with t = −8.03 is real** (and survives a block
  bootstrap at −4.06, a Newey-West t at −4.06, winsorising at −4.06, and
  dropping the most extreme name-days at −4.93 — every robustness test makes it
  *more* significant, not less).
- **It does not convert into a tradeable portfolio.** That is the result.

## The lesson, which is the same one as E#3

E#3's gross was negative. E#4's information coefficient was spectacular. **Both
had a null portfolio.** Across this project a statistically strong intermediate
quantity has now failed to become a profit in every case: the 92-hypothesis
screen, Shark's gross, H13's holdout PF, E#3's rank power, and now E#4's IC.

> **An information coefficient is a measurement of association, not of
> money.** The only number that has ever mattered is the return of the actual
> portfolio, and it must be reported first, not derived from a formula about
> what the association ought to be worth.
