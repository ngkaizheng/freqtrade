"""STEP 25: validate the 5m findings on 1-minute data.

    python -m shark_hunter.run_1m_validation

The spec tests timeframes independently rather than combining them, so this
runs SHARK-01 on 1m for the primary symbol and asks whether the 5m conclusion
("the gross edge is absent, and friction alone is fatal") holds at a different
resolution -- where the stop is narrower still, and the cost problem is
therefore strictly worse.

Phase 3 of the spec (5m signal with 1m execution) is deliberately *not*
attempted: it requires a different execution model than the bar-level engine
and would be a separate piece of work.
"""

from __future__ import annotations

import time

import pandas as pd

from . import config as C
from .analysis import costs as cost_analysis
from .reporting.metrics import compute_metrics
from .runner import git_commit, get_dataset, slice_result, write_frame
from .strategies.recipes import STRATEGIES, build_spec
from .backtest.costs import CostModel
from .backtest.engine import run_backtest

SPLITS = ("train", "validation", "oos", "final_unseen")


def main() -> int:
    t0 = time.time()
    symbol = C.PRIMARY_SYMBOL
    print("=" * 74)
    print(f"STEP 25 -- 1-minute validation ({symbol})")
    print("=" * 74)

    df = get_dataset(symbol, "1m").frame
    print(f"bars: {len(df):,}")

    spec = build_spec(df, STRATEGIES["SHARK-01"],
                      time_stop_bars=C.DEFAULT_TIME_STOP_BARS["1m"])
    res = run_backtest(df, spec, symbol=symbol, timeframe="1m",
                       costs=CostModel.for_symbol(symbol))

    rows = []
    for s in C.SPLITS:
        if s.name not in SPLITS:
            continue
        m = compute_metrics(slice_result(res, s.start, s.end, 10_000.0))
        rows.append({"split": s.name, **{k: m[k] for k in
                    ("total_trades", "expectancy_r", "expectancy_r_gross",
                     "cost_per_trade_r", "profit_factor_r", "hit_rate_r",
                     "r_sharpe", "r_max_drawdown")}})
    f = pd.DataFrame(rows)
    write_frame(f, "step25_1m_validation")

    disp = f.copy()
    for c in ("expectancy_r", "expectancy_r_gross", "cost_per_trade_r",
              "profit_factor_r", "hit_rate_r", "r_sharpe"):
        disp[c] = disp[c].map(lambda v: f"{v:,.4f}" if pd.notna(v) else "n/a")
    disp["r_max_drawdown"] = disp["r_max_drawdown"].map(lambda v: f"{v:,.3f}")
    print()
    print(disp.to_string(index=False))

    # The cost ratio is resolution-dependent, so compare it explicitly.
    prof = cost_analysis.stop_width_profile(df)
    write_frame(prof, "step25_1m_cost_profile")
    if not prof.empty:
        row = prof[prof["atr_multiple"] == 1.0]
        if not row.empty:
            c1 = float(row["cost_in_r"].iloc[0])
            s1 = float(row["median_stop_pct"].iloc[0])
            print(f"\n1m 1-ATR stop: {s1 * 100:.4f}% of price -> cost_in_r = {c1:.2f}R")
            print(f"5m reference : {C.VIABLE_STOP_PCT * 100:.4f}% would be needed for "
                  f"friction < 0.2R")

    print(f"\nelapsed {time.time() - t0:.1f}s")
    print("NOTE: 1m narrows the stop without narrowing the round trip, so the cost")
    print("      problem is strictly worse than at 5m. It is reported for that reason,")
    print("      not because a finer timeframe is expected to rescue the hypothesis.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
