import requests, json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
for cat in ["Derivatives","Dexs"]:
    r=S.get("https://api.llama.fi/overview/dexs",params={"excludeTotalDataChart":"false","excludeTotalDataChartBreakdown":"true","dataType":"dailyVolume","category":cat},timeout=120)
    print(cat, r.status_code, len(r.text))
    if r.status_code==200:
        d=r.json()
        tdc=sorted([(int(x[0]),float(x[1] or 0)) for x in (d.get("totalDataChart") or [])])
        print("  pts",len(tdc),"last",tdc[-1] if tdc else None)
        json.dump(tdc,open(f"cat_{cat}_vol.json","w"))
        ps=[(p.get("displayName"),p.get("total30d")) for p in d.get("protocols",[]) if (p.get("total30d") or 0)>0]
        print("  top:", [(a,round(b/1e6,1)) for a,b in sorted(ps,key=lambda x:-x[1])[:8]])
