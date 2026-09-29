import requests, json, sys, time, statistics, datetime
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
mk=None
for i in range(10):
    r=S.get("https://api.coingecko.com/api/v3/coins/markets",params={
        "vs_currency":"usd","order":"market_cap_desc","per_page":"250","page":"1",
        "price_change_percentage":"7d,30d,1y"},timeout=90)
    if r.status_code==200: mk=r.json(); break
    time.sleep(22)
if not mk: print("FAILED"); raise SystemExit
print("updated_at(last):", mk[0].get("last_updated"), " n:",len(mk))
for label,key in [("7D","price_change_percentage_7d_in_currency"),("30D","price_change_percentage_30d_in_currency"),("1Y","price_change_percentage_1y_in_currency")]:
    vals=[c[key] for c in mk if c.get(key) is not None]
    pos=sum(1 for v in vals if v>0)
    print(f"TOP{len(vals)} {label}: positive={pos} ({round(100*pos/len(vals),1)}%)  median={round(statistics.median(vals),2)}%  mean={round(statistics.mean(vals),2)}%")
print("\nTop-200 subset:")
for label,key in [("7D","price_change_percentage_7d_in_currency"),("30D","price_change_percentage_30d_in_currency")]:
    vals=[c[key] for c in mk[:200] if c.get(key) is not None]
    pos=sum(1 for v in vals if v>0)
    print(f"  TOP200 {label}: positive={pos} ({round(100*pos/len(vals),1)}%)  median={round(statistics.median(vals),2)}%")
json.dump(mk,open("mk250.json","w"))
