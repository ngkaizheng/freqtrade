"""Detect stale/zero-volume runs in the downloaded klines.

The integrity check in `data/normalization.py` verifies that no *rows* are
missing. It does not catch bars that are present but frozen: identical
open/high/low/close with zero volume.  A cross-check of native 1h klines
against the aggregation of 5m klines exposed a 35-bar run on BTCUSDT
2023-11-10 where the 5m series froze at 37118.4 with zero volume while the
exchange's own 1h bar shows an active market.

Frozen runs are not merely cosmetic:
  * RVOL is pinned near zero, so the bars can never qualify as a spike
  * a rolling 20-bar high/low computed across a freeze suppresses the real
    breakout that follows it
  * ATR collapses, which shrinks the stop and inflates cost_in_r

This script measures how much of the sample is affected before anything is
changed, because the first question is whether it moves the results at all.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from shark_hunter import config as C
from shark_hunter.data import loader

MIN_RUN = 3          # consecutive frozen bars before it counts as an artefact


def frozen_runs(df: pd.DataFrame, min_run: int = MIN_RUN) -> pd.DataFrame:
    """Contiguous runs of bars with no trading range."""
    flat = (df["high"] <= df["low"])
    zero_vol = df["volume"] <= 0
    bad = (flat & zero_vol).to_numpy()
    rows, start = [], None
    for i, v in enumerate(bad):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if i - start >= min_run:
                rows.append({"start": df.index[start], "end": df.index[i - 1],
                             "bars": i - start})
            start = None
    if start is not None and len(bad) - start >= min_run:
        rows.append({"start": df.index[start], "end": df.index[-1],
                     "bars": len(bad) - start})
    return pd.DataFrame(rows)


def main() -> int:
    print("=" * 74)
    print("STALE / ZERO-VOLUME RUN DETECTION")
    print("=" * 74)
    summary, total_runs, total_bars = [], 0, 0
    for sym in C.UNIVERSE:
        for tf in ("5m", "1h", "4h"):
            df = loader.load_klines(sym, tf)
            runs = frozen_runs(df)
            nbars = int(runs["bars"].sum()) if not runs.empty else 0
            total_runs += len(runs)
            total_bars += nbars
            summary.append({
                "symbol": sym, "timeframe": tf, "bars": len(df),
                "frozen_runs": len(runs), "frozen_bars": nbars,
                "frozen_pct": 100.0 * nbars / max(len(df), 1),
                "max_run_bars": int(runs["bars"].max()) if not runs.empty else 0,
            })
            if len(runs) and tf == "5m":
                print(f"  {sym:<10} 5m  {len(runs):>3} runs, {nbars:>4} bars "
                      f"({100.0 * nbars / len(df):.3f}%), longest "
                      f"{int(runs['bars'].max())}")
    s = pd.DataFrame(summary)
    print("\n--- by timeframe ---")
    g = (s.groupby("timeframe")
         .agg(runs=("frozen_runs", "sum"), bars=("frozen_bars", "sum"),
              max_run=("max_run_bars", "max"),
              worst_pct=("frozen_pct", "max"), mean_pct=("frozen_pct", "mean"))
         .reset_index())
    print(g.to_string(index=False))
    print(f"\nTOTAL: {total_runs} runs, {total_bars} frozen bars "
          f"({100.0 * total_bars / s['bars'].sum():.4f}% of all bars)")

    out = C.RESULTS_DIR / "data_quality_frozen_runs.csv"
    s.to_csv(out, index=False)
    print(f"written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
