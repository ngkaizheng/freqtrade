"""Build 12h / 1d / 3d panels by aggregating the 4h panel UPWARD.

WHY
---
H-1 (`docs-myself/PREREG_HORIZON_2026-09-30.md`) backtests the frozen strategy on a
coarser clock. The 4h panel is the finest data this project holds for 515 perps, so
coarser horizons are built from it.

THE RULE, AND IT IS THE ONE THIS PROJECT HAS ALREADY PAID FOR
--------------------------------------------------------------
Section 35's first version of the family pre-screen resampled 4h DOWN to 1m/5m/15m/1h
and called the result measured. It printed an identical ATR at five horizons, all
thirteen families came out OPEN, and the whole screen was wrong. The correct rule,
now enforced in `family_prescreen.py`:

    FEWER bars than the source  => a coarser bucket  => VALID aggregation
    MORE   bars than the source => finer than the data => FABRICATED, reject

This tool only ever produces fewer bars, and **it asserts that it did**:

    rows_out <= rows_in     for every symbol, or the run aborts.

OHLC aggregation is exact: the coarser high is the max of the finer highs, the low is
the min, and the close is the last close. A stop that sat on an intrabar extreme is
therefore preserved, which matters because this project's exits are ATR stops.

WHERE THE FILES GO
------------------
`user_data/data/wide526/futures/`, alongside the 4h files. Freqtrade resolves data as
`<pair>-<timeframe>-futures.feather`, so adding 12h/1d/3d files cannot affect the 4h
run, and the 1h funding and mark files this project depends on stay exactly where the
engine already finds them (`backtesting.py:416-465`, `fail_without_data=True`). The
alternative - a separate `--datadir` - would put those files out of reach.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\build_coarse_panels.py
"""

from __future__ import annotations

import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "user_data" / "data" / "wide526" / "futures"
TARGETS = {"12h": "12h", "1d": "1d", "3d": "3d"}
# 12h = 3 x 4h, 1d = 6 x 4h, 3d = 18 x 4h
FACTOR = {"12h": 3, "1d": 6, "3d": 18}


def build(args: tuple[str, str]) -> tuple[str, int, int, str]:
    path, tf = args
    p = Path(path)
    if not p.name.endswith("-4h-futures.feather"):
        return p.name, 0, 0, "skip"
    out = DATA / p.name.replace("-4h-futures.feather", f"-{tf}-futures.feather")
    if out.exists() and out.stat().st_size > 0:
        return p.name, -1, -1, "cached"
    x = pd.read_feather(p)[["date", "open", "high", "low", "close", "volume"]]
    x["date"] = pd.to_datetime(x["date"], utc=True).dt.as_unit("ns")
    n_in = len(x)
    rule = {"12h": "12h", "1d": "1D", "3d": "3D"}[tf]
    g = (x.set_index("date")
         .resample(rule, label="left", closed="left")
         .agg({"open": "first", "high": "max", "low": "min",
               "close": "last", "volume": "sum"})
         .dropna(subset=["open", "high", "low", "close"])
         .reset_index())
    n_out = len(g)
    # THE ASSERTION. A resample that produced MORE bars than it consumed is a bug,
    # and §35's bug produced a table with a completely normal shape.
    if n_out > n_in:
        return p.name, n_in, n_out, "REFUSED: more bars out than in"
    g.to_feather(out)
    return p.name, n_in, n_out, "ok"


def main() -> int:
    src = sorted(DATA.glob("*-4h-futures.feather"))
    print(f"BUILDING COARSER PANELS by UPWARD aggregation from {len(src)} 4h files")
    print(f"rule: fewer bars than the source is a coarser bucket and is VALID;")
    print(f"      more bars would be FABRICATED. Asserted per symbol, not assumed.\n")
    bad = 0
    for tf in TARGETS:
        jobs = [(str(p), tf) for p in src]
        with ProcessPoolExecutor(max_workers=6) as ex:
            res = list(ex.map(build, jobs))
        tally: dict[str, int] = {}
        for _, st, _, why in res:
            tally[why] = tally.get(why, 0) + 1
        made = sum(1 for _, a, b, w in res if w == "ok")
        refused = tally.get("REFUSED: more bars out than in", 0)
        bad += refused
        sizes = {f: DATA.glob(f"*-{f}-futures.feather") for f in TARGETS}
        n = sum(1 for _ in sizes[tf])
        mb = sum(f.stat().st_size for f in sizes[tf]) / 1e6
        print(f"  {tf:<4} built {made:>4}   {dict(tally)}")
        print(f"       -> {n} files on disk, {mb:.0f} MB")
        if made:
            r = [x for x in res if x[3] == "ok"][0]
            print(f"       e.g. {r[0][:22]}: {r[1]:,} 4h bars -> {r[2]:,} {tf} bars "
                  f"({r[1]/r[2]:.1f}x fewer)")
    print(f"\n{'OK - no symbol produced more bars than it consumed' if not bad else f'** {bad} REFUSED **'}")
    print("The 4h files are untouched, and freqtrade resolves data by "
          "<pair>-<timeframe>-, so\nthe deployed 4h run cannot be affected by anything here.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
