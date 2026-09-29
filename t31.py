import requests, json, sys, datetime
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0","Content-Type":"application/json"})
try:
    r=S.post("https://api.hyperliquid.xyz/info",json={"type":"metaAndAssetCtxs"},timeout=45)
    d=r.json()
    meta,ctxs=d[0],d[1]
    tot=sum(float(c.get("dayNtlVlm") or 0) for c in ctxs)
    tot7=sum(float(c.get("prevDayPx") or 0)*0 for c in ctxs)
    print("Hyperliquid 24h PERP volume (all perps): $%.2fB"%(tot/1e9))
    top=sorted([(meta["universe"][i]["name"], float(ctxs[i].get("dayNtlVlm") or 0), float(ctxs[i].get("openInterest") or 0)*float(ctxs[i].get("markPx") or 0)) for i in range(len(ctxs))], key=lambda x:-x[1])[:10]
    print("top perps 24h vol / OI:")
    for n,v,oi in top: print(f"   {n:<10} vol24h=${v/1e6:>8.1f}M  OI=${oi/1e6:>8.1f}M")
    tot_oi=sum(float(c.get("openInterest") or 0)*float(c.get("markPx") or 0) for c in ctxs)
    print("Hyperliquid TOTAL perp OI: $%.2fB"%(tot_oi/1e9))
    json.dump({"vol24h":tot,"oi":tot_oi},open("hl.json","w"))
except Exception as e:
    print("HL ERR",repr(e)[:200])
# daily volume history via candles on BTC
try:
    now=int(datetime.datetime.now(datetime.timezone.utc).timestamp()*1000)
    r=S.post("https://api.hyperliquid.xyz/info",json={"type":"candleSnapshot","req":{"coin":"BTC","interval":"1d","startTime":now-95*86400000,"endTime":now}},timeout=45)
    c=r.json()
    print("\nBTC perp daily candles:",len(c))
    rows=sorted([(x["t"], float(x["v"]), float(x["c"])) for x in c])
    def w(off,days=30):
        hi=rows[-1][0]-off*86400000; lo=hi-days*86400000
        s=[r2 for r2 in rows if lo<r2[0]<=hi]
        return sum(r2[1] for r2 in s), len(s)
    v30,n30=w(0); vp30,_=w(30); v7,_=w(0,7); vp7,_=w(7,7)
    f=lambda t: datetime.datetime.fromtimestamp(t/1000,datetime.timezone.utc).strftime("%Y-%m-%d")
    print("  last candle:",f(rows[-1][0]), "close",rows[-1][2])
    print("  BTC perp vol last30d  = $%.2fB (n=%d)"%(v30/1e9,n30))
    print("  BTC perp vol prior30d = $%.2fB"% (vp30/1e9))
    print("  30d-over-30d = %.1f%%"%((v30/vp30-1)*100))
    print("  last7d=$%.2fB prior7d=$%.2fB chg=%.1f%%"%(v7/1e9,vp7/1e9,(v7/vp7-1)*100))
except Exception as e:
    print("HL candle ERR",repr(e)[:300])
