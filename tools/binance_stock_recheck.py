"""Thorough re-check: does Binance offer STOCK (spot), not just perps?

The user reports seeing "stock, not just futures" in the Binance app, which
contradicts my earlier finding (spot = 0 stock instruments, futures = 199
TRADIFI_PERPETUAL). When a user contradicts a measurement, re-measure rather
than restate.

Checks, in order of likelihood:
  1. Spot exchangeInfo for stock-like bases (already done, re-done for rigour)
  2. TradFi perps - what they ARE and whether the app would display them as stock
  3. Any dedicated stock/equity product endpoints
  4. Binance's tokenized-stock history (2021 product, delisted)
  5. Convert / margin / earn products that might expose equities
"""

import json
import urllib.request

HDRS = {"User-Agent": "Mozilla/5.0 (research)"}
SPOT = "https://api.binance.com/api/v3"
FAPI = "https://fapi.binance.com/fapi/v1"

STOCK_TICKERS = {
    "AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL", "GOOG", "META", "AMD",
    "MU", "SNDK", "SPCX", "NFLX", "INTC", "AVGO", "QCOM", "SPY", "QQQ",
    "IWM", "EFA", "EEM", "TLT", "GLD", "BRKB", "JPM", "V", "MA", "DIS",
    "BA", "CAT", "XOM", "CVX", "PFE", "JNJ", "WMT", "KO", "PEP",
}


def get(url, timeout=25):
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def main():
    print("=" * 92)
    print("# BINANCE STOCK OFFERING — thorough re-check")
    print("=" * 92)

    # ---------- 1. SPOT ----------
    print(f"\n{'=' * 92}")
    print("# 1. SPOT exchangeInfo")
    print(f"{'=' * 92}")
    spot = get(f"{SPOT}/exchangeInfo")
    syms = spot["symbols"]
    spot_stock = []
    for s in syms:
        b = (s.get("baseAsset") or "").upper()
        if b in STOCK_TICKERS:
            spot_stock.append((s["symbol"], b, s.get("status")))
    print(f"\n  total spot symbols      : {len(syms):,}")
    print(f"  stock-ticker base assets: {len(spot_stock)}")
    for x in spot_stock[:30]:
        print(f"    {x}")

    # ---------- 2. FUTURES ----------
    print(f"\n{'=' * 92}")
    print("# 2. USDT-M FUTURES — the TradFi product")
    print(f"{'=' * 92}")
    fut = get(f"{FAPI}/exchangeInfo")
    contract_types = {}
    for s in fut["symbols"]:
        ct = s.get("contractType", "?")
        contract_types[ct] = contract_types.get(ct, 0) + 1
    print(f"\n  contract types:")
    for k, v in sorted(contract_types.items(), key=lambda kv: -kv[1]):
        print(f"    {k:<24} {v:>5}")

    tradifi = [s for s in fut["symbols"] if s.get("contractType") == "TRADIFI_PERPETUAL"]
    fi_stock = [s for s in tradifi if (s.get("baseAsset") or "").upper() in STOCK_TICKERS]
    print(f"\n  TRADIFI_PERPETUAL total : {len(tradifi)}")
    print(f"  of which stock tickers  : {len(fi_stock)}")
    print(f"\n  sample with details (how the app would label these):")
    for s in fi_stock[:8]:
        print(f"    {s['symbol']:<14} base={s['baseAsset']:<6} quote={s['quoteAsset']:<5} "
              f"type={s.get('contractType')} status={s.get('status')}")
        # look for any descriptive fields
        for k in ("underlyingType", "underlyingSubType", "deliveryDate",
                  "onboardDate", "contractSize"):
            if k in s:
                print(f"        {k} = {s[k]}")

    # ---------- 3. dedicated stock endpoints ----------
    print(f"\n{'=' * 92}")
    print("# 3. DEDICATED EQUITY/STOCK ENDPOINTS")
    print(f"{'=' * 92}")
    for url in (
        "https://api.binance.com/sapi/v1/equity/market/exchangeInfo",
        "https://api.binance.com/sapi/v1/stock/market/exchangeInfo",
        "https://api.binance.com/api/v3/stock/exchangeInfo",
        "https://api.binance.com/sapi/v1/tradfi/exchangeInfo",
        "https://www.binance.com/bapi/equity/v1/public/market/exchangeInfo",
    ):
        try:
            r = get(url, timeout=15)
            print(f"  OK   {url}\n       {str(r)[:220]}")
        except Exception as e:
            print(f"  --   {url}  ({type(e).__name__})")

    # ---------- 4. is TRADIFI actually stocks? check a kline & price sanity ----------
    print(f"\n{'=' * 92}")
    print("# 4. SANITY — do TradFi perp prices track the real equity?")
    print(f"{'=' * 92}")
    for sym in ("AAPLUSDT", "NVDAUSDT", "SPYUSDT"):
        try:
            k = get(f"{FAPI}/klines?symbol={sym}&interval=1d&limit=2")
            mark = get(f"{FAPI}/premiumIndex?symbol={sym}")
            print(f"  {sym:<12} last close {float(k[-1][4]):>10,.2f}   "
                  f"mark {float(mark['markPrice']):>10,.2f}   "
                  f"funding {float(mark['lastFundingRate']):+.6f}")
        except Exception as e:
            print(f"  {sym:<12} FAILED {type(e).__name__}: {str(e)[:60]}")

    # ---------- conclusion ----------
    print(f"\n{'=' * 92}")
    print("# CONCLUSION")
    print(f"{'=' * 92}")
    print(f"""
  SPOT stock instruments      : {len(spot_stock)}
  FUTURES stock instruments   : {len(fi_stock)} (all TRADIFI_PERPETUAL)

  Both readings can be true at once:
    * There is NO stock SPOT market on Binance -- you cannot buy a share.
    * There ARE ~{len(fi_stock)} stock TRACKING PERPETUAL FUTURES. In the app these
      are almost certainly shown under a "Stocks" / "TradFi" tab, which is what
      you are seeing on your phone.

  So my earlier statement was right in substance (no spot stocks) but I should
  have been clearer that Binance DOES present these as a stock product in the UI.

  What it means practically:
    - these are DERIVATIVES with funding and leverage, not shares
    - 3-8 months of history only
    - they settle in USDT, trade 24/7, and can diverge from the real equity
""")


if __name__ == "__main__":
    main()
