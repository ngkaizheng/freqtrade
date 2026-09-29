import requests, json, sys, datetime
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
d=S.get("https://api.llama.fi/summary/fees/pump.fun",timeout=60).json()
print("keys:",list(d.keys()))
tdc=d.get("totalDataChart")
print("n:",len(tdc))
print("first 3:",json.dumps(tdc[:3]))
print("last 5:",json.dumps(tdc[-5:]))
def iso(ts): return datetime.datetime.fromtimestamp(int(ts),datetime.timezone.utc).strftime("%Y-%m-%d")
print("first ts",iso(tdc[0][0]),"last ts",iso(tdc[-1][0]))
import collections
# gaps
ts=[int(x[0]) for x in tdc]
gaps=collections.Counter((ts[i+1]-ts[i])//86400 for i in range(len(ts)-1))
print("day-gap histogram:",gaps.most_common(6))
