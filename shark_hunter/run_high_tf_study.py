"""Phase 2: does the signal become monetisable where friction stops dominating?

    python -m shark_hunter.run_high_tf_study

The 5m study failed for a structural reason, not a signal reason: a 1-ATR
stop on a 5m crypto bar is comparable in width to a round-trip commission, so
friction consumed most of the amount at risk.  This asks the follow-up the
5m result actually implies: **in a regime where friction is small, is there
anything underneath?**

The primary deliverable is the **friction frontier** -- expectancy plotted
against stop width, for every strategy.  It is reported as a curve and never
as a selected point.  Picking the best stop width after seeing the frontier is
the multiple-testing error this whole study exists to avoid, and the DSR is
deflated for exactly that.

The candidate that matters is SHARK-05: at 5m it was the only variant that
lifted the *gross* hit rate above the 33.3% a 1R/2R bracket needs to break
even (32.4% -> 33.4%).  Whether that converts into net expectancy is the
question this run exists to answer.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd

from . import config as C
from .analysis import costs as cost_analysis
from .backtest.costs import CostModel
from .backtest.engine import run_backtest
from .reporting.metrics import classify, compute_metrics
from .runner import get_dataset, git_commit, slice_result, write_frame, write_manifest
from .strategies.recipes import BASELINES, STRATEGIES, build_spec
from .validation import monte_carlo as mc
from .validation import statistics as stats_mod
from .validation import walk_forward as wf

SPLITS = ("train", "validation", "oos", "final_unseen")
TIMEFRAMES = ("1h", "4h")
# 5m x 9 symbols x exits x parameter grid, now plus the two extra timeframes
# explored here.  Inflating this is the correct response to having widened the
# search, and it makes the DSR harder, not easier, to pass.
N_TRIALS_DECLARED = 8 * 9 * 4 * 4 * 3 * 4 * 3      # ... x 3 timeframes
STOP_GRID = (0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0)


def _log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def stage_cost() -> dict:
    _log("stage 1/5  cost feasibility at higher resolutions")
    out = {}
    for tf in TIMEFRAMES:
        frames = {s: get_dataset(s, tf).frame for s in C.UNIVERSE}
        tab = cost_analysis.symbol_cost_table(frames)
        tab["timeframe"] = tf
        out[tf] = tab
        _log(f"           {tf}: median cost_in_r = "
             f"{tab['cost_in_r_1atr'].median():.3f}R "
             f"(5m reference: ~0.62R)")
    full = pd.concat(out.values(), ignore_index=True)
    write_frame(full, "phase2_cost_by_timeframe")
    return {tf: t.to_dict("records") for tf, t in out.items()}


def stage_ladder(timeframe: str, per_symbol: bool = False) -> tuple[pd.DataFrame, dict]:
    """Full strategy ladder at one timeframe, on out-of-sample data."""
    _log(f"stage 2/5  strategy ladder at {timeframe}"
         + (" (per symbol)" if per_symbol else ""))
    rows = []
    per_symbol_rows: list[pd.DataFrame] = []
    for name, recipe in list(STRATEGIES.items()) + list(BASELINES.items()):
        recs, blocked = [], []
        for sym in C.UNIVERSE:
            df = get_dataset(sym, timeframe).frame
            out_spec = build_spec(df, recipe,
                                  time_stop_bars=C.DEFAULT_TIME_STOP_BARS[timeframe])
            res = run_backtest(df, out_spec, symbol=sym, timeframe=timeframe,
                               costs=CostModel.for_symbol(sym))
            if res.trades.empty:
                blocked.append(sym)
                continue
            for s in C.SPLITS:
                if s.name not in SPLITS or (per_symbol and s.name != "oos"):
                    continue
                sub = slice_result(res, s.start, s.end, 10_000.0)
                m = compute_metrics(sub)
                recs.append({"strategy": name, "symbol": sym, "split": s.name,
                             "avg_holding_bars": m.get("avg_holding_bars"),
                             **{k: m[k] for k in ("total_trades", "expectancy_r",
                                                   "expectancy_r_gross", "cost_per_trade_r",
                                                   "profit_factor_r", "hit_rate_r",
                                                   "r_sharpe", "r_max_drawdown")}})
        if not recs:
            _log(f"           {name:<22} BLOCKED ({len(blocked)} symbols)")
            continue
        f = pd.DataFrame(recs)
        if per_symbol:
            per_symbol_rows.append(f)
            continue
        oos = f[f["split"] == "oos"]
        rows.append({
            "timeframe": timeframe, "strategy": name, "n_symbols": len(set(f["symbol"])),
            "trades": int(oos["total_trades"].sum()),
            "expectancy_r": float(oos["expectancy_r"].mean()),
            "expectancy_r_gross": float(oos["expectancy_r_gross"].mean()),
            "cost_per_trade_r": float(oos["cost_per_trade_r"].mean()),
            "profit_factor_r": float(oos["profit_factor_r"].mean()),
            "hit_rate_r": float(oos["hit_rate_r"].mean()),
            "r_sharpe": float(oos["r_sharpe"].mean()),
            "positive_symbol_fraction": float((oos["expectancy_r"] > 0).mean()),
            "avg_holding_bars": float(oos["avg_holding_bars"].mean()),
        })
        _log(f"           {name:<22} trades={rows[-1]['trades']:>6}  "
             f"exp={rows[-1]['expectancy_r']:+.4f}R  gross={rows[-1]['expectancy_r_gross']:+.4f}R  "
             f"cost={rows[-1]['cost_per_trade_r']:.3f}R  hit={rows[-1]['hit_rate_r']:.1%}  "
             f"+sym={rows[-1]['positive_symbol_fraction']:.0%}")
    if per_symbol:
        return (pd.concat(per_symbol_rows, ignore_index=True) if per_symbol_rows
                else pd.DataFrame()), {}
    return pd.DataFrame(rows), {}


def stage_frontier(timeframe: str) -> pd.DataFrame:
    """Expectancy vs stop width -- the friction frontier, as a curve.

    Every point is a full re-run across the universe, so the curve is not an
    interpolation and not a single cherry-picked cell.
    """
    _log(f"stage 3/5  friction frontier at {timeframe}")
    rows = []
    for name in ("SHARK-01", "SHARK-02", "SHARK-05", "SHARK-06", "BASELINE-C-BREAKOUT"):
        recipe = STRATEGIES.get(name) or BASELINES[name]
        for mult in STOP_GRID:
            exp_r, gross_r, cost_r, hit, n = [], [], [], [], 0
            for sym in C.UNIVERSE:
                df = get_dataset(sym, timeframe).frame
                spec = build_spec(df, recipe, atr_stop=mult,
                                  time_stop_bars=C.DEFAULT_TIME_STOP_BARS[timeframe])
                res = run_backtest(df, spec, symbol=sym, timeframe=timeframe,
                                   costs=CostModel.for_symbol(sym))
                if res.trades.empty:
                    continue
                n += len(res.trades)
                for s in C.SPLITS:
                    if s.name != "oos":
                        continue
                    m = compute_metrics(slice_result(res, s.start, s.end, 10_000.0))
                    exp_r.append(m["expectancy_r"])
                    gross_r.append(m["expectancy_r_gross"])
                    cost_r.append(m["cost_per_trade_r"])
                    hit.append(m["hit_rate_r"])
            if not exp_r:
                continue
            rows.append({
                "timeframe": timeframe, "strategy": name, "atr_stop": mult,
                "trades": n,
                "expectancy_r": float(np.mean(exp_r)),
                "expectancy_r_gross": float(np.mean(gross_r)),
                "cost_per_trade_r": float(np.mean(cost_r)),
                "hit_rate_r": float(np.mean(hit)),
            })
        _log(f"           {name:<22} {len(STOP_GRID)} stop widths")
    out = pd.DataFrame(rows)
    # One file per timeframe: a shared name means the second call silently
    # overwrites the first and half the frontier disappears.
    write_frame(out, f"phase2_friction_frontier_{timeframe}")
    return out


def stage_validation(timeframe: str) -> dict:
    _log(f"stage 4/5  walk-forward / Monte Carlo / DSR at {timeframe}")
    res = {timeframe: {}}

    full = {}
    for sym in C.UNIVERSE:
        df = get_dataset(sym, timeframe).frame
        spec = build_spec(df, STRATEGIES["SHARK-01"],
                          time_stop_bars=C.DEFAULT_TIME_STOP_BARS[timeframe])
        full[sym] = run_backtest(df, spec, symbol=sym, timeframe=timeframe,
                                 costs=CostModel.for_symbol(sym))

    def evaluate(tr_s, tr_e, oos_s, oos_e):
        rows = []
        for r_ in full.values():
            m = compute_metrics(slice_result(r_, oos_s, oos_e, 10_000.0))
            rows.append({k: m[k] for k in ("expectancy_r", "hit_rate_r", "total_trades")})
        f = pd.DataFrame(rows)
        return {"symbols": len(rows), "total_trades": int(f["total_trades"].sum()),
                "expectancy_r": float(f["expectancy_r"].mean()),
                "hit_rate_r": float(f["hit_rate_r"].mean()),
                "positive_symbol_fraction": float((f["expectancy_r"] > 0).mean())}

    w = wf.walk_forward(evaluate, window_months=6, step_months=3)
    if not w.empty:
        write_frame(w.assign(timeframe=timeframe), f"phase2_walk_forward_{timeframe}")
        res[timeframe]["walk_forward_windows"] = len(w)
        res[timeframe]["walk_forward_positive_windows"] = int(w["expectancy_r"].gt(0).sum())

    # R-series panel for the statistical battery.
    series = []
    for sym, r_ in full.items():
        if not r_.trades.empty:
            series.append(r_.trades[["exit_time", "r_net"]])
    if series:
        s = pd.concat(series).groupby("exit_time")["r_net"].sum()
        trades = pd.DataFrame({"r_net": s.to_numpy()})
        mcr = mc.monte_carlo(trades, n_simulations=10_000)
        mcr["timeframe"] = timeframe
        write_frame(pd.DataFrame([mcr]), f"phase2_monte_carlo_{timeframe}")
        span = max((s.index.max() - s.index.min()).total_seconds() / 86400.0, 1.0)
        d = stats_mod.deflated_sharpe(s.to_numpy(), trials=N_TRIALS_DECLARED,
                                      periods_per_year=len(s) / (span / 365.25))
        d["timeframe"] = timeframe
        write_frame(pd.DataFrame([d]), f"phase2_dsr_{timeframe}")
        res[timeframe]["monte_carlo"] = mcr
        res[timeframe]["dsr"] = d
        _log(f"           {timeframe}: {len(s):,} trades, "
             f"DSR={d['dsr']:.4f}, P(expectancy<0)={mcr['prob_expectancy_negative']:.3f}")
    return res[timeframe]


def main() -> int:
    t0 = time.time()
    print("=" * 78)
    print("SHARK HUNTER -- PHASE 2: LOW-FRICTION REGIME")
    print("Testing whether the signal is real underneath the cost drag.")
    print("=" * 78)

    cost = stage_cost()
    ladders = []
    for tf in TIMEFRAMES:
        f, _ = stage_ladder(tf)
        if not f.empty:
            ladders.append(f)
    ladder = pd.concat(ladders, ignore_index=True) if ladders else pd.DataFrame()
    if not ladder.empty:
        write_frame(ladder, "phase2_strategy_ladder")

    # Per-symbol detail, so a portfolio average cannot hide a result carried
    # by one lucky symbol.
    if not ladder.empty:
        for tf in TIMEFRAMES:
            f, _ = stage_ladder(tf, per_symbol=True)
            if not f.empty:
                write_frame(f[f["split"] == "oos"],
                            f"phase2_per_symbol_{tf}")

    frontier = pd.concat([stage_frontier(tf) for tf in TIMEFRAMES],
                         ignore_index=True)

    validation = {tf: stage_validation(tf) for tf in TIMEFRAMES}

    manifest = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "git_commit": git_commit(),
        "config": C.describe(),
        "timeframes": list(TIMEFRAMES),
        "stop_grid": list(STOP_GRID),
        "declared_trials_for_dsr": N_TRIALS_DECLARED,
        "cost": cost,
        "validation": validation,
        "elapsed_seconds": time.time() - t0,
    }
    write_manifest(manifest, "manifest_phase2.json")
    print(f"\ntotal elapsed {time.time() - t0:.1f}s -> {C.RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
