import requests, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
urls=[
 "https://api.llama.fi/overview/dexs?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true&dataType=dailyVolume",
 "https://api.llama.fi/overview/fees?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true&dataType=dailyFees",
 "https://api.llama.fi/overview/derivatives?excludeTotalDataChart=false&dataType=dailyVolume",
 "https://api.llama.fi/v2/historicalChainTvl",
 "https://api.llama.fi/protocols",
 "https://api.llama.fi/v2/protocols",
 "https://api.llama.fi/aggregations",
 "https://api.llama.fi/overview/options?excludeTotalDataChart=false",
 "https://coins.llama.fi/prices/current/coingecko:bitcoin",
 "https://api.llama.fi/Tvl",
]
for u in urls:
    try:
        r=S.get(u,timeout=60); print(f"{r.status_code} len={len(r.text):>9}  {u[:110]}")
    except Exception as e: print("ERR",u[:90],e)
