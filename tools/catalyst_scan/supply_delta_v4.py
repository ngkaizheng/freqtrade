"""Focused net-supply measurement for the candidates the report actually cites.

The broad 80-coin market_chart sweep in v4_evidence.py is rate-limited to
crawling and most of its output (volume velocity on names that fail the
information-gap gate anyway) is not load-bearing. This measures only what the
report quotes: realised circulating-supply growth for the candidates whose
Score S is argued from a number.

`market_caps[i] / prices[i]` is the implied circulating supply at that instant.
The change over the window is the realised net supply effect - issuance net of
burn - which is the only supply measure that cannot be talked up by a tokenomics
document.

Writes out/supply_delta_v4.csv.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v4_evidence import OUT, get  # noqa: E402

CG = "https://api.coingecko.com/api/v3"

TARGETS = [
    "kinetiq", "concierge-io", "syrup", "lido-dao", "aerodrome-finance",
    "sushi", "ethena", "ondo-finance", "layerzero", "immutable-x",
    "hyperliquid", "uniswap", "rhea-2", "thorchain", "the-graph", "sei-network",
    "lighter", "doublezero", "monad",
]


def measure(coin_id: str) -> dict:
    d = get(f"{CG}/coins/{coin_id}/market_chart", vs_currency="usd", days="180")
    row = {"id": coin_id}
    if not isinstance(d, dict):
        return row
    mc, pr = d.get("market_caps") or [], d.get("prices") or []
    if len(mc) < 30 or len(pr) < 30:
        return row

    def circ(i):
        return mc[i][1] / pr[i][1] if pr[i][1] else None

    c0, c1 = circ(0), circ(-1)
    if not (c0 and c1):
        return row
    chg30 = (c1 / circ(len(mc) - min(len(mc), 31)) - 1) * 100 \
        if circ(len(mc) - min(len(mc), 31)) else float("nan")
    row.update({
        "circ_start_180d": c0,
        "circ_end": c1,
        "supply_180d_pct": (c1 / c0 - 1) * 100,
        "supply_ann_pct": (c1 / c0 - 1) * 365.0 / 180.0 * 100,
        "supply_30d_pct": chg30,
        "supply_ann_from_30d_pct": chg30 * 365.0 / 30.0,
        "points": len(mc),
    })
    # volume velocity over the same window
    vol = d.get("total_volumes") or []
    if len(vol) >= 30:
        recent = sum(v[1] for v in vol[-3:]) / 3.0
        base = sum(v[1] for v in vol[3:-3]) / max(len(vol[3:-3]), 1)
        if base > 0:
            row["vol_accel_3d_vs_prior"] = recent / base
    return row


def main() -> None:
    rows = []
    for i, cid in enumerate(TARGETS, 1):
        r = measure(cid)
        rows.append(r)
        got = "ok" if "supply_180d_pct" in r else "NO DATA"
        print(f"  [{i}/{len(TARGETS)}] {cid}: {got}", file=sys.stderr)
        time.sleep(4.0)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "supply_delta_v4.csv", index=False)
    pd.set_option("display.width", 200)
    show = [c for c in ["id", "circ_end", "supply_30d_pct",
                        "supply_ann_from_30d_pct", "supply_180d_pct",
                        "supply_ann_pct", "vol_accel_3d_vs_prior"] if c in df]
    print(df[show].to_string(index=False, float_format=lambda x: f"{x:,.3f}"))


if __name__ == "__main__":
    main()
