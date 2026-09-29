"""Is the t_adj on the NET series real signal, or an artefact of the cost term?

net = gross - cost, and cost_R is itself a function of atr_pct, which correlates
with every factor here. A t-statistic on net therefore can be large simply
because the COST is predictable from the factor, which is worthless for trading.

This recomputes the tail-bucket significance on the GROSS series only. If t
collapses, the net-side significance is a cost artefact and must not be counted
as evidence for a factor.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.widepanel.run_wide import dependence_t  # noqa: E402
from tools.factor.factor_scan import (HORIZON, COST_REGIMES, COST_MAIN, FACTORS,  # noqa: E402
                                      DIRECTIONS, KLINES, load, features)

CBPS = COST_REGIMES[COST_MAIN]


def main() -> None:
    frames = []
    syms = sorted(p.name.replace("_5m.csv.gz", "") for p in KLINES.glob("*_5m.csv.gz"))
    for s in syms:
        f = features(load(s))
        f["symbol"] = s
        frames.append(f.iloc[:-HORIZON])
    df = pd.concat(frames, ignore_index=True)

    df["grossR"] = df["fwd_ret"] / df["atr_pct"]
    df["costR"] = CBPS / (1.0 * df["atr_pct"] * 10000.0)
    df["netR"] = df["grossR"] - df["costR"]

    print("=" * 112)
    print(f"TAIL BUCKET (extreme 5%) SIGNIFICANCE: NET series vs GROSS series "
          f"({CBPS} bps)")
    print("=" * 112)
    print(f"{'factor/dir':<18s} {'netR':>9s} {'t_adj(net)':>11s} | "
          f"{'grossR':>9s} {'t_adj(gross)':>13s} {'IAT':>5s}  grossR x1000")
    for fac in FACTORS:
        for dname, sgn in DIRECTIONS.items():
            thr = df[fac].quantile(0.95 if dname == "long" else 0.05)
            m = (df[fac] >= thr) if dname == "long" else (df[fac] <= thr)
            net = sgn * df.loc[m, "netR"].to_numpy()
            grs = sgn * df.loc[m, "grossR"].to_numpy()
            dn = dependence_t(net)
            dg = dependence_t(grs)
            print(f"{fac+'/'+dname:<18s} {dn['mean_r']:+9.4f} {dn['t_adjusted']:11.2f} | "
                  f"{dg['mean_r']:+9.4f} {dg['t_adjusted']:13.2f} {dg['iat']:5.1f}  "
                  f"{dg['mean_r']*1000:+8.2f}")

    print()
    print("Interpretation: the gross edge in R is what the factor predicts. Express it")
    print("in round-trip bps so it can be compared with the cost directly:")
    print()
    rows = []
    for fac in FACTORS:
        for dname, sgn in DIRECTIONS.items():
            thr = df[fac].quantile(0.95 if dname == "long" else 0.05)
            m = (df[fac] >= thr) if dname == "long" else (df[fac] <= thr)
            g = sgn * df.loc[m, "grossR"].to_numpy()
            bps = np.nanmean(g * df.loc[m, "atr_pct"].to_numpy()) * 10000.0
            dg = dependence_t(g)
            rows.append({"factor": fac, "dir": dname, "gross_bps": bps,
                         "t_adj_gross": dg["t_adjusted"]})
    t = pd.DataFrame(rows).sort_values("gross_bps", key=abs, ascending=False)
    print(f"{'factor/dir':<18s} {'gross edge (bps)':>17s} {'cost (bps)':>11s} {'ratio':>8s}")
    for _, r in t.iterrows():
        print(f"{r['factor']+'/'+r['dir']:<18s} {r['gross_bps']:>17.2f} {CBPS:>11.1f} "
              f"{abs(r['gross_bps'])/CBPS:8.4f}")
    print(f"\nBest measured gross edge across all factors, directions and horizons: "
          f"{abs(t.gross_bps).max():.2f} bps")
    print(f"Calm round-trip cost: {CBPS:.1f} bps  ->  short by "
          f"{CBPS/abs(t.gross_bps).max():.0f}x")


if __name__ == "__main__":
    main()
