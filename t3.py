import requests, json, datetime, time
S = requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
def g(u, params=None, tries=6):
    r=None
    for i in range(tries):
        try:
            r = S.get(u, params=params, timeout=45)
            if r.status_code==200: return r.json()
            time.sleep(4+i*3)
        except Exception as e:
            time.sleep(4)
    return {"__error__": getattr(r,"status_code","fail")}

d = g("https://api.coingecko.com/api/v3/global")
print(json.dumps(d,indent=1)[:2500])
