"""Stop-multiple frontier, published whole. Includes the MECHANISTIC gate S7.

S7 is the reason this is not just another parameter sweep. A rung can make money
and still fail the hypothesis, because the hypothesis was specifically about the
**stop-out rate**, not about the P&L. If the stop-out rate does not fall roughly
as `H_a` predicts, then whatever moved the number, it was not the mechanism this
design claimed - and the design has to say so rather than bank the P&L.

Read `docs-myself/PREREG_STOP_MULTIPLE_2026-09-28.md` first. It forbids picking a
rung and forbids re-opening this with a second sweep if it fails.

Run:
    $env:PERP_SHORT_DATADIR="user_data/data/wide104"
    .venv\\Scripts\\python.exe tools\\perp_short\\stopfront_report.py
"""

from __future__ import annotations

import glob
import json
import os
import sys
import zipfile
from collections import Counter

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join("tools", "perp_short"))

import r_stats  # noqa: E402

RUNGS = [("1.0", "s_1p0"), ("1.5", "s_1p5"), ("2.5", "s_2p5"), ("4.0", "s_4p0")]
ROOT = "user_data/stopfront_out"
STRATEGY = "PerpShort4hStop"
REGIMES = [("engine", 5.0, 0.0), ("calm", 5.0, 12.0),
           ("volatile", 5.0, 22.8), ("covid", 5.0, 34.9)]


def archive(d: str) -> str | None:
    c = glob.glob(os.path.join(ROOT, d, "*.zip"))
    return max(c, key=os.path.getmtime) if c else None


def exit_mix(trades: list[dict]) -> Counter:
    return Counter(t.get("exit_reason", "?") for t in trades)


def main() -> int:
    rows = []
    mixes = {}
    for label, d in RUNGS:
        ap = archive(d)
        if ap is None:
            print(f"atr_stop={label}: NO EXPORT - skipped")
            continue
        trades = sorted(r_stats.load_trades(ap, strategy=STRATEGY),
                        key=lambda t: t["open_date"])
        pairs = sorted({t["pair"] for t in trades})
        frames = r_stats.load_frames(pairs)
        mixes[label] = exit_mix(trades)
        n = len(trades)
        n_stop = sum(v for k, v in mixes[label].items() if "stop_loss" in k)
        n_tgt = sum(v for k, v in mixes[label].items() if k.startswith("target"))

        for regime, fee, slip in REGIMES:
            df = r_stats.build(trades, frames, fee, slip)
            o = r_stats.report(df, regime)
            rows.append({"atr_stop": label, "regime": regime, "n_trades": n,
                         "mean_R": o["mean_R"], "t_naive": o["t_naive"],
                         "t_by_timestamp": o["t_by_timestamp"],
                         "t_by_week": o["t_by_week"],
                         "frac_pairs_positive": o["frac_pairs_positive"],
                         "stop_out_rate": n_stop / n, "target_rate": n_tgt / n,
                         "win_rate": float((df["R"] > 0).mean())})
        df = r_stats.build(trades, frames, 5.0, 34.9)
        df["y"] = pd.to_datetime(df["open"], utc=True).dt.year
        for y, g in df.groupby("y"):
            rows.append({"atr_stop": label, "regime": f"year_{y}", "n_trades": len(g),
                         "mean_R": float(g["R"].mean()), "t_naive": np.nan,
                         "t_by_timestamp": np.nan, "t_by_week": np.nan,
                         "frac_pairs_positive": np.nan,
                         "stop_out_rate": np.nan, "target_rate": np.nan,
                         "win_rate": np.nan})

    out = pd.DataFrame(rows)
    os.makedirs("user_data/perp_short_out", exist_ok=True)
    out.to_csv("user_data/perp_short_out/stopfront.csv", index=False)

    lab = [r[0] for r in RUNGS]
    print("\n=== EXIT MIX (gate S7 lives here) ===")
    print(f"{'atr_stop':>9}{'trades':>9}{'stop-out':>10}{'target':>9}{'time':>8}{'win(R>0)':>10}")
    for L in lab:
        if L not in mixes:
            continue
        m = mixes[L]
        n = sum(m.values())
        so = sum(v for k, v in m.items() if "stop_loss" in k) / n
        tg = sum(v for k, v in m.items() if k.startswith("target")) / n
        ts = sum(v for k, v in m.items() if k == "time_stop") / n
        wr = out[(out["atr_stop"] == L) & (out["regime"] == "engine")]["win_rate"]
        w = f"{float(wr.iloc[0])*100:>9.1f}%" if len(wr) else f"{'-':>10}"
        print(f"{L:>9}{n:>9}{so*100:>9.1f}%{tg*100:>8.1f}%{ts*100:>7.1f}%{w}")

    print("\n=== MEAN NET R BY STOP MULTIPLE ===")
    piv = out.pivot_table(index="atr_stop", columns="regime", values="mean_R")
    cc = [c for c, _, _ in REGIMES if c in piv.columns]
    print(piv[cc].to_string(float_format=lambda v: f"{v:+.4f}"))

    for metric, lbl in (("t_naive", "naive"), ("t_by_timestamp", "by-timestamp"),
                        ("t_by_week", "by-week")):
        print(f"\n=== t ({lbl}) ===")
        p = out[out["regime"].isin([c for c, _, _ in REGIMES])].pivot_table(
            index="atr_stop", columns="regime", values=metric)
        print(p[[c for c, _, _ in REGIMES if c in p.columns]].to_string(
            float_format=lambda v: f"{v:>6.2f}"))

    print("\n=== PER-SYMBOL POSITIVE (gate S4) ===")
    p = out[out["regime"].isin(["calm", "covid"])].pivot_table(
        index="atr_stop", columns="regime", values="frac_pairs_positive")
    for c in p.columns:
        p[c] = (p[c] * 100).round(0).astype(int).astype(str) + "%"
    print(p.to_string())

    print("\n=== CALENDAR YEARS at the stress end (mean R) ===")
    yrs = sorted({r.split("_")[1] for r in out["regime"] if r.startswith("year_")})
    print(f"{'stop':>6}" + "".join(f"{y:>10}" for y in yrs) + f"{'>=3 yrs +':>12}")
    for L in lab:
        vals, np_ = [], 0
        for y in yrs:
            m = out[(out["atr_stop"] == L) & (out["regime"] == f"year_{y}")]
            if len(m):
                v = float(m["mean_R"].iloc[0])
                vals.append(f"{v:>+10.3f}")
                np_ += 1 if v > 0 else 0
            else:
                vals.append(f"{'-':>10}")
        print(f"{L:>6}" + "".join(vals) + f"{np_:>12}")

    print("\n=== GATES (evaluated on EVERY rung; none selected) ===")
    best_t, best_cell = -9e9, None
    for L in lab:
        for regime, _, _ in REGIMES:
            m = out[(out["atr_stop"] == L) & (out["regime"] == regime)]
            if not len(m):
                continue
            r = m.iloc[0]
            t = r["t_by_timestamp"]
            s2 = t == t and t >= 2.0
            s3 = r["mean_R"] > 0
            s4 = r["frac_pairs_positive"] == r["frac_pairs_positive"] and r["frac_pairs_positive"] >= 0.5
            if regime == "covid" and t == t and t > best_t:
                best_t, best_cell = t, L
            print(f"   stop={L:<5} {regime:<9} t={t:>6.2f} {'PASS' if s2 else 'FAIL':<4} "
                  f"meanR={r['mean_R']:+.4f} {'PASS' if s3 else 'FAIL':<4} "
                  f"pairs+={r['frac_pairs_positive']*100:>3.0f}% {'PASS' if s4 else 'FAIL'}")

    print("\n=== S1 (interior structure) and S7 (the mechanism) ===")
    calm = out[out["regime"] == "covid"].set_index("atr_stop")
    base = float(calm.loc["1.5", "mean_R"]) if "1.5" in calm.index else np.nan
    for L in lab:
        if L not in calm.index:
            continue
        r = calm.loc[L]
        d = r["mean_R"] - base
        print(f"   stop={L:<5} meanR@covid={r['mean_R']:+.4f} (vs 1.5: {d:+.4f})  "
              f"stop-out={r['stop_out_rate']*100:>5.1f}%  "
              f"target={r['target_rate']*100:>5.1f}%")
    if best_cell:
        b = calm.loc[best_cell]
        s7 = b["stop_out_rate"] < float(calm.loc["1.5", "stop_out_rate"])
        print(f"\n   best rung by t(by-ts) @covid: {best_cell}  -> S7 "
              f"{'PASS' if s7 else 'FAIL'} "
              f"({b['stop_out_rate']*100:.1f}% vs baseline "
              f"{float(calm.loc['1.5','stop_out_rate'])*100:.1f}%)")
    print("\n   NOTE: S1/S7 are read here, not used to pick a rung. A rung that")
    print("   improves P&L without moving the stop-out rate has NOT done what")
    print("   the hypothesis claimed, and the prereg says so out loud.")
    print("\nwrote user_data/perp_short_out/stopfront.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
