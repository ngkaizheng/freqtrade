import requests, json, datetime, time, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
u="https://api.coingecko.com/api/v3/global/market_cap_chart"
for i in range(8):
    r=S.get(u,params={"vs_currency":"usd","days":"90"},timeout=45)
    print("try",i,r.status_code,len(r.text))
    if r.status_code==200:
        d=r.json(); break
    time.sleep(12)
else:
    d=None
if d:
    pts=d["total_market_cap"]; btc=d.get("market_cap",{}).get("btc")
    print("SAMPLE",pts[-1], btc[-1] if btc else None)
    json.dump(d,open("mcap_chart.json","w"))
