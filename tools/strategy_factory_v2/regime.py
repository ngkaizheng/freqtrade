"""Phase B -- the deterministic, interpretable market-regime engine.

The classifier is deliberately rule-based. The plan forbids training a model
here, and more importantly a learned regime label cannot be explained to anyone
who asks *why* a bar was classified the way it was. Every state below is a
published percentile cut on a published statistic.

Two conventions run through the whole module:

* **Percentiles, not absolutes.** A funding rate of 0.05% is extreme for BTC and
  unremarkable for a low-fee alt. Ranking inside each symbol's own trailing
  distribution is what makes symbols comparable at all.
* **Trailing only.** Each percentile is the rank of the current value within
  its own past window, so a bar's regime is fixed at that bar's close and can
  never be revised by later data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from tools.strategy_factory_v2.features import _trailing_rank
from tools.strategy_factory_v2.spec import (
    FUNDING_PERCENTILE_CUTS,
    LIQUIDITY_PERCENTILE_CUTS,
    OI_PERCENTILE_CUTS,
    PERCENTILE_WINDOW,
    TREND_SCORE_CUTS as _TREND_SCORE_CUTS,
    VOL_PERCENTILE_CUTS,
)

#: Trend state boundaries, in units of the normalised trend score. Five
#: symmetric states need four cut points; these are preregistered, not fitted.
#: See ``spec.TREND_SCORE_CUTS`` for why the trend is *not* classified by a
#: trailing percentile while the other four regimes are.
TREND_SCORE_CUTS = _TREND_SCORE_CUTS
#: The volatility window whose percentile drives the volatility regime.
VOL_REGIME_WINDOW = 30
#: Equal weight on the normalised move and the normalised moving-average
#: structure. Fixed here so it cannot be tuned after results exist.
TREND_MOVE_WEIGHT = 0.5
TREND_STRUCTURE_WEIGHT = 0.5

TREND_STATES = ("STRONG_DOWN", "WEAK_DOWN", "NEUTRAL", "WEAK_UP", "STRONG_UP")
VOL_STATES = ("LOW_VOL", "NORMAL_VOL", "HIGH_VOL", "EXTREME_VOL")
LIQUIDITY_STATES = ("LOW_LIQUIDITY", "NORMAL_LIQUIDITY", "HIGH_LIQUIDITY")
OI_STATES = ("OI_LOW", "OI_NORMAL", "OI_HIGH", "OI_EXTREME")
FUNDING_STATES = (
    "FUNDING_NEG_EXTREME",
    "FUNDING_NEG",
    "FUNDING_NEUTRAL",
    "FUNDING_POS",
    "FUNDING_POS_EXTREME",
)
#: A state used where the underlying data does not exist at all. Reporting
#: UNKNOWN is required; silently defaulting to NEUTRAL would let a missing
#: open-interest feed masquerade as a genuine mid-range reading.
UNKNOWN = "UNKNOWN"

REGIME_COLUMNS = (
    "trend_regime",
    "volatility_regime",
    "liquidity_regime",
    "oi_regime",
    "funding_regime",
)


def _cut(percentile: pd.Series, cuts: tuple[float, ...], labels: tuple[str, ...]) -> pd.Series:
    """Bucket a percentile series into ordered labels.

    ``cuts`` is ascending and must have exactly one fewer entry than
    ``labels``. Rows without a percentile (warm-up, or data that does not
    exist) are UNKNOWN, never a middle bucket -- silently calling missing
    open interest "OI_NORMAL" would let an absent feed look like a measured
    market state.
    """

    if len(labels) != len(cuts) + 1:
        raise ValueError(
            f"cuts {cuts} and labels {labels} are inconsistent: "
            f"expected {len(cuts) + 1} labels, got {len(labels)}"
        )
    values = percentile.to_numpy(dtype=float)
    buckets = np.digitize(values, np.asarray(cuts, dtype=float), right=False)
    state = np.asarray(labels, dtype=object)[buckets]
    state[~np.isfinite(values)] = UNKNOWN
    return pd.Series(state, index=percentile.index, dtype="object")


def trend_score(frame: pd.DataFrame) -> pd.Series:
    """Volatility-normalised blend of recent move and moving-average structure.

    Both terms are scaled by realised volatility so they are directly
    comparable, and both are in units of "standard deviations of move". This
    makes the score comparable across symbols and across market states without
    any per-symbol calibration constant.
    """

    minutes = float(frame["bar_minutes"].iloc[0]) if "bar_minutes" in frame else 1.0
    annual_bars = 365.0 * 24.0 * 60.0 / minutes
    realised = frame.get(f"realized_vol_{VOL_REGIME_WINDOW}")
    if realised is None:
        raise KeyError(f"realized_vol_{VOL_REGIME_WINDOW} is required by the trend score")
    scale = realised * np.sqrt(24.0 / annual_bars)
    with np.errstate(divide="ignore", invalid="ignore"):
        move = frame["ret_24"] / scale
        structure = frame["ema_spread_50_200"] / scale
    score = TREND_MOVE_WEIGHT * move + TREND_STRUCTURE_WEIGHT * structure
    return score.replace([np.inf, -np.inf], np.nan)


def classify_trend(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Return ``(score, trailing percentile, state)`` for the trend regime.

    The state comes from the score's absolute position against the preregistered
    cut points. The trailing percentile is still returned, but only as a
    diagnostic: it is reported for cross-symbol comparison of *relative*
    strength, not used to label the regime, because a sustained trend
    saturates its own trailing distribution.
    """

    score = trend_score(frame)
    percentile = _trailing_rank(score, PERCENTILE_WINDOW)
    regime = _cut(score, TREND_SCORE_CUTS, TREND_STATES)
    return score, percentile, regime


def classify_volatility(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    series = frame[f"realized_vol_{VOL_REGIME_WINDOW}"]
    percentile = _trailing_rank(series, PERCENTILE_WINDOW)
    return percentile, _cut(percentile, VOL_PERCENTILE_CUTS, VOL_STATES)


def classify_liquidity(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    percentile = frame["volume_percentile"]
    return percentile, _cut(percentile, LIQUIDITY_PERCENTILE_CUTS, LIQUIDITY_STATES)


def classify_open_interest(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    if "open_interest" not in frame or frame["open_interest"].isna().all():
        empty = pd.Series(np.nan, index=frame.index, dtype=float)
        return empty, pd.Series(UNKNOWN, index=frame.index, dtype="object")
    percentile = frame["oi_percentile"]
    if not np.isfinite(percentile.to_numpy(dtype=float)).any():
        return percentile, pd.Series(UNKNOWN, index=frame.index, dtype="object")
    return percentile, _cut(percentile, OI_PERCENTILE_CUTS, OI_STATES)


def classify_funding(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    if "funding_percentile" not in frame or frame["funding_percentile"].isna().all():
        return (
            pd.Series(np.nan, index=frame.index, dtype=float),
            pd.Series(UNKNOWN, index=frame.index, dtype="object"),
        )
    percentile = frame["funding_percentile"]
    if not np.isfinite(percentile.to_numpy(dtype=float)).any():
        return percentile, pd.Series(UNKNOWN, index=frame.index, dtype="object")
    return percentile, _cut(percentile, FUNDING_PERCENTILE_CUTS, FUNDING_STATES)


def classify(frame: pd.DataFrame) -> pd.DataFrame:
    """Return the five regime columns plus their driving percentiles.

    The identifying columns of the input (``decision_time``, ``symbol``,
    ``timeframe``) are carried through unchanged so the result can be joined
    back onto the price grid or onto another symbol's bars.
    """

    out = pd.DataFrame(index=frame.index)
    for name in ("decision_time", "date", "symbol", "timeframe", "bar_minutes"):
        if name in frame.columns:
            out[name] = frame[name].to_numpy()
    score, trend_pct, trend_state = classify_trend(frame)
    out["trend_score"] = score
    out["trend_percentile"] = trend_pct
    out["trend_regime"] = trend_state

    vol_pct, vol_state = classify_volatility(frame)
    out["volatility_percentile"] = vol_pct
    out["volatility_regime"] = vol_state

    liq_pct, liq_state = classify_liquidity(frame)
    out["liquidity_percentile"] = liq_pct
    out["liquidity_regime"] = liq_state

    oi_pct, oi_state = classify_open_interest(frame)
    out["oi_percentile_trail"] = oi_pct
    out["oi_regime"] = oi_state

    funding_pct, funding_state = classify_funding(frame)
    out["funding_percentile_trail"] = funding_pct
    out["funding_regime"] = funding_state

    out["market_state"] = market_state(out)
    return out


def market_state(regimes: pd.DataFrame) -> pd.Series:
    """The combined state string, e.g. ``STRONG_UP+HIGH_VOL+UNKNOWN+UNKNOWN``."""

    columns = [regimes[name].astype(str) for name in REGIME_COLUMNS]
    joined = columns[0]
    for column in columns[1:]:
        joined = joined + "+" + column
    return joined


def attach_reference_regime(
    frame: pd.DataFrame,
    reference: pd.DataFrame,
    reference_symbol: str = "BTC/USDT:USDT",
) -> pd.DataFrame:
    """Merge a reference asset's regime onto another symbol's bars.

    The join is a strictly backward as-of on ``decision_time``, so an alt's bar
    at decision time *t* can only see the BTC regime that was already true at
    *t*. A naive ``merge`` on a rounded timestamp would leak, and a
    ``resample('1h').last()`` without a shift would leak by a whole bar.
    """

    from tools.strategy_factory_v2.data import asof_join

    # Accept either a feature frame or an already-classified regime frame.
    if not all(name in reference.columns for name in REGIME_COLUMNS):
        reference = classify(reference)
    if "decision_time" not in reference.columns or "decision_time" not in frame.columns:
        # A missing join key is a programming error, not a data condition.
        # Returning UNKNOWN here would make a bug indistinguishable from an
        # absent market state, which is precisely the confusion V2 forbids.
        raise ValueError(
            "attach_reference_regime requires a decision_time column on both the "
            "symbol frame and the reference frame; missing on "
            f"{sorted(set(frame.columns) ^ set(reference.columns)) or 'one of them'}"
        )
    if reference.empty:
        for name in REGIME_COLUMNS:
            frame[f"reference_{name}"] = UNKNOWN
        frame["reference_symbol"] = reference_symbol
        return frame

    right = reference[["decision_time", *REGIME_COLUMNS, "trend_percentile"]].copy()
    right = right.sort_values("decision_time", kind="stable")
    joined = asof_join(
        frame[["decision_time"]].reset_index(drop=True),
        right,
        "decision_time",
        "decision_time",
        "reference_",
    ).reset_index(drop=True)

    result = frame.copy()
    for name in REGIME_COLUMNS:
        column = joined.get(f"reference_{name}")
        result[f"reference_{name}"] = (
            column.to_numpy() if column is not None else np.full(len(result), UNKNOWN, dtype=object)
        )
    trend_pct = joined.get("reference_trend_percentile")
    result["reference_trend_percentile"] = (
        pd.to_numeric(trend_pct, errors="coerce").to_numpy()
        if trend_pct is not None
        else np.full(len(result), np.nan)
    )
    result["reference_symbol"] = reference_symbol
    return result


def relative_strength(frame: pd.DataFrame) -> pd.Series:
    """Asset return minus reference return over the preregistered horizons.

    A positive value means the asset has outrun the reference over that window,
    which is what makes "divergence" a measurable statement rather than two
    independent trend labels that happen to disagree.
    """

    reference = pd.to_numeric(frame.get("reference_ret_24"), errors="coerce")
    own = pd.to_numeric(frame.get("ret_24"), errors="coerce")
    with np.errstate(divide="ignore", invalid="ignore"):
        out = own - reference
    return out.replace([np.inf, -np.inf], np.nan)


def regime_distribution(regimes: pd.DataFrame) -> pd.DataFrame:
    """Share of bars in each state, for the regime-stability report."""

    rows: list[dict[str, object]] = []
    total = max(len(regimes), 1)
    for name in REGIME_COLUMNS:
        counts = regimes[name].value_counts(dropna=False)
        for state, count in counts.items():
            rows.append(
                {
                    "regime": name,
                    "state": str(state),
                    "bars": int(count),
                    "share": round(float(count) / total, 6),
                }
            )
    return pd.DataFrame(rows, columns=["regime", "state", "bars", "share"])
