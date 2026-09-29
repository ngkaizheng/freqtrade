"""Phase C -- the discovery feature frame, built from the recovered dataset.

This is where the A2.5 work pays off or does not. The frame is assembled from
four sources that disagree about time: bars on a regular grid, open interest on
an irregular one, funding on an 8-hour event schedule, and index/mark on yet
another. Every attachment goes through :mod:`joins`, which is the only code in
the project permitted to attach an event to a bar.

Three properties are structural rather than promised:

* The frame is built from **development data only**. The holdout guard runs
  before any feature is computed, so the boundary cannot be crossed by a
  trailing window or a percentile that happens to reach past it.
* Every attached event stream carries ``source_timestamp`` and
  ``age_seconds`` on the frame itself, so any later consumer can audit the
  attachment without re-deriving it.
* Percentiles are trailing and computed on the development frame only. A
  percentile computed over a frame that included the holdout would leak the
  holdout's distribution into the development regime, which is a leak that
  leaves no fingerprint on any single bar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from tools.strategy_factory_v2 import holdout as H
from tools.strategy_factory_v2.data import TIMEFRAME_MINUTES, load_funding_events
from tools.strategy_factory_v2.features import (
    _atr,
    _ema,
    _slope,
    _trailing_rank,
    _trailing_zscore,
    excursion_features,
    forward_returns,
    price_features,
)
from tools.strategy_factory_v2.ingest import CANONICAL_DIR
from tools.strategy_factory_v2.joins import causal_asof_join
from tools.strategy_factory_v2.regime import classify, relative_strength
from tools.strategy_factory_v2.spec import (
    DISCOVERY_TIMEFRAMES,
    EXPANDING_MIN_EVENTS,
    OI_WINDOWS,
    PERCENTILE_WINDOW,
    TAKER_FLOW_WINDOWS,
)

#: Forward-return horizons evaluated in Phase C, in bars of the feature
#: timeframe. The plan asks for 5m/15m/30m/1h/4h; on a 15m grid that is
#: 1/1/2/4/16 bars and on a 1h grid 5/15/30/60/240 bars. The registry stores
#: horizons in bars, so both are expressed here in bars and labelled in the
#: output by their clock equivalent.
FORWARD_HORIZON_BARS = (1, 3, 6, 12, 24, 48, 96, 240)


def _load(symbol: str, folder: str, interval: str) -> pd.DataFrame | None:
    path = CANONICAL_DIR / folder / f"{symbol}_{interval}.feather"
    return pd.read_feather(path) if path.exists() else None


def _funding_events(symbol: str) -> pd.DataFrame | None:
    base = symbol.replace("USDT", "_USDT")
    for folder, pattern in (
        (Path("user_data/data/binance_funding"), f"{base}-funding.feather"),
        (
            Path("user_data/data/binance/futures"),
            f"{base}_USDT_USDT-8h-funding_rate.feather",
        ),
    ):
        path = folder / pattern
        if path.exists():
            return load_funding_events(path)
    return None


@dataclass
class DiscoveryFrame:
    """One symbol and timeframe, development region only."""

    symbol: str
    timeframe: str
    frame: pd.DataFrame
    funding_events: pd.DataFrame
    partition: Any
    attach_report: dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.frame)


#: Bars of development history allowed before the holdout start, so trailing
#: windows and regime percentiles are already warm when the holdout opens.
#:
#: This is the standard warm-up convention and it is causal rather than
#: convenient: every feature in this engine is trailing, so a bar at the
#: holdout boundary can only ever reference bars *before* it, all of which lie
#: in development. Signals are still evaluated only from ``holdout_start``
#: onwards, and the warm-up rows are never counted as observations.
#:
#: 90 days comfortably exceeds the longest window in use: 288 bars (12 days) for
#: the percentile features plus 288 bars (12 days) for the open-interest
#: percentile, plus the 30-settlement (10 day) expanding funding warm-up.
HOLDOUT_WARMUP_DAYS = 90


def build_discovery_frame(
    symbol: str,
    timeframe: str,
    partition: H.DataPartition,
    region: str = "development",
    warmup_days: int = HOLDOUT_WARMUP_DAYS,
) -> DiscoveryFrame:
    """Assemble the causal feature frame for one symbol and timeframe.

    ``region`` selects development, validation, or the final holdout. Reaching
    the holdout additionally requires the partition to have been unsealed --
    a region flag alone cannot open it.
    """

    if region not in ("development", "validation", "final_holdout"):
        raise ValueError(
            f"region must be 'development', 'validation' or 'final_holdout'; got {region!r}"
        )
    if region == "final_holdout":
        partition.require_unsealed(f"build({symbol},{timeframe})")

    price = _load(symbol, "price", timeframe)
    if price is None:
        raise FileNotFoundError(f"no recovered {timeframe} price for {symbol}")
    minutes = TIMEFRAME_MINUTES[timeframe]
    price = price.sort_values("date").reset_index(drop=True)
    price["decision_time"] = price["date"] + pd.Timedelta(minutes=minutes)

    # The frame is trimmed to the requested region *before* any feature is
    # computed. That ordering is the whole point: building features first and
    # trimming afterwards would let a trailing window near the boundary -- and
    # any full-sample percentile -- see later data before the rows are dropped.
    if region == "development":
        lower = pd.Timestamp(partition.development_start)
        # Trim to development_end, NOT validation_end. Extending the
        # development frame into the reserved validation window lets the
        # walk-forward folds reach into data that is supposed to be unseen, so
        # the "validation" result stops being independent of the screening
        # statistic. This was measured, not theorised: Phase C's fold 18 for
        # H13_BTC_FILTER_1H_STRONG_UP_SHORT lay entirely inside the validation
        # region, and Phase D's reported validation_n=3 was bit-identical to
        # that same fold.
        upper = pd.Timestamp(partition.development_end)
    elif region == "validation":
        lower = pd.Timestamp(partition.validation_start)
        upper = pd.Timestamp(partition.validation_end)
    else:
        # Warm-up rows are inside development and are retained so the trailing
        # windows are defined; they are excluded at evaluation time.
        lower = pd.Timestamp(partition.holdout_start) - pd.Timedelta(days=warmup_days)
        upper = pd.Timestamp(partition.holdout_end)

    stamps = pd.to_datetime(price["date"], utc=True)
    price = price[(stamps >= lower) & (stamps <= upper)].reset_index(drop=True)
    if price.empty:
        raise ValueError(f"{symbol}/{timeframe}: no rows in the {region} region")

    if region != "final_holdout":
        # For the research regions the boundary is a wall: nothing at or after
        # the holdout start may enter. The final holdout is the one case where
        # the frame legitimately extends to holdout_end.
        #
        # The check runs on the *trimmed* frame, not on the file as loaded.
        # Those are not the same object, and only one of them is the thing the
        # boundary is about. The canonical price file runs to the end of the
        # recovered data, so a check on the loaded file rejects every
        # development build outright -- a file that *contains* later rows is
        # not a development frame *using* them, and those rows are dropped one
        # line above. Checking the frame that actually enters the pipeline
        # keeps the guarantee exact (a development frame can never carry a
        # timestamp at or after the boundary) and keeps the phase reproducible.
        H.assert_development_window(
            price,
            partition,
            "date",
            context=f"build({symbol},{timeframe},{region})",
        )

    out = price.loc[
        :, ["date", "decision_time", "open", "high", "low", "close", "volume",
            "quote_volume", "trades", "taker_buy_volume", "taker_sell_volume"]
    ].copy()
    out = pd.concat([out, price_features(out, timeframe)], axis=1)
    # Taker flow rides inside the price frame, so it needs no join at all --
    # the bar's own field is knowable at that bar's close.
    total = out["volume"]
    with np.errstate(divide="ignore", invalid="ignore"):
        out["taker_imbalance"] = (
            (out["taker_buy_volume"] - out["taker_sell_volume"]) / total
        ).replace([np.inf, -np.inf], np.nan)
    for window in TAKER_FLOW_WINDOWS:
        out[f"taker_imbalance_roll_{window}"] = out["taker_imbalance"].rolling(
            window, min_periods=window
        ).mean()
    out["taker_imbalance_percentile"] = _trailing_rank(
        out[f"taker_imbalance_roll_{TAKER_FLOW_WINDOWS[2]}"], PERCENTILE_WINDOW
    )
    out["taker_flow_available"] = out["taker_imbalance"].notna()

    attach: dict[str, Any] = {}

    # ---- open interest: irregular event stream, causal as-of -------------
    oi = _load(symbol, "open_interest", "5m")
    if oi is not None:
        oi = oi.sort_values("timestamp").reset_index(drop=True)
        join = causal_asof_join(out["decision_time"], oi, ["open_interest", "open_interest_value"])
        out["open_interest"] = join.frame["open_interest"]
        out["open_interest_value"] = join.frame["open_interest_value"]
        out["oi_source_timestamp"] = join.frame["source_timestamp"]
        out["oi_age_seconds"] = join.frame["age_seconds"]
        oi_series = out["open_interest"]
        for window in OI_WINDOWS:
            previous = oi_series.shift(window)
            with np.errstate(divide="ignore", invalid="ignore"):
                out[f"oi_change_{window}"] = oi_series - previous
                out[f"oi_pct_change_{window}"] = (oi_series - previous) / previous.abs()
            out[f"oi_zscore_{window}"] = _trailing_zscore(oi_series, window)
        out["oi_percentile_288"] = _trailing_rank(oi_series, PERCENTILE_WINDOW)
        # The validated regime engine reads ``oi_percentile``. The frame also
        # carries the window-explicit name the registry's hypothesis text uses.
        # Aliasing here rather than editing the regime engine keeps the engine
        # exactly as it was validated in Phase B.
        out["oi_percentile"] = out["oi_percentile_288"]
        out["oi_slope"] = _slope(oi_series, PERCENTILE_WINDOW)
        out["oi_acceleration"] = out["oi_slope"].diff(48)
        out["open_interest_available"] = out["open_interest"].notna()
        attach["open_interest"] = join.as_dict()

    # ---- funding: 8h events, causal as-of -------------------------------
    events = _funding_events(symbol)
    if events is not None:
        events = events.sort_values("settlement_time").reset_index(drop=True)
        rate = pd.to_numeric(events["funding_rate"], errors="coerce")
        derived = pd.DataFrame(
            {
                "settlement_time": events["settlement_time"],
                "funding_rate": rate,
                "funding_zscore": _expanding_zscore(rate),
                "funding_percentile": _expanding_rank(rate),
                "funding_change": rate.diff(),
            }
        )
        window = 3
        derived["rolling_funding_mean"] = rate.rolling(window, min_periods=3).mean()
        derived["rolling_funding_sum"] = rate.rolling(window, min_periods=3).sum()
        join = causal_asof_join(
            out["decision_time"], derived, ["funding_rate", "funding_zscore", "funding_percentile",
                                            "funding_change", "rolling_funding_mean",
                                            "rolling_funding_sum"],
            event_time_column="settlement_time",
        )
        frame = join.frame
        out["funding_rate_last"] = frame["funding_rate"]
        for name in ("funding_zscore", "funding_percentile", "funding_change",
                     "rolling_funding_mean", "rolling_funding_sum"):
            out[name] = frame[name]
        out["funding_source_timestamp"] = frame["source_timestamp"]
        out["funding_age_seconds"] = frame["age_seconds"]
        out["funding_available"] = out["funding_rate_last"].notna()
        attach["funding"] = join.as_dict()
    else:
        for name in ("funding_rate_last", "funding_zscore", "funding_percentile",
                     "funding_change", "rolling_funding_mean", "rolling_funding_sum"):
            out[name] = np.nan
        out["funding_available"] = False

    # ---- index and mark: causal as-of, then a derived basis -------------
    index = _load(symbol, "index_price", "1h")
    mark = _load(symbol, "mark_price", "1h")
    if index is not None and mark is not None:
        index = index.sort_values("timestamp")
        mark = mark.sort_values("timestamp")
        index_join = causal_asof_join(out["decision_time"], index, ["index_price"])
        mark_join = causal_asof_join(out["decision_time"], mark, ["mark_price"])
        out["index_price"] = index_join.frame["index_price"]
        out["mark_price"] = mark_join.frame["mark_price"]
        out["index_source_timestamp"] = index_join.frame["source_timestamp"]
        out["mark_source_timestamp"] = mark_join.frame["source_timestamp"]
        with np.errstate(divide="ignore", invalid="ignore"):
            out["basis"] = out["mark_price"] / out["index_price"] - 1.0
        out["basis"] = out["basis"].replace([np.inf, -np.inf], np.nan)
        out["basis_zscore"] = _trailing_zscore(out["basis"], PERCENTILE_WINDOW)
        out["basis_percentile"] = _trailing_rank(out["basis"], PERCENTILE_WINDOW)
        out["basis_change"] = out["basis"].diff()
        out["mark_index_spread"] = out["mark_price"] - out["index_price"]
        out["basis_available"] = out["basis"].notna()
        attach["index_price"] = index_join.as_dict()
        attach["mark_price"] = mark_join.as_dict()
    else:
        for name in ("index_price", "mark_price", "basis", "basis_zscore",
                     "basis_percentile", "basis_change", "mark_index_spread"):
            out[name] = np.nan
        out["basis_available"] = False

    # ---- forward returns and excursions ---------------------------------
    # Computed once for every horizon: the caller would otherwise rebuild the
    # whole shift for each one.
    forward = forward_returns(out, FORWARD_HORIZON_BARS)
    for column in forward.columns:
        out[column] = forward[column]
    excursions = excursion_features(out, (12, 24))
    for column in excursions.columns:
        out[column] = excursions[column]

    out["timeframe"] = timeframe
    out["symbol"] = symbol
    out["bar_minutes"] = minutes
    out["region"] = region
    if region == "final_holdout":
        # Recorded, not assumed: these rows exist so the trailing windows are
        # defined, and they are excluded from every count.
        out["is_warmup"] = out["decision_time"] < pd.Timestamp(partition.holdout_start)
    else:
        out["is_warmup"] = False

    return DiscoveryFrame(
        symbol=symbol,
        timeframe=timeframe,
        frame=out,
        funding_events=events if events is not None else pd.DataFrame(),
        partition=partition,
        attach_report=attach,
    )


def _expanding_zscore(series: pd.Series) -> pd.Series:
    mean = series.expanding(min_periods=EXPANDING_MIN_EVENTS).mean()
    std = series.expanding(min_periods=EXPANDING_MIN_EVENTS).std(ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        zscore = (series - mean) / std
    return zscore.replace([np.inf, -np.inf], np.nan)


def _expanding_rank(series: pd.Series) -> pd.Series:
    return series.expanding(min_periods=EXPANDING_MIN_EVENTS).rank(pct=True) * 100.0


def with_regime(discovery: DiscoveryFrame) -> DiscoveryFrame:
    """Attach the validated regime columns to a discovery frame."""

    regimes = classify(discovery.frame)
    additions = {
        column: regimes[column].to_numpy()
        for column in regimes.columns
        if column not in ("decision_time", "date") and column not in discovery.frame.columns
    }
    # One concat rather than many inserts: assigning a hundred columns one at a
    # time fragments the block manager and turns a two-second build into a
    # thirty-second one.
    discovery.frame = pd.concat([discovery.frame, pd.DataFrame(additions, index=discovery.frame.index)], axis=1)
    return discovery


def with_reference(
    discovery: DiscoveryFrame, reference: DiscoveryFrame
) -> DiscoveryFrame:
    """Attach a reference asset's regime and relative strength, causally."""

    from tools.strategy_factory_v2.regime import attach_reference_regime

    merged = attach_reference_regime(
        discovery.frame, reference.frame, reference.symbol
    )
    for column in merged.columns:
        if column not in discovery.frame.columns:
            discovery.frame[column] = merged[column].to_numpy()
    for column in list(discovery.frame.columns):
        if column.startswith("reference_") and column not in merged:
            discovery.frame.drop(columns=[column], inplace=True)
    if "reference_trend_percentile" in merged:
        discovery.frame["reference_trend_percentile"] = merged[
            "reference_trend_percentile"
        ].to_numpy()
        discovery.frame["reference_ret_24"] = _reference_return(reference, discovery)
    discovery.frame["relative_strength"] = relative_strength(discovery.frame)
    discovery.frame["pullback_depth"] = (
        discovery.frame["ret_24"].abs() / discovery.frame["realized_vol_30"].abs()
    )
    discovery.frame = discovery.frame.copy()
    return discovery


def _reference_return(reference: DiscoveryFrame, discovery: DiscoveryFrame) -> pd.Series:
    """The reference asset's own return at the same decision time, causally."""

    ref = reference.frame.loc[:, ["decision_time", "ret_24"]].sort_values("decision_time")
    join = causal_asof_join(
        discovery.frame["decision_time"], ref, ["ret_24"], event_time_column="decision_time"
    )
    return join.frame["ret_24"].reset_index(drop=True)


def higher_timeframe_regime(
    symbol: str,
    timeframe: str,
    partition: H.DataPartition,
    decision_times: pd.Series,
) -> pd.Series:
    """The next-higher-timeframe trend regime, attached causally.

    A higher-timeframe bar is actionable only once it has closed, so the join
    runs on the higher timeframe's ``decision_time``: a 1h bar labelled 08:00 is
    usable from 09:00, not from 08:00. Joining on the *label* instead would
    hand every 15m bar a higher-timeframe state that had not finished forming.
    """

    ladder = {"15m": "1h", "1h": "4h"}
    higher = ladder.get(timeframe)
    if higher is None:
        return pd.Series("UNKNOWN", index=decision_times.index, dtype="object")
    try:
        reference = with_regime(
            build_discovery_frame(symbol, higher, partition, "development")
        )
    except (FileNotFoundError, ValueError):
        return pd.Series("UNKNOWN", index=decision_times.index, dtype="object")
    join = causal_asof_join(
        decision_times,
        reference.frame.loc[:, ["decision_time", "trend_regime"]],
        ["trend_regime"],
        event_time_column="decision_time",
    )
    return join.frame["trend_regime"].reset_index(drop=True)
