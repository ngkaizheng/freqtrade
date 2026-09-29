import requests, json, sys, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
p=S.get("https://api.llama.fi/protocols",timeout=120).json()
cats=collections.Counter(x.get("category") or "UNCATEGORIZED" for x in p)
print("CATEGORIES (%d):"%len(cats))
for c,n in sorted(cats.items()): print(f"  {c}: {n}")
json.dump(p,open("protocols.json","w"))
