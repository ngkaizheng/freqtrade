"""Join DefiLlama dailyHoldersRevenue to each protocol's market cap to rank
annualised holder revenue / market cap.

That ratio is the screen for 'is the protocol paying holders something material
relative to what the token costs' - the entry point for the catalyst work, not a
conclusion. A high ratio is a question ('why is the market not paying for this?'),
never a buy signal.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_market as fm  # noqa: E402

OUT = fm.OUT


def main() -> None:
    df = pd.read_csv(OUT / "llama_dailyHoldersRevenue.csv")
    df = df.dropna(subset=["fees_30d", "slug"])
    df = df[df["fees_30d"] > 0].copy()
    df["ann_holders_rev"] = df["fees_30d"] * 12

    top = df.nlargest(int(sys.argv[1]) if len(sys.argv) > 1 else 90, "fees_30d").copy()

    mcaps = {}
    for i, row in enumerate(top.itertuples(), 1):
        slug = row.slug
        data = fm.get(f"{fm.LLAMA}/protocol/{slug}")
        mc = None
        if isinstance(data, dict):
            mc = data.get("mcap")
            if mc is None:
                # some protocols carry it on the token mapping
                mc = (data.get("tokens") or [{}])
        mcaps[slug] = mc if isinstance(mc, (int, float)) else None
        print(f"  {i}/{len(top)} {slug} mcap={mcaps[slug]}", file=sys.stderr)
        time.sleep(1.2)

    top["mcap_llama"] = top["slug"].map(mcaps)
    top["ann_rev_over_mcap"] = top["ann_holders_rev"] / top["mcap_llama"]

    have = top.dropna(subset=["mcap_llama"]).copy()
    have = have[have["mcap_llama"] > 0]
    have = have.sort_values("ann_rev_over_mcap", ascending=False)

    cols = [
        "protocol",
        "slug",
        "category",
        "fees_1d",
        "fees_30d",
        "ann_holders_rev",
        "mcap_llama",
        "ann_rev_over_mcap",
        "change_30d",
    ]
    out = have[cols]
    out.to_csv(OUT / "holders_yield.csv", index=False)
    print()
    print("=== ANNUALISED HOLDER REVENUE / MARKET CAP, TOP 90 BY 30D REVENUE ===")
    print(f"({len(have)} of {len(top)} protocols had a market cap on DefiLlama)")
    print(out.to_string(index=False, float_format=lambda x: f"{x:,.4f}"))
    print()
    print("=== NO MARKET CAP ON DEFILLAMA (needs manual lookup) ===")
    print(
        top[top["mcap_llama"].isna()][["protocol", "slug", "category", "fees_30d", "ann_holders_rev", "change_30d"]]
        .to_string(index=False, float_format=lambda x: f"{x:,.0f}")
    )


if __name__ == "__main__":
    main()
