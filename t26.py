import requests, json, sys, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
res={}
for label,url in [("FEES","https://api.llama.fi/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true&dataType=dailyFees"),
                  ("REVDEX","https://api.llama.fi/overview/dexs?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true&dataType=dailyVolume")]:
    d=S.get(url,timeout=180).json()
    agg=collections.defaultdict(lambda:{"now":0.0,"ago":0.0,"n":0,"top":[]})
    for p in d.get("protocols",[]):
        c=p.get("category") or "UNCAT"
        now=p.get("total30d") or 0.0; ago=p.get("total30DaysAgo") or 0.0
        agg[c]["now"]+=now; agg[c]["ago"]+=ago; agg[c]["n"]+=1
        if now>0: agg[c]["top"].append((p.get("displayName") or p.get("name"), round(now/1e6,2), round((p.get("change_30dover30d") or 0),1)))
    res[label]={c:{"now_M":round(v["now"]/1e6,1),"ago_M":round(v["ago"]/1e6,1),
                   "chg_pct":round((v["now"]/v["ago"]-1)*100,1) if v["ago"]>0 else None,
                   "n":v["n"],"top":sorted(v["top"],key=lambda x:-x[1])[:8]} for c,v in agg.items()}
    print("="*100); print(label,"— 30d aggregate by category (USD M)"); print("="*100)
    for c,v in sorted(res[label].items(), key=lambda x:-(x[1]["now_M"]))[:28]:
        ch=f'{v["chg_pct"]:>8.1f}%' if v["chg_pct"] is not None else "     n/a"
        print(f'{c:<26} 30d=${v["now_M"]:>10,.0f}M  30dchg={ch}  n={v["n"]}')
json.dump(res,open("fees_vol.json","w"),indent=1)
