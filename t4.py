import requests, json, datetime, time
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
r=S.get("https://api.binance.com/api/v3/klines",params={"symbol":"BTCUSDT","interval":"1d","limit":5},timeout=30)
print("binance",r.status_code, r.text[:300])
r2=S.get("https://api.coinbase.com/v2/prices/BTC-USD/spot",timeout=30)
print("coinbase",r2.status_code, r2.text[:200])
