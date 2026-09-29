import requests, sys, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
for u in ["https://api.llama.fi/summary/fees/pump.fun",
          "https://api.llama.fi/summary/fees/pump-fun",
          "https://api.llama.fi/summary/fees/pump",
          "https://api.llama.fi/summary/dexs/pump.fun",
          "https://api.llama.fi/summary/fees/aave",
          "https://api.llama.fi/summary/fees/aave-v3",
          "https://api.llama.fi/overview/fees/pump.fun?excludeTotalDataChart=false&dataType=dailyFees",
          ]:
    r=S.get(u,timeout=60)
    n=len(r.json().get("totalDataChart") or []) if r.status_code==200 else 0
    print(f"{r.status_code} chart_pts={n:>5}  {u}")
