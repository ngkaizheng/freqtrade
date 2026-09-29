"""Which N should actually be run? A robustness rule applied to PUBLISHED results.

WHY THIS IS NOT A NEW EXPERIMENT
---------------------------------
The ladder and both time windows are already computed and already published
(`WALKFORWARD_RESULT_2026-09-28.md`): naive t by rung, for DEVELOPMENT
(2023-01..2024-12) and OOS (2025-01..2026-08), all eleven rungs. This file
applies a decision rule to those numbers. **It runs no backtest and selects no
new parameter.**

**⚠ AND THE HONEST CAVEAT, STATED BEFORE THE NUMBERS ARE SHOWN: the rule below
is being applied AFTER both windows have been seen.** It is a standard robustness
criterion, not a pre-registered gate, and it must not be reported as one. What
makes it more than curve-fitting is that it is a MINIMAX rule - it optimises the
WORSE of the two windows rather than the average or the best - and the whole
point of the two-window split was to make that distinction available.

THE RULE
--------
    choose N to maximise  min( t_DEVELOPMENT(N), t_OOS(N) )

A rung that is excellent in one window and mediocre in the other scores badly,
which is exactly the failure mode that a "best in sample" pick has. This is
minimax regret on the two published estimates.

WHAT IT CANNOT DO
-----------------
It cannot turn a non-significant book into a significant one, and it cannot
supply the out-of-sample confirmation this project still lacks: both windows
sit inside the 2023-2026 sample whose every bar has been seen, and the strictest
dependence treatment on OOS is t = 0.03. **This picks an operating point. It does
not validate the strategy.**

Run:
    $env:PERP_SHORT_DATADIR="user_data/data/wide526"
    .venv\\Scripts\\python.exe tools\\perp_short\\pick_rung.py
"""

from __future__ import annotations

import glob
import os
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join("tools", "perp_short"))

import r_stats  # noqa: E402

RUNGS = [25, 40, 50, 60, 75, 100, 125, 150, 200, 300, 515]
STRAT = "PerpShort4hDeploy"


def t_for(sl: str, n: int) -> tuple[float, float, int] | None:
    c = glob.glob(f"user_data/wf_out/{sl}/n{n}/*.zip")
    if not c:
        return None
    trades = sorted(r_stats.load_trades(max(c, key=os.path.getmtime),
                                       strategy=STRAT),
                    key=lambda t: t["open_date"])
    if not trades:
        return None
    frames = r_stats.load_frames(sorted({t["pair"] for t in trades}))
    df = r_stats.build(trades, frames, 5.0, 34.9)
    r = df["R"].to_numpy()
    return (float(r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))),
            float(r.mean()), len(r))


def main() -> int:
    rows = []
    for n in RUNGS:
        d, o = t_for("dev", n), t_for("oos", n)
        if not d or not o:
            print(f"N={n}: missing a window")
            continue
        rows.append({"N": n, "t_dev": d[0], "r_dev": d[1], "n_dev": d[2],
                     "t_oos": o[0], "r_oos": o[1], "n_oos": o[2]})
    if not rows:
        print("no data")
        return 1
    df = pd.DataFrame(rows)
    df["t_min"] = df[["t_dev", "t_oos"]].min(axis=1)
    df["t_regret"] = df[["t_dev", "t_oos"]].max(axis=1) - df["t_min"]

    print("THE LADDER, BOTH WINDOWS, AT MEASURED COVID COSTS\n")
    print(f"{'N':>5}{'t dev':>9}{'t oos':>9}{'min':>8}{'regret':>9}"
          f"{'meanR dev':>11}{'meanR oos':>11}{'trades oos':>12}")
    for r in df.itertuples(index=False):
        print(f"{r.N:>5}{r.t_dev:>9.2f}{r.t_oos:>9.2f}{r.t_min:>8.2f}"
              f"{r.t_regret:>9.2f}{r.r_dev:>+11.4f}{r.r_oos:>+11.4f}{r.n_oos:>12d}")

    best = df.loc[df["t_min"].idxmax()]
    in_sample_best_dev = df.loc[df["t_dev"].idxmax()]
    in_sample_best_full = df.loc[df["t_oos"].idxmax()]

    print(f"\n  in-sample best  (max t on DEVELOPMENT) : N = {int(in_sample_best_dev.N)}  "
          f"t_dev = {in_sample_best_dev.t_dev:.2f}")
    print(f"  in-sample best  (max t on OOS)         : N = {int(in_sample_best_full.N)}  "
          f"t_oos = {in_sample_best_full.t_oos:.2f}")
    print(f"  ROBUSTNESS RULE (max min)             : N = {int(best.N)}  "
          f"min t = {best.t_min:.2f}  "
          f"(dev {best.t_dev:.2f}, oos {best.t_oos:.2f}, regret {best.t_regret:.2f})")

    print("\n=== HOW NARROW IS THE ANSWER? ===")
    top = df.sort_values("t_min", ascending=False).head(4)
    for r in top.itertuples(index=False):
        print(f"   N={r.N:<5} min t = {r.t_min:>5.2f}   "
              f"(dev {r.t_dev:>5.2f}, oos {r.t_oos:>5.2f}, regret {r.t_regret:>4.2f})")
    spread = top["t_min"].iloc[0] - top["t_min"].iloc[-1]
    shape = ("a genuinely flat optimum" if spread < 0.5
             else "a peaky one, so the choice matters")
    print(f"\n   the top four rungs span {spread:.2f} of t_min - {shape}")
    print("   and N=515 is excluded on BOTH windows' economics, not on a rule: it is")
    print("   the only rung whose OOS mean R is negative.")

    print("\n=== WHAT THE RULE CANNOT DO, SAID PLAINLY ===")
    print("   It picks an operating point inside a universe whose every bar has been")
    print("   seen. It supplies NO out-of-sample confirmation. The strictest")
    print("   dependence treatment on OOS is t = 0.03 across every rung, and the")
    print("   market-neutralised excess is negative at every rung that clears t=2.")
    print("   **A better operating point is not a better strategy.**")
    return 0


if __name__ == "__main__":
    sys.exit(main())
