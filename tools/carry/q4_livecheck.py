"""Compare the repo's 8h funding series against Binance's live funding stream for 3 symbols."""
import io
import sys

import pandas as pd
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = r"E:\FreqTrader\freqtrade\user_data\data\binance_funding"

for sym in ("BTCUSDT", "LINKUSDT", "BNBUSDT"):
    d = pd.read_feather(ROOT + "\\" + sym.replace("USDT", "_USDT") + "-funding.feather")
    t = pd.to_datetime(d["fundingTime"], utc=True)
    repo = pd.Series(pd.to_numeric(d["fundingRate"]).to_numpy(),
                     index=pd.DatetimeIndex(t)).sort_index()
    gaps = repo.index.to_series().diff().dt.total_seconds().div(3600)
    print(f"\n=== {sym}  repo n={len(repo)}  span {repo.index[0]} .. {repo.index[-1]}")
    print(f"    repo gap value counts (hours): {gaps.value_counts().head(6).to_dict()}")
    print(f"    repo rows after 2025-05-02: {(repo.index >= pd.Timestamp('2025-05-02', tz='UTC')).sum()}")

    try:
        r = requests.get("https://fapi.binance.com/fapi/v1/fundingRate",
                         params={"symbol": sym, "limit": 1000},
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=40)
        j = r.json()
        live = pd.Series([float(x["fundingRate"]) for x in j],
                         index=pd.DatetimeIndex(
                             [pd.to_datetime(x["fundingTime"], unit="ms", utc=True) for x in j]))
        live = live.sort_index()
        lg = live.index.to_series().diff().dt.total_seconds().div(3600)
        print(f"    LIVE n={len(live)} span {live.index[0]} .. {live.index[-1]}")
        print(f"    LIVE gap value counts (hours): {lg.value_counts().head(6).to_dict()}")
    except Exception as e:  # noqa: BLE001
        print(f"    LIVE fetch failed: {e}")

    # do repo and live agree on the most recent common timestamps?
    common = repo.index.intersection(live.index)
    print(f"    common timestamps: {len(common)}")
    if len(common):
        a = repo.loc[common].to_numpy()
        b = live.loc[common].to_numpy()
        print(f"    max |repo-live| on common: {abs(a - b).max():.8f}   "
              f"n mismatched: {(abs(a - b) > 1e-9).sum()}")

# and the fundingInfo endpoint: current interest rate + cap/floor per symbol
try:
    r = requests.get("https://fapi.binance.com/fapi/v1/fundingInfo",
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=40)
    j = r.json()
    print(f"\n=== /fapi/v1/fundingInfo  n={len(j)}")
    for e in j:
        if e.get("symbol") in ("BTCUSDT", "ETHUSDT", "BNBUSDT", "LINKUSDT", "SOLUSDT"):
            print(f"    {e.get('symbol')}: adjustedFundingRateCap={e.get('adjustedFundingRateCap')} "
                  f"floor={e.get('adjustedFundingRateFloor')} intervalHours={e.get('fundingIntervalHours')}")
except Exception as e:  # noqa: BLE001
    print(f"fundingInfo failed: {e}")
