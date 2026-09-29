# §50 — D-1: THE TWO BOOKS ARE MEASURABLY COMPLEMENTARY. DAILY CORRELATION +0.007.

**Date:** 2026-09-30 · **Prereg:** `docs-myself/PREREG_DIVERSITY_2026-09-30.md`
**Tool:** `tools/perp_short/diversity_check.py` · **Raw:** `user_data/logs/diversity_check.txt`

---

## 1. What was asserted, and what was actually evidence

§49 measured the two books **separately** and reported that they behave differently by
year. **A table of two annual numbers is not a measurement of complementarity.** If their
return series move together, the user has bought one bet twice and the entire rationale for
a second strategy is a story. **That was the one claim in this objective with no evidence
behind it, and this round is the evidence.**

## 2. D1 — the correlation

| | value |
|---|---:|
| **daily Pearson r** | **+0.007** |
| monthly Pearson r | **−0.124** (n = 40 months) |
| **monthly sign agreement** | **55.0 %** |
| overlap | **1,247 common daily returns**, 2023-04-03 → 2026-08-31, on 1,248 days each |

> **The two books' daily returns are UNCORRELATED — r = +0.007.** Monthly sign agreement of
> 55.0 % is a coin flip, which is what independence looks like and is not what a shared
> factor looks like. **§15c measured that the perp cross-section is one factor at every
> horizon; this is what it means for a portfolio: a short timing book and a long timing book
> on the same 40 names are not two reads of the same bet.**

## 3. D2/D3 — the 50/50 combination, and the deciding comparison

| book | total | CAGR | **Sharpe** | maxDD | days |
|---|---:|---:|---:|---:|---:|
| short alone | +113.9 % | 25.0 % | **1.03** | −18.2 % | 1,248 |
| long alone | +95.4 % | 21.7 % | **0.88** | −27.6 % | 1,248 |
| **COMBINED 50/50** | +104.7 % | 23.3 % | **1.29** | **−14.9 %** | 1,248 |

> **The combined Sharpe (1.29) EXCEEDS BOTH singles (1.03 and 0.88), and the combined
> drawdown (−14.9 %) IS SMALLER THAN EITHER (−18.2 % and −27.6 %).**
>
> **That is the complement claim supported by a per-unit-of-risk measurement, not by a
> two-row annual table.** It is exactly the statistic the preregistration named, and it is
> the one that could have come out "between the two" and forced a retraction.

**Every Sharpe in that table is recomputed from the same daily series**, so the three are on
one basis. **The engine's own Sharpe is a different statistic on a different basis and is
not comparable** — printed as a separate number, never mixed in.

## 4. By year — the claim in the form the user would meet it

| year | **short** | **long** | **combined** | panel |
|---|---:|---:|---:|---:|
| 2023 | +11.8 % | **+32.3 %** | +22.0 % | +198.6 % |
| 2024 | +26.7 % | **+42.9 %** | +35.5 % | +103.6 % |
| **2025** | **+35.5 %** | **−5.1 %** | +12.3 % | −56.8 % |
| 2026 | +12.9 % | +9.2 % | +11.1 % | −17.6 % |

**The combined book is positive in 4 of 4 years**, and the mechanism is visible in the rows:
in 2023 and 2024 the long leg dominates; in 2025 the short leg carries it and the long leg's
−5.1 % is diluted to +12.3 %.

**And the sanity check that was built in fires correctly:** the short book is **+35.5 % in
2025, the year the panel fell 56.8 %** — as a short book must be. That is the one-line
reason the rest of the table can be believed, and it is printed by the tool so it cannot be
skipped.

## 5. ⚠ What the 50/50 row is, stated every time it is printed

**It is a CONSTRUCTION, not an engine backtest.** The tool computes the combined daily
return as the equal-weighted average of the two daily returns, which is exact to the extent
that both books are risk-sized as a fraction of equity and near-linear in size.

**A real two-strategy deployment would differ:** capital would be shared, the 24-slot cap
and free balance would be shared rather than doubled, and rebalancing would be real. **The
measured number here is therefore an upper bound on what a deployed pair would achieve**,
and the tool says so in its own output.

## 6. Verdict

**The complement claim is MEASURED, not asserted.** Three independent facts agree:

1. **daily r = +0.007** and **55.0 % monthly sign agreement** — the two books are
   statistically independent.
2. **the combined Sharpe beats both singles** and **the combined drawdown is smaller than
   either** — which is what a genuine complement does and a shared factor cannot.
3. **the combined book is positive in 4 of 4 calendar years**, including a year the panel
   fell 56.8 %.

**What this does not say:** that the pair is better than the short book alone. It is not —
**+104.7 % combined versus +113.9 % for the short book alone.** **The pair trades total
return for a lower drawdown and independence**, which is a different and legitimate thing to
want, and it is the user's call, not the project's.

**The delivered short book is untouched, and B0 reproduces 113.74 % on every run of the
long-book family — the control that made all of this trustworthy.**
