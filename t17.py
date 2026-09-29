import requests, json, datetime, time, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
def gg(u,p,tries=8):
    for i in range(tries):
        try:
            r=S.get(u,params=p,timeout=45)
            if r.status_code==200: return r.json()
        except Exception: pass
        time.sleep(8+i*4)
    return None
mk=gg("https://api.coingecko.com/api/v3/coins/markets",
      {"vs_currency":"usd","order":"market_cap_desc","per_page":"250","page":"1","price_change_percentage":"7d,30d"})
print("top coins fetched:", len(mk) if mk else 0, flush=True)
ids=[c["id"] for c in mk]
json.dump(mk,open("top250_now.json","w"))
hist={}
for i,cid in enumerate(ids):
    d=gg(f"https://api.coingecko.com/api/v3/coins/{cid}/market_chart",{"vs_currency":"usd","days":"95"})
    if d and "market_caps" in d:
        hist[cid]=d["market_caps"]
    if i%10==0: print(i,cid,len(hist),flush=True)
    time.sleep(2.2)
json.dump(hist,open("top250_hist.json","w"))
print("DONE", len(hist))
