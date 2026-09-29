"""Funding carry, year by year, and by symbol.

The naive pooled average is +0.924 bps per 8h, i.e. ~10%/yr gross for holding a
short perpetual against a long spot. That number is a backward-looking mean
over a period when funding was structurally higher, and the single question
that decides the strategy is whether it persists.

This computes the thing that matters: annualised gross funding by calendar
year, per symbol and pooled, plus the tail behaviour. A carry that decayed to
zero would be a historical artefact; a carry that held would be the
"observable cashflow" the state file is betting on.

No costs are deducted here on purpose. The point of this pass is the shape of
the raw series; costs come next and must be applied to the same series.
"""

from __future__ import annotations

import glob
import os

import numpy as np
import pandas as pd

FUNDING_DIR = "user_data/data/binance_funding"


def load_all() -> dict[str, pd.DataFrame]:
    out = {}
    for p in sorted(glob.glob(f"{FUNDING_DIR}/*.feather")):
        sym = os.path.basename(p).replace("_USDT-funding.feather", "")
        df = pd.read_feather(p)
        s = df[["fundingTime", "fundingRate"]].copy()
        s["fundingTime"] = pd.to_datetime(s["fundingTime"], unit="ms", utc=True)
        s["fundingRate"] = pd.to_numeric(s["fundingRate"], errors="coerce")
        s = (s.dropna().sort_values("fundingTime")
               .drop_duplicates("fundingTime", keep="last").set_index("fundingTime"))
        out[sym] = s
    return out


def main() -> int:
    frames = load_all()
    common = None
    for s in frames.values():
        common = s.index if common is None else common.intersection(s.index)
    panel = pd.DataFrame({k: v["fundingRate"].reindex(common) for k, v in frames.items()})
    panel = panel.dropna()
    print("=" * 78)
    print("FUNDING CARRY: shape of the raw series, no costs deducted yet")
    print("=" * 78)
    print(f"common panel: {len(panel):,} settlements x {panel.shape[1]} symbols, "
          f"{panel.index.min().date()} -> {panel.index.max().date()}\n")

    SETTLEMENTS_PER_YEAR = 3 * 365.25

    # ---- 1. annualised by year, pooled -----------------------------------
    print("--- pooled gross funding by calendar year (bps/8h and %/yr) ---")
    rows = []
    for year, g in panel.groupby(panel.index.year):
        arr = g.to_numpy()
        m = float(arr.mean())
        rows.append({
            "year": int(year), "n_settlements": int(len(g)),
            "mean_bps": m * 1e4, "median_bps": float(np.median(arr)) * 1e4,
            "pct_positive": float((arr > 0).mean()),
            "annualised_pct": m * SETTLEMENTS_PER_YEAR * 100,
        })
    by_year = pd.DataFrame(rows)
    print(by_year.round(3).to_string(index=False))

    # ---- 2. same, per symbol, split into halves -------------------------
    print("\n--- pooled annualised % by period, per symbol ---")
    mid = common.min() + (common.max() - common.min()) / 2
    per = []
    for sym in panel.columns:
        s = panel[sym]
        early = s[s.index < mid].mean() * SETTLEMENTS_PER_YEAR * 100
        late = s[s.index >= mid].mean() * SETTLEMENTS_PER_YEAR * 100
        y1 = s[s.index < "2023-01-01"].mean() * SETTLEMENTS_PER_YEAR * 100
        y25 = s[s.index >= "2025-01-01"].mean() * SETTLEMENTS_PER_YEAR * 100
        per.append({"symbol": sym, "early_%/yr": early, "late_%/yr": late,
                    "pre2023_%/yr": y1, "since2025_%/yr": y25,
                    "decay_ratio": (late / early) if early else np.nan})
    p = pd.DataFrame(per).sort_values("since2025_%/yr", ascending=False)
    print(p.round(2).to_string(index=False))
    print(f"\n  median pre-2023 : {p['pre2023_%/yr'].median():+.2f}%/yr")
    print(f"  median since-2025: {p['since2025_%/yr'].median():+.2f}%/yr")
    print(f"  symbols whose carry DECAYED (late < early): "
          f"{(p['late_%/yr'] < p['early_%/yr']).sum()}/{len(p)}")

    # ---- 3. tail behaviour ----------------------------------------------
    print("\n--- tail: the shorts are short volatility ---")
    allv = panel.to_numpy().ravel()
    for q in (0.001, 0.01, 0.5, 0.99, 0.999):
        print(f"  q{q*100:>6.1f}: {np.quantile(allv, q) * 1e4:+9.2f} bps")
    print(f"  worst single settlement: {allv.min() * 1e4:+.1f} bps")
    print(f"  fraction of settlements worse than -10 bps: "
          f"{(allv < -0.001).mean():.3%}")
    print(f"  fraction worse than -50 bps: {(allv < -0.005).mean():.3%}")

    # ---- 4. what a single-symbol book would have earned ------------------
    print("\n--- single-symbol carry, full period, annualised % ---")
    single = (panel.mean() * SETTLEMENTS_PER_YEAR * 100).sort_values(ascending=False)
    print(single.round(2).to_string())
    print(f"\n  best {single.index[0]}: {single.iloc[0]:+.2f}%/yr    "
          f"worst {single.index[-1]}: {single.iloc[-1]:+.2f}%/yr")
    print(f"  median: {single.median():+.2f}%/yr")
    print(f"  equal-weight across all 20: "
          f"{panel.to_numpy().mean() * SETTLEMENTS_PER_YEAR * 100:+.2f}%/yr")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
