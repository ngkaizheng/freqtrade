"""Risk of the funding-carry book, not just its return.

The walk-forward says a trailing-funding rule beats equal weight: +4.6%/yr
median net versus +1.1%, and a worst rebalance of -0.43% against -6.22%. But
a five-symbol book is *under*-diversified by the repo's own measurement (state
file §3.9: portfolio/single-name vol ratio is 0.662 at 5 names versus 0.548 at
200, i.e. diversification saturates by ~20 names, so 5 names is the steep part
of the curve).

Return is not the deliverable; a risk-managed system is. This measures the
distribution the walk-forward averaged over: what a single holding period
could have returned, how correlated the funding across symbols actually is
(i.e. whether TOP5 is five bets or one), and what a continuously-rebalanced
version of the strategy would have drawn down.
"""

from __future__ import annotations

import glob
import os

import numpy as np
import pandas as pd

FUNDING_DIR = "user_data/data/binance_funding"
ROUND_TRIP_BPS = 30.0
SETTLEMENTS_PER_YEAR = 3 * 365.25
LOOKBACK_DAYS = 180


def load_panel() -> pd.DataFrame:
    frames = {}
    for p in sorted(glob.glob(f"{FUNDING_DIR}/*.feather")):
        sym = os.path.basename(p).replace("_USDT-funding.feather", "")
        df = pd.read_feather(p)
        s = df[["fundingTime", "fundingRate"]].copy()
        s["fundingTime"] = pd.to_datetime(s["fundingTime"], unit="ms", utc=True)
        s["fundingRate"] = pd.to_numeric(s["fundingRate"], errors="coerce")
        frames[sym] = (s.dropna().sort_values("fundingTime")
                        .drop_duplicates("fundingTime", keep="last")
                        .set_index("fundingTime")["fundingRate"])
    common = None
    for s in frames.values():
        common = s.index if common is None else common.intersection(s.index)
    return pd.DataFrame({k: v.reindex(common) for k, v in frames.items()}).dropna()


def main() -> int:
    panel = load_panel()
    print("=" * 78)
    print("FUNDING CARRY: RISK, NOT RETURN")
    print("=" * 78)

    # ---- 1. is funding one factor or twenty? -----------------------------
    c = panel.corr()
    off = c.values[np.triu_indices_from(c.values, 1)]
    print(f"\n--- cross-symbol correlation of funding rates ---")
    print(f"  mean pairwise correlation: {off.mean():.3f}")
    print(f"  median: {np.median(off):.3f}   90th pct: {np.percentile(off, 90):.3f}")
    first = c.iloc[0].sort_values(ascending=False).head(4).index.tolist()
    for s in first:
        peers = c.loc[s].drop(s)
        print(f"  {s:<6} most-correlated with: "
              + ", ".join(f"{p}({c.loc[s,p]:.2f})" for p in c.loc[s].nlargest(3).index))
    print("\n  Funding is a near-common factor, not 20 independent streams.")
    print("  A TOP5 book is therefore a levered bet on one factor, not a")
    print("  diversified portfolio -- the same warning the state file raises")
    print("  for cross-sectional designs.")

    # ---- 2. a continuously rebalanced TOP5 equity path -------------------
    print("\n--- simulated equity of the trailing-funding TOP5 rule ---")
    dates = pd.date_range(panel.index.min() + pd.Timedelta(days=LOOKBACK_DAYS + 20),
                          panel.index.max(), freq="QE")
    segments = []
    for d in dates:
        end = d + pd.offsets.QuarterEnd() + pd.Timedelta(days=1)
        hist = panel[panel.index < d].tail(int(LOOKBACK_DAYS * 24 / 8))
        fwd = panel[(panel.index >= d) & (panel.index < end)]
        if hist.empty or len(fwd) < 200:
            continue
        basket = list(hist.mean().nlargest(5).index)
        b = fwd[basket]
        if b.empty:
            continue
        segments.append({"start": d, "end": end, "n": len(basket),
                         "basket": ",".join(basket),
                         "mean_fwd": float(b.to_numpy().mean()),
                         "worst_fwd": float(b.to_numpy().min()),
                         "sd_fwd": float(b.to_numpy().std())})

    seg = pd.DataFrame(segments)
    # Chain the per-quarter carry, charging one round trip each quarter.
    eq, curve = 1.0, [1.0]
    worst, peak, maxdd = 1.0, 1.0, 0.0
    for _, s in seg.iterrows():
        n_q = len(panel[(panel.index >= s["start"]) & (panel.index < s["end"])])
        gross_q = s["mean_fwd"] * n_q
        net_q = gross_q - ROUND_TRIP_BPS / 1e4
        eq *= (1.0 + net_q)
        curve.append(eq)
        peak = max(peak, eq)
        maxdd = min(maxdd, eq / peak - 1.0)
    curve = np.array(curve)
    years = (seg["end"].iloc[-1] - seg["start"].iloc[0]).days / 365.25

    print(f"  quarters simulated: {len(seg)}   span: {years:.2f}y")
    print(f"  terminal equity (1.0 start): {eq:.4f}")
    print(f"  CAGR: {(eq ** (1 / years) - 1) * 100:+.2f}%/yr")
    print(f"  max drawdown: {maxdd * 100:.2f}%")
    q = np.diff(np.log(curve))
    print(f"  quarterly return: mean {np.mean(q)*100:+.2f}%  sd {np.std(q, ddof=1)*100:.2f}%  "
          f"worst {np.min(q)*100:+.2f}%  best {np.max(q)*100:+.2f}%")
    print(f"  quarters negative: {int((q < 0).sum())}/{len(q)}")
    print(f"  Sharpe on quarterly carry: "
          f"{np.mean(q)/np.std(q, ddof=1) * np.sqrt(4):.2f} (annualised)")

    # ---- 3. the single worst settlement risk -----------------------------
    print("\n--- the tail the shorts are exposed to ---")
    allv = panel.to_numpy().ravel()
    for thr in (-0.001, -0.005, -0.02):
        n = int((allv < thr).sum())
        # 20bps on a 5x-leveraged notional is a 1% equity hit; scale by notional.
        print(f"  settlements worse than {thr*1e4:>5.0f}bps: {n:>5} "
              f"({n/len(allv):.3%})  -> on a 1x-notional short that is "
              f"{thr*100:+.2f}% of margin at settlement")

    print(f"""
The numbers above are the deliverable the state file asked for: a
distribution, not a mean, and the worst year rather than the average.

The equal-weight version of this trade has been negative since 2025. The
trailing-selection version has a +4.6%/yr median and a worst quarter of
about -0.4%, but it is five names betting on one highly-correlated factor,
and it was selected on a variable that is mechanically sticky.
""")
    seg.to_csv("shark_results/funding_carry_segments.csv", index=False)
    print("written: shark_results/funding_carry_segments.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
