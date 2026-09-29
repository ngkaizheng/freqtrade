"""Is a liquidity filter on the 515-symbol universe just a survivorship filter?

The question
------------
`WIDENED_UNIVERSE_RESULT_2026-09-28.md` located the failure precisely: the gross
edge exists on BOTH cohorts (BCDE gross PF 1.08), and costs eat the newer coins'
edge entirely (PF 1.08 -> 1.01) while the 2023 survivors' survives (1.25 -> 1.10).

The obvious repair is therefore "trade only where the signal survives cost", and
the obvious instrument is a liquidity filter - the `cost_R` law and the cohort
comparison both say cost is the mechanism.

**But before building that, the honest question is whether it would work at all,
and it is cheap to answer: is the most liquid slice of 515 just cohort A wearing
a different name?** If top-100-by-volume is 90% survivors, then a liquidity
filter is a SURVIVORSHIP FILTER, it re-imports exactly the bias the last round
measured and declared unfixable, and building it would be a way of getting the
retracted +52.4% back without saying so.

This prints the cohort composition of the top-N by median quote volume, so that
can be settled BEFORE a prereg commits to a design.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\liq_overlap.py
"""

from __future__ import annotations

import glob
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = "."
OUT = "user_data/perp_short_out/liquidity_515.csv"


def main() -> int:
    uni = json.load(open("shark_data/widened/universe.json"))
    co = {u["symbol"]: u["cohort"] for u in uni}
    rows = []
    for f in glob.glob("user_data/data/wide526/futures/*-4h-futures.feather"):
        stem = os.path.basename(f).split("-4h-futures")[0]
        sym = stem[:-len("_USDT_USDT")] + "USDT"
        d = pd.read_feather(f, columns=["close", "volume"])
        if len(d) < 420:
            continue
        rows.append({"symbol": sym, "cohort": co.get(sym, "?"),
                     "med_quote": float((d["close"] * d["volume"]).median())})
    if not rows:
        print("no symbols with >=420 bars")
        return 1
    df = pd.DataFrame(rows).sort_values("med_quote", ascending=False).reset_index(drop=True)
    df.to_csv(OUT, index=False)
    print(f"symbols with >=420 bars: {len(df)}")
    print(f"overall cohort mix     : {df['cohort'].value_counts().sort_index().to_dict()}")
    print()
    print("COHORT COMPOSITION OF THE TOP-N BY MEDIAN QUOTE VOLUME")
    print("  A = the 104 perps that existed before 2023-01 and are still listed")
    print()
    print(f"{'top N':>7}{'A':>6}{'B-E':>6}{'A share':>10}{'median quote/bar':>20}")
    for n in (12, 24, 50, 100, 150, 200, 300, 400, len(df)):
        if n > len(df):
            break
        sub = df.head(n)
        a = int((sub["cohort"] == "A").sum())
        print(f"{n:>7}{a:>6}{n-a:>6}{a/n*100:>9.1f}%{sub['med_quote'].median():>19,.0f}")

    print()
    print("=== WHERE DOES EACH COHORT SIT IN THE LIQUIDITY RANKING? ===")
    df["rank"] = np.arange(1, len(df) + 1)
    print(df.groupby("cohort")["rank"].agg(["count", "median", "min", "max"]))

    print()
    print("=== THE HONEST READING ===")
    top50 = df.head(50)
    a50 = int((top50["cohort"] == "A").sum())
    if a50 / 50 > 0.5:
        print(f"  top-50 is {a50}/50 = {a50/50*100:.0f}% cohort A. A liquidity filter")
        print("  here is substantially a SURVIVORSHIP filter: it re-imports the bias")
        print("  the widened-universe round measured and declared unfixable.")
    else:
        print(f"  top-50 is only {a50}/50 = {a50/50*100:.0f}% cohort A, so a liquidity")
        print("  filter is NOT a survivorship filter and can be tested on its merits.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
