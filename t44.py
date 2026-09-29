import requests, json, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
def get(u,tries=7):
    for i in range(tries):
        r=S.get(u,timeout=60)
        if r.status_code==200: return r.json()
        time.sleep(18+i*6)
    return None
for cid in ["real-world-assets-rwa","tokenized-products","tokenized-gold","tokenized-stock","tokenized-commodities","tokenized-exchange-traded-funds-etfs"]:
    d=get(f"https://api.coingecko.com/api/v3/coins/categories/{cid}")
    if not d: print(cid,"FAIL"); continue
    print("="*100)
    print(f'{d.get("name")} | mcap=${(d.get("market_cap") or 0)/1e9:,.2f}B | 24h={(d.get("market_cap_change_24h") or 0):+.2f}% | vol24h=${(d.get("volume_24h") or 0)/1e6:,.0f}M | updated={d.get("updated_at")}')
    for c in sorted(d.get("coins") or [], key=lambda x:-(x.get("market_cap") or 0))[:10]:
        print(f'   {str(c.get("name"))[:24]:<26} rank={str(c.get("market_cap_rank")):>5} mcap=${(c.get("market_cap") or 0)/1e6:>9,.1f}M 24h={(c.get("price_change_percentage_24h") or 0):>8.2f}% vol24h=${(c.get("total_volume") or 0)/1e6:>7,.1f}M')
