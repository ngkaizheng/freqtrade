"""Cost feasibility (spec section 32/33/34, answering question 8).

The single most important number in this study is not a return.  It is the
ratio

    cost_in_R = round_trip_friction / stop_distance

because it bounds what any exit rule can achieve.  A strategy that pays 0.9R
per trade in friction needs a 0.9R *gross* edge just to reach break-even, which
no combination of entry filters can supply if the gross edge is smaller than
that.

This is a property of the instrument, timeframe and stop width, not of any
particular signal, so it is measured first and reported before any strategy
ranking.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import config as C


def round_trip_for(symbol: str) -> float:
    """Actual round-trip friction for one symbol, as a fraction of notional.

    Per symbol, not global: BTC pays 1bp slippage against LINK's 4bp, which
    is a 60% difference in the round trip and therefore in cost_in_r.  Using
    one portfolio-average number for every symbol overstates BTC and
    understates the alts.
    """
    return 2 * (C.TAKER_FEE_BPS + C.SLIPPAGE_BPS.get(symbol, C.DEFAULT_SLIPPAGE_BPS)) * 1e-4


def stop_width_profile(df: pd.DataFrame, atr_period: int = 14,
                       atr_multiples: tuple[float, ...] = (0.5, 1.0, 1.5, 2.0, 3.0, 5.0),
                       round_trip: float | None = None) -> pd.DataFrame:
    """For each ATR stop multiple, how much of 1R do fees and slippage consume?"""
    if "atr" not in df.columns or "close" not in df.columns:
        return pd.DataFrame()
    rt = C.ROUND_TRIP_COST if round_trip is None else round_trip
    atr_pct = (df["atr"] / df["close"]).replace(0.0, np.nan)
    rows = []
    for m in atr_multiples:
        stop_pct = atr_pct * m
        med = float(stop_pct.median())
        rows.append({
            "atr_multiple": m,
            "median_stop_pct": med,
            "cost_in_r": rt / med if med else np.nan,
            "pct_of_trades_below_cost_floor": float((stop_pct < rt).mean()),
            "breakeven_hit_rate_1R_to_2R": 1 / 3.0,
            "required_gross_edge_in_r_to_break_even": rt / med if med else np.nan,
        })
    return pd.DataFrame(rows)


def symbol_cost_table(datasets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Cost-in-R per symbol at the default 1-ATR stop, across the universe."""
    rows = []
    for sym, df in datasets.items():
        if "atr" not in df.columns:
            continue
        stop_pct = (df["atr"] / df["close"]).replace(0.0, np.nan).dropna()
        if stop_pct.empty:
            continue
        med = float(stop_pct.median())
        rt = round_trip_for(sym)
        rows.append({
            "symbol": sym,
            "median_atr_pct": med,
            "stop_pct_1atr": med,
            "round_trip_bps": rt * 1e4,
            "cost_in_r_1atr": rt / med,
            "slippage_bps": C.SLIPPAGE_BPS.get(sym, C.DEFAULT_SLIPPAGE_BPS),
            "pct_trades_below_cost_floor": float((stop_pct < rt).mean()),
        })
    return pd.DataFrame(rows).sort_values("cost_in_r_1atr") if rows else pd.DataFrame()


def slippage_sensitivity(trades: pd.DataFrame,
                         notional: float = 10_000.0,
                         slippage_grid_bps: tuple[float, ...] = (0, 2, 5, 10)) -> pd.DataFrame:
    """Spec 33: what happens to expectancy across a slippage grid.

    Recomputes net PnL per trade at each slippage level by re-pricing the
    existing fills; it does not re-run the engine, because the signal and the
    fill times are unaffected by a different slippage assumption.
    """
    if trades.empty:
        return pd.DataFrame()
    rows = []
    n = len(trades)
    for bps in slippage_grid_bps:
        extra = 2 * bps * 1e-4 * notional          # both legs
        net = trades["gross_pnl"].to_numpy() - trades["fees"].to_numpy() - extra
        wins = net[net > 0].sum()
        losses = -net[net <= 0].sum()
        rows.append({
            "slippage_bps": bps,
            "expectancy": float(net.mean()),
            "profit_factor": float(wins / losses) if losses > 0 else np.inf,
            "win_rate": float((net > 0).mean()),
            "total_net": float(net.sum()),
        })
    return pd.DataFrame(rows)


def fee_sensitivity(trades: pd.DataFrame, notional: float = 10_000.0,
                    fee_grid_bps: tuple[float, ...] = (0, 2, 5, 10)) -> pd.DataFrame:
    """Spec 32: expectancy across taker-fee tiers, including a zero-fee world."""
    if trades.empty:
        return pd.DataFrame()
    notionals = (trades["quantity"] * (trades["entry_price"] + trades["exit_price"]) / 2).to_numpy()
    gross = trades["gross_pnl"].to_numpy()
    rows = []
    for bps in fee_grid_bps:
        net = gross - notionals * bps * 1e-4 * 2
        wins = net[net > 0].sum()
        losses = -net[net <= 0].sum()
        rows.append({
            "taker_fee_bps": bps,
            "expectancy": float(net.mean()),
            "profit_factor": float(wins / losses) if losses > 0 else np.inf,
            "win_rate": float((net > 0).mean()),
            "total_net": float(net.sum()),
        })
    return pd.DataFrame(rows)
