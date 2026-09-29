import requests, json, sys, datetime
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
# final derivatives snapshot
out={}
for sym in ["BTCUSDT","ETHUSDT","SOLUSDT"]:
    d=S.get("https://fapi.binance.com/fapi/v1/premiumIndex",params={"symbol":sym},timeout=30).json()
    fr=float(d["lastFundingRate"])
    out[sym]={"markPx":float(d["markPrice"]),"lastFundingRate":fr,"annPct":round(fr*3*365*100,2),
              "nextFunding":datetime.datetime.fromtimestamp(d["nextFundingTime"]/1000,datetime.timezone.utc).isoformat(),
              "asof":datetime.datetime.fromtimestamp(d["time"]/1000,datetime.timezone.utc).isoformat()}
    print(sym,out[sym])
# 30d funding summary
for sym in ["BTCUSDT","ETHUSDT","SOLUSDT"]:
    r=S.get("https://fapi.binance.com/fapi/v1/fundingRate",params={"symbol":sym,"limit":90},timeout=45).json()
    rates=[float(x["fundingRate"]) for x in r]
    neg=sum(1 for x in rates if x<0)
    last30=rates[-30:]; prev30=rates[-60:-30]
    print(f"{sym}: last30 prints mean_ann={round(sum(last30)/len(last30)*3*365*100,2)}%  prev30 mean_ann={round(sum(prev30)/len(prev30)*3*365*100,2)}%  neg_in_last90={neg}/90")
json.dump(out,open("funding_final.json","w"),indent=1)
