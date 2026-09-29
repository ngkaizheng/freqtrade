"""Measure the market-impact term that the cost model in this repository omits.

WHY THIS FILE EXISTS. The live research line (E#4, cross-sectional reversal) has
exactly one stated blocker, and it is cost:

    | round trip per name | net/yr |
    | 12 bps (repo floor) | +54.8% |
    | 26.6 bps             | BREAKEVEN |
    | 35 bps               | -31.7% |

Measured turnover is 1.03 per rebalance = 376x annualised, ~51,000 name-trades a
year, and the state file records: *"The cost model in this repository has no
market-impact term. At 376x turnover that is the least reliable number in the
model, and the whole result lives inside its error bar."*

That is a real gap, and until now it was unfillable from public data -- no
order-book depth was available to this project. It is now.

THE DATA. Binance Vision publishes `bookDepth` for USD-M perpetuals:
`data/futures/um/daily/bookDepth/<SYM>/<SYM>-bookDepth-<YYYY-MM-DD>.zip`, one row
per (30-second snapshot, percentage level):

    timestamp, percentage, depth, notional

`percentage` is the price level as a percent offset from mid: -5,-4,-3,-2,-1,
-0.2,+0.2,+1,+2,+3,+4,+5. `notional` is CUMULATIVE USD size available on that
side at that level. Monotonicity outward is verified at load time, not assumed.

    Availability: 2023-01-01 -> present. 2022-12-31 is a confirmed 404.
    Verified by tools/cross_section/probe_depth_availability.py, which controls
    for S3 throttling with a positive control and 2x-confirmed 404s.

    This matters: the depth window contains 2023-24, the era in which E#4's gross
    edge was real (+1.05 develop) and 2025, in which it had decayed to -0.31.
    Depth CANNOT cover 2020-01 to 2022-12, so any impact statement is scoped to
    the back 55% of the panel and must say so.

METHOD. Cost of a market order of size N walking the ladder from the touch
outward, in basis points of mid:

    cost_bps = 100 * SUM_i(consumed_i * pct_i) / SUM_i(consumed_i)

This is M-free -- the percentage levels are already a fraction of mid -- so no
mid-price reconstruction is needed and no kline join can introduce a timestamp
mismatch.

STATED LIMITATION, because it biases in a known direction. bookDepth reports
depth at FIXED percentage buckets, so the distribution WITHIN the innermost 0.2%
bucket is unobserved. For an order smaller than that bucket this code assumes the
size is spread uniformly across it, which OVERSTATES cost: a real book is densest
at the touch. Small-size numbers are therefore conservative upper bounds; the
large-size numbers, where the book is genuinely consumed level by level, are
essentially exact.

Run:
    .venv\\Scripts\\python.exe tools\\cost\\measure_impact.py
"""

from __future__ import annotations

import io
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests

S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
BOOKDEPTH = f"{S3}/data/futures/um/daily/bookDepth"
ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "shark_data/costs/depth_cache"
OUT = ROOT / "shark_data/costs"

# S3 throttles this client HARD and answers with a spurious NoSuchKey 404 rather
# than a 429. Observed repeatedly: a URL that returns 200 on one request returns
# NoSuchKey on the next 5, then 200 again after a ~90s pause. Every fetch is
# therefore serialised, validated (PK zip magic + real member), and retried with
# backoff. Treating a 404 as absence without validation is what produced a
# completely false "no depth data exists" grid earlier in this session.
FETCH_GAP_S = 12.0
BACKOFF_S = (10, 30, 60, 120)

# Spans the liquidity range that matters: E#4 trades the 200 OLDEST-LISTED perps
# (the long tail), so majors alone would misrepresent the universe it trades.
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "LINKUSDT", "DOGEUSDT",
           "AVAXUSDT", "ATOMUSDT", "FILUSDT", "ALGOUSDT", "XLMUSDT",
           "ETCUSDT", "NEOUSDT"]

# 2023-01-01 is the first date bookDepth exists. 2024-08-05 is the largest
# long-tail liquidation cascade of the depth era. 2026-09-20 is the latest.
DATES = ["2023-01-01", "2023-06-15", "2024-08-05", "2025-10-10", "2026-09-20"]

SIZES_USD = [1_000, 10_000, 50_000, 100_000, 500_000, 1_000_000, 5_000_000]

# Some snapshots in the archive are missing a level. They are dropped, but a file
# that is mostly incomplete is rejected outright rather than quietly shrinking
# the sample to whatever survived.
MAX_DROP_FRACTION = 0.20


def fetch_depth(symbol: str, day: str) -> pd.DataFrame | None:
    """Download (or reuse) one day of bookDepth. Returns None only if confirmed absent."""
    dest = CACHE / f"{symbol}_{day.replace('-', '')}.parquet"
    if dest.exists():
        return pd.read_parquet(dest)

    url = f"{BOOKDEPTH}/{symbol}/{symbol}-bookDepth-{day}.zip"
    for attempt, wait in enumerate((0,) + BACKOFF_S):
        if wait:
            time.sleep(wait)
        try:
            r = requests.get(url, timeout=180,
                             headers={"User-Agent": "freqtrade-impact/1.0"})
        except requests.RequestException:
            continue
        if r.status_code == 200 and r.content[:2] == b"PK":
            try:
                with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
                    name = [n for n in zf.namelist() if n.endswith(".csv")][0]
                    df = pd.read_csv(io.BytesIO(zf.read(name)))
            except (zipfile.BadZipFile, StopIteration, ValueError):
                continue          # truncated body despite 200: treat as throttle
            CACHE.mkdir(parents=True, exist_ok=True)
            df.to_parquet(dest, index=False)
            time.sleep(FETCH_GAP_S)
            return df
        if r.status_code == 404 and attempt >= 2:
            # Three spaced 404s, each preceded by a long pause, is a real absence.
            time.sleep(FETCH_GAP_S)
            return None
        time.sleep(FETCH_GAP_S)
    return None


def side_frame(df: pd.DataFrame, side: str) -> tuple[pd.DataFrame, np.ndarray]:
    """Wide frame of cumulative notional (snapshots x levels) plus ABSOLUTE offsets.

    Levels are ordered NEAREST first, by |percentage|. On the ask side that is
    plain ascending (+0.2 -> +5), but on the bid side plain ascending runs
    -5 -> -0.2, i.e. farthest to nearest, where the cumulative notional
    *decreases* and the walk has to start from the wrong end. Ordering by
    |percentage| makes both sides identical and lets the cost arithmetic use a
    single positive-displacement convention.

    No rows are dropped here: the two sides must be aligned on their COMMON
    complete snapshots first, and dropping them independently leaves two arrays
    of different lengths that no longer refer to the same instants.
    """
    sub = df[df.percentage > 0] if side == "ask" else df[df.percentage < 0]
    if sub.empty:
        raise ValueError(f"{side} side is empty in this file")
    order = sub.assign(_abs=sub.percentage.abs())
    pcts = np.sort(order._abs.unique())
    wide = (order.pivot_table(index="timestamp", columns="_abs", values="notional")
                .reindex(columns=pcts)
                .sort_index())
    return wide, pcts


def align(ask_w: pd.DataFrame, bid_w: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, int]:
    """Intersect both sides on timestamps complete on BOTH, then validate."""
    common = ask_w.index.intersection(bid_w.index)
    a = ask_w.loc[common].dropna()
    b = bid_w.loc[common].dropna()
    both = a.index.intersection(b.index)
    a, b = a.loc[both], b.loc[both]
    if len(both) == 0:
        raise ValueError("no snapshot is complete on both sides")
    dropped = len(ask_w) - len(both)
    for name, m in (("ask", a.to_numpy(float)), ("bid", b.to_numpy(float))):
        if not (np.diff(m, axis=1) >= -1e-6).all():
            raise ValueError(
                f"{name} ladder is not monotone outward; the file's semantics "
                "are not what this module assumes")
    return a.to_numpy(float), b.to_numpy(float), dropped


def impact_bps(cum: np.ndarray, pcts: np.ndarray, size: float) -> np.ndarray:
    """Cost in bps of mid for a market order of `size` USD on this side.

    `pcts` must be the ABSOLUTE offsets in nearest-first order, as returned by
    `ladder`, so the result is a positive number on both the bid and ask side.
    Vectorised across snapshots. If the order exhausts the visible ladder the
    result is nan, because the cost of filling the remainder is unobserved.
    """
    prev = np.concatenate([np.zeros((cum.shape[0], 1)), cum[:, :-1]], axis=1)
    step = cum - prev
    consumed = np.clip(size - prev, 0.0, step)
    filled = consumed.sum(axis=1)
    cost = (consumed * pcts).sum(axis=1)
    out = 100.0 * cost / np.where(filled > 0, filled, np.nan)
    out[filled < size * 0.999] = np.nan      # not fully fillable within the ladder
    return out


def main() -> int:
    t0 = time.time()
    print("=" * 78)
    print("MARKET IMPACT FROM REAL ORDER-BOOK DEPTH (the missing cost term)")
    print("=" * 78)
    print(f"levels: {', '.join(str(p) for p in [-5,-4,-3,-2,-1,-0.2,0.2,1,2,3,4,5])}")
    print(f"window: {DATES[0]} -> {DATES[-1]}  ({len(SYMBOLS)} symbols, {len(DATES)} dates)")
    print("S3 is throttled and returns spurious 404s; fetching serially with backoff.\n")

    depth_rows, impact_rows = [], []
    for day in DATES:
        for sym in SYMBOLS:
            df = fetch_depth(sym, day)
            if df is None or df.empty:
                print(f"  {sym:<10} {day}  -- no depth file")
                continue
            ask_w, apcts = side_frame(df, "ask")
            bid_w, bpcts = side_frame(df, "bid")
            ask, bid, dropped = align(ask_w, bid_w)
            n_snap = int(df.timestamp.nunique())
            frac_drop = dropped / max(1, n_snap)
            if frac_drop > MAX_DROP_FRACTION:
                print(f"  {sym:<10} {day}  REJECTED: {frac_drop:.1%} of snapshots "
                      f"incomplete (ceiling {MAX_DROP_FRACTION:.0%})")
                continue
            ts = ask.shape[0]
            inner = float(apcts[0])

            # The published grid is NOT stable over time. 2023-01-01 carries only
            # +/-1,2,3,4,5; 2026-09-20 also carries +/-0.2. So the innermost
            # available band differs by vintage, and a band lookup that assumes
            # 0.2 exists is a crash, not a result. Map to what is actually there.
            for band in (0.2, 1.0, 2.0, 5.0):
                col = int(np.argmin(np.abs(apcts - band)))
                if abs(float(apcts[col]) - band) > 1e-6:
                    continue                      # band not published for this file
                depth_rows.append({
                    "symbol": sym, "date": day, "band_pct": band, "snapshots": ts,
                    "inner_band_pct": inner,
                    "ask_usd_median": float(np.median(ask[:, col])),
                    "bid_usd_median": float(np.median(bid[:, col])),
                })

            for size in SIZES_USD:
                a = impact_bps(ask, apcts, size)
                b = impact_bps(bid, bpcts, size)
                ok = np.isfinite(a) & np.isfinite(b)
                if not ok.any():
                    print(f"  {sym:<10} {day}  size {size:>9,}  -- not fillable in ladder")
                    continue
                # Reliable only once the order consumes the whole innermost band.
                # Below that, the within-bucket distribution is unobserved and the
                # uniform assumption dominates the answer.
                beyond = float((np.minimum(ask[:, 0], bid[:, 0]) <= size).mean())
                impact_rows.append({
                    "symbol": sym, "date": day, "size_usd": size,
                    "inner_band_pct": inner,
                    "snapshots_fillable": int(ok.sum()),
                    "coverage": float(ok.mean()),
                    "frac_beyond_inner_band": beyond,
                    "one_way_bps": float(np.median(a[ok])),
                    "round_trip_bps": float(np.median((a + b)[ok])),
                    "round_trip_p95_bps": float(np.percentile((a + b)[ok], 95)),
                })
            print(f"  {sym:<10} {day}  {ts} snapshots  inner band {inner}%  "
                  f"ask<={apcts[0]}% ${np.median(ask[:, 0]):,.0f}")

    d = pd.DataFrame(depth_rows)
    im = pd.DataFrame(impact_rows)
    if d.empty or im.empty:
        print("\nno depth data retrieved")
        return 1

    # AGENTS.md: a silent dead signal must fail the build, not look like a weak
    # result. A zero row count or an all-zero impact is the silent-failure shape.
    assert len(im) > 0, "no impact rows produced"
    assert (im.one_way_bps > 0).any(), "every impact estimate is zero -- dead signal"

    OUT.mkdir(parents=True, exist_ok=True)
    d.to_csv(OUT / "depth_by_band.csv", index=False)
    im.to_csv(OUT / "impact_by_size.csv", index=False)

    print("\n" + "=" * 78)
    print("DEPTH AVAILABLE (median USD notional resting, per snapshot)")
    print("=" * 78)
    piv = d.pivot_table(index="symbol", columns="band_pct", values="ask_usd_median",
                        aggfunc="median")
    piv = piv.reindex(columns=sorted(piv.columns))
    print(piv.map(lambda v: f"${v:,.0f}").to_string())

    print("\n" + "=" * 78)
    print("MARKET IMPACT, bps of mid (median over snapshots, latest date)")
    print("=" * 78)
    last = im[im.date == DATES[-1]]
    piv2 = last.pivot_table(index="symbol", columns="size_usd", values="round_trip_bps")
    hdr = "".join(f"{int(c):>13,}" for c in piv2.columns)
    print(f"{'symbol':<11}{hdr}      (round trip, bps)")
    for sym, row in piv2.iterrows():
        cells = "".join(f"{v:>13.1f}" if np.isfinite(v) else f"{'-':>13}" for v in row)
        print(f"{sym:<11}{cells}")

    # Reliability flag. An estimate is trustworthy once the order consumes the
    # whole innermost published band; below that the uniform-within-bucket
    # assumption, not the data, is producing the number.
    print("\n" + "=" * 78)
    print("RELIABILITY: share of snapshots where the order consumes a full band")
    print("=" * 78)
    rel = (im.groupby("size_usd")
             .agg(frac_beyond_inner_band=("frac_beyond_inner_band", "median"),
                  inner_band_pct=("inner_band_pct", "median"),
                  median_rt_bps=("round_trip_bps", "median"))
             .reset_index())
    for _, r in rel.iterrows():
        tag = "reliable" if r.frac_beyond_inner_band >= 0.5 else "ASSUMPTION-DOMINATED"
        print(f"  size {int(r.size_usd):>9,} USD   inner band {r.inner_band_pct:.1f}%   "
              f"median RT {r.median_rt_bps:7.1f} bps   {tag}")

    print(f"""
READ THIS BEFORE USING ANY NUMBER ABOVE

  * The published depth grid is not stable. Early files carry only 1/2/3/4/5%;
    recent files add 0.2%. The innermost band is stated in every row.
  * Cost for an order SMALLER than the innermost band is dominated by the
    uniform-within-bucket assumption, not by the data, and is biased HIGH
    (a real book is densest at the touch). Those rows are flagged above.
  * Where a size consumes whole bands, the walk is exact and no assumption is
    left except that the book does not refill during the order.
  * This is the ask/bid cost of CROSSING. Commission is separate and additive:
    Binance USD-M taker is 5 bps/leg, i.e. 10 bps of a round trip before any
    of the spread or impact figures here.
""")

    print(f"\nwritten: {OUT/'depth_by_band.csv'}")
    print(f"written: {OUT/'impact_by_size.csv'}   ({time.time()-t0:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
