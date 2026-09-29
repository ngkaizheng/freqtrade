import requests, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
urls=["https://api.llama.fi/v1/rwa/","https://api.llama.fi/protocols/rwa","https://api.llama.fi/rwa",
 "https://api.l2beat.com/v1/scaling/summary","https://l2beat.com/api/scaling/summary",
 "https://gamma-api.polymarket.com/markets?closed=false&limit=1",
 "https://api.llama.fi/overview/options?excludeTotalDataChart=true",
 "https://api.llama.fi/v2/historicalChainTvl/Ethereum",
 "https://api.llama.fi/chain/Arbitrum",
 "https://api.llama.fi/overview/dexs?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true&dataType=dailyVolume&category=Derivatives",
]
for u in urls:
    try:
        r=S.get(u,timeout=60); print(f"{r.status_code} len={len(r.text):>8}  {u[:105]}")
    except Exception as e: print("ERR",u[:95],repr(e)[:80])
