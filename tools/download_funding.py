"""Download Binance USDT-M perpetual funding-rate history for the majors.

Funding rate is paid every 8h between longs and shorts. It is a REAL cost, not
a transformation of price — a genuinely orthogonal information source.

Binance funding rate semantics:
  positive -> longs pay shorts (crowded long, bullish positioning)
  negative -> shorts pay longs (crowded short, bearish positioning)
"""

import json
import os
import time
import urllib.request

import pandas as pd

MAJORS = [
    "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "DOT", "LINK",
    "LTC", "BCH", "ATOM", "UNI", "AAVE", "XLM", "ETC", "ALGO", "FIL",
    "NEO", "TRX",
]

OUT_DIR = "user_data/data/binance_funding"
BASE = "https://fapi.binance.com/fapi/v1/fundingRate"
START_MS = 1546300800000  # 2019-01-01
LIMIT = 1000


def fetch_symbol(symbol: str) -> pd.DataFrame:
    rows = []
    cursor = START_MS
    while True:
        url = (f"{BASE}?symbol={symbol}&startTime={cursor}"
               f"&limit={LIMIT}")
        for attempt in range(4):
            try:
                with urllib.request.urlopen(url, timeout=25) as r:
                    batch = json.loads(r.read())
                break
            except Exception as e:
                if attempt == 3:
                    raise
                print(f"    retry {attempt + 1} ({type(e).__name__})")
                time.sleep(2 * (attempt + 1))
        if not batch:
            break
        rows.extend(batch)
        last = batch[-1]["fundingTime"]
        if len(batch) < LIMIT:
            break
        cursor = last + 1
        time.sleep(0.12)  # be polite to the API

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["fundingTime"] = pd.to_datetime(df["fundingTime"], unit="ms", utc=True)
    df["fundingRate"] = df["fundingRate"].astype(float)
    df = (df[["fundingTime", "fundingRate"]]
          .drop_duplicates("fundingTime")
          .sort_values("fundingTime")
          .reset_index(drop=True))
    return df


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"downloading funding rate history for {len(MAJORS)} majors\n")
    summary = []
    for m in MAJORS:
        symbol = f"{m}USDT"
        try:
            df = fetch_symbol(symbol)
        except Exception as e:
            print(f"  {symbol:<10} FAILED {type(e).__name__}: {str(e)[:80]}")
            continue
        if df.empty:
            print(f"  {symbol:<10} no data")
            continue
        path = os.path.join(OUT_DIR, f"{m}_USDT-funding.feather")
        df.to_feather(path)
        summary.append((m, len(df), df.fundingTime.min().date(),
                        df.fundingTime.max().date(),
                        df.fundingRate.mean()))
        print(f"  {symbol:<10} {len(df):>6} records  "
              f"{df.fundingTime.min().date()} -> {df.fundingTime.max().date()}  "
              f"mean {df.fundingRate.mean():+.6f}")

    print(f"\n{'=' * 92}")
    print(f"{'pair':<10}{'records':>8}  {'from':<12}{'to':<12}{'mean 8h rate':>14}"
          f"{'annualised':>12}")
    for m, n, a, b, mu in summary:
        print(f"{m + '/USDT':<10}{n:>8}  {str(a):<12}{str(b):<12}"
              f"{mu:>14.6f}{mu * 3 * 365:>12.2%}")
    print(f"\ntotal pairs: {len(summary)}")


if __name__ == "__main__":
    main()
