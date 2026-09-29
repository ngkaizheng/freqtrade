import requests, json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"})
r=S.get("https://l2beat.com/api/scaling/summary",timeout=60)
print("status",r.status_code,len(r.text))
d=r.json()
print("KEYS:",list(d.keys())[:20])
ch=d.get("charts") or []
print("charts:",len(ch))
# projects
proj=d.get("projects")
if proj:
    rows=[]
    for p in proj:
        st=p.get("stats") or {}
        rows.append((p.get("name"), st.get("tvs"), st.get("activity",{}).get("transactions"), st.get("risk"), p.get("hostedOn")))
    rows.sort(key=lambda x:-(x[1] or 0))
    print(f"\n{'PROJECT':<26}{'TVS (30d)':>16}{'STATE':<10}{'STAGE'}")
    for n,t,a,rk,ho in rows[:18]:
        print(f"{str(n)[:24]:<26}{(t or 0):>16,}{str(rk or ''):<10}{str(ho or '')[:18]}")
