import requests, json, sys, datetime
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0","Content-Type":"application/json"})
now=int(datetime.datetime.now(datetime.timezone.utc).timestamp()*1000)
coins=["BTC","ETH","SOL","HYPE","ZEC","XRP","PUMP","NEAR","DOGE","LINK","AAVE","UNI","ENA","ONDO","SUI","AVAX"]
tot={}
for c in coins:
    try:
        d=S.post("https://api.hyperliquid.xyz/info",json={"type":"candleSnapshot","req":{"coin":c,"interval":"1d","startTime":now-100*86400000,"endTime":now}},timeout=45).json()
        rows=sorted([(x["t"], float(x["v"])*float(x["c"]), float(x["c"])) for x in d])
        if not rows: continue
        last=rows[-1][0]
        def w(off,days):
            hi=last-off*86400000; lo=hi-days*86400000
            return sum(v for t,v,_ in rows if lo<t<=hi)
        c30=w(0,30); p30=w(30,30); c7=w(0,7); p7=w(7,7)
        tot[c]={"c30_B":round(c30/1e9,3),"p30_B":round(p30/1e9,3),"chg30_pct":round((c30/p30-1)*100,1) if p30 else None,
                "c7_B":round(c7/1e9,3),"p7_B":round(p7/1e9,3),"chg7_pct":round((c7/p7-1)*100,1) if p7 else None}
        print(f"{c:<6} 30d=${c30/1e9:>7.3f}B prior30d=${p30/1e9:>7.3f}B  30dchg={tot[c]['chg30_pct']:>7}%  7dchg={tot[c]['chg7_pct']:>7}%")
    except Exception as e: print(c,"ERR",repr(e)[:100])
A=lambda k: sum(tot[x][k] for x in tot)
print("\n--- SUM of these 16 HL perps ---")
print(f"30d total = ${A('c30_B'):.3f}B   prior30d = ${A('p30_B'):.3f}B   chg = {round((A('c30_B')/A('p30_B')-1)*100,1)}%")
print(f"7d  total = ${A('c7_B'):.3f}B   prior7d  = ${A('p7_B'):.3f}B   chg = {round((A('c7_B')/A('p7_B')-1)*100,1)}%")
json.dump(tot,open("hl_hist.json","w"),indent=1)
