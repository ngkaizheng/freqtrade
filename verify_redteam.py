"""Verify the red team's claims against the data. Do not take them on trust.

Three claims are decisive and checkable in minutes. If they hold, they change
the conclusion and must be recorded; if they do not, the red team was wrong
and that is equally worth knowing.

  1. TAIL DELETION. My own panel used an intersection across symbols. If
     SOL ran a 1-hour funding interval during the FTX collapse, those rows
     sit off the shared 00/08/16 grid and the intersection silently discards
     them -- the worst settlements in the corpus.
  2. PARAMETER SHARE. Binance documents that while the premium index sits in
     a band, funding equals the interest rate, 0.01% per 8h. If most
     settlements sit exactly at +0.0100%, a large share of "carry" is an
     exchange parameter, not a market premium.
  3. INTERVAL REGIME. Binance changed the funding interval schedule inside
     the sample. A single "8h settlement" average would span two regimes.
"""

from __future__ import annotations

import glob
import os

import numpy as np
import pandas as pd

FUND_DIR = "user_data/data/binance_funding"


def raw_by_symbol() -> dict[str, pd.DataFrame]:
    out = {}
    for p in sorted(glob.glob(f"{FUND_DIR}/*.feather")):
        sym = os.path.basename(p).split("_")[0]
        s = pd.read_feather(p)[["fundingTime", "fundingRate"]].copy()
        s["fundingTime"] = pd.to_datetime(s["fundingTime"], unit="ms", utc=True)
        s["fundingRate"] = pd.to_numeric(s["fundingRate"], errors="coerce")
        out[sym] = s.dropna().sort_values("fundingTime")
    return out


def main() -> int:
    raw = raw_by_symbol()
    print("=" * 78)
    print("VERIFYING THE RED TEAM")
    print("=" * 78)

    # ---- 1. tail deletion ------------------------------------------------
    print("\n--- 1. does the intersection delete the extreme tail? ---")
    common = None
    for s in raw.values():
        idx = pd.DatetimeIndex(s["fundingTime"])
        common = idx if common is None else common.intersection(idx)
    n_raw = sum(len(s) for s in raw.values())
    n_kept = int((len(raw) - 1) * len(common))
    print(f"  raw rows across all symbols        : {n_raw:,}")
    print(f"  rows surviving the intersection    : {n_kept:,} "
          f"({n_raw - n_kept:,} discarded)")

    deleted = []
    for sym, s in raw.items():
        miss = s[~s["fundingTime"].isin(common)]
        if len(miss):
            deleted.append((sym, miss))
    print(f"\n  symbols with discarded settlements: "
          f"{ {s: len(m) for s, m in deleted} }")
    if deleted:
        for sym, miss in deleted:
            by_year = miss.groupby(miss["fundingTime"].dt.year)["fundingRate"]
            print(f"    {sym}: {len(miss)} discarded, "
                  f"mean {miss['fundingRate'].mean()*1e4:+.2f} bps, "
                  f"sum {miss['fundingRate'].sum()*100:+.3f}% of notional")
            nov = miss[(miss["fundingTime"] >= "2022-11-01") &
                       (miss["fundingTime"] < "2022-12-01")]
            if len(nov):
                print(f"      Nov 2022 alone: {len(nov)} rows, "
                      f"mean {nov['fundingRate'].mean()*1e4:+.2f} bps, "
                      f"sum {nov['fundingRate'].sum()*100:+.3f}%")
            print(f"      worst discarded: {miss['fundingRate'].min()*1e4:+.2f} bps "
                  f"at {miss.loc[miss['fundingRate'].idxmin(), 'fundingTime']}")

    kept_min = min(s["fundingRate"].min() for s in raw.values())
    print(f"\n  worst rate in the WHOLE corpus      : {kept_min*1e4:+.4f} bps")
    print(f"  worst rate in the kept intersection: "
          f"{min(raw[sym]['fundingRate'][raw[sym]['fundingTime'].isin(common)].min() for sym in raw)*1e4:+.4f} bps")

    # ---- 2. parameter share ---------------------------------------------
    print("\n--- 2. how much carry is Binance's interest-rate parameter? ---")
    allv = pd.concat([s["fundingRate"] for s in raw.values()])
    at_par = (allv.round(8) == 0.0001).mean()
    print(f"  settlements at exactly +0.0100%    : {at_par:.1%}")
    print(f"  their share of the TOTAL sum      : "
          f"{allv[allv.round(8) == 0.0001].sum() / allv.sum():.1%}")
    print("  (Binance: while the premium index is within -0.04%..+0.06%, the")
    print("   funding rate equals the interest rate, 0.01% per 8h = 10.95%/yr.)")
    print(f"  par-equivalent carry if the rate were the ONLY component: "
          f"{0.0001 * 3 * 365 * 100:.2f}%/yr")

    # ---- 3. interval regimes ---------------------------------------------
    print("\n--- 3. did the funding interval change inside the sample? ---")
    for sym in ("SOL", "BTC", "ETH"):
        s = raw[sym]
        gap = s["fundingTime"].diff().dt.total_seconds().div(3600).dropna()
        by_era = {}
        for label, lo, hi in (("pre-2025-05", "2000-01-01", "2025-05-02"),
                              ("2025-05..2026-01", "2025-05-02", "2026-01-02"),
                              ("post-2026-01", "2026-01-02", "2030-01-01")):
            seg = s[(s["fundingTime"] >= lo) & (s["fundingTime"] < hi)]
            if len(seg) < 10:
                continue
            g = seg["fundingTime"].diff().dt.total_seconds().div(3600).dropna()
            by_era[label] = g.value_counts().head(2).to_dict()
        print(f"  {sym}: " + " | ".join(
            f"{k}: {dict((int(a), int(b)) for a, b in v.items())}" for k, v in by_era.items()))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
