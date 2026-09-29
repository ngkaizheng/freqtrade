import requests, json, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
def gg(u,p,tries=6):
    for i in range(tries):
        try:
            r=S.get(u,params=p,timeout=40)
            if r.status_code==200: return r.json()
        except Exception: pass
        time.sleep(15+i*8)
    return None
mk=gg("https://api.coingecko.com/api/v3/coins/markets",{"vs_currency":"usd","order":"market_cap_desc","per_page":"100","page":"1"})
if not mk: print("MARKETS FAILED"); raise SystemExit
ids=[c["id"] for c in mk]
print("top100 total mcap now = $%.4fT"%(sum(c["market_cap"] or 0 for c in mk)/1e12),flush=True)
hist={}
for i,cid in enumerate(ids):
    d=gg(f"https://api.coingecko.com/api/v3/coins/{cid}/market_chart",{"vs_currency":"usd","days":"95"})
    if d and "market_caps" in d: hist[cid]=d["market_caps"]
    if i%4==0:
        print(i,cid,len(hist),flush=True); json.dump(hist,open("top100_hist.json","w"))
    time.sleep(9)
json.dump(hist,open("top100_hist.json","w"))
print("DONE",len(hist),flush=True)
