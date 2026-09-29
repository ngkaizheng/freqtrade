"""Gate L2: when the liquidity ladder makes money, WHICH COINS make it?

The prereg (`PREREG_LIQUIDITY_ON_515_2026-09-28.md`) is explicit that the
obvious reading of any liquidity ladder - "the top rung made money" - is not the
question. The question is whether the NON-cohort-A portion carries the book or
the cohort-A portion does, because a liquidity filter on this panel is roughly
half a survivorship filter (top-50 is 52% cohort A).

So every trade is tagged with its cohort from the rung's own cohort map - the map
travels WITH the config, so nothing has to be joined afterwards and nothing can
be dropped in the join - and mean R is reported for the two parts separately at
each cost regime.

It also reports the PAIR-ORDER effect, which turned out to be the single largest
robustness problem in the whole project: the same 515 pairs ordered
alphabetically give +4.14% and ordered by liquidity give -17.52%, because 24
slots and 515 pairs means the whitelist order decides who gets filled.

Run:
    $env:PERP_SHORT_DATADIR="user_data/data/wide526"
    .venv\\Scripts\\python.exe tools\\perp_short\\liq515_report.py
"""

from __future__ import annotations

import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join("tools", "perp_short"))

import r_stats  # noqa: E402

RUNGS = [50, 100, 200, 515]
REGIMES = [("calm", 5.0, 12.0), ("covid", 5.0, 34.9)]
STRAT = "PerpShort4hDeploy"


def pair_to_symbol(p: str) -> str:
    return p.split("/")[0] + "USDT"


def main() -> int:
    out_rows = []
    print("LIQUIDITY LADDER ON 515, DECOMPOSED BY COHORT")
    print("A = the 104 perps that existed before 2023-01 and are still listed")
    print("gate L2: the NON-A portion must be net-positive on its own\n")

    for n in RUNGS:
        ap = max(glob.glob(f"user_data/liq515_out/n{n}/*.zip"),
                 key=os.path.getmtime)
        cmap = pd.read_csv(f"user_data/config_liq515/liq515_{n}_cohorts.csv")
        cohort = dict(zip(cmap["symbol"], cmap["cohort"]))
        trades = sorted(r_stats.load_trades(ap, strategy=STRAT),
                        key=lambda t: t["open_date"])
        pairs = sorted({t["pair"] for t in trades})
        frames = r_stats.load_frames(pairs)
        a_share = int((cmap["cohort"] == "A").sum()) / len(cmap)

        print(f"--- N={n}   pairs={len(cmap)}   cohort A share = {a_share*100:.1f}%"
              f"   (gate L3: {'PASS' if a_share < 0.6 else 'FAIL'}) ---")
        for label, fee, slip in REGIMES:
            df = r_stats.build(trades, frames, fee, slip)
            df["cohort"] = df["pair"].map(lambda p: cohort.get(pair_to_symbol(p), "?"))
            a = df[df["cohort"] == "A"]["R"]
            b = df[df["cohort"] != "A"]["R"]

            def stat(x):
                if len(x) < 5:
                    return float("nan"), float("nan"), 0
                t = x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))
                return float(x.mean()), float(t), len(x)

            ma, ta, na = stat(a)
            mb, tb, nb = stat(b)
            mall, tall, nall = stat(df["R"])
            out_rows.append({"N": n, "regime": label, "A_share": a_share,
                             "meanR": mall, "t_all": tall, "n_all": nall,
                             "meanR_A": ma, "t_A": ta, "n_A": na,
                             "meanR_nonA": mb, "t_nonA": tb, "n_nonA": nb})
            print(f"  {label:<6} all   n={nall:<5} meanR {mall:+.4f}  t {tall:>6.2f}")
            print(f"         A     n={na:<5} meanR {ma:+.4f}  t {ta:>6.2f}")
            print(f"         non-A n={nb:<5} meanR {mb:+.4f}  t {tb:>6.2f}   "
                  f"<- GATE L2: {'PASS' if (mb == mb and mb > 0) else 'FAIL'}")
        print()

    out = pd.DataFrame(out_rows)
    out.to_csv("user_data/perp_short_out/liq515_decomp.csv", index=False)

    print("=== THE LADDER, ALL REGIMES (gate L5: should be monotone as N falls) ===")
    for label, _, _ in REGIMES:
        sub = out[out["regime"] == label]
        print(f"\n  -- {label} --")
        print(f"{'N':>6}{'A share':>10}{'meanR all':>12}{'meanR A':>11}"
              f"{'meanR non-A':>14}{'n non-A':>9}")
        for r in sub.itertuples(index=False):
            print(f"{r.N:>6}{r.A_share*100:>9.1f}%{r.meanR:>12.4f}{r.meanR_A:>11.4f}"
                  f"{r.meanR_nonA:>14.4f}{r.n_nonA:>9d}")
        ms = sub["meanR"].to_numpy()
        mono = all(ms[i] >= ms[i + 1] for i in range(len(ms) - 1)) or \
            all(ms[i] <= ms[i + 1] for i in range(len(ms) - 1))
        print(f"  monotone as N falls: {'YES' if mono else 'NO'}"
              f"   -> gate L5 {'PASS' if mono else 'FAIL'}")

    print("\n=== THE PAIR-ORDER EFFECT (not in the prereg; found while running it) ===")
    print("  same 515 pairs, ALPHABETICAL whitelist order : +4.14%  (1,980 trades)")
    print("  same 515 pairs, LIQUIDITY-ranked order       : -17.52% (1,955 trades)")
    print("  With 24 slots and 515 pairs, more than 24 pairs frequently signal at once,")
    print("  so the whitelist order decides who is filled. A 21-point swing on a")
    print("  detail nobody would think to vary is the most damaging robustness")
    print("  finding in this project, and it is NOT a bug - it is how any portfolio")
    print("  with a slot limit behaves. The honest response is to make the ordering")
    print("  a RULE ('when slots are scarce, take the most liquid') rather than an")
    print("  accident of string sorting, and then to say so.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
