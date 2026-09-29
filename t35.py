import requests, json, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
r=None
for i in range(8):
    r=S.get("https://api.coingecko.com/api/v3/coins/categories",timeout=90)
    if r.status_code==200: break
    print("retry",r.status_code); time.sleep(14)
print("status",r.status_code,len(r.text))
if r.status_code==200:
    d=r.json()
    print("n categories:",len(d))
    print("SAMPLE:",json.dumps(d[0],indent=1)[:1200])
    json.dump(d,open("cg_cats.json","w"))
