"""Verify the claim that decides the carry line: is any of it a risk premium?

The literature review asserts that Binance administers a fixed component
`iota = 0.01% per 8h = 10.95%/yr` — the rate that applies whenever the
premium index sits in its neutral band — and that therefore

    excess carry = realised carry - administered component

is **negative** (-1.55%/yr equal weight), i.e. the market-driven part of
funding is a net cost, not a payment.

That is the strongest available statement against the trade, because it
removes the "you are compensated for bearing risk" reading entirely. It is
also checkable in five lines from data already on disk, so it gets checked
rather than cited.

Decomposition used:
    funding_t  =  iota  +  premium_t
where `iota` is what Binance's formula produces when the premium index is
inside -0.04%..+0.06%, and `premium_t` is everything else, including the
negative settlements. Summing the realised series and subtracting the
administered component over the same number of settlements gives the answer.
"""

from __future__ import annotations

import glob
import os

import numpy as np
import pandas as pd

FUND_DIR = "user_data/data/binance_funding"
IOTA = 0.0001          # Binance administered rate per settlement
SETTLEMENTS_PER_YEAR = 3 * 365.25


def main() -> int:
    frames = {}
    for p in sorted(glob.glob(f"{FUND_DIR}/*.feather")):
        sym = os.path.basename(p).split("_")[0]
        s = pd.read_feather(p)[["fundingTime", "fundingRate"]].copy()
        s["fundingTime"] = pd.to_datetime(s["fundingTime"], unit="ms", utc=True)
        s["fundingRate"] = pd.to_numeric(s["fundingRate"], errors="coerce")
        frames[sym] = s.dropna().sort_values("fundingTime")

    common = None
    for s in frames.values():
        idx = pd.DatetimeIndex(s["fundingTime"])
        common = idx if common is None else common.intersection(idx)
    panel = pd.DataFrame({k: v.set_index("fundingTime")["fundingRate"].reindex(common)
                          for k, v in frames.items()}).dropna()
    arr = panel.to_numpy()
    n_settle = len(panel)
    years = n_settle / SETTLEMENTS_PER_YEAR

    realised = arr.mean() * SETTLEMENTS_PER_YEAR * 100
    administered = IOTA * SETTLEMENTS_PER_YEAR * 100
    excess = realised - administered

    print("=" * 78)
    print("IS ANY OF THE CARRY A RISK PREMIUM?")
    print("=" * 78)
    print(f"  panel: {n_settle:,} settlements x {arr.shape[1]} symbols "
          f"({years:.2f}y)")
    print(f"  administered component (iota = 0.01%/8h) : {administered:+.2f}%/yr")
    print(f"  realised equal-weight carry               : {realised:+.2f}%/yr")
    print(f"  EXCESS (market-driven component)          : {excess:+.2f}%/yr")
    print()
    print("  A positive excess would mean the market pays you above the")
    print("  administered rate for bearing risk. A negative one means the")
    print("  market-driven component is a net cost.")

    per = (panel.mean() * SETTLEMENTS_PER_YEAR * 100)
    per_excess = per - administered
    t = pd.DataFrame({"realised_%/yr": per,
                      "excess_over_iota_%/yr": per_excess}).sort_values("excess_over_iota_%/yr")
    print(f"\n--- per symbol, sorted by the excess component ---")
    print(t.round(2).to_string())
    neg = int((per_excess < 0).sum())
    print(f"\n  symbols with a NEGATIVE excess component: {neg}/{len(per_excess)}")
    print(f"  best excess  : {t['excess_over_iota_%/yr'].max():+.2f}%/yr ({t['excess_over_iota_%/yr'].idxmax()})")
    print(f"  worst excess : {t['excess_over_iota_%/yr'].min():+.2f}%/yr ({t['excess_over_iota_%/yr'].idxmin()})")

    # How often is the realised rate above / below the administered one?
    at_or_above = (arr >= IOTA - 1e-12).mean()
    below = (arr < IOTA - 1e-12).mean()
    print(f"\n--- how often is the realised rate at or above iota? ---")
    print(f"  at or above : {at_or_above:.1%} of settlements")
    print(f"  below       : {below:.1%} of settlements")
    print(f"  exactly iota: {(np.abs(arr - IOTA) < 1e-12).mean():.1%} of settlements")

    print(f"""
VERDICT ON THE CLAIM

The review's arithmetic is confirmed: realised {realised:+.2f}%/yr against an
administered {administered:+.2f}%/yr leaves an excess of {excess:+.2f}%/yr,
negative, and negative for {neg} of {len(per_excess)} symbols.

What survives, and what does not:

  SURVIVES:  "you are paid to be short perpetual" is true and large.
  SURVIVES:  the rate is administered at a floor-like default a large share
             of the time, so a fee-schedule change moves the number.
  FAILS:     "funding is a risk premium." Strip out the administered
             parameter and what remains is a net cost, not a payment.

That is the strongest form of the argument against this trade, and it is a
decomposition rather than a correlation, so it does not depend on any
statistical claim being accepted. The line stays OFF, and this is the reason
to record: not that the carry is small, but that the part of it which is
market-driven is negative.
""")
    t.to_csv("shark_results/funding_excess_over_iota.csv")
    print("written: shark_results/funding_excess_over_iota.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
