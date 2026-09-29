"""Targeted, patient retry of the ONE CoinGecko page that kept 429ing (rank ~501-750).

Long backoff, single page, merge on success. Idempotent.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_market as fm  # noqa: E402

OUT = fm.OUT
H = {"accept": "application/json", "user-agent": "catalyst-scan/1.0"}
PAGE = 3
PER_PAGE = 250


def attempt(page: int, wait_first: int) -> list[dict] | None:
    if wait_first:
        print(f"  sleeping {wait_first}s before request ...", flush=True)
        time.sleep(wait_first)
    r = requests.get(
        f"{fm.CG}/coins/markets",
        params={
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": PER_PAGE,
            "page": page,
            "price_change_percentage": "7d,30d",
            "sparkline": "false",
        },
        headers=H,
        timeout=60,
    )
    if r.status_code == 200:
        return r.json()
    print(f"  HTTP {r.status_code}", flush=True)
    return None


def main() -> None:
    data = None
    for i, wait in enumerate([30, 60, 120, 180, 240]):
        print(f"attempt {i + 1}/5 for page {PAGE}", flush=True)
        data = attempt(PAGE, wait)
        if data:
            break
    if not data:
        print("PAGE 3 STILL UNAVAILABLE after 5 patient attempts - gap remains, reported as such")
        return

    rows = []
    for c in data:
        rows.append(
            {
                "id": c.get("id"),
                "symbol": (c.get("symbol") or "").upper(),
                "name": c.get("name"),
                "price": c.get("current_price"),
                "mcap": c.get("market_cap"),
                "fdv": c.get("fully_diluted_valuation"),
                "vol24": c.get("total_volume"),
                "circ": c.get("circulating_supply"),
                "total": c.get("total_supply"),
                "max": c.get("max_supply"),
                "chg24": c.get("price_change_percentage_24h"),
                "chg7": c.get("price_change_percentage_7d_in_currency"),
                "chg30": c.get("price_change_percentage_30d_in_currency"),
                "ath": c.get("ath"),
                "ath_chg": c.get("ath_change_percentage"),
                "ath_date": c.get("ath_date"),
                "rank": c.get("market_cap_rank"),
                "updated": c.get("last_updated"),
            }
        )
    new = pd.DataFrame(rows)
    new = new[new["mcap"].notna()].copy()
    new["vol_mcap"] = new["vol24"] / new["mcap"]
    new["fdv_mcap"] = new["fdv"] / new["mcap"]

    base = pd.read_csv(OUT / "market_snapshot.csv")
    have = set(base["id"].dropna())
    add = new[~new["id"].isin(have)]
    print(f"page {PAGE}: {len(new)} rows, {len(add)} new")
    merged = pd.concat([base, add], ignore_index=True).drop_duplicates(subset=["id"], keep="first")
    merged.to_csv(OUT / "market_snapshot.csv", index=False)
    print(f"merged snapshot: {len(merged)} coins, ranks 1-{int(merged['rank'].max())}")

    band = merged[(merged["rank"] > 500) & (merged["rank"] <= 750)]
    print(f"coins now held in ranks 501-750: {len(band)}")
    print()
    print("=== RANKS 501-750: TOP 20 BY 30D CHANGE (mcap > $15M) ===")
    b = band[band["mcap"] > 15e6].nlargest(20, "chg30")
    print(
        b[["symbol", "name", "rank", "mcap", "chg7", "chg30", "vol_mcap", "ath_chg"]].to_string(
            index=False, float_format=lambda x: f"{x:,.3f}"
        )
    )
    print()
    print("=== RANKS 501-750: POSITIVE 7D AND 30D, BEST LIQUIDITY ===")
    b2 = band[(band["chg7"] > 0) & (band["chg30"] > 0) & (band["mcap"] > 15e6)]
    b2 = b2[(b2["vol_mcap"] > 0.02) & (b2["vol_mcap"] < 5)]
    print(
        b2.nlargest(20, "vol_mcap")[
            ["symbol", "name", "rank", "mcap", "chg7", "chg30", "vol_mcap"]
        ].to_string(index=False, float_format=lambda x: f"{x:,.3f}")
    )
    print()
    print("=== DATA-QUALITY CHECK: vol/MC > 50 is implausible - flag, do not trade on it ===")
    bad = merged[(merged["vol_mcap"] > 50) & (merged["mcap"] > 10e6)]
    print(
        bad[["symbol", "name", "mcap", "vol24", "vol_mcap"]].to_string(
            index=False, float_format=lambda x: f"{x:,.2f}"
        )
    )


if __name__ == "__main__":
    main()
