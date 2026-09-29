import requests, json, sys, datetime
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0","Content-Type":"application/json"})
now=int(datetime.datetime.now(datetime.timezone.utc).timestamp()*1000)
r=S.post("https://api.hyperliquid.xyz/info",json={"type":"candleSnapshot","req":{"coin":"BTC","interval":"1d","startTime":now-40*86400000,"endTime":now}},timeout=45)
c=r.json()
print("SAMPLE CANDLE:", json.dumps(c[-1],indent=1))
print("SAMPLE CANDLE -1:", json.dumps(c[-2],indent=1))
