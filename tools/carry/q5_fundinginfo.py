"""Summarise fundingInfo + leverageBracket; also record a negative-control (perp-only symbols)."""
import json
import sys
from collections import Counter

import requests

UA = {"User-Agent": "Mozilla/5.0 (research)"}
F = "https://fapi.binance.com"


def g(url):
    r = requests.get(url, headers=UA, timeout=30)
    return r.json()


fi = g(F + "/fapi/v1/fundingInfo")
print("fundingInfo rows:", len(fi))
print("keys:", sorted(fi[0].keys()))
caps = Counter(r["adjustedFundingRateCap"] for r in fi)
print("cap histogram:", dict(caps))
floors = Counter(r["adjustedFundingRateFloor"] for r in fi)
print("floor histogram:", dict(floors))
iv = Counter(r["fundingIntervalHours"] for r in fi)
print("fundingIntervalHours histogram:", dict(iv))
disc = Counter(r["disclaimer"] for r in fi)
print("disclaimer histogram:", dict(disc))
print()
want = {"BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "DOGEUSDT", "XRPUSDT",
        "LINKUSDT", "ADAUSDT", "LTCUSDT", "TRXUSDT", "BCHUSDT", "AVAXUSDT",
        "DOTUSDT", "MATICUSDT", "ARBUSDT", "OPUSDT", "SUIUSDT", "1000SHIBUSDT"}
print("--- selected symbols, verbatim ---")
for r in fi:
    if r["symbol"] in want:
        print(json.dumps(r))
print()
by = {r["symbol"]: r for r in fi}
for s in ("BTCUSDT", "ETHUSDT", "SOLUSDT", "1000SHIBUSDT", "SUSDT"):
    print(s, "->", json.dumps(by.get(s)))
print()
print("--- leverage brackets ---")
for sym in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
    lb = g(F + f"/fapi/v1/leverageBracket?symbol={sym}")
    if isinstance(lb, list) and lb:
        b = lb[0]
        brs = b.get("brackets", [])
        print(f"{sym}: notionalCoef={b.get('notionalCoef')} initialLeverage={b.get('initialLeverage')} "
              f"n_bracket={len(brs)} n_floor={b.get('floor')}")
        for br in brs[:6]:
            print("   ", json.dumps(br))
    else:
        print(sym, "->", json.dumps(lb)[:300])
    print()
