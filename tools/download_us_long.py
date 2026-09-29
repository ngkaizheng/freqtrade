"""Download long US-equity history from the Yahoo chart API.

Confirmed reachable: SPY 1993-01-29 -> present (8,467 bars). This gives 33.6
years vs crypto's 14.6 -- SE(Sharpe) 0.17 vs 0.26, i.e. ~1.5x better resolution.

Writes the same schema as the existing caches (Date,Open,High,Low,Close,Volume)
so the existing backtest scripts work unchanged.

Output: user_data/data/us_long/<TICKER>.csv
"""

import datetime as dt
import json
import os
import time
import urllib.request

import pandas as pd

HDRS = {"User-Agent": "Mozilla/5.0 (research)"}
OUT = "user_data/data/us_long"

TICKERS = [
    # broad market
    "SPY", "QQQ", "IWM", "DIA", "EFA", "EEM",
    # rates / commodities / real assets
    "TLT", "IEF", "GLD", "SLV", "VNQ", "TIP",
    # sectors (long history, useful for cross-sectional work)
    "XLE", "XLF", "XLK", "XLV", "XLP", "XLU", "XLI", "XLY",
    # mega caps with long history
    "AAPL", "MSFT", "JNJ", "KO", "PG", "WMT", "XOM", "JPM", "IBM", "GE",
    # the tickers the user asked about, where they exist
    "MU", "NVDA", "TSLA", "META", "AMD", "GOOGL", "AMZN", "NFLX", "AVGO", "QCOM",
]


def fetch(ticker):
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{ticker}?period1=0&period2=9999999999&interval=1d"
           "&events=div%2Csplit")
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def to_frame(ticker, d):
    res = d["chart"]["result"][0]
    ts = res["timestamp"]
    q = res["indicators"]["quote"][0]
    adj = res["indicators"].get("adjclose", [{}])[0].get("adjclose")
    df = pd.DataFrame({
        "Date": pd.to_datetime(ts, unit="s", utc=True).tz_localize(None),
        "Open": q["open"], "High": q["high"], "Low": q["low"],
        "Close": q["close"], "Volume": q["volume"],
    })
    if adj:
        df["AdjClose"] = adj
    df = df.dropna(subset=["Close"]).drop_duplicates("Date").sort_values("Date")
    return df.reset_index(drop=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    print("=" * 92)
    print("# DOWNLOADING LONG US-EQUITY HISTORY (Yahoo chart API)")
    print("=" * 92)

    rows = []
    for t in TICKERS:
        try:
            d = fetch(t)
            df = to_frame(t, d)
            if df.empty:
                print(f"  {t:<6} empty")
                continue
            df.to_csv(os.path.join(OUT, f"{t}.csv"), index=False)
            yrs = (df["Date"].max() - df["Date"].min()).days / 365.25
            rows.append({"ticker": t, "start": df["Date"].min().date(),
                         "end": df["Date"].max().date(), "rows": len(df),
                         "years": yrs})
            print(f"  {t:<6} {len(df):>6} rows  {df['Date'].min().date()} -> "
                  f"{df['Date'].max().date()}  ({yrs:.1f}y)")
        except Exception as e:
            print(f"  {t:<6} FAILED {type(e).__name__}: {str(e)[:70]}")
        time.sleep(0.35)

    if not rows:
        print("\n  nothing downloaded")
        return 1

    df = pd.DataFrame(rows).sort_values("years", ascending=False)
    print(f"\n{'=' * 92}")
    print("# SUMMARY")
    print(f"{'=' * 92}")
    print(f"\n  tickers downloaded : {len(df)}")
    print(f"  longest            : {df['years'].max():.1f}y "
          f"({df.iloc[0]['ticker']}, from {df.iloc[0]['start']})")
    print(f"  median             : {df['years'].median():.1f}y")
    print(f"  SE(Sharpe) at max  : {1/df['years'].max()**0.5:.3f}")

    lo = df[df["years"] >= 30]
    print(f"\n  tickers with >=30y : {len(lo)}")
    for _, r in lo.iterrows():
        print(f"    {r['ticker']:<6} {r['years']:.1f}y from {r['start']}")

    print(f"\n  saved to {OUT}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
