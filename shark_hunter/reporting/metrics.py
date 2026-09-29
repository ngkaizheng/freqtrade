"""Performance metrics (spec section 42) and the fixed classification rules
for FAILED / PROMISING / ROBUST (spec section 60).

The classification thresholds are constants defined *here*, before any result
is looked at.  Nothing downstream is allowed to move them.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..backtest.engine import BacktestResult
from ..config import ROUND_TRIP_COST

# --- bars per year, for annualising bar-frequency returns -------------------
BARS_PER_YEAR = {
    "1m": 525_600, "3m": 175_200, "5m": 105_120, "15m": 35_040,
    "1h": 8_760, "4h": 2_190,
}

# --- spec 60 decision thresholds, frozen ------------------------------------
MIN_TRADES = 30
PROMISING_MIN_PF = 1.0
PROMISING_MIN_WIN_RATE = 0.35
ROBUST_MIN_TRADES = 100
ROBUST_MAX_POSITIVE_FRACTION = 0.60      # at least 60% of symbols profitable
ROBUST_MIN_SHARPE = 0.75
ROBUST_MAX_DRAWDOWN = 0.35


def _safe(x, default=np.nan):
    return default if x is None or (isinstance(x, float) and not np.isfinite(x)) else x


def drawdown(equity: pd.Series) -> pd.Series:
    peak = equity.cummax()
    return equity / peak - 1.0


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    return float(drawdown(equity).min())


def _annual_factor(equity: pd.Series, timeframe: str) -> float:
    bars = BARS_PER_YEAR.get(timeframe, 105_120)
    return float(np.sqrt(bars))


def r_equity(trades: pd.DataFrame, initial_equity: float = 10_000.0,
             risk_fraction: float = 0.005) -> pd.Series:
    """Compounded equity from R multiples, stepped at trade exit.

    Absolute-PnL equity is unusable for comparing strategies here: a losing
    strategy drives cash equity toward zero, and once it does, position sizing
    shrinks with it and every later metric collapses toward zero -- which looks
    like "no trades" rather than "consistently losing".  The R curve is
    scale-free and keeps reporting the true edge per trade.

    This is a reporting curve, not a tradeable account: it assumes a constant
    fractional risk and ignores the leverage and liquidity caps of the cash
    simulation.
    """
    if trades.empty:
        return pd.Series([initial_equity], name="r_equity")
    eq, out = initial_equity, [initial_equity]
    for r in trades["r_net"].fillna(0.0).to_numpy():
        eq *= max(0.0, 1.0 + r * risk_fraction)
        out.append(eq)
    # n+1 points: the starting balance, then one per trade exit.
    start = pd.Timestamp(trades["entry_time"].iloc[0]) - pd.Timedelta(seconds=1)
    index = [start] + list(trades["exit_time"])
    return pd.Series(out, index=index, name="r_equity")


def compute_metrics(result: BacktestResult) -> dict:
    """Full metric set for one backtest result."""
    eq = result.equity.dropna()
    trades = result.trades
    init = result.initial_equity
    n_bars = max(len(eq) - 1, 1)

    m: dict = {
        "symbol": result.symbol, "timeframe": result.timeframe,
        "strategy": result.strategy,
        "start": str(eq.index.min()) if len(eq) else None,
        "end": str(eq.index.max()) if len(eq) else None,
        "bars": len(eq),
        "total_trades": int(len(trades)),
    }

    if eq.empty:
        return {**m, "total_return": 0.0, "max_drawdown": 0.0}

    final = float(eq.iloc[-1])
    m["final_equity"] = final
    m["total_return"] = final / init - 1.0

    # Annualisation by elapsed calendar time, not by bar count: a partial
    # study window must not be reported as a full year.
    elapsed_days = max((eq.index[-1] - eq.index[0]).total_seconds() / 86400.0, 1.0)
    years = elapsed_days / 365.25
    m["elapsed_years"] = years
    if years > 0 and final > 0:
        m["annualized_return"] = float((final / init) ** (1.0 / years) - 1.0)
    else:
        m["annualized_return"] = np.nan

    m["max_drawdown"] = max_drawdown(eq)

    # --- R-compounded view -------------------------------------------------
    # This is the primary reporting basis.  Cash equity spirals toward zero on
    # a losing strategy, after which every cash-based ratio is an artifact of
    # a dead account rather than a measure of the strategy.
    if not trades.empty:
        r_eq = r_equity(trades, initial_equity=init)
        m["r_final_equity"] = float(r_eq.iloc[-1])
        m["r_total_return"] = float(r_eq.iloc[-1]) / init - 1.0
        m["r_max_drawdown"] = max_drawdown(r_eq)
        r_rets = r_eq.pct_change().dropna()
        r_per_trade = trades["r_net"].dropna()
        # Per-trade annualisation: sqrt(trades per year) from the actual
        # trade frequency, which is the honest scaling for a trade-level edge.
        if len(r_rets) > 2 and r_rets.std() > 0:
            years = max(elapsed_days / 365.25, 1e-9)
            trades_per_year = len(trades) / years
            m["r_sharpe"] = float(r_per_trade.mean() / r_per_trade.std() * np.sqrt(trades_per_year)) \
                if len(r_per_trade) > 2 and r_per_trade.std() > 0 else 0.0
        else:
            m["r_sharpe"] = 0.0
        m["r_annualized_return"] = float((m["r_final_equity"] / init) ** (1.0 / max(elapsed_days / 365.25, 1e-9)) - 1.0) \
            if elapsed_days > 0 and m["r_final_equity"] > 0 else np.nan
        m["r_calmar"] = float(m["r_annualized_return"] / abs(m["r_max_drawdown"])) \
            if m["r_max_drawdown"] < 0 and np.isfinite(m["r_annualized_return"]) else 0.0
        stop_pct = (trades["atr"] * trades["atr_stop"]) / trades["entry_price"]
        m["median_stop_pct"] = float(stop_pct.median())
        m["cost_floor_violation_frac"] = float((stop_pct < ROUND_TRIP_COST).mean())
        m["cost_in_r_median"] = float((ROUND_TRIP_COST / stop_pct.replace(0.0, np.nan)).median())
    else:
        m.update({"r_final_equity": init, "r_total_return": 0.0, "r_max_drawdown": 0.0,
                  "r_sharpe": 0.0, "r_annualized_return": 0.0, "r_calmar": 0.0,
                  "median_stop_pct": np.nan, "cost_floor_violation_frac": np.nan,
                  "cost_in_r_median": np.nan})

    rets = eq.pct_change().dropna()
    ann = _annual_factor(eq, result.timeframe)
    if len(rets) > 2 and rets.std() > 0:
        m["sharpe"] = float(rets.mean() / rets.std() * ann)
    else:
        m["sharpe"] = 0.0
    downside = rets[rets < 0]
    dstd = downside.std() if len(downside) > 2 else np.nan
    m["sortino"] = float(rets.mean() / dstd * ann) if dstd and np.isfinite(dstd) and dstd > 0 else 0.0
    m["calmar"] = float(m["annualized_return"] / abs(m["max_drawdown"])) \
        if m["max_drawdown"] < 0 and np.isfinite(m["annualized_return"]) else 0.0

    # --- trade statistics -------------------------------------------------
    if trades.empty:
        m.update({"win_rate": np.nan, "expectancy": 0.0, "profit_factor": 0.0,
                  "expectancy_r": 0.0, "profit_factor_r": 0.0,
                  "expectancy_r_gross": 0.0, "cost_per_trade_r": 0.0,
                  "total_r": 0.0, "hit_rate_r": 0.0,
                  "avg_win": 0.0, "avg_loss": 0.0, "total_fees": 0.0,
                  "total_funding": 0.0, "total_slippage": 0.0,
                  "long_trades": 0, "short_trades": 0,
                  "avg_holding_bars": np.nan, "median_holding_bars": np.nan,
                  "exposure": 0.0, "turnover": 0.0, "net_pnl": 0.0,
                  "largest_win": 0.0, "largest_loss": 0.0, "gross_pnl_total": 0.0,
                  "cost_drag": 0.0, "cost_drag_pct_of_gross": np.nan,
                  "consecutive_wins": 0, "consecutive_losses": 0})
        return m

    pnl = trades["net_pnl"]
    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]
    gross_win = float(wins.sum())
    gross_loss = float(-losses.sum())

    m["win_rate"] = float((pnl > 0).mean())
    m["expectancy"] = float(pnl.mean())
    m["profit_factor"] = float(gross_win / gross_loss) if gross_loss > 0 else np.inf

    # R-normalised view: the primary comparison basis, because it is immune to
    # the choice of risk fraction and to account-size collapse.
    r = trades["r_net"].dropna()
    if len(r):
        rw = float(r[r > 0].sum())
        rl = float(-r[r <= 0].sum())
        m["expectancy_r"] = float(r.mean())
        m["profit_factor_r"] = float(rw / rl) if rl > 0 else np.inf
        m["expectancy_r_gross"] = float(trades["r_gross"].dropna().mean())
        m["cost_per_trade_r"] = float(trades["r_cost"].dropna().mean())
        m["total_r"] = float(r.sum())
        m["hit_rate_r"] = float((r > 0).mean())
    else:
        m.update({"expectancy_r": 0.0, "profit_factor_r": 0.0,
                  "expectancy_r_gross": 0.0, "cost_per_trade_r": 0.0,
                  "total_r": 0.0, "hit_rate_r": 0.0})
    m["avg_win"] = float(wins.mean()) if len(wins) else 0.0
    m["avg_loss"] = float(losses.mean()) if len(losses) else 0.0
    m["largest_win"] = float(pnl.max())
    m["largest_loss"] = float(pnl.min())
    m["net_pnl"] = float(pnl.sum())
    m["total_fees"] = float(trades["fees"].sum())
    m["total_funding"] = float(trades["funding"].sum())
    m["total_slippage"] = float(trades["slippage_cost"].sum())
    m["long_trades"] = int((trades["direction"] == "long").sum())
    m["short_trades"] = int((trades["direction"] == "short").sum())
    m["avg_holding_bars"] = float(trades["holding_bars"].mean())
    m["median_holding_bars"] = float(trades["holding_bars"].median())
    m["consecutive_losses"] = _max_streak(pnl <= 0)
    m["consecutive_wins"] = _max_streak(pnl > 0)

    held = trades["holding_bars"].clip(lower=1)
    overlap = float(held.sum()) / n_bars
    m["exposure"] = min(overlap, 1.0)
    m["turnover"] = float((trades["quantity"] * trades["entry_price"]).sum() / max(init, 1e-9))

    # Cost drag: how much of the gross result the frictions consumed.
    m["gross_pnl_total"] = float(trades["gross_pnl"].sum())
    m["cost_drag"] = m["total_fees"] + m["total_funding"] + m["total_slippage"]
    m["cost_drag_pct_of_gross"] = (
        m["cost_drag"] / abs(m["gross_pnl_total"]) if m["gross_pnl_total"] else np.nan)

    return m


def _max_streak(mask: pd.Series) -> int:
    best = cur = 0
    for v in mask.to_numpy():
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return int(best)


# --------------------------------------------------------------------------
# spec 60: classification, thresholds frozen above
# --------------------------------------------------------------------------

def classify(metrics_list: list[dict]) -> dict:
    """Aggregate per-symbol metrics into a FAILED / PROMISING / ROBUST verdict.

    ``metrics_list`` must be the out-of-sample metrics, one per symbol.
    """
    live = [m for m in metrics_list if m.get("total_trades", 0) > 0]
    if not live:
        return {"label": "FAILED", "reason": "no trades generated out of sample",
                "n_symbols": 0, "positive_symbol_fraction": 0.0}

    trades = sum(m["total_trades"] for m in live)
    pf = [m.get("profit_factor_r", m["profit_factor"]) for m in live
          if np.isfinite(m.get("profit_factor_r", m["profit_factor"]))]
    pos_frac = float(np.mean([1.0 if m.get("total_r", m["net_pnl"]) > 0 else 0.0 for m in live]))
    # R-normalised expectancy is the decision basis: absolute expectancy
    # depends on the arbitrary risk fraction and collapses as cash equity
    # spirals toward zero, which would mislabel a consistent loser as
    # "inconclusive".
    mean_exp = float(np.mean([m.get("expectancy_r", m["expectancy"]) for m in live]))
    med_sharpe = float(np.median([m.get("r_sharpe", m["sharpe"]) for m in live]))
    worst_dd = float(min(m.get("r_max_drawdown", m["max_drawdown"]) for m in live))

    failed_reasons: list[str] = []
    if mean_exp <= 0:
        failed_reasons.append("non-positive mean out-of-sample expectancy")
    if pf and float(np.median(pf)) <= PROMISING_MIN_PF:
        failed_reasons.append(f"median profit factor <= {PROMISING_MIN_PF}")
    if pos_frac <= 0.5 and trades >= MIN_TRADES:
        failed_reasons.append("profitable on at most half the symbols")
    if failed_reasons:
        return {"label": "FAILED", "reason": "; ".join(failed_reasons),
                "n_symbols": len(live), "total_trades": trades,
                "positive_symbol_fraction": pos_frac, "median_profit_factor_r":
                    float(np.median(pf)) if pf else float("nan"),
                "mean_expectancy_r": mean_exp, "median_sharpe": med_sharpe,
                "worst_max_drawdown": worst_dd}

    if trades < MIN_TRADES:
        return {"label": "PROMISING", "reason": f"too few trades ({trades} < {MIN_TRADES})",
                "n_symbols": len(live), "total_trades": trades,
                "positive_symbol_fraction": pos_frac, "mean_expectancy_r": mean_exp,
                "median_sharpe": med_sharpe, "worst_max_drawdown": worst_dd,
                "caveat": "under-powered; treat as inconclusive"}

    robust_gaps: list[str] = []
    if trades < ROBUST_MIN_TRADES:
        robust_gaps.append(f"fewer than {ROBUST_MIN_TRADES} trades")
    if pos_frac < ROBUST_MIN_POSITIVE_FRACTION:
        robust_gaps.append(
            f"only {pos_frac:.0%} of symbols profitable (< {ROBUST_MIN_POSITIVE_FRACTION:.0%})")
    if med_sharpe < ROBUST_MIN_SHARPE:
        robust_gaps.append(f"median Sharpe {med_sharpe:.2f} < {ROBUST_MIN_SHARPE}")
    if abs(worst_dd) > ROBUST_MAX_DRAWDOWN:
        robust_gaps.append(f"worst drawdown {worst_dd:.1%} beyond {ROBUST_MAX_DRAWDOWN:.0%}")
    # A strategy that cannot survive its own round trip is not a candidate
    # however good it looks gross of costs.
    cost_drag = float(np.median([m.get("cost_in_r_median", 0.0) for m in live
                                 if np.isfinite(m.get("cost_in_r_median", np.nan))] or [0.0]))
    if cost_drag >= 0.5:
        robust_gaps.append(f"round-trip friction is {cost_drag:.2f}R per trade")

    if robust_gaps:
        return {"label": "PROMISING", "reason": "missing robustness evidence: " + "; ".join(robust_gaps),
                "n_symbols": len(live), "total_trades": trades,
                "positive_symbol_fraction": pos_frac, "mean_expectancy": mean_exp,
                "median_sharpe": med_sharpe, "worst_max_drawdown": worst_dd}

    return {"label": "ROBUST", "reason": "meets all pre-registered criteria",
            "n_symbols": len(live), "total_trades": trades,
            "positive_symbol_fraction": pos_frac, "mean_expectancy_r": mean_exp,
            "median_sharpe": med_sharpe, "worst_max_drawdown": worst_dd}


def metrics_frame(results: list[BacktestResult]) -> pd.DataFrame:
    rows = [compute_metrics(r) for r in results]
    return pd.DataFrame(rows)


def aggregate_by(df: pd.DataFrame, by: str = "symbol") -> dict:
    """Aggregate per-symbol metrics into portfolio-level numbers (spec 40)."""
    if df.empty:
        return {}
    g = df.groupby(by)
    return {
        "n_symbols": int(g.ngroups),
        "total_trades": int(g["total_trades"].sum()),
        "positive_symbol_fraction": float((g["net_pnl"].sum() > 0).mean()),
        "median_expectancy": float(g["expectancy"].mean()),
        "median_profit_factor": float(g["profit_factor"].replace(np.inf, np.nan).mean()),
        "median_sharpe": float(g["sharpe"].mean()),
        "total_net_pnl": float(g["net_pnl"].sum()),
        "mean_total_return": float(g["total_return"].mean()),
        "worst_max_drawdown": float(g["max_drawdown"].min()),
        "long_trades": int(g["long_trades"].sum()),
        "short_trades": int(g["short_trades"].sum()),
        "total_fees": float(g["total_fees"].sum()),
        "total_funding": float(g["total_funding"].sum()),
        "total_slippage": float(g["total_slippage"].sum()),
    }
