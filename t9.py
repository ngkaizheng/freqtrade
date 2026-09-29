import requests, json, datetime, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
d=S.get("https://stablecoins.llama.fi/stablecoincharts/all",timeout=90).json()
def iso(ts): return datetime.datetime.fromtimestamp(int(ts),datetime.timezone.utc).strftime("%Y-%m-%d")
print("SAMPLE ROW:", json.dumps(d[-1])[:600])
