import requests, json, sys, time, datetime, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
h=json.load(open("top100_hist.json"))
def mcap_at(pts,t):
    c=[p for p in pts if p[0]<=t]; return c[-1][1] if c else None
ref=max(max(p[0] for p in v) for v in h.values())
print(f"consistent-basis BTC dominance over top-{len(h)} coins")
print(f"{'date':<12}{'sum mcap $T':>14}{'BTC mcap $T':>14}{'dominance %':>13}")
for d,label in [(0,'now'),(7,'t-7d'),(14,'t-14d'),(30,'t-30d'),(60,'t-60d'),(90,'t-90d')]:
    t=ref-d*86400000
    tot=btc=0.0
    for cid,pts in h.items():
        v=mcap_at(pts,t)
        if v:
            tot+=v
            if cid=="bitcoin": btc=v
    if btc:
        print(f"{datetime.datetime.fromtimestamp(t/1000,datetime.timezone.utc).strftime('%Y-%m-%d'):<12}{tot/1e12:>14.4f}{btc/1e12:>14.4f}{100*btc/tot:>13.2f}   ({label})")
