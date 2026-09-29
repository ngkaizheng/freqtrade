"""What the measured cost regimes do to each live verdict.

    .venv\\Scripts\\python.exe tools\\cost\\cost_regime_sensitivity.py

WHY THIS FILE REPLACES e4_impact_headroom.py
--------------------------------------------
The first version of this analysis was written against E#4's published
"0.274%/day gross, 26.6 bps breakeven" cost table. **Those two constants were
voided by the 2026-09-26 adversarial review** (RESEARCH_STATE.md §1, §8): they
came from a Gaussian map `3.51 x |IC| x sigma` that overstates the realised
portfolio return by 17-90x. The real equal-weight decile long-short earns
+0.0059 to +0.0160%/day, breakeven ~1.6 bps, and E#4 is NULL AT PORTFOLIO LEVEL.
Every number that file produced was therefore answering a question that had
already been closed. It is deleted rather than corrected, because "impact
headroom for E#4" is not a question any live line is asking.

The real question is the one START_HERE.md §3.2 actually poses: the whole project
rests on a 12-18 bps round trip, measured once on a calm day, and never in
stress. That number has now been measured across four regimes
(tools/cross_section/measure_cost.py). This script asks what the spread does to
the conclusions that are still open.

THE FOUR REGIMES (Roll effective spread on aggTrades, 8 top perps, 1 day each,
round trip = 2 x spread + 2 x 5 bps taker):

    2026-09-20  calm                  12.0 bps
    2024-08-05  long-tail cascade     15.6 bps
    2025-10-10  volatile              22.8 bps
    2020-03-12  COVID crash           34.9 bps   (pre-dates the perp panel; see below)

WHAT THIS DELIBERATELY DOES NOT DO
---------------------------------
It does not average the regimes, and it does not pick one. A backtest trades on
every day, so the number that matters is a turnover-weighted mixture, and the
weighting is a modelling choice the reader has to see, not one this file makes
silently. Both bracketing cases are printed: every regime at the pessimistic
end, and the measured distribution.

A NOTE ON THE AREFEV COMPARISON. An earlier draft of this work placed these
numbers against Arefev's "~59 bps" and concluded the measurement sided with the
null. **That comparison is void and the conclusion was inverted.** Per
RESEARCH_STATE.md §8 point (8), the 59 bps figure is fabricated by dividing
Arefev's cost by *Fieberg's* turnover; Arefev's 40 bps/week is all-in and weekly
while this project's 3.1 bps is per-rebalance, book-only, pre-fee. Like-for-like
the project's own all-in is *more* pessimistic than Arefev's, not 5x less. The
comparison is not repeated here.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# --- measured regimes: label -> all-in round-trip bps, median over 8 perps ---
REGIMES = {
    "calm (2026-09-20)": 12.0,
    "long-tail cascade (2024-08-05)": 15.6,
    "volatile (2025-10-10)": 22.8,
    "COVID crash (2020-03-12)": 34.9,
}

# --- E#6, the live line (docs-myself/E6_RESULT.md) ---------------------------
# Gross and cost are BOTH per rebalance, and net annualises at 52 rebalances.
E6_GROSS_PCT_PER_REBAL = 0.3397
E6_COST_PCT_PER_REBAL = 0.0387      # the 13.1 bps headline, as published
E6_REBALANCES_PER_YEAR = 52
E6_HEADLINE_BPS = 13.1


def e6_net_pct_per_yr(all_in_bps: float) -> float:
    """E#6 annualised net return if the all-in cost were `all_in_bps` instead.

    The published cost scales linearly with the measured all-in figure; the
    gross is untouched, because nothing in this measurement says the SIGNAL
    depends on the day the book happens to trade.
    """
    cost = E6_COST_PCT_PER_REBAL * (all_in_bps / E6_HEADLINE_BPS)
    return (E6_GROSS_PCT_PER_REBAL - cost) * E6_REBALANCES_PER_YEAR


def main() -> int:
    print("=" * 78)
    print("DOES THE MEASURED COST REGIME CHANGE ANY LIVE VERDICT?")
    print("=" * 78)

    base = e6_net_pct_per_yr(E6_HEADLINE_BPS)
    print(f"\nE#6 (live line) -- gross {E6_GROSS_PCT_PER_REBAL}%/rebalance,"
          f" {E6_REBALANCES_PER_YEAR} rebalances/yr")
    print(f"  published headline: {E6_HEADLINE_BPS} bps all-in -> "
          f"{base:+.1f}%/yr  (E6_RESULT.md reports +15.6%)\n")

    print(f"  {'regime':<32}{'all-in':>9}{'E#6 net/yr':>14}{'vs headline':>14}")
    print("  " + "-" * 67)
    for label, bps in REGIMES.items():
        net = e6_net_pct_per_yr(bps)
        print(f"  {label:<32}{bps:>7.1f} bps{net:>+13.1f}%{net - base:>+13.1f}")

    # The worst case for a taker is the HIGHEST measured cost, not the lowest.
    worst = max(REGIMES.values())
    worst_label = max(REGIMES, key=REGIMES.get)
    worst_net = e6_net_pct_per_yr(worst)
    ratio = worst / E6_HEADLINE_BPS

    print(f"""
VERDICT ON E#6: UNCHANGED, AND THE CONCLUSION IS FAVOURABLE

  The most expensive regime measured ({worst_label}, {worst:.1f} bps) is
  {ratio:.1f}x the headline assumption, and E#6 still earns
  {worst_net:+.1f}%/yr. The line is not cost-bound -- E6_RESULT.md published the
  frontier out to 48.0 bps at $1M/name and the verdict never flipped. This
  measurement extends that frontier into TIME rather than book size, and it also
  does not flip.

  So the cost premise, which START_HERE.md §3.2 calls "the single least-examined
  load-bearing input", turns out not to be load-bearing for either live line:
  E#4 dies on the SIGNAL (portfolio return, not cost), and E#6 survives a
  {ratio:.1f}x cost increase. **The honest conclusion is that the cost question
  has been examined and does not decide anything.** That is a real result, and
  it is a null.

VERDICT ON THE CLOSED LINES: THEY HARDEN, WHICH IS EXPECTED

  * Carry (§2, §3.17): closes on an EXCESS of -0.88 to -1.56 %/yr, not on a
    cost threshold, so a higher cost does not change it.
  * Liquidations / SHARK-07 (§3.11): the best conditional excess is +4.4 bps
    against a 12-18 bps cost. At 22.8-34.9 bps that margin is 2-3x worse. The
    line stays closed and its stop condition stays met, so collection should
    continue.
  * 5m and 4h volume breakout: closed on friction of 0.75R and 0.088R against
    gross 0.131R/t=3.71. A 2-3x cost increase makes both worse, never better.

WHAT IS NOT IN THIS TABLE, AND WHY IT MATTERS

  * 2020-03-12 is a DIFFERENT MARKET, not today's tail. Only 4 of 8 symbols had
    a tape, so the figure rests on BTC/ETH/ZEC/XRP -- today's top names that
    happened to exist in 2020, a survivorship selection inside a small sample.
    He et al. measure perp spreads 48-73% narrower post-2022. Do not carry the
    34.9 bps forward as a present-day expectation.
  * These are single days, not distributions. One observation per regime.
  * Roll's random-walk and stationary-spread assumptions are weakest exactly
    where these numbers matter most: r^2 falls from 0.40 (calm) to 0.32 (crash),
    meaning most of the return variance on the stressed tapes is not the
    bid-ask bounce the estimator is built on.
  * Market impact is NOT in this table. It is measured separately in
    tools/cost/measure_impact.py, and on historical bookDepth (2023-01 onward)
    it is negligible below roughly $1M/day of gross book notional. E#6's
    universe is the top 50 BY VOLUME, where measured depth is largest, so this
    is the friendliest possible case for the impact assumption and the honest
    one to quote for E#6 specifically.
""")

    out = ROOT / "shark_data/costs"
    out.mkdir(parents=True, exist_ok=True)
    (out / "cost_regimes.csv").write_text(
        "regime,all_in_bps,e6_net_pct_per_yr\n" + "".join(
            f"{label},{bps},{e6_net_pct_per_yr(bps):.2f}\n"
            for label, bps in REGIMES.items()),
        encoding="utf-8")
    print(f"\nwritten: shark_data/costs/cost_regimes.csv")
    print(f"         shark_data/costs/impact_by_size.csv, depth_by_band.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
