import requests, json, datetime
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
def klines(sym, limit=1000, start=None):
    p={"symbol":sym,"interval":"1d","limit":limit}
    if start: p["startTime"]=start
    r=S.get("https://api.binance.com/api/v3/klines",params=p,timeout=45)
    r.raise_for_status(); return r.json()

# paginate full history
def full(sym):
    rows=[]; start=None
    for i in range(12):
        k=klines(sym,1000,start)
        if not k: break
        rows+=k
        start=k[-1][0]+86400000
        if len(k)<1000: break
        time.sleep(0.4)
    return rows

import time
res={}
for sym in ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT"]:
    rows=full(sym)
    # dedupe by open time
    seen={}
    for r in rows: seen[r[0]]=r
    ks=sorted(seen.values(), key=lambda x:x[0])
    ath=max(ks,key=lambda x:float(x[2]))
    last=ks[-1]
    def px_ago(days):
        t=last[0]-days*86400000
        c=[k for k in ks if k[0]<=t]
        return c[-1]
    def iso(ms): return datetime.datetime.fromtimestamp(ms/1000,datetime.timezone.utc).strftime("%Y-%m-%d")
    a={}
    for d in (7,30,90):
        k=px_ago(d)
        a[f"chg_{d}d_pct"]=round((float(last[4])/float(k[4])-1)*100,2)
        a[f"px_{d}d_ago"]=round(float(k[4]),2); a[f"date_{d}d_ago"]=iso(k[0])
    a.update({
      "last_close":round(float(last[4]),2),"last_date":iso(last[0]),
      "ath_high":round(float(ath[2]),2),"ath_date":iso(ath[0]),
      "pct_from_ath":round((float(last[4])/float(ath[2])-1)*100,2),
      "chg_365d_pct": round((float(last[4])/float(px_ago(365)[4])-1)*100,2),
      "px_365d_ago": round(float(px_ago(365)[4]),2),
    })
    res[sym]=a
    print(sym, json.dumps(a))
    time.sleep(0.6)

# ratios
def ratio(nu,de):
    n=res[nu]; d=res[de]
    r={"now":round(n["last_close"]/d["last_close"],5)}
    for x in (7,30,90):
        r[f"{x}d_ago"]=round(n[f"px_{x}d_ago"]/d[f"px_{x}d_ago"],5)
        r[f"chg_{x}d_pct"]=round((r["now"]/r[f"{x}d_ago"]-1)*100,2)
    return r
res["ETHBTC"]=ratio("ETHUSDT","BTCUSDT")
res["SOLBTC"]=ratio("SOLUSDT","BTCUSDT")
res["BNBBTC"]=ratio("BNBUSDT","BTCUSDT")
print("ETHBTC",json.dumps(res["ETHBTC"]))
print("SOLBTC",json.dumps(res["SOLBTC"]))
print("BNBBTC",json.dumps(res["BNBBTC"]))
json.dump(res,open("prices.json","w"),indent=1)
