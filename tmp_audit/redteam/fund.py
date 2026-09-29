import requests, json, datetime as dt
H={"User-Agent":"Mozilla/5.0"}
# LIVE funding check across Binance USD-M majors
u="https://fapi.binance.com/fapi/v1/premiumIndex"
r=requests.get(u, headers=H, timeout=30)
print("premiumIndex", r.status_code)
d=r.json()
maj=["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","ADAUSDT","DOGEUSDT","LINKUSDT","LTCUSDT","AVAXUSDT","TRXUSDT","BCHUSDT","UNIUSDT","NEARUSDT","APTUSDT","ARBUSDT","OPUSDT","SUIUSDT","INJUSDT","PEPEUSDT","AAVEUSDT","FILUSDT","ETCUSDT","ATOMUSDT"]
tot=0
for x in d:
    if x["symbol"] in maj:
        fr=float(x["lastFundingRate"]); tot+=fr
        print(f"{x['symbol']:10s} lastFunding={fr*100:+.4f}%  mark={x['markPrice']}  next={dt.datetime.utcfromtimestamp(x['nextFundingTime']/1000)}")
n=len(maj)
print(f"\nEW mean last funding rate = {tot/n*100:+.4f}% per 8h -> {tot/n*3*365*100:+.2f}%/yr (annualised, 8h grid)")
