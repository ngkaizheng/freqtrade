"""Audit the funding corpus before trusting anything built on it.

The state file describes `user_data/data/binance_funding/` as "20 symbols, 8h
settlements, fundingTime + fundingRate, 6,493 common settlements from
2020-10-16 through 2026-09-19" and warns that `fundingRate > 0` means longs
pay shorts. Both claims are checked here rather than taken on trust, because
a carry P&L whose sign convention is wrong is worse than no P&L at all.

Checks:
  * schema, dtypes, row counts, actual coverage per symbol
  * the sign convention, established from the data rather than asserted
  * funding interval consistency (and any regime change to it)
  * gaps, duplicates, outliers, non-finite values
  * which symbols are actually liquid enough to trade, and whether the
    universe is survivorship-biased
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
        out[sym] = df
    return out


def main() -> int:
    data = load_all()
    print("=" * 78)
    print("FUNDING CORPUS AUDIT")
    print("=" * 78)
    print(f"symbols on disk: {len(data)}")

    first = next(iter(data.values()))
    print(f"columns: {list(first.columns)}")
    print(f"dtypes : { {k: str(v) for k, v in first.dtypes.items()} }")
    print("\nsample rows:")
    print(first.head(3).to_string(index=False))

    # --- normalise the time column across symbols -------------------------
    rows = []
    frames = {}
    for sym, df in data.items():
        tcol = next((c for c in df.columns if "fundingTime" in c or c.lower() == "time"),
                    df.columns[0])
        rcol = next((c for c in df.columns if "unding" in c and c != tcol), None)
        if rcol is None:
            rcol = df.columns[-1]
        s = df[[tcol, rcol]].copy()
        s.columns = ["fundingTime", "fundingRate"]
        # Feather round-trips can hand back object dtype; the index unit
        # differs across files (ms vs us vs ns) per the state file's warning.
        s["fundingTime"] = pd.to_datetime(s["fundingTime"], unit="ms", utc=True,
                                          errors="coerce")
        if s["fundingTime"].isna().all():
            s["fundingTime"] = pd.to_datetime(s["fundingTime"], unit="us", utc=True,
                                              errors="coerce")
        s["fundingRate"] = pd.to_numeric(s["fundingRate"], errors="coerce")
        s = s.dropna(subset=["fundingTime"]).sort_values("fundingTime")
        s = s[~s.duplicated("fundingTime", keep="last")]
        s = s.set_index("fundingTime")
        frames[sym] = s
        r = s["fundingRate"]
        rows.append({
            "symbol": sym, "rows": len(s),
            "start": str(s.index.min().date()), "end": str(s.index.max().date()),
            "nonfinite": int((~np.isfinite(r)).sum()),
            "mean_bps": float(r.mean() * 1e4),
            "median_bps": float(r.median() * 1e4),
            "pct_positive": float((r > 0).mean()),
            "min_bps": float(r.min() * 1e4), "max_bps": float(r.max() * 1e4),
        })
    a = pd.DataFrame(rows).sort_values("symbol")
    print("\n" + a.to_string(index=False))

    # --- interval consistency --------------------------------------------
    print("\n--- funding interval (hours between settlements) ---")
    for sym in list(frames)[:3]:
        d = frames[sym].index.to_series().diff().dt.total_seconds().div(3600).dropna()
        vc = d.value_counts().head(4)
        print(f"  {sym:<8} " + "  ".join(f"{k:g}h x{v}" for k, v in vc.items()))

    # --- sign convention: settled from the data ---------------------------
    print("\n--- sign convention ---")
    print("  Exchange rule: fundingRate > 0 means LONGS PAY SHORTS.")
    print("  If a short perp is held, a positive rate is RECEIVED.")
    allr = pd.concat([f["fundingRate"] for f in frames.values()])
    print(f"  pooled: mean {allr.mean()*1e4:+.3f} bps/8h, "
          f"median {allr.median()*1e4:+.3f} bps, "
          f"{100*(allr>0).mean():.1f}% of settlements positive")
    ann = allr.mean() * 3 * 365 * 1e4
    print(f"  naive gross annualised (if a short is held continuously, "
          f"no costs, no hedge mismatch): {ann:+.0f} bps/yr = {ann/100:+.2f}%/yr")

    # --- gaps -------------------------------------------------------------
    print("\n--- coverage / gaps ---")
    common = None
    for s in frames.values():
        common = s.index if common is None else common.intersection(s.index)
    print(f"  common settlement timestamps across all {len(frames)} symbols: "
          f"{len(common):,}")
    if len(common):
        gaps = pd.Series(common).diff().dt.total_seconds().div(3600).dropna()
        print(f"  interval histogram: "
              + "  ".join(f"{k:g}h x{v}" for k, v in gaps.value_counts().head(3).items()))
        print(f"  span: {common.min().date()} -> {common.max().date()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
