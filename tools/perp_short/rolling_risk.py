"""What living with this book actually looks like: rolling-window loss distribution.

WHY THIS AND NOT ANOTHER EXPERIMENT
-----------------------------------
A maximum drawdown is ONE number, and it is the wrong one to plan around. What a
person deciding to trade this needs is the distribution: how often is a rolling
year negative, how deep is the bad tail, and how long am I underwater.

It is also the last unexamined property of the delivered book. Every number
reported so far is a full-sample aggregate, which means the 3.4-year path is being
described by its best single observation.

WHAT IT IS NOT
---------------
This is descriptive. It introduces no parameter, re-runs no backtest, and
cannot convert a non-significant strategy into a significant one. If the tail is
worse than the headline, that is a fact about the delivered product, not a
finding that changes it.

It uses the account curve at MEASURED COVID costs (34.9 bps round trip), because
the engine's own no-slippage number is an upper bound by construction
(`docs/backtesting.md:562`).

Run:
    $env:PERP_SHORT_DATADIR="user_data/data/wide526"
    .venv\\Scripts\\python.exe tools\\perp_short\\rolling_risk.py
"""

from __future__ import annotations

import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join("tools", "perp_short"))

import r_stats  # noqa: E402
from cost_frontier import atr_at  # noqa: E402

STRAT = "PerpShort4hDeploy"
CASES = [("N=40", "user_data/wf_out/oos/n40/*.zip"),
         ("N=50", "user_data/lshape_out/n50/*.zip")]


def curve(trades, frames, fee=5.0, slip=34.9, risk=0.005, cap=0.25, lev=1.0):
    """Re-derive stakes from the running equity at MEASURED cost.

    risk defaults to 0.5% - the deployed setting from HOW_TO_RUN_2026-09-29,
    not the 1% the headline numbers were computed at. The drawdown profile at
    0.5% risk is the one that will actually be experienced.
    """
    eq = 100_000.0
    rows = []
    for t in trades:
        entry, close = float(t["open_rate"]), float(t["close_rate"])
        ts = pd.Timestamp(t["open_date"])
        atr = atr_at(frames, t["pair"], ts)
        if not (np.isfinite(atr) and atr > 0 and entry > 0):
            continue
        stake = min(risk * eq / (4.0 * (atr / entry)) / lev, eq * cap)
        qty = stake / entry * lev
        eq += ((entry - close) * qty
               - fee / 1e4 * (qty * entry + qty * close)
               - slip / 1e4 * qty * (entry + close) / 2.0
               - float(t.get("funding_fees") or 0.0) * (stake / float(t["stake_amount"])))
        rows.append({"date": t["close_date"], "equity": eq})
    return pd.DataFrame(rows)


def main() -> int:
    print("ROLLING-WINDOW LOSS DISTRIBUTION at measured COVID costs")
    print("risk 0.5% per trade (the deployed setting), 1x, 4xATR stop\n")
    for name, pat in CASES:
        c = glob.glob(pat)
        if not c:
            print(f"{name}: no export")
            continue
        trades = sorted(r_stats.load_trades(max(c, key=os.path.getmtime),
                                           strategy=STRAT),
                        key=lambda t: t["open_date"])
        frames = r_stats.load_frames(sorted({t["pair"] for t in trades}))
        df = curve(trades, frames)
        if df.empty:
            continue
        s = df.set_index(pd.to_datetime(df["date"], utc=True))["equity"]
        days = s.resample("1D").last().ffill()
        print(f"=== {name}   {len(trades)} trades, "
              f"{days.index[0].date()} -> {days.index[-1].date()} ===")
        print(f"   total {(days.iloc[-1]/days.iloc[0]-1)*100:+.1f}%   "
              f"max drawdown {((days.cummax()-days)/days.cummax()).max()*100:.1f}%")

        print(f"\n   {'window':>9}{'median':>10}{'p25':>10}{'p5':>10}"
              f"{'worst':>10}{'% neg':>8}{'% < -20%':>11}")
        for m, lbl in ((1, "1 month"), (3, "3 month"), (6, "6 month"),
                       (12, "12 month")):
            r = days.pct_change(m * 30).dropna()
            if r.empty:
                continue
            print(f"{lbl:>9}{r.median()*100:>9.1f}%{r.quantile(.25)*100:>9.1f}%"
                  f"{r.quantile(.05)*100:>9.1f}%{r.min()*100:>9.1f}%"
                  f"{(r<0).mean()*100:>7.0f}%{(r<-0.20).mean()*100:>10.0f}%")

        # drawdown duration
        peak = days.cummax()
        dd = (peak - days) / peak
        under = dd > 0.005
        runs, cur = [], 0
        for u in under:
            cur = cur + 1 if u else 0
            if cur:
                runs.append(cur)
        print(f"\n   time underwater (>0.5% below a prior peak): "
              f"{under.mean()*100:.0f}% of all days")
        if runs:
            print(f"   drawdown episodes: {len(runs)}   longest "
                  f"{max(runs)} days   median {int(np.median(runs))} days")
        worst = dd.idxmax()
        rec = days.loc[worst:]
        back = rec[rec >= days.loc[worst]]
        if len(back):
            print(f"   deepest drawdown reached {worst.date()} and took "
                  f"{(back.index[0]-worst).days} days to recover")

        print(f"\n   WORST 12-MONTH WINDOW: {days.pct_change(360).min()*100:+.1f}%")
        print(f"   -> that is the number to size against, not the "
              f"{(days.iloc[-1]/days.iloc[0]-1)*100:+.1f}% headline")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
