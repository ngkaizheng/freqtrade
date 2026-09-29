"""Where does the edge actually live? Decompose mean R by COINCIDENCE.

THE OBSERVATION THAT PROMPTS THIS
---------------------------------
On the 4.0-ATR arm at measured_covid:

    t (naive, over trades)          = +0.60
    t (by-timestamp, averaged)     = -0.15
    t (by-week)                     = +0.64

Averaging trades that share a timestamp DESTROYS the signal, while treating them
as independent observations INFLATES it. Both cannot be right, and the gap is
the whole question. 1,140 trades over 549 distinct timestamps means the average
timestamp holds ~2 trades and the distribution is heavy-tailed.

`WIDE_PANEL_RESULT_2026-09-28.md` §2 already measured something in this
direction and stated it as a finding: *"独占突破（只有它自己在动）是亏的。只有在大
量合约同时突破时才有 edge"* - a breakout that is alone in the market LOSES, and
the edge appears when many contracts break out together. That is a hypothesis
about exactly this decomposition, and it has never been run on the freqtrade
trades.

So: compute, for every trade, how many OTHER symbols carried the same signal on
the same bar, and ask whether mean R rises with that count.

WHAT THIS IS AND IS NOT
-----------------------
This is a DIAGNOSIS, not a strategy. It introduces no parameter and no filter;
it only reads the trades that already happened. Whatever it shows, a threshold
built on top of it must be pre-registered separately, and the fact that the
decomposition is run first is a reason to be MORE careful with the threshold,
not less: the favourable bucket is visible the moment this prints.

Run:
    $env:PERP_SHORT_DATADIR="user_data/data/wide104"
    .venv\\Scripts\\python.exe tools\\perp_short\\coincidence.py
"""

from __future__ import annotations

import glob
import os
import sys
from collections import Counter

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join("tools", "perp_short"))
sys.path.insert(0, os.path.join("user_data", "strategies"))

import r_stats  # noqa: E402
from PerpShort4h import PerpShort4h  # noqa: E402

DATADIR = os.environ.get("PERP_SHORT_DATADIR", "user_data/data/wide104")
ARCHIVE = os.environ.get("PERP_SHORT_GLOB",
                         "user_data/stopfront_out/s_4p0/*.zip")
STRATEGY = os.environ.get("PERP_SHORT_STRATEGY", "PerpShort4hStop")


def coincidence_table() -> dict:
    """(pair, bar_index) -> how many symbols signalled on that bar.

    Built from the strategy's OWN populate_indicators over every panel symbol, so
    the signal set here is the same one the backtest used. Keyed by bar INDEX
    rather than timestamp because the frames are all aligned to the same
    4h grid starting 2023-01-01; a timestamp join would be silently wrong if any
    symbol started late, which is exactly the failure AGENTS.md section 3 is
    about.
    """
    files = sorted(glob.glob(os.path.join(DATADIR, "futures", "*-4h-futures.feather")))
    if not files:
        raise SystemExit(f"no 4h futures files under {DATADIR}")
    s = PerpShort4h(config={})
    counts: Counter = Counter()
    frames = {}
    for fp in files:
        d = pd.read_feather(fp)[["date", "open", "high", "low", "close", "volume"]]
        out = s.populate_indicators(d.copy(), {"pair": "X/USDT:USDT"})
        sig = out["shark_short"].to_numpy()
        frames[os.path.basename(fp)] = out
        for i in np.flatnonzero(sig):
            counts[int(i)] += 1
    return counts, frames


def main() -> int:
    ap = max(glob.glob(ARCHIVE), key=os.path.getmtime)
    trades = sorted(r_stats.load_trades(ap, strategy=STRATEGY),
                    key=lambda t: t["open_date"])
    pairs = sorted({t["pair"] for t in trades})
    print(f"archive   : {ap}")
    print(f"trades    : {len(trades)}   symbols: {len(pairs)}")

    print("\nbuilding the cross-sectional coincidence count over the panel ...")
    counts, frames = coincidence_table()
    n_bars_signed = len(counts)
    n_symbols = len(frames)
    print(f"   {n_symbols} symbols, {n_bars_signed} bars carry at least one signal")
    if n_bars_signed:
        vals = np.array(list(counts.values()))
        print(f"   symbols signalling per signed bar: mean {vals.mean():.2f}  "
              f"median {np.median(vals):.0f}  p90 {np.percentile(vals, 90):.0f}  "
              f"max {vals.max()}")

    # map each trade's open timestamp to the signal bar's INDEX.
    # NB: comparing a tz-aware numpy datetime64 array against a NAIVE np.datetime64
    # returns all-False and produces a zero-row alignment, so the lookup goes
    # through pandas Timestamps. This is the same tz trap §4 records for
    # cross-symbol joins, and it is why the tool refuses to print rather than
    # printing an empty table that would read like a null result.
    fr = r_stats.load_frames(pairs)
    rows = []
    for t in trades:
        fname = t["pair"].replace("/", "_").replace(":", "_").replace("-", "_")
        d = frames.get(f"{fname}-4h-futures.feather")
        if d is None:
            continue
        idx_of = {pd.Timestamp(x): i for i, x in enumerate(d["date"])}
        ts = pd.Timestamp(t["open_date"])
        # the SIGNAL bar is the one before the fill bar
        target = ts - pd.Timedelta(hours=4)
        i = idx_of.get(target)
        if i is None:
            continue
        rows.append({"pair": t["pair"], "bar": int(i),
                     "n_coincident": counts.get(int(i), 1),
                     "close_date": t["close_date"]})
    sig = pd.DataFrame(rows)
    if sig.empty:
        print("could not align trades to signal bars - refusing to print a table")
        return 1
    print(f"   {len(sig)}/{len(trades)} trades aligned to a signal bar")

    tr = r_stats.load_trades(ap, strategy=STRATEGY)
    tr = sorted(tr, key=lambda t: t["open_date"])
    keep = {(r.pair, r.close_date): r.n_coincident
            for r in sig.itertuples(index=False)}

    atr_stop = float(os.environ.get("PERP_SHORT_ATR_STOP", "4.0"))
    built = r_stats.build(tr, fr, 5.0, 34.9)
    built["n_coincident"] = [
        keep.get((t["pair"], t["close_date"]), np.nan) for t in tr
    ]
    built = built.dropna(subset=["n_coincident"])
    built["n_coincident"] = built["n_coincident"].astype(int)

    print("\n=== MEAN NET R BY COINCIDENCE (how many symbols signalled together) ===")
    print("    at measured_covid; R = net pnl / (stake x stop_mult x atr%)")
    print(f"\n{'n_coincident':>13}{'trades':>9}{'mean R':>10}{'t naive':>9}"
          f"{'p95 R':>9}{'win':>8}")
    for lo, hi, lbl in [(1, 1, "1 (alone)"), (2, 2, "2"), (3, 4, "3-4"),
                        (5, 7, "5-7"), (8, 12, "8-12"), (13, 10**9, "13+")]:
        g = built[(built["n_coincident"] >= lo) & (built["n_coincident"] <= hi)]
        if len(g) < 5:
            continue
        r = g["R"].to_numpy()
        t = r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))
        print(f"{lbl:>13}{len(g):>9}{r.mean():>+10.4f}{t:>9.2f}"
              f"{np.percentile(r, 95):>9.3f}{(r > 0).mean()*100:>7.1f}%")

    print("\n=== THE MONOTONE QUESTION, stated as the prereg would read it ===")
    g = built.groupby("n_coincident")["R"].agg(["count", "mean"])
    g = g[g["count"] >= 5]
    m = g["mean"].to_numpy()
    rho = np.corrcoef(np.arange(len(m)), m)[0, 1]
    print(f"   buckets: {len(m)}   spearman-ish corr(bucket index, mean R) = {rho:+.3f}")
    print("   monotone increasing" if rho > 0.5 else
          ("   monotone-ish" if rho > 0.2 else
           "   NOT monotone increasing - the edge is not a coincidence-count effect"))

    print("\n=== HOW MUCH OF THE EDGE SITS IN THE TOP BUCKET? ===")
    tot_w = built["risk_usd"].sum()
    for frac in (0.5, 0.25):
        thr = built["n_coincident"].quantile(1 - frac)
        sub = built[built["n_coincident"] >= thr]
        share = sub["R"].clip(lower=0).sum() / built["R"].clip(lower=0).sum()
        print(f"   top {frac*100:.0f}% of trades by coincidence "
              f"(>= {thr:.0f} symbols): n={len(sub)}  mean R={sub['R'].mean():+.4f}  "
              f"carries {share*100:.0f}% of all positive R")

    print("\n=== BY CALENDAR YEAR, split at the median coincidence ===")
    built["y"] = pd.to_datetime(built["open"], utc=True).dt.year
    med = built["n_coincident"].median()
    for y, g in built.groupby("y"):
        hi_ = g[g["n_coincident"] > med]["R"]
        lo_ = g[g["n_coincident"] <= med]["R"]
        print(f"   {y}  n={len(g):>4}  all {g['R'].mean():+.4f}   "
              f"high-coincidence {hi_.mean() if len(hi_) else float('nan'):+.4f}"
              f" (n={len(hi_)})   rest {lo_.mean() if len(lo_) else float('nan'):+.4f}")

    out = "user_data/perp_short_out/coincidence.csv"
    built[["pair", "open", "close", "n_coincident", "R", "reason"]].to_csv(out, index=False)
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
