"""Bar-by-bar execution engine.

The ordering contract, which is the whole point of this file:

    at bar i:  1. execute the order decided at bar i-1's close, at bar i's OPEN
               2. charge funding if a funding timestamp falls in this bar
               3. test resting stop / target against bar i's high and low
               4. mark to market at bar i's close
               5. evaluate strategy signals at bar i's close -> order for i+1

A signal formed at bar ``t`` therefore cannot be filled before bar ``t+1``'s
open, and can never be filled at a price that bar ``t``'s own high/low or
close reveals.  Both properties are asserted by
``tests/test_no_lookahead.py``.

Levels are tracked in *raw market price* space; slippage is applied once, at
the moment of each fill, to the price actually paid.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .. import config as C
from .costs import CostModel

FLAT, LONG, SHORT = 0, 1, -1

EXIT_STOP = "stop"
EXIT_TARGET = "target"
EXIT_TIME = "time_stop"
EXIT_SIGNAL = "signal"
EXIT_EOD = "end_of_data"
EXIT_TRAIL = "trailing_stop"

# Attribution codes -> names.  Spec section 54 requires every trade to record
# which combination of conditions produced it.
REASON_NAMES: dict[int, str] = {
    0: "NONE",
    1: "RVOL_BREAKOUT",
    2: "RVOL_BREAKOUT_VWAP",
    3: "RVOL_BREAKOUT_CVD",
    4: "RVOL_BREAKOUT_OBV",
    5: "RVOL_BREAKOUT_OI",
    6: "RVOL_BREAKOUT_CVD_OI",
    7: "RVOL_BREAKOUT_LIQ",
    8: "SHARK08_FULL",
    9: "BREAKOUT_ONLY",
    10: "RVOL_ONLY",
    11: "RANDOM",
    12: "LIQ_LONG",
    13: "LIQ_SHORT",
    14: "FUNDING_FILTER",
}

R_NONE, R_VOL_BO, R_VOL_BO_VWAP, R_VOL_BO_CVD, R_VOL_BO_OBV, R_VOL_BO_OI = 1, 1, 2, 3, 4, 5
R_VOL_BO_CVD_OI, R_VOL_BO_LIQ, R_SHARK08, R_BO_ONLY, R_VOL_ONLY, R_RANDOM = 6, 7, 8, 9, 10, 11


@dataclass
class StrategySpec:
    """Everything the engine needs, as boolean/int arrays over the bar grid.

    A strategy is a pure function of the feature frame: it never sees equity,
    never sizes a position, and never decides an exit price.  That keeps the
    ablation honest -- the only thing changing between SHARK-01 and SHARK-08
    is the boolean expressions.
    """

    name: str
    long_entry: np.ndarray
    short_entry: np.ndarray
    long_exit: np.ndarray
    short_exit: np.ndarray
    long_reason: np.ndarray
    short_reason: np.ndarray
    atr_stop: float = C.DEFAULT_ATR_STOP
    r_multiple: float = C.DEFAULT_R_MULTIPLE
    time_stop_bars: int = 24
    cooldown_bars: int = C.DEFAULT_COOLDOWN_BARS
    trailing_atr: float | None = None
    use_signal_exit: bool = True

    def validate(self, n: int) -> "StrategySpec":
        for name in ("long_entry", "short_entry", "long_exit", "short_exit",
                     "long_reason", "short_reason"):
            arr = getattr(self, name)
            if len(arr) != n:
                raise ValueError(f"{self.name}.{name} has length {len(arr)}, expected {n}")
        return self


@dataclass
class BacktestResult:
    trades: pd.DataFrame
    equity: pd.Series
    symbol: str
    timeframe: str
    strategy: str
    params: dict
    costs: dict
    initial_equity: float
    meta: dict = field(default_factory=dict)

    @property
    def n_trades(self) -> int:
        return len(self.trades)


def _nan_bool(n: int) -> np.ndarray:
    return np.zeros(n, dtype=bool)


def run_backtest(df: pd.DataFrame, spec: StrategySpec, *,
                 symbol: str = "UNKNOWN",
                 timeframe: str = C.PRIMARY_TIMEFRAME,
                 costs: CostModel | None = None,
                 initial_equity: float = 10_000.0,
                 risk_fraction: float = C.DEFAULT_RISK_FRACTION,
                 max_leverage: float = C.DEFAULT_MAX_LEVERAGE) -> BacktestResult:
    """Execute ``spec`` over ``df``.

    ``df`` must be the full-history feature frame.  Slicing happens *after*
    the trade list is built, so that cumulative features (CVD, VWAP) never
    restart at a split boundary.
    """
    costs = costs or CostModel()
    n = len(df)
    if n < 2:
        return _empty_result(df, spec, symbol, timeframe, costs, initial_equity)
    spec.validate(n)

    idx = df.index
    o = df["open"].to_numpy(dtype=float)
    h = df["high"].to_numpy(dtype=float)
    l = df["low"].to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float)
    atr = df["atr"].to_numpy(dtype=float) if "atr" in df.columns else np.full(n, np.nan)
    funding_rate = (df["funding_rate"].to_numpy(dtype=float)
                    if "funding_rate" in df.columns else np.zeros(n))
    funding_event = (df["funding_event"].to_numpy(dtype=bool)
                     if "funding_event" in df.columns else np.zeros(n, dtype=bool))

    le = spec.long_entry.astype(bool)
    se = spec.short_entry.astype(bool)
    lx = spec.long_exit.astype(bool)
    sx = spec.short_exit.astype(bool)
    lr = spec.long_reason.astype(int)
    sr = spec.short_reason.astype(int)

    # ---- position state ---------------------------------------------------
    pos = FLAT
    entry_ref = entry_fill = stop_ref = target_ref = 0.0
    entry_fee = 0.0
    funding_acc = 0.0
    qty = 0.0
    entry_i = 0
    entry_signal_i = 0
    entry_atr = np.nan
    entry_reason = 0
    bars_held = 0
    cooldown_until = -1
    pending_entry = FLAT
    pending_reason = 0
    pending_exit = False
    pending_exit_reason = EXIT_SIGNAL
    initial_risk = np.nan
    mfe = mae = 0.0
    trail_ref = np.nan
    trail_armed = False

    cash = initial_equity
    equity = np.empty(n, dtype=float)
    equity[0] = initial_equity
    records: list[dict] = []

    def close_position(i: int, fill_ref: float, reason: str) -> None:
        """Exit at market reference ``fill_ref``, paying real spread."""
        nonlocal pos, cash, qty, entry_fee, funding_acc, bars_held
        nonlocal trail_armed, trail_ref, cooldown_until, initial_risk

        fill = costs.apply_slippage(fill_ref, -pos)
        raw_pnl = (fill_ref - entry_ref) * qty * pos
        exec_pnl = (fill - entry_fill) * qty * pos
        exit_fee = costs.fee(qty * fill)
        fees_total = entry_fee + exit_fee
        net = exec_pnl - fees_total - funding_acc
        cash += exec_pnl - exit_fee

        records.append({
            "symbol": symbol, "timeframe": timeframe, "strategy": spec.name,
            "signal_time": idx[entry_signal_i],
            "entry_time": idx[entry_i], "exit_time": idx[i],
            "entry_price": entry_fill, "exit_price": fill,
            "entry_reference": entry_ref, "exit_reference": fill_ref,
            "direction": "long" if pos == LONG else "short",
            "quantity": qty,
            "gross_pnl": raw_pnl,
            "slippage_cost": raw_pnl - exec_pnl,
            "fees": fees_total, "fee_entry": entry_fee, "fee_exit": exit_fee,
            "funding": funding_acc,
            "net_pnl": net,
            "initial_risk": initial_risk,
            "r_net": (net / initial_risk) if initial_risk and initial_risk > 0 else np.nan,
            "r_gross": (raw_pnl / initial_risk) if initial_risk and initial_risk > 0 else np.nan,
            "r_cost": ((fees_total + funding_acc + (raw_pnl - exec_pnl)) / initial_risk)
                      if initial_risk and initial_risk > 0 else np.nan,
            "return_on_risk": (net / abs(entry_ref - stop_ref) * qty) if qty else np.nan,
            "mfe": mfe, "mae": mae,
            "mfe_pct": mfe / entry_ref if entry_ref else np.nan,
            "mae_pct": mae / entry_ref if entry_ref else np.nan,
            "holding_bars": bars_held,
            "atr": entry_atr, "stop_price": stop_ref, "target_price": target_ref,
            "r_multiple": spec.r_multiple, "atr_stop": spec.atr_stop,
            "entry_reason": REASON_NAMES.get(entry_reason, "UNKNOWN"),
            "exit_reason": reason,
            "split": C.split_of(idx[entry_i]),
        })

        pos = FLAT
        qty = 0.0
        entry_fee = 0.0
        funding_acc = 0.0
        bars_held = 0
        initial_risk = np.nan
        trail_armed = False
        trail_ref = np.nan
        cooldown_until = i + spec.cooldown_bars

    for i in range(n):
        # -- 1. execute the order decided at bar i-1's close, at this open ----
        if pending_entry != FLAT and pos == FLAT and i > cooldown_until:
            atr_ref = atr[i - 1] if not np.isnan(atr[i - 1]) else atr[i]
            stop_dist = atr_ref * spec.atr_stop
            raw_entry = o[i]
            if not np.isnan(stop_dist) and stop_dist > 0 and raw_entry > 0:
                eq_now = cash
                size = (risk_fraction * eq_now) / stop_dist
                size = min(size, (max_leverage * eq_now) / raw_entry)
                if size > 0:
                    pos = pending_entry
                    entry_ref = raw_entry
                    entry_fill = costs.apply_slippage(raw_entry, pending_entry)
                    qty = size
                    entry_i = i
                    entry_signal_i = i - 1
                    entry_atr = atr_ref
                    entry_reason = pending_reason
                    stop_ref = raw_entry - pending_entry * stop_dist
                    target_ref = raw_entry + pending_entry * spec.r_multiple * stop_dist
                    entry_fee = costs.fee(qty * raw_entry)
                    cash -= entry_fee
                    funding_acc = 0.0
                    initial_risk = stop_dist * size
                    mfe = mae = 0.0
                    trail_ref = np.nan
                    trail_armed = False
                    bars_held = 0

        if pending_exit and pos != FLAT:
            close_position(i, o[i], pending_exit_reason)

        pending_entry = FLAT
        pending_reason = 0
        pending_exit = False
        pending_exit_reason = EXIT_SIGNAL

        # -- 2. funding (spec 34) ------------------------------------------
        if pos != FLAT and costs.apply_funding and funding_event[i] \
                and not np.isnan(funding_rate[i]):
            fc = costs.funding_cost(pos, qty * c[i], funding_rate[i])
            cash -= fc
            funding_acc += fc

        # -- 3. resting stop / target ---------------------------------------
        if pos != FLAT:
            bars_held += 1
            fav = (h[i] - entry_ref) * pos
            adv = (l[i] - entry_ref) * pos
            mfe = max(mfe, fav)
            mae = min(mae, adv)

            # Trailing variant (spec 27): arm at +1R, then trail by k*ATR.
            if spec.trailing_atr is not None and not np.isnan(atr[i]) and not np.isnan(entry_atr):
                if not trail_armed and fav >= entry_atr:
                    trail_armed = True
                    trail_ref = (h[i] - spec.trailing_atr * atr[i]) if pos == LONG \
                        else (l[i] + spec.trailing_atr * atr[i])
                elif trail_armed:
                    trail_ref = max(trail_ref, h[i] - spec.trailing_atr * atr[i]) if pos == LONG \
                        else min(trail_ref, l[i] + spec.trailing_atr * atr[i])

            active_stop = trail_ref if (trail_armed and not np.isnan(trail_ref)) else stop_ref
            stop_reason = EXIT_TRAIL if (trail_armed and not np.isnan(trail_ref)) else EXIT_STOP

            if pos == LONG:
                stop_touched = l[i] <= active_stop
                target_touched = h[i] >= target_ref
                gapped = o[i] < active_stop
            else:
                stop_touched = h[i] >= active_stop
                target_touched = l[i] <= target_ref
                gapped = o[i] > active_stop

            # Stop assumed first when a bar touches both -- the conservative
            # reading of an ambiguous intrabar path.
            if stop_touched:
                close_position(i, o[i] if gapped else active_stop, stop_reason)
            elif target_touched:
                close_position(i, target_ref, EXIT_TARGET)

        # -- 4. mark to market ----------------------------------------------
        equity[i] = cash + ((c[i] - entry_fill) * qty * pos if pos != FLAT else 0.0)

        # -- 5. decisions at this bar's close -------------------------------
        if i < n - 1:
            if pos == FLAT and i > cooldown_until:
                if le[i]:
                    pending_entry, pending_reason = LONG, lr[i]
                elif se[i]:
                    pending_entry, pending_reason = SHORT, sr[i]
            elif pos != FLAT:
                if spec.use_signal_exit and ((pos == LONG and lx[i]) or (pos == SHORT and sx[i])):
                    pending_exit = True
                    pending_exit_reason = EXIT_SIGNAL
                if bars_held >= spec.time_stop_bars:
                    pending_exit = True
                    pending_exit_reason = EXIT_TIME

    # ---- close anything still open at the final close --------------------
    if pos != FLAT:
        close_position(n - 1, c[n - 1], EXIT_EOD)
        # The last bar was marked to market *before* this liquidation, so it
        # still carried the position's unrealised PnL and omitted the exit
        # fee.  Re-mark it to the post-liquidation value, otherwise reported
        # final equity and the trade log disagree by the exit fee.
        equity[n - 1] = cash

    equity = pd.Series(equity, index=idx, name="equity")
    trades = pd.DataFrame(records)
    if not trades.empty:
        trades = trades.sort_values("entry_time").reset_index(drop=True)
        trades["trade_number"] = np.arange(1, len(trades) + 1)

    return BacktestResult(
        trades=trades, equity=equity, symbol=symbol, timeframe=timeframe,
        strategy=spec.name,
        params={"atr_stop": spec.atr_stop, "r_multiple": spec.r_multiple,
                "time_stop_bars": spec.time_stop_bars, "cooldown_bars": spec.cooldown_bars,
                "trailing_atr": spec.trailing_atr, "use_signal_exit": spec.use_signal_exit},
        costs=costs.describe(), initial_equity=initial_equity,
    )


def _empty_result(df, spec, symbol, timeframe, costs, initial_equity) -> BacktestResult:
    return BacktestResult(
        trades=pd.DataFrame(),
        equity=pd.Series(initial_equity, index=df.index, name="equity"),
        symbol=symbol, timeframe=timeframe, strategy=spec.name,
        params={}, costs=costs.describe(), initial_equity=initial_equity)
