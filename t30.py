import requests, json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
d=S.get("https://api.llama.fi/overview/dexs?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true&dataType=dailyVolume",timeout=180).json()
ps=d["protocols"]
names={ (p.get("displayName") or p.get("name")):p for p in ps }
print("searching perp venues...")
for q in ["Hyperliquid","Lighter","Aster","dYdX","PancakeSwap Perpetual","Variational","edgeX","Axiom","Jupiter","Variational"]:
    hit=[k for k in names if q.lower() in k.lower()]
    for h in hit[:2]:
        p=names[h]; print(f"  {h:<32} cat={p.get('category'):<16} 30d=${(p.get('total30d') or 0)/1e6:,.1f}M  slug={p.get('slug')} module={p.get('module')}")
print()
print("all categories present in dexs overview with totals:")
import collections
c=collections.defaultdict(float)
for p in ps: c[p.get("category") or "UNCAT"]+= (p.get("total30d") or 0)
for k,v in sorted(c.items(),key=lambda x:-x[1])[:15]: print(f"  {k:<24} ${v/1e6:,.0f}M")
