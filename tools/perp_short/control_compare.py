"""Control vs real, compared in R (per trade), not in USDT.

WHY NOT USDT
-------------
The two arms do not execute the same number of trades. The real signal CLUSTERS
(72% of its trades share a timestamp with another - WIDE_PANEL_RESULT §2), so
many of its signals are rejected because all 24 slots are busy, while the
control's timing-destroyed signals are spread evenly and nearly all of them get
filled. Measured: real 1,140 executed trades vs control 2,876.

A USDT comparison would therefore be comparing a 1,140-trade book with a
2,876-trade book, and the control pays proportionally more fees and spends
proportionally more time in the market. **R per trade is the size- and
count-independent comparison, and it is the one the prereg asks for.**

The signal FREQUENCY does match exactly - verified bar-for-bar at 75 / 65 / 65 /
67 / 63 signals on BTC / ETH / SOL / DOGE / AAVE, control == real on every pair.
Only the clustering differs, and the dependence correction below handles that.

Run:
    $env:PERP_SHORT_DATADIR="user_data/data/wide104"
    .venv\\Scripts\\python.exe tools\\perp_short\\control_compare.py
"""

from __future__ import annotations

import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join("tools", "perp_short"))

import r_stats  # noqa: E402

REGIMES = [("engine", 5.0, 0.0), ("calm", 5.0, 12.0),
           ("volatile", 5.0, 22.8), ("covid", 5.0, 34.9)]

ARMS = {
    "real 4.0 ATR": ("user_data/stopfront_out/s_4p0", "PerpShort4hStop"),
    "CONTROL (timing destroyed)": ("user_data/stopfront_out/ctrl", "PerpShort4hControl"),
}


def newest(d: str) -> str | None:
    c = glob.glob(os.path.join(d, "*.zip"))
    return max(c, key=os.path.getmtime) if c else None


def main() -> int:
    results = {}
    for name, (d, strat) in ARMS.items():
        ap = newest(d)
        if ap is None:
            print(f"{name}: NO EXPORT")
            continue
        tr = sorted(r_stats.load_trades(ap, strategy=strat),
                    key=lambda t: t["open_date"])
        pairs = sorted({t["pair"] for t in tr})
        fr = r_stats.load_frames(pairs)
        print(f"{name}\n   trades={len(tr)}  symbols={len(pairs)}")
        mix = {}
        for t in tr:
            k = t.get("exit_reason", "?")
            mix[k] = mix.get(k, 0) + 1
        tot = sum(mix.values())
        so = sum(v for k, v in mix.items() if "stop_loss" in k) / tot
        tg = sum(v for k, v in mix.items() if k.startswith("target")) / tot
        ts = sum(v for k, v in mix.items() if k == "time_stop") / tot
        print(f"   exit mix: stop-out {so*100:.1f}%  target {tg*100:.1f}%  "
              f"time stop {ts*100:.1f}%")
        row = {}
        for label, fee, slip in REGIMES:
            df = r_stats.build(tr, fr, fee, slip)
            o = r_stats.report(df, label)
            row[label] = o
            print(f"   {label:<9} meanR={o['mean_R']:+.4f}  "
                  f"t_naive={o['t_naive']:>6.2f}  t_ts={o['t_by_timestamp']:>6.2f}  "
                  f"t_wk={o['t_by_week']:>6.2f}  pairs+={o['frac_pairs_positive']*100:.0f}%")
        results[name] = row
        print()

    if len(results) != 2:
        print("need both arms")
        return 1
    a = results["real 4.0 ATR"]
    b = results["CONTROL (timing destroyed)"]

    print("=== GATE C1: control must not reach 80% of the real arm's mean R ===")
    for label, _, _ in REGIMES:
        m = a[label]["mean_R"]
        c = b[label]["mean_R"]
        ok = c < 0.8 * m
        print(f"   {label:<9} real {m:+.4f}   control {c:+.4f}   "
              f"control/real = {c/m:>6.2f}   {'PASS' if ok else 'FAIL'}")

    print("\n=== GATE C2: real must beat control at EVERY cost regime ===")
    allok = True
    for label, _, _ in REGIMES:
        ok = a[label]["mean_R"] > b[label]["mean_R"]
        allok = allok and ok
        print(f"   {label:<9} {'PASS' if ok else 'FAIL'}")
    print(f"   -> C2 {'PASS' if allok else 'FAIL'}")

    print("\n=== GATE C3: real t(by-timestamp) must exceed control's at every regime ===")
    allok = True
    for label, _, _ in REGIMES:
        ta, tb = a[label]["t_by_timestamp"], b[label]["t_by_timestamp"]
        ok = ta > tb
        allok = allok and ok
        print(f"   {label:<9} real {ta:>6.2f}  control {tb:>6.2f}  "
              f"{'PASS' if ok else 'FAIL'}")
    print(f"   -> C3 {'PASS' if allok else 'FAIL'}")

    print("\n=== MARGIN (how much of the real arm survives the control) ===")
    for label, _, _ in REGIMES:
        m, c = a[label]["mean_R"], b[label]["mean_R"]
        print(f"   {label:<9} real - control = {m - c:+.4f} R/trade")

    print("\n=== CALENDAR YEARS at the stress end (mean R) ===")
    print(f"{'arm':<28}" + "".join(f"{y:>10}" for y in (2023, 2024, 2025, 2026)))
    for name, (d, strat) in ARMS.items():
        ap = newest(d)
        tr = sorted(r_stats.load_trades(ap, strategy=strat),
                    key=lambda t: t["open_date"])
        fr = r_stats.load_frames(sorted({t["pair"] for t in tr}))
        df = r_stats.build(tr, fr, 5.0, 34.9)
        df["y"] = pd.to_datetime(df["open"], utc=True).dt.year
        out = []
        for y in (2023, 2024, 2025, 2026):
            g = df[df["y"] == y]
            out.append(f"{g['R'].mean():>+10.3f}" if len(g) else f"{'-':>10}")
        print(f"{name:<28}" + "".join(out))

    print("\nwrote nothing to disk - this is a decision aid, not an artifact")
    return 0


if __name__ == "__main__":
    sys.exit(main())
