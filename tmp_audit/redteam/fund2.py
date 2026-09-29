import requests, datetime as dt, statistics as st
H={"User-Agent":"Mozilla/5.0"}
maj=["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","ADAUSDT","DOGEUSDT","LINKUSDT","LTCUSDT",
     "AVAXUSDT","TRXUSDT","BCHUSDT","UNIUSDT","NEARUSDT","APTUSDT","ARBUSDT","OPUSDT","SUIUSDT",
     "INJUSDT","AAVEUSDT","FILUSDT","ETCUSDT","ATOMUSDT"]
panels={}
for s in maj:
    try:
        r=requests.get(f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={s}&limit=1000",headers=H,timeout=30)
        d=r.json()
        if not isinstance(d,list) or not d: continue
        panels[s]={int(x["fundingTime"]):float(x["fundingRate"]) for x in d}
    except Exception as e: print("ERR",s,e)
ts=sorted(set().union(*[set(v) for v in panels.values()]))
print("symbols:",len(panels),"common ts:",len(ts))
last=ts[-1]; print("newest:",dt.datetime.utcfromtimestamp(last/1000),"oldest:",dt.datetime.utcfromtimestamp(ts[0]/1000))
def ann(days):
    cut=last-days*86400000
    sel=[t for t in ts if t>=cut]
    rows=[(t,st.mean([p[t] for p in panels.values() if t in p])) for t in sel]
    rows=[(t,v) for t,v in rows if len([p for p in panels.values() if t in p])>=15]
    m=st.mean([v for _,v in rows])*3*365
    return len(rows), m*100
for d in [30,90,180,365,1000]:
    n,v=ann(d)
    print(f"trailing {d:4d}d  n={n:5d}  EW gross carry = {v:+6.2f}%/yr")
print()
print("--- by calendar year (EW) ---")
byyr={}
for t in ts:
    y=dt.datetime.utcfromtimestamp(t/1000).year
    vals=[p[t] for p in panels.values() if t in p]
    if len(vals)>=15: byyr.setdefault(y,[]).append(st.mean(vals))
for y in sorted(byyr): print(f"  {y}: {st.mean(byyr[y])*3*365*100:+.2f}%/yr  (n={len(byyr[y])})")
print()
med=st.median([p[t] for p in panels.values() for t in ts if t in p])
allv=[p[t] for p in panels.values() for t in ts if t in p]
print(f"pooled median funding = {med*100:+.4f}%  (Binance administered iota = +0.0100%)")
print(f"pooled mean   funding = {st.mean(allv)*100:+.4f}%  -> {st.mean(allv)*3*365*100:+.2f}%/yr")
print(f"share at exactly +0.0100% = {100*sum(1 for v in allv if abs(v-0.0001)<1e-9)/len(allv):.1f}%")
