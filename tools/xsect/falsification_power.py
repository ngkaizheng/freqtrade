"""
Power analysis for the cross-sectional crypto-perp FALSIFICATION test.

AGENTS.md 1a: "Before proposing a test, a forward period, or a data-collection
effort, check that the available data could produce a verdict at all. Compute
the sample size the measurement requires and compare it with what the design
generates."

This script answers one question: given a weekly-rebalanced long-short
cross-section over a perp panel, what net annualised Sharpe is detectable at
what power, and does the panel supply enough rebalances?

Conventions
-----------
* ONE observation per rebalance. Not one per symbol. (RESEARCH_STATE.md 3.5)
* t-statistic of a mean = SR_period * sqrt(N_eff). SR_period is the
  per-rebalance (here: per-week) Sharpe, i.e. annualised / sqrt(52).
* IAT deflation: the per-rebalance return series is serially dependent. We
  report power both at IAT=1 (iid) and at IAT=2 (mild weekly autocorrelation,
  which the repo has measured repeatedly on crypto return series).
* t critical values are two-sided, computed from the normal approximation to
  the t distribution (N_eff >= 30, so this is accurate).

Run:  .venv\\Scripts\\python.exe tools/xsect/falsification_power.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Weeks available for a Binance USD-M perp cross-section, by panel vintage.
# BTCUSDT perp: 2019-09. Most liquid alts: 2020-2021. A stable top-100 panel
# with continuous history is realistically 2021-01 onward.
PANELS = {
    "3y weekly (the repo's stated test)": 3 * 52,
    "4y weekly": 4 * 52,
    "5y weekly (2021-09 -> 2026-09)": 5 * 52,
    "6.5y weekly (2020-03 -> 2026-09)": int(6.5 * 52),
}

# Published reference points. Sources in docs-myself/XSECT_REVIEW_2026-09-26.md
PUBLISHED = {
    "Fieberg et al. (JFQA 2025) CTREND, full universe, GROSS": 1.94,
    "Fieberg et al. CTREND, net of 30/40bp, top-100": 1.45,
    "Fieberg et al. CTREND, MEDIAN of 55,296 designs": 1.34,
    "Fieberg et al. CTREND, MEDIAN with validation sample": 1.19,
    "Fieberg et al. CMOM (plain cross-sec momentum), MEDIAN": 0.83,
    "Ammann et al. 1-wk momentum, value-weighted, surviving": 0.06,
}


def t_crit(df: float, two_sided_alpha: float = 0.05) -> float:
    """Two-sided t critical value. Normal approximation, refined by a small
    Cornish-Fisher term so N_eff=30..60 is not materially off."""
    z = {0.05: 1.959963985, 0.10: 1.644853627}[two_sided_alpha]
    if df > 1000:
        return z
    # Cornish-Fisher expansion for the t quantile
    g1 = (z**3 + z) / 4.0
    g2 = (5 * z**5 + 16 * z**3 + 3 * z) / 96.0
    g3 = (3 * z**7 + 19 * z**5 + 17 * z**3 - 15 * z) / 384.0
    return z + g1 / df + g2 / df**2 + g3 / df**3


@dataclass(frozen=True)
class PowerRow:
    n_raw: int
    iat: float
    n_eff: float
    df: float
    t_sig: float          # |t| needed to reject at 5% two-sided
    sr_annual_sig: float  # annualised Sharpe that just reaches significance
    sr_annual_80: float   # annualised Sharpe with 80% power at 5%
    sr_annual_90: float   # annualised Sharpe with 90% power at 5%


def power_table(n_raw: int, iat: float, alpha: float = 0.05) -> PowerRow:
    n_eff = n_raw / iat
    df = n_eff - 1
    t_sig = t_crit(df, alpha)
    # For 80% power at 5% two-sided, the alternative must clear
    # t_crit + t_crit(0.80) where t_crit(0.80) ~ 0.8416 one-sided.
    t80 = t_sig + 0.8416212335729143
    t90 = t_sig + 1.2815515655446004
    scale = math.sqrt(52) / math.sqrt(n_eff)
    return PowerRow(
        n_raw, iat, n_eff, df,
        t_sig, t_sig * scale, t80 * scale, t90 * scale,
    )


def main() -> None:
    print(__doc__)
    print("=" * 78)
    print("PART 1 -- MINIMUM DETECTABLE SHARPE, BY PANEL LENGTH")
    print("=" * 78)
    print(
        f"{'panel':<34}{'wks':>5}{'N_eff':>8}{'SR@5%':>9}"
        f"{'SR@80%':>9}{'SR@90%':>9}"
    )
    print("-" * 78)
    for label, n in PANELS.items():
        for iat in (1.0, 2.0):
            r = power_table(n, iat)
            tag = "" if iat == 1.0 else "  (IAT=2)"
            print(
                f"{label + tag:<34}{r.n_raw:>5}{r.n_eff:>8.0f}"
                f"{r.sr_annual_sig:>9.3f}{r.sr_annual_80:>9.3f}"
                f"{r.sr_annual_90:>9.3f}"
            )
    print()
    print("SR@5%  = net annualised Sharpe that merely reaches p<0.05 (null rejected)")
    print("SR@80% = net annualised Sharpe detected with 80% power at p<0.05")
    print()

    print("=" * 78)
    print("PART 2 -- PUBLISHED BENCHMARKS AGAINST THAT POWER CURVE")
    print("=" * 78)
    for k, v in PUBLISHED.items():
        print(f"  {v:>6.2f}   {k}")
    print()

    print("=" * 78)
    print("PART 3 -- REQUIRED SAMPLE SIZE TO DETECT A GIVEN EFFECT")
    print("=" * 78)
    print("How many weekly rebalances to detect a given TRUE net annualised Sharpe")
    print("at 80% power, p<0.05 two-sided, IAT=2:")
    print()
    print(f"{'true SR':>9}{'weeks needed':>15}{'years':>9}{'at 5y panel?':>14}")
    print("-" * 78)
    n5y = PANELS["5y weekly (2021-09 -> 2026-09)"]
    for sr in (0.5, 0.79, 0.95, 1.19, 1.5, 2.0, 3.0):
        n_eff_needed = ((2 * 0.8416212335729143 + t_crit(1000)) / (sr / math.sqrt(52))) ** 2
        n_needed = n_eff_needed * 2.0
        print(
            f"{sr:>9.2f}{n_needed:>15.0f}{n_needed / 52:>9.1f}"
            f"{'YES' if n_needed <= n5y else 'NO':>14}"
        )
    print()

    print("=" * 78)
    print("PART 4 -- THE DECISION RULE, WITH ITS THREE BARS")
    print("=" * 78)
    print("The bar is computed at IAT=1, because the statistic is a Newey-West")
    print("HAC t, which already corrects for serial dependence in the weekly")
    print("rebalance series. Deflating again by IAT double-counts the")
    print("autocorrelation -- RESEARCH_STATE.md 3.1/3.2, a trap already paid.")
    print()
    for label, n in PANELS.items():
        a = power_table(n, 1.0)
        b = power_table(n, 2.0)
        print(
            f"  {label:<32} KILL bar @5%   IAT=1 {a.sr_annual_sig:.2f}"
            f"   IAT=2 {b.sr_annual_sig:.2f}"
        )
    print()
    n3y = PANELS["3y weekly (the repo's stated test)"]
    r1 = power_table(n5y, 1.0)
    r3 = power_table(n3y, 1.0)
    med = PUBLISHED["Fieberg et al. CTREND, MEDIAN with validation sample"]
    haircut = 0.42  # McLean & Pontiff: 58% post-publication decline
    print(f"  3y weekly panel -> KILL bar {r3.sr_annual_sig:.2f} at 95% confidence,")
    print(f"                    {power_table(n3y, 1.0, 0.10).sr_annual_sig:.2f} at 90% confidence")
    print("                    (the repo's internal 0.95 is the 90% figure:")
    print("                     1.645/sqrt(156)*sqrt(52) = 0.950)")
    print(f"  5y weekly panel -> KILL bar {r1.sr_annual_sig:.2f} at 95% confidence,")
    print(f"                    {power_table(n5y, 1.0, 0.10).sr_annual_sig:.2f} at 90% confidence")
    print("                    (use ALL available history, not 3y)")
    print()
    print(f"  BAR 1   KILL      lower 95% bound on net annualised SR <= "
          f"{r1.sr_annual_sig:.2f}")
    print("                      (= cannot rule out zero after costs. STOP.)")
    print(f"  BAR 2   DECAY     point estimate < {med * haircut:.2f}")
    print(f"                      (= below the published median {med:.2f} after a 58%")
    print("                       post-publication haircut, McLean & Pontiff 2016.)")
    print("                       Below this a real effect is not worth trading.")
    print(f"  PROCEED           point estimate >= {med:.2f} net annualised AND")
    print(f"                      lower 95% bound > {r1.sr_annual_sig:.2f}")
    print()
    print(f"Sanity: on a 5y weekly panel the test resolves SR={r1.sr_annual_80:.2f}")
    print(f"at 80% power. The published net result is about "
          f"{PUBLISHED['Fieberg et al. CTREND, net of 30/40bp, top-100']:.2f}, so")
    print("the test is ~80% powered to detect exactly the effect the")
    print("literature claims. That is the correct calibration for a KILL test.")
    print()
    print("Why this is NOT the underpowered test that closed prior lines: you")
    print("are not searching for a marginal edge, you are testing for the")
    print("EXISTENCE of a LARGE already-published edge. A test that resolves")
    print(f"SR={r1.sr_annual_sig:.2f} at 5% is decisive when the hypothesis is")
    print("'Sharpe ~1.5' or 'Sharpe ~0'. The awkward middle is real, but the")
    print("CONFIDENCE INTERVAL resolves it; the point estimate alone does not.")
    print()
    print("=" * 78)
    print("PART 5 -- WHY 'DAILY' IS NOT THE RIGHT CADENCE (cost arithmetic)")
    print("=" * 78)
    rt_bps = {"BTC": 12, "alt": 18}
    weekly_to = 0.6846  # Fieberg et al. Table 9, CTREND weekly turnover
    for name, bps in rt_bps.items():
        for cad, mult in (("weekly", 1), ("daily", 5), ("4-hourly", 30)):
            to = min(1.0, weekly_to * mult)
            cost_pa = to * (bps / 10000.0) * 52 * 100.0  # %/yr
            print(
                f"  {name:<4} {cad:<9} turnover/period {to:>6.1%}"
                f"   drag {cost_pa:>5.2f}%/yr"
            )
    print()
    print("CTREND's breakeven cost is 1.41% and its 5%-significance cost is")
    print("0.88% PER TRADE -- enormous cushions, and 5-10x this repo's own")
    print("12-18bp perp round trip. A daily cadence therefore does NOT fail")
    print("because of fees. It fails because the signal itself is a REVERSAL")
    print("at that horizon: Fieberg et al. Table 2 gives sma_5d H-L = -2.90%/wk")
    print("(t = -3.35) and sma_20d = -3.13%/wk (t = -3.80).")
    print()


if __name__ == "__main__":
    main()
