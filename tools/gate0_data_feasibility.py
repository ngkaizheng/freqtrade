"""Gate 0 data feasibility: can we actually GET long US-equity history?

The handoff claims 33.6y of SPY but shipped only 16.7y. Before recommending an
equity research restart, confirm long history is obtainable for real -- otherwise
the recommendation repeats the same power failure in a new market.

Sources probed (all free, no key):
  * Stooq     - plain CSV download for US tickers
  * Yahoo/query1 - chart API JSON (no library needed)
  * FRED      - CSV endpoint for SP500 index
"""

import io
import json
import urllib.request

HDRS = {"User-Agent": "Mozilla/5.0 (research)"}


def fetch(url, timeout=45):
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def probe_stooq(ticker):
    url = f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d"
    try:
        b = fetch(url)
    except Exception as e:
        return f"FAIL {type(e).__name__}: {str(e)[:70]}"
    txt = b.decode("utf-8", errors="ignore")
    lines = [l for l in txt.strip().splitlines() if l.strip()]
    if len(lines) < 3 or "Date" not in lines[0]:
        return f"unexpected payload: {txt[:90]!r}"
    return (f"OK  rows={len(lines)-1}  first={lines[1].split(',')[0]}  "
            f"last={lines[-1].split(',')[0]}")


def probe_yahoo(ticker):
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{ticker}?period1=0&period2=9999999999&interval=1d")
    try:
        d = json.loads(fetch(url))
    except Exception as e:
        return f"FAIL {type(e).__name__}: {str(e)[:70]}"
    try:
        res = d["chart"]["result"][0]
        ts = res["timestamp"]
        import datetime as dt
        first = dt.datetime.utcfromtimestamp(ts[0]).date()
        last = dt.datetime.utcfromtimestamp(ts[-1]).date()
        return f"OK  bars={len(ts)}  {first} -> {last}"
    except Exception as e:
        return f"payload error: {type(e).__name__} {str(d)[:90]}"


def probe_fred(series):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
    try:
        b = fetch(url)
    except Exception as e:
        return f"FAIL {type(e).__name__}: {str(e)[:70]}"
    lines = [l for l in b.decode("utf-8", errors="ignore").strip().splitlines()]
    if len(lines) < 3:
        return "empty"
    return f"OK  rows={len(lines)-1}  first={lines[1].split(',')[0]}  last={lines[-1].split(',')[0]}"


def main():
    print("=" * 92)
    print("# GATE 0 — DATA FEASIBILITY FOR LONG US-EQUITY HISTORY")
    print("=" * 92)

    print(f"\n{'=' * 92}")
    print("# STOOQ (free CSV, no key)")
    print(f"{'=' * 92}")
    for t in ("SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "GLD", "AAPL", "MU"):
        print(f"  {t:<6} {probe_stooq(t)}")

    print(f"\n{'=' * 92}")
    print("# YAHOO CHART API (no library)")
    print(f"{'=' * 92}")
    for t in ("SPY", "QQQ", "GLD"):
        print(f"  {t:<6} {probe_yahoo(t)}")

    print(f"\n{'=' * 92}")
    print("# FRED (index series, no dividends)")
    print(f"{'=' * 92}")
    for s in ("SP500", "DGS10", "VIXCLS", "BAMLH0A0HYM2"):
        print(f"  {s:<14} {probe_fred(s)}")

    print(f"""
{'=' * 92}
# DECISION INPUTS
{'=' * 92}

  Whatever is reachable determines whether an equity restart is even worth
  starting. Gate 0 says: if required history > available history, do not run the
  study. The point of this probe is to find out BEFORE spending effort.""")


if __name__ == "__main__":
    main()
