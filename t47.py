import requests, json, sys, datetime, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
def iso(s): return datetime.datetime.fromtimestamp(int(s),datetime.timezone.utc).strftime("%Y-%m-%d")
ch=S.get("https://api.llama.fi/v2/chains",timeout=60).json()
tot=sum(c["tvl"] for c in ch)
print(f"TOTAL DeFi TVL across chains: ${tot/1e9:,.1f}B  ({len(ch)} chains)  as of ~{iso(datetime.datetime.now().timestamp())}")
top=sorted(ch,key=lambda c:-c["tvl"])[:22]
print(f"\n{'CHAIN':<26}{'TVL$B':>10}{'SHARE%':>9}")
for c in top:
    print(f"{c['name'][:24]:<26}{c['tvl']/1e9:>10,.2f}{100*c['tvl']/tot:>9.1f}")
# 30d chain tvl change for top chains
h=S.get("https://api.llama.fi/v2/historicalChainTvl",timeout=60).json()
print("\nAGGREGATE chain TVL series pts:",len(h))
if h:
    rows=sorted([(int(x["date"]),float(x["tvl"])) for x in h])
    last=rows[-1]
    def ago(n):
        t=last[0]-n*86400; c=[r for r in rows if r[0]<=t]; return c[-1]
    print("  now  ", iso(last[0]), f"${last[1]/1e9:,.1f}B")
    for n in (7,30,90,365):
        a=ago(n); print(f"  {n:>3}d  ", iso(a[0]), f"${a[1]/1e9:,.1f}B  chg={round((last[1]/a[1]-1)*100,2)}%")
