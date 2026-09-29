"""The liquidity ladder, published whole. One block per rung, no ranking.

`PREREG_LIQUIDITY_LADDER_2026-09-28.md` forbids quoting a single rung: the whole
point of the design is that the favourable end was already known when it was
written, so a single number would be a maximum-over-4 selection dressed up as a
result. The rungs are printed in order, and the gate is evaluated on all of them
rather than on the one that happens to clear it.

Run:
    $env:PERP_SHORT_DATADIR="user_data/data/wide104"
    .venv\\Scripts\\python.exe tools\\perp_short\\ladder_report.py
"""

from __future__ import annotations

import glob
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join("tools", "perp_short"))

import r_stats  # noqa: E402

RUNGS = [12, 24, 50, 104]
ROOT = "user_data/ladder_out"
REGIMES = [("engine", 5.0, 0.0), ("calm", 5.0, 12.0),
           ("volatile", 5.0, 22.8), ("covid", 5.0, 34.9)]


def archive(n: int) -> str | None:
    c = glob.glob(os.path.join(ROOT, f"l{n}", "*.zip"))
    return max(c, key=os.path.getmtime) if c else None


def main() -> int:
    frames_cache: dict = {}
    rows = []
    print("LIQUIDITY LADDER - all four rungs, one dataset, one strategy,")
    print("max_open_trades pinned to the rung size so concurrency cannot float.\n")

    for n in RUNGS:
        ap = archive(n)
        if ap is None:
            print(f"N={n}: NO EXPORT - skipped")
            continue
        trades = sorted(r_stats.load_trades(ap), key=lambda t: t["open_date"])
        pairs = sorted({t["pair"] for t in trades})
        for p in pairs:
            if p not in frames_cache:
                frames_cache[p] = None
        frames = r_stats.load_frames(pairs)

        block = {"n": n, "n_pairs": len(pairs), "n_trades": len(trades)}
        for label, fee, slip in REGIMES:
            df = r_stats.build(trades, frames, fee, slip)
            o = r_stats.report(df, label)
            block[label] = o
        for label, o in block.items():
            if isinstance(o, dict):
                # NB: r_stats.report() itself returns an "n" (the TRADE count).
                # Merging it under the key "n" would silently overwrite the RUNG
                # size, which is the axis the whole ladder is plotted on - and
                # the resulting table still looks plausible. Rename it.
                rows.append({"n": n, "regime": label, **{
                    k: o.get(k) for k in
                    ("mean_R", "t_naive", "t_by_timestamp", "t_by_week",
                     "frac_pairs_positive", "pairs", "mean_R_drop_best")},
                    "n_trades": o.get("n")})
        # calendar years at the stress end
        df = r_stats.build(trades, frames, 5.0, 34.9)
        df["y"] = pd.to_datetime(df["open"], utc=True).dt.year
        for y, g in df.groupby("y"):
            rows.append({"n": n, "regime": f"year_{y}", "n_trades": len(g),
                         "mean_R": float(g["R"].mean()), "t_naive": np.nan,
                         "t_by_timestamp": np.nan, "t_by_week": np.nan,
                         "frac_pairs_positive": np.nan, "pairs": np.nan,
                         "mean_R_drop_best": np.nan})
        print(f"  N={n:<4} symbols traded {len(pairs):<4} trades {len(trades):<6} done")

    out = pd.DataFrame(rows)
    os.makedirs("user_data/perp_short_out", exist_ok=True)
    out.to_csv("user_data/perp_short_out/ladder.csv", index=False)

    print("\n=== MEAN R BY RUNG (liquidity narrows left -> right) ===")
    piv = out.pivot_table(index="n", columns="regime", values="mean_R")
    cols = [c for c in ["engine", "calm", "volatile", "covid"] if c in piv.columns]
    print(piv[cols].to_string(float_format=lambda v: f"{v:+.4f}"))

    print("\n=== DEPENDENCE-ADJUSTED t BY RUNG ===")
    for metric, lbl in (("t_naive", "naive"), ("t_by_timestamp", "by-timestamp"),
                        ("t_by_week", "by-week")):
        print(f"\n  -- {lbl} --")
        sub = out[out["regime"].isin([c for c, _, _ in REGIMES])]
        p = sub.pivot_table(index="n", columns="regime", values=metric)
        cc = [c for c in ["engine", "calm", "volatile", "covid"] if c in p.columns]
        print(p[cc].to_string(float_format=lambda v: f"{v:>6.2f}"))

    print("\n=== PER-SYMBOL CONSISTENCY (gate L4: >= 50%) ===")
    sub = out[out["regime"].isin(["calm", "covid"])]
    p = sub.pivot_table(index="n", columns="regime",
                        values="frac_pairs_positive")
    for c in p.columns:
        p[c] = (p[c] * 100).round(0).astype(int).astype(str) + "%"
    print(p.to_string())

    print("\n=== CALENDAR YEARS at the stress end (mean R) ===")
    yrs = sorted({r.split("_")[1] for r in out["regime"] if r.startswith("year_")})
    print(f"{'N':>5}" + "".join(f"{y:>10}" for y in yrs))
    for n in RUNGS:
        vals = []
        for y in yrs:
            m = out[(out["n"] == n) & (out["regime"] == f"year_{y}")]
            vals.append(f"{m['mean_R'].iloc[0]:>+10.3f}" if len(m) else f"{'-':>10}")
        print(f"{n:>5}" + "".join(vals))

    print("\n=== GATES (L2/L3/L4/L5 evaluated on EVERY rung, none selected) ===")
    any_pass = False
    for n in RUNGS:
        for label, _, _ in REGIMES:
            m = out[(out["n"] == n) & (out["regime"] == label)]
            if not len(m):
                continue
            r = m.iloc[0]
            t = r["t_by_timestamp"]
            g2 = t == t and t >= 2.0
            g3 = r["mean_R"] > 0
            g4 = r["frac_pairs_positive"] == r["frac_pairs_positive"] and r["frac_pairs_positive"] >= 0.5
            any_pass = any_pass or g2
            print(f"   N={n:<4} {label:<9} t(by-ts)={t:>6.2f} {('PASS' if g2 else 'FAIL'):<4} "
                  f"meanR={r['mean_R']:+.4f} {('PASS' if g3 else 'FAIL'):<4} "
                  f"pairs+={r['frac_pairs_positive']*100:>3.0f}% {('PASS' if g4 else 'FAIL')}")
    print()
    if not any_pass:
        print("NO RUNG CLEARS t >= 2.0 ON NET R AT ANY COST REGIME.")
        print("Gate L1 (cost per R rises as the universe widens) is the only")
        print("claim this design can still make, and it is a claim about COST,")
        print("not about the signal.")
    print("\nwrote user_data/perp_short_out/ladder.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
