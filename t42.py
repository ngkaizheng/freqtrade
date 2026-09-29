import json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
d=json.load(open("cg_cats.json"))
for c in d:
    if any(k in c["name"].lower() for k in ["rwa","tokenized","real world","gold","treasur"]):
        print(f'{c["id"]:<42} | {c["name"]:<40} mcap=${(c.get("market_cap") or 0)/1e9:>8,.2f}B 24h={(c.get("market_cap_change_24h") or 0):+8.2f}% vol24h=${(c.get("volume_24h") or 0)/1e6:>8,.0f}M')
