"""Probe Bybit's funding-history endpoint directly, with no file writes."""
from __future__ import annotations

import sys
import time

import requests

S = requests.Session()
S.headers.update({"User-Agent": "freqtrade-research/1.0"})

CASES = [
    ("limit 5", {"category": "linear", "symbol": "BTCUSDT", "limit": "5"}),
    ("limit 200", {"category": "linear", "symbol": "BTCUSDT", "limit": "200"}),
    ("no limit", {"category": "linear", "symbol": "BTCUSDT"}),
    ("alt symbol", {"category": "linear", "symbol": "DOGEUSDT", "limit": "5"}),
]

for label, p in CASES:
    try:
        r = S.get("https://api.bybit.com/v5/market/funding/history",
                  params=p, timeout=30)
        j = r.json()
        lst = j.get("result", {}).get("list", [])
        print(f"{label:<12} retCode={j.get('retCode')} retMsg={j.get('retMsg')} "
              f"rows={len(lst)}")
        if lst:
            k = list(lst[0].keys())
            print(f"   keys: {k}")
            print(f"   newest: { {x: lst[0][x] for x in k[:4]} }")
    except Exception as e:  # noqa: BLE001
        print(f"{label:<12} FAILED {type(e).__name__}: {e}")
    time.sleep(0.3)

print("\nDOES startTime PAGE BACKWARDS? (the `end` cursor did not)")
import datetime as dt
for label, p in (
    ("startTime 2022-12", {"category": "linear", "symbol": "BTCUSDT",
                            "limit": "200",
                            "startTime": str(int(dt.datetime(
                                2022, 12, 1, tzinfo=dt.timezone.utc
                            ).timestamp() * 1000))}),
    ("startTime 2024-01", {"category": "linear", "symbol": "BTCUSDT",
                            "limit": "200",
                            "startTime": str(int(dt.datetime(
                                2024, 1, 1, tzinfo=dt.timezone.utc
                            ).timestamp() * 1000))}),
    ("startTime+end", {"category": "linear", "symbol": "BTCUSDT", "limit": "200",
                       "startTime": str(int(dt.datetime(
                           2022, 12, 1, tzinfo=dt.timezone.utc
                       ).timestamp() * 1000)),
                       "end": str(int(dt.datetime(
                           2024, 1, 1, tzinfo=dt.timezone.utc
                       ).timestamp() * 1000))}),
):
    try:
        r = S.get("https://api.bybit.com/v5/market/funding/history",
                  params=p, timeout=30)
        j = r.json()
        lst = j.get("result", {}).get("list", [])
        if lst:
            ts = sorted(int(x["fundingRateTimestamp"]) for x in lst)
            print(f"   {label:<20} rows={len(lst):<5} "
                  f"span {dt.datetime.fromtimestamp(ts[0]/1000, dt.timezone.utc).date()}"
                  f" -> {dt.datetime.fromtimestamp(ts[-1]/1000, dt.timezone.utc).date()}")
        else:
            print(f"   {label:<20} rows=0 retCode={j.get('retCode')} "
                  f"{j.get('retMsg')}")
    except Exception as e:  # noqa: BLE001
        print(f"   {label:<20} FAILED {type(e).__name__}")
    time.sleep(0.3)

