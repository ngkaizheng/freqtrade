import requests, json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"})
d=S.get("https://l2beat.com/api/scaling/summary",timeout=60).json()
p=d["projects"]
k0=list(p)[0]
print("SAMPLE tvs obj:",json.dumps(p[k0].get("tvs"))[:400])
def num(x):
    if isinstance(x,dict):
        for kk in ("tvs","current","value","usd","amount"):
            if kk in x and isinstance(x[kk],(int,float)): return x[kk]
        if x: return num(list(x.values())[0])
        return 0
    return x or 0
rows=[(v.get("name"), v.get("stage"), num(v.get("tvs")), v.get("type"), (v.get("category") or "")) for v in p.values()]
rows.sort(key=lambda x:-float(x[2] or 0))
print(f"\n{'PROJECT':<22}{'STAGE':<8}{'TVS(30d) USD':>18}  {'TYPE':<10}CATEGORY")
for n,st,tvs,ty,cat in rows[:20]:
    print(f"{str(n)[:20]:<22}{str(st):<8}{float(tvs or 0):>18,.0f}  {str(ty):<10}{str(cat)[:22]}")
tot=sum(float(r[2] or 0) for r in rows)
print(f"\nTOTAL TVS across {len(rows)} projects: ${tot/1e9:,.1f}B")
