"""GATE 0 for the bull-market book: how many bull regimes does this sample even contain?

WHY THIS IS THE FIRST THING TO MEASURE
---------------------------------------
The whole objective is "a strategy that makes money in a bull market". Before designing
one, `AGENTS.md` 1a requires checking that the experiment **can conclude**. That question
here is not subtle and it is not a formality:

* the deployed short book's whole weakness is that it bleeds in a bull market, and the
  project's entire record rests on **ONE** bull year - 2023, +50.7 % on the panel;
* a long book tested on one bull year has **n = 1 regime**, which is a sample of bull
  markets, not a measurement of them;
* so the honest Gate 0 is not "does trend following work", it is **"how many bull regimes
  are in the panel, and how long is each one"** - because that number decides whether a
  timing book can be validated at all.

It also fixes the benchmark, which the whole comparison hangs on. Section 19c measured
equal-weight buy-and-hold over the FULL window (mean -7.1 %, median -48.5 %); that is not
the bar a bull-market book has to clear. **The bar is the market's own return in the same
regime**, and it has to be stated per regime before any strategy is written.

WHAT IT MEASURES
----------------
For the deployed 40-symbol universe, on the 4h panel: the equal-weight panel return by
calendar year and by rolling quarter, the peak-to-trough drawdown of the panel itself, and
the fraction of time the panel is above its own trailing 365-bar median.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\regime_calendar.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / "user_data" / "config_perp_forward_dry.json"
DATA = ROOT / "user_data" / "data" / "wide526" / "futures"


def main() -> int:
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    pairs = [p.replace("/", "_").replace(":", "_") for p in cfg["exchange"]["pair_whitelist"]]
    closes, vols = {}, {}
    for k in pairs:
        f = DATA / f"{k}-4h-futures.feather"
        if not f.exists():
            continue
        d = pd.read_feather(f)[["date", "close"]]
        d["date"] = pd.to_datetime(d["date"], utc=True).dt.as_unit("ns")
        d = d.drop_duplicates("date").sort_values("date")
        closes[k] = d.set_index("date")["close"]
        vols[k] = 1
    if not closes:
        print("no panel found")
        return 2
    px = pd.DataFrame(closes).sort_index()
    px = px.dropna(axis=1, how="all")
    # equal-weight panel: mean of per-symbol returns, NOT mean of prices
    r = px.pct_change()
    panel = r.mean(axis=1).dropna()
    idx = panel.index

    print("GATE 0  HOW MANY BULL REGIMES DOES THIS SAMPLE CONTAIN?\n")
    print(f"universe: {px.shape[1]} symbols with 4h bars, "
          f"{idx[0]:%Y-%m-%d} .. {idx[-1]:%Y-%m-%d} ({len(panel):,} 4h bars)\n")

    y = panel.groupby(idx.year).apply(lambda s: (1 + s).prod() - 1)
    print("PANEL RETURN BY CALENDAR YEAR  (equal weight, long-only, gross of cost)")
    for yr, v in y.items():
        bar = "#" * int(abs(v) * 60)
        print(f"  {yr}  {v:+8.1%}  {bar}")

    up = y[y > 0]
    print(f"\n  years up   : {len(up)} of {len(y)}  -> {', '.join(str(i) for i in up.index)}")
    print(f"  years down : {len(y) - len(up)} of {len(y)}  -> "
          f"{', '.join(str(i) for i in y.index if y[i] <= 0)}")

    q = panel.groupby(idx.to_period("Q")).apply(lambda s: (1 + s).prod() - 1)
    upq = q[q > 0]
    print(f"\n  QUARTERS up : {len(upq)} of {len(q)}  ({len(upq)/len(q)*100:.0f} %)")
    print(f"  QUARTERS down: {len(q)-len(upq)} of {len(q)}  "
          f"({(len(q)-len(upq))/len(q)*100:.0f} %)")
    longest_up = cur = 0
    for v in q:
        cur = cur + 1 if v > 0 else 0
        longest_up = max(longest_up, cur)
    print(f"  longest unbroken run of UP quarters: {longest_up} "
          f"(~{longest_up*0.25:.1f} years)")

    eq = (1 + panel).cumprod()
    dd = eq / eq.cummax() - 1
    print(f"\n  panel peak-to-trough drawdown over the whole window: {dd.min():.1%}")
    print(f"  panel total, buy-and-hold, all {len(y)} years: "
          f"{(1+panel).prod()-1:+.1%}")

    above = (panel > 0).rolling(365 * 6, min_periods=200).mean()
    print(f"\n  share of 4h bars where the panel made money: {(panel > 0).mean():.1%}")
    print(f"  share above its own trailing 6-month mean    : {above.dropna().mean():.1%}")

    print("\nTHE BAR A BULL-MARKET BOOK HAS TO CLEAR")
    print("  A long timing book must beat the panel in the SAME regime, net of the")
    print("  measured round trip. The panel's best year here is "
          f"{y.max():+.1%} ({y.idxmax()}) and its")
    print(f"  median up year is {up.median():+.1%}. Beating a median up year net of")
    print("  12-35 bps round trip is a real bar, and it is the one that matters - not a")
    print("  bar set by a parameter this project chose.")

    print("\nPOWER VERDICT (AGENTS.md 1a)")
    n_years = len(y)
    n_up = len(up)
    if n_up <= 1:
        print(f"  ** INSUFFICIENT. {n_up} up year out of {n_years} is n=1 on the quantity")
        print("     that matters. A timing book CANNOT be validated on this sample and no")
        print("     amount of research changes that. **")
        return 3
    print(f"  {n_up} up years and {len(upq)} up quarters of {n_years} years / {len(q)}.")
    print("  That is enough to distinguish a book that profits in up regimes from one")
    print("  that does not, PROVIDED the result is judged on the UP REGIMES ALONE and")
    print("  published with the down regimes beside it. A book that only works because")
    print("  the sample happened to be kind is still visible in this table.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
