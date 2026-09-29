"""Gate 0 (charter 2.C): is a second venue even FEASIBLE as a data source?

Run this BEFORE downloading anything, per `RESEARCH_GOAL.md` 2.C. If the data
is not reachable with enough history, the venue idea is BLOCKED and must be
reported as blocked rather than approximated.

What is being checked, per venue:
  1. does the public API list USDT-margined perpetuals at all
  2. how far back does the candle endpoint actually reach
  3. is there a bulk archive (monthly zips) like Binance Vision, which is what
     made the 515-symbol panel possible in minutes

Why the venue at all: the entire ladder result is a COST story - the strategy
works where liquidity is high and fails where it is thin, and cost_R falls with
tradability. **A venue is a pure cost lever that this project has never pulled**,
and it is the last major axis untouched. It is also independent in the sense
the charter requires: different microstructure, different listing universe,
different fee schedule, not a parameter of anything already closed.

This script only probes. It downloads nothing.
"""

from __future__ import annotations

import sys
import time

import requests

S = requests.Session()
S.headers.update({"User-Agent": "freqtrade-research/1.0"})


def probe(name: str, fn) -> None:
    t0 = time.time()
    try:
        fn()
        print(f"   ({time.time()-t0:.1f}s)")
    except Exception as e:  # noqa: BLE001
        print(f"   FAILED after {time.time()-t0:.1f}s: {type(e).__name__}: {e}")


def okx_instruments() -> None:
    r = S.get("https://www.okx.com/api/v5/public/instruments?instType=SWAP", timeout=40)
    j = r.json()
    n = [i for i in j.get("data", []) if i.get("settleCcy") == "USDT"
         and i.get("state") == "live"]
    print(f"   OKX USDT SWAP live: {len(n)}")
    print(f"   sample: {[i['instId'] for i in n[:6]]}")


def okx_depth() -> None:
    for inst in ("BTC-USDT-SWAP", "ETH-USDT-SWAP", "DOGE-USDT-SWAP"):
        r = S.get(f"https://www.okx.com/api/v5/market/history-candles"
                  f"?instId={inst}&bar=4H&limit=100", timeout=40)
        j = r.json()
        d = j.get("data", [])
        oldest = d[-1][0] if d else None
        print(f"   history-candles {inst}: code={j.get('code')} rows={len(d)} "
              f"oldest_ts_ms={oldest}")
    # the archive route that actually matters
    for url in (
        "https://static.okx.com/cdn/okex/spot/daily/spot BTC-USDT 4H 20260101.zip",
        "https://www.okx.com/data-download/OKX_SWAP_4H.csv",
    ):
        try:
            r = S.head(url, timeout=25, allow_redirects=True)
            print(f"   bulk {url[:60]}... -> HTTP {r.status_code}")
        except Exception as e:  # noqa: BLE001
            print(f"   bulk probe failed: {type(e).__name__}")


def bybit_instruments() -> None:
    r = S.get("https://api.bybit.com/v5/market/instruments-info"
              "?category=linear&limit=1000", timeout=40)
    j = r.json()
    n = [x for x in j.get("result", {}).get("list", [])
         if x.get("quoteCoin") == "USDT" and x.get("status") == "Trading"]
    print(f"   Bybit USDT linear Trading: {len(n)}")


def bybit_depth() -> None:
    # Bybit serves klines back to listing; one request proves reachability
    r = S.get("https://api.bybit.com/v5/market/kline?category=linear"
              "&symbol=BTCUSDT&interval=240&limit=1000", timeout=40)
    j = r.json()
    d = j.get("result", {}).get("list", [])
    oldest = d[-1][0] if d else None
    print(f"   Bybit kline BTCUSDT 4h: ret={j.get('retCode')} rows={len(d)} "
          f"oldest_ts_ms={oldest}")


def main() -> int:
    print("VENUE FEASIBILITY PROBE (Gate 0, charter 2.C) - downloads nothing\n")
    print("[OKX]")
    probe("okx", okx_instruments)
    probe("okx_depth", okx_depth)
    print("\n[Bybit]")
    probe("bybit", bybit_instruments)
    probe("bybit_depth", bybit_depth)

    print("\nDECISION RULE, stated before the result is read:")
    print("  * bulk monthly/daily archives reachable -> the venue line is FEASIBLE,")
    print("    download the same top-N universe and run the frozen rule.")
    print("  * API-only with a few thousand bars -> NOT feasible for a 2023-2026")
    print("    test; the line is BLOCKED and must be reported as blocked.")
    print("  * neither reachable -> the line is BLOCKED, no approximation allowed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
