"""
E#6 -- pre-registration: MOMENTUM on the LIQUID universe.

This is the one cell of the cross-sectional grid this project has never run.

E#3 ran momentum on the 200 OLDEST-listed perpetuals, because that maximises
usable history. It found no rank power at all (IC +0.005 / -0.009 / +0.006 /
-0.000 at 3/6/12/24-week formation, every |t| < 0.8). That is consistent with
Fieberg et al., who state the effect "originates mainly from the biggest and
most liquid cryptocurrencies" -- E#3 tested the universe where they report it
weakest.

E#5 measured the actual taker round trip on those liquid names: 3.1 bps at
$10k, 7.7 at $50k, 18.4 at $250k, 38.0 at $1M, before fees. Fieberg's claimed
breakeven is 1.25%. So liquidity is where the effect is claimed to be AND
where it is affordable.

Written before any result. Nothing here may be tuned afterwards.

------------------------------------------------------------------------------
WHY THIS IS A NEW EXPERIMENT AND NOT A REPEAT OF E#3
------------------------------------------------------------------------------
Different universe, and the difference is the entire point:

    E#3   200 oldest-listed perps, ~16m USD median daily quote volume
    E#6   50 most liquid perps,   ~91m USD median daily quote volume

E#3's FAIL is a statement about the long tail. It is not a statement about
liquidity, and it must not be quoted as one.

------------------------------------------------------------------------------
PRIMARY SOURCE
------------------------------------------------------------------------------
Fieberg, Liedtke, Poddig, Walker & Zaremba, "A Trend Factor for the Cross
Section of Cryptocurrency Returns", JFQA 60(7), 3116-3153 (2025),
doi 10.1017/S0022109024000747. Verified via Crossref/OpenAlex and read from
the open-access PDF.

Table 8, Panel B (most liquid, Top100), weekly rebalance, H-L gross:
    3.30 %/wk  (t = 4.36)
    against the LTW 3-factor model: 2.28 %/wk  (t = 3.62)
Table 9, Panel B (largest 100), net of costs:
    30bp long / 40bp short : 2.45 %/wk  (t = 3.22)
    breakeven cost 1.25 %; breakeven-5%-significance 0.70 %
    turnover 68.21 %/wk
The paper states the effect remains significant with holding periods up to
~4 weeks.

------------------------------------------------------------------------------
PRE-REGISTERED SPECIFICATION -- fixed in advance
------------------------------------------------------------------------------
Universe      top 50 USD-M perpetuals by MEDIAN DAILY QUOTE VOLUME over the
              full sample. Chosen by COST, not by signal: this is where
              measure_cost.py returned the lowest round trip. Any symbol with a
              single-day return below -90% is excluded before the test, not
              after it (G7).
Interval      daily bars, weekly rebalance (last observation of each ISO week)
Formation     3 / 6 / 12 / 24-week trailing returns, cross-sectionally
              ranked and averaged into one trend score. IDENTICAL to E#3's
              construction, so the universe is the only thing that changes.
              Price only; volume indicators are NOT included, because
              including them would be a second change.
Direction     LONG high trend / SHORT low trend. Fixed by the source paper's
              reported sign. NOT a parameter. (E#4 found the OPPOSITE sign in
              the long tail; that is a different universe and does not license
              flipping this one -- if the sign comes out negative here, that is
              a result, not an invitation to flip.)
Portfolio     long top quintile, short bottom quintile, equal weight,
              dollar-neutral
Cost          MEASURED, not assumed. Base case: the measured book cost for
              the book size actually used, plus 5 bps per side (VIP0 USD-M
              taker). The full cost frontier is published at every size from
              $10k to $1M per name, and the sign of the result at each is
              reported. No size is selected after the fact.
Book size     $10,000 per name => $500,000 total. FIXED IN ADVANCE as the
              headline case, chosen because it is the cheapest measured point
              and therefore the least favourable to a null. The frontier is
              published alongside.
Causality     signal formed at the close of week t, position earns the return
              from t to t+1. A truncation assertion runs before any number is
              produced (see e3_backtest.py::causality_check).
Survivorship  disclosed, not corrected. This is a survivor universe and the
              effect of that on a LONG-momentum strategy is to flatter it.
              That is stated next to the result, not buried.

------------------------------------------------------------------------------
GATES -- all pre-registered
------------------------------------------------------------------------------
  G1  net expectancy > 0 at the measured base cost
  G2  net expectancy > 0 at 2x that cost
  G3  |t| >= 2.0 on a dependence-adjusted statistic
  G4  annualised net Sharpe >= 0.95   (the corrected pre-registered bar;
      the search-time benchmark of E[max of N] does NOT apply to a single
      pre-registered rule)
  G5  positive in >= 60% of yearly subperiods
  G6  positive in >= 60% of symbols, and no single symbol contributes
      more than 35% of total profit
  G7  no rebased/dead names anywhere in the traded book

------------------------------------------------------------------------------
WHAT WOULD FALSIFY IT
------------------------------------------------------------------------------
A clean null. Fieberg is a 2015-2022 spot study on the largest coins; this is
2020-2026 perps on the top 50 by volume. A null here would not refute the
paper -- it would say the effect does not survive the venue, the instrument and
the post-2022 period. That is a real and useful finding, and it is the reason
this experiment is worth running rather than assuming the paper transfers.

If it fails, the correct action is to report the null. E#3 already failed, and
E#4 already succeeded, on a different universe; a third result that differs by
universe is the expected shape of the truth, not a surprise to be tuned away.

------------------------------------------------------------------------------
FORBIDDEN
------------------------------------------------------------------------------
  parameter tuning of any kind
  formation-window selection after seeing results
  flipping the sign after seeing results
  universe selection by anything other than median daily quote volume
  reporting an information coefficient without net return in the same breath
  quoting E#3's FAIL as evidence about liquid coins
"""

from __future__ import annotations

SPEC = {
    "experiment": "E#6",
    "version": "E6-momentum-liquid-2026-09-26",
    "written_utc": "2026-09-26",
    "question": "Does cross-sectional momentum work on the LIQUID perpetual universe?",
    "why_new": "E#3 ran momentum on the 200 oldest-listed perps (~16m USD median "
               "daily quote volume) and found no rank power. Fieberg et al. "
               "state the effect originates mainly in the biggest and most liquid "
               "coins. E#6 runs the same construction on the universe where the "
               "paper claims the effect is strongest AND where the measured cost "
               "is lowest.",
    "source": {
        "citation": "Fieberg, Liedtke, Poddig, Walker & Zaremba, A Trend Factor "
                    "for the Cross Section of Cryptocurrency Returns",
        "journal": "JFQA 60(7) 3116-3153",
        "doi": "10.1017/S0022109024000747",
        "reported_liquid_h_minus_l_gross_pct_per_week": 3.30,
        "reported_liquid_h_minus_l_t": 4.36,
        "reported_largest100_net_of_30_40bp_pct_per_week": 2.45,
        "reported_largest100_net_t": 3.22,
        "reported_breakeven_cost_pct": 1.25,
        "reported_breakeven_cost_significance_5pct_pct": 0.70,
    },
    "universe": "top 50 USD-M perpetuals by median daily quote volume",
    "rebalance": "weekly, last observation of each ISO week",
    "formation_weeks": [3, 6, 12, 24],
    "features": "price only, identical construction to E#3",
    "direction": "long high trend, short low trend (fixed by the source)",
    "portfolio": "long top quintile / short bottom quintile, equal weight, dollar-neutral",
    "book_size_per_name_usd": 10_000,
    "total_book_usd": 500_000,
    "cost": {
        "basis": "MEASURED book cost + 5 bps per side VIP0 taker",
        "measured_rt_bps": {"10000": 3.1, "50000": 7.7, "250000": 18.4, "1000000": 38.0},
        "frontier_published": [10_000, 50_000, 250_000, 1_000_000],
    },
    "gates": {
        "G1_net_positive_base_cost": True,
        "G2_net_positive_2x_cost": True,
        "G3_abs_t_at_least": 2.0,
        "G4_annualised_net_sharpe_at_least": 0.95,
        "G5_positive_year_fraction_at_least": 0.60,
        "G6_positive_symbol_fraction_at_least": 0.60,
        "G6b_max_symbol_profit_share_at_most": 0.35,
        "G7_no_rebased_names": True,
    },
    "forbidden": [
        "parameter tuning of any kind",
        "formation-window selection after seeing results",
        "flipping the sign after seeing results",
        "universe selection by anything but median daily quote volume",
        "quoting E#3's FAIL as evidence about liquid coins",
    ],
    "stopping_rule": "run once; if it fails, report the null",
}
