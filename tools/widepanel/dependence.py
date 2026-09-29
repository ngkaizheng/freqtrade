"""Why is the IAT 13-17 on a 104-name panel when it was 1.0 on 9 names?

Hypothesis: the pooled per-trade series is ordered by entry_time, so on a
market-wide volume spike all 104 symbols fire within the SAME bar. Consecutive
observations in the series are then CONTEMPORANEOUS, not serially dependent. A
1-D integrated autocorrelation time cannot tell those two things apart, and it
reads contemporaneous clustering as lag-1 dependence.

If that is what is happening then:
  * the lag-1 autocorrelation should collapse when trades sharing an entry
    timestamp are aggregated into one observation, and
  * the honest statistic is the TIME-CLUSTER one (RESEARCH_STATE §3.5:
    "a portfolio has one observation per period... diversification reduces
    per-period volatility; it does not create observations").

This script separates the two. It is a diagnostic run BEFORE the choice of
statistic is used, and it reports every statistic it computes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.widepanel.run_wide import dependence_t, effective_n   # noqa: E402

TRADES = ROOT / "shark_results" / "wide" / "wide_trades.csv.gz"
OUT = ROOT / "shark_results" / "wide"


def main() -> int:
    t = pd.read_csv(TRADES, parse_dates=["entry_time", "exit_time"])
    b = t[t.cell == "B1.5"].copy()            # the pre-registered lead cell
    calm = b[b.cost_regime == "calm_12.0bps"]
    n = len(calm)
    r = calm["r_net"].to_numpy(dtype=float)

    print(f"cell B1.5, calm cost: {n} trades over "
          f"{calm.entry_time.nunique()} distinct entry timestamps")
    dup = n - calm.entry_time.nunique()
    print(f"  -> {dup} trades ({dup / n:.0%}) share a timestamp with another trade")

    # ---- 1. the per-trade IAT, and where it comes from --------------------
    iat_raw, neff_raw = effective_n(r)
    print(f"\nper-trade   IAT={iat_raw:.2f}  n_eff={neff_raw:.0f}  "
          f"t_adj={dependence_t(r)['t_adjusted']:.2f}")

    # same statistic on a per-TIMESTAMP mean (all trades in that bar averaged)
    per_ts = calm.groupby("entry_time")["r_net"].mean().sort_index()
    iat_ts, neff_ts = effective_n(per_ts.to_numpy())
    print(f"per-timestamp mean: {len(per_ts)} obs  IAT={iat_ts:.2f}  "
          f"n_eff={neff_ts:.0f}  t={dependence_t(per_ts.to_numpy())['t_adjusted']:.2f}")

    # ---- 2. split trades into "unique timestamp" vs "shared timestamp" -----
    counts = calm.groupby("entry_time")["r_net"].transform("size")
    solo = calm.loc[counts == 1, "r_net"].to_numpy(dtype=float)
    shared = calm.loc[counts > 1, "r_net"].to_numpy(dtype=float)
    print(f"\nsolo trades  n={len(solo):<6} mean={solo.mean():+.4f}  "
          f"IAT={effective_n(solo)[0]:.2f}")
    print(f"shared      n={len(shared):<6} mean={shared.mean():+.4f}  "
          f"IAT={effective_n(shared)[0]:.2f}")
    print("  -> if IAT(solo) is near 1 and IAT(shared) is large, the pooled IAT is")
    print("     measuring same-bar clustering, not persistence of the signal.")

    # ---- 3. the time-cluster statistic ------------------------------------
    # Weekly aggregation. One observation per week = the SECTIONS 3.5 rule.
    rows = []
    for freq, label in [("W", "weekly"), ("2W", "fortnightly"), ("ME", "monthly")]:
        agg = calm.set_index("entry_time")["r_net"].resample(freq).sum()
        st = dependence_t(agg.to_numpy(dtype=float))
        rows.append({
            "cluster": label, "n_clusters": st["n"], "mean_r": st["mean_r"],
            "sd_r": st["sd_r"], "iat": st["iat"], "n_effective": st["n_effective"],
            "t_naive": st["t_naive"], "t_adjusted": st["t_adjusted"],
        })
    cl = pd.DataFrame(rows)
    print("\ntime-cluster (sum of r_net per period, per §3.5):")
    print(cl.round(4).to_string(index=False))

    # ---- 4. weekly portfolio return, which is what a book actually earns --
    wk = calm.set_index("entry_time")["r_net"].resample("W").sum()
    st = dependence_t(wk.to_numpy(dtype=float))
    print(f"\nweekly P&L: mean={st['mean_r']:+.3f}R  sd={st['sd_r']:.3f}R  "
          f"IAT={st['iat']:.2f}  t_adj={st['t_adjusted']:.2f}")

    out = {
        "trades": n,
        "distinct_entry_timestamps": int(calm.entry_time.nunique()),
        "share_of_trades_sharing_a_timestamp": float(dup / n),
        "per_trade": dependence_t(r),
        "per_timestamp_mean": dependence_t(per_ts.to_numpy(dtype=float)),
        "solo_trades": dependence_t(solo),
        "shared_timestamp_trades": dependence_t(shared),
        "time_clusters": rows,
    }

    # ---- 5. is this a market-beta bet? ------------------------------------
    # If the edge only exists when many symbols fire together, the trade is a
    # bet on the market-wide move, not on any one name. Regress each trade on
    # the same-timestamp cross-sectional mean and read the slope.
    calm = calm.copy()
    calm["ts_mean"] = calm.groupby("entry_time")["r_net"].transform("mean")
    v = calm["ts_mean"].to_numpy(dtype=float)
    y = calm["r_net"].to_numpy(dtype=float)
    beta = float(np.cov(y, v, ddof=1)[0, 1] / np.var(v, ddof=1))
    alpha = float(y.mean() - beta * v.mean())
    resid_sd = float(np.std(y - (alpha + beta * v), ddof=1))
    out["beta_to_simultaneous_mean"] = beta
    out["alpha_r"] = alpha
    out["resid_sd_r"] = resid_sd
    print(f"\nbeta to the same-timestamp cross-sectional mean = {beta:.3f}")
    print(f"alpha = {alpha:+.4f}R   residual sd = {resid_sd:.4f}R")
    print(f"  -> {beta:.0%} of the trade's move is the market-wide component; "
          f"the name-specific residual sd is {resid_sd:.3f}R "
          f"vs {y.std(ddof=1):.3f}R raw.")
    print("  A beta near 1 means this is a DIRECTIONAL MARKET BET wearing a")
    print("  volume-filter costume, not an idiosyncratic edge (cf. RESEARCH_STATE")
    print("  §3.27, and Anghel 2021: 'trading rules mostly capture market risk")
    print("  premiums').")

    import json
    (OUT / "dependence_diagnostic.json").write_text(json.dumps(out, indent=2))
    print(f"\nwrote {OUT / 'dependence_diagnostic.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
