"""Print the exact cited rows for the 2026-09-29 catalyst report, so every number
in the write-up traces to a saved artifact."""
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent / "out"
m = pd.read_csv(OUT / "market_snapshot.csv")
rev = pd.read_csv(OUT / "llama_dailyHoldersRevenue.csv")

NAMES = [
    "Lido",
    "Kinetiq kHYPE",
    "LayerZero V2",
    "Maple",
    "Ethena",
    "Aerodrome Slipstream",
    "Aerodrome V1",
    "StonkFun",
    "Pons V1",
    "Pons V2",
    "ORE Protocol",
    "Hyperliquid Perps",
    "pump.fun",
    "Uniswap V3",
    "Canton",
    "SushiSwap",
]
print("=== DefiLlama dailyHoldersRevenue, cited rows ===")
print(
    rev[rev["protocol"].isin(NAMES)][
        ["protocol", "slug", "category", "fees_1d", "fees_30d", "change_30d"]
    ].to_string(index=False, float_format=lambda x: f"{x:,.0f}")
)
print()

CITE = ["KNTQ", "AERO", "ENA", "LDO", "SYRUP", "ZRO", "BTT", "WIN", "CC", "STONK", "PONS", "ORE", "AVA", "VSN", "SUSHI", "HYPE", "UNI", "PUMP"]
print("=== CoinGecko snapshot, cited rows (updated %s) ===" % m["updated"].max())
cols = ["symbol", "name", "price", "mcap", "fdv", "vol24", "chg7", "chg30", "ath_chg", "circ", "max"]
print(m[m["symbol"].isin(CITE)][cols].to_string(index=False, float_format=lambda x: f"{x:,.4f}"))
print()
print("=== derived: 24h volume / market cap (liquidity screen) ===")
s = m[m["symbol"].isin(CITE)].copy()
s["vol_mcap_pct"] = 100 * s["vol24"] / s["mcap"]
s["fdv_mcap"] = s["fdv"] / s["mcap"]
print(
    s[["symbol", "mcap", "vol_mcap_pct", "fdv_mcap"]]
    .sort_values("vol_mcap_pct")
    .to_string(index=False, float_format=lambda x: f"{x:,.2f}")
)
