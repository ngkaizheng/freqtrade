"""Per-pair coverage of the leaderboard universe + the fee frontier runner.

Written 2026-09-27 for the freqle.org leaderboard audit.
Prediction registered in docs-myself/COMMUNITY_STRATEGY_REVIEW_2026-09-27.md:
the gross-vs-net curve STARTS AT OR BELOW ZERO AT ZERO COST.
"""
import glob
import os
import sys

import pandas as pd

DATADIR = "user_data/data_leaderboard"


def coverage():
    rows = []
    for f in sorted(glob.glob(os.path.join(DATADIR, "*_USDT-5m.feather"))):
        d = pd.read_feather(f, columns=["date"])
        rows.append(
            (
                os.path.basename(f).replace("_USDT-5m.feather", ""),
                str(d["date"].min())[:10],
                str(d["date"].max())[:10],
                len(d),
            )
        )
    rows.sort(key=lambda r: r[3])
    print("{:8s} {:12s} {:12s} {:>9s}".format("pair", "start", "end", "bars"))
    for r in rows:
        print("{:8s} {:12s} {:12s} {:>9d}".format(*r))
    full = 525675  # bars in a clean 2021-01-01 -> 2026-01-01 5m series
    print()
    print("pairs                 :", len(rows))
    print("total bars            :", sum(r[3] for r in rows))
    print("late-listed pairs     :", sum(1 for r in rows if r[1] > "2021-01-01"), "of", len(rows))
    print("full-window pairs     :", sum(1 for r in rows if r[3] == full))
    missing = sum(full - r[3] for r in rows if r[3] < full)
    print("bars missing vs full  :", missing, "({:.1f}% of a 33-pair full universe)".format(
        100.0 * missing / (full * len(rows))))
    return rows


if __name__ == "__main__":
    coverage()
    sys.exit(0)
