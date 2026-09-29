"""Time, capital and P&L summary for the wide-panel short-leg work.

Times are MEASURED by re-running the pipeline steps, not estimated. Wall-clock
figures for the interactive/literature work cannot be measured from inside a
script and are reported separately as approximations.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
WIDE = ROOT / "shark_data" / "wide"


def dir_size_mb(p: Path) -> float:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1e6


def timed(label: str, args: list[str]) -> float:
    t0 = time.time()
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    dt = time.time() - t0
    if r.returncode != 0:
        print(f"  !! {label} failed rc={r.returncode}")
        print(r.stdout[-500:], r.stderr[-500:])
    print(f"  {label:<34} {dt:7.1f} s")
    return dt


def main() -> int:
    print("=" * 78)
    print("DATA VOLUME ON DISK")
    print("=" * 78)
    for sub in ("klines_4h", "funding", "features"):
        p = WIDE / sub
        n = len(list(p.glob("*"))) if p.exists() else 0
        print(f"  {sub:<14} {n:>6} files  {dir_size_mb(p):9.1f} MB")
    print(f"  {'TOTAL':<14} {'':>6}        {dir_size_mb(WIDE):9.1f} MB")

    print("\n" + "=" * 78)
    print("COMPUTE TIME (measured, single machine, no GPU)")
    print("=" * 78)
    t_fetch = timed("fetch_wide (104 sym x 44mo)", [PY, "tools/widepanel/fetch_wide.py"])
    t_build = timed("build_panel + causality test", [PY, "tools/widepanel/build_panel.py"])
    t_fund = timed("check_funding", [PY, "tools/widepanel/check_funding.py"])
    t_run = timed("run_wide (4 cells x 3 regimes)",
                  [PY, "tools/widepanel/run_wide.py"])
    t_dep = timed("dependence diagnostic", [PY, "tools/widepanel/dependence.py"])
    t_legs = timed("leg decomposition", [PY, "tools/widepanel/legs.py"])
    t_short = timed("shortleg frozen gates", [PY, "tools/widepanel/shortleg.py"])
    t_ft = timed("freqtrade backtesting (24 pairs)",
                 [PY, "-m", "freqtrade", "backtesting",
                  "--config", "user_data/config_wide_ft.json",
                  "--datadir", "user_data/data/wide_ft",
                  "--strategy", "ShortBreakout4h",
                  "--timerange", "20230101-20260901"])
    total = t_fetch + t_build + t_fund + t_run + t_dep + t_legs + t_short + t_ft
    print(f"  {'-'*34} {'-'*9}")
    print(f"  {'TOTAL measured pipeline':<34} {total:7.1f} s  "
          f"= {total/60:.1f} min")

    print("\n" + "=" * 78)
    print("TRADE COUNT AND CAPITAL")
    print("=" * 78)
    t = pd.read_csv(ROOT / "shark_results" / "wide" / "subset_shark_shorts.csv",
                    parse_dates=["entry_time", "exit_time"])
    t = t[(t.exit_time >= "2023-01-01") & (t.exit_time <= "2026-09-01")]
    n = len(t)
    span_y = (t.exit_time.max() - t.entry_time.min()).days / 365.25
    print(f"  trades on the 24-pair subset : {n}")
    print(f"  span                         : {span_y:.2f} years")
    print(f"  trades / year                : {n/span_y:.0f}")
    print(f"  mean r_net                   : {t.r_net.mean():+.4f} R")
    print(f"  median r_net                 : {t.r_net.median():+.4f} R  "
          f"<- the typical trade loses ~1R")
    print(f"  win rate                     : {(t.r_net > 0).mean():.1%}")
    print(f"  mean holding                 : {t.holding_bars.mean():.1f} bars "
          f"= {t.holding_bars.mean()*4/24:.1f} days")

    STOP = 0.036
    print("\n  Capital required, by risk size "
          "(notional = risk / stop):")
    print(f"  {'risk/trade':>10} {'notional/trade':>15} {'notional @ median 4 open':>26}")
    for r in (0.005, 0.01, 0.02):
        print(f"  {r:>9.1%} {r/STOP:>14.1%} {4*r/STOP:>25.1%}")
    print("  -> at 0.5% risk and ~4 concurrent positions, a book needs about")
    print("     56% of equity deployed at 1x, or 19% at 3x leverage.")

    print("\n" + "=" * 78)
    print("P&L ON A CONCRETE ACCOUNT (24 pairs, 2023-01-01 -> 2026-09-01)")
    print("=" * 78)
    sys.path.insert(0, str(ROOT))
    from tools.widepanel.what_return import curve, stats   # noqa: E402

    print(f"  {'account':>10} {'risk':>6} {'cap':>5} {'final $':>12} "
          f"{'P&L $':>11} {'P&L %':>8} {'CAGR %':>8} {'maxDD %':>9}")
    for acct, risk, cap in [(10_000, 0.005, 0.03), (100_000, 0.005, 0.03),
                            (100_000, 0.01, 0.03), (100_000, 0.01, 0.06)]:
        c = curve(t, risk, cap)
        s = stats(c)
        mult = c.iloc[-1] / c.iloc[0]
        print(f"  {acct:>10,} {risk:>5.1%} {cap:>4.0%} {acct*mult:>12,.0f} "
              f"{acct*(mult-1):>11,.0f} {s['total_%']:>+7.1f}% "
              f"{s['cagr_%']:>+7.1f}% {s['max_dd_%']:>8.1f}%")

    print("\n  Turnover on a $100k account at 0.5% risk:")
    notional_per_trade = 100_000 * 0.005 / STOP
    total_notional = notional_per_trade * n
    print(f"    {notional_per_trade:,.0f} USDT per trade x {n} trades "
          f"= {total_notional/1e6:.1f}M USDT over {span_y:.1f}y "
          f"= {total_notional/span_y/365:,.0f} USDT/day")
    print("    (the measured depth cap for the THINNEST name is 0.8M-3.9M/day,"
          "\n     so capacity is not binding at retail size)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
