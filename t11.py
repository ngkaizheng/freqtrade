import requests, json, datetime, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
d=S.get("https://stablecoins.llama.fi/stablecoincharts/all",timeout=90).json()
print("TOP KEYS:", list(d[-1].keys()))
d.sort(key=lambda x:int(x["date"]))
last=d[-1]
def usd(x):
    tc=x.get("totalCirculatingUSD")
    if isinstance(tc,(int,float)): return tc
    return sum(v for k,v in x["totalCirculating"].items() if k in ("peggedUSD",))
def iso(ts): return datetime.datetime.fromtimestamp(int(ts),datetime.timezone.utc).strftime("%Y-%m-%d")
def ago(days, ref=None):
    t=int((ref or last["date"]))-days*86400
    c=[x for x in d if int(x["date"])<=t]; return c[-1]
out={"now_B":round(usd(last)/1e9,2),"now_date":iso(last["date"])}
for dd in (7,30,90,180,365):
    a=ago(dd)
    out[f"chg_{dd}d_pct"]=round((usd(last)/usd(a)-1)*100,2)
    out[f"px_{dd}d_ago_B"]=round(usd(a)/1e9,2); out[f"date_{dd}d_ago"]=iso(a["date"])
print(json.dumps(out,indent=1))
print("\n--- last 20 days stablecoin mcap (B USD) ---")
for x in d[-20:]: print(iso(x["date"]), round(usd(x)/1e9,2))
json.dump(out,open("stable.json","w"),indent=1)
