import requests, json, sys, time, datetime
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
CAT={
"L1 (Layer 1)":["SOL","BNB","AVAX","DOT","ADA","NEAR","SUI","APT","TRX","TON","HBAR","ICP","ALGO","EGLD","ATOM","XLM"],
"L2 (Layer 2)":["ARB","OP","STRK","MNT","ZK","ZRO","IMX","MANTA","METIS","TAIKO","BRETT","LDO"],
"DeFi":["ENA","PENDLE","UNI","AAVE","LDO","MKR","SKY","CRV","CVX","GMX","JUP","CAKE","MORPHO","SUSDS","EIGEN"],
"Meme":["DOGE","SHIB","PEPE","WIF","BONK","FLOKI","TRUMP","BRETT","POPCAT","MOG","SPX","TURBO","BOME","NEIRO"],
"AI":["FET","RENDER","TAO","VIRTUAL","WLD","AI16Z","PHYS","ARKM","TAO","SNT","AKT","IO","GRID"],
"RWA":["ONDO","CFG","PENDLE","MPL","SYRUP","PLUME","PROPS","TRUMP","XAUT","PAXG"],
"Gaming":["IMX","GALA","SAND","AXS","ENJ","BEAM","MAGIC","PIXEL","YGG","BIGTIME","SAG"],
"DePIN":["RENDER","HNT","MOBILE","IOT","ACC","LPT","STORJ","NKN","THETA","SC"],
"Restaking":["EIGEN","OM","KERNEL","SWELL","LVL","BNT","AVS"],
"Privacy":["ZEC","XMR","SCRT","DASH","ZEN","KEEP","SENS"],
"Payments":["XLM","HBAR","ALGO","ICP","IOTA","XRP","LTC","BCH","DOGE"],
"PredictionMkt":["PUMP","FOMO","JUP","PNUT","WIF"],
}
def kline(sym,limit=100):
    for i in range(4):
        r=S.get("https://api.binance.com/api/v3/klines",params={"symbol":sym+"USDT","interval":"1d","limit":limit},timeout=30)
        if r.status_code==200: return r.json()
        time.sleep(2)
    return None
print(f"{'CATEGORY':<18}{'TOKEN':<10}{'PRICE':>11}{'7D%':>9}{'30D%':>9}{'90D%':>9}{'FROM_ATH%':>11}")
res={}
for cat,syms in CAT.items():
    agg={"n":0,"m7":[],"m30":[],"m90":[]}
    for s in syms:
        k=kline(s)
        if not k: continue
        cl=[float(x[4]) for x in k]; hi=[float(x[2]) for x in k]
        last=cl[-1]
        c7=round((last/cl[-8]-1)*100,1) if len(cl)>8 else None
        c30=round((last/cl[-31]-1)*100,1) if len(cl)>31 else None
        c90=round((last/cl[-91]-1)*100,1) if len(cl)>91 else None
        ath=max(hi); fa=round((last/ath-1)*100,1)
        print(f"{cat:<18}{s:<10}{last:>11,.4f}{c7:>9}{c30:>9}{c90:>9}{fa:>11}")
        res[f"{cat}|{s}"]={"px":last,"chg7":c7,"chg30":c30,"chg90":c90,"from_ath":fa}
        for kk,vv in (("chg7",c7),("chg30",c30),("chg90",c90)):
            if vv is not None: agg["m"+kk[3:]].append(vv)
        agg["n"]+=1
    def med(x): 
        x=sorted(x); return round(x[len(x)//2],1) if x else None
    print(f"{'>> '+cat:<28} n={agg['n']:<3} MEDIAN 7d={med(agg['m7'])}%  30d={med(agg['m30'])}%  90d={med(agg['m90'])}%")
    print()
json.dump(res,open("cat_perf.json","w"),indent=1)
