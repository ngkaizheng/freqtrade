import requests, json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"})
d=S.get("https://l2beat.com/api/scaling/summary",timeout=60).json()
proj=d["projects"]
print("type:",type(proj),"n:",len(proj))
if isinstance(proj,dict):
    k=list(proj)[:3]; print("keys sample:",k)
    import itertools
    first=proj[k[0]]
    print("entry type",type(first))
    if isinstance(first,dict): print("entry keys:",list(first.keys()))
# chart key
ch=d.get("chart")
print("chart type:",type(ch), (list(ch)[:10] if isinstance(ch,dict) else str(ch)[:300]))
