import requests, json, sys, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
f=S.get("https://api.llama.fi/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true&dataType=dailyFees",timeout=180).json()
d=S.get("https://api.llama.fi/overview/dexs?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true&dataType=dailyVolume",timeout=180).json()
def bycat(src):
    a=collections.defaultdict(list)
    for p in src.get("protocols",[]):
        if (p.get("total30d") or 0)>0:
            a[p.get("category") or "UNCAT"].append((p.get("displayName") or p.get("name"), p.get("total30d"), p.get("module"), p.get("slug")))
    return a
FF,DD=bycat(f),bycat(d)
NARR={"AI Agents":"AI Agents","Decentralized AI":"Decentralized AI","RWA":"RWA","DePIN":"DePIN",
 "Gaming":"Gaming","Payments":"Payments","Prediction Market":"Prediction Market",
 "Restaking":"Restaking","Liquid Restaking":"Liquid Restaking","Restaked BTC":"Restaked BTC",
 "Privacy":"Privacy","Derivatives":"Derivatives (perp DEX)","Dexs":"Spot DEX",
 "Stablecoin Issuer":"Stablecoin Issuer","Launchpad":"Launchpad","Trading App":"Trading App",
 "Crypto Card Issuer":"Crypto Card Issuer","CDP":"CDP / RWA lending","Lending":"Lending"}
for n,c in NARR.items():
    print("="*95); print(f"### {n}   [DefiLlama category: {c}]"); print("="*95)
    fl=sorted(FF.get(c,[]),key=lambda x:-x[1])[:6]
    dl=sorted(DD.get(c,[]),key=lambda x:-x[1])[:6]
    print("  FEES 30d:", ", ".join(f"{n2}=${v/1e6:.1f}M" for n2,v,_,_ in fl) or "—")
    print("  VOL  30d:", ", ".join(f"{n2}=${v/1e6:.1f}M" for n2,v,_,_ in dl) or "—")
    mods=[(m,s) for _,_,m,s in dl if m]+[(m,s) for _,_,m,s in fl if m]
    print("  slugs:", ", ".join(sorted(set(s for _,s in mods if s))[:12]))
