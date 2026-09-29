"""Gate 0, applied in the right order this time: test the BLOCKING feed first.

Last round the sequence was: probe the venue -> download 190 symbols of PRICE
data -> discover the REQUIRED funding feed was unreachable -> BLOCKED, with 107
seconds of download and a lot of plumbing wasted.

The fix is ordering, not effort. **The funding feed is what blocks the run**, so
it gets tested FIRST, on one symbol, before a single candle is fetched. If OKX's
funding history pages back to 2023 like its candles do, the venue line opens. If
it does not, the line is closed and this costs thirty seconds instead of ninety
minutes.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\okx_funding_probe.py
"""

from __future__ import annotations

import datetime as dt
import sys
import time

import requests

S = requests.Session()
S.headers.update({"User-Agent": "freqtrade-research/1.0"})
URL = "https://www.okx.com/api/v5/public/funding-rate-history"
START = dt.datetime(2022, 12, 1, tzinfo=dt.timezone.utc)


def one(inst: str) -> None:
    r = S.get(URL, params={"instId": inst}, timeout=30)
    j = r.json()
    d = j.get("data", [])
    if not d:
        print(f"   {inst}: no rows, code={j.get('code')} msg={j.get('msg')}")
        return
    ts = sorted(int(x["fundingTime"]) for x in d)
    print(f"   {inst}: rows={len(d)}  span "
          f"{dt.datetime.fromtimestamp(ts[0]/1000, dt.timezone.utc).date()} -> "
          f"{dt.datetime.fromtimestamp(ts[-1]/1000, dt.timezone.utc).date()}")


def walk(inst: str, pages: int = 8) -> int | None:
    """Page BACKWARDS with OKX's `after` cursor and report how far we get."""
    after = None
    oldest = None
    prev = None
    t0 = time.time()
    stuck = False
    for p in range(pages):
        params = {"instId": inst, "limit": "100"}
        if after is not None:
            params["after"] = str(after)      # OKX: records EARLIER than this
        r = S.get(URL, params=params, timeout=30)
        j = r.json()
        d = j.get("data", [])
        if not d:
            print(f"   page {p+1}: EMPTY code={j.get('code')} msg={j.get('msg')}")
            break
        ts = [int(x["fundingTime"]) for x in d]
        cur = min(ts)
        # the same guard the 11th bug demanded: prove the cursor advanced
        if prev is not None and cur >= prev:
            print(f"   page {p+1}: CURSOR DID NOT ADVANCE (stuck at "
                  f"{dt.datetime.fromtimestamp(cur/1000, dt.timezone.utc).date()})")
            stuck = True
            break
        prev = cur
        oldest = cur if oldest is None else min(oldest, cur)
        after = cur
        time.sleep(0.12)
    if oldest is None:
        print("   walk produced nothing")
        return None
    dt_old = dt.datetime.fromtimestamp(oldest / 1000, dt.timezone.utc)
    print(f"   {pages} requested pages in {time.time()-t0:.1f}s, oldest "
          f"{dt_old.date()}{' (CURSOR STUCK)' if stuck else ''}")
    bars = int((oldest - START.timestamp() * 1000) / (4 * 3600 * 1000) / 100)
    print(f"      -> {max(bars,0)} more pages of 100 to reach 2023-01-01")
    return oldest


def main() -> int:
    print("OKX FUNDING FEASIBILITY - tested BEFORE any candle download\n")
    print("[one call, no cursor]")
    one("BTC-USDT-SWAP")
    one("DOGE-USDT-SWAP")
    print("\n[paging backwards with `after`]")
    walk("BTC-USDT-SWAP", pages=10)

    print("\nDECISION (stated before the result is read):")
    print("  reaches 2023-01-01 or near it -> the venue line OPENS; download the")
    print("  candles, export, run the same frozen ladder on OKX, and compare the")
    print("  rung at which t >= 2.0 holds against Binance's.")
    print("  stuck within the last year -> the venue line is CLOSED, not BLOCKED,")
    print("  because no amount of downloading changes it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
