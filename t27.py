import requests, json, sys, collections, datetime
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
def series(url):
    d=S.get(url,timeout=180).json()
    return d
def dsec(ts): return datetime.datetime.fromtimestamp(int(ts),datetime.timezone.utc).strftime("%Y-%m-%d")

for label,url in [("FEES","https://api.llama.fi/overview/fees?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true&dataType=dailyFees"),
                  ("DEXVOL","https://api.llama.fi/overview/dexs?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true&dataType=dailyVolume")]:
    d=series(url)
    tdc=d.get("totalDataChart") or []
    pts=sorted([(int(x[0]),float(x[1] or 0)) for x in tdc])
    last=pts[-1][0]
    def win(days,end_off=0):
        hi=last-end_off*86400; lo=hi-days*86400
        return sum(v for t,v in pts if lo < t <= hi)
    c30=win(30); p30=win(30,30)
    print("="*70); print(label,"AGGREGATE (from totalDataChart daily series)"); print("="*70)
    print("last data point:", dsec(last), f"${pts[-1][1]:,.0f}")
    print(f"last 30d total : ${c30/1e6:,.1f}M")
    print(f"prior 30d total: ${p30/1e6:,.1f}M")
    print(f"30d-over-30d   : {round((c30/p30-1)*100,2) if p30 else 'n/a'}%")
    print(f"last 7d        : ${win(7)/1e6:,.1f}M   prior7d: ${win(7,7)/1e6:,.1f}M  chg={round((win(7)/win(7,7)-1)*100,2) if win(7,7) else 'n/a'}%")
    print(f"last 90d       : ${win(90)/1e6:,.1f}M")
    json.dump(pts,open(f"{label}_series.json","w"))
