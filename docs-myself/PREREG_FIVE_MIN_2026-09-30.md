# PREREG — F-1: measure the 5m cost law instead of extrapolating it

**Written:** 2026-09-30, **before** any 5m bar was downloaded.
**Tool:** `tools/perp_short/probe_5m_feed.py` (Gate 0, done), `tools/perp_short/five_min_horizon.py`.
**Question this settles:** the last input in the closed-list machinery that is still an
extrapolation (§38d).

---

## 1. Why this is worth a round

§35 built `family_prescreen.py`: a family is CLOSED or OPEN **from arithmetic**, before any
research is spent. It applies `cost_R = round_trip_bps / (stop_mult × atr_pct × 1e4)`.

**All thirteen families it screened came out REFUSED because they are already closed**
(§38). The one that was not — the **5m liquidation-cascade** family — was closed on a
**square-root-of-time extrapolation wearing a measurement's label**, and §38d said so
explicitly. Two different extrapolations of the same number disagree by 1.8×, which is
what one should expect when neither is measured.

**This is the only number in the whole pre-screen that was never measured.** Measuring it
either (a) confirms the closure with a real number, or (b) opens a family, and either way
the machinery stops resting on an extrapolation.

**Gate 0 was run first, as the charter requires**, and it is already informative
(`user_data/logs/probe_5m_feed.txt`):

| month | reachable | note |
|---|---:|---|
| 2024-03 | 32/40 | 8 symbols listed later |
| 2024-09 | 34/40 | 6 symbols listed later |
| **2020-03** | **9/40** | **the deployed 40 barely existed in 2020** |
| **2020-07** | **10/40** | same |
| 2025-11 | **40/40** | full coverage |
| 2026-01 | **40/40** | full coverage |

**So 5m data is fully available — the COVID-2020 months are the sparse ones, and the reason
is a property of the UNIVERSE, not of the feed.** The deployed 40 is ranked by *2026*
liquidity, so it is loaded with 2024-2025 listings that did not exist in 2020. **A design
that needs 2020-03 for all 40 symbols is asking for a universe this project does not have,
and the fix is to measure the stress regime INSIDE the coverage, not to substitute a
major-only panel and call it the deployed universe.**

## 2. What will be measured, and the rule from §39 is not optional

`tools/perp_short/five_min_horizon.py` downloads 5m klines for the deployed 40 and computes
the ATR% at **5m, 1h and 4h on the SAME symbols over the SAME window.**

> ⚠ **§39 cost this project a 13 % error: two routes averaged 7 years and 3.7 years and
> called the difference a disagreement.** The three horizons here MUST be pinned to one
> symbol list and one date range, and the tool prints the row counts for each so the
> pinning is visible rather than promised. If the counts differ, the run reports the
> problem instead of a ratio.

4h is already on disk; 1h exists for only 23 of the 40. **The 5m/4h ratio is the one that
matters** (5m is what the family trades, 4h is what the book trades), and it needs no 1h
file at all.

## 3. Pre-registered decisions

**D1 — the gate.** With `atr_5m / atr_4h = r` measured on one window,
`cost_R(5m) = cost_R(4h) / r`. The cascade family's documented effect band is **0.05–0.15 R**.
Using the measured 4h stress cost_R of **0.0308** (34.9 bps, §4):

> **The family is OPEN at the stress bar if and only if `r ≥ 0.0308 / 0.15 = 0.205`.**

**D2 — regime split.** The same ratio computed on (a) the whole window and (b) only the
**top-decile volatility days** inside it, so the stress number is measured rather than
borrowed from 2020. Both are reported; the family verdict is taken on the **worse** of the
two, because a cascade family is a crash family and closing it on a calm-only ATR would be
the same error §38d warns about.

**D3 — the extrapolation audit.** The √t prediction from 4h to 5m is `1/√48 = 0.1443`.
> **If the measured `r` differs from 0.1443 by more than 1.5× in either direction, §38d's
> claim that "the conclusion survives any plausible ATR" must be restated with the measured
> number**, and the pre-screen's 5m row stops being an extrapolation.

**D4 — KILL RULE.** If fewer than **25 of the 40** deployed symbols have usable 5m coverage
in the window, the run reports **BLOCKED** and no ratio is published. A median over a
surviving subset that is systematically the *old* symbols is not the deployed universe's
number, and §17's positive-control discipline applies: if the surviving set is skewed
towards majors, say so and do not generalise.

**D5 — WHAT HAPPENS IF IT OPENS. Written now, so it cannot be written later.**
> **An OPEN verdict is NOT a mandate to build a 5m strategy.** If F-1 opens the family, the
> next step is the §15c-5 **free gate** — first-principal-component loading and a net
> long-short leg, judged by regression, on price data alone, before any backtest. A family
> that clears the cost bar still has to clear the factor gate, and §15c measured that the
> crypto cross-section is one factor at **every** horizon.
>
> **This preregistration does not authorise a 5m backtest.** If F-1 opens the family, that
> is a decision for a later round with its own preregistration.

## 4. Cost and blast radius of this round

* **Download:** 5m monthly zips are ~0.4 MB per symbol-month. 40 symbols × 13 months
  ≈ **210 MB**. Nothing else in the repo is touched.
* **Compute:** 40 × 13 × 8,928 bars ≈ 4.6 M rows, read one symbol at a time, under the
  standing **4 GB** cap.
* **What is NOT touched:** the deployed strategy, the config, the whitelist, the risk level,
  the 4h book, and every number in `HOW_TO_RUN` §4.

## 5. What would make me wrong

* The measured `r` could exceed 0.205, which would open the family. The pre-registered
  response is D5: **it does not authorise building anything.**
* The 5m/4h scaling could be non-monotonic in a way that makes a single ratio misleading.
  The regime split in D2 is there to expose exactly that, and the tool prints the ratio for
  each regime rather than one number.
* The surviving 25+ symbols could be unrepresentative. D4 handles the size of the problem;
  **representativeness is reported, not assumed away.**
