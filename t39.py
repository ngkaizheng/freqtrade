import requests, json, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
def get(u,p=None,tries=6):
    for i in range(tries):
        r=S.get(u,params=p,timeout=60)
        if r.status_code==200: return r.json()
        time.sleep(10+i*4)
    return None
for cid in ["real-world-assets-rwa","tokenized-assets","tokenized-gold","tokenized-us-treasuries"]:
    d=get(f"https://api.coingecko.com/api/v3/coins/categories/{cid}")
    if not d: print(cid,"FAIL"); continue
    print("="*95)
    print(f"{d.get('name')}  id={cid}  mcap=${(d.get('market_cap') or 0)/1e9:,.2f}B  24h={(d.get('market_cap_change_24h') or 0):+.2f}%  vol24h=${(d.get('volume_24h') or 0)/1e6:,.0f}M  updated={d.get('updated_at')}")
    print("-"*95)
    for c in sorted(d.get("coins") or [], key=lambda x:-(x.get("market_cap") or 0))[:12]:
        print(f"   {c.get('name')[:26]:<28} rank={str(c.get('market_cap_rank')):>5} mcap=${(c.get('market_cap') or 0)/1e6:>10,.1f}M  24h={(c.get('price_change_percentage_24h') or 0):>8.2f}%  vol24h=${(c.get('total_volume') or 0)/1e6:>8,.1f}M  ${c.get('id')}")
