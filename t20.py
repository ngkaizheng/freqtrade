import requests, json, datetime, time, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
def iso(ms): return datetime.datetime.fromtimestamp(ms/1000,datetime.timezone.utc).strftime("%Y-%m-%d")
out={}
print("="*30,"BINANCE PERP OI (BTC/ETH/SOL)","="*30)
for sym in ["BTCUSDT","ETHUSDT","SOLUSDT"]:
    r=S.get("https://fapi.binance.com/futures/data/openInterestHist",params={"symbol":sym,"period":"1d","limit":32},timeout=45).json()
    rows=[{"ts":x["timestamp"],"oi_contracts":float(x["sumOpenInterest"]),"oi_usd":float(x["sumOpenInterestValue"])} for x in r]
    rows.sort(key=lambda z:z["ts"])
    last=rows[-1]
    o={"now_usd":round(last["oi_usd"]/1e9,3),"now_contracts":round(last["oi_contracts"],0),"now_date":iso(last["ts"])}
    for d in (7,30):
        cand=[x for x in rows if x["ts"]<=last["ts"]-d*86400000]
        if cand:
            a=cand[-1]
            o[f"chg_{d}d_pct"]=round((last["oi_usd"]/a["oi_usd"]-1)*100,2)
            o[f"oi_{d}d_ago_usd_B"]=round(a["oi_usd"]/1e9,3); o[f"date_{d}d_ago"]=iso(a["ts"])
    # also first vs last for full 31d
    o["first_date"]=iso(rows[0]["ts"]); o["first_usd_B"]=round(rows[0]["oi_usd"]/1e9,3)
    out[sym]=o; print(sym, json.dumps(o))
    time.sleep(0.5)

print("="*30,"BINANCE FUNDING (last 30 prints)","="*30)
for sym in ["BTCUSDT","ETHUSDT","SOLUSDT"]:
    r=S.get("https://fapi.binance.com/fapi/v1/fundingRate",params={"symbol":sym,"limit":30},timeout=45).json()
    rates=[float(x["fundingRate"]) for x in r]
    last3=rates[-3:]; 
    o={"last_rate_8h":round(rates[-1],7),
       "last_8h_annualized_pct":round(rates[-1]*3*365*100,2),
       "avg_last_3_8h_ann_pct":round(sum(last3)/3*3*365*100,2),
       "avg_last_9_8h_ann_pct":round(sum(rates[-9:])/9*3*365*100,2),
       "avg_last_30_8h_ann_pct":round(sum(rates)/len(rates)*3*365*100,2),
       "neg_count_last_30":sum(1 for x in rates if x<0),
       "last_print_ts":iso(r[-1]["fundingTime"])}
    out[sym+"_funding"]=o; print(sym, json.dumps(o))
    time.sleep(0.4)

print("="*30,"OKX OI now (BTC/ETH/SOL/XRP)","="*30)
for c in ["BTC","ETH","SOL","XRP"]:
    d=S.get("https://www.okx.com/api/v5/public/open-interest",params={"instType":"SWAP","instId":f"{c}-USDT-SWAP"},timeout=45).json()
    v=d["data"][0]; print("OKX",c, round(float(v["oiUsd"])/1e9,3),"B usd", "@", iso(int(v["ts"])))
    out[f"okx_{c}_oi_usd_B"]=round(float(v["oiUsd"])/1e9,3)
    time.sleep(0.4)

print("="*30,"BYBIT BTC OI now","="*30)
d=S.get("https://api.bybit.com/v5/market/tickers",params={"category":"linear","symbol":"BTCUSDT"},timeout=45).json()
t=d["result"]["list"][0]
print("Bybit BTC openInterest:", t.get("openInterest"), "oiValue:", t.get("openInterestValue"), "@", iso(int(t.get("time"))))
out["bybit_btc_oi_value_usd"]=t.get("openInterestValue")
json.dump(out,open("derivs.json","w"),indent=1)
