"""Is t(N) a curve or a spike? The shape test for the ladder selection.

`PREREG_LADDER_SHAPE_2026-09-28.md` asks whether the project's first t>=2.0
(N=50, t=2.25) sits on a smooth cost gradient or is a selected local maximum.
The answer decides how much the selection objection is worth.

It also measures, rather than assumes, the thing that decides whether selection
matters at all here: **the rungs are NESTED**, so the per-trade R series across
neighbouring rungs may be highly correlated - and a nested family is a far weaker
multiple-testing problem than independent trials. "Nesting" is an argument; the
correlation is the measurement.

Run:
    $env:PERP_SHORT_DATADIR="user_data/data/wide526"
    .venv\\Scripts\\python.exe tools\\perp_short\\ladder_shape.py
"""

from __future__ import annotations

import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join("tools", "perp_short"))

import r_stats  # noqa: E402

RUNGS = [25, 40, 50, 60, 75, 100, 125, 150, 200, 300, 515]
STRAT = "PerpShort4hDeploy"
REG = ("covid", 5.0, 34.9)


def main() -> int:
    rows, series = [], {}
    for n in RUNGS:
        cands = glob.glob(f"user_data/lshape_out/n{n}/*.zip")
        if not cands:
            print(f"N={n}: NO EXPORT - skipped")
            continue
        ap = max(cands, key=os.path.getmtime)
        trades = sorted(r_stats.load_trades(ap, strategy=STRAT),
                        key=lambda t: t["open_date"])
        pairs = sorted({t["pair"] for t in trades})
        frames = r_stats.load_frames(pairs)
        df = r_stats.build(trades, frames, *REG[1:])
        r = df["R"].to_numpy()
        t = r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))
        # r_stats.tstat returns (t, mean, n_eff, iat) - taking [0] is the t
        # ⚠ `df.set_index(idx).groupby(idx)` yields an EMPTY series (idx is
        # aligned to the original RangeIndex, the frame's index is timestamps,
        # pandas aligns them to nothing), so t_by_ts was nan for EVERY rung -
        # the strictest dependence treatment was simply absent. Group the frame
        # by the Series, which aligns on the frame's own index.
        idx = pd.to_datetime(df["open"], utc=True)
        ts = r_stats.tstat(df.groupby(idx)["R"].mean().to_numpy())[0]
        m = r_stats.market_excess(df, frames)
        cmap = pd.read_csv(f"user_data/config_laddershape/lshape_{n}_cohorts.csv")
        a_share = float((cmap["cohort"] == "A").mean())
        rows.append({"N": n, "n_trades": len(r), "mean_R": float(r.mean()),
                     "t_naive": float(t), "t_by_ts": float(ts),
                     "A_share": a_share,
                     "mkt_excess": m["excess_mean"], "mkt_t": m["t"]})
        series[n] = pd.Series(r, index=[f"{t_}|{p}" for t_, p in
                                        zip(df["open"], df["pair"])])
        print(f"N={n:<4} trades={len(r):<5} meanR={r.mean():+.4f}  "
              f"t_naive={t:>5.2f}  t_by_ts={ts:>5.2f}  A={a_share*100:4.1f}%  "
              f"mkt_excess={m['excess_mean']*100 if m['excess_mean']==m['excess_mean'] else float('nan'):+.3f}% "
              f"(t={m['t']:+.2f})")

    out = pd.DataFrame(rows)
    out.to_csv("user_data/perp_short_out/ladder_shape.csv", index=False)

    print("\n=== S1: is meanR monotone as N widens? ===")
    m = out["mean_R"].to_numpy()
    # rows are in ASCENDING N, so the cost mechanism predicts meanR FALLS as N
    # widens, i.e. m[i] >= m[i+1]. The first version of this check tested
    # m[i] <= m[i+1] and printed "S1 FAIL" on a strictly monotone curve.
    # ⚠ A test whose direction is wrong reports the opposite of the truth, and
    # on a smooth curve it looks entirely like a real finding.
    mono = all(m[i] >= m[i + 1] for i in range(len(m) - 1))
    print(f"   meanR by ascending N: {np.round(m, 4).tolist()}")
    viol = [int(out['N'].iloc[i]) for i in range(len(m) - 1) if m[i] < m[i + 1]]
    print(f"   decreasing in N (the cost mechanism): "
          f"{'YES -> S1 PASS' if mono else f'NO -> S1 FAIL, violations at N={viol}'}")

    print("\n=== S2/S3: is N=50 a spike? ===")
    t = out.set_index("N")["t_naive"]
    neighbours = [n for n in (40, 60) if n in t.index]
    best_other = t.drop(index=50).max()
    i50 = list(out["N"]).index(50)
    t50 = float(t.loc[50])
    left = float(t.loc[40]) if 40 in t.index else np.nan
    right = float(t.loc[60]) if 60 in t.index else np.nan
    local_max = (not np.isnan(left) and not np.isnan(right)
                 and left < t50 and right < t50)
    print(f"   t(40)={left:.2f}  t(50)={t50:.2f}  t(60)={right:.2f}")
    print(f"   N=50 is a local max with lower neighbours on BOTH sides: "
          f"{'YES -> S2 FAIL (it is a spike)' if local_max else 'NO -> S2 PASS (it is on a curve)'}")
    margin = t50 - best_other
    print(f"   best other rung: N={int(t.drop(index=50).idxmax())} at t={best_other:.2f}"
          f"   (margin {margin:+.2f})")

    print("\n=== S4: are the rungs independent bets, or a nested family? ===")
    # correlation of the per-trade R series between ADJACENT rungs, on the
    # intersection of their trades
    adj = []
    ns = [r for r in RUNGS if r in series]
    for a, b in zip(ns[:-1], ns[1:]):
        j = pd.concat([series[a], series[b]], axis=1, join="inner").dropna()
        if len(j) > 50:
            adj.append((a, b, len(j), float(j.iloc[:, 0].corr(j.iloc[:, 1]))))
    print(f"{'pair':>10}{'shared trades':>16}{'corr of R':>12}")
    for a, b, n, c in adj:
        print(f"{a:>4}-{b:<5}{n:>16}{c:>12.3f}")
    if adj:
        mean_corr = float(np.mean([c for *_, c in adj]))
        print(f"\n   mean adjacent-rung correlation: {mean_corr:.3f}")
        print("   A HIGH correlation means the rungs are a NESTED family, not "
              "independent\n   bets, so the effective number of independent "
              "tests is far below 11 and the\n   multiple-testing penalty is "
              "small. That is a MEASUREMENT, not the\n   argument 'they are "
              "nested' - and it is also exactly why a spike is the\n   diagnostic "
              "that matters: in a nested family a selection artifact does not "
              "need to\n   oscillate, it only needs one cell to sit above the "
              "curve it was read off.")

    print("\n=== MARKET NEUTRALISED (caveat 6 of LIQ515_RESULT, finally checked) ===")
    print(f"{'N':>6}{'A share':>10}{'excess %':>12}{'t':>8}")
    for r in out.itertuples(index=False):
        ex = r.mkt_excess
        print(f"{r.N:>6}{r.A_share*100:>9.1f}%"
              f"{(ex*100 if ex == ex else float('nan')):>11.3f}%{r.mkt_t:>8.2f}")
    print("\n   If the excess stays indistinguishable from zero at the rungs that "
          "pass,\n   then the ladder is a better TRADABLE version of the same "
          "market-beta book,\n   not a new edge. Read that before reading +89.9%.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
