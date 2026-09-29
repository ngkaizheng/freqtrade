"""Funding carry with costs, and the arithmetic of how often you may rebalance.

The raw series says the pooled carry was +0.924 bps/8h, about +10%/yr. The
year-by-year breakdown shows that is a 2021 artefact: 2021 alone ran at
+38%/yr, 2022 was negative, and the median symbol has decayed from +20.8%/yr
pre-2023 to +1.6%/yr since 2025, with 8 of 20 now negative.

What decides the strategy is therefore not "is the average positive" but
"what is left after the cost of establishing and unwrapping a delta-neutral
position, and how long must you hold for that cost to amortise".

Cost model, stated explicitly because four incompatible ones exist in this
repo (state file §4). This uses actual Binance retail fees, not a
back-of-envelope number:

  spot taker      10 bps per leg   (Binance spot, no BNB discount)
  perp  taker      5 bps per leg
  open  a hedge   = buy spot + short perp     -> 15 bps
  close a hedge   = sell spot + buy  perp     -> 15 bps
  round trip                                 -> 30 bps = 0.30%

Maker fees would roughly halve it (spot 10/perp 2), but a hedge must be able
to exit when its funding turns, so taker is the honest assumption.
"""

from __future__ import annotations

import glob
import os

import numpy as np
import pandas as pd

FUNDING_DIR = "user_data/data/binance_funding"
SPOT_TAKER_BPS = 10.0
PERP_TAKER_BPS = 5.0
ROUND_TRIP_BPS = 2 * (SPOT_TAKER_BPS + PERP_TAKER_BPS)   # 30
SETTLEMENTS_PER_YEAR = 3 * 365.25
RECENT = "2025-01-01"


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
    print("FUNDING CARRY NET OF THE COST OF TRADING IT")
    print("=" * 78)
    print(f"panel: {len(panel):,} settlements x {panel.shape[1]} symbols, "
          f"{panel.index.min().date()} -> {panel.index.max().date()}")
    print(f"cost model: spot {SPOT_TAKER_BPS:.0f}bps + perp {PERP_TAKER_BPS:.0f}bps "
          f"per leg -> {ROUND_TRIP_BPS:.0f}bps round trip "
          f"({ROUND_TRIP_BPS/100:.2f}%)\n")

    gross_full = panel.to_numpy().mean() * SETTLEMENTS_PER_YEAR * 100
    recent = panel[panel.index >= RECENT]
    gross_recent = recent.to_numpy().mean() * SETTLEMENTS_PER_YEAR * 100

    print(f"pooled gross, full period 2020-2026 : {gross_full:+.2f}%/yr")
    print(f"pooled gross, since {RECENT}        : {gross_recent:+.2f}%/yr")
    print(f"  -> the headline number is {(gross_full / gross_recent):.0f}x the recent "
          f"experience\n" if gross_recent != 0 else "")

    # ---- net as a function of how often the hedge is rebuilt ------------
    print("--- net carry vs number of round trips per year (pooled, all 20) ---")
    print(f"{'rebalances/yr':>15} {'cost %/yr':>12} {'net full %':>12} {'net recent %':>14}")
    for n in (1, 2, 3, 4, 6, 12, 24):
        cost = n * ROUND_TRIP_BPS / 100
        print(f"{n:>15} {cost:>12.2f} {gross_full - cost:>12.2f} "
              f"{gross_recent - cost:>14.2f}")

    breakeven = gross_recent / (ROUND_TRIP_BPS / 100)
    print(f"\n  at the recent rate, one round trip costs "
          f"{ROUND_TRIP_BPS/100:.2f}% against {gross_recent:+.2f}%/yr of gross")
    print(f"  -> breakeven holding period is {breakeven:.1f} years; you may rebuild "
          f"the hedge at most {max(int(breakeven), 0)}x per year and stay positive")

    # ---- per symbol, recent vs full -------------------------------------
    print("\n--- per symbol, annualised %, since 2025 ---")
    g_all = panel.mean() * SETTLEMENTS_PER_YEAR * 100
    g_rec = recent.mean() * SETTLEMENTS_PER_YEAR * 100
    n_rebal = 4
    cost = n_rebal * ROUND_TRIP_BPS / 100
    tab = pd.DataFrame({
        "gross_full_%": g_all, "gross_recent_%": g_rec,
        "net_recent_1x_%": g_rec - ROUND_TRIP_BPS / 100,
        "net_recent_4x_%": g_rec - cost,
    }).sort_values("gross_recent_%", ascending=False)
    print(tab.round(2).to_string())
    pos = int((g_rec > 0).sum())
    pos_net1 = int((g_rec - ROUND_TRIP_BPS / 100 > 0).sum())
    pos_net4 = int((g_rec - cost > 0).sum())
    print(f"\n  symbols with positive gross carry since 2025     : {pos}/{len(g_rec)}")
    print(f"  positive after 1 round trip per year              : {pos_net1}/{len(g_rec)}")
    print(f"  positive after {n_rebal} round trips per year               : {pos_net4}/{len(g_rec)}")

    # ---- the selection trap ------------------------------------------------
    print("\n--- the selection trap, stated explicitly ---")
    k = 5
    top = g_rec.sort_values(ascending=False).head(k)
    print(f"  best {k} symbols ex-post, net at 4 round trips/yr: "
          f"{(top.mean() - cost):+.2f}%/yr")
    print(f"  equal-weight all {len(g_rec)} symbols, same cost   : "
          f"{(g_rec.mean() - cost):+.2f}%/yr")
    print("  The first number is not achievable: it requires knowing in advance")
    print("  which five symbols would keep paying funding. That gap between")
    print("  'ex-post best' and 'equal weight' is the price of selection, and it")
    print("  is why the state file's own diversification measurement (vol ratio")
    print("  saturating by ~20 names) matters here.")

    # ---- what would have to be true --------------------------------------
    print("\n--- the honest summary ---")
    best_case = g_rec.max() - ROUND_TRIP_BPS / 100
    print(f"""
Gross carry, best single symbol since 2025 : {g_rec.max():+.2f}%/yr
Net of one round trip, same symbol        : {best_case:+.2f}%/yr
Gross carry, equal weight across 20       : {g_rec.mean():+.2f}%/yr
Net of four round trips, equal weight     : {g_rec.mean() - cost:+.2f}%/yr

The full-period {gross_full:+.1f}%/yr is a 2021 artefact. Since {RECENT} the
median symbol pays {g_rec.median():+.2f}%/yr and {len(g_rec) - pos} of {len(g_rec)}
pay nothing at all. A strategy whose payoff depends on reaping a rate that
has already been arbitraged away is not a strategy.

This is a negative result on the designated next line, obtained the way the
state file demanded: as a number, not a p-value.
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
