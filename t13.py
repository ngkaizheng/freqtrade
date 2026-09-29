import requests, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
tests={
 "FRED_DGS10":"https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10",
 "STOOQ_DXY":"https://stooq.com/q/l/?s=dx.f&f=sd2t2ohlcv&h&e=csv",
 "STOOQ_US10Y":"https://stooq.com/q/l/?s=10usy.b&f=sd2t2ohlcv&h&e=csv",
 "YAHOO_DXY":"https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB?range=1mo&interval=1d",
 "YAHOO_TNX":"https://query1.finance.yahoo.com/v8/finance/chart/%5ETNX?range=1mo&interval=1d",
 "CME_FEDWATCH":"https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html",
}
for k,u in tests.items():
    try:
        r=S.get(u,timeout=45); print("###",k,r.status_code,len(r.text)); print(r.text[:400].replace("\n"," | ")); print()
    except Exception as e: print("###",k,"ERR",e)
