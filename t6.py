import requests, json
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
for u in ["https://api.coingecko.com/api/v3/global/market_cap_chart",
          "https://stablecoins.llama.fi/stablecoincharts/all",
          "https://stablecoins.llama.fi/stablecoins?includePrices=true",
          "https://api.llama.fi/overview/dexs",
          "https://api.llama.fi/overview/fees",
          "https://api.llama.fi/overview/derivatives",
          "https://api.llama.fi/overview/options"]:
    try:
        r=S.get(u,timeout=60); print(u,"->",r.status_code,len(r.text))
    except Exception as e: print(u,"-> ERR",e)
