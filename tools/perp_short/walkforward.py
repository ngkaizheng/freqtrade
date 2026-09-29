"""Walk-forward test of the SELECTION PROCESS.

`PREREG_WALKFORWARD_SELECTION_2026-09-28.md` asks: if the ladder rung had to be
chosen using ONLY 2023-2024, which rung would it be - and does that rung still
work on 2025-2026?

THE ORDERING IS ENFORCED BY THIS SCRIPT, NOT BY GOOD INTENTIONS
--------------------------------------------------------------
The development ranking is computed and PRINTED, and the chosen N is written to
disk, BEFORE any OOS trade is read. That is deliberate: a selection test in
which the selector can see the test data is not a selection test, and the failure
mode is invisible - you simply find that the OOS result "disagrees" and
re-examine the rule. Here the rule is frozen in a prereg, and the choice is
recorded before it can be doubted.

Run:
    $env:PERP_SHORT_DATADIR="user_data/data/wide526"
    .venv\\Scripts\\python.exe tools\\perp_short\\walkforward.py
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

RUNGS = [25, 40, 50, 60, 75, 100, 125, 150, 200, 300, 515]
STRAT = "PerpShort4hDeploy"
REGIMES = [("engine", 5.0, 0.0), ("calm", 5.0, 12.0), ("covid", 5.0, 34.9)]
CHOICE_FILE = "user_data/perp_short_out/wf_choice.json"


def stats_for(sl: str, n: int) -> dict:
    cands = glob.glob(f"user_data/wf_out/{sl}/n{n}/*.zip")
    if not cands:
        return {}
    ap = max(cands, key=os.path.getmtime)
    trades = sorted(r_stats.load_trades(ap, strategy=STRAT),
                    key=lambda t: t["open_date"])
    if not trades:
        return {}
    pairs = sorted({t["pair"] for t in trades})
    frames = r_stats.load_frames(pairs)
    out = {"n_trades": len(trades)}
    for label, fee, slip in REGIMES:
        df = r_stats.build(trades, frames, fee, slip)
        r = df["R"].to_numpy()
        t = r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))
        # ⚠ `df.set_index(idx).groupby(idx)` returns an EMPTY series: `idx` is a
        # Series aligned to the frame's ORIGINAL RangeIndex, while the frame's
        # index is now timestamps, so pandas aligns the two to nothing. The
        # result was `len == 0` -> tstat nan -> **the strictest dependence
        # treatment silently absent from the shape test AND this one**. A wrong
        # number gets argued about; a missing one just disappears. Group the
        # frame by the Series instead, which aligns on the frame's own index.
        idx = pd.to_datetime(df["open"], utc=True)
        by_ts = df.groupby(idx)["R"].mean().to_numpy()
        tby = r_stats.tstat(by_ts)[0]
        twk = r_stats.tstat(df.set_index(idx)["R"].resample("1W").sum()
                            .dropna().to_numpy())[0]
        out[label] = {"mean_R": float(r.mean()), "t_naive": float(t),
                      "t_by_ts": float(tby), "t_by_wk": float(twk),
                      "win": float((r > 0).mean())}
    return out


def main() -> int:
    # ---------- PHASE 1: development only ----------
    print("PHASE 1 — DEVELOPMENT (2023-01-01 to 2024-12-31) ONLY")
    print("the choice rule is frozen in the prereg: highest naive t on net R at")
    print("measured_covid costs. No OOS data is read in this phase.\n")
    dev = {}
    for n in RUNGS:
        s = stats_for("dev", n)
        if s:
            dev[n] = s
            print(f"  N={n:<4} trades={s['n_trades']:<5} "
                  f"meanR={s['covid']['mean_R']:+.4f}  t={s['covid']['t_naive']:>5.2f}")
    if not dev:
        print("no development exports")
        return 1
    chosen = max(dev, key=lambda n: dev[n]["covid"]["t_naive"])
    print(f"\n  ==> DEVELOPMENT PICKS N = {chosen}   (t = {dev[chosen]['covid']['t_naive']:.2f})")
    print(f"  ==> full sample picked N = 50        (t = 2.25)")
    step = min(abs(c - 50) for c in RUNGS)
    w1 = abs(chosen - 50) <= max(step, 10)
    print(f"  ==> W1 selection stability: {'PASS' if w1 else 'FAIL'}"
          f"   (chose {chosen}, full sample chose 50, ladder step {step})")
    with open(CHOICE_FILE, "w") as f:
        json.dump({"chosen_N": chosen, "dev": dev, "w1": bool(w1)}, f, indent=1)
    print(f"\n  choice written to {CHOICE_FILE} BEFORE any OOS number is read.\n")

    # ---------- PHASE 2: OOS, once ----------
    print("PHASE 2 — OOS (2025-01-01 to 2026-08-31), evaluated once\n")
    print(f"{'N':>6}{'trades':>8}{'meanR':>10}{'t':>8}{'t_ts':>8}{'t_wk':>8}{'win':>8}")
    oos = {}
    for n in RUNGS:
        s = stats_for("oos", n)
        if s:
            oos[n] = s
            c = s["covid"]
            print(f"{n:>6}{s['n_trades']:>8}{c['mean_R']:>+10.4f}{c['t_naive']:>8.2f}"
                  f"{c['t_by_ts']:>8.2f}{c['t_by_wk']:>8.2f}{c['win']*100:>7.1f}%")
    if chosen not in oos:
        print(f"chosen N={chosen} has no OOS export")
        return 1

    c = oos[chosen]["covid"]
    w2 = c["mean_R"] > 0
    w3 = c["t_naive"] >= 1.0
    print(f"\n  CHOSEN N={chosen} on OOS at measured_covid:")
    print(f"    mean R = {c['mean_R']:+.4f}   naive t = {c['t_naive']:.2f}   "
          f"by-timestamp t = {c['t_by_ts']:.2f}   by-week t = {c['t_by_wk']:.2f}")
    print(f"    W2 OOS sign  : {'PASS' if w2 else 'FAIL'}")
    print(f"    W3 OOS t>=1.0: {'PASS' if w3 else 'FAIL'}")
    for label, _, _ in REGIMES:
        o = oos[chosen][label]
        print(f"    {label:<6} meanR {o['mean_R']:+.4f}  t {o['t_naive']:>5.2f}  "
              f"win {o['win']*100:.1f}%")

    print(f"\n  W4 honesty check - full-sample N=50 at measured_covid was "
          f"mean R +0.2128, t 2.25.")
    print(f"     The OOS number above is what a practitioner who had chosen N on "
          f"2023-2024\n     alone would actually have faced in 2025-2026. Both are "
          f"on the table; neither is\n     the headline on its own.")

    with open(CHOICE_FILE, "w") as f:
        json.dump({"chosen_N": chosen, "dev": dev, "oos": oos,
                   "w1": bool(w1), "w2": bool(w2), "w3": bool(w3)}, f, indent=1)
    print(f"\n  OVERALL: W1 {'PASS' if w1 else 'FAIL'} | "
          f"W2 {'PASS' if w2 else 'FAIL'} | W3 {'PASS' if w3 else 'FAIL'}")
    print(f"  (full detail written to {CHOICE_FILE})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
