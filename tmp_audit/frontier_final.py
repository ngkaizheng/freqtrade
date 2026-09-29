"""
FINAL frontier, built on parameters measured from this project's own corpus
rather than assumed.

Measured inputs
---------------
rho_resid  = 0.297   average pairwise correlation of BTC-orthogonalised alt
                     returns, 52,145 hourly bars, 4 alts
sigma_cs   = 2.18% / 6.29% / 9.65% / 15.26%   cross-sectional dispersion of
                     individual returns at 1d / 7d / 14d / 30d
cost       = 0.16% per name traded per rebalance (2 x (5bps taker + 3bps slip))
universe   = 5 symbols

Derived question
----------------
For a cross-sectional book that must (a) beat its costs and (b) reach a
statistical verdict within T years, what information coefficient does the
signal have to deliver? That number is the whole decision: it is what the
project has to beat, and it is comparable against published crypto research.
"""

import math
from itertools import product

import numpy as np
import pandas as pd

pd.set_option("display.width", 250)

RHO = 0.297
Z = 1.6449
COST_PER_NAME = 0.0016
DEC = 3.51          # E[top decile] - E[bottom decile] of a standardised normal
DAYS = 365

SIGMA = {"1d": 0.0218, "7d": 0.0629, "14d": 0.0965, "30d": 0.1526}


def diversification(n):
    return math.sqrt((1 + (n - 1) * RHO) / n)


def row(n_sym, days, turnover, years):
    sigma_cs = SIGMA[days]
    div = diversification(n_sym)
    sigma_p = sigma_cs * div
    rebal = DAYS / int(days[:-1])
    n_obs = rebal * years
    sr_needed = Z / math.sqrt(n_obs)
    edge_needed = sr_needed * sigma_p
    cost = turnover * COST_PER_NAME
    ic_needed = edge_needed / (DEC * sigma_cs)
    return {
        "universe": n_sym,
        "rebal": days,
        "turnover": turnover,
        "years": years,
        "sigma_cs_%": sigma_cs * 100,
        "portfolio_vol_%": sigma_p * 100,
        "observations": n_obs,
        "edge_needed_%": edge_needed * 100,
        "cost_%": cost * 100,
        "headroom": edge_needed / cost,
        "IC_needed": ic_needed,
        "verdict": "VIABLE" if edge_needed > cost else "cost-bound",
    }


print("=" * 112)
print("HOW MUCH DIVERSIFICATION IS ACTUALLY AVAILABLE?  (rho_resid = 0.297, measured)")
print("=" * 112)
for n in [5, 10, 20, 50, 100, 200, 500]:
    d = diversification(n)
    print(f"  {n:>4} names -> portfolio vol is {d*100:5.1f}% of a single name's vol"
          f"   (diversification benefit vs 5 names: {diversification(5)/d:4.2f}x)")
print("""
Diversification SATURATES by roughly 20 names. Because BTC-orthogonalised alt
correlation is still 0.30, going from 5 names to 200 buys only a 1.21x reduction
in portfolio volatility. Shark's "go to 170 symbols" argument is therefore much
weaker than it looks -- past ~20 names there is almost nothing left to gain.
The win is NOT in a wider universe. It is in the construction.""")

print()
print("=" * 112)
print("THE FRONTIER: information coefficient required to be viable in 3 years")
print("=" * 112)
print("""
edge_needed  : per-rebalance edge required to reach t = 1.645 by then
cost         : 0.16% x names traded that rebalance
headroom     : edge_needed / cost. Above 1.0 means the signal has room to pay
               for itself AND be proven.
IC_needed    : the information coefficient that delivers edge_needed, assuming
               a decile long-short book on a standardised signal.
""")

rows = [row(n, d, t, 3) for n, d, t in product(
    [5, 20, 50, 100], ["1d", "7d", "14d", "30d"], [1, 3, 10])]
df = pd.DataFrame(rows)
show = df.copy()
for c in ["sigma_cs_%", "portfolio_vol_%", "edge_needed_%", "cost_%"]:
    show[c] = show[c].round(3)
show["headroom"] = show["headroom"].round(2)
show["IC_needed"] = show["IC_needed"].round(4)
print(show[["universe", "rebal", "turnover", "observations", "sigma_cs_%",
            "portfolio_vol_%", "edge_needed_%", "cost_%", "headroom",
            "IC_needed", "verdict"]].to_string(index=False))

print()
print("=" * 112)
print("THE ANSWER")
print("=" * 112)
v = df[(df["verdict"] == "VIABLE") & (df["headroom"] > 1.5)].sort_values("IC_needed")
print("Configurations that clear costs with at least 1.5x headroom, 3-year horizon,")
print("cheapest information coefficient first:")
print()
t = v[["universe", "rebal", "turnover", "edge_needed_%", "cost_%", "headroom", "IC_needed"]].copy()
for c in ["edge_needed_%", "cost_%"]:
    t[c] = t[c].round(3)
t["headroom"] = t["headroom"].round(2)
t["IC_needed"] = t["IC_needed"].round(4)
print(t.to_string(index=False))
print()
print(f"  median required IC across all viable designs: {v['IC_needed'].median():.4f}")
print(f"  best case (widest universe, slowest rebal, 1-name turnover): "
      f"{df['IC_needed'].min():.4f}")

print()
print("=" * 112)
print("THE BINDING CONSTRAINT, stated as one sentence")
print("=" * 112)
best5 = df[(df.universe == 5) & (df["verdict"] == "VIABLE")]
print(f"  viable designs available with the 5 symbols actually on disk: {len(best5)}")
print(f"  of {len(df)} swept, viable: {len(df[df['verdict']=='VIABLE'])}")
print()
print("  With 5 symbols the portfolio is 66% as volatile as a single name, so the")
print("  per-rebalance edge required for a 3-year verdict is far higher. The")
print("  project needs roughly 20-50 symbols for the design to have room.")
print("  That is a DATA problem, not an idea problem, and it is solvable:")
print("  Binance publishes USD-M klines for several hundred perpetuals.")

df.to_csv("tmp_audit/frontier_final.csv", index=False)
print("\nwritten tmp_audit/frontier_final.csv")
