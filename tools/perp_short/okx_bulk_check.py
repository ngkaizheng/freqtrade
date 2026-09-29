"""Last check on the venue line: does OKX publish a BULK funding archive?

Both venues' REST funding endpoints are capped at 1-3 months, and the pre-stated
decision rule says a cap that no amount of downloading moves is a CLOSE, not a
BLOCK. Before applying that, one thing could still open it: a bulk archive, which
is what made the Binance panel possible in the first place (Binance Vision's
8,540 monthly zips).

This probes the documented static.okx.com path patterns and reports exactly what
each returned, so the close is on the record rather than assumed.
"""

from __future__ import annotations

import sys
import time

import requests

S = requests.Session()
S.headers.update({"User-Agent": "freqtrade-research/1.0"})

CANDIDATES = [
    "https://static.okx.com/cdn/okex/perp/monthly/funding-rate/BTC-USDT-SWAP-2024-01.zip",
    "https://static.okx.com/cdn/okex/perp/daily/funding-rate/BTC-USDT-SWAP-20240101.zip",
    "https://static.okx.com/cdn/okex/perp/monthly/history-candles/BTC-USDT-SWAP-4H-2024-01.zip",
    "https://static.okx.com/cdn/okex/spot/monthly/spot/2024-01/BTC-USDT-4h.zip",
    "https://static.okx.com/cdn/okex/perp/monthly/BTC-USDT-SWAP-2024-01.zip",
    "https://www.okx.com/data-download",
]

for u in CANDIDATES:
    try:
        r = S.head(u, timeout=25, allow_redirects=True)
        print(f"   {r.status_code}  {u}")
        if r.status_code == 200:
            print("      *** BULK ARCHIVE REACHABLE - the venue line is OPEN ***")
    except Exception as e:  # noqa: BLE001
        print(f"   ERR {type(e).__name__}  {u}")
    time.sleep(0.3)

print("\nVERDICT RULE: if every candidate is 404, the venue line is CLOSED -")
print("REST funding is capped at 1-3 months on both venues and no bulk")
print("archive exists, so no amount of downloading changes it.")
