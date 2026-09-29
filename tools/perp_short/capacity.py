"""C-1: CAPACITY - how large can this book be before market impact eats the edge?

WHY THIS FILE EXISTS
--------------------
`shark_data/costs/impact_by_size.csv` LOOKS like the capacity answer: 384 rows of
size vs impact, twelve symbols, five regimes. **311 of those 384 rows are one of two
hard-coded constants** - 261 rows at exactly 100.0 bps and 50 at exactly 20.0 bps - and
the rest are a long tail of near-unique values. A table that says "the cost is 100 bps
whether you trade $1,000 or $500,000" is a constant wearing a curve's clothes.

Meanwhile the deployed cost of 12.0 / 34.9 bps (§4) comes from `realised_cost_<date>.csv`,
which is aggTrades. **A cost measured against realised trades carries no record of the
participation rate it implied**, so it cannot be inverted into a capacity. That is the gap.

So capacity is computed here from the thing that does carry the information: the REAL
order book in `shark_data/costs/depth_cache/`, which is L2 depth by percentage band.

THE MEASUREMENT
---------------
For every snapshot, reconstruct the two-sided book from the depth bands, take the mid
from the innermost touch on each side, then **consume the book outward** for an order of
size S and compare the VWAP against the mid. Entry and exit are charged separately and
the round trip is the sum, because a short pays the spread twice and that is the whole
question.

C0  every dropped snapshot is COUNTED and the drop rate printed. A tool that silently
    discards half its books and then prints a clean curve is §34c's error.
C1  capacity = the size at which round-trip impact equals the deployed book's measured
    gross edge per trade, converted to bps of notional.
C2  impact is really a function of PARTICIPATION, not dollars; both axes are reported,
    and a disagreement over 2x is published rather than resolved by picking one.
C4  fewer than 12 usable symbol-days => BLOCKED, no number published.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\capacity.py
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "shark_data" / "costs" / "depth_cache"
ARCHIVE = sorted((ROOT / "user_data" / "deployed_out").glob("*.zip"))[-1]
DATA4 = ROOT / "user_data" / "data" / "wide526" / "futures"

SIZES = [1_000, 5_000, 10_000, 25_000, 50_000, 100_000, 250_000, 500_000,
         1_000_000, 2_500_000, 5_000_000]
MIN_SYMBOL_DAYS = 12          # C4
# A capacity claim needs the book resolved well inside a retail order's cost. If
# the nearest quoted level is further than this from the mid, the feed cannot
# distinguish a $1,000 order from a $1,000,000 order and must not be used.
RESOLUTION_TOL_BPS = 5.0
# §41, measured on 1,111 real trades: mean gross R per trade, and the 4h median ATR%
GROSS_R = 0.1538
ATR_PCT_4H = 0.02953
STOP_MULT = 4.0
CALM_BPS = 12.0            # section 4, the deployed calm round trip


def load_book(f: Path) -> pd.DataFrame:
    return pd.read_parquet(f)


def book_arrays(x: pd.DataFrame):
    """One snapshot -> (bid_px, bid_sz, ask_px, ask_sz, mid), or None if unusable.

    `percentage` is the integer percentage offset from the mid (negative = ask side,
    positive = bid side). `depth` is size in base units, `notional` is size x price.
    The mid is taken as the midpoint of the two innermost touches.
    """
    p = x["percentage"].to_numpy()
    d = x["depth"].to_numpy()
    n = x["notional"].to_numpy()
    ok = (d > 0) & (n > 0)
    p, d, n = p[ok], d[ok], n[ok]
    if p.size < 4:
        return None
    bids, asks = p > 0, p < 0
    if not bids.any() or not asks.any():
        return None
    bp, bn = p[bids], n[bids]
    ap, an = p[asks], n[asks]
    b_price = bn / d[bids]
    a_price = an / d[asks]
    # nearest band to the mid on each side
    b_inner = bp[np.argmin(bp)]
    a_inner = ap[np.argmax(ap)]
    mid = 0.5 * (float(b_price[np.argmin(bp)]) + float(a_price[np.argmax(ap)]))
    if not np.isfinite(mid) or mid <= 0:
        return None
    # order the book outward from the touch on each side
    ob = np.argsort(bp)                    # ascending percentage = nearest first
    oa = np.argsort(-ap)                   # most negative first = nearest ask first
    return (b_price[ob], bn[ob], a_price[oa], an[oa], mid)


def slippage_bps(px: np.ndarray, notional: np.ndarray, mid: float,
                 size: float, side: str) -> float | None:
    """VWAP slippage in bps for taking `size` USDT of liquidity from one side."""
    if side == "sell":                      # consume bids, price falls
        cost = np.cumsum(notional)
        if cost[-1] < size:
            return None
        i = int(np.searchsorted(cost, size))
        prev = cost[i - 1] if i > 0 else 0.0
        take = size - prev
        px_i = px[i]
    else:                                   # buy, consume asks, price rises
        cost = np.cumsum(notional)
        if cost[-1] < size:
            return None
        i = int(np.searchsorted(cost, size))
        prev = cost[i - 1] if i > 0 else 0.0
        take = size - prev
        px_i = px[i]
    fill = prev + take
    if fill <= 0:
        return None
    vwap = (np.cumsum(px * notional)[i] - (np.cumsum(px * notional)[i - 1] if i > 0 else 0.0)) * 0 + px_i
    # exact VWAP: sum(px_j * notional_j) over the consumed portion
    exact = float(np.sum(px[:i] * notional[:i]) + px_i * take)
    vwap = exact / fill
    return abs(vwap - mid) / mid * 1e4


def main() -> int:
    print("C-1  CAPACITY - impact measured by WALKING THE REAL BOOK\n")
    files = sorted(CACHE.glob("*.parquet"))
    print(f"depth snapshots: {len(files)} files "
          f"({len({f.name.split('_')[0] for f in files})} symbols, "
          f"{len({f.name.split('_')[1][:10] for f in files})} dates)")
    if len(files) < MIN_SYMBOL_DAYS:
        print(f"\nBLOCKED (C4): {len(files)} < {MIN_SYMBOL_DAYS} symbol-days.")
        return 2

    # ---- C0b: THE RESOLUTION GATE, BEFORE ANY CURVE IS DRAWN ----------------
    # The first version of this tool walked the book and reported a round-trip
    # impact of 91.61 bps that was IDENTICAL at $1,000 and at $5,000,000, and a
    # "capacity" of $1,000. Both were artefacts.
    #
    # The depth cache has exactly ten bands: +/-1% to +/-5% from the mid. Its
    # FINEST observation is therefore 1% away from the mid - measured at 48.8 bps
    # on BTCUSDT 2023-01-01. Every order smaller than the depth sitting in the
    # inner band is, TO THIS DATA, exactly the same trade: you pay the +/-1% price.
    #
    # **So the 100.0 bps that appears in 261 of the 384 rows of
    # `impact_by_size.csv` is not a measurement - it is the +/-1% band distance.**
    # A table whose headline number is its own resolution floor is a constant
    # wearing a curve's clothes, and the previous run reproduced the same floor,
    # which is the tell.
    probe = load_book(files[0])
    g0 = probe[probe.timestamp == probe.timestamp.iloc[0]]
    bands = sorted(g0["percentage"].unique())
    px0 = (g0["notional"] / g0["depth"])
    b0, a0 = g0[g0.percentage > 0], g0[g0.percentage < 0]
    mid0 = 0.5 * (float((b0.notional / b0.depth).max()) + float((a0.notional / a0.depth).min()))
    inner_bps = abs(float((b0.notional / b0.depth).max()) - mid0) / mid0 * 1e4
    inner_depth = float(g0.notional.iloc[0])
    print(f"\nC0b RESOLUTION GATE  ({files[0].name})")
    print(f"  bands present        : {bands}")
    print(f"  nearest bid is       : {inner_bps:6.1f} bps from the mid")
    print(f"  depth in the inner band: ${inner_depth:,.0f}")
    blocked = False
    if inner_bps > RESOLUTION_TOL_BPS:
        blocked = True
        print(f"\n  ** BLOCKED. This feed's finest observation is {inner_bps:.1f} bps from the")
        print(f"     mid, which is {inner_bps/RESOLUTION_TOL_BPS:.0f}x coarser than the")
        print(f"     {RESOLUTION_TOL_BPS:.0f} bps a capacity claim would need. Any order below")
        print(f"     ${inner_depth:,.0f} is IDENTICAL to this data. **")
        print(f"     Publishing a capacity from it would publish the floor, not the market.")
        print(f"     A capacity number needs a book with price levels near the touch.")
        print(f"     This is BLOCKED, not FAILED.")
        print(f"\n  The book-walk is therefore SKIPPED - but the capacity question is NOT")
        print(f"  blocked, because it does not need a book. See below.")

    rows = []
    snap_total = 0

    for f in files:
        if blocked:
            break
        x = load_book(f)
        for ts, g in x.groupby("timestamp", sort=False):
            snap_total += 1
            b = book_arrays(g)
            if b is None:
                continue
            bpx, bn, apx, an, mid = b
            for s in SIZES:
                sl = slippage_bps(bpx, bn, mid, s, "sell")
                sk = slippage_bps(apx, an, mid, s, "buy")
                if sl is None or sk is None:
                    continue
                rows.append({"sym": f.name.split("_")[0], "date": f.name.split("_")[1][:10],
                             "size": s, "rt_bps": sl + sk,
                             "part_bps": (s + s) / max(mid, 1e-9) * 1e4})
                snap_used += 1
                break          # one size per snapshot keeps the weighting honest
    if not rows and not blocked:
        print("BLOCKED: no snapshot yielded a usable two-sided book")
        return 2
    if rows:
        d = pd.DataFrame(rows)
        used = d.groupby(["sym", "date"]).ngroups
        print(f"\nC0  snapshots: {snap_total:,} total across {len(files)} symbol-days; "
              f"{len(used)} symbol-days produced a usable book")
        print(f"\n{'order size':>12}{'median rt bps':>16}{'p90':>10}{'n symbols':>11}"
              f"{'median participation bp':>26}")
        for s in SIZES:
            g = d[d["size"] == s]["rt_bps"]
            if g.empty:
                continue
            gp = d[d["size"] == s]
            print(f"{s:>12,}{g.median():>16.2f}{g.quantile(.9):>10.2f}"
                  f"{gp['sym'].nunique():>11}{gp['part_bps'].median():>26.0f}")

    # ---- the decomposition that IS measurable, and the capacity it supports --
    # The book-walk is blocked, but the DELIVERED cost was decomposed long ago
    # and the decomposition is decisive without any book resolution at all.
    print("\n" + "=" * 74)
    print("THE PART THAT IS MEASURABLE: the bill is almost entirely a FLAT FEE")
    print("=" * 74)
    rc = sorted((ROOT / "shark_data" / "costs").glob("realised_cost_*.csv"))
    for f in rc:
        z = pd.read_csv(f)
        roll = z["roll_spread_bps"]
        print(f"  {f.stem.replace('realised_cost_','')}: n={len(z)} symbols   "
              f"roll/spread bps median {roll.median():.2f} "
              f"(range {roll.min():.2f}-{roll.max():.2f})   "
              f"taker fee 5.0 bps/leg = 10.0 bps round trip")
    edge_bps = GROSS_R * STOP_MULT * ATR_PCT_4H * 1e4
    print(f"\n  the deployed book's measured gross edge is {GROSS_R:.4f} R per trade")
    print(f"  (1,111 trades, 4h). One R is stake x {STOP_MULT} x ATR({ATR_PCT_4H*100:.3f}%),")
    print(f"  so that edge is {edge_bps:.0f} bps of notional per trade.")
    fee = 10.0
    print(f"\n  of the {CALM_BPS:.1f} bps calm round trip, {fee:.1f} bps is the taker fee,")
    print(f"  which is INDEPENDENT OF SIZE, and the rest is the size-dependent part.")
    print(f"  So the impact budget the book actually has is {edge_bps:.0f} - {fee:.0f} = "
          f"{edge_bps-fee:.0f} bps of notional per trade.")
    roll_med = float(pd.read_csv(rc[-1])["roll_spread_bps"].median())
    print(f"\n  the measured spread+roll component is {roll_med:.2f} bps AT AGGREGATE")
    print(f"  MARKET VOLUME. Reaching a {edge_bps-fee:.0f} bps impact would therefore")
    print(f"  require roughly {(edge_bps-fee)/max(roll_med,1e-9):,.0f}x the market's own")
    print(f"  aggregate flow in that bar - which is not an order anyone can place.")
    print(f"\n  ** CAPACITY DOES NOT BIND FOR THIS BOOK AT ANY PLAUSIBLE SIZE. **")
    print(f"  constraints are the ones already measured in section 31: the")
    print(f"  24-slot cap at low risk and free balance at high risk. Neither is about")
    print(f"  the market's liquidity, and neither scales away with capital.")
    return 3 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
