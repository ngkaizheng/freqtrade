# PRE-REGISTRATION — payoff ratio, funding filter, and a long-side book

**Date frozen:** 2026-09-27, **before any of these three results is computed.**
**Author:** agent session, at the user's request to run the payoff-ratio and
funding-filter tests and to build a long strategy on 2024-01 → 2025-09.

---

## 0. THE TRAP, STATED FIRST (AGENTS.md §3)

The user specified the window **2024-01 → 2025-09** for the long strategy. That
window was chosen before the result was seen, and it is 21 months. At the
measured 286 trades/year it yields roughly **500 trades and an effective N of
30–40**, which **cannot reach t = 2.0 under any parameterisation.**

> **Every result is therefore reported on BOTH the requested window AND the full
> 2023-01 → 2026-08 sample.** The gap between them is the finding. A number
> quoted from the short window alone is not a result, and if the two disagree
> the short-window number is the one that is wrong.

The two mechanism tests (§1, §2) run on the **FULL SAMPLE only**, so that the
window cannot contaminate them.

---

## 1. Payoff ratio — the question REPORT_PHASE4 flagged and never measured

`REPORT_PHASE4.md` §4, verbatim: *"The 1R stop / 2R target bracket needs a 33%
hit rate before costs, which leaves no room for a small edge. A wider stop with
a higher payoff ratio reduces the trade count but raises the edge demanded per
trade. **Whether that helps depends on whether the edge is proportional or
fixed — which is itself a measurable question.**"*

It was never measured. **Fixed:** stop at 1.5 ATR, low-vol filter on, SHORT leg
only, all four cost regimes. **Vary `r_multiple` over a frozen 5-point grid:
1.5 / 2.0 / 2.5 / 3.0 / 4.0.**

- **The whole grid is published as a frontier.** Picking the best cell is
  forbidden — that is the multiple-testing error this apparatus exists to catch,
  and 2.0 is already the incumbent, so a winner here is expected by chance
  alone at roughly 1-in-5.
- Reported statistic: net R per trade, total R, and dependence-adjusted t,
  **at every point**.

## 2. Funding filter — economically motivated, never run

Data for all 104 symbols is already on disk. Hypothesis: **positive funding
means longs are crowded and pay, which precedes downward moves** — so trade the
short side only when funding is high.

**Frozen definition:** `funding7d` = cumulative funding rate over the trailing
7 days (42 bars), ex-ante by construction. Two cells, both reported:
short when `funding7d` is **above** its own 365-bar median, and **below**.

Both signs are reported because the sign is genuinely not known a priori;
selecting one afterwards is forbidden.

## 3. The long book

The long leg of SHARK-01 is net-negative in all 12 cells and all 3 cost
regimes on the full sample. This tests whether that is a property of the signal
or of the missing filter.

| cell | rule |
|---|---|
| **L1** | long leg, no filter |
| **L2** | long leg, **high-vol** — the exact inverse of the frozen low-vol filter |
| **L3** | long leg, **funding filter** (both signs, as §2) |

**L2 is the pre-registered hypothesis with a mechanism behind it:** the
low-vol filter is validated on the short side (Kurth et al., ⚠ preprint), and if
low volatility is where breakouts mean-revert then high volatility is where
they continue. **If L2 also fails, the honest reading is that the edge is
specifically a short-side edge, not a volatility-conditioned edge in general.**

**Reported on both windows**, per §0.

## 4. What is forbidden

- Quoting the 2024-01 → 2025-09 window without the full-sample number beside it.
- Selecting the best `r_multiple` and calling it the strategy.
- Selecting one funding sign.
- Adding a fourth filter because the first three were disappointing.

## 5. The bar, and what a fail means

None of these can be expected to clear significance at this sample size. The
question they answer is **"does this mechanism raise edge per trade at all?"**,
not "is this a tradeable strategy". A cell that raises net R per trade while
leaving t unchanged is a **lead**, not a result, and will be labelled as such.

**The standing verdict on the parent line is unchanged and is not reopened
here:** the frozen short-leg cell sits at **t = 1.8746 vs a 2.0 bar**, with the
leg selected on the full sample. Nothing below changes that.
