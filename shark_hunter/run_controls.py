"""Phase 3: the controls.

    python -m shark_hunter.run_controls

Phase 2 produced a positive 4h result.  Before that can be called anything
except promising, two controls that were missing have to run:

1. **Buy and hold** (spec section 36, Baseline A).  Never implemented.  A
   +0.14R-per-trade strategy means nothing without knowing what simply
   holding the coin did over the same window.

2. **Time-series momentum** (Baseline E).  The single most likely confound.
   Baseline E is SHARK-01 with the breakout replaced by a momentum sign test
   and everything else held fixed -- same stop, same target, same costs, same
   sizing.  If it performs like SHARK-01, then the 4h "edge" is 4h momentum
   wearing a volume filter, and the headline claim that the volume filter adds
   +0.10R is an artifact of how the breakout baseline was built.

Plus an effective-sample-size and power analysis, because 464 nominal trades
that are sequential, regime-clustered and drawn from nine correlated
instruments are not 464 independent observations.

The prior against this being a real, tradeable effect is not good: the
canonical momentum result lives at a 1-12 month horizon (Moskowitz, Ooi and
Pedersen), volume-confirmed breakout is wall-to-wall documented (so
McLean-Pontiff post-publication decay applies), and a 4h horizon is three
orders of magnitude from anything established.  These controls are how that
prior gets tested rather than argued.
"""

from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from . import config as C
from .analysis.benchmarks import (buy_and_hold_table, effective_sample_size,
                                  minimum_detectable_effect)
from .backtest.costs import CostModel
from .backtest.engine import run_backtest
from .reporting.metrics import compute_metrics
from .runner import get_dataset, git_commit, slice_result, write_frame, write_manifest
from .strategies.recipes import BASELINES, STRATEGIES, build_spec

SPLITS = ("train", "validation", "oos", "final_unseen")
CONTROL_SETS = ("SHARK-01", "BASELINE-C-BREAKOUT", "BASELINE-D-RVOL",
                "BASELINE-E-TSM")


def _log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def run_control(timeframe: str) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    _log(f"control ladder at {timeframe}")
    rows, trade_store = [], {}
    for name in CONTROL_SETS:
        recipe = STRATEGIES.get(name) or BASELINES[name]
        recs, per_sym = [], {}
        for sym in C.UNIVERSE:
            df = get_dataset(sym, timeframe).frame
            spec = build_spec(df, recipe,
                              time_stop_bars=C.DEFAULT_TIME_STOP_BARS[timeframe])
            res = run_backtest(df, spec, symbol=sym, timeframe=timeframe,
                               costs=CostModel.for_symbol(sym))
            if res.trades.empty:
                continue
            per_sym[sym] = res.trades
            for s in C.SPLITS:
                m = compute_metrics(slice_result(res, s.start, s.end, 10_000.0))
                recs.append({"strategy": name, "symbol": sym, "split": s.name,
                             **{k: m[k] for k in ("total_trades", "expectancy_r",
                                                   "expectancy_r_gross",
                                                   "cost_per_trade_r", "hit_rate_r")}})
        if not recs:
            _log(f"           {name:<22} no trades")
            continue
        f = pd.DataFrame(recs)
        oos = f[f["split"] == "oos"]
        rows.append({
            "timeframe": timeframe, "strategy": name,
            "trades": int(oos["total_trades"].sum()),
            "expectancy_r": float(oos["expectancy_r"].mean()),
            "expectancy_r_gross": float(oos["expectancy_r_gross"].mean()),
            "cost_per_trade_r": float(oos["cost_per_trade_r"].mean()),
            "hit_rate_r": float(oos["hit_rate_r"].mean()),
            "positive_symbol_fraction": float((oos["expectancy_r"] > 0).mean()),
        })
        trade_store[name] = pd.concat(per_sym.values(), ignore_index=True)
        _log(f"           {name:<22} trades={rows[-1]['trades']:>6}  "
             f"exp={rows[-1]['expectancy_r']:+.4f}R  hit={rows[-1]['hit_rate_r']:.1%}  "
             f"+sym={rows[-1]['positive_symbol_fraction']:.0%}")
    return pd.DataFrame(rows), trade_store


def main() -> int:
    t0 = time.time()
    print("=" * 78)
    print("SHARK HUNTER -- PHASE 3: THE MISSING CONTROLS")
    print("=" * 78)

    out: dict = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"),
                 "git_commit": git_commit(), "timeframes": {}}

    all_rows, bnh_rows, power_rows, ess_rows = [], [], [], []
    for tf in ("1h", "4h"):
        _log(f"--- {tf} ---")

        # Baseline A: buy and hold.
        frames = {s: get_dataset(s, tf).frame for s in C.UNIVERSE}
        bnh = buy_and_hold_table(frames, tf)
        for split in [x.name for x in C.SPLITS]:
            s = next(x for x in C.SPLITS if x.name == split)
            for sym, df in frames.items():
                sub = df[(df.index >= s.start) & (df.index < s.end)]
                if sub.empty:
                    continue
                from .analysis.benchmarks import buy_and_hold
                b = buy_and_hold(sub, sym, tf)
                b["split"] = split
                bnh_rows.append(b)
        write_frame(pd.concat([bnh.assign(split="full")], ignore_index=True),
                    f"phase3_buyandhold_{tf}")
        b_all = pd.DataFrame(bnh_rows)
        b_all = b_all[b_all["timeframe"] == tf]
        b_oos = b_all[b_all["split"] == "oos"]
        _log(f"           buy&hold  OOS: median return="
             f"{b_oos['total_return'].median():+.1%}  median Sharpe="
             f"{b_oos['sharpe'].median():.2f}  worst DD="
             f"{b_oos['max_drawdown'].min():.1%}")

        rows, trades = run_control(tf)
        all_rows.append(rows)

        # Power / effective sample size on the headline strategy.
        for name, tr in trades.items():
            if tr.empty:
                continue
            e = effective_sample_size(tr)
            p = minimum_detectable_effect(tr)
            ess_rows.append({"timeframe": tf, "strategy": name,
                             "n_nominal": e["n_nominal"],
                             "n_effective": e["n_effective_newey_west"],
                             "inflation_factor": e["inflation_factor"],
                             "lag1_autocorr": e["lag1_autocorrelation"]})
            power_rows.append({"timeframe": tf, "strategy": name,
                               "observed_expectancy_r": p["observed_expectancy_r"],
                               "observed_t_stat": p["observed_t_stat"],
                               "min_detectable_effect_r": p["min_detectable_effect_r"],
                               "p_value": p["p_value"], "detectable": p["detectable"]})
            _log(f"           {name:<22} n={p['n_nominal']:>5} -> "
                 f"n_eff={p['n_effective_newey_west']:6.0f} "
                 f"(x{p['inflation_factor']:.1f})  t={p['observed_t_stat']:+.2f}  "
                 f"MDE={p['min_detectable_effect_r']:.4f}R  detectable={p['detectable']}")

        out["timeframes"][tf] = {
            "buy_and_hold_oos": b_oos.to_dict("records"),
            "controls": rows.to_dict("records"),
        }

    ladder = pd.concat(all_rows, ignore_index=True)
    write_frame(ladder, "phase3_control_ladder")
    write_frame(pd.DataFrame(ess_rows), "phase3_effective_sample_size")
    write_frame(pd.DataFrame(power_rows), "phase3_power_analysis")
    bnh_all = pd.DataFrame(bnh_rows)
    write_frame(bnh_all, "phase3_buy_and_hold_by_split")
    out["effective_sample_size"] = ess_rows
    out["power"] = power_rows
    write_manifest(out, "manifest_phase3.json")
    print(f"\ntotal elapsed {time.time() - t0:.1f}s -> {C.RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
