import requests, json, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
for cid in ["real-world-assets-rwa","tokenized-products"]:
    ok=False
    for i in range(10):
        r=S.get(f"https://api.coingecko.com/api/v3/coins/categories/{cid}",timeout=60)
        if r.status_code==200:
            d=r.json(); ok=True; break
        time.sleep(25)
    if not ok: print(cid,"STILL RATE LIMITED"); continue
    print("="*100)
    print(f'{d.get("name")} | mcap=${(d.get("market_cap") or 0)/1e9:,.2f}B | 24h={(d.get("market_cap_change_24h") or 0):+.2f}% | updated={d.get("updated_at")}')
    cs=sorted(d.get("coins") or [], key=lambda x:-(x.get("market_cap") or 0))
    print(f"n_coins={len(cs)}")
    for c in cs[:14]:
        print(f'   {str(c.get("name"))[:24]:<26} rank={str(c.get("market_cap_rank")):>5} mcap=${(c.get("market_cap") or 0)/1e6:>9,.1f}M 24h={(c.get("price_change_percentage_24h") or 0):>8.2f}% vol24h=${(c.get("total_volume") or 0)/1e6:>7,.1f}M')
    time.sleep(20)
