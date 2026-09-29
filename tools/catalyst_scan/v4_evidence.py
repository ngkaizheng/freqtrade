"""v4 evidence pull: re-verify the v3 candidate set on FRESH live data, and run the
attention/velocity screen that the v3 round structurally could not produce.

Why this file exists
--------------------
The v3 scan screened candidates by `annualised holders revenue / market cap` off
DefiLlama `dailyHoldersRevenue`. That screen can only ever surface protocols that
already publish a token-capture line, so opportunity archetypes C (Attention
Repricing) and D (Meme/Reflexive) were never able to enter the candidate set.
Applying the v4 formal scoring system to a universe that was pre-filtered against
two of its six archetypes would be scoring a biased sample. This file fixes that
by generating candidates from attention/velocity instead, and re-verifies every
v3 number on fresh data rather than trusting the previous report (v3 section 46).

What is and is not measurable with free sources (this drives the Score A cap)
--------------------------------------------------------------------------
    measurable : price, volume (level AND velocity), turnover, FDV/MC, mcap
    NOT free   : X mentions, Google Trends, holder counts, KOL reach, engagement
For Score A, v4 section 58 score 4 requires several metrics rising in sync
(mentions / engagement / search / volume / holders). We can only ever verify the
volume leg here, so Score A is CAPPED AT 3 unless the coin is independently
corroborated as a CoinGecko trending / dated-media name. The cap is enforced in
code (`ATTENTION_SCORE_CAP`) rather than left to judgement.

Writes
    tools/catalyst_scan/out/v4_evidence.csv     fresh per-candidate metrics
    tools/catalyst_scan/out/attention_screen.csv  attention/velocity shortlist
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(parents=True, exist_ok=True)

CG = "https://api.coingecko.com/api/v3"
LLAMA = "https://api.llama.fi"
HEADERS = {"accept": "application/json", "user-agent": "catalyst-v4/1.0"}

# Enforced cap on the v4 Attention dimension. See module docstring.
ATTENTION_SCORE_CAP = 3

CANDIDATE_IDS = [
    "kinetiq", "aerodrome-finance", "lido-dao", "ethena", "syrup", "layerzero",
    "concierge-io", "vision-3", "sushi", "bittorrent", "wink", "ore", "stonk-3",
    "pons", "hyperliquid", "uniswap", "monad", "ondo-finance", "doublezero",
    "lighter", "immutable-x", "kaito",
]

# DefiLlama slugs whose holders-revenue line feeds the Fundamental dimension.
LLAMA_SLUGS = [
    "kinetiq-khype", "aerodrome-slipstream", "lido", "ethena", "maple",
    "layerzero", "concierge", "sushi", "ore-protocol", "stonkfun",
    "hyperliquid", "uniswap", "ondo-finance", "lighter", "monad",
]


def get(url: str, **params):
    for attempt in range(5):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=45)
            if r.status_code == 200:
                return r.json()
            print(f"  [warn] {r.status_code} {url} try{attempt+1}", file=sys.stderr)
            if r.status_code == 429:
                time.sleep(20 * (attempt + 1))
        except Exception as exc:  # noqa: BLE001
            print(f"  [warn] {type(exc).__name__} {url} try{attempt+1}", file=sys.stderr)
        time.sleep(5 * (attempt + 1))
    return None


# ---------------------------------------------------------------- market data
def fresh_markets(ids: list[str]) -> pd.DataFrame:
    data = get(
        f"{CG}/coins/markets",
        vs_currency="usd",
        ids=",".join(ids),
        price_change_percentage="1h,24h,7d,30d,1y",
        sparkline="false",
    )
    if not isinstance(data, list):
        return pd.DataFrame()
    rows = []
    for c in data:
        rows.append(
            {
                "id": c.get("id"),
                "symbol": (c.get("symbol") or "").upper(),
                "name": c.get("name"),
                "rank": c.get("market_cap_rank"),
                "price": c.get("current_price"),
                "mcap": c.get("market_cap"),
                "fdv": c.get("fully_diluted_valuation"),
                "vol24": c.get("total_volume"),
                "circ": c.get("circulating_supply"),
                "total": c.get("total_supply"),
                "chg1h": c.get("price_change_percentage_1h_in_currency"),
                "chg24": c.get("price_change_percentage_24h"),
                "chg7": c.get("price_change_percentage_7d_in_currency"),
                "chg30": c.get("price_change_percentage_30d_in_currency"),
                "chg1y": c.get("price_change_percentage_1y_in_currency"),
                "ath_chg": c.get("ath_change_percentage"),
                "ath_date": c.get("ath_date"),
                "updated": c.get("last_updated"),
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["vol_mcap"] = df["vol24"] / df["mcap"]
    df["fdv_mcap"] = df["fdv"] / df["mcap"]
    # NOTE: circulating-supply growth canNOT be derived from this snapshot.
    # mcap_t = price_t * circ_t and both mcap and price are quoted at the same
    # instant, so a 30d price change cancels exactly and yields circ_t = circ_0.
    # It has to come from the historical market_chart instead; see
    # `history_metrics` below, which divides historical mcap by historical price.
    return df


def history_metrics(coin_id: str) -> dict:
    """Per-coin history: volume velocity AND a real net supply measure.

    Volume velocity : avg daily volume over the last 3d vs days 4-30.
                      This is the only genuinely measurable 'attention is
                      accelerating' leg that free sources expose.
    Net supply      : implied circulating supply = historical mcap / historical
                      price, taken at the first and last point of the window.
                      A rising number is real dilution; a falling number is
                      genuine net contraction (burn/buyback outrunning issuance).
                      This is the v4 Score S workhorse.
    """
    data = get(f"{CG}/coins/{coin_id}/market_chart",
               vs_currency="usd", days="30")
    empty = {
        "vol_accel": float("nan"), "vol_days": 0,
        "circ_start": float("nan"), "circ_end": float("nan"),
        "supply_30d_pct": float("nan"), "supply_ann_pct": float("nan"),
    }
    if not isinstance(data, dict):
        return empty
    vols = data.get("total_volumes") or []
    mcaps = data.get("market_caps") or []
    prices = data.get("prices") or []
    out = dict(empty)
    out["vol_days"] = len(vols)
    if len(vols) >= 20:
        recent = sum(v[1] for v in vols[-3:]) / 3.0
        base_vals = [v[1] for v in vols[3:-3]]
        base = sum(base_vals) / max(len(base_vals), 1)
        if base > 0:
            out["vol_accel"] = recent / base
    if len(mcaps) >= 20 and len(prices) >= 20:
        circ0 = mcaps[0][1] / prices[0][1] if prices[0][1] else float("nan")
        circ1 = mcaps[-1][1] / prices[-1][1] if prices[-1][1] else float("nan")
        out["circ_start"] = circ0
        out["circ_end"] = circ1
        if circ0 and circ0 > 0 and circ1 == circ1:
            out["supply_30d_pct"] = (circ1 / circ0 - 1.0) * 100.0
            out["supply_ann_pct"] = out["supply_30d_pct"] * 365.0 / 30.0
    return out


# ------------------------------------------------------------------ llama data
def llama_rows(data_type: str) -> pd.DataFrame:
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
                "fees_1d": p.get("total24h"),
                "fees_7d": p.get("total7d"),
                "fees_30d": p.get("total30d"),
                "change_7d": p.get("change_7d"),
                "change_1m": p.get("change_1m"),
                "mcap_llama": p.get("mcap") or p.get("mcap_llama"),
            }
        )
    return pd.DataFrame(rows)


# ------------------------------------------------------------ attention screen
def attention_screen(snap: pd.DataFrame, top_n: int = 60) -> pd.DataFrame:
    """Generate archetype C/D candidates from the universe snapshot.

    Filters are deliberately conservative and every one of them is a v4 veto
    stated in code, not a preference:
      * mcap 5M-1B       -> VETO-4 non-exitable below this for a $500 book
      * vol_mcap 0.05-25 -> VETO-4 liquidity floor, and the v3 Sand trap
                             (vol/MC of 292 was a CoinGecko data error)
      * fdv_mcap <= 3    -> VETO-5 supply overhang filter
    """
    d = snap.copy()
    d = d[
        (d["mcap"] >= 5e6)
        & (d["mcap"] <= 1e9)
        & (d["vol_mcap"] >= 0.05)
        & (d["vol_mcap"] <= 25.0)
        & (d["fdv_mcap"] <= 3.0)
        & (d["chg7"].notna())
        & (d["chg30"].notna())
    ].copy()
    # Momentum acceleration: 7D run-rate weekly vs 30D run-rate weekly.
    # Positive => the last week is running hotter than the month average.
    d["mom_accel"] = d["chg7"] - d["chg30"] / 4.2857142857
    d["screen_score"] = (
        d["mom_accel"].clip(lower=0) * 1.0
        + d["chg7"].clip(lower=0) * 0.35
        + np.log1p(d["vol_mcap"].clip(lower=0)) * 6.0
    )
    d = d.nlargest(top_n, "screen_score")
    return d[
        [
            "id", "symbol", "name", "rank", "mcap", "fdv", "vol_mcap", "fdv_mcap",
            "chg24", "chg7", "chg30", "ath_chg", "mom_accel", "screen_score",
        ]
    ]


def trending() -> list[str]:
    data = get(f"{CG}/search/trending")
    if not isinstance(data, dict):
        return []
    return [
        (i.get("item", {}).get("name") or "")
        for i in (data.get("coins") or [])
    ]


def main() -> None:
    print("fresh market pull ...", file=sys.stderr)
    mkt = fresh_markets(CANDIDATE_IDS)
    if mkt.empty:
        print("FATAL: market pull empty", file=sys.stderr)
        return
    print(f"  {len(mkt)} coins", file=sys.stderr)

    print("llama pull ...", file=sys.stderr)
    holders = llama_rows("dailyHoldersRevenue")
    holders.to_csv(OUT / "v4_llama_holders.csv", index=False)

    print("attention screen ...", file=sys.stderr)
    snap = pd.read_csv(OUT / "market_snapshot.csv")
    att = attention_screen(snap)
    print(f"  {len(att)} shortlisted", file=sys.stderr)

    tr = trending()
    print(f"  trending: {tr}", file=sys.stderr)

    # volume velocity for the shortlisted attention names + all v3 candidates
    ids = list(dict.fromkeys(list(att["id"]) + CANDIDATE_IDS))
    vrows = []
    for i, cid in enumerate(ids, 1):
        vrows.append({"id": cid, **history_metrics(cid)})
        if i % 10 == 0:
            print(f"  history {i}/{len(ids)}", file=sys.stderr)
        time.sleep(2.2)
    vel = pd.DataFrame(vrows)

    mkt = mkt.merge(vel, on="id", how="left")
    # Deliberately NOT fuzzy-joining holders revenue to tickers here. A
    # substring match protocol-slug -> CoinGecko-id is exactly how "Kinetiq"
    # picks up "Kinetiq Staked HYPE" while missing the plain protocol, and how
    # a launchpad's fee line gets silently attached to its own token. The join
    # is an explicit slug->id table in v4_score.py instead.
    mkt.to_csv(OUT / "v4_evidence.csv", index=False)
    att.to_csv(OUT / "attention_screen.csv", index=False)
    (OUT / "trending.txt").write_text("\n".join(tr), encoding="utf-8")
    print("done", file=sys.stderr)


if __name__ == "__main__":
    main()
