import requests, json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"})
d=S.get("https://l2beat.com/api/scaling/summary",timeout=60).json()
p=d["projects"]
print(f"{'PROJECT':<22}{'STAGE':<8}{'TVS(30d,USD)':>18}{'TYPE':<10}{'CATEGORY'}")
rows=[]
for k,v in p.items():
    st=v.get("stage") or ""
    tvs=v.get("tvs")
    if tvs is None: tvs=0
    rows.append((v.get("name"), st, tvs, v.get("type"), (v.get("category") or "")))
rows.sort(key=lambda x:-(x[2] or 0))
for n,st,tvs,ty,cat in rows[:20]:
    print(f"{str(n)[:20]:<22}{str(st):<8}{(tvs or 0):>18,}{str(ty):<10}{str(cat)[:20]}")
ch=d.get("chart") or {}
print("\nsyncedUntil:", ch.get("syncedUntil"))
print("types:", json.dumps(ch.get("types"))[:500])
data=ch.get("data")
print("data keys:", list(data)[:12] if isinstance(data,dict) else type(data))
