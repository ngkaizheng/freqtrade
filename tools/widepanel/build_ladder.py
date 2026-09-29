"""Build the liquidity ladder configs - top N by MEDIAN DAILY QUOTE VOLUME.

WHY THIS QUANTITY
-----------------
Quote volume is a property of the market, not of the strategy's return, so
ranking on it cannot select on outcome. It is a cost proxy, and it is the one
this repository has measured independently of any backtest
(`RESEARCH_STATE.md` §1b: Binance `bookDepth` shows the long tail is 1-3 orders
of magnitude thinner than BTC; §1c's `cost_R = bps/(stop_multiple x atr_pct x
1e4)` turns a thinner book into several times the cost per unit of risk).

CONCURRENCY IS PINNED PER RUNG, ON PURPOSE
------------------------------------------
`optimize_reports.py:577` computes `max_open_trades = min(setting, len(pairlist))`.
Left alone, every rung would also change the number of concurrent positions, so a
difference between rungs would be uninterpretable - the same trap the state file
records for the universe ladder. Here `max_open_trades` is set to the rung size
explicitly, so the ONLY thing that varies down the ladder is the universe.

Every rung shares one datadir (`wide104`), so the data is byte-identical across
rungs and only the whitelist changes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FEAT = ROOT / "shark_data" / "wide" / "features"
RUNGS = [12, 24, 50, 104]
BASE_CFG = ROOT / "user_data" / "config_perp_short_104.json"
OUT = ROOT / "user_data" / "config_ladder"


def main() -> int:
    syms = pd.read_csv(FEAT / "universe.csv")["symbol"].tolist()
    rows = []
    for s in syms:
        d = pd.read_parquet(FEAT / f"{s}.parquet")
        q = (d["volume"] * d["close"]).median()
        rows.append({"symbol": s, "med_quote": float(q)})
    rank = pd.DataFrame(rows).sort_values("med_quote", ascending=False)
    rank.to_csv(OUT.parent / "perp_short_out" / "liquidity_rank.csv", index=False)

    OUT.mkdir(parents=True, exist_ok=True)
    summary = []
    for n in RUNGS:
        pick = rank.head(n)["symbol"].tolist()
        pairs = [s[:-4] + "/USDT:USDT" if s.endswith("USDT") else s + "/USDT:USDT"
                 for s in pick]
        cfg = json.load(open(BASE_CFG))
        cfg["pair_whitelist"] = pairs
        cfg["exchange"]["pair_whitelist"] = pairs
        # pinned to the rung so concurrency cannot float with len(pairlist)
        cfg["max_open_trades"] = n
        cfg["logfile"] = f"user_data/logs/ladder_{n}.log"
        p = OUT / f"ladder_{n}.json"
        json.dump(cfg, open(p, "w"), indent=2)
        med = rank.head(n)["med_quote"].median()
        summary.append({"n": n, "median_quote_usd": med, "config": str(p)})
        print(f"N={n:<4} median quote vol ${med:,.0f}/bar   -> {p.name}")

    top, bottom = rank.head(24), rank.tail(54)
    print(f"\nliquidity spread across the panel: "
          f"top-24 median ${top['med_quote'].median():,.0f} vs "
          f"bottom-54 median ${bottom['med_quote'].median():,.0f} "
          f"= {top['med_quote'].median()/bottom['med_quote'].median():.0f}x")
    print(f"widest single name: ${rank['med_quote'].min():,.0f}/bar")

    json.dump(summary, open(OUT / "ladder.json", "w"), indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
