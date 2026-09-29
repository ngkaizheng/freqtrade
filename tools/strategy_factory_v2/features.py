"""Phase B -- the causal feature engine.

Every column produced here is available at the *close* of the bar it is
attached to, and at no earlier time. The engine is built so that this is
structural rather than a matter of care:

* Only trailing windows are used. ``Series.rolling(n)`` and
  ``Series.expanding()`` look backwards, so a feature at bar *t* can only ever
  reference bars ``<= t``.
* Percentiles use ``rolling(n).rank(pct=True)``, the rank of the current value
  within its own trailing window. A full-sample percentile would be a lookahead
  disguised as a normalisation, and is never used.
* Every external series is attached with a strictly backward ``merge_asof`` on
  ``decision_time``. A value stamped later than the decision is unreachable.
* The funding *event stream* is returned separately and is never forward-filled.
  The ``funding_rate_last`` feature is a step function of the last published
  rate, which is a genuine observable, and it is named to say so.

The engine tolerates absent derivatives data. Missing inputs produce NaN
features and a ``False`` availability flag; they never produce a substitute.
That is what lets a future open-interest file light the OI features up without
touching this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from tools.strategy_factory_v2.data import asof_join, timeframe_minutes
from tools.strategy_factory_v2.spec import (
    ATR_PERIODS,
    EMA_PERIODS,
    EXPANDING_MIN_EVENTS,
    FUNDING_PERCENTILE_CUTS,
    OI_WINDOWS,
    PERCENTILE_WINDOW,
    RANGE_WINDOW,
    REALIZED_VOL_WINDOWS,
    RETURN_WINDOWS,
    ROLLING_HIGH_LOW_WINDOW,
    TAKER_FLOW_WINDOWS,
    VWAP_WINDOW,
)

#: Availability flag names emitted alongside the features they gate.
AVAILABILITY_FLAGS = (
    "price_available",
    "funding_available",
    "open_interest_available",
    "taker_flow_available",
    "basis_available",
)


@dataclass
class FeatureBundle:
    """Features plus the untouched input events they were derived from."""

    frame: pd.DataFrame
    symbol: str
    timeframe: str
    funding_events: pd.DataFrame = field(default_factory=pd.DataFrame)
    open_interest_events: pd.DataFrame = field(default_factory=pd.DataFrame)
    taker_events: pd.DataFrame = field(default_factory=pd.DataFrame)
    basis_events: pd.DataFrame = field(default_factory=pd.DataFrame)
    #: Column -> earliest ``decision_time`` at which the column is defined.
    #: Filled by :func:`build_features`; consumed by the leakage tests.
    availability: dict[str, pd.Series] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.frame)


def _ema(series: pd.Series, span: int) -> pd.Series:
    """Exponential moving average, seeded only once ``span`` bars exist."""

    return series.ewm(span=span, adjust=False, min_periods=span).mean()


def _atr(frame: pd.DataFrame, period: int) -> pd.Series:
    """Wilder's average true range, computed from bars up to and including *t*."""

    high, low, close = frame["high"], frame["low"], frame["close"]
    previous = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - previous).abs(), (low - previous).abs()], axis=1
    ).max(axis=1)
    return true_range.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def _trailing_rank(series: pd.Series, window: int) -> pd.Series:
    """Percentile of the current value within its own trailing window.

    ``Rolling.rank`` returns the rank of the *last* observation, so the result
    at bar *t* depends only on bars ``<= t``. NaN until the window fills.
    """

    return series.rolling(window, min_periods=window).rank(pct=True) * 100.0


def _trailing_zscore(series: pd.Series, window: int, ddof: int = 1) -> pd.Series:
    mean = series.rolling(window, min_periods=window).mean()
    std = series.rolling(window, min_periods=window).std(ddof=ddof)
    with np.errstate(divide="ignore", invalid="ignore"):
        zscore = (series - mean) / std
    return zscore.replace([np.inf, -np.inf], np.nan)


def _expanding_zscore(series: pd.Series, min_periods: int) -> pd.Series:
    mean = series.expanding(min_periods=min_periods).mean()
    std = series.expanding(min_periods=min_periods).std(ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        zscore = (series - mean) / std
    return zscore.replace([np.inf, -np.inf], np.nan)


def _expanding_rank(series: pd.Series, min_periods: int) -> pd.Series:
    return series.expanding(min_periods=min_periods).rank(pct=True) * 100.0


def _slope(series: pd.Series, window: int) -> pd.Series:
    """Least-squares slope over a trailing window, scaled to per-bar units."""

    def _fit(values: np.ndarray) -> float:
        n = values.size
        if n < 2:
            return np.nan
        x = np.arange(n, dtype=float)
        x_centred = x - x.mean()
        denominator = float((x_centred**2).sum())
        if denominator == 0.0:
            return np.nan
        return float((x_centred * (values - values.mean())).sum() / denominator)

    return series.rolling(window, min_periods=window).apply(_fit, raw=True)


# ---------------------------------------------------------------------------
# Price features (plan section 12)
# ---------------------------------------------------------------------------


def price_features(frame: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Price, volatility, moving-average and range features for one timeframe."""

    minutes = timeframe_minutes(timeframe)
    close = frame["close"]
    log_return = np.log(close / close.shift(1))
    out = pd.DataFrame(index=frame.index)

    for window in RETURN_WINDOWS:
        out[f"ret_{window}"] = close.pct_change(window)
    out["log_ret_1"] = log_return

    for period in ATR_PERIODS:
        out[f"atr_{period}"] = _atr(frame, period)
    out["atr_14_pct"] = out["atr_14"] / close

    for window in REALIZED_VOL_WINDOWS:
        # Annualisation is a reporting convenience only; the raw stdev is what
        # every regime cut is applied to.
        out[f"realized_vol_{window}"] = log_return.rolling(
            window, min_periods=window
        ).std(ddof=1) * np.sqrt(365 * 24 * 60 / minutes)

    for span in EMA_PERIODS:
        out[f"ema_{span}"] = _ema(close, span)
    out["ema_spread_20_50"] = (out["ema_20"] - out["ema_50"]) / close
    out["ema_spread_50_200"] = (out["ema_50"] - out["ema_200"]) / close
    out["ema_stack"] = (
        (out["ema_20"] > out["ema_50"])
        & (out["ema_50"] > out["ema_100"])
        & (out["ema_100"] > out["ema_200"])
    ).astype("boolean")
    out["ema_stack_inverse"] = (
        (out["ema_20"] < out["ema_50"])
        & (out["ema_50"] < out["ema_100"])
        & (out["ema_100"] < out["ema_200"])
    ).astype("boolean")

    typical = (frame["high"] + frame["low"] + close) / 3.0
    money_flow = typical * frame["volume"]
    rolling_money_flow = money_flow.rolling(VWAP_WINDOW, min_periods=VWAP_WINDOW).sum()
    rolling_volume = frame["volume"].rolling(VWAP_WINDOW, min_periods=VWAP_WINDOW).sum()
    with np.errstate(divide="ignore", invalid="ignore"):
        out["vwap_48"] = rolling_money_flow / rolling_volume
        out["vwap_distance"] = (close - out["vwap_48"]) / close
    out["vwap_distance_bps"] = out["vwap_distance"] * 10_000

    out["rolling_high_48"] = (
        frame["high"].rolling(ROLLING_HIGH_LOW_WINDOW, min_periods=ROLLING_HIGH_LOW_WINDOW).max()
    )
    out["rolling_low_48"] = (
        frame["low"].rolling(ROLLING_HIGH_LOW_WINDOW, min_periods=ROLLING_HIGH_LOW_WINDOW).min()
    )
    out["range_position"] = (close - out["rolling_low_48"]) / (
        out["rolling_high_48"] - out["rolling_low_48"]
    )
    out["range"] = frame["high"] - frame["low"]
    out["range_ratio"] = out["range"] / out["range"].rolling(
        RANGE_WINDOW, min_periods=RANGE_WINDOW
    ).median()
    out["body"] = (frame["close"] - frame["open"]) / frame["open"]
    out["true_range"] = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - close.shift(1)).abs(),
            (frame["low"] - close.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    out["volume_median_48"] = frame["volume"].rolling(
        RANGE_WINDOW, min_periods=RANGE_WINDOW
    ).median()
    with np.errstate(divide="ignore", invalid="ignore"):
        out["volume_ratio"] = frame["volume"] / out["volume_median_48"]
    out["volume_percentile"] = _trailing_rank(frame["volume"], PERCENTILE_WINDOW)

    # Signed move size, used by the deleveraging-proxy family.
    out["abs_ret_1"] = out["ret_1"].abs()
    out["abs_ret_6"] = out["ret_6"].abs()
    out["abs_ret_12"] = out["ret_12"].abs()
    out["abs_ret_24"] = out["ret_24"].abs()
    out["abs_ret_48"] = out["ret_48"].abs()
    return out


# ---------------------------------------------------------------------------
# Derivatives features
# ---------------------------------------------------------------------------


def _attach_events(
    events: pd.DataFrame | None, frame: pd.DataFrame, columns: tuple[str, ...]
) -> pd.DataFrame:
    """Attach an event series to every bar with a strictly backward as-of join.

    The join key is ``decision_time`` on both sides, so a bar at decision time
    *t* can only ever see events stamped at or before *t*. Events are never
    shifted forward and a bar with no prior event stays NaN.
    """

    empty = pd.DataFrame(np.nan, index=range(len(frame)), columns=list(columns))
    if events is None or len(events) == 0:
        return empty

    prepared = events.copy()
    if "decision_time" not in prepared.columns:
        if "timestamp" in prepared.columns:
            prepared["decision_time"] = prepared["timestamp"]
        elif "settlement_time" in prepared.columns:
            prepared["decision_time"] = prepared["settlement_time"]
        else:
            raise ValueError("Event frame has no timestamp column to attach on")
    prepared = prepared.sort_values("decision_time", kind="stable")
    keep = [c for c in ("decision_time", *columns) if c in prepared.columns]
    left = pd.DataFrame({"decision_time": frame["decision_time"].to_numpy()})
    attached = asof_join(left, prepared[keep], "decision_time", "decision_time", "")
    attached = attached.reset_index(drop=True)
    for column in columns:
        if column not in attached.columns:
            attached[column] = np.nan
    return attached


def open_interest_features(
    events: pd.DataFrame | None, frame: pd.DataFrame
) -> pd.DataFrame:
    """Open-interest level, change, z-score, percentile, slope, acceleration.

    All windows are the preregistered ``OI_WINDOWS`` and are never optimised.
    """

    columns = ["open_interest"]
    for window in OI_WINDOWS:
        columns += [f"oi_change_{window}", f"oi_pct_change_{window}", f"oi_zscore_{window}"]
    columns += ["open_interest", "oi_percentile", "oi_slope", "oi_acceleration"]
    if events is None or events.empty:
        return pd.DataFrame(np.nan, index=frame.index, columns=list(dict.fromkeys(columns)))

    attached = _attach_events(events, frame, ("open_interest",))
    oi = pd.to_numeric(attached["open_interest"], errors="coerce")
    out = pd.DataFrame(index=frame.index)
    out["open_interest"] = oi
    for window in OI_WINDOWS:
        previous = oi.shift(window)
        with np.errstate(divide="ignore", invalid="ignore"):
            out[f"oi_change_{window}"] = oi - previous
            out[f"oi_pct_change_{window}"] = (oi - previous) / previous.abs()
        out[f"oi_zscore_{window}"] = _trailing_zscore(oi, window)
    out["oi_percentile"] = _trailing_rank(oi, PERCENTILE_WINDOW)
    out["oi_slope"] = _slope(oi, PERCENTILE_WINDOW)
    out["oi_acceleration"] = out["oi_slope"].diff(ROLLING_HIGH_LOW_WINDOW)
    return out


def taker_flow_features(
    events: pd.DataFrame | None, frame: pd.DataFrame
) -> pd.DataFrame:
    """Taker buy/sell volume and the signed imbalance, plus rolling versions.

    ``taker_imbalance`` is exactly the plan's definition::

        (taker_buy_volume - taker_sell_volume)
        ----------------------------------------
        (taker_buy_volume + taker_sell_volume)

    It is undefined when no taker flow was reported, and stays NaN there rather
    than defaulting to a neutral zero that would look like a real reading.
    """

    columns = ["taker_buy_volume", "taker_sell_volume", "taker_imbalance"]
    columns += [f"taker_imbalance_roll_{window}" for window in TAKER_FLOW_WINDOWS]
    columns += ["taker_imbalance_percentile"]
    if events is None or events.empty:
        return pd.DataFrame(np.nan, index=frame.index, columns=columns)

    attached = _attach_events(events, frame, ("taker_buy_volume", "taker_sell_volume"))
    buy = pd.to_numeric(attached["taker_buy_volume"], errors="coerce")
    sell = pd.to_numeric(attached["taker_sell_volume"], errors="coerce")
    total = buy + sell
    with np.errstate(divide="ignore", invalid="ignore"):
        imbalance = (buy - sell) / total
    out = pd.DataFrame(index=frame.index)
    out["taker_buy_volume"] = buy
    out["taker_sell_volume"] = sell
    out["taker_imbalance"] = imbalance.replace([np.inf, -np.inf], np.nan)
    for window in TAKER_FLOW_WINDOWS:
        out[f"taker_imbalance_roll_{window}"] = out["taker_imbalance"].rolling(
            window, min_periods=window
        ).mean()
    out["taker_imbalance_percentile"] = _trailing_rank(
        out[f"taker_imbalance_roll_{TAKER_FLOW_WINDOWS[2]}"], PERCENTILE_WINDOW
    )
    return out


def funding_features(
    events: pd.DataFrame, frame: pd.DataFrame, interval_hours: float | None = None
) -> pd.DataFrame:
    """Funding features built on the *event* stream, then attached backward.

    Percentiles and z-scores are computed over the expanding history of
    settlements, not over the price grid, because funding is an event series and
    a price-bar percentile of a step function would mostly measure how many
    bars fit between settlements.
    """

    columns = [
        "funding_rate_last",
        "funding_age_bars",
        "funding_zscore",
        "funding_percentile",
        "funding_change",
        "rolling_funding_mean",
        "rolling_funding_sum",
    ]
    if events is None or events.empty:
        empty = pd.DataFrame(np.nan, index=frame.index, columns=columns)
        empty["funding_available"] = False
        return empty

    ordered = events.sort_values("settlement_time", kind="stable").copy()
    rate = pd.to_numeric(ordered["funding_rate"], errors="coerce")
    derived = pd.DataFrame(
        {
            "settlement_time": ordered["settlement_time"].to_numpy(),
            "funding_rate": rate.to_numpy(),
            "funding_zscore": _expanding_zscore(rate, EXPANDING_MIN_EVENTS).to_numpy(),
            "funding_percentile": _expanding_rank(rate, EXPANDING_MIN_EVENTS).to_numpy(),
            "funding_change": rate.diff().to_numpy(),
        }
    )
    hours = float(interval_hours) if interval_hours else 8.0
    window = max(3, int(round(24.0 / hours)) * 3)
    derived["rolling_funding_mean"] = rate.rolling(window, min_periods=3).mean().to_numpy()
    derived["rolling_funding_sum"] = rate.rolling(window, min_periods=3).sum().to_numpy()

    left = pd.DataFrame({"decision_time": frame["decision_time"].to_numpy()})
    attached = asof_join(
        left, derived, "decision_time", "settlement_time", ""
    ).reset_index(drop=True)

    out = pd.DataFrame(index=frame.index)
    out["funding_rate_last"] = pd.to_numeric(attached["funding_rate"], errors="coerce")
    for name in (
        "funding_zscore",
        "funding_percentile",
        "funding_change",
        "rolling_funding_mean",
        "rolling_funding_sum",
    ):
        out[name] = pd.to_numeric(attached[name], errors="coerce")
    out["funding_available"] = out["funding_rate_last"].notna()
    out["funding_age_bars"] = (
        pd.to_datetime(attached["settlement_time"], errors="coerce") - left["decision_time"]
    ).dt.total_seconds() / 60.0
    return out


def basis_features(
    mark: pd.DataFrame | None,
    index: pd.DataFrame | None,
    frame: pd.DataFrame,
) -> pd.DataFrame:
    """Basis ``(mark - index) / index`` with its percentile and change.

    Basis is only defined from a genuine index price. A mark-versus-perpetual
    spread is a different quantity and is deliberately not accepted here.
    """

    columns = ["basis", "basis_zscore", "basis_percentile", "basis_change"]
    if mark is None or index is None or len(mark) == 0 or len(index) == 0:
        return pd.DataFrame(np.nan, index=frame.index, columns=columns)

    left = pd.DataFrame({"decision_time": frame["decision_time"].to_numpy()})
    mark_attached = _attach_events(mark, frame, ("mark_price",))
    index_attached = _attach_events(index, frame, ("index_price",))
    mark_price = pd.to_numeric(mark_attached["mark_price"], errors="coerce")
    index_price = pd.to_numeric(index_attached["index_price"], errors="coerce")
    with np.errstate(divide="ignore", invalid="ignore"):
        basis = (mark_price - index_price) / index_price
    basis = basis.replace([np.inf, -np.inf], np.nan)
    out = pd.DataFrame(index=frame.index)
    out["basis"] = basis
    out["basis_zscore"] = _trailing_zscore(basis, PERCENTILE_WINDOW)
    out["basis_percentile"] = _trailing_rank(basis, PERCENTILE_WINDOW)
    out["basis_change"] = basis.diff()
    return out


# ---------------------------------------------------------------------------
# Top level
# ---------------------------------------------------------------------------


def build_features(
    frame: pd.DataFrame,
    timeframe: str,
    symbol: str = "",
    funding_events: pd.DataFrame | None = None,
    funding_interval_hours: float | None = None,
    open_interest_events: pd.DataFrame | None = None,
    taker_events: pd.DataFrame | None = None,
    mark_events: pd.DataFrame | None = None,
    index_events: pd.DataFrame | None = None,
) -> FeatureBundle:
    """Build the full causal feature frame for one symbol and timeframe."""

    if "decision_time" not in frame.columns:
        raise ValueError(
            "Price frame must carry a decision_time column; it is the instant a "
            "bar becomes actionable and is what every causality assertion uses."
        )
    minutes = timeframe_minutes(timeframe)
    if not frame["decision_time"].is_monotonic_increasing:
        raise ValueError("Price frame must be sorted by decision_time")

    result = pd.concat(
        [
            frame[["date", "decision_time", "open", "high", "low", "close", "volume"]],
            price_features(frame, timeframe),
            funding_features(funding_events, frame, funding_interval_hours),
            open_interest_features(open_interest_events, frame),
            taker_flow_features(taker_events, frame),
            basis_features(mark_events, index_events, frame),
        ],
        axis=1,
    )
    result["timeframe"] = timeframe
    result["symbol"] = symbol
    result["bar_minutes"] = minutes

    # Availability flags. These are the single source of truth for whether a
    # family may run; the hypothesis registry consults them via the data audit.
    result["price_available"] = result["close"].notna()
    result["funding_available"] = result["funding_available"].fillna(False).astype(bool)
    result["open_interest_available"] = result["open_interest"].notna()
    result["taker_flow_available"] = result["taker_imbalance"].notna()
    result["basis_available"] = result["basis"].notna()
    result["warmup_complete"] = result["realized_vol_120"].notna() & result["ema_200"].notna()

    availability = {
        name: result["decision_time"] for name in result.columns if name != "warmup_complete"
    }
    bundle = FeatureBundle(
        frame=result,
        symbol=symbol,
        timeframe=timeframe,
        funding_events=funding_events if funding_events is not None else pd.DataFrame(),
        open_interest_events=open_interest_events
        if open_interest_events is not None
        else pd.DataFrame(),
        taker_events=taker_events if taker_events is not None else pd.DataFrame(),
        basis_events=mark_events if mark_events is not None else pd.DataFrame(),
        availability=availability,
    )
    return bundle


def forward_returns(frame: pd.DataFrame, horizons: tuple[int, ...]) -> pd.DataFrame:
    """Forward close-to-close returns over trailing-bar horizons.

    Measured from the decision at bar *t* to the close of bar ``t + horizon``,
    i.e. the return a position actually earns after entering at the next open.
    The final ``horizon`` bars of every frame are NaN by construction: there is
    no future to measure, and inventing one would be the exact failure the
    leakage tests exist to prevent.
    """

    close = frame["close"]
    out = pd.DataFrame(index=frame.index)
    for horizon in horizons:
        out[f"fwd_ret_{horizon}"] = close.shift(-horizon) / close - 1.0
    return out


def excursion_features(
    frame: pd.DataFrame, horizons: tuple[int, ...] = (6, 12, 24, 48)
) -> pd.DataFrame:
    """Maximum adverse and favourable excursion over each horizon.

    MAE is the worst loss along the path and MFE the best gain, both measured
    from the decision close. They answer a different question from the forward
    return: a positive mean return with deeply negative excursions is a
    strategy the funding and fee model can eat, and the plan requires both to
    be reported.
    """

    high, low = frame["high"], frame["low"]
    close = frame["close"]
    out = pd.DataFrame(index=frame.index)
    for horizon in horizons:
        future_high = high.shift(-1).rolling(horizon, min_periods=horizon).max().shift(-(horizon - 1))
        future_low = low.shift(-1).rolling(horizon, min_periods=horizon).min().shift(-(horizon - 1))
        with np.errstate(divide="ignore", invalid="ignore"):
            out[f"mfe_{horizon}"] = future_high / close - 1.0
            out[f"mae_{horizon}"] = future_low / close - 1.0
    return out.replace([np.inf, -np.inf], np.nan)


def baseline_distribution(returns: pd.Series) -> dict[str, float]:
    """The unconditional distribution every hypothesis must beat.

    A positive mean conditional return proves nothing on its own; it has to be
    an improvement on what the same symbol and horizon delivers with no
    condition at all.
    """

    values = pd.Series(returns, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    if values.empty:
        return {"count": 0}
    return {
        "count": int(len(values)),
        "mean": float(values.mean()),
        "median": float(values.median()),
        "std": float(values.std(ddof=1)) if len(values) > 1 else np.nan,
        "p05": float(values.quantile(0.05)),
        "p25": float(values.quantile(0.25)),
        "p75": float(values.quantile(0.75)),
        "p95": float(values.quantile(0.95)),
    }
