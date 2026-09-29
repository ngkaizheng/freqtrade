"""F-1: download Binance Vision daily `metrics` (open interest + positioning) for the
deployed 40-symbol universe, 2023-01-01 .. 2026-08-31.

WHY THIS FEED AND WHY IT MATTERS
--------------------------------
`docs-myself/GAP_ANALYSIS_2026-09-30.md` ranked Open Interest #1 for a strategic
reason: the two delivered books are BOTH pure price/volume trend on the SAME 40
symbols, so a third book from that family is the same bet twice. OI carries
information price and volume cannot - "was this move backed by new positions".

The archive is `um DAILY metrics`, not monthly. That was found by probing nine
candidate paths with a known-good klines URL as a CONTROL, after the first probe
returned 0/40 at every month and an all-or-nothing result is a bug signature, not
a data result.

⚠ THE COLUMNS ARE A FINDING IN THEIR OWN RIGHT. The archive carries not only
`sum_open_interest` but also:
    count_long_short_ratio            - retail account long/short positioning
    count_toptrader_long_short_ratio  - top-trader position long/short ratio
    sum_taker_long_short_vol_ratio    - TAKER BUY/SELL VOLUME RATIO
That last one is the `taker-flow` signal this project closed BY COST in
`CLOSED_FAMILIES.json` #11 - closed because the taker data was not in the repo.
**It was never refuted; it was unaffordable. Now it is available, and that entry
is reopened on new evidence rather than quietly reused.**

RESOLUTION
----------
The source is 5-minute (288 rows/day). The delivered books run on 4h bars, so this
keeps every 12th row -> 1h. The 5m source remains re-downloadable; the 1h form is
what is stored, and `OI_TIMEFRAME` records that so nobody later mistakes it for
5-minute data.

RESUMABILITY
------------
53,520 files, ~65 minutes of pure latency, against a host that has already
rate-limited this session twice. Written as a background job:
  * one output file per symbol, so a partial run is still 40 partial files and
    never a corrupt whole;
  * skips any symbol whose output already exists -> rerun to resume;
  * backs off on 429/418 instead of hammering;
  * prints a progress line so "hung" and "slow" are distinguishable.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\fetch_oi.py [--workers N]
"""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / "user_data" / "config_perp_forward_dry.json"
OUT = ROOT / "user_data" / "data" / "oi"
BASE = "https://data.binance.vision/data/futures/um/daily/metrics"

START = date(2023, 1, 1)
END = date(2026, 8, 31)
KEEP_EVERY = 12                       # 5m -> 1h
OI_TIMEFRAME = "1h"

KEEP_COLS = ["create_time", "symbol", "sum_open_interest", "sum_open_interest_value",
             "count_toptrader_long_short_ratio", "sum_toptrader_long_short_ratio",
             "count_long_short_ratio", "sum_taker_long_short_vol_ratio"]


def archive_symbol(pair: str) -> str:
    base, _, rest = pair.partition("/")
    return f"{base}{rest.split(':')[0]}"


def days() -> list[date]:
    out, d = [], START
    while d <= END:
        out.append(d)
        d += timedelta(days=1)
    return out


def fetch_symbol(sym: str, dl: list[date], retries: int = 3) -> tuple[str, int, str]:
    dest = OUT / f"{sym}-oi.parquet"
    if dest.exists() and dest.stat().st_size > 0:
        return sym, len(dl), "cached"
    parts, misses = [], 0
    for d in dl:
        ds = d.isoformat()
        url = f"{BASE}/{sym}/{sym}-metrics-{ds}.zip"
        for a in range(retries):
            try:
                r = requests.get(url, timeout=45)
                if r.status_code == 404:
                    misses += 1
                    break
                if r.status_code in (418, 429) or r.status_code >= 500:
                    time.sleep(3 * (a + 1))            # back off, do not hammer
                    continue
                if r.status_code != 200:
                    break
                import io
                import zipfile
                with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
                    name = [n for n in zf.namelist() if n.endswith(".csv")][0]
                    with zf.open(name) as fh:
                        parts.append(pd.read_csv(fh))
                break
            except Exception:                                    # noqa: BLE001
                time.sleep(2)
    if not parts:
        return sym, misses, "empty"
    df = pd.concat(parts, ignore_index=True)
    cols = [c for c in KEEP_COLS if c in df.columns]
    df = df[cols]
    df["create_time"] = pd.to_datetime(df["create_time"], errors="coerce")
    df = df.dropna(subset=["create_time"]).sort_values("create_time")
    df = df.iloc[::KEEP_EVERY]                        # 5m -> 1h
    for c in cols[2:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["sum_open_interest"]).reset_index(drop=True)
    df.to_parquet(dest, index=False)
    return sym, misses, f"{len(df):,} rows"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    syms = [archive_symbol(p) for p in cfg["exchange"]["pair_whitelist"]]
    dl = days()
    workers = 6
    if "--workers" in sys.argv:
        workers = int(sys.argv[sys.argv.index("--workers") + 1])
    print(f"fetching OI for {len(syms)} symbols x {len(dl)} days "
          f"({len(dl)*(KEEP_EVERY)} source files) at {workers} workers")
    print(f"resolution kept: {OI_TIMEFRAME} (every {KEEP_EVERY}th 5m bar) -> {OUT}")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i, (sym, misses, why) in enumerate(ex.map(lambda s: fetch_symbol(s, dl), syms), 1):
            el = time.time() - t0
            eta = el / i * (len(syms) - i)
            print(f"  [{i:>2}/{len(syms)}] {sym:<18} {why:<12} misses={misses:<4} "
                  f"{el/60:>5.1f}m elapsed, {eta/60:>5.1f}m left", flush=True)
    print(f"\ndone in {(time.time()-t0)/60:.1f} min; "
          f"{sum(f.stat().st_size for f in OUT.glob('*.parquet'))/1e6:,.0f} MB in {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
