import requests, json, sys, datetime
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
# Polymarket gamma API
r=S.get("https://gamma-api.polymarket.com/markets",params={"closed":"false","limit":"500","order":"volume24hr","ascending":"false"},timeout=60)
print("status",r.status_code,len(r.text))
if r.status_code==200:
    ms=r.json()
    tot24=sum(float(m.get("volume24hr") or 0) for m in ms)
    totall=sum(float(m.get("volume") or 0) for m in ms)
    liq=sum(float(m.get("liquidity") or 0) for m in ms)
    print(f"top500 open markets: vol24h=${tot24/1e6:,.1f}M  cumVol=${totall/1e9:,.2f}B  liquidity=${liq/1e6:,.1f}M")
    print("\nTop 12 open markets by 24h volume:")
    for m in ms[:12]:
        print(f"  {str(m.get('question'))[:58]:<60} v24=${(float(m.get('volume24hr') or 0))/1e6:>7.2f}M  liq=${(float(m.get('liquidity') or 0))/1e6:>7.2f}M  end={m.get('endDate')}")
# Polymarket overall stats
for u in ["https://gamma-api.polymarket.com/events?closed=false&limit=1"]:
    pass
