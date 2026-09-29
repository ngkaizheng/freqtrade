import requests, time, sys, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
for u,p in [("https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",{"vs_currency":"usd","days":"90"}),
            ("https://api.coingecko.com/api/v3/coins/markets",{"vs_currency":"usd","order":"market_cap_desc","per_page":"5","page":"1"})]:
    for i in range(4):
        r=S.get(u,params=p,timeout=45)
        if r.status_code==200:
            print("OK",u.split("/")[-1],r.status_code,r.text[:200]); break
        print("  retry",r.status_code); time.sleep(10)
