"""Live: compare Binance spot vs the perp's composite index; also assetIndex and constituents."""
import json

import requests

UA = {"User-Agent": "Mozilla/5.0 (research)"}


def g(url, params=None, limit=2500):
    r = requests.get(url, params=params, headers=UA, timeout=25)
    print(f"--- [{r.status_code}] {r.url}")
    try:
        print(json.dumps(r.json(), indent=1)[:limit])
    except Exception:  # noqa: BLE001
        print(r.text[:limit])
    print()


g("https://api.binance.com/api/v3/ticker/bookTicker", {"symbol": "BTCUSDT"}, 800)
g("https://api.binance.com/api/v3/ticker/price", {"symbol": "BTCUSDT"}, 400)
g("https://fapi.binance.com/fapi/v1/premiumIndex", {"symbol": "BTCUSDT"}, 600)
g("https://fapi.binance.com/fapi/v1/ticker/bookTicker", {"symbol": "BTCUSDT"}, 800)
g("https://fapi.binance.com/fapi/v1/indexPriceConstituents", {"symbol": "BTCUSDT"}, 3000)
g("https://fapi.binance.com/fapi/v1/assetIndex", {"symbol": "BTCUSDT"}, 800)
g("https://fapi.binance.com/fapi/v1/fundingRate", {"symbol": "BTCUSDT", "limit": 3}, 900)
g("https://fapi.binance.com/fapi/v1/fundingRate", {"symbol": "BTCUSDT", "limit": 1,
                                                 "startTime": 1649721600000,
                                                 "endTime": 1649808000000}, 900)
g("https://fapi.binance.com/fapi/v1/markPriceKlines", {"symbol": "BTCUSDT", "interval": "8h", "limit": 2}, 900)
g("https://fapi.binance.com/fapi/v1/exchangeInfo",
  {"symbols": '["BTCUSDT","ETHUSDT"]'}, 3500)
g("https://api.binance.com/sapi/v1/capital/config/getall", None, 400)
