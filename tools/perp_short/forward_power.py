"""Power analysis for a FORWARD test of the N-ladder timing book.

WHY THIS FILE EXISTS
-------------------
Nine rounds produced a lead: on the most liquid slice of 515 Binance USD-M
perps, the frozen 4h short book returns +89.9% at measured COVID costs, Sharpe
0.67, maxDD 31.5%, 3 of 4 calendar years positive. It fails the project's
strictest test out of sample (by-timestamp t = 0.03) and its rung is
window-dependent. `RESEARCH_GOAL.md` §2.F.3 says a dry-run's duration must be set
by a preregistered power calculation, not by "run it for a few weeks and see".
So the honest closing action is to compute what a forward test would actually
require - in months - and let that number decide whether it is worth starting.

THE OBVIOUS REPAIR, AND WHY IT IS NOT BEING BUILT
-------------------------------------------------
The book's one real risk is bleeding in a crypto bull market: 2023 cost it -40.5%
on the 104-symbol version. The obvious repair is to scale exposure down when the
panel is in an uptrend - NOT to go long, which is the direction switch and was
already refuted (-58.7% vs -52.4%).

**That repair cannot be validated with any data this project has.** It would be
designed AFTER seeing 2023, and the only out-of-sample window (2025-2026) is a
falling market where the repair is a no-op, so the test has no power to detect
the benefit it was designed to produce. `AGENTS.md` §1a: a design that cannot
conclude is worse than none. It is recorded here and NOT built.

Run:
    $env:PERP_SHORT_DATADIR="user_data/data/wide526"
    .venv\\Scripts\\python.exe tools\\perp_short\\forward_power.py
"""

from __future__ import annotations

import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join("tools", "perp_short"))

import r_stats  # noqa: E402

STRAT = "PerpShort4hDeploy"
FULL = "user_data/lshape_out/n50/*.zip"
OOS = "user_data/wf_out/oos/n50/*.zip"
T_BAR = 2.0


def load(pattern: str) -> tuple[pd.DataFrame, float]:
    ap = max(glob.glob(pattern), key=os.path.getmtime)
    trades = sorted(r_stats.load_trades(ap, strategy=STRAT),
                    key=lambda t: t["open_date"])
    frames = r_stats.load_frames(sorted({t["pair"] for t in trades}))
    return r_stats.build(trades, frames, 5.0, 34.9), len(trades)


def main() -> int:
    print("FORWARD POWER ANALYSIS - the 4h short timing book at N=50\n")
    for label, pat in (("FULL SAMPLE 2023-03..2026-08", FULL),
                       ("OOS 2025-01..2026-08", OOS)):
        df, n = load(pat)
        r = df["R"].to_numpy()
        sd = float(r.std(ddof=1))
        mean = float(r.mean())
        idx = pd.to_datetime(df["open"], utc=True)
        by_ts = df.groupby(idx)["R"].mean().to_numpy()
        iat = r_stats.iat(by_ts)
        years = (idx.max() - idx.min()).total_seconds() / (365.25 * 86400)
        rate = n / years
        print(f"--- {label} ---")
        print(f"   trades {n}   over {years:.2f}y   -> {rate:.0f} trades/year")
        print(f"   mean R {mean:+.4f}   sd {sd:.4f}   mean/sd {mean/sd:.5f}")
        print(f"   IAT on the timestamp-averaged series: {iat:.2f}")
        for tname, need in (("naive", (T_BAR * sd / mean) ** 2),
                            ("by-timestamp (IAT-adjusted)",
                             (T_BAR * sd / mean) ** 2 * iat)):
            yrs = need / rate
            print(f"   trades needed for t={T_BAR} [{tname:<26}] "
                  f"{need:>8.0f}   = {yrs:>6.1f} years")
        print()

    print("=== THE HONEST CLOSING NUMBER ===")
    df, n = load(FULL)
    idx = pd.to_datetime(df["open"], utc=True)
    years = (idx.max() - idx.min()).total_seconds() / (365.25 * 86400)
    rate = n / years
    r = df["R"].to_numpy()
    mean, sd = float(r.mean()), float(r.std(ddof=1))
    iat = r_stats.iat(df.groupby(idx)["R"].mean().to_numpy())
    need_years = (T_BAR * sd / mean) ** 2 * iat / rate
    print(f"   event rate      : {rate:.0f} trades/year at N=50")
    print(f"   effect to detect: mean R {mean:+.4f}, sd {sd:.4f} (a 35R outlier")
    print(f"                      exists, which is why sd is so large)")
    print(f"   IAT             : {iat:.2f}")
    print(f"   a forward test reaching t=2.0 under the IAT treatment needs")
    print(f"   **{need_years:.1f} years** of trading.")
    print()
    print("   That is not a research programme this session can complete, and it is")
    print("   not a reason to start collecting on a hunch either. It IS a reason to")
    print("   start a DRY-RUN that costs nothing and produces exactly the series")
    print("   the test needs.")
    print()
    print("=== WHAT A FORWARD COLLECTION WOULD HAVE TO BE ===")
    print(f"   venue/instrument : Binance USD-M perps, the 25-300 liquidity band")
    print(f"   feature          : rvol(20)>=2.0, 20-bar Donchian breakdown, low-vol")
    print(f"                      regime filter, 4.0xATR entry-bar stop, 2R target,")
    print(f"                      42-bar time stop")
    print(f"   events needed    : ~{(T_BAR*sd/mean)**2*iat:,.0f} independent trades")
    print(f"   at ~{rate:.0f}/year  : ~{need_years:.1f} years")
    print("   recording        : EVERY trade, with entry timestamp, pair, R, and the")
    print("                      contemporaneous panel forward return - the last is")
    print("                      what makes the by-timestamp t computable at all,")
    print("                      and it is the field whose absence in the 10th bug")
    print("                      turned a missing measurement into a nan.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
