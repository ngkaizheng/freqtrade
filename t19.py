import requests, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 research/1.0"})
urls=[
 ("BIN_OI_CUR","https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT"),
 ("BIN_OI_HIST","https://fapi.binance.com/futures/data/openInterestHist?symbol=BTCUSDT&period=1d&limit=35"),
 ("BIN_FUND","https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&limit=10"),
 ("BIN_FUND_ETH","https://fapi.binance.com/fapi/v1/fundingRate?symbol=ETHUSDT&limit=10"),
 ("BIN_PREMIUM","https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT"),
 ("OKX_FUND","https://www.okx.com/api/v5/public/funding-rate-history?instId=BTC-USDT-SWAP&limit=5"),
 ("OKX_OI","https://www.okx.com/api/v5/public/open-interest?instType=SWAP&instId=BTC-USDT-SWAP"),
 ("BYBIT_TICKER","https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT"),
]
for n,u in urls:
    try:
        r=S.get(u,timeout=45); print(f"### {n} {r.status_code} {r.text[:260]}")
    except Exception as e: print("###",n,"ERR",e)
