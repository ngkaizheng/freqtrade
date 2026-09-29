"""
PRE-REGISTRATION — Experiment E#3: cross-sectional trend on a wide perp universe

Written BEFORE any result is computed on the new universe. That ordering is
the entire point: it is what makes the forward test a single pre-registered
test (benchmark 1.645) rather than another entry in a search (benchmark
E[max of N]). The 41,472-fold deflation this project has been carrying was
the reason the required Sharpe was overstated at 2.0-2.4; the correct bar for
a frozen, pre-registered rule on 3 years of weekly data is **0.95** net
annualised.

PRIMARY SOURCE
--------------
Fieberg, Liedtke, Poddig, Walker & Zaremba, "A Trend Factor for the Cross
Section of Cryptocurrency Returns", Journal of Financial and Quantitative
Analysis 60(7), 3116-3153 (2025), doi 10.1017/S0022109024000747. Verified
first-hand against Crossref and OpenAlex and read from the open-access PDF
(`tmp_audit/ctrend.pdf`, text in `tmp_audit/ctrend.txt`). 19 citations.

This is an IMPLEMENTATION OF A PUBLISHED FACTOR, not a discovery. The
hypothesis is not "does a crypto trend factor exist" -- the paper answers
that, at t = 3.22 net on the largest 100 coins. The hypothesis is that the
effect survives in this repository's instrument, universe and cost model.

WHAT THE PAPER REPORTS, for the case that matters here
------------------------------------------------------
Table 9, Panel B (largest 100 cryptocurrencies, weekly rebalance, H-L):
    gross                 3.40 %/wk   (t = 4.48)
    net @ 30bp long/40bp short   2.45 %/wk   (t = 3.22)
    net @ 40bp/50bp              2.17 %/wk   (t = 2.86)
    net @ 50bp/60bp              1.90 %/wk   (t = 2.50)
    turnover 68.21 %/wk; BETC 1.25 %; BETC-5% 0.70 %

Table 8, Panel B (most liquid), Top100: H-L 3.30 %/wk gross (t = 4.36);
against the LTW 3-factor model 2.28 %/wk (t = 3.62).

The paper states the effect "persists in big and liquid coins" and remains
significant with holding periods up to ~4 weeks. This repository's perp
round trip is 12-18 bps, i.e. **one third to one half** of the cost the paper
assumes, and its breakeven is 0.70-1.25 %.

PRE-REGISTERED DESIGN -- fixed in advance
-----------------------------------------
Universe     all USD-M perpetuals with a continuous daily history, as built
             by tools/universe/build_universe.py. Exclude any symbol whose
             history starts after the study start. Survivorship is a known,
             uncorrectable bias; it is disclosed, not corrected.
Interval     daily bars, weekly rebalance (last observation of each ISO week)
Formation    3 / 6 / 12 / 24 weeks of return, cross-sectionally ranked,
             averaged into a single trend score (the paper's aggregate
             characteristic). Volume is included as a second dimension only
             if the primary specification passes; the PRIMARY specification
             is price-only, because that is the version whose cost profile is
             cleanest.
Portfolio    long the top quintile, short the bottom quintile, equal weight,
             dollar-neutral, weekly rebalance.
Direction    long high trend / short low trend. This is fixed by the paper's
             reported sign and is NOT a free parameter.
Costs        0.16 % round trip per name (this repository's measured
             VIP0 figure: spot taker 0.10 % + USD-M taker 0.05 %, both legs).
             Charged on the name that changed. Also reported at 2x.
No           no parameter selection, no timeframe choice, no threshold
             tuning, no universe filtering beyond the history rule above.

PRIMARY MEASURE
---------------
Net return per rebalance in R, mean and t, with a Newey-West standard error
(weekly overlap makes naive errors optimistic) and the integrated
autocorrelation time reported alongside. R-multiples, never cash.

GATES -- all must pass, all pre-registered
-----------------------------------------
  G1  net expectancy > 0 at base cost
  G2  net expectancy > 0 at 2x cost
  G3  |t| >= 2.0 on the dependence-adjusted statistic
  G4  annualized net Sharpe >= 0.95      (the corrected pre-registered bar)
  G5  positive in at least 60 % of yearly subperiods
  G6  positive in at least 60 % of symbols traded, AND no single symbol
      contributes more than 35 % of total profit
  G7  the short leg is free of rebases: no symbol contributing to the short
      leg has a single-day return below -90 % (a dead or rebased token --
      found to be a systematic failure of this construction, see
      RESEARCH_STATE.md)

G7 IS A HARD GATE. The short side of a crypto momentum sort preferentially
selects dead and rebased tokens -- single days of -1,374 % have been observed
on this panel. A result that clears G1-G6 while failing G7 is void, not
"promising".

WHAT WOULD FALSIFY THIS
-----------------------
A clean null: the factor does not survive in perps at this cost, or its
sign flips, or it is carried by three symbols (G6), or by rebased names (G7).
Given a 3-year weekly horizon the test has 156 observations, so it can reach
G4 if the true net Sharpe is 0.95 and cannot if it is 0.4. That is a
meaningful test, and it is the test being registered.

WHAT THIS EXPERIMENT IS NOT
---------------------------
It is not a search. If it fails, the honest next step is to report the null
and to reconsider the construction -- not to vary the formation window until
something passes. The paper's own 79%-of-55,296 figure is the reason: that
construction is unusually robust, and this project must not discover that the
robustness is a mirage by trying fifty neighbours of it.
"""

from __future__ import annotations

REGISTRY_VERSION = "E#3-cross-sectional-trend-2026-09-26"

SPEC = {
    "experiment": "E#3",
    "version": REGISTRY_VERSION,
    "written_utc": "2026-09-26",
    "source": {
        "citation": "Fieberg, Liedtke, Poddig, Walker & Zaremba, "
                    "A Trend Factor for the Cross Section of Cryptocurrency Returns",
        "journal": "Journal of Financial and Quantitative Analysis 60(7) 3116-3153",
        "doi": "10.1017/S0022109024000747",
        "verified": "Crossref + OpenAlex metadata; open-access PDF read at "
                    "tmp_audit/ctrend.pdf",
        "citations_openalex": 19,
    },
    "universe": "all USD-M perpetuals with continuous daily history",
    "rebalance": "weekly, last observation of each ISO week",
    "formation_weeks": [3, 6, 12, 24],
    "features_primary": "price only (cross-sectionally ranked return, averaged)",
    "portfolio": "long top quintile / short bottom quintile, equal weight, dollar-neutral",
    "direction": "long high trend, short low trend (fixed by the source, not tuned)",
    "cost_round_trip": 0.0016,
    "stress_cost_round_trip": 0.0032,
    "measure": "net R per rebalance, Newey-West t, IAT reported",
    "gates": {
        "G1_net_positive_base": True,
        "G2_net_positive_2x_cost": True,
        "G3_abs_t_at_least": 2.0,
        "G4_annualised_net_sharpe_at_least": 0.95,
        "G5_positive_year_fraction_at_least": 0.60,
        "G6_positive_symbol_fraction_at_least": 0.60,
        "G6b_max_symbol_profit_share_at_most": 0.35,
        "G7_no_rebased_names_in_short_leg": True,
    },
    "forbidden": [
        "parameter tuning of any kind",
        "formation-window selection after seeing results",
        "universe filtering beyond the continuous-history rule",
        "reporting an IC without net R",
    ],
    "stopping_rule": "run once; if it fails, report the null. Do not rescue.",
}
