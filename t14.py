import requests, json, datetime, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
def yq(sym, rng="2y"):
    r=S.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
            params={"range":rng,"interval":"1d"},timeout=45); return r.json()["chart"]["result"][0]
def show(sym,label):
    d=yq(sym)
    ts=d["timestamp"]; cl=d["indicators"]["quote"][0]["close"]
    rows=[(t,c) for t,c in zip(ts,cl) if c is not None]
    last=rows[-1]
    def ago(n):
        t=last[0]-n*86400; c=[r for r in rows if r[0]<=t]; return c[-1]
    f=lambda ms: datetime.datetime.fromtimestamp(ms,datetime.timezone.utc).strftime("%Y-%m-%d")
    o={"last":round(last[1],4),"date":f(last[0])}
    for n in (7,30,90):
        a=ago(n); o[f"chg_{n}d_pct"]=round((last[1]/a[1]-1)*100,2); o[f"px_{n}d_ago"]=round(a[1],4); o[f"date_{n}d_ago"]=f(a[0])
    o["meta_regularMarketPrice"]=d["meta"].get("regularMarketPrice")
    print(label, json.dumps(o,indent=1))
show("%5ETNX","US10Y(^TNX, x10 => %)")
show("DX-Y.NYB","DXY")
show("%5EFV","2Y-not-used") if False else None
show("%5EIRX","13W-Bill(not 2y)") if False else None
