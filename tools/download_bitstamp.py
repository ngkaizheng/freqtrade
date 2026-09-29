"""Download long-history daily OHLCV from Bitstamp.

Why: Lo (2002) says SE(annualised Sharpe) ~ 1/sqrt(YEARS), independent of
sampling frequency. So the ONLY way to buy statistical power is more calendar
years. Binance caps BTC at 2018; Bitstamp reaches 2011-08-18.

Critical methodological bonus: 2011-2019 is a period that has NEVER been
searched in this project. It is a genuine holdout, not re-used data.

Output: user_data/data/bitstamp/<PAIR>-1d.feather in freqtrade's schema
(date, open, high, low, close, volume).
"""

import datetime as dt
import json
import os
import time
import urllib.request

import pandas as pd

HDRS = {"User-Agent": "Mozilla/5.0 (research)"}
OUT_DIR = "user_data/data/bitstamp"
STEP = 86400

PAIRS = {
    "BTC/USD": "btcusd",
    "ETH/USD": "ethusd",
    "LTC/USD": "ltcusd",
    "XRP/USD": "xrpusd",
    "BCH/USD": "bchusd",
}


def get_json(url, tries=4):
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers=HDRS)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except Exception:
            if a == tries - 1:
                raise
            time.sleep(1.5 * (a + 1))


def fetch_all(sym: str, end: int | None = None) -> pd.DataFrame:
    """Page BACKWARD through Bitstamp OHLC using `end` as the cursor.

    Bitstamp returns the last `limit` candles *before* `end`; `start` is only a
    lower bound and does not advance the window. Paging therefore walks
    backwards from the newest candle until no more data is returned.
    """
    rows = []
    cursor = end or int(time.time())
    while True:
        url = (f"https://www.bitstamp.net/api/v2/ohlc/{sym}/"
               f"?step={STEP}&limit=1000&end={cursor}")
        data = get_json(url)
        oh = data.get("data", {}).get("ohlc", [])
        if not oh:
            break
        rows.extend(oh)
        first = int(oh[0]["timestamp"])
        next_cursor = first - STEP
        if next_cursor >= cursor:
            break  # no backward progress -> done
        cursor = next_cursor
        if len(oh) < 1000:
            break
        time.sleep(0.15)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["timestamp"].astype(int), unit="s", utc=True)
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = df[c].astype(float)
    df = (df[["date", "open", "high", "low", "close", "volume"]]
          .drop_duplicates("date")
          .sort_values("date")
          .reset_index(drop=True))
    return df


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    print("downloading long-history daily data from Bitstamp\n")
    for pair, sym in PAIRS.items():
        try:
            df = fetch_all(sym)
        except Exception as e:
            print(f"  {pair:<10} FAILED {type(e).__name__}: {str(e)[:80]}")
            continue
        if df.empty:
            print(f"  {pair:<10} no data")
            continue
        fname = pair.replace("/", "_") + "-1d.feather"
        path = os.path.join(OUT_DIR, fname)
        df.to_feather(path)
        yrs = (df.date.max() - df.date.min()).days / 365.25
        print(f"  {pair:<10} {len(df):>6} rows  "
              f"{df.date.min().date()} -> {df.date.max().date()}  ({yrs:.1f}y)")

    print(f"\n{'=' * 92}")
    print(f"{'pair':<10}{'rows':>7}  {'from':<12}{'to':<12}{'years':>7}  "
          f"{'SE(Sharpe)':>11}")
    import glob
    for p in sorted(glob.glob(os.path.join(OUT_DIR, "*-1d.feather"))):
        d = pd.read_feather(p)
        yrs = (d.date.max() - d.date.min()).days / 365.25
        name = os.path.basename(p).replace("-1d.feather", "").replace("_", "/")
        print(f"{name:<10}{len(d):>7}  {str(d.date.min().date()):<12}"
              f"{str(d.date.max().date()):<12}{yrs:>7.1f}  {1/yrs**0.5:>11.3f}")


if __name__ == "__main__":
    main()
