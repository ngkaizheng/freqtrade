import requests, json, sys, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
proto=json.load(open("protocols.json"))
bycat=collections.defaultdict(list)
for p in proto:
    if p.get("category"): bycat[p["category"]].append(p)

TARGET=["AI Agents","Decentralized AI","RWA","DePIN","Gaming","Payments","Prediction Market",
        "Restaking","Liquid Restaking","Restaked BTC","Privacy","Derivatives","Dexs","Lending",
        "Stablecoin Issuer","CDP","Yield","Services","CEX","Chain","Algo-Stables","Launchpad","Meme"]
print("="*95)
print("TVL BY CATEGORY (DefiLlama /protocols, tvl + change_7d)")
print("="*95)
rows=[]
for c in TARGET:
    ps=bycat.get(c,[])
    tvl=sum(p.get("tvl") or 0 for p in ps)
    rows.append((c,len(ps),tvl))
for c,n,t in sorted(rows,key=lambda x:-x[2]):
    print(f"{c:<24} n={n:<5} TVL=${t/1e9:>10.3f}B")
json.dump({c:{"n":n,"tvl":t} for c,n,t in rows},open("cat_tvl.json","w"),indent=1)
