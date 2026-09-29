"""Probe Binance for tokenized / synthetic US stock instruments.

Question: can the Binance API serve MU, NVDA, SNDK, SPCX, TSLA, AAPL, META,
AMD, GOOGL?

History note: Binance listed "stock tokens" (TSLA, AAPL, COIN, MSFT...) in 2021
and delisted them in July 2021 under regulatory pressure. Whether a successor
product exists now must be checked, not assumed.

This script scans spot and USDT-M futures exchangeInfo for stock-like symbols,
then probes klines for any hits so we can see HISTORY LENGTH and LIQUIDITY --
which decide whether the data is usable at all.
"""

import json
import sys
import time
import urllib.request

HDRS = {"User-Agent": "Mozilla/5.0 (research)"}

TICKERS = ["MU", "NVDA", "SNDK", "SPCX", "TSLA", "AAPL", "META", "AMD",
           "GOOGL", "MSFT", "AMZN", "NFLX", "INTC", "AVGO", "QCOM", "SPY", "QQQ"]

SPOT = "https://api.binance.com/api/v3"
FAPI = "https://fapi.binance.com/fapi/v1"


def get(url, timeout=30):
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def scan(label, base, info_path, quote_filter=None):
    """Return symbols whose BASE asset looks like a stock ticker."""
    try:
        data = get(f"{base}{info_path}")
    except Exception as e:
        print(f"  {label}: FAILED {type(e).__name__}: {str(e)[:90]}")
        return []
    syms = data.get("symbols", [])
    hits = []
    for s in syms:
        b = s.get("baseAsset", "") or ""
        q = s.get("quoteAsset", "") or ""
        # exact ticker, or ticker + suffix like X / T / PERP
        cand = b.upper()
        for t in TICKERS:
            if cand == t or cand.startswith(t + "X") or cand.startswith(t + "_") \
               or cand.rstrip("X") == t:
                hits.append((s.get("symbol"), b, q, s.get("status"),
                             s.get("contractType", "")))
                break
    print(f"  {label}: scanned {len(syms)} symbols, {len(hits)} stock-like hits")
    for h in hits[:40]:
        print(f"      {h[0]:<22} base={h[1]:<8} quote={h[2]:<6} "
              f"status={h[3]:<8} type={h[4]}")
    return hits


def kline_history(base, path, symbol):
    """Report first/last kline date and recent volume."""
    import datetime as dt
    try:
        # earliest
        k0 = get(f"{base}{path}?symbol={symbol}&interval=1d&startTime=0&limit=5")
        k1 = get(f"{base}{path}?symbol={symbol}&interval=1d&limit=5")
    except Exception as e:
        print(f"      {symbol}: kline FAILED {type(e).__name__}: {str(e)[:80]}")
        return None
    if not k0 or not k1:
        print(f"      {symbol}: no klines returned")
        return None
    first = dt.datetime.utcfromtimestamp(k0[0][0] / 1000).date()
    last = dt.datetime.utcfromtimestamp(k1[-1][0] / 1000).date()
    quote_vol = float(k1[-1][7])
    return {"first": first, "last": last, "quote_vol": quote_vol}


def main():
    print("=" * 92)
    print("# BINANCE TOKENIZED-STOCK PROBE")
    print("=" * 92)
    print(f"\n  looking for: {', '.join(TICKERS)}\n")

    print("=" * 92)
    print("# 1. SCAN EXCHANGE INFO")
    print("=" * 92 + "\n")
    spot = scan("SPOT", SPOT, "/exchangeInfo")
    fut = scan("USDT-M FUTURES", FAPI, "/exchangeInfo")
    print(f"\n  (quote assets seen in futures sample: "
          f"{sorted({h[2] for h in fut})[:10] if fut else 'n/a'})")

    # Broader look: any symbol containing a ticker as substring
    print(f"\n{'=' * 92}")
    print("# 2. BROAD SUBSTRING SEARCH (catches odd naming)")
    print(f"{'=' * 92}\n")
    for label, base, path in (("SPOT", SPOT, "/exchangeInfo"),
                              ("FUTURES", FAPI, "/exchangeInfo")):
        try:
            data = get(f"{base}{path}")
        except Exception as e:
            print(f"  {label}: {type(e).__name__}")
            continue
        found = []
        for s in data.get("symbols", []):
            sym = (s.get("symbol") or "").upper()
            b = (s.get("baseAsset") or "").upper()
            for t in TICKERS:
                if t in sym or t in b:
                    found.append((s.get("symbol"), b, s.get("quoteAsset"),
                                  s.get("status")))
                    break
        print(f"  {label}: {len(found)} substring matches")
        for f in found[:30]:
            print(f"      {f[0]:<24} base={f[1]:<10} quote={f[2]:<6} {f[3]}")

    # 3. History for any real hits
    print(f"\n{'=' * 92}")
    print("# 3. HISTORY + LIQUIDITY FOR ANY HITS")
    print(f"{'=' * 92}\n")
    if not spot and not fut:
        print("  no instruments found -- nothing to measure")
    else:
        for label, base, path, hits in (("SPOT", SPOT, "/klines", spot),
                                        ("FUTURES", FAPI, "/klines", fut)):
            for h in hits[:10]:
                info = kline_history(base, path, h[0])
                if info:
                    print(f"      {h[0]:<20} {label:<8} "
                          f"{info['first']} -> {info['last']}  "
                          f"last-day quote vol {info['quote_vol']:,.0f}")

    # 4. Also check the 2021-era stock token endpoints for completeness
    print(f"\n{'=' * 92}")
    print("# 4. LEGACY STOCK-TOKEN ENDPOINTS (2021 product)")
    print(f"{'=' * 92}\n")
    for url in ("https://api.binance.com/sapi/v1/equity/market/exchangeInfo",
                "https://api.binance.com/sapi/v1/stock/market/exchangeInfo",
                "https://api.binance.com/api/v3/stock/exchangeInfo"):
        try:
            r = get(url, timeout=15)
            print(f"  OK   {url}\n       {str(r)[:200]}")
        except Exception as e:
            print(f"  fail {url} -> {type(e).__name__}: {str(e)[:70]}")

    print(f"\n{'=' * 92}")
    print("# SUMMARY")
    print(f"{'=' * 92}")
    print(f"  spot stock-like symbols   : {len(spot)}")
    print(f"  futures stock-like symbols: {len(fut)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
