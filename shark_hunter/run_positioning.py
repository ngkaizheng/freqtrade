"""Phase 7: the positioning signals that were downloaded but never tested.

    python -m shark_hunter.run_positioning

The Binance metrics archive carries top-trader long/short ratios, the global
long/short account ratio, and the taker buy/sell volume ratio alongside open
interest.  The spec only asked for OI, so the other three were fetched and
carried through the pipeline but never used by any strategy.  They are free,
5-minute, and cover the whole sample -- and positioning is the closest thing
this data has to a direct measurement of the "crowded participants" the whole
thesis is about.

Reported with SHARK-01 as the control, at 4h (the timeframe where friction
stops dominating) and 5m (for continuity with phase 1).
"""

from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from . import config as C
from .analysis.benchmarks import effective_sample_size, minimum_detectable_effect
from .backtest.costs import CostModel
from .backtest.engine import run_backtest
from .reporting.metrics import compute_metrics
from .runner import get_dataset, git_commit, slice_result, write_frame, write_manifest
from .strategies.positioning import (POSITIONING_STRATEGIES, build_positioning_spec,
                                     positioning_signal)
from .strategies.recipes import STRATEGIES, build_spec

SPLITS = ("train", "validation", "oos", "final_unseen")


def _log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def _universe(recipe, timeframe: str, *, positioning: bool):
    rows, trades = [], []
    for sym in C.UNIVERSE:
        df = get_dataset(sym, timeframe).frame
        if positioning:
            spec = build_positioning_spec(
                df, recipe, time_stop_bars=C.DEFAULT_TIME_STOP_BARS[timeframe])
        else:
            spec = build_spec(df, recipe,
                              time_stop_bars=C.DEFAULT_TIME_STOP_BARS[timeframe])
        res = run_backtest(df, spec, symbol=sym, timeframe=timeframe,
                           costs=CostModel.for_symbol(sym))
        if res.trades.empty:
            continue
        trades.append(res.trades)
        for s in C.SPLITS:
            m = compute_metrics(slice_result(res, s.start, s.end, 10_000.0))
            # timeframe must travel with the row: without it the 4h and 5m
            # results are indistinguishable and any group-by silently blends
            # two regimes that have nothing in common.
            rows.append({"timeframe": timeframe, "strategy": recipe.name,
                         "symbol": sym, "split": s.name,
                         **{k: m[k] for k in ("total_trades", "expectancy_r",
                                              "expectancy_r_gross", "cost_per_trade_r",
                                              "hit_rate_r")}})
    return rows, trades


def main() -> int:
    t0 = time.time()
    print("=" * 78)
    print("PHASE 7: POSITIONING SIGNALS (downloaded since phase 1, never tested)")
    print("=" * 78)

    all_rows, power_rows, sig_rows = [], [], []

    for tf in ("4h", "5m"):
        _log(f"--- {tf} ---")
        base_rows, base_trades = _universe(STRATEGIES["SHARK-01"], tf, positioning=False)
        all_rows += base_rows
        for recipe in POSITIONING_STRATEGIES.values():
            rows, trades = _universe(recipe, tf, positioning=True)
            all_rows += rows
            if not trades:
                _log(f"           {recipe.name:<26} no trades")
                continue
            f = pd.DataFrame(rows)
            oos = f[f["split"] == "oos"]
            t = pd.concat(trades, ignore_index=True)
            p = minimum_detectable_effect(t)
            power_rows.append({
                "timeframe": tf, "strategy": recipe.name,
                "trades_all_splits": p["n_nominal"],
                "expectancy_r": float(t["r_net"].mean()),
                "min_detectable_r": p["min_detectable_effect_r"],
                "detectable": p["detectable"],
            })
            _log(f"           {recipe.name:<26} OOS n={int(oos['total_trades'].sum()):>5}  "
                 f"exp={oos['expectancy_r'].mean():+.4f}R  "
                 f"gross={oos['expectancy_r_gross'].mean():+.4f}R  "
                 f"hit={oos['hit_rate_r'].mean():.1%}  "
                 f"detectable={p['detectable']}")

    # Control for the control: what does SHARK-01 look like on the same axes,
    # per timeframe.  Never blend timeframes here -- the two regimes differ by
    # an order of magnitude in cost and nothing about them is comparable.
    for tf in ("4h", "5m"):
        base = [r for r in all_rows
                if r["strategy"] == "SHARK-01" and r["split"] == "oos"
                and r["timeframe"] == tf]
        f = pd.DataFrame(base)
        _log(f"  {tf}  {'SHARK-01 (control)':<26} OOS n={int(f['total_trades'].sum()):>5}  "
             f"exp={f['expectancy_r'].mean():+.4f}R  "
             f"gross={f['expectancy_r_gross'].mean():+.4f}R  "
             f"hit={f['hit_rate_r'].mean():.1%}")

    # Raw forward returns conditioned on the positioning signal, before any
    # trading rule -- the cheapest possible test of whether it carries anything.
    for tf in ("4h",):
        for name, recipe in POSITIONING_STRATEGIES.items():
            rows = []
            for sym in C.UNIVERSE:
                df = get_dataset(sym, tf).frame
                sig = positioning_signal(df, recipe)
                for bars, minutes in ((3, 12), (6, 24), (18, 72)):
                    col = f"fwd_ret_{bars}"
                    if col not in df.columns:
                        continue
                    r = df.loc[sig.to_numpy(), col].dropna()
                    r0 = df.loc[~sig.to_numpy(), col].dropna()
                    if r.empty or r0.empty:
                        continue
                    rows.append({
                        "timeframe": tf, "signal": name, "horizon_min": minutes,
                        "n_when": len(r), "n_other": len(r0),
                        "mean_when": float(r.mean()), "mean_other": float(r0.mean()),
                        "spread": float(r.mean() - r0.mean()),
                    })
            if rows:
                sig_rows += rows

    frame = pd.DataFrame(all_rows)
    write_frame(frame, "phase7_positioning_results")
    if power_rows:
        write_frame(pd.DataFrame(power_rows), "phase7_positioning_power")
    if sig_rows:
        s = pd.DataFrame(sig_rows)
        agg = (s.groupby(["signal", "horizon_min"])
               .apply(lambda g: pd.Series({
                   "n_when": int(g["n_when"].sum()),
                   "n_other": int(g["n_other"].sum()),
                   "mean_when": float(np.average(g["mean_when"], weights=g["n_when"])),
                   "mean_other": float(np.average(g["mean_other"], weights=g["n_other"])),
               }), include_groups=False).reset_index())
        agg["spread"] = agg["mean_when"] - agg["mean_other"]
        write_frame(agg, "phase7_positioning_forward_returns")
        _log("\n--- forward returns conditioned on the positioning signal (4h) ---")
        for _, r in agg.iterrows():
            _log(f"   {r['signal']:<26} {int(r['horizon_min']):>3}h  "
                 f"when-signal {r['mean_when']:+.5f}  "
                 f"otherwise {r['mean_other']:+.5f}  spread {r['spread']:+.5f}")

    oos = (frame[frame["split"] == "oos"]
           .groupby(["timeframe", "strategy"])
           .agg(trades=("total_trades", "sum"), expectancy_r=("expectancy_r", "mean"),
                gross_r=("expectancy_r_gross", "mean"),
                hit=("hit_rate_r", "mean")).reset_index())
    write_frame(oos, "phase7_positioning_oos_summary")
    print("\n--- OOS summary by timeframe ---")
    for tf in ("4h", "5m"):
        sub = oos[oos["timeframe"] == tf]
        if sub.empty:
            continue
        print(f"  {tf}")
        for _, r in sub.iterrows():
            print(f"    {r['strategy']:<26} n={int(r['trades']):>6}  "
                  f"exp={r['expectancy_r']:+.4f}R  gross={r['gross_r']:+.4f}R  "
                  f"hit={r['hit']:.1%}")

    write_manifest({
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"), "git_commit": git_commit(),
        "note": ("Top-trader long/short ratio, global long/short account ratio "
                 "and taker buy/sell volume ratio were downloaded from the "
                 "Binance metrics archive in phase 1 and never used by any "
                 "strategy until this phase."),
        "oos": oos.to_dict("records"),
    }, "manifest_phase7.json")
    print(f"\nelapsed {time.time() - t0:.1f}s -> {C.RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
