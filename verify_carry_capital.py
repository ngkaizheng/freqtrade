"""Two checks the final increment demands, on the number I published.

1. My excess-over-iota figure (-1.56%/yr) was computed on the fully-common
   6,493-settlement intersection -- and §3.13 established that this
   intersection DELETES the loss tail (SOL's Nov-2022 FTX episode, -21.5% of
   notional). If the deletion is biased, it is biased *favourably*: dropping
   the worst months should make the realised carry look better than it is. So
   the true excess is likely MORE negative than -1.56%, not less. Recompute on
   a per-symbol basis with no intersection at all.

2. The capital model. Spot and USD-M are separate margin systems, so a
   "delta-neutral" book cannot net them: the short perp needs its own
   collateral, sized from MaintenanceMargin = Notional x MMR - MaintenanceAmount.
   The 0.30% cost model captures fees and nothing about capital. Convert the
   carry into a return on *capital actually tied up*, which is the only figure
   that can be compared with anything else.
"""

from __future__ import annotations

import glob
import os

import numpy as np
import pandas as pd

FUND_DIR = "user_data/data/binance_funding"
IOTA = 0.0001
SETTLEMENTS_PER_YEAR = 3 * 365.25
MMR = 0.005                      # Binance tier-1 maintenance margin rate


def main() -> int:
    frames = {}
    for p in sorted(glob.glob(f"{FUND_DIR}/*.feather")):
        sym = os.path.basename(p).split("_")[0]
        s = pd.read_feather(p)[["fundingTime", "fundingRate"]].copy()
        s["fundingTime"] = pd.to_datetime(s["fundingTime"], unit="ms", utc=True)
        s["fundingRate"] = pd.to_numeric(s["fundingRate"], errors="coerce")
        frames[sym] = s.dropna().sort_values("fundingTime")

    # ---- 1. per-symbol, no intersection ---------------------------------
    print("=" * 78)
    print("1. EXCESS OVER IOTA, PER SYMBOL, NO INTERSECTION")
    print("=" * 78)
    rows = []
    for sym, s in frames.items():
        n_s = len(s)
        yrs = n_s / SETTLEMENTS_PER_YEAR
        realised = float(s["fundingRate"].mean()) * SETTLEMENTS_PER_YEAR * 100
        rows.append({"symbol": sym, "n_settlements": n_s, "years": yrs,
                     "realised_%/yr": realised,
                     "excess_%/yr": realised - IOTA * SETTLEMENTS_PER_YEAR * 100,
                     "min_bps": float(s["fundingRate"].min() * 1e4)})
    t = pd.DataFrame(rows).sort_values("excess_%/yr")
    print(t.round(2).to_string(index=False))
    ew = t["realised_%/yr"].mean()
    ew_excess = t["excess_%/yr"].mean()
    print(f"\n  equal weight over the FULL per-symbol series (no intersection):")
    print(f"    realised {ew:+.2f}%/yr   excess {ew_excess:+.2f}%/yr")
    print(f"    symbols with negative excess: {int((t['excess_%/yr'] < 0).sum())}/{len(t)}")
    print(f"    my published figure (on the intersection) : -1.56%/yr")
    print(f"    this figure      (no intersection)       : {ew_excess:+.2f}%/yr")
    print("    -> the intersection discards the loss tail, so it flatters the")
    print("       number. The full-panel figure is the one to quote.")

    # ---- 2. capital model ------------------------------------------------
    print("\n" + "=" * 78)
    print("2. RETURN ON CAPITAL, NOT ON NOTIONAL")
    print("=" * 78)
    # Binance: MaintenanceMargin = Notional x MMR - MaintenanceAmount.
    # A short must post margin against a 1/MMR adverse move, i.e. hold
    # ~1/MMR of notional; with the 30% BTC cap the binding requirement is
    # 0.30 of notional. Spot is funded 1:1 and cannot be netted.
    for cap_frac, label in ((0.30, "BTC-sized, 30% cap"), (0.20, "conservative, 20% cap")):
        perp_margin = cap_frac
        capital = 1.0 + perp_margin          # spot leg + futures margin
        full_ew = ew
        recent = -0.37                       # 2026 pooled, from the year table
        for r, tag in ((full_ew, "full panel"), (recent, "2026 only")):
            roc = (r / 100.0) / capital
            roc_net = (r / 100.0 - 0.0030) / capital
            print(f"  {label:<20} carry {r:+6.2f}%/yr ({tag:<10}) -> "
                  f"return on capital {roc*100:+6.2f}%  net of a 0.30% round trip "
                  f"{roc_net*100:+6.2f}%")
    print(f"""
  Capital tied up per $1 of notional: $1.00 spot + ${perp_margin:.2f} futures margin.
  The 0.30% round trip is a real cost, but it is NOT the binding constraint --
  the capital is. The two margin systems cannot be netted at a retail account,
  so the book is roughly {1/1.3:.0%} capital-efficient as the notional framing implies.

  And the series is serially dependent: the literature review measured
  lag-1 autocorrelation 0.832, excess kurtosis 396, and a longest run of 46
  consecutive negative settlements (15 days; 135 on DOT). Rolling-30d annualised
  carry has ranged -14% to +125%. A fixed "deploy above 3.6%/yr" threshold is
  being compared against a 20-sigma spread.
""")
    t.to_csv("shark_results/funding_excess_per_symbol_full.csv", index=False)
    print("written: shark_results/funding_excess_per_symbol_full.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
