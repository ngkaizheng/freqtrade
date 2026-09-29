import requests, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
try:
    import pandas as pd
    S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) research"})
    dfs=pd.read_html("https://www.federalreserve.gov/monetarypolicy/fomcprojtabl20260916.htm")
    for i,df in enumerate(dfs):
        print("### TABLE",i,df.shape)
        print(df.to_string()[:2600]); print()
except Exception as e:
    print("ERR",repr(e)[:200])
