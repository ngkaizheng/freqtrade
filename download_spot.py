"""Download Binance spot 1h klines for the perp universe.

The full-hedge calculation needs both legs, and only 4 of the 20 funding
symbols had a spot book on disk. That sample is not representative: it
happens to exclude UNI and LTC, the two strongest recent carriers. Widening
it is the difference between a 4-name illustration and an actual answer.

Source: data.binance.vision spot monthly klines, same archive layout as the
perp files but under /spot/.
"""

from __future__ import annotations

import io
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests

S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
        "quote_volume", "count", "taker_buy_volume", "taker_buy_quote_volume",
        "ignore"]
OUT = "shark_data/spot"
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
           "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT"]
YEARS = [(2023, m) for m in range(1, 13)] + [(2024, m) for m in range(1, 13)] + \
        [(2025, m) for m in range(1, 13)] + [(2026, m) for m in range(1, 9)]


def months(sym: str):
    for y, m in YEARS:
        yield y, m


def fetch_month(sym: str, y: int, m: int) -> pd.DataFrame | None:
    url = f"{S3}/data/spot/monthly/klines/{sym}/1h/{sym}-1h-{y}-{m:02d}.zip"
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=45)
            if r.status_code != 200:
                return None
            with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
                name = [n for n in zf.namelist() if n.endswith(".csv")][0]
                with zf.open(name) as fh:
                    raw = fh.read()
            df = pd.read_csv(io.BytesIO(raw), header=None)
            if df.shape[1] == 12:
                df.columns = COLS
            else:
                df = df.iloc[:, :6]
                df.columns = COLS[:6]
            return df
        except Exception:                       # noqa: BLE001
            time.sleep(1.5 * (attempt + 1))
    return None


def build(sym: str) -> str:
    frames = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for df in pool.map(lambda ym: fetch_month(sym, *ym), months(sym)):
            if df is not None and len(df):
                frames.append(df)
    if not frames:
        return f"{sym}: nothing"
    df = pd.concat(frames, ignore_index=True)
    ot = pd.to_numeric(df["open_time"], errors="coerce")
    # Some spot months use the older 6-column layout; those rows have no
    # timestamp and must be dropped rather than turned into a garbage index.
    ot = ot.where(ot.between(1.4e12, 1.9e12))
    df = df[ot.notna()].copy()
    ot = ot[ot.notna()]
    df.index = pd.DatetimeIndex(pd.to_datetime(ot.to_numpy(), unit="ms", utc=True))
    df = df[~df.index.duplicated(keep="last")].sort_index()
    out = df[["open", "high", "low", "close", "volume"]].apply(
        pd.to_numeric, errors="coerce")
    import os
    os.makedirs(OUT, exist_ok=True)
    p = f"{OUT}/{sym}_1h.csv.gz"
    out.to_csv(p, compression="gzip")
    return (f"{sym}: {len(out):,} bars "
            f"{out.index.min().date()} -> {out.index.max().date()}")


def main() -> int:
    t0 = time.time()
    for sym in SYMBOLS:
        print(build(sym), flush=True)
    print(f"elapsed {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
