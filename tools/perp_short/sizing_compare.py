"""Compare the coincidence-sized book against the unsized one, in R and in risk.

`PREREG_SIZING_COINCIDENCE_2026-09-29.md` gates on C-2..C-5, and C-4 is the
important one: **the sized book's MAX DRAWDOWN must be at least 20% lower at the
same total risk.** A rule that improves mean R but leaves the drawdown alone has
not addressed the stated problem, and the prereg says to reject it on that basis
alone.

Total risk is matched by construction (base risk divided by the mean size
multiplier, 0.5695), so this is a redistribution and not a leverage change, and
the realised trade count and peak concurrency are printed so that can be checked
rather than believed.

Run:
    $env:PERP_SHORT_DATADIR="user_data/data/wide526"
    .venv\\Scripts\\python.exe tools\\perp_short\\sizing_compare.py
"""

from __future__ import annotations

import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join("tools", "perp_short"))

import r_stats  # noqa: E402
from cost_frontier import atr_at  # noqa: E402  (it lives there, not in r_stats)

ARMS = {
    "unsized  N=50 ": ("user_data/lshape_out/n50/*.zip", "PerpShort4hDeploy"),
    "sized    N=50 ": ("user_data/sizing_out/full/n50/*.zip", "PerpShort4hSizing"),
    "unsized  N=100": ("user_data/lshape_out/n100/*.zip", "PerpShort4hDeploy"),
    "sized    N=100": ("user_data/sizing_out/full/n100/*.zip", "PerpShort4hSizing"),
}


def equity_curve(trades, frames, fee=5.0, slip=34.9, risk=0.01, cap=0.25, lev=1.0):
    eq = 100_000.0
    rows = []
    for t in trades:
        entry, close = float(t["open_rate"]), float(t["close_rate"])
        ts = pd.Timestamp(t["open_date"])
        atr = atr_at(frames, t["pair"], ts)
        if not (np.isfinite(atr) and atr > 0 and entry > 0):
            continue
        notional = risk * eq / (4.0 * (atr / entry))
        stake = min(notional / lev, eq * cap)
        qty = stake / entry * lev
        gross = (entry - close) * qty
        fee_c = fee / 1e4 * (qty * entry + qty * close)
        slip_c = slip / 1e4 * qty * (entry + close) / 2.0
        fund = float(t.get("funding_fees") or 0.0) * (stake / float(t["stake_amount"]))
        eq += gross - fee_c - slip_c - fund
        rows.append({"date": t["close_date"], "equity": eq})
    return pd.DataFrame(rows)


def main() -> int:
    print("COINCIDENCE SIZING vs UNSIZED, at MATCHED total risk")
    print("cost regime: measured COVID 34.9 bps round trip\n")
    print(f"{'arm':<15}{'trades':>8}{'meanR':>9}{'t naive':>9}{'t by-ts':>9}"
          f"{'account':>10}{'maxDD':>8}{'CAGR':>8}{'peakConc':>10}")
    res = {}
    for name, (pat, strat) in ARMS.items():
        c = glob.glob(pat)
        if not c:
            print(f"{name:<15} NO EXPORT")
            continue
        ap = max(c, key=os.path.getmtime)
        trades = sorted(r_stats.load_trades(ap, strategy=strat),
                        key=lambda t: t["open_date"])
        pairs = sorted({t["pair"] for t in trades})
        frames = r_stats.load_frames(pairs)
        df = r_stats.build(trades, frames, 5.0, 34.9)
        r = df["R"].to_numpy()
        t = r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))
        idx = pd.to_datetime(df["open"], utc=True)
        tts = r_stats.tstat(df.groupby(idx)["R"].mean().to_numpy())[0]
        eq = equity_curve(trades, frames)
        acc = eq["equity"].iloc[-1] / 100_000.0 - 1
        dd = float((eq["equity"].cummax() - eq["equity"]).div(
            eq["equity"].cummax()).max())
        yrs = (pd.to_datetime(eq["date"].iloc[-1])
               - pd.to_datetime(eq["date"].iloc[0])).days / 365.25
        cagr = (eq["equity"].iloc[-1] / 100_000.0) ** (1 / max(yrs, 1e-9)) - 1
        conc, ev = 0, []
        for tr in trades:
            ts, te = pd.Timestamp(tr["open_date"]), pd.Timestamp(tr["close_date"])
            ev = [e for e in ev if e > ts]
            ev.append(te)
            conc = max(conc, len(ev))
        res[name] = dict(meanR=float(r.mean()), t=float(t), acc=float(acc),
                         dd=float(dd), n=len(r), conc=conc)
        print(f"{name:<15}{len(r):>8}{r.mean():>+9.4f}{t:>9.2f}{tts:>9.2f}"
              f"{acc*100:>9.1f}%{dd*100:>7.1f}%{cagr*100:>7.1f}%{conc:>10d}")

    print("\n=== GATES ===")
    for n in (50, 100):
        a = res.get(f"unsized  N={n} ")
        b = res.get(f"sized    N={n} ")
        if not a or not b:
            continue
        dd_red = 1 - b["dd"] / a["dd"]
        mr_chg = b["meanR"] / a["meanR"] - 1
        print(f"  N={n}")
        print(f"    C-2 meanR still positive  : "
              f"{'PASS' if b['meanR'] > 0 else 'FAIL'}  ({b['meanR']:+.4f})")
        print(f"    C-3 peak exposure not up : "
              f"{'PASS' if b['conc'] <= a['conc'] else 'FAIL'} "
              f"({b['conc']} vs {a['conc']})")
        print(f"    C-4 maxDD >=20% lower   : "
              f"{'PASS' if dd_red >= 0.20 else 'FAIL'}  "
              f"(reduction {dd_red*100:+.1f}%)")
        print(f"    C-5 meanR not worse -25%: "
              f"{'PASS' if mr_chg >= -0.25 else 'FAIL'}  "
              f"(change {mr_chg*100:+.1f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
