"""Gate 0 continued: can the venue APIs PAGE BACKWARDS?

The first probe found OKX serving 18 days and Bybit 5.5 months of candle
history, which by the pre-stated decision rule would make the venue line
BLOCKED. But that rule was written before checking the one thing that decides
it: **these endpoints take a cursor.**

Binance Vision gave this project 515 symbols in minutes because it publishes
monthly zips. Neither OKX nor Bybit does. So the whole feasibility question is
whether the REST API can be paged back to 2023, symbol by symbol, at a tolerable
rate - because a 2023-2026 test that only reaches back to 2026-04 is not a slower
test, it is no test at all.

Nothing is downloaded here. This asks one question of each venue: how far back
does ONE page-cursor walk go, and what is the per-request latency?

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\venue_paging.py
"""

from __future__ import annotations

import sys
import time

import requests

S = requests.Session()
S.headers.update({"User-Agent": "freqtrade-research/1.0"})
MS_4H = 4 * 3600 * 1000


def okx_walk(inst: str = "BTC-USDT-SWAP", pages: int = 6) -> None:
    url = "https://www.okx.com/api/v5/market/history-candles"
    end = None
    oldest = None
    t0 = time.time()
    for p in range(pages):
        params = {"instId": inst, "bar": "4H", "limit": "100"}
        if end is not None:
            params["after"] = str(end)   # OKX: `after` = return records EARLIER than this ts
        r = S.get(url, params=params, timeout=40)
        j = r.json()
        d = j.get("data", [])
        if not d:
            print(f"   page {p+1}: EMPTY (code={j.get('code')}, msg={j.get('msg')})")
            break
        ts = [int(x[0]) for x in d]
        oldest = min(ts) if oldest is None else min(oldest, min(ts))
        end = min(ts)
        time.sleep(0.15)
    import datetime as dt
    print(f"   OKX {inst}: {pages} pages in {time.time()-t0:.1f}s, "
          f"oldest {dt.datetime.fromtimestamp(oldest/1000, dt.timezone.utc).date() if oldest else None}")
    n_to_2023 = 0
    if oldest:
        import datetime as dt2
        target = dt2.datetime(2023, 1, 1, tzinfo=dt2.timezone.utc).timestamp() * 1000
        n_to_2023 = int((oldest - target) / MS_4H / 100)
        print(f"      -> {n_to_2023} more pages of 100 to reach 2023-01-01")


def bybit_walk(sym: str = "BTCUSDT", pages: int = 6) -> None:
    url = "https://api.bybit.com/v5/market/kline"
    end = None
    oldest = None
    t0 = time.time()
    for p in range(pages):
        params = {"category": "linear", "symbol": sym, "interval": "240",
                  "limit": "1000"}
        if end is not None:
            params["end"] = str(end)     # Bybit: `end` = return records at or before this ts
        r = S.get(url, params=params, timeout=40)
        j = r.json()
        d = j.get("result", {}).get("list", [])
        if not d:
            print(f"   page {p+1}: EMPTY (retCode={j.get('retCode')}, "
                  f"retMsg={j.get('retMsg')})")
            break
        ts = [int(x[0]) for x in d]
        oldest = min(ts) if oldest is None else min(oldest, min(ts))
        end = min(ts)
        time.sleep(0.12)
    import datetime as dt
    print(f"   Bybit {sym}: {pages} pages in {time.time()-t0:.1f}s, "
          f"oldest {dt.datetime.fromtimestamp(oldest/1000, dt.timezone.utc).date() if oldest else None}")
    if oldest:
        import datetime as dt2
        target = dt2.datetime(2023, 1, 1, tzinfo=dt2.timezone.utc).timestamp() * 1000
        n = int((oldest - target) / MS_4H / 1000)
        print(f"      -> {n} more pages of 1000 to reach 2023-01-01")


def main() -> int:
    print("CAN THE VENUE APIs PAGE BACKWARDS TO 2023?\n")
    print("[OKX]  (history-candles, cursor=`after`, 100 bars/page)")
    okx_walk()
    print("\n[Bybit]  (kline, cursor=`end`, 1000 bars/page)")
    bybit_walk()

    print("\nDECISION (same rule as the first probe, applied to the numbers above):")
    print("  If pages-to-2023 is in the tens, the venue line is FEASIBLE and the")
    print("  frozen rule can be run on a second venue. If it is in the hundreds or")
    print("  thousands per symbol, the line is BLOCKED - a full universe would need")
    print("  more requests than Binance Vision's whole 8,540-file download used,")
    print("  and the honest report is BLOCKED, not an approximation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
