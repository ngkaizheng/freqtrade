"""Fill the CoinGecko page that 429'd during the main run, and extend the
universe, then re-run the mover screen on the completed snapshot.

This closes a stated coverage gap: page 3 (ranks ~501-750) was rate-limited in the
original run, so the mid-cap band was never screened.
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
    base = pd.read_csv(OUT / "market_snapshot.csv")
    have = set(base["id"].dropna())
    print(f"existing snapshot: {len(base)} coins, max rank observed {int(base['rank'].max())}")

    new = fm.fetch_market(pages=8, per_page=250)
    print(f"fresh pull: {len(new)} coins, ranks {int(new['rank'].min())}-{int(new['rank'].max())}")

    add = new[~new["id"].isin(have)].copy()
    print(f"new rows not already held: {len(add)}")
    ranks = add["rank"].dropna().astype("int64").sort_values().tolist()
    print(f"ranks of new rows: {ranks[:40]}{' ...' if len(ranks) > 40 else ''}")

    merged = pd.concat([base, add], ignore_index=True)
    merged = merged.drop_duplicates(subset=["id"], keep="first")
    merged.to_csv(OUT / "market_snapshot.csv", index=False)
    print(f"merged snapshot: {len(merged)} coins, ranks 1-{int(merged['rank'].max())}")

    m = merged.dropna(subset=["chg30"])
    print()
    print("=== TOP 30 BY 30D CHANGE, mcap $20M-$400M (mid-cap band that was missing) ===")
    band = m[(m["mcap"] > 20e6) & (m["mcap"] < 400e6)].nlargest(30, "chg30")
    print(
        band[["symbol", "name", "rank", "mcap", "chg7", "chg30", "vol_mcap", "ath_chg"]].to_string(
            index=False, float_format=lambda x: f"{x:,.3f}"
        )
    )
    print()
    print("=== MID-CAP BAND WITH POSITIVE 7D AND 30D, SORTED BY vol/MC (tradeable liquidity) ===")
    band2 = m[(m["mcap"] > 20e6) & (m["mcap"] < 400e6) & (m["chg7"] > 0) & (m["chg30"] > 0)]
    band2 = band2.nlargest(25, "vol_mcap")
    print(
        band2[["symbol", "name", "rank", "mcap", "chg7", "chg30", "vol_mcap"]].to_string(
            index=False, float_format=lambda x: f"{x:,.3f}"
        )
    )
    print()
    print(f"breadth recheck: coins={len(m)}, share up 30d={100*(m['chg30']>0).mean():.1f}%")
    time.sleep(1)


if __name__ == "__main__":
    main()
