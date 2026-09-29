import collections
import requests

UA = {"User-Agent": "Mozilla/5.0"}
d = requests.get("https://fapi.binance.com/fapi/v1/fundingInfo", headers=UA, timeout=60).json()
c = collections.Counter(x.get("fundingIntervalHours") for x in d)
print("ALL", len(d), "symbols. fundingIntervalHours histogram:",
      dict(sorted(c.items(), key=lambda kv: -kv[1])))
maj = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT",
       "LINKUSDT", "AVAXUSDT", "LTCUSDT", "TRXUSDT", "SUIUSDT", "AAVEUSDT", "UNIUSDT",
       "DOTUSDT", "BCHUSDT", "XLMUSDT", "NEARUSDT", "APTUSDT", "ARBUSDT", "ATOMUSDT",
       "ETCUSDT", "FILUSDT", "ALGOUSDT", "NEOUSDT"]
m = {x["symbol"]: x for x in d}
print()
for s in maj:
    x = m.get(s)
    iv = x.get("fundingIntervalHours") if x else "?"
    cap = x.get("adjustedFundingRateCap") if x else "?"
    flag = "   <-- NOT 8h" if iv != 8 else ""
    print(f"  {s:10s} interval={str(iv):>4}  cap={str(cap):>12}{flag}")

non8 = [x["symbol"] for x in d if x.get("fundingIntervalHours") != 8]
print(f"\n  non-8h symbols: {len(non8)} of {len(d)} ({len(non8)/len(d)*100:.0f}%)")
big = [s for s in non8 if any(s.startswith(p) for p in
       ("BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "LINK", "AVAX", "LTC", "SUI",
        "AAVE", "UNI", "DOT", "BNB", "NEAR", "APT", "ARB", "ATOM", "ETC", "FIL"))]
print("  of the repo's 20 + other majors, on non-8h:", sorted(set(big)) or "none")
