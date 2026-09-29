import requests, json, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
r=S.get("https://api.coingecko.com/api/v3/coins/categories/real-world-assets-rwa",timeout=60)
print("status",r.status_code)
d=r.json()
print("KEYS:",list(d.keys()))
print("n coins:",len(d.get("coins") or []))
print(json.dumps((d.get("coins") or [])[:5],indent=1))
