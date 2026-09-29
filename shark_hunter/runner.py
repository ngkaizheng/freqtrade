"""Experiment runner: orchestrates dataset building, backtests, split slicing
and result persistence.

Two design decisions worth stating, because both change the numbers:

1.  **One backtest run per (symbol, strategy) over the full history**, then
    metrics are computed per split from the trades whose *entry* falls in the
    split window.  Re-running the engine per split would restart capital and
    drop positions that were open across a boundary.  A position opened in
    December 2023 and closed in January 2024 is a real trade, and the spec
    asks for a chronological split of the *sample*, not of the account.

2.  **Features are always built on the full history** and only then sliced,
    because CVD and daily VWAP are cumulative (see ``features/__init__``).
"""

from __future__ import annotations

import datetime as dt
import json
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C
from .backtest.costs import CostModel
from .backtest.engine import BacktestResult, run_backtest
from .data.loader import Dataset, build_dataset
from .reporting.metrics import classify, compute_metrics
from .strategies.recipes import StrategyRecipe, build_spec, unavailable_dependencies

_DATASET_CACHE: dict[tuple, Dataset] = {}


# --------------------------------------------------------------------------
# dataset cache
# --------------------------------------------------------------------------

def get_dataset(symbol: str, timeframe: str = C.PRIMARY_TIMEFRAME) -> Dataset:
    key = (symbol, timeframe)
    if key not in _DATASET_CACHE:
        _DATASET_CACHE[key] = build_dataset(symbol, timeframe)
    return _DATASET_CACHE[key]


def clear_cache() -> None:
    _DATASET_CACHE.clear()


# --------------------------------------------------------------------------
# split slicing
# --------------------------------------------------------------------------

def slice_result(result: BacktestResult, start: dt.datetime, end: dt.datetime,
                 initial_equity: float) -> BacktestResult:
    """Restrict a full-history result to one chronological window."""
    trades = result.trades
    if not trades.empty:
        t = trades[(trades["entry_time"] >= start) & (trades["entry_time"] < end)]
    else:
        t = trades

    eq = result.equity.loc[(result.equity.index >= start) & (result.equity.index < end)]
    prior = result.equity.loc[result.equity.index < start]
    base = float(prior.iloc[-1]) if len(prior) else initial_equity
    if len(eq):
        # Rebase so the window opens at the equity actually held at `start`.
        eq = eq - (base - initial_equity)
    else:
        eq = pd.Series([initial_equity], index=[start], name="equity")

    return BacktestResult(
        trades=t.reset_index(drop=True), equity=eq, symbol=result.symbol,
        timeframe=result.timeframe, strategy=result.strategy,
        params=result.params, costs=result.costs,
        initial_equity=initial_equity, meta=result.meta)


# --------------------------------------------------------------------------
# single strategy execution
# --------------------------------------------------------------------------

@dataclass
class RunOutcome:
    strategy: str
    symbol: str
    timeframe: str
    status: str                 # ok | blocked
    blocked_by: list[str]
    metrics_by_split: dict[str, list[dict]]   # split -> per-symbol metrics rows
    results: dict[str, BacktestResult]
    recipe: StrategyRecipe
    params: dict

    def all_rows(self) -> pd.DataFrame:
        frames = []
        for split, rows in self.metrics_by_split.items():
            for r in rows:
                frames.append({**r, "split": split})
        return pd.DataFrame(frames)


def run_recipe(recipe: StrategyRecipe, symbol: str, *,
               timeframe: str = C.PRIMARY_TIMEFRAME,
               atr_stop: float = C.DEFAULT_ATR_STOP,
               r_multiple: float = C.DEFAULT_R_MULTIPLE,
               time_stop_bars: int | None = None,
               cooldown_bars: int = C.DEFAULT_COOLDOWN_BARS,
               trailing_atr: float | None = None,
               rvol_threshold: float = -1.0,
               oi_lag: int | None = None,
               breakout_period: int | None = None,
               splits: tuple[str, ...] | None = None,
               initial_equity: float = 10_000.0) -> RunOutcome:
    ds = get_dataset(symbol, timeframe)
    df = ds.frame
    # A breakout-period sweep needs its own prev_high/prev_low; the cached
    # feature block was built once at the default period.
    if breakout_period is not None:
        from . import features as _features
        df = _features.add_breakout(df, period=breakout_period)

    blocked = unavailable_dependencies(df, recipe)
    params = {"atr_stop": atr_stop, "r_multiple": r_multiple,
              "cooldown_bars": cooldown_bars, "trailing_atr": trailing_atr,
              "rvol_threshold": rvol_threshold, "oi_lag": oi_lag,
              "breakout_period": breakout_period or recipe.breakout_period,
              "time_stop_bars": time_stop_bars or C.DEFAULT_TIME_STOP_BARS[timeframe]}
    if blocked:
        return RunOutcome(recipe.name, symbol, timeframe, "blocked", blocked,
                          {}, {}, recipe, params)

    spec = build_spec(df, recipe, atr_stop=atr_stop, r_multiple=r_multiple,
                      time_stop_bars=params["time_stop_bars"],
                      cooldown_bars=cooldown_bars, trailing_atr=trailing_atr,
                      rvol_threshold=rvol_threshold, oi_lag=oi_lag)
    spec.name = recipe.name
    if breakout_period is not None:
        from dataclasses import replace as _replace
        spec = _replace(spec, name=f"{recipe.name}-bo{breakout_period}")
    costs = CostModel.for_symbol(symbol)
    res = run_backtest(df, spec, symbol=symbol, timeframe=timeframe,
                       costs=costs, initial_equity=initial_equity)

    wanted = splits or tuple(s.name for s in C.SPLITS)
    by_split: dict[str, list[dict]] = {}
    results: dict[str, BacktestResult] = {}
    for s in C.SPLITS:
        if s.name not in wanted:
            continue
        sub = slice_result(res, s.start, s.end, initial_equity)
        results[s.name] = sub
        by_split[s.name] = [compute_metrics(sub)]
    # The unsliced run, for callers that need a continuous series across the
    # whole study (Monte Carlo, DSR, the Reality Check panel).
    results["__full__"] = res

    return RunOutcome(recipe.name, symbol, timeframe, "ok", [], by_split, results,
                      recipe, params)


# --------------------------------------------------------------------------
# universe execution
# --------------------------------------------------------------------------

def run_recipe_universe(recipe: StrategyRecipe, *,
                        symbols: tuple[str, ...] = C.UNIVERSE,
                        timeframe: str = C.PRIMARY_TIMEFRAME,
                        splits: tuple[str, ...] | None = None,
                        **kw) -> tuple[pd.DataFrame, dict[str, dict], list[str], list[pd.DataFrame]]:
    """Run one recipe across the whole universe.

    Returns ``(metrics_frame, classification_by_split, blocked_symbols,
    full_trade_frames)``.  The trade frames come from the same backtest runs
    that produced the metrics -- nothing is re-run -- so callers that need a
    continuous per-trade series (Monte Carlo, DSR, Reality Check) do not pay
    for a second pass.
    """
    rows: list[dict] = []
    blocked: list[str] = []
    trade_frames: list[pd.DataFrame] = []
    for sym in symbols:
        out = run_recipe(recipe, sym, timeframe=timeframe, splits=splits, **kw)
        if out.status == "blocked":
            blocked.append(sym)
            continue
        for split, rs in out.metrics_by_split.items():
            for r in rs:
                rows.append({**r, "split": split, "status": out.status,
                             "blocked_by": ";".join(out.blocked_by)})
        tr = out.results["__full__"].trades
        if not tr.empty:
            trade_frames.append(tr)
    frame = pd.DataFrame(rows)
    verdicts: dict[str, dict] = {}
    if not frame.empty and splits:
        for split in splits:
            sub = frame[frame["split"] == split]
            if not sub.empty:
                verdicts[split] = classify(sub.to_dict("records"))
    return frame, verdicts, blocked, trade_frames


# --------------------------------------------------------------------------
# persistence (spec 56, 57, 58)
# --------------------------------------------------------------------------

def experiment_id(prefix: str = "shark") -> str:
    return f"{prefix}-{time.strftime('%Y%m%d-%H%M%S')}"


def git_commit() -> str:
    import subprocess
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             cwd=str(C.ROOT), capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "unknown"
    except Exception:                       # noqa: BLE001
        return "unknown"


def write_frame(df: pd.DataFrame, name: str, directory: Path = C.RESULTS_DIR) -> Path:
    path = directory / f"{name}.csv"
    df.to_csv(path, index=False)
    return path


def write_trades(trades: pd.DataFrame, name: str) -> Path:
    path = C.TRADES_DIR / f"{name}.csv"
    trades.to_csv(path, index=False)
    return path


def write_manifest(payload: dict, name: str = "manifest.json") -> Path:
    path = C.RESULTS_DIR / name
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path
