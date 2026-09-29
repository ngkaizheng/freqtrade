"""Causal OHLCV execution and net-performance metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from tools.strategy_factory.models import CostScenario, StrategySpec


@dataclass(frozen=True)
class Trade:
    pair: str
    side: int
    entry_index: int
    exit_index: int
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_open: float
    exit_price_raw: float
    atr_at_entry: float
    exit_reason: str
    bars_held: int
    funding_rate_sum: float
    funding_payer_cost: float
    funding_events: int

    def with_costs(self, scenario: CostScenario) -> dict[str, object]:
        fee = scenario.fee_bps / 10_000
        slippage = scenario.slippage_bps / 10_000
        entry_fill = self.entry_open * (1 + self.side * slippage)
        exit_fill = self.exit_price_raw * (1 - self.side * slippage)
        gross_return = self.side * (exit_fill / entry_fill - 1)
        # The frozen MVP convention charges only funding debits. Credits are
        # deliberately ignored; a negative rate can never create a rebate.
        funding_cashflow = -self.funding_payer_cost
        net_return = gross_return + funding_cashflow - 2 * fee
        return {
            "pair": self.pair,
            "side": self.side,
            "entry_index": self.entry_index,
            "exit_index": self.exit_index,
            "entry_time": self.entry_time,
            "exit_time": self.exit_time,
            "entry_open": self.entry_open,
            "exit_price_raw": self.exit_price_raw,
            "atr_at_entry": self.atr_at_entry,
            "bars_held": self.bars_held,
            "exit_reason": self.exit_reason,
            "funding_rate_sum": self.funding_rate_sum,
            "funding_payer_cost": self.funding_payer_cost,
            "funding_events": self.funding_events,
            "gross_return": gross_return,
            "funding_cashflow": funding_cashflow,
            "fee_cost": 2 * fee,
            "net_return": net_return,
        }


def funding_rate_vector(
    dates: pd.Series,
    funding: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray]:
    """Align observed funding events to their containing 1m candle.

    Returns both rates and an event mask so a genuine zero-rate event is not
    confused with a missing event. No rate is forward-filled.
    """

    rates = np.zeros(len(dates), dtype=float)
    event_mask = np.zeros(len(dates), dtype=bool)
    if funding.empty:
        return rates, event_mask
    date_values = pd.to_datetime(dates, utc=True).to_numpy(dtype="datetime64[ns]")
    event_dates = pd.to_datetime(funding["date"], utc=True).to_numpy(dtype="datetime64[ns]")
    event_rates = pd.to_numeric(funding["funding_rate"], errors="coerce").to_numpy(dtype=float)
    for event_date, rate in zip(event_dates, event_rates, strict=True):
        if not np.isfinite(rate):
            continue
        position = int(np.searchsorted(date_values, event_date, side="left"))
        if position < len(date_values) and date_values[position] == event_date:
            rates[position] += float(rate)
            event_mask[position] = True
    return rates, event_mask


def _first_exit(
    side: int,
    open_price: float,
    high: float,
    low: float,
    stop: float,
    target: float,
) -> tuple[float | None, str | None]:
    """Return the first conservative exit in one candle."""

    if side == 1 and open_price <= stop:
        return open_price, "gap_stop"
    if side == -1 and open_price >= stop:
        return open_price, "gap_stop"
    if side == 1 and open_price >= target:
        return open_price, "gap_target"
    if side == -1 and open_price <= target:
        return open_price, "gap_target"
    # Unknown intrabar path: stop first, then target.
    if side == 1:
        if low <= stop:
            return stop, "stop"
        if high >= target:
            return target, "target"
    else:
        if high >= stop:
            return stop, "stop"
        if low <= target:
            return target, "target"
    return None, None


def simulate_trades(
    frame: pd.DataFrame,
    long_signal: np.ndarray,
    short_signal: np.ndarray,
    spec: StrategySpec,
    funding: pd.DataFrame,
    reset_indices: set[int] | None = None,
) -> list[Trade]:
    """Simulate one pair with signal-close/next-open causal timing.

    ``reset_indices`` force a flat state at fold boundaries. A position open at
    a boundary is closed at that boundary open and its trade is excluded from
    both adjacent fold metrics by the entry-time filter.
    """

    if len(long_signal) != len(frame) or len(short_signal) != len(frame):
        raise ValueError("Signal arrays must align with the feature frame")
    dates = pd.to_datetime(frame["date"], utc=True).reset_index(drop=True)
    opens = frame["open"].to_numpy(dtype=float)
    highs = frame["high"].to_numpy(dtype=float)
    lows = frame["low"].to_numpy(dtype=float)
    closes = frame["close"].to_numpy(dtype=float)
    atr = frame["atr14_1m"].to_numpy(dtype=float)
    funding_rates, funding_events = funding_rate_vector(dates, funding)
    reset_indices = reset_indices or set()
    stop_multiplier = float(spec.params["atr_stop"])
    target_r = float(spec.params["target_r"])
    trades: list[Trade] = []
    side = 0
    entry_index = -1
    entry_open = stop = target = entry_atr = 0.0

    def append_trade(index: int, exit_price: float, reason: str) -> None:
        held = index - entry_index
        event_slice = funding_rates[entry_index : index + 1]
        event_mask_slice = funding_events[entry_index : index + 1]
        trades.append(
            Trade(
                pair=str(frame.attrs.get("pair", "unknown")),
                side=side,
                entry_index=entry_index,
                exit_index=index,
                entry_time=dates.iloc[entry_index],
                exit_time=dates.iloc[index],
                entry_open=entry_open,
                exit_price_raw=float(exit_price),
                atr_at_entry=entry_atr,
                exit_reason=str(reason),
                bars_held=held,
                funding_rate_sum=float(event_slice.sum()),
                funding_payer_cost=float(np.maximum(0.0, side * event_slice).sum()),
                funding_events=int(event_mask_slice.sum()),
            )
        )

    candidate_indices = np.flatnonzero(long_signal | short_signal)
    candidate_pointer = 0
    index = 1
    while index < len(frame):
        if index in reset_indices:
            if side != 0:
                append_trade(index, float(opens[index]), "boundary_reset")
                side = 0
            # Do not use the signal from the candle immediately before a
            # boundary. The first post-boundary entry may use this candle's
            # completed signal on the following bar.
            index += 1
            continue

        if side == 0:
            signal_index = index - 1
            while (
                candidate_pointer < len(candidate_indices)
                and candidate_indices[candidate_pointer] < signal_index
            ):
                candidate_pointer += 1
            if candidate_pointer >= len(candidate_indices):
                break
            next_signal_index = int(candidate_indices[candidate_pointer])
            if next_signal_index > signal_index:
                # Skip a flat stretch without touching every minute.
                index = next_signal_index + 1
                continue
            if long_signal[signal_index]:
                side = 1
            elif short_signal[signal_index]:
                side = -1
            else:
                candidate_pointer += 1
                index += 1
                continue
            candidate_pointer += 1
            if not np.isfinite(atr[signal_index]) or atr[signal_index] <= 0:
                side = 0
                index += 1
                continue
            entry_index = index
            entry_open = float(opens[index])
            entry_atr = float(atr[signal_index])
            distance = stop_multiplier * entry_atr
            stop = entry_open - side * distance
            target = entry_open + side * target_r * distance
            index += 1
            continue

        exit_price, exit_reason = _first_exit(
            side, float(opens[index]), float(highs[index]), float(lows[index]), stop, target
        )
        if exit_price is None and index - entry_index >= spec.max_hold_minutes:
            exit_price, exit_reason = float(closes[index]), "time_stop"
        if exit_price is None:
            index += 1
            continue
        append_trade(index, exit_price, str(exit_reason))
        side = 0
        index += 1

    if side != 0:
        append_trade(len(frame) - 1, float(closes[-1]), "end_of_data")
    return trades


def raw_trades_to_frame(trades: Iterable[Trade]) -> pd.DataFrame:
    """Store path-level fields once; cost scenarios can be applied vectorially."""

    rows = [
        {
            "pair": trade.pair,
            "side": trade.side,
            "entry_index": trade.entry_index,
            "exit_index": trade.exit_index,
            "entry_time": trade.entry_time,
            "exit_time": trade.exit_time,
            "entry_open": trade.entry_open,
            "exit_price_raw": trade.exit_price_raw,
            "atr_at_entry": trade.atr_at_entry,
            "bars_held": trade.bars_held,
            "exit_reason": trade.exit_reason,
            "funding_rate_sum": trade.funding_rate_sum,
            "funding_payer_cost": trade.funding_payer_cost,
            "funding_events": trade.funding_events,
        }
        for trade in trades
    ]
    columns = [
        "pair",
        "side",
        "entry_index",
        "exit_index",
        "entry_time",
        "exit_time",
        "entry_open",
        "exit_price_raw",
        "atr_at_entry",
        "bars_held",
        "exit_reason",
        "funding_rate_sum",
        "funding_payer_cost",
        "funding_events",
    ]
    return pd.DataFrame(rows, columns=columns)


def apply_cost_scenario(
    raw_trades: pd.DataFrame,
    scenario: CostScenario,
) -> pd.DataFrame:
    """Apply one fixed per-side cost scenario to a raw trade path."""

    if raw_trades.empty:
        return raw_trades.assign(
            gross_return=pd.Series(dtype=float),
            funding_cashflow=pd.Series(dtype=float),
            fee_cost=pd.Series(dtype=float),
            net_return=pd.Series(dtype=float),
        )
    result = raw_trades.copy()
    side = result["side"].to_numpy(dtype=float)
    entry_open = result["entry_open"].to_numpy(dtype=float)
    exit_raw = result["exit_price_raw"].to_numpy(dtype=float)
    fee = float(scenario.fee_bps) / 10_000
    slippage = float(scenario.slippage_bps) / 10_000
    entry_fill = entry_open * (1 + side * slippage)
    exit_fill = exit_raw * (1 - side * slippage)
    result["gross_return"] = side * (exit_fill / entry_fill - 1)
    result["funding_cashflow"] = -result["funding_payer_cost"].to_numpy(dtype=float)
    result["fee_cost"] = 2 * fee
    result["net_return"] = result["gross_return"] + result["funding_cashflow"] - 2 * fee
    return result


def trades_to_frame(trades: Iterable[Trade], scenario: CostScenario) -> pd.DataFrame:
    return apply_cost_scenario(raw_trades_to_frame(trades), scenario)


def _daily_pair_returns(
    trades: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.Series:
    # Fold intervals are half-open. Exclude the end day when `end` is midnight
    # so adjacent rolling validation windows cannot share a calendar key.
    index = pd.date_range(
        start=start.floor("D"), end=end.floor("D"), freq="D", inclusive="left"
    )
    if trades.empty:
        return pd.Series(0.0, index=index)
    selected = trades[
        (trades["entry_time"] >= start) & (trades["exit_time"] < end)
    ].copy()
    if selected.empty:
        return pd.Series(0.0, index=index)
    selected["day"] = pd.to_datetime(selected["exit_time"], utc=True).dt.floor("D")
    daily = selected.groupby("day")["net_return"].apply(
        lambda values: float(np.prod(1 + values) - 1)
    )
    return daily.reindex(index, fill_value=0.0).astype(float)


def daily_portfolio_returns(
    trade_frames: dict[str, pd.DataFrame],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.Series:
    sleeves = []
    for pair in sorted(trade_frames):
        series = _daily_pair_returns(trade_frames[pair], start, end)
        series.name = pair
        sleeves.append(series)
    if not sleeves:
        return pd.Series(dtype=float)
    return pd.concat(sleeves, axis=1).mean(axis=1).fillna(0.0)


def performance_metrics(
    daily_returns: pd.Series,
    trades: pd.DataFrame,
) -> dict[str, float | int | str | None]:
    """Return net, calendar-time metrics for one sleeve or equal-weight pair."""

    daily = pd.Series(daily_returns, dtype=float).fillna(0.0)
    if trades.empty:
        return {
            "trades": 0,
            "win_rate": np.nan,
            "expectancy": np.nan,
            "profit_factor": np.nan,
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe": np.nan,
            "avg_hold_minutes": np.nan,
            "funding_cost": 0.0,
            "fees": 0.0,
        }
    net = trades["net_return"].astype(float)
    losses = -net[net < 0].sum()
    equity = (1 + daily).cumprod()
    drawdown = equity / equity.cummax() - 1
    standard_deviation = float(daily.std(ddof=1)) if len(daily) > 1 else 0.0
    return {
        "trades": int(len(net)),
        "win_rate": float((net > 0).mean()),
        "expectancy": float(net.mean()),
        "profit_factor": float(net[net > 0].sum() / losses) if losses > 0 else np.inf,
        "total_return": float(equity.iloc[-1] - 1),
        "max_drawdown": float(drawdown.min()),
        "sharpe": float(daily.mean() / standard_deviation * np.sqrt(365))
        if standard_deviation > 0
        else np.nan,
        "avg_hold_minutes": float(trades["bars_held"].mean()),
        "funding_cost": float(-trades["funding_cashflow"].sum()),
        "fees": float(trades["fee_cost"].sum()),
    }
