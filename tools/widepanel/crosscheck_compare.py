"""Like-for-like: the SAME 24 symbols, the SAME cell, in the shark engine.

The freqtrade cross-check disagreed violently with the wide-panel result
(-22.4%, PF 0.67 vs +0.176R/trade). Before concluding anything, both engines
must be run on the identical universe and their EXIT DISTRIBUTIONS compared -
not just their P&L, because an exit-distribution mismatch localises the fault.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from shark_hunter.backtest.costs import CostModel                # noqa: E402
from shark_hunter.backtest.engine import run_backtest           # noqa: E402
from shark_hunter.strategies.recipes import STRATEGIES, build_spec  # noqa: E402
from shark_hunter import config as C                             # noqa: E402

FEAT = ROOT / "shark_data" / "wide" / "features"
# read as plain JSON: pd.read_json on a bare array silently mis-parses it and
# yields the string "0" as a "symbol"
SUBSET = json.loads((ROOT / "user_data" / "data" / "wide_ft"
                     / "pairs.json").read_text())


def main() -> int:
    syms = list(SUBSET)
    print(f"subset: {len(syms)} symbols")

    frames = []
    for sym in syms:
        df = pd.read_parquet(FEAT / f"{sym}.parquet").set_index("open_time")
        df = df.copy()
        df.loc[~df["low_vol"].fillna(False), "rvol"] = np.nan   # frozen filter
        spec = build_spec(df, STRATEGIES["SHARK-01"], atr_stop=1.5,
                          r_multiple=2.0,
                          time_stop_bars=C.DEFAULT_TIME_STOP_BARS["4h"])
        res = run_backtest(df, spec, symbol=sym, timeframe="4h",
                           costs=CostModel(taker_fee_bps=C.TAKER_FEE_BPS,
                                           slippage_bps=1.0))   # calm regime
        if not res.trades.empty:
            frames.append(res.trades)
    t = pd.concat(frames, ignore_index=True)
    sh = t[t.direction == "short"].copy()
    print(f"\nshark engine, SHORT leg only, {len(syms)} symbols, B1.5, calm:")
    print(f"  short trades      : {len(sh)}")
    print(f"  mean r_net        : {sh.r_net.mean():+.4f}")
    print(f"  hit rate          : {(sh.r_net > 0).mean():.4f}")
    print(f"  mean holding bars : {sh.holding_bars.mean():.2f}")
    print(f"  median holding    : {sh.holding_bars.median():.1f}")
    print("\n  exit_reason distribution:")
    er = sh.exit_reason.value_counts(normalize=True).mul(100).round(2)
    print("   " + "\n   ".join(f"{k:<14} {v:>6.2f}%" for k, v in er.items()))
    print("\n  mean r_net by exit reason:")
    print(sh.groupby("exit_reason")["r_net"].agg(["count", "mean", "median"])
          .round(4).to_string())

    # how much of the book is exited inside 3 bars?
    early = (sh.holding_bars <= 3).mean()
    print(f"\n  fraction exiting within 3 bars: {early:.2%}")
    print(f"  mean r_net for those          : {sh.loc[sh.holding_bars <= 3, 'r_net'].mean():+.4f}")
    print(f"  mean r_net for the rest       : {sh.loc[sh.holding_bars > 3, 'r_net'].mean():+.4f}")

    sh.to_csv(ROOT / "shark_results" / "wide" / "subset_shark_shorts.csv",
              index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
