"""Build a wide USD-M perpetual cross-section.

    python -m tools.cross_section.download_universe --timeframes 4h

The previously-rejected cross-sectional design had exactly one blocker:
"5 perpetuals is not a cross-section". Binance lists 527 trading USD-M
perpetuals, so the blocker is data acquisition, not a conceptual objection.

4h is downloaded first and at 1h/5m after it, because a cross-sectional
momentum design holds positions for days, so 4h bars are the finest
resolution that still supports a multi-day holding period at a manageable
file count.

Two facts about this universe must travel with every result that uses it
(state file §3.8): `exchangeInfo` returns only **currently-listed** contracts,
so this is a survivor universe, and the tokens that squeeze hardest are the
ones most likely to be absent from it. That bias is not correctable, only
disclosed.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests

S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
FAPI = "https://fapi.binance.com"
OUT = "shark_data/universe"
COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
        "quote_volume", "count", "taker_buy_volume", "taker_buy_quote_volume",
        "ignore"]
YEARS = [(2023, m) for m in range(1, 13)] + [(2024, m) for m in range(1, 13)] + \
        [(2025, m) for m in range(1, 13)] + [(2026, m) for m in range(1, 9)]
MONTHS = [(y, m) for y, m in YEARS]


def list_perps() -> list[str]:
    r = requests.get(f"{FAPI}/fapi/v1/exchangeInfo", timeout=60).json()
    return sorted(s["symbol"] for s in r["symbols"]
                  if s.get("quoteAsset") == "USDT"
                  and s.get("status") == "TRADING"
                  and s.get("contractType") == "PERPETUAL")


def _month_url(sym: str, tf: str, y: int, m: int) -> str:
    return (f"{S3}/data/futures/um/monthly/klines/{sym}/{tf}/"
            f"{sym}-{tf}-{y}-{m:02d}.zip")


def _fetch(sym: str, tf: str, y: int, m: int):
    url = _month_url(sym, tf, y, m)
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=45)
            if r.status_code != 200:
                return None
            with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
                name = [n for n in zf.namelist() if n.endswith(".csv")][0]
                raw = zf.read(name)
            df = pd.read_csv(io.BytesIO(raw), header=None)
            if df.shape[1] == 12:
                df.columns = COLS
            else:
                df = df.iloc[:, :6]
                df.columns = COLS[:6]
            return df
        except Exception:                                   # noqa: BLE001
            time.sleep(1.2 * (attempt + 1))
    return None


def build_symbol(sym: str, tf: str) -> tuple[str, int, str]:
    path = f"{OUT}/{sym}_{tf}.csv.gz"
    if os.path.exists(path):
        try:
            n = len(pd.read_csv(path, index_col=0))
            return sym, n, "cached"
        except Exception:                                   # noqa: BLE001
            pass
    frames = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for df in pool.map(lambda ym: _fetch(sym, tf, *ym), MONTHS):
            if df is not None and len(df):
                frames.append(df)
    if not frames:
        return sym, 0, "no data"
    df = pd.concat(frames, ignore_index=True)
    ot = pd.to_numeric(df["open_time"], errors="coerce")
    ot = ot.where(ot.between(1.4e12, 1.9e12))
    df = df[ot.notna()].copy()
    ot = ot[ot.notna()]
    if len(df) == 0:
        return sym, 0, "no valid timestamps"
    df.index = pd.DatetimeIndex(pd.to_datetime(ot.to_numpy(), unit="ms", utc=True))
    df = df[~df.index.duplicated(keep="last")].sort_index()
    out = df[["open", "high", "low", "close", "volume"]].apply(pd.to_numeric,
                                                               errors="coerce")
    os.makedirs(OUT, exist_ok=True)
    out.to_csv(path, compression="gzip")
    return sym, len(out), str(out.index.min().date())[:7]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeframes", nargs="*", default=["4h"])
    ap.add_argument("--limit", type=int, default=0, help="0 = all")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()

    syms = list_perps()
    if a.limit:
        syms = syms[: a.limit]
    print(f"{len(syms)} trading USD-M perps", flush=True)

    for tf in a.timeframes:
        print(f"\n=== {tf} ===", flush=True)
        t0, done, empty = time.time(), 0, 0
        with ThreadPoolExecutor(max_workers=a.workers) as pool:
            futs = {pool.submit(build_symbol, s, tf): s for s in syms}
            for f in as_completed(futs):
                sym, n, note = f.result()
                done += 1
                if n == 0:
                    empty += 1
                if done % 25 == 0 or done == len(syms):
                    print(f"  [{done}/{len(syms)}] {sym:<14} {n:>6} bars  "
                          f"({note})  empty={empty}  {time.time()-t0:.0f}s", flush=True)
        print(f"  {tf} complete in {time.time()-t0:.0f}s, {empty} symbols with no data",
              flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
