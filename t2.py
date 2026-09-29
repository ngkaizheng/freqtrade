import requests, json, datetime, time
S = requests.Session()
S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
def g(u, params=None, tries=5):
    for i in range(tries):
        try:
            r = S.get(u, params=params, timeout=45)
            if r.status_code == 200:
                return r.json()
            time.sleep(3+i*3)
        except Exception as e:
            time.sleep(3)
    return {"__error__": r.status_code if 'r' in dir() else "fail"}

out={}
# market_chart gives full history -> ATH + 7d/30d/90d ago prices
for pid in ["bitcoin","ethereum","solana"]:
    d = g(f"https://api.coingecko.com/api/v3/coins/{pid}/market_chart",
          {"vs_currency":"usd","days":"max","interval":"daily"})
    if "__error__" in d:
        print(pid,"ERR",d); continue
    pr = d["prices"]
    ath = max(pr, key=lambda x:x[1])
    last = pr[-1]
    def ago(days):
        target = last[0] - days*86400
        # nearest point at or before target
        cands=[p for p in pr if p[0] <= target]
        return cands[-1] if cands else None
    a7,a30,a90 = ago(7),ago(30),ago(90)
    out[pid]={
      "last_usd": round(last[1],2), "last_ts": datetime.datetime.fromtimestamp(last[0]/1000,datetime.timezone.utc).isoformat(),
      "ath_usd": round(ath[1],2), "ath_date": datetime.datetime.fromtimestamp(ath[0]/1000,datetime.timezone.utc).isoformat(),
      "pct_from_ath": round((last[1]/ath[1]-1)*100,2),
      "chg_7d_pct": round((last[1]/a7[1]-1)*100,2), "px_7d_ago": round(a7[1],2), "d7_ts": datetime.datetime.fromtimestamp(a7[0]/1000,datetime.timezone.utc).isoformat(),
      "chg_30d_pct": round((last[1]/a30[1]-1)*100,2), "px_30d_ago": round(a30[1],2), "d30_ts": datetime.datetime.fromtimestamp(a30[0]/1000,datetime.timezone.utc).isoformat(),
      "chg_90d_pct": round((last[1]/a90[1]-1)*100,2), "px_90d_ago": round(a90[1],2), "d90_ts": datetime.datetime.fromtimestamp(a90[0]/1000,datetime.timezone.utc).isoformat(),
    }
    print(pid, json.dumps(out[pid],indent=1))
    time.sleep(3)
json.dump(out, open("regime_raw.json","w"), indent=1)
