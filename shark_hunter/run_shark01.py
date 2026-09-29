"""Milestone 1 (spec section 63): SHARK-01 on 5m BTCUSDT.

    python -m shark_hunter.run_shark01

Establishes whether the base hypothesis -- relative volume >= 2 plus a 20-bar
breakout, exited at 1 ATR stop / 2R target, next-bar execution, with fees and
slippage -- survives out of sample.  Every later strategy is measured against
this number, so it is worth getting exactly right before stacking anything on
top of it.
"""

from __future__ import annotations

import json
import time

import pandas as pd

from . import config as C
from .reporting.metrics import classify
from .runner import git_commit, run_recipe_universe, write_frame
from .strategies.recipes import BASELINES, STRATEGIES


def _show(title: str, frame: pd.DataFrame, cols: list[str]) -> None:
    print(f"\n--- {title} " + "-" * max(0, 66 - len(title)))
    if frame.empty:
        print("  (no rows)")
        return
    disp = frame[cols].copy()
    for c in disp.columns:
        if pd.api.types.is_float_dtype(disp[c]):
            disp[c] = disp[c].map(lambda v: "" if pd.isna(v) else f"{v:,.4f}")
    print(disp.to_string(index=False))


def main() -> int:
    t0 = time.time()
    cols = ["split", "strategy", "total_trades", "win_rate", "expectancy_r",
            "profit_factor_r", "expectancy_r_gross", "cost_per_trade_r",
            "hit_rate_r", "max_drawdown", "total_r"]

    print("=" * 74)
    print("SHARK HUNTER -- MILESTONE 1")
    print("5m BTCUSDT | RVOL>=2 + 20-bar breakout | 1 ATR stop | 2R target")
    print(f"costs: taker {C.TAKER_FEE_BPS}bps  slippage BTC {C.SLIPPAGE_BPS['BTCUSDT']}bps/side"
          f"  funding on 8h events")
    print("=" * 74)

    rows = []
    for name in ("SHARK-01", "BASELINE-C-BREAKOUT", "BASELINE-D-RVOL"):
        recipe = STRATEGIES.get(name) or BASELINES[name]
        frame, verdicts, blocked, _ = run_recipe_universe(
            recipe, symbols=("BTCUSDT",),
            splits=("train", "validation", "oos", "final_unseen"))
        print(f"\n### {name}: {recipe.description}")
        _show(f"{name} by split", frame, cols)
        for split, v in verdicts.items():
            print(f"    {split:>13}: {v['label']:<10} ({v['reason']})")
        rows.append(frame)

    full = pd.concat(rows, ignore_index=True)
    write_frame(full, "milestone1_shark01_btcusdt_5m")

    # --- the decisive comparison: does the volume filter add anything? -----
    print("\n" + "=" * 74)
    print("DECISIVE TEST (spec 47): breakout alone vs breakout + volume filter")
    print("all figures are R-multiples: expectancy in R per trade")
    print("=" * 74)
    oos = full[full["split"] == "oos"].set_index("strategy")
    if len(oos):
        for metric in ("total_trades", "expectancy_r", "expectancy_r_gross",
                       "cost_per_trade_r", "profit_factor_r", "hit_rate_r"):
            if metric in oos.columns:
                a = oos.loc["SHARK-01", metric]
                b = oos.loc["BASELINE-C-BREAKOUT", metric]
                fa = f"{a:,.4f}" if isinstance(a, float) else f"{a:,}"
                fb = f"{b:,.4f}" if isinstance(b, float) else f"{b:,}"
                print(f"  {metric:>20}  SHARK-01={fa:>12}   pure-breakout={fb:>12}")
    print("\nNOTE: a 1R stop against a 2R target needs a 33.3% hit rate to break")
    print("      even before costs. Compare hit_rate_r against that line.")

    print(f"\nelapsed {time.time() - t0:.1f}s")
    print(f"results written to {C.RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
