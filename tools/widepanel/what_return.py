"""What would this book actually return at a conventional risk size?

The freqtrade run reports +43.83% / CAGR 11.03% over 3.67 years, and that
number is close to meaningless as a statement about the STRATEGY: with
`stake_amount: unlimited` and `max_open_trades: 24`, notional is split equally,
so a -3.6% stop costs only 0.15% of the wallet per trade. The book is
under-risked by roughly 3x against the repo's own DEFAULT_RISK_FRACTION = 0.005.

This rebuilds the equity curve from the same trades under explicit risk-based
sizing, and — the part that actually decides the answer — caps AGGREGATE open
risk, because 72% of the trades share a timestamp with another trade. Sizing
each of those at 0.5% of equity independently would imply 8 simultaneous
full-risk positions, which is not a book anyone can hold.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
TRADES = ROOT / "shark_results" / "wide" / "subset_shark_shorts.csv"

RISK = 0.005          # the repo's own DEFAULT_RISK_FRACTION
MAX_OPEN_RISK = 0.03  # cap on total equity-at-risk across all open positions


def curve(t: pd.DataFrame, risk: float, cap: float) -> pd.Series:
    """Compounded equity, one observation per trade, sized by risk and capped
    by concurrent exposure. This file is the SHORT leg only."""
    t = t.sort_values("entry_time").reset_index(drop=True)
    eq, out = 1.0, []
    # list of (exit_time, risk_committed) currently at risk
    open_pos: list[tuple[pd.Timestamp, float]] = []
    for _, row in t.iterrows():
        open_pos = [(x, f) for x, f in open_pos if x > row.entry_time]
        used = sum(f for _, f in open_pos)
        f = min(risk, max(0.0, cap - used))
        if f > 0:
            eq *= (1.0 + f * row.r_net)
            open_pos.append((row.exit_time, f))
        out.append(eq)
    return pd.Series(out, index=t["entry_time"])


def concurrency(t: pd.DataFrame) -> np.ndarray:
    """Open positions over time, as a proper event stream.

    A first attempt concatenated entry/exit frames and set the index without
    sorting, so the cumsum ran over unsorted data and reported 512 concurrent
    positions out of 1,024 trades. Build the event stream explicitly.
    """
    ev = pd.DataFrame({
        "ts": pd.concat([t["entry_time"], t["exit_time"]], ignore_index=True),
        "d": np.concatenate([np.ones(len(t)), -np.ones(len(t))]),
    }).sort_values("ts", kind="mergesort")
    return np.cumsum(ev["d"].to_numpy())


def stats(c: pd.Series) -> dict:
    c = c / c.iloc[0]
    r = c.pct_change().dropna()
    years = (c.index[-1] - c.index[0]).days / 365.25
    dd = (c / c.cummax() - 1.0)
    return {
        "total_%": (c.iloc[-1] - 1) * 100,
        "cagr_%": ((c.iloc[-1]) ** (1 / years) - 1) * 100,
        "max_dd_%": dd.min() * 100,
        "sharpe": (r.mean() / r.std(ddof=1)) * np.sqrt(365 * 0.75) if r.std() else np.nan,
        "calmar": ((c.iloc[-1]) ** (1 / years) - 1) / abs(dd.min())
        if dd.min() else np.nan,
        "years": years,
    }


def main() -> int:
    t = pd.read_csv(TRADES, parse_dates=["entry_time", "exit_time"])
    print(f"short-leg trades on the 24-symbol subset: {len(t)}")
    print(f"mean r_net {t.r_net.mean():+.4f}   median {t.r_net.median():+.4f}   "
          f"win rate {(t.r_net > 0).mean():.1%}")
    print(f"mean holding {t.holding_bars.mean():.1f} bars\n")

    conc = concurrency(t)
    print(f"concurrent open positions: mean {conc.mean():.1f}  "
          f"p50 {np.percentile(conc, 50):.0f}  p90 {np.percentile(conc, 90):.0f}  "
          f"max {conc.max()}")
    print(f"-> at 0.5% risk each, the median moment has "
          f"{np.percentile(conc, 50) * 0.5:.1f}% of equity at risk; "
          f"the p90 has {np.percentile(conc, 90) * 0.5:.1f}%\n")

    rows = []
    for risk, cap in [(0.005, 1.0), (0.005, 0.03), (0.01, 0.03),
                      (0.01, 0.06), (0.02, 0.06)]:
        c = curve(t, risk, cap)
        s = stats(c)
        s.update(risk_per_trade=risk, cap_on_open_risk=cap,
                 effective_capped=f"{'yes' if cap < 1 else 'NO'}")
        rows.append(s)
        print(f"risk {risk:.1%}/trade, cap {cap:.0%} open risk -> "
              f"total {s['total_%']:+7.1f}%  CAGR {s['cagr_%']:+6.2f}%  "
              f"maxDD {s['max_dd_%']:6.2f}%  Sharpe {s['sharpe']:+.2f}  "
              f"Calmar {s['calmar']:+.2f}")

    pd.DataFrame(rows).to_csv(ROOT / "shark_results" / "wide" / "sizing.csv",
                              index=False)
    print("\nFor scale, buy-and-hold BTC over the same window: see "
          "PERP_SLOW_BACKTEST_2026-09-27.md (+177% on BTC/ETH 1h perps, "
          "2021-2025) and MULTI_STRATEGY_RESULT_2026-09-27.md (BTC spot "
          "CAGR 88.8%, maxDD 84.9%).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
