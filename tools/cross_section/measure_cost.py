"""Measure the realised round-trip cost this project has been assuming.

Every conclusion in this repository rests on one number that nobody has
measured: the round-trip cost of crossing a crypto perpetual. The published
bull and bear cases on cross-sectional crypto momentum differ almost entirely
because of it —

    Fieberg et al. (JFQA 2025, bull)   30-40 bps per trade
    Arefev (SSRN 7404139, null)         ~59 bps per trade
    THIS REPO                           12-18 bps round trip

— a 3-5x spread. If the true cost is at the high end, the 4h and 5m results
are worse than reported, not better. If it is at the low end, some lines that
were closed on cost grounds deserve another look. Either way the number is
load-bearing and currently unmeasured.

METHOD. Binance publishes aggregated trades. From a tick series the Roll
(1984) estimator gives the **effective spread**, which is the quantity that
matters for a taker:

    spread_hat = 2 * sqrt( -Cov( p_t - p_{t-1},  p_{t-1} - p_{t-2} ) )

Roll estimates the effective spread because consecutive trades that bounce
between bid and ask are negatively autocorrelated. It measures what a
market-taking trader actually pays, not the quoted spread, and it is the
standard estimator in exactly this setting.

Caveats stated up front: Roll assumes the efficient component is a random
walk and a stationary spread, both of which fail in a squeeze, so the
estimate is a lower bound on stress conditions. It is a MARKET spread and
excludes commission. It is measured on the historical tape, so it contains
no information about order-book depth at a given size, which is the term that
would bind for a book larger than the top of book.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
import zipfile

import numpy as np
import pandas as pd
import requests

S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
FAPI = "https://fapi.binance.com"
OUT = "shark_data/costs"


def top_perps(n: int = 20) -> list[str]:
    r = requests.get(f"{FAPI}/fapi/v1/ticker/24hr", timeout=60).json()
    rows = [t for t in r if t.get("symbol", "").endswith("USDT")
            and "PERPETUAL" in t.get("contractType", "PERPETUAL")]
    rows.sort(key=lambda t: float(t.get("quoteVolume", 0)), reverse=True)
    return [t["symbol"] for t in rows[:n]]


def fetch_aggtrades(sym: str, day: str) -> pd.DataFrame | None:
    url = f"{S3}/data/futures/um/daily/aggTrades/{sym}/{sym}-aggTrades-{day}.zip"
    for _ in range(3):
        try:
            r = requests.get(url, timeout=90)
            if r.status_code != 200:
                return None
            with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
                name = [n for n in zf.namelist() if n.endswith(".csv")][0]
                raw = zf.read(name)
            df = pd.read_csv(io.BytesIO(raw), header=None)
            # a,p,q,f,l,T,m  -> keep price and whether the buyer was the maker
            return pd.DataFrame({"p": pd.to_numeric(df[1], errors="coerce"),
                                "m": pd.to_numeric(df[3], errors="coerce")}).dropna()
        except Exception:                                    # noqa: BLE001
            time.sleep(1.5)
    return None


def roll_spread(prices: np.ndarray) -> tuple[float, float]:
    """Roll effective spread in bps, plus the tick-level return variance.

    Returns (spread_bps, r2) where r2 reports how much of the return variance
    the negative lag-1 autocorrelation explains. A low r2 means Roll's
    identifying assumption is doing real work, i.e. the estimate is credible.
    """
    if len(prices) < 200:
        return np.nan, np.nan
    dp = np.diff(prices)
    dp1, dp2 = dp[1:], dp[:-1]
    cov = float(np.mean(dp1 * dp2))
    var = float(np.var(dp))
    if cov >= 0 or var <= 0:
        return np.nan, np.nan
    spread = 2.0 * np.sqrt(-cov)
    return float(spread / np.mean(prices) * 1e4), float(-cov / var)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", type=int, default=12)
    ap.add_argument("--days", type=int, default=2)
    ap.add_argument("--date", default="2026-09-20")
    a = ap.parse_args()

    t0 = time.time()
    syms = top_perps(a.symbols)
    print("=" * 78)
    print("MEASURED ROUND-TRIP COST (the premise every conclusion rests on)")
    print("=" * 78)
    print(f"symbols: {', '.join(syms)}")
    print(f"tape:   {a.days} day(s) from {a.date}, Binance aggTrades\n")

    tv = requests.get(f"{FAPI}/fapi/v1/exchangeInfo", timeout=60).json()
    taker = {s["symbol"]: float(s.get("takerCommission", 0.0005))
             for s in tv["symbols"]}

    rows = []
    for sym in syms:
        day = a.date
        spreads, r2s, ntr, used = [], [], 0, None
        for _ in range(a.days):
            df = fetch_aggtrades(sym, day)
            if df is None or len(df) < 500:
                day = (pd.Timestamp(day) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
                continue
            sp, r2 = roll_spread(df["p"].to_numpy())
            if np.isfinite(sp):
                spreads.append(sp)
                r2s.append(r2)
                ntr += len(df)
                used = day          # the date actually measured, not the one asked for
            day = (pd.Timestamp(day) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        if not spreads:
            print(f"  {sym:<14} no tape")
            continue
        sp = float(np.median(spreads))
        fee_bps = taker.get(sym, 5.0) * 1e4
        rt = sp * 2 + fee_bps * 2          # cross in and out, both legs taker
        # The window is walked backwards until a tape is found, so a symbol that
        # did not exist on the requested day silently reports a DIFFERENT day's
        # spread. For a calm-day average that is harmless. For a STRESS date it
        # quietly dilutes the crash with calm sessions, which is the one thing
        # the measurement exists to avoid. So the dates actually used are
        # recorded and printed, and `drifted` is flagged.
        drifted = used != a.date
        rows.append({"symbol": sym, "roll_spread_bps": sp,
                     "roll_r2": float(np.nanmedian(r2s)),
                     "taker_fee_bps_leg": fee_bps,
                     "round_trip_bps": rt, "trades": ntr,
                     "date_requested": a.date, "date_used": used,
                     "drifted": drifted})
        print(f"  {sym:<14} roll spread {sp:6.2f} bps  (r2={np.nanmedian(r2s):.2f})  "
              f"fee {fee_bps:.1f}bps/leg  ->  round trip {rt:6.1f} bps"
              f"{'   [DATE DRIFTED from ' + a.date + ']' if drifted else ''}")

    f = pd.DataFrame(rows)
    if f.empty:
        print("no tapes retrieved")
        return 1
    n_drift = int(f.drifted.sum()) if "drifted" in f else 0
    if n_drift:
        print(f"\n  !! {n_drift}/{len(f)} symbols measured on a date OTHER than "
              f"{a.date}. Their spreads do NOT describe the requested session.")
    print(f"\n--- summary over {len(f)} symbols ---")
    print(f"  Roll effective spread (one way) : median {f['roll_spread_bps'].median():.2f} bps, "
          f"range {f['roll_spread_bps'].min():.2f}-{f['roll_spread_bps'].max():.2f}")
    print(f"  FULL ROUND TRIP (spread x2 + taker x2): median {f['round_trip_bps'].median():.1f} bps, "
          f"range {f['round_trip_bps'].min():.1f}-{f['round_trip_bps'].max():.1f}")
    print(f"  median Roll r2                : {f['roll_r2'].median():.2f}")

    print(f"""
COMPARISON WITH THE THREE PUBLISHED ASSUMPTIONS

  this repo (used throughout)   12-18 bps round trip
  Fieberg et al. (bull case)   30-40 bps per trade
  Arefev (the only null)       ~59 bps per trade

A measured round trip of {f['round_trip_bps'].median():.0f} bps on top-{len(f)}
perpetuals places this repo's assumption at the {'optimistic' if f['round_trip_bps'].median() < 18 else 'CORRECT, or still optimistic' if f['round_trip_bps'].median() < 30 else 'TOO OPTIMISTIC - the null case is right'}
end of that range.

WHAT THIS DOES AND DOES NOT CHANGE
  * It does NOT reopen any closed line by itself. A higher cost makes them
    worse, never better.
  * It DOES resolve whether the cost premise was conservative. The project has
    described 12-18 bps as "conservative" throughout. If the measurement says
    otherwise, that word has to come out of the reports.
  * It is a market spread. It excludes commission, order-book depth beyond
    the touch, and any size above the top of book. A book large enough to move
    the market pays more, and the square-root impact law only holds above a
    volume fraction of ~1e-3; retail size sits below that, where impact is
    approximately LINEAR and materially worse.
""")
    import os
    os.makedirs(OUT, exist_ok=True)
    f.to_csv(f"{OUT}/realised_cost_{a.date.replace('-', '')}.csv", index=False)
    print(f"written: {OUT}/realised_cost_{a.date.replace('-', '')}.csv  "
          f"({time.time()-t0:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
