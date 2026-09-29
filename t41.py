import requests, json, sys, datetime
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
def ser(kind,slug):
    r=S.get(f"https://api.llama.fi/summary/{kind}/{slug}",timeout=60)
    if r.status_code!=200: return None
    return sorted([(int(x[0]),float(x[1] or 0)) for x in (r.json().get("totalDataChart") or [])])
def win(pts,off,days):   # timestamps in SECONDS
    last=pts[-1][0]; hi=last-off*86400; lo=hi-days*86400
    return sum(v for t,v in pts if lo<t<=hi)
def iso(s): return datetime.datetime.fromtimestamp(s,datetime.timezone.utc).strftime("%Y-%m-%d")
GROUPS={
 "RWA":["ondo-global-markets","ondo-yield-assets","centrifuge-protocol","spiko","grayscale","blackrock-buidl","wisdomtree"],
 "PredictionMarket":["polymarket-us","polymarket-international","kalshi","predict-fun","opinion","limitless-exchange","predictstreet"],
 "HyperliquidSpot":["hyperliquid-spot-orderbook","lighter-spot","edgex-spot"],
 "AIAgents":["virtuals-protocol","termix","aeon","morpheusai","zyfai","chutes","flock.io"],
 "Restaking":["eigencloud","b14g","solayer-restaking","kelp","renzo","lombard-lbtc","bedrock-unieth"],
 "Gaming":["axie-infinity","illuvium","pixie-chess","topstrike","kintara","bloom-trading-bot"],
 "Payments":["sablier-lockup","streamflow","superfluid","llamapay","unlock-protocol","p2p.me","helio"],
 "Privacy":["tornado-cash","railgun","privacy-cash","zerc20","privacy-pools","hopr"],
 "MemeLaunchpad":["pump.fun","pons-v2","stonkfun","flap-sh","launchlab","meteora-dynamic-bonding-curve","bonk.fun-launchpad"],
 "CreditLending":["aave-v3","morpho-blue","world-liberty-financial","maple","sparklend","etherfi-cash-liquid"],
 "DePIN":["render-network-bme","hivemapper","nodeops","auki","prism"],
}
out={}
for g,slugs in GROUPS.items():
    print("="*112); print("###",g); print("="*112)
    for sl in slugs:
        any_=False
        for kind,label in [("fees","FEES"),("dexs","VOL ")]:
            pts=ser(kind,sl)
            if not pts or len(pts)<20: continue
            c30=win(pts,0,30); p30=win(pts,30,30); c7=win(pts,0,7); p7=win(pts,7,7)
            if c30<=0 and p30<=0: continue
            k=f"{g}|{sl}|{label.strip()}"
            out[k]={"first_date":iso(pts[0][0]),"last_date":iso(pts[-1][0]),"n_days":len(pts),
                    "c30_M":round(c30/1e6,2),"p30_M":round(p30/1e6,2),
                    "chg30_pct":round((c30/p30-1)*100,1) if p30>0 else None,
                    "c7_M":round(c7/1e6,2),"chg7_pct":round((c7/p7-1)*100,1) if p7>0 else None}
            cs=f"{out[k]['chg30_pct']:>9}%" if p30>0 else "      n/a"
            s7=f"{out[k]['chg7_pct']:>8}%" if p7>0 else "     n/a"
            print(f"  {sl:<29} {label} 30d=${c30/1e6:>10,.1f}M prior=${p30/1e6:>10,.1f}M chg30={cs} 7d=${c7/1e6:>9,.1f}M chg7={s7}  [hist from {iso(pts[0][0])}]")
            any_=True
        if not any_: print(f"  {sl:<29} (no series)")
json.dump(out,open("narratives.json","w"),indent=1)
print("SAVED",len(out))
