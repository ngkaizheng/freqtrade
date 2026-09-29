"""Funding carry, with the P&L component that actually dominates: basis.

A long-spot / short-perp position is not a cash machine. It has three P&L
components and the funding study only counted one:

  1. funding      -- paid to the short leg every 8h.            small, steady
  2. basis        -- the perp's premium/discount to spot. If the perp
                     trades 4% rich when you open and 1% rich when you
                     close, you lose 3% of notional instantly and no amount
                     of funding makes up for it.
  3. liquidation  -- the short leg can be liquidated in a violent rally even
                     while the spot leg is profitable.

The 7.5%/yr, 0.11%-max-drawdown figure from `funding_risk.py` is therefore a
number about a strategy that does not exist: it omits (2) and (3), and those
dominate. This script recomputes the total return of the actual hedge, using
the spot and perp books already on disk.

Convention: a position opened at time t and closed at t+H earns
    (spot_t+1/spot_t) - 1        long spot leg
  - (perp_t+1/perp_t) - 1        short perp leg
  + sum(fundingRate) * (perp/spot notional ratio)   funding to the short
both legs pay taker on entry and exit, and funding accrues to the short leg
because fundingRate > 0 means longs pay shorts.
"""

from __future__ import annotations

import glob
import os
import re

import numpy as np
import pandas as pd

SPOT_DIR = "user_data/data/binance"
FUND_DIR = "user_data/data/binance_funding"
SPOT_TAKER_BPS = 10.0
PERP_TAKER_BPS = 5.0
OPEN_COST = (SPOT_TAKER_BPS + PERP_TAKER_BPS) / 1e4      # 15 bps
CLOSE_COST = OPEN_COST
LOOKBACK_DAYS = 180


def load_funding() -> dict[str, pd.DataFrame]:
    out = {}
    for p in sorted(glob.glob(f"{FUND_DIR}/*.feather")):
        sym = os.path.basename(p).split("_")[0]
        s = pd.read_feather(p)[["fundingTime", "fundingRate"]].copy()
        s["fundingTime"] = pd.to_datetime(s["fundingTime"], unit="ms", utc=True)
        s["fundingRate"] = pd.to_numeric(s["fundingRate"], errors="coerce")
        out[sym] = (s.dropna().sort_values("fundingTime")
                     .drop_duplicates("fundingTime", keep="last")
                     .set_index("fundingTime")["fundingRate"])
    return out


def load_spot(sym: str) -> pd.DataFrame | None:
    p = f"{SPOT_DIR}/{sym}_USDT-1h.feather"
    if not os.path.exists(p):
        return None
    df = pd.read_feather(p)
    # The spot book indexes on `date` and arrives already tz-aware; the perp
    # book carries its timestamp in the index. Normalise both here rather than
    # assuming a schema.
    tcol = next((c for c in ("date", "open_time", "time", "timestamp")
                 if c in df.columns), df.columns[0])
    if tcol in ("open_time", "timestamp"):
        df[tcol] = pd.to_datetime(df[tcol], unit="ms", utc=True)
    df = df.sort_values(tcol).set_index(tcol)
    df.index = pd.DatetimeIndex(df.index).tz_convert("UTC")
    return df


def load_perp(sym: str) -> pd.DataFrame | None:
    p = f"shark_data/klines/{sym}USDT_1h.csv.gz"
    if not os.path.exists(p):
        return None
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    df.index = pd.DatetimeIndex(df.index).tz_convert("UTC")
    return df.sort_index()


def main() -> int:
    funding = load_funding()
    print("=" * 78)
    print("FUNDING CARRY: THE FULL HEDGE, INCLUDING BASIS")
    print("=" * 78)

    usable = []
    for sym in funding:
        s, k = load_spot(sym), load_perp(sym)
        if s is not None and k is not None:
            usable.append(sym)
    print(f"\nsymbols with BOTH spot and perp on disk: {len(usable)} of {len(funding)}")
    print(f"  {usable}")
    missing = sorted(set(funding) - set(usable))
    print(f"  missing a leg: {missing}")
    if not usable:
        print("\nCannot compute the real hedge return without both legs.")
        return 1

    # State the coverage limit rather than letting it silently truncate the
    # result: the funding book starts 2019-11 but the perp price book only
    # starts 2023-01, so the full hedge can only be evaluated from 2023.
    spans = []
    for sym in usable:
        k = load_perp(sym)
        if k is not None and len(k):
            spans.append((str(k.index.min().date()), str(k.index.max().date())))
    print(f"\n  COVERAGE LIMIT: perp prices only span {spans[0][0]} -> {spans[-1][1]}.")
    print("  The funding series starts 2019-11, so 2019-2022 CANNOT be scored")
    print("  on the full hedge with the data on disk. Everything below is")
    print("  2023 onward, which is also the period that matters (the carry")
    print("  collapsed after 2021).")

    # ---- basis: how wide is it, and does it move? ------------------------
    print("\n--- basis: perp premium/discount to spot, at 8h settlement times ---")
    basis_rows = []
    for sym in usable:
        s, k = load_spot(sym), load_perp(sym)
        f = funding[sym]
        common = f.index.intersection(s.index.floor("1h")).intersection(k.index)
        common = common.sort_values()
        if len(common) < 100:
            continue
        px_s = s["close"].reindex(common)
        px_k = k["close"].reindex(common)
        b = px_k / px_s - 1.0
        basis_rows.append({
            "symbol": sym, "n": len(b),
            "mean_bps": float(b.mean() * 1e4), "sd_bps": float(b.std() * 1e4),
            "p95_bps": float(b.quantile(0.95) * 1e4),
            "max_abs_bps": float(b.abs().max() * 1e4),
        })
    basis = pd.DataFrame(basis_rows).sort_values("mean_bps", ascending=False)
    print(basis.round(2).to_string(index=False))
    print(f"\n  median basis dispersion across symbols: "
          f"{basis['sd_bps'].median():.1f} bps")
    print("  Compare with the funding earned per quarter (~+30bps gross on the")
    print("  recent sample). Basis moves are the same order of magnitude and")
    print("  they are NOT collected -- they are paid or received.")

    # ---- the actual hedge P&L, quarter by quarter ------------------------
    print("\n--- quarterly P&L of the real hedge, per symbol (no selection) ---")
    rows = []
    for sym in usable:
        s, k = load_spot(sym), load_perp(sym)
        f = funding[sym]
        idx = f.index.intersection(s.index.floor("1h")).intersection(k.index).sort_values()
        if len(idx) < 400:
            continue
        q = pd.Series(idx, index=idx).resample("QE").first()
        prev = None
        for d, t_open in q.items():
            seg = idx[(idx >= t_open - pd.Timedelta(hours=1)) & (idx <= t_open + pd.Timedelta(days=92))]
            if len(seg) < 20:
                continue
            t_close = seg[-1]
            spot_ret = s["close"].reindex([t_open, t_close])
            perp_ret = k["close"].reindex([t_open, t_close])
            if spot_ret.isna().any() or perp_ret.isna().any():
                continue
            s0, s1 = float(spot_ret.iloc[0]), float(spot_ret.iloc[1])
            p0, p1 = float(perp_ret.iloc[0]), float(perp_ret.iloc[1])
            fund = float(f.reindex(seg).fillna(0.0).sum())
            gross = (s1 / s0 - 1.0) - (p1 / p0 - 1.0) + fund
            net = gross - OPEN_COST - CLOSE_COST
            rows.append({"symbol": sym, "quarter": d, "funding_bps": fund * 1e4,
                         "spot_bps": (s1 / s0 - 1) * 1e4, "perp_bps": (p1 / p0 - 1) * 1e4,
                         "basis_bps": ((s1 / s0) - (p1 / p0)) * 1e4,
                         "net_bps": net * 1e4})
    r = pd.DataFrame(rows)
    if r.empty:
        print("  not enough aligned data")
        return 1
    print(f"  observations: {len(r)} symbol-quarters, "
          f"{r['quarter'].nunique()} quarters\n")
    comp = (r.groupby("symbol")[["funding_bps", "basis_bps", "net_bps"]]
              .mean().sort_values("net_bps", ascending=False))
    print(comp.round(1).to_string())
    print(f"\n  mean funding per quarter : {r['funding_bps'].mean():+.1f} bps")
    print(f"  mean basis   per quarter : {r['basis_bps'].mean():+.1f} bps")
    print(f"  mean NET     per quarter : {r['net_bps'].mean():+.1f} bps")
    print(f"  quarters where net < 0   : {100*(r['net_bps'] < 0).mean():.0f}%")

    r.to_csv("shark_results/funding_full_hedge.csv", index=False)
    comp.to_csv("shark_results/funding_full_hedge_by_symbol.csv")
    print("\nwritten: shark_results/funding_full_hedge.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
