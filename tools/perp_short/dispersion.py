"""Is the 6.8-year power requirement intrinsic, or is it a few symbols?

`forward_power.py` concluded that a forward test of the N=50 book reaching
t >= 2.0 under the IAT treatment needs ~6.8 years, because sd(R) = 2.77 against
a mean of 0.21. The paper's most important sentence is in the previous result:
**the market-neutralised excess is NEGATIVE at every rung that clears the bar**,
i.e. the signalling symbol falls less than the panel.

If the dispersion is cross-sectional - a handful of symbols bleeding out while the
rest behave - then the power problem is a UNIVERSE problem, and the honest
question becomes whether a per-symbol quality screen is defensible or is just
selection wearing a risk-control costume. If the dispersion is spread evenly,
6.8 years is intrinsic and the line simply cannot be settled in this project.

This measures it, and it also reports the tail explicitly rather than letting a
single sigma stand in for a distribution.

Run:
    $env:PERP_SHORT_DATADIR="user_data/data/wide526"
    .venv\\Scripts\\python.exe tools\\perp_short\\dispersion.py
"""

from __future__ import annotations

import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join("tools", "perp_short"))

import r_stats  # noqa: E402

STRAT = "PerpShort4hDeploy"


def main() -> int:
    ap = max(glob.glob("user_data/lshape_out/n50/*.zip"), key=os.path.getmtime)
    trades = sorted(r_stats.load_trades(ap, strategy=STRAT),
                    key=lambda t: t["open_date"])
    frames = r_stats.load_frames(sorted({t["pair"] for t in trades}))
    df = r_stats.build(trades, frames, 5.0, 34.9)
    r = df["R"].to_numpy()
    print(f"N=50, {len(r)} trades, mean R {r.mean():+.4f}, sd {r.std(ddof=1):.4f}\n")

    print("=== THE TAIL, EXPLICITLY ===")
    qs = [0.001, 0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]
    print("   " + "  ".join(f"p{q*100:g}%={np.quantile(r, q):+.2f}" for q in qs))
    print(f"   min {r.min():+.2f}   max {r.max():+.2f}   "
          f"skew {float(pd.Series(r).skew()):+.2f}   "
          f"kurtosis {float(pd.Series(r).kurt()):+.2f}")
    print(f"   trades below -1.5R: {(r < -1.5).sum()} ({(r < -1.5).mean()*100:.1f}%)")
    print(f"   trades below -3R  : {(r < -3).sum()} ({(r < -3).mean()*100:.1f}%)")
    print("   (a 4.0xATR stop should cap a loss near -1R, so anything past that is")
    print("    a gap or a normalised-ATR artefact - worth knowing which)")

    print("\n=== IS THE DISPERSION CROSS-SECTIONAL? ===")
    per = df.groupby("pair")["R"].agg(["count", "mean", "std"])
    per = per[per["count"] >= 3].sort_values("mean")
    print(f"   symbols with >=3 trades: {len(per)}")
    print(f"   mean R per symbol: worst {per['mean'].min():+.3f}  "
          f"median {per['mean'].median():+.3f}  best {per['mean'].max():+.3f}")
    print(f"   symbols with NEGATIVE mean R: {(per['mean'] < 0).sum()} "
          f"({(per['mean'] < 0).mean()*100:.0f}%)")
    print("\n   worst 10 symbols:")
    print(per.head(10)[["count", "mean", "std"]].to_string())

    print("\n=== HOW MUCH OF THE TAIL DO THEY OWN? ===")
    sym_r = df.groupby("pair")["R"].sum().sort_values()
    k = 10
    print(f"   the {k} worst symbols contribute "
          f"{sym_r.head(k).sum()/r.sum()*100:.1f}% of the TOTAL R "
          f"({sym_r.head(k).sum():+.1f} against {r.sum():+.1f})")
    drop = df[~df["pair"].isin(sym_r.head(k).index)]["R"].to_numpy()
    print(f"   excluding them: {len(drop)} trades, mean R {drop.mean():+.4f}, "
          f"sd {drop.std(ddof=1):.4f}  (was {r.mean():+.4f} / {r.std(ddof=1):.4f})")
    idx = df[~df["pair"].isin(sym_r.head(k).index)]
    iat2 = r_stats.iat(idx.groupby(pd.to_datetime(idx["open"], utc=True))["R"]
                        .mean().to_numpy())
    n_drop = (2.0 * drop.std(ddof=1) / drop.mean()) ** 2 * iat2
    print(f"   -> a forward test would need {n_drop:,.0f} trades instead of "
          f"{(2.0*r.std(ddof=1)/r.mean())**2*r_stats.iat(df.groupby(pd.to_datetime(df['open'], utc=True))['R'].mean().to_numpy()):,.0f}"
          f"  ({n_drop/250:.1f} years at 250/yr instead of 6.8)")

    print("\n=== AND THE PART THAT MATTERS MORE THAN THE POWER NUMBER ===")
    print("   A per-symbol screen is not a risk control. It is a universe choice,")
    print("   and the ranking would be computed on the same 3.4 years the result")
    print("   is measured on. That is the minimum-of-N construction this project")
    print("   exists to refuse - it is how a -0.55R book becomes a +0.60R one")
    print("   without anything about the market changing.")
    print("   So the number above is reported as DIAGNOSTIC, and the screen is NOT")
    print("   built. The honest position on the 6.8 years is that it is intrinsic")
    print("   to a book whose dispersion is cross-sectional, and that removing the")
    print("   dispersion would require selecting the universe on the outcome.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
