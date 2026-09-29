"""Does the low-vol filter RAISE return, or only raise Sharpe?

The filter improves per-trade edge (+15% on the short leg) but drops 43% of the
trades. Those two facts point in opposite directions for TOTAL edge:

    A1.5 short:  7,279 trades x 0.1533 R = 1,116 R
    B1.5 short:  4,144 trades x 0.1757 R =   728 R

So on raw summed R the filter DESTROYS 35% of the edge. It is only worth
having if the book is constrained by something other than trade count — and the
thing that constrains it is CONCURRENT RISK, because 72% of trades fire in
clusters. The right comparison is therefore return per unit of open risk, and
that has to be measured, not argued.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.widepanel.run_wide import dependence_t                 # noqa: E402
from tools.widepanel.what_return import curve, stats             # noqa: E402

TRADES = ROOT / "shark_results" / "wide" / "wide_trades.csv.gz"


def open_risk_profile(t: pd.DataFrame) -> pd.Series:
    """Equity-at-risk over time, assuming each trade risks a fixed fraction."""
    ev = pd.DataFrame({
        "ts": pd.concat([t["entry_time"], t["exit_time"]], ignore_index=True),
        "d": np.concatenate([np.ones(len(t)), -np.ones(len(t))]),
    }).sort_values("ts", kind="mergesort")
    return np.cumsum(ev["d"].to_numpy())


def main() -> int:
    t = pd.read_csv(TRADES, parse_dates=["entry_time", "exit_time"])
    rows = []
    for cname in ["calm_12.0bps"]:
        for cell in sorted(t.cell.unique()):
            b = t[(t.cost_regime == cname) & (t.cell == cell)]
            sh = b[b.direction == "short"]
            if sh.empty:
                continue
            conc = open_risk_profile(sh)
            span_y = (sh.exit_time.max() - sh.entry_time.min()).days / 365.25

            # total edge per calendar year
            total_r = sh.r_net.sum()
            r_per_yr = total_r / span_y

            # equity curve under a fixed concurrent-risk budget
            c = curve(sh, 0.005, 0.03)
            s = stats(c)

            rows.append({
                "cell": cell,
                "n": len(sh),
                "net_r_per_trade": sh.r_net.mean(),
                "total_R": total_r,
                "R_per_year": r_per_yr,
                "mean_concurrent": conc.mean(),
                "p90_concurrent": np.percentile(conc, 90),
                "R_per_concurrent": r_per_yr / max(conc.mean(), 1e-9),
                "cagr_%": s["cagr_%"],
                "maxdd_%": s["max_dd_%"],
                "sharpe": s["sharpe"],
            })

    d = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    print("SHORT LEG, calm cost, all four cells")
    print("=" * 118)
    print(d.round(3).to_string(index=False))

    print("\nWhich cell maximises RETURN at a fixed concurrent-risk budget?")
    best = d.loc[d.cagr_.idxmax()] if hasattr(d, "cagr_") else d.loc[d["cagr_%"].idxmax()]
    print(f"  -> highest CAGR: {best.cell}  ({best['cagr_%']:+.1f}%/yr, "
          f"maxDD {best['maxdd_%']:.1f}%, Sharpe {best.sharpe:.2f})")

    print("\nRaw summed R vs CAGR — they disagree, which is the whole point:")
    for _, r in d.iterrows():
        print(f"  {r.cell:<6} total {r.total_R:7.0f}R over the sample | "
              f"per year {r.R_per_year:6.0f}R | CAGR {r['cagr_%']:+6.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
