import requests, json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
p=S.get("https://api.llama.fi/protocols",timeout=120).json()
print("protocols:",len(p))
print("SAMPLE KEYS:", list(p[0].keys()))
cats=sorted(set(x.get("Category") or "?" for x in p))
print("\nCATEGORIES (%d):"%len(cats)); print(cats)
json.dump(cats,open("cats.json","w"))
