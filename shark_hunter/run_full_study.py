"""Full study: SHARK-01..08 + baselines, ablation, walk-forward and the
statistical battery, writing every machine-readable artefact the spec asks for.

    python -m shark_hunter.run_full_study

Outputs land in ``shark_results/`` as CSV plus one JSON manifest, and
``reporting/report.py`` renders them into REPORT.md.
"""

from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from . import config as C
from .analysis import costs as cost_analysis
from .analysis import forward_returns as fr
from .backtest.engine import run_backtest
from .backtest.costs import CostModel
from .data.loader import build_dataset
from .reporting.metrics import aggregate_by, compute_metrics, classify
from .runner import (get_dataset, git_commit, run_recipe, run_recipe_universe,
                     slice_result, write_frame, write_manifest, write_trades)
from .strategies.recipes import (ALL_RECIPES, BASELINES, STRATEGIES,
                                 ablation_variants, build_spec,
                                 unavailable_dependencies)
from .validation import monte_carlo as mc
from .validation import statistics as stats_mod
from .validation import walk_forward as wf

SPLITS = ("train", "validation", "oos", "final_unseen")
# Total configurations evaluated.  The DSR is deflated by this number, so it
# must be counted honestly: strategies x symbols x exits x parameter grid.
N_TRIALS_DECLARED = 8 * 9 * 4 * 4 * 3 * 4      # strategies, symbols, exits, RVOL, TP, ATR


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# --------------------------------------------------------------------------
# 1. data + cost feasibility
# --------------------------------------------------------------------------

def stage_data_and_costs() -> dict:
    _log("stage 1/7  data integrity + cost feasibility")
    frames, integrity = {}, []
    for sym in C.UNIVERSE:
        ds = get_dataset(sym)
        frames[sym] = ds.frame
        rep = ds.integrity.to_dict()
        rep["symbol"] = sym
        integrity.append(rep)
    write_frame(pd.DataFrame(integrity), "data_integrity")

    profile = cost_analysis.stop_width_profile(frames[C.PRIMARY_SYMBOL])
    write_frame(profile, "cost_feasibility_by_stop_multiple")

    symbols = cost_analysis.symbol_cost_table(frames)
    write_frame(symbols, "cost_feasibility_by_symbol")

    blocked = sorted({d for sym in C.UNIVERSE for d in get_dataset(sym).unavailable})
    _log(f"           universe={len(C.UNIVERSE)}  bars={len(frames[C.PRIMARY_SYMBOL]):,}")
    _log(f"           median 1-ATR stop as % price = "
         f"{float(symbols['stop_pct_1atr'].median()) * 100:.4f}%")
    _log(f"           round trip = {C.ROUND_TRIP_COST * 1e4:.1f} bps")
    return {"integrity": integrity, "cost_profile": profile.to_dict("records"),
            "cost_symbols": symbols.to_dict("records"), "unavailable": blocked}


# --------------------------------------------------------------------------
# 2. all strategies across the universe
# --------------------------------------------------------------------------

def stage_strategies() -> tuple[pd.DataFrame, dict, dict]:
    _log("stage 2/7  SHARK-01..08 + baselines across the universe")
    rows, blocked_map, rseries = [], {}, {}
    trade_frames_by_recipe: dict[str, list[pd.DataFrame]] = {}

    for name, recipe in list(STRATEGIES.items()) + list(BASELINES.items()):
        t0 = time.time()
        frame, verdicts, blocked, trades = run_recipe_universe(recipe, splits=SPLITS)
        blocked_map[name] = blocked
        if not frame.empty:
            rows.append(frame.assign(recipe=name))
        # Per-trade R series over the whole study, pooled across symbols, for
        # the Monte Carlo / DSR / Reality Check panel.  Reuses the same runs.
        if trades:
            trade_frames_by_recipe[name] = trades
            allt = pd.concat(trades, ignore_index=True)
            rseries[name] = allt.groupby("exit_time")["r_net"].sum()
        _log(f"           {name:<22} {len(frame):>4} rows  {time.time() - t0:5.1f}s"
             f"{'  BLOCKED:' + ','.join(blocked) if blocked else ''}")

    metrics = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    write_frame(metrics, "strategy_summary")
    return metrics, blocked_map, rseries, trade_frames_by_recipe


# --------------------------------------------------------------------------
# 3. signal quality, before stops and targets
# --------------------------------------------------------------------------

def stage_signal_quality() -> dict:
    _log("stage 3/7  signal quality (forward returns, buckets, price x OI)")
    out = {}
    tables = []
    for sym in C.UNIVERSE:
        df = get_dataset(sym).frame
        rvol_spike = (df["rvol"] >= 2.0).fillna(False)
        brk_long = (df["close"] > df["prev_high"]).fillna(False)
        brk_short = (df["close"] < df["prev_low"]).fillna(False)
        for label, mask in (("rvol>=2", rvol_spike),
                           ("breakout_long", brk_long),
                           ("breakout_short", brk_short),
                           ("rvol>=2 & breakout", rvol_spike & (brk_long | brk_short))):
            t = fr.forward_return_table(df, mask, label)
            if not t.empty:
                t["symbol"] = sym
                tables.append(t)
    if tables:
        f = pd.concat(tables, ignore_index=True)
        write_frame(f, "signal_quality_forward_returns")
        out["mean_by_horizon"] = (f.groupby(["signal", "horizon_min"])["mean"]
                                  .mean().reset_index().to_dict("records"))

    # Bucket analysis on the primary symbol.
    df = get_dataset(C.PRIMARY_SYMBOL).frame
    buckets = []
    for col, label in (("rvol", "rvol"), ("cvd_delta_5", "cvd_delta_5"),
                       ("oi_change_3", "oi_change_3"), ("atr_pct", "atr_pct")):
        if col in df.columns:
            b = fr.bucket_table(df, col, label=label)
            if not b.empty:
                buckets.append(b)
    if buckets:
        write_frame(pd.concat(buckets, ignore_index=True), "signal_buckets")

    quad = fr.price_oi_matrix(df)
    if not quad.empty:
        quad["symbol"] = C.PRIMARY_SYMBOL
        write_frame(quad, "price_oi_quadrant")
        out["price_oi_quadrant"] = quad.to_dict("records")

    liq = fr.liquidation_states(df)
    if not liq.empty:
        write_frame(liq, "liquidation_states")
        out["liquidation_states"] = liq.to_dict("records")

    score = fr.participation_score(df)
    if score.notna().any():
        q = pd.qcut(score, 5, labels=["low", "med-low", "med", "med-high", "high"])
        tab = (df.groupby(q, observed=False)["fwd_ret_12"]
               .agg(["count", "mean", "median"]).reset_index())
        tab.columns = ["participation_quintile", "count", "mean_fwd", "median_fwd"]
        write_frame(tab, "participation_score_vs_forward_return")
        out["participation_score"] = tab.to_dict("records")
    return out


# --------------------------------------------------------------------------
# 4. ablation
# --------------------------------------------------------------------------

def stage_ablation() -> pd.DataFrame:
    _log("stage 4/7  ablation (spec 37)")
    rows = []
    for name in ("SHARK-06", "SHARK-08"):
        for leg, recipe in ablation_variants(name):
            frame, _, blocked, _ = run_recipe_universe(recipe, splits=("train", "oos"))
            if not frame.empty:
                sub = frame[frame["split"] == "oos"]
                rows.append({"strategy": name, "removed_leg": leg,
                             "blocked": bool(blocked),
                             "total_trades": int(sub["total_trades"].sum()),
                             "expectancy_r": float(sub["expectancy_r"].mean()),
                             "profit_factor_r": float(sub["profit_factor_r"].mean()),
                             "hit_rate_r": float(sub["hit_rate_r"].mean())})
    # Full-vs-full references
    for name in ("SHARK-06", "SHARK-08"):
        frame, _, _, _ = run_recipe_universe(STRATEGIES[name], splits=("oos",))
        if not frame.empty:
            rows.append({"strategy": name, "removed_leg": "(none: full)",
                         "blocked": False,
                         "total_trades": int(frame["total_trades"].sum()),
                         "expectancy_r": float(frame["expectancy_r"].mean()),
                         "profit_factor_r": float(frame["profit_factor_r"].mean()),
                         "hit_rate_r": float(frame["hit_rate_r"].mean())})
    ab = pd.DataFrame(rows)
    if not ab.empty:
        write_frame(ab, "ablation_results")
    return ab


def stage_parameters() -> pd.DataFrame:
    """Spec 38 parameter grid, one factor at a time.

    A full 4x3x4x3 grid is 144 configurations and would be an invitation to
    pick the best cell, which is exactly the multiple-testing problem the spec
    is trying to avoid.  One-at-a-time around the pre-registered default shows
    whether the conclusion is a knife-edge or a plateau, at a fourteenth of
    the search pressure.
    """
    _log("stage 4b/7  parameter grid (one factor at a time)")
    grid = {
        "rvol_threshold": [1.5, 2.0, 2.5, 3.0],
        "breakout_period": [10, 20, 40],
        "atr_stop": [0.75, 1.0, 1.5, 2.0],
        "r_multiple": [1.5, 2.0, 3.0],
    }
    default = {"rvol_threshold": 2.0, "breakout_period": 20,
               "atr_stop": C.DEFAULT_ATR_STOP, "r_multiple": C.DEFAULT_R_MULTIPLE}
    rows = []
    recipe = STRATEGIES["SHARK-01"]
    for factor, values in grid.items():
        for v in values:
            kw = {factor: v}
            frame, _, blocked, _ = run_recipe_universe(
                recipe, splits=("oos",), **kw)
            if frame.empty or blocked:
                continue
            rows.append({
                "factor": factor, "value": v,
                "is_default": v == default[factor],
                "total_trades": int(frame["total_trades"].sum()),
                "expectancy_r": float(frame["expectancy_r"].mean()),
                "expectancy_r_gross": float(frame["expectancy_r_gross"].mean()),
                "cost_per_trade_r": float(frame["cost_per_trade_r"].mean()),
                "hit_rate_r": float(frame["hit_rate_r"].mean()),
                "profit_factor_r": float(frame["profit_factor_r"].mean()),
            })
        _log(f"           {factor:<18} swept {len(values)} values")
    out = pd.DataFrame(rows)
    write_frame(out, "parameter_results")
    return out


def stage_trade_log(rseries_frames: dict[str, list[pd.DataFrame]]) -> None:
    """Spec 53/58: every trade, with the reason it was taken."""
    _log("stage 4c/7  trade log")
    frames = [t for lst in rseries_frames.values() for t in lst]
    if not frames:
        return
    allt = pd.concat(frames, ignore_index=True)
    path = C.RESULTS_DIR / "trade_log.csv.gz"
    allt.to_csv(path, index=False, compression="gzip")
    _log(f"           {len(allt):,} trades -> {path.name}")


# --------------------------------------------------------------------------
# 5. walk-forward
# --------------------------------------------------------------------------

def stage_walk_forward() -> pd.DataFrame:
    _log("stage 5/7  walk-forward (6-month train, 3-month step)")
    # Backtest each symbol ONCE over the full history, then slice per window.
    # Re-running the engine per window would take ~45 minutes and change
    # nothing: the signal and fills inside a window do not depend on which
    # window is being scored.
    full: dict[str, object] = {}
    for sym in C.UNIVERSE:
        df = get_dataset(sym).frame
        spec = build_spec(df, STRATEGIES["SHARK-01"])
        full[sym] = run_backtest(df, spec, symbol=sym, costs=CostModel.for_symbol(sym))

    def evaluate(tr_s, tr_e, oos_s, oos_e):
        rows = []
        for sym, res in full.items():
            sub = slice_result(res, oos_s, oos_e, 10_000.0)
            m = compute_metrics(sub)
            rows.append({k: m[k] for k in ("expectancy_r", "profit_factor_r",
                                           "hit_rate_r", "total_trades")})
        if not rows:
            return None
        f = pd.DataFrame(rows)
        return {"symbols": len(rows),
                "total_trades": int(f["total_trades"].sum()),
                "expectancy_r": float(f["expectancy_r"].mean()),
                "profit_factor_r": float(f["profit_factor_r"].replace(np.inf, np.nan).mean()),
                "hit_rate_r": float(f["hit_rate_r"].mean()),
                "positive_symbol_fraction": float((f["expectancy_r"] > 0).mean())}

    w = wf.walk_forward(evaluate, window_months=6, step_months=3)
    if not w.empty:
        write_frame(w, "walk_forward_results")
    return w


# --------------------------------------------------------------------------
# 6. statistical battery
# --------------------------------------------------------------------------

def stage_statistics(rseries: dict, metrics: pd.DataFrame) -> dict:
    _log("stage 6/7  Monte Carlo, DSR, White Reality Check, SPA")
    out = {}

    mc_rows = []
    for name, series in rseries.items():
        if series is None or len(series) < 10:
            continue
        trades = pd.DataFrame({"r_net": series.to_numpy()})
        r = mc.monte_carlo(trades, n_simulations=10_000)
        r["strategy"] = name
        mc_rows.append(r)
    if mc_rows:
        f = pd.DataFrame(mc_rows)
        write_frame(f, "monte_carlo_results")
        out["monte_carlo"] = f.set_index("strategy").to_dict("index")

    dsr_rows = []
    for name, series in rseries.items():
        if series is None or len(series) < 30:
            continue
        # Trade exits are irregularly spaced, so the annualisation factor is
        # supplied explicitly from the actual trade frequency over the study.
        span_days = max((series.index.max() - series.index.min()).total_seconds() / 86400.0, 1.0)
        trades_per_year = len(series) / (span_days / 365.25)
        d = stats_mod.deflated_sharpe(series, trials=N_TRIALS_DECLARED,
                                      periods_per_year=trades_per_year)
        d["strategy"] = name
        dsr_rows.append(d)
    if dsr_rows:
        f = pd.DataFrame(dsr_rows)
        write_frame(f, "dsr_results")
        out["dsr"] = f.set_index("strategy").to_dict("index")

    panel = {k: v for k, v in rseries.items() if v is not None and len(v) > 30}
    if len(panel) >= 2:
        # Daily-compounded R returns: the standard basis for a Reality Check,
        # and tractable -- bootstrapping over 60k intraday bars per strategy
        # would allocate gigabytes on every iteration.
        daily = {k: v.resample("1D").sum() for k, v in panel.items()}
        common = None
        for s in daily.values():
            common = s.index if common is None else common.intersection(s.index)
        if common is not None and len(common) > 60:
            daily = {k: s.reindex(common).fillna(0.0) for k, s in daily.items()}
            rc = stats_mod.reality_check(daily, n_bootstrap=5_000)
            spa = stats_mod.spa_test(daily, n_bootstrap=5_000)
            write_frame(pd.DataFrame([
                {"test": "white_reality_check", **{k: str(v) for k, v in rc.items()}},
                {"test": "hansen_spa", **{k: str(v) for k, v in spa.items()}},
            ]), "reality_check_results")
            out["reality_check"] = rc
            out["spa"] = spa
        else:
            out["reality_check"] = {"note": "insufficient overlapping daily observations"}
    return out


# --------------------------------------------------------------------------
# 7. classification
# --------------------------------------------------------------------------

def stage_classification(metrics: pd.DataFrame, blocked_map: dict) -> dict:
    _log("stage 7/7  classification")
    verdicts = {}
    for name in list(STRATEGIES) + list(BASELINES):
        sub = metrics[metrics["strategy"] == name] if not metrics.empty else pd.DataFrame()
        if sub.empty:
            verdicts[name] = {"label": "BLOCKED" if blocked_map.get(name)
                              else "NO_DATA",
                              "reason": f"data unavailable: {blocked_map.get(name)}"
                              if blocked_map.get(name) else "no results"}
            continue
        for split in SPLITS:
            rows = sub[sub["split"] == split].to_dict("records")
            if rows:
                verdicts[f"{name}|{split}"] = classify(rows)
    return verdicts


# --------------------------------------------------------------------------

def main() -> int:
    t0 = time.time()
    print("=" * 78)
    print("SHARK HUNTER -- FULL STUDY")
    print("=" * 78)

    data_info = stage_data_and_costs()
    metrics, blocked_map, rseries, trade_frames_by_recipe = stage_strategies()
    signal = stage_signal_quality()
    ablation = stage_ablation()
    stage_trade_log(trade_frames_by_recipe)
    params = stage_parameters()
    walk = stage_walk_forward()
    stat = stage_statistics(rseries, metrics)
    verdicts = stage_classification(metrics, blocked_map)

    manifest = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "git_commit": git_commit(),
        "config": C.describe(),
        "declared_trials_for_dsr": N_TRIALS_DECLARED,
        "data": {k: v for k, v in data_info.items() if k != "integrity"},
        "data_integrity_ok": all(r["ok"] for r in data_info["integrity"]),
        "blocked_strategies": {k: v for k, v in blocked_map.items() if v},
        "signal_quality": signal,
        "statistics": stat,
        "verdicts": verdicts,
        "elapsed_seconds": time.time() - t0,
    }
    write_manifest(manifest)
    print(f"\ntotal elapsed {time.time() - t0:.1f}s -> {C.RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
