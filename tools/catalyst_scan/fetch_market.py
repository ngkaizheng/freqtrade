"""Catalyst scan helper: pull a wide live market snapshot and join it to
DefiLlama fee/revenue data so we can see where revenue and market cap disagree.

Writes:
    tools/catalyst_scan/out/market_snapshot.csv
    tools/catalyst_scan/out/fees_joined.csv
    tools/catalyst_scan/out/screen.txt

All data is live as of the run. Every downstream report must cite the run date.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(parents=True, exist_ok=True)

CG = "https://api.coingecko.com/api/v3"
LLAMA = "https://api.llama.fi"
HEADERS = {"accept": "application/json", "user-agent": "catalyst-scan/1.0"}


def get(url: str, **params) -> object:
    for attempt in range(4):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=45)
            if r.status_code == 200:
                return r.json()
            print(f"  [warn] {r.status_code} on {url} attempt {attempt+1}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            print(f"  [warn] {type(exc).__name__} on {url} attempt {attempt+1}", file=sys.stderr)
        time.sleep(4 * (attempt + 1))
    return None


def fetch_market(pages: int = 6, per_page: int = 250) -> pd.DataFrame:
    rows: list[dict] = []
    for page in range(1, pages + 1):
        data = get(
            f"{CG}/coins/markets",
            vs_currency="usd",
            order="market_cap_desc",
            per_page=per_page,
            page=page,
            price_change_percentage="7d,30d",
            sparkline="false",
        )
        if not data:
            print(f"  [warn] page {page} empty", file=sys.stderr)
            continue
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
        time.sleep(2.5)
    df = pd.DataFrame(rows)
    df = df[df["mcap"].notna()].copy()
    df["vol_mcap"] = df["vol24"] / df["mcap"]
    df["fdv_mcap"] = df["fdv"] / df["mcap"]
    return df


def fetch_fees(data_type: str) -> pd.DataFrame:
    """DefiLlama overview: dataType = dailyFees | dailyRevenue | dailyHoldersRevenue."""
    data = get(
        f"{LLAMA}/overview/fees",
        excludeTotalDataChart="true",
        excludeTotalDataChartBreakdown="true",
        dataType=data_type,
    )
    if not isinstance(data, dict):
        return pd.DataFrame()
    rows = []
    for p in data.get("protocols") or []:
        rows.append(
            {
                "protocol": p.get("displayName") or p.get("name"),
                "slug": p.get("slug"),
                "category": p.get("category"),
                "chains": ",".join(p.get("chains") or []),
                "fees_1d": p.get("total24h"),
                "fees_7d": p.get("total7d"),
                "fees_30d": p.get("total30d"),
                "fees_1y": p.get("total1y"),
                "fees_all": p.get("totalAllTime"),
                "change_7d": p.get("change_7d"),
                "change_30d": p.get("change_1m"),
                "mcap_llama": p.get("mcap") or p.get("mcap_llama"),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    print("Fetching CoinGecko market pages ...", file=sys.stderr)
    mkt = fetch_market()
    print(f"  {len(mkt)} coins", file=sys.stderr)
    mkt.to_csv(OUT / "market_snapshot.csv", index=False)

    frames = {}
    for dt in ("dailyFees", "dailyRevenue", "dailyHoldersRevenue"):
        print(f"Fetching DefiLlama {dt} ...", file=sys.stderr)
        frames[dt] = fetch_fees(dt)
        time.sleep(2)
        if not frames[dt].empty:
            frames[dt].to_csv(OUT / f"llama_{dt}.csv", index=False)

    lines: list[str] = []
    stamp = mkt["updated"].dropna().max()
    lines.append(f"RUN: market data last_updated max = {stamp}")
    lines.append(f"coins in snapshot: {len(mkt)}")
    lines.append("")

    lines.append("=== TOP 40 BY 30D CHANGE (mcap > $30M) ===")
    big = mkt[mkt["mcap"] > 30e6].nlargest(40, "chg30")
    lines.append(
        big[["symbol", "mcap", "fdv", "chg7", "chg30", "vol_mcap", "ath_chg"]]
        .to_string(index=False, float_format=lambda x: f"{x:,.3f}")
    )
    lines.append("")

    lines.append("=== TOP 30 BY 7D CHANGE (mcap > $100M) ===")
    mid = mkt[mkt["mcap"] > 100e6].nlargest(30, "chg7")
    lines.append(
        mid[["symbol", "mcap", "chg7", "chg30", "vol_mcap", "ath_chg"]].to_string(
            index=False, float_format=lambda x: f"{x:,.3f}"
        )
    )
    lines.append("")

    lines.append("=== BOTTOM 25 BY 30D CHANGE (mcap > $150M) ===")
    b = mkt[mkt["mcap"] > 150e6].nsmallest(25, "chg30")
    lines.append(
        b[["symbol", "mcap", "chg7", "chg30", "ath_chg"]].to_string(
            index=False, float_format=lambda x: f"{x:,.3f}"
        )
    )
    lines.append("")

    lines.append("=== FDV/MCAP BLOWOUTS (mcap > $80M, fdv/mcap > 4) ===")
    o = mkt[(mkt["mcap"] > 80e6) & (mkt["fdv_mcap"] > 4)].nlargest(30, "fdv_mcap")
    lines.append(
        o[["symbol", "mcap", "fdv", "fdv_mcap", "chg30"]].to_string(
            index=False, float_format=lambda x: f"{x:,.3f}"
        )
    )
    lines.append("")

    # join fees/revenue by symbol guessed from protocol name is unreliable; instead print
    # the raw leaders so a human/agent can match them deliberately.
    for dt in ("dailyFees", "dailyRevenue", "dailyHoldersRevenue"):
        df = frames[dt]
        if df.empty:
            lines.append(f"=== {dt}: UNAVAILABLE ===")
            continue
        d = df[df["fees_30d"].notna()].copy()
        d["ann"] = d["fees_30d"] * 12
        d = d.nlargest(45, "fees_30d")
        lines.append(f"=== {dt}: TOP 45 BY 30D (annualised = 30d x 12) ===")
        lines.append(
            d[["protocol", "category", "fees_1d", "fees_30d", "ann", "change_30d", "mcap_llama"]]
            .to_string(index=False, float_format=lambda x: f"{x:,.0f}")
        )
        lines.append("")

    (OUT / "screen.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT / 'screen.txt'}", file=sys.stderr)


if __name__ == "__main__":
    main()
