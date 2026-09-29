"""Q5: live Binance API evidence collector. Prints raw JSON, no interpretation."""
import json
import sys

import requests

UA = {"User-Agent": "Mozilla/5.0 (research)"}
F = "https://fapi.binance.com"
S = "https://api.binance.com"


def g(url, label, limit=4000):
    try:
        r = requests.get(url, headers=UA, timeout=30)
    except Exception as e:  # noqa: BLE001
        print(f"##### {label} FAILED: {e}")
        return None
    print(f"##### {label} [{r.status_code}] {url}")
    try:
        j = r.json()
    except Exception:  # noqa: BLE001
        print(r.text[:limit])
        return None
    txt = json.dumps(j, indent=1)
    print(txt[:limit])
    print()
    return j


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("all", "fundinginfo"):
        g(F + "/fapi/v1/fundingInfo", "FUNDING INFO (caps/floors + interest rate)", 12000)
    if what in ("all", "lev"):
        for sym in ("BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT"):
            g(F + f"/fapi/v1/leverageBracket?symbol={sym}", f"LEVERAGE BRACKET {sym}", 3000)
    if what in ("all", "prem"):
        for sym in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
            g(F + f"/fapi/v1/premiumIndex?symbol={sym}", f"PREMIUM INDEX {sym}", 2000)
    if what in ("all", "fr"):
        g(F + "/fapi/v1/fundingRate?symbol=BTCUSDT&limit=10", "FUNDING RATE BTCUSDT last 10", 3000)
        g(F + "/fapi/v1/fundingRate?symbol=BTCUSDT&limit=1&startTime=1600000000000",
          "FUNDING RATE 2020-09 snapshot", 1000)
    if what in ("all", "ei"):
        j = g(F + "/fapi/v1/exchangeInfo", "USD-M EXCHANGE INFO (truncated)", 200)
        if j:
            s = j["symbols"][0]
            print(json.dumps(s, indent=1)[:3000], "\n")
    if what in ("all", "spot"):
        g(S + "/api/v3/exchangeInfo?symbols=%5B%22BTCUSDT%22%5D", "SPOT exchangeInfo BTCUSDT", 3000)
    if what in ("all", "assetindex"):
        g(F + "/fapi/v1/assetIndex?symbol=BTCUSDT", "ASSET INDEX BTCUSDT", 1500)
        g(F + "/fapi/v1/constituents?symbol=BTCUSDT", "CONSTITUENTS BTCUSDT", 2000)
    if what in ("all", "klines"):
        g(F + "/fapi/v1/markPriceKlines?symbol=BTCUSDT&interval=8h&limit=3",
          "MARK PRICE KLINES 8h", 2000)
        g(F + "/fapi/v1/premiumIndexKlines?symbol=BTCUSDT&interval=8h&limit=3",
          "PREMIUM INDEX KLINES 8h", 2000)
