"""Measure implied circulating-supply change from CoinGecko (supply = mcap/price).

This is the net-supply test: a headline burn or buyback is meaningless until it is
netted against issuance. For Canton in particular the question is whether the
uncapped mint exceeds the fee burn.

Usage: python tools/catalyst_scan/supply_delta.py canton-network aerodrome-finance ...
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_market as fm  # noqa: E402

H = {"accept": "application/json", "user-agent": "catalyst-scan/1.0"}


def series(coin_id: str, days: int = 365) -> tuple[pd.Series, pd.Series, pd.Series]:
    r = requests.get(
        f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart",
        params={"vs_currency": "usd", "days": days, "interval": "daily"},
        headers=H,
        timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"{coin_id}: HTTP {r.status_code}")
    d = r.json()
    conv = lambda k: pd.Series(  # noqa: E731
        {pd.to_datetime(int(t), unit="ms").date(): v for t, v in d[k] if v is not None}
    ).sort_index()
    return conv("prices"), conv("market_caps"), conv("total_volumes")


def report(coin_id: str) -> None:
    px, mc, vol = series(coin_id)
    sup = (mc / px).replace([float("inf"), float("-inf")], pd.NA).dropna()
    n = len(sup)
    print(f"=== {coin_id} ===  {n} daily points")
    if n < 31:
        print("   too few points\n")
        return
    for label, back in (("30d", 30), ("90d", 90), ("180d", 180), ("365d", 364)):
        if n > back:
            a, b = sup.iloc[-1 - back], sup.iloc[-1]
            chg = b / a - 1
            days = back
            ann = (1 + chg) ** (365 / days) - 1
            print(
                f"   {label:>5}: supply {a:,.0f} -> {b:,.0f}   {chg*100:+7.2f}%   "
                f"annualised {ann*100:+7.2f}%"
            )
    print(f"   now   : supply {sup.iloc[-1]:,.0f}  price ${px.iloc[-1]:,.6f}  mc ${mc.iloc[-1]:,.0f}")
    if n >= 60:
        h = n // 2
        print(f"   supply 1st half mean {sup.iloc[:h].mean():,.0f} vs 2nd half {sup.iloc[h:].mean():,.0f}")
    print()


if __name__ == "__main__":
    for cid in sys.argv[1:]:
        try:
            report(cid)
        except Exception as exc:  # noqa: BLE001
            print(f"=== {cid} === FAILED: {exc}\n")
        time.sleep(3)
