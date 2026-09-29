"""Build the target-R FRONTIER from the exported runs. One row per cell.

The preregistration (`PREREG_TARGET_R_2026-09-28.md`) forbids selecting a cell,
so this prints the whole curve and does not rank, score, or highlight anything.
If a cell reaches the gate it is marked, not recommended - and the file says in
advance that a pass is a lead, not a confirmation, because the hypothesis was
generated from this same sample.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\frontier_report.py
"""

from __future__ import annotations

import glob
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.join("tools", "perp_short"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import r_stats  # noqa: E402

CELLS = ["1.5", "2.0", "3.0", "5.0", "10.0", "none"]
ROOT = "user_data/frontier_out"
# freqtrade's --export-directory MANGLES a directory name containing a dot:
# "frontier_out/1.5" became "frontier_out/1-<timestamp>.meta.json" (it strips
# what it thinks is a file extension), the directory did not exist, and the
# backtest finished with every export lost and only a traceback in the log.
DIRS = {"1.5": "tr_1p5", "2.0": "tr_2p0", "3.0": "tr_3p0",
        "5.0": "tr_5p0", "10.0": "tr_10p0", "none": "tr_none"}


def archive(cell: str) -> str | None:
    c = glob.glob(os.path.join(ROOT, DIRS[cell], "*.zip"))
    return max(c, key=os.path.getmtime) if c else None


def main() -> int:
    rows = []
    for cell in CELLS:
        ap = archive(cell)
        if ap is None:
            print(f"target_r={cell:<6} NO EXPORT - skipped")
            continue
        trades = sorted(
            r_stats.load_trades(ap, strategy="PerpShort4hTarget"),
            key=lambda t: t["open_date"])
        pairs = sorted({t["pair"] for t in trades})
        frames = r_stats.load_frames(pairs)
        for regime, fee, slip in (("calm", 5.0, 12.0), ("covid", 5.0, 34.9)):
            df = r_stats.build(trades, frames, fee, slip)
            o = r_stats.report(df, regime)
            rows.append({
                "target_r": cell, "regime": regime, "n": o["n"],
                "mean_R": o["mean_R"],
                "t_naive": o["t_naive"], "t_ts": o["t_by_timestamp"],
                "t_wk": o["t_by_week"],
                "frac_pairs_pos": o["frac_pairs_positive"],
                "n_pairs": o["pairs"],
            })
        # calendar years at the stress end
        df = r_stats.build(trades, frames, 5.0, 34.9)
        df["y"] = pd.to_datetime(df["open"], utc=True).dt.year
        for y, g in df.groupby("y"):
            t = g["R"].to_numpy()
            rows.append({"target_r": cell, "regime": f"year_{y}", "n": len(g),
                         "mean_R": float(t.mean()) if len(t) else np.nan,
                         "t_naive": np.nan, "t_ts": np.nan, "t_wk": np.nan,
                         "frac_pairs_pos": np.nan, "n_pairs": np.nan})

    out = pd.DataFrame(rows)
    os.makedirs(ROOT, exist_ok=True)
    out.to_csv(os.path.join(ROOT, "frontier.csv"), index=False)

    print("\n=== TARGET-R FRONTIER (published whole; no cell selected) ===\n")
    for regime in ("calm", "covid"):
        sub = out[out["regime"] == regime]
        if sub.empty:
            continue
        print(f"-- {regime} --")
        print(f"{'target_r':>9}{'n':>7}{'mean R':>10}{'t naive':>10}"
              f"{'t by-ts':>10}{'t by-wk':>10}{'pairs+':>9}")
        for _, r in sub.iterrows():
            print(f"{r['target_r']:>9}{r['n']:>7}{r['mean_R']:>+10.4f}"
                  f"{r['t_naive']:>10.2f}{r['t_ts']:>10.2f}{r['t_wk']:>10.2f}"
                  f"{r['frac_pairs_pos']*100:>8.0f}%")
        print()

    print("-- calendar years at the stress end (mean R) --")
    yrs = sorted({r.split("_")[1] for r in out["regime"] if r.startswith("year_")})
    print(f"{'target_r':>9}" + "".join(f"{y:>10}" for y in yrs))
    for cell in CELLS:
        vals = []
        for y in yrs:
            m = out[(out["target_r"] == cell) & (out["regime"] == f"year_{y}")]
            vals.append(f"{m['mean_R'].iloc[0]:>+10.3f}" if len(m) else f"{'-':>10}")
        print(f"{cell:>9}" + "".join(vals))
    print()

    print("-- H1: does the curve have a shape, or is the target irrelevant? --")
    for regime in ("calm", "covid"):
        sub = out[out["regime"] == regime]
        if len(sub) < 3:
            continue
        m = sub["mean_R"].to_numpy()
        best = sub.iloc[int(np.argmax(m))]
        print(f"   {regime:<6} mean R ranges {m.min():+.4f} .. {m.max():+.4f}   "
              f"interior max at target_r={best['target_r']}   "
              f"max t(by-ts)={sub['t_ts'].max():.2f}")
    print()
    print("GATE H2 (t >= 2.0 on net R at measured_covid) — checked, NOT optimised:")
    sub = out[out["regime"] == "covid"]
    for _, r in sub.iterrows():
        for key, lbl in (("t_naive", "naive"), ("t_ts", "by-ts"), ("t_wk", "by-wk")):
            print(f"   target_r={r['target_r']:<6} {lbl:<7} t={r[key]:>7.2f}  "
                  f"{'PASS' if r[key] == r[key] and r[key] >= 2.0 else 'FAIL'}")
    print("\nwrote user_data/frontier_out/frontier.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
