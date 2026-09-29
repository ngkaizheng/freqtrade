import requests, json, sys, time, datetime
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
for i in range(6):
    r=S.get("https://api.coingecko.com/api/v3/global",timeout=60)
    if r.status_code==200: g=r.json()["data"]; break
    time.sleep(20)
print("=== CoinGecko /global (as of live) ===")
print("total_market_cap_usd : $%.4fT"%(g["total_market_cap"]["usd"]/1e12))
print("total_volume_usd     : $%.2fB"%(g["total_volume"]["usd"]/1e9))
print("btc_dominance        : %.2f%%"%g["market_cap_percentage"]["btc"])
print("eth_dominance        : %.2f%%"%g["market_cap_percentage"]["eth"])
print("usdt_dominance       : %.2f%%"%g["market_cap_percentage"]["usdt"])
print("usdc_dominance       : %.2f%%"%g["market_cap_percentage"]["usdc"])
print("mcap_change_24h_usd  : %.2f%%"%g.get("market_cap_change_percentage_24h_usd"))
print("active_cryptocurrencies:",g["active_cryptocurrencies"])
print("updated_at           :", datetime.datetime.fromtimestamp(g["updated_at"],datetime.timezone.utc).isoformat())
json.dump({k:g[k] for k in ["total_market_cap","market_cap_percentage","total_volume","market_cap_change_percentage_24h_usd","updated_at"]},open("global.json","w"),indent=1)
# partial dominance from top100_hist
try:
    h=json.load(open("top100_hist.json"))
    print(f"\n=== partial top-{len(h)} history ===")
    def mcap_at(pts,target):
        c=[p for p in pts if p[0]<=target]
        return c[-1][1] if c else None
    ref=max(max(p[0] for p in v) for v in h.values())
    import collections
    agg=collections.defaultdict(float)
    for cid,pts in h.items():
        v=mcap_at(pts,ref)
        if v: agg[ref]+=v
    print("common ref ts:",datetime.datetime.fromtimestamp(ref/1000,datetime.timezone.utc).strftime("%Y-%m-%d")," sum mcap of %d coins: $%.4fT"%(len(h),agg[ref]/1e12))
    for d in (7,30,90):
        t=ref-d*86400000
        tot=0.0; btc=0.0
        for cid,pts in h.items():
            v=mcap_at(pts,t)
            if v:
                tot+=v
                if cid=="bitcoin": btc=v
        if btc: print(f"  t-{d}d ({datetime.datetime.fromtimestamp(t/1000,datetime.timezone.utc).strftime('%Y-%m-%d')}): sum=${tot/1e12:.4f}T  BTC=${btc/1e12:.4f}T  dominance={round(100*btc/tot,2)}%")
except Exception as e:
    print("partial err",repr(e)[:150])
