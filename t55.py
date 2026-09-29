import requests, json, sys, datetime
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
now=datetime.datetime.now(datetime.timezone.utc)
print("NOW_UTC:",now.isoformat())
print("\n--- SPOT, multi-venue cross-check ---")
for name,u in [("Coinbase ETH-USD","https://api.coinbase.com/v2/prices/ETH-USD/spot"),
               ("Coinbase BTC-USD","https://api.coinbase.com/v2/prices/BTC-USD/spot"),
               ("Coinbase SOL-USD","https://api.coinbase.com/v2/prices/SOL-USD/spot")]:
    try: print(f"  {name:<20}", S.get(u,timeout=25).json()["data"]["amount"])
    except Exception as e: print(" ",name,"ERR",repr(e)[:60])
for sym in ["BTCUSDT","ETHUSDT","SOLUSDT"]:
    d=S.get("https://api.binance.com/api/v3/ticker/24hr",params={"symbol":sym},timeout=25).json()
    print(f"  Binance {sym:<9} last={float(d['lastPrice']):,.2f}  24h={float(d['priceChangePercent']):+.2f}%")
d=S.get("https://api.binance.com/api/v3/ticker/bookTicker",params={"symbol":"ETHUSDT"},timeout=25).json()
print("  Binance ETHUSDT bookTicker bid/ask:",d["bidPrice"],d["askPrice"])
# DefiLlama price cross-check
r=S.get("https://coins.llama.fi/prices/current/coingecko:ethereum,coingecko:bitcoin",timeout=30)
print("\n  DefiLlama/CoinGecko:",r.text)
