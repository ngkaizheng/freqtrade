import requests, json, datetime, time
S = requests.Session()
S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
def g(u, **kw):
    r = S.get(u, timeout=45, **kw)
    return r
now = datetime.datetime.now(datetime.timezone.utc)
print("NOW_UTC", now.isoformat())

# 1. Simple price for BTC/ETH/SOL + 24h/7d/30d
for pid in ["bitcoin","ethereum","solana"]:
    r = g(f"https://api.coingecko.com/api/v3/simple/price",
          params={"ids":pid,"vs_currencies":"usd","include_market_cap":"true",
                  "include_24hr_change":"true","include_last_updated_at":"true"})
    print(pid, r.status_code, r.text[:400])
    time.sleep(2.5)
