"""SCOUT ONLY - listing-rate power check for the new-listing hypothesis.

Counts Binance USDT PERPETUAL listings by onboardDate year, straight from the
exchange's own exchangeInfo endpoint. Primary-source measurement of the ONE
number that decides whether this hypothesis is testable at all: n events/year.
"""
import json
import collections
import datetime
import ssl
import urllib.request

ctx = ssl.create_default_context()
try:
    with urllib.request.urlopen("https://fapi.binance.com/fapi/v1/exchangeInfo", timeout=30, context=ctx) as r:
        d = json.load(r)
except Exception as e:  # noqa: BLE001
    print("ERR fetching exchangeInfo:", type(e).__name__, e)
    raise SystemExit(1)

syms = d["symbols"]
print("total symbols in exchangeInfo :", len(syms))
print("status counts                 :", dict(collections.Counter(s.get("status") for s in syms)))
print("contractType counts           :", dict(collections.Counter(s.get("contractType") for s in syms)))

perp = [s for s in syms
        if s.get("contractType") == "PERPETUAL"
        and s.get("status") == "TRADING"
        and s.get("quoteAsset") == "USDT"]

print()
print("USDT PERP currently TRADING   :", len(perp))

cnt = collections.Counter()
nodate = 0
for s in perp:
    od = s.get("onboardDate")
    if not od:
        nodate += 1
        continue
    cnt[datetime.datetime.utcfromtimestamp(od / 1000.0).year] += 1

print("perps with no onboardDate      :", nodate)
print()
print("--- new USDT perps onboarded, by year ---")
for y in sorted(cnt):
    print(f"  {y}: {cnt[y]:4d}")

recent = sum(v for k, v in cnt.items() if k >= 2023)
print()
print("new perps onboarded 2023..now :", recent)
yrs = [k for k in cnt if k >= 2023]
if yrs:
    print("mean per year 2023..now      : %.1f" % (recent / (max(yrs) - min(yrs) + 1)))
print("mean per year 2025..now      : %.1f"
      % (sum(cnt[y] for y in cnt if y >= 2025) / len([y for y in cnt if y >= 2025])))

# how many listings per week in the most active year
for y in sorted(cnt):
    if y >= 2023:
        print(f"  {y}: {cnt[y]/52.0:.1f} perps/week")
