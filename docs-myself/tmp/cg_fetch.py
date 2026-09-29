"""Cache CoinGecko market data for research (rate-limit tolerant)."""
import json
import os
import sys
import time

import requests

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cg_cache")
os.makedirs(CACHE, exist_ok=True)
HDR = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
FIELDS = [
    "id", "symbol", "name", "current_price", "market_cap", "market_cap_rank",
    "fully_diluted_valuation", "total_volume", "circulating_supply",
    "total_supply", "max_supply", "ath", "ath_change_percentage", "ath_date",
    "atl", "atl_change_percentage", "atl_date", "last_updated",
    "price_change_percentage_1h_in_currency",
    "price_change_percentage_24h_in_currency",
    "price_change_percentage_7d_in_currency",
    "price_change_percentage_14d_in_currency",
    "price_change_percentage_30d_in_currency",
    "price_change_percentage_60d_in_currency",
    "price_change_percentage_200d_in_currency",
    "price_change_percentage_1y_in_currency",
]


def get(path, params, tries=10, wait=10):
    for attempt in range(tries):
        r = requests.get("https://api.coingecko.com/api/v3/" + path,
                         params=params, headers=HDR, timeout=30)
        if r.status_code == 200:
            return r.json()
        time.sleep(wait)
    return {"__error__": r.status_code, "__body__": r.text[:300]}


def search(q):
    fn = os.path.join(CACHE, "search_" + q.replace(" ", "_") + ".json")
    if os.path.exists(fn):
        return json.load(open(fn))
    d = get("search", {"query": q})
    json.dump(d, open(fn, "w"))
    return d


def markets(ids, tag):
    fn = os.path.join(CACHE, "markets_" + tag + ".json")
    if os.path.exists(fn):
        return json.load(open(fn))
    d = get("coins/markets", {
        "vs_currency": "usd", "ids": ",".join(ids),
        "price_change_percentage": "1h,24h,7d,14d,30d,60d,200d,1y",
        "precision": "full"})
    json.dump(d, open(fn, "w"))
    return d


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "search":
        for q in sys.argv[2:]:
            d = search(q)
            print("===", q)
            for c in d.get("coins", [])[:12]:
                print("   ", c.get("id"), "|", c.get("symbol"), "|",
                      c.get("name"), "| rank", c.get("market_cap_rank"))
    elif mode == "markets":
        tag = sys.argv[2]
        d = markets(sys.argv[3:], tag)
        if isinstance(d, dict):
            print(json.dumps(d)[:500])
        else:
            for c in d:
                print("=== %s (%s) rank %s" % (c["name"], c["symbol"], c["market_cap_rank"]))
                for f in FIELDS:
                    print("   %-42s %s" % (f, c.get(f)))
