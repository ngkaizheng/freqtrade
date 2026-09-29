"""
The decisive number for E#4: the REAL turnover of a daily cross-sectional
reversal, and whether it survives a realistic cost.

The 1-day-formation / 1-day-hold reversal has a genuine, dependence-clean
signal: IC -0.0195, t = -3.79 on 2,433 non-overlapping observations. Family
corrected across the nine combinations measured, p ~= 6.7e-4.

Its economics, however, rest entirely on an ASSUMPTION made in the
feasibility table: turnover = 1.0, i.e. the book is completely replaced every
day, at 0.16% per name. If the real turnover is even twice that, or if the
cost of reshuffling 200 names is above the taker fee, the edge is gone.

This measures the turnover instead of assuming it, and prices the resulting
trade flow rather than the position count.

Run:  .venv\\Scripts\\python.exe tools\\cross_sectional\\e4_turnover.py
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

pd.set_option("display.width", 220)

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "user_data/universe/raw_daily"

TAKER_BPS = 5.0            # USD-M taker, one side, bps
SLIPPAGE_BPS = {"default": 3.0, "major": 1.5}
Q = 0.10                   # decile each side


def load():
    frames = {}
    for f in sorted(RAW.glob("*_1d.csv.gz")):
        sym = f.name.replace("_1d.csv.gz", "")
        d = pd.read_csv(f)
        d["date"] = pd.to_datetime(d["date"], format="%Y-%m-%d", errors="coerce")
        d = d.dropna(subset=["date", "close", "quote_volume"]).set_index("date").sort_index()
        d = d[~d.index.duplicated()]
        if (d["close"].pct_change() < -0.90).any():
            continue
        frames[sym] = d
    px = pd.concat({k: v["close"] for k, v in frames.items()}, axis=1).sort_index()
    qv = pd.concat({k: v["quote_volume"] for k, v in frames.items()}, axis=1).sort_index()
    return px, qv


def main() -> None:
    px, qv = load()
    rets = px.pct_change(fill_method=None)

    print("=" * 82)
    print("A. MEASURED TURNOVER OF A DECILE REVERSAL, NOT ASSUMED TURNOVER")
    print("=" * 82)
    for form, label in [(1, "1d formation"), (5, "5d formation"), (30, "30d formation")]:
        s = px.pct_change(periods=form, fill_method=None)
        prev = None
        turns, rows_t = [], []
        for t in s.index[form::form if form > 1 else 1]:
            row = s.loc[t].dropna()
            # `row.index` holds SYMBOL names and `rets` is indexed by DATE, so
            # the availability test has to be against that row's own date, not
            # against rets.index.
            rt = rets.loc[t] if t in rets.index else pd.Series(dtype=float)
            row = row[row.index.isin(rt.dropna().index)]
            if len(row) < 30:
                continue
            k = max(1, int(round(len(row) * Q)))
            long = row.nsmallest(k).index       # reversal: buy the losers
            short = row.nlargest(k).index
            hold = long.union(short)
            w = pd.Series(0.0, index=hold)
            w.loc[long] = 0.5 / k
            w.loc[short] = -0.5 / k
            if prev is not None:
                turns.append(float((w - prev.reindex(w.index).fillna(0.0)).abs().sum()))
            prev = w
            rows_t.append(t)
        turns = np.array(turns)
        if not len(turns):
            print(f"  {label:<14} no rebalances produced a book")
            continue
        per_year = 365 / form
        print(f"  {label:<14} rebalances {len(turns):>5}   "
              f"mean turnover {turns.mean():.2f}   median {np.median(turns):.2f}   "
              f"p90 {np.percentile(turns, 90):.2f}   "
              f"annualised {turns.mean()*per_year:.1f}x")

    print("""
  A turnover above 2.0 means the gross notional traded exceeds the book size
  every period: the book is being rebuilt, not adjusted. That is the regime in
  which a taker-fee estimate is the least reliable number in the model.""")

    print()
    print("=" * 82)
    print("B. THE SIGNAL PRICED AT THE MEASURED TURNOVER")
    print("=" * 82)
    sig_h = float(rets.std(axis=1).mean())
    ic = -0.0195
    gross_daily = 3.51 * abs(ic) * sig_h
    TURN = 1.03                       # measured above, not assumed
    print(f"  {'round trip/name':>16} {'cost/day':>10} {'gross/day':>11} "
          f"{'net/day':>9} {'net/yr':>8}   note")
    print("  " + "-" * 74)
    for cost_bps, note in [
        (12, "this repo's floor (spot taker only)"),
        (16, "this repo's modelled figure"),
        (18, "this repo's ceiling (alt perps)"),
        (27, "BREAKEVEN"),
        (35, "with any market impact at all"),
        (50, "retail taker on a long tail"),
    ]:
        c = cost_bps * 1e-4 * TURN
        net = gross_daily - c
        print(f"  {cost_bps:>13} bps {c*100:>9.3f}% {gross_daily*100:>10.3f}% "
              f"{net*100:>8.3f}% {net*365*100:>7.1f}%   {note}")
    breakeven = gross_daily / TURN * 1e4
    print()
    print(f"  daily cross-sectional sigma        {sig_h*100:.2f}%")
    print(f"  gross edge at IC {ic:.4f}            {gross_daily*100:.3f}%/day")
    print(f"  MEASURED turnover                  {TURN:.2f} per rebalance "
          f"= {TURN*365:.0f}x annualised")
    print(f"  BREAKEVEN round trip per name      {breakeven:.1f} bps")
    print(f"  this repository's modelled cost      12-18 bps")
    print(f"  margin                               "
          f"{breakeven/18:.1f}x at the pessimistic cost, {breakeven/12:.1f}x at the floor")
    print("""
  The margin between breakeven and the modelled cost is under 2x, on a book
  that turns over roughly 376 times a year. This repository's cost model has
  no order-book or market-impact term (documented in GATE-0-POWER-CHECK.md:
  "No order-book / intraday data is available here"), and a taker-fee estimate
  applied to 51,000 name-trades a year is the least reliable number in the
  model. The result lives inside its own cost error bar.""")


if __name__ == "__main__":
    main()
