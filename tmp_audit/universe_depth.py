"""How wide a cross-sectional universe is actually available, by study start date."""

import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = {"User-Agent": "Mozilla/5.0"}
BASE = "https://data.binance.vision/data/futures/um/monthly/klines/{sym}/1h/{sym}-1h-{ym}.zip"

info = json.loads(urllib.request.urlopen(
    urllib.request.Request("https://fapi.binance.com/fapi/v1/exchangeInfo", headers=UA), timeout=60).read())
syms = [s["symbol"] for s in info["symbols"]
        if s["contractType"] == "PERPETUAL" and s["quoteAsset"] == "USDT"
        and s["status"] in ("TRADING", "SETTLING")]
print(f"candidates (TRADING + SETTLING): {len(syms)}")


def has(sym, ym):
    try:
        urllib.request.urlopen(
            urllib.request.Request(BASE.format(sym=sym, ym=ym), method="HEAD", headers=UA), timeout=25)
        return True
    except Exception:
        return False


PROBES = ["2020-01", "2021-01", "2022-01", "2023-01", "2024-01", "2025-01"]
sample = syms[::4]          # ~1/4 of the list, evenly spread
print(f"probing {len(sample)} symbols at {len(PROBES)} dates ...\n")

with ThreadPoolExecutor(max_workers=24) as ex:
    results = list(ex.map(lambda s: (s, [has(s, y) for y in PROBES]), sample))

print(f"{'first month with 1h archive available':<42} {'# of 527':>10}  {'%':>6}")
print("-" * 62)
for i, y in enumerate(PROBES):
    n = sum(1 for _, r in results if r[i])
    print(f"  {y} and everything after            {n:>10}  {100*n/len(syms):5.1f}%")

first_avail = {}
for s, r in results:
    idx = next((i for i, v in enumerate(r) if v), None)
    if idx is not None:
        first_avail[s] = PROBES[idx]

print()
print("Symbols with NO archive at any probed date (dead or too new):",
      len(sample) - len(first_avail))

print()
print("=" * 74)
print("THE USABLE UNIVERSE FOR A BACKTEST STARTING ON A GIVEN DATE")
print("=" * 74)
print("""
A cross-sectional book needs every member present on every rebalance date, so
the universe is set by the symbols that already existed at the study start.
From the sample above, extrapolated to all 527:
""")
for i, y in enumerate(PROBES):
    n = sum(1 for _, r in results if r[i])
    est = int(n / len(sample) * len(syms))
    print(f"  start {y}  -> roughly {est:>3} symbols available from day one")

print()
print("Earlier recall: diversification saturates near 20 names (measured rho 0.297,")
print("1.21x total benefit from 5 -> 200 names). A 30-50 name universe captures")
print("essentially all of the available diversification, so a 3-year study is")
print("sufficient and does not require going back to 2020 with a thinner set.")
