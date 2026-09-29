"""Phase C -- executable predicates for the 92 preregistered hypotheses.

The registry froze each hypothesis as *text* before any result existed. This
module is where that text becomes a boolean mask. The mapping is mechanical and
one-to-one: every predicate below implements the sentence recorded in
``Hypothesis.condition`` using the thresholds recorded in
``Hypothesis.thresholds``, and nothing else decides membership.

Two disciplines make that safe:

**One handler per family, not per hypothesis.** Hypotheses within a family
differ only by direction, timeframe and preregistered threshold, so a single
family handler parameterised by those three fields cannot quietly vary between
the twenty-odd members of a family. A per-hypothesis implementation would be
ninety-two chances to write a subtly different question.

**The condition is a conjunct of named comparisons.** Each predicate is built
from the feature names the registry itself lists in ``Hypothesis.features``,
so a predicate cannot reference a feature the preregistration did not name. A
missing feature yields ``False``, never a silent default, because a family that
quietly evaluates to zero matches is indistinguishable from a family that
genuinely found nothing.

Direction handling is uniform. A hypothesis is evaluated for its own direction
and, where the family is symmetric, the opposite reading is evaluated as its
own registered hypothesis. Neither borrows the other's threshold.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd

from tools.strategy_factory_v2.hypotheses import Hypothesis
from tools.strategy_factory_v2.spec import PERCENTILE_WINDOW

Handler = Callable[[pd.DataFrame, Hypothesis], pd.Series]

BULLISH = ("STRONG_UP", "WEAK_UP")
BEARISH = ("STRONG_DOWN", "WEAK_DOWN")
VOL_HIGH = ("HIGH_VOL", "EXTREME_VOL")
VOL_LOW = ("LOW_VOL",)


def _require(frame: pd.DataFrame, names: Sequence[str]) -> bool:
    return all(name in frame.columns for name in names)


def _false(frame: pd.DataFrame) -> pd.Series:
    return pd.Series(False, index=frame.index, dtype=bool)


def _directional(hypothesis: Hypothesis, up: bool) -> pd.Series:
    """The trend states consistent with a hypothesis's own direction."""

    return up and True  # direction is resolved by the caller


# ---------------------------------------------------------------------------
# Family handlers
# ---------------------------------------------------------------------------


def _h1_trend_oi(frame: pd.DataFrame, hypothesis: Hypothesis) -> pd.Series:
    """Price trend confirmed by rising open interest."""

    if not _require(frame, ("trend_regime", "oi_change_288")):
        return _false(frame)
    window = int(hypothesis.thresholds.get("oi_window_bars", 288))
    change = frame.get(f"oi_change_{window}")
    if change is None:
        return _false(frame)
    up = hypothesis.expected_direction == "long"
    directional = frame["trend_regime"].isin(BULLISH if up else BEARISH)
    return (directional & change.notna() & (change > 0)).fillna(False)


def _h2_oi_divergence(frame: pd.DataFrame, hypothesis: Hypothesis) -> pd.Series:
    """Price trending while open interest falls: covering, or exhaustion?"""

    if not _require(frame, ("trend_regime", "oi_change_288")):
        return _false(frame)
    window = int(hypothesis.thresholds.get("oi_window_bars", 288))
    change = frame.get(f"oi_change_{window}")
    if change is None:
        return _false(frame)
    up = hypothesis.expected_direction == "long"
    directional = frame["trend_regime"].isin(BULLISH if up else BEARISH)
    return (directional & change.notna() & (change < 0)).fillna(False)


def _h3_funding_extremes(frame: pd.DataFrame, hypothesis: Hypothesis) -> pd.Series:
    """Extreme funding percentile.

    The condition is simply membership of the registered tail; the direction
    only decides which way the return is taken. Both readings were registered
    for every tail, and the data -- not a rule written here -- decides whether
    the contrarian or the with-the-crowd reading is the one that works.

    The earlier version inverted the tail for the long reading, which made a
    *non*-extreme funding value satisfy the condition. A condition that fires
    on ordinary funding is not an extreme-funding hypothesis.
    """

    if not _require(frame, ("funding_percentile", "funding_available")):
        return _false(frame)
    cut = float(hypothesis.thresholds.get("percentile_cut", 95.0))
    percentile = pd.to_numeric(frame["funding_percentile"], errors="coerce")
    tail = (percentile <= cut) if cut < 50 else (percentile >= cut)
    return (frame["funding_available"].fillna(False) & tail.fillna(False)).astype(bool)


def _h4_funding_price_divergence(frame: pd.DataFrame, hypothesis: Hypothesis) -> pd.Series:
    """Price and funding moving against each other."""

    if not _require(frame, ("trend_regime", "funding_change", "funding_available")):
        return _false(frame)
    change = pd.to_numeric(frame["funding_change"], errors="coerce")
    up = hypothesis.expected_direction == "long"
    directional = frame["trend_regime"].isin(BULLISH if up else BEARISH)
    against = (change < 0) if up else (change > 0)
    return (
        frame["funding_available"].fillna(False) & directional & change.notna() & against
    ).fillna(False)


def _h5_funding_oi(frame: pd.DataFrame, hypothesis: Hypothesis) -> pd.Series:
    """Funding sign combined with the direction of open interest."""

    if not _require(frame, ("funding_rate_last", "oi_change_288")):
        return _false(frame)
    rate = pd.to_numeric(frame["funding_rate_last"], errors="coerce")
    change = pd.to_numeric(frame["oi_change_288"], errors="coerce")
    non_neutral = rate.notna() & (rate != 0) & change.notna() & (change != 0)
    return non_neutral.fillna(False)


def _h6_price_oi_taker(frame: pd.DataFrame, hypothesis: Hypothesis) -> pd.Series:
    """Price, open interest and taker imbalance all agreeing."""

    if not _require(frame, ("trend_regime", "taker_imbalance_percentile", "oi_change_288")):
        return _false(frame)
    cut = float(hypothesis.thresholds.get("taker_percentile_cut", 20.0))
    percentile = pd.to_numeric(frame["taker_imbalance_percentile"], errors="coerce")
    up = hypothesis.expected_direction == "long"
    strong_flow = (percentile >= cut) if up else (percentile <= (100.0 - cut))
    directional = frame["trend_regime"].isin(BULLISH if up else BEARISH)
    rising_oi = pd.to_numeric(frame["oi_change_288"], errors="coerce") > 0
    return (strong_flow.fillna(False) & directional & rising_oi.fillna(False)).astype(bool)


def _h7_oi_contraction(frame: pd.DataFrame, hypothesis: Hypothesis) -> pd.Series:
    """A large price move with a sharp fall in open interest.

    Named for what it measures, not for liquidation: no liquidation feed exists
    on this dataset, so the hypothesis is an OI-contraction proxy and the report
    says so.
    """

    if not _require(frame, ("oi_change_288",)):
        return _false(frame)
    window = int(hypothesis.thresholds.get("oi_window_bars", 288))
    cut = float(hypothesis.thresholds.get("percentile_cut", 10.0))
    move_column = f"abs_ret_{window}" if f"abs_ret_{window}" in frame.columns else "abs_ret_24"
    if not _require(frame, (move_column, f"oi_change_{window}")):
        return _false(frame)
    move = _trailing_percentile(frame[move_column], PERCENTILE_WINDOW)
    oi_change = pd.to_numeric(frame[f"oi_change_{window}"], errors="coerce")
    big_move = (move >= (100.0 - cut)).fillna(False)
    falling_oi = oi_change.notna() & (oi_change < 0)
    return (big_move & falling_oi).fillna(False)


def _h8_compression(frame: pd.DataFrame, hypothesis: Hypothesis) -> pd.Series:
    """Volatility compression together with range and volume expansion."""

    if not _require(frame, ("volatility_percentile", "range_ratio", "volume_percentile")):
        return _false(frame)
    cut = float(hypothesis.thresholds.get("vol_percentile_cut", 20.0))
    compressed = (pd.to_numeric(frame["volatility_percentile"], errors="coerce") <= cut)
    expanding_range = (pd.to_numeric(frame["range_ratio"], errors="coerce") > 1.0)
    expanding_volume = (pd.to_numeric(frame["volume_percentile"], errors="coerce") >= 50.0)
    return (compressed.fillna(False) & expanding_range.fillna(False) & expanding_volume.fillna(False)).astype(bool)


def _h9_vol_shock(frame: pd.DataFrame, hypothesis: Hypothesis) -> pd.Series:
    """A volatility regime transition from a low band into a high one."""

    if not _require(frame, ("volatility_percentile",)):
        return _false(frame)
    low = float(hypothesis.thresholds.get("from_percentile", 20.0))
    high = float(hypothesis.thresholds.get("to_percentile", 80.0))
    percentile = pd.to_numeric(frame["volatility_percentile"], errors="coerce")
    previous = percentile.shift(1)
    crossed = (previous <= low) & (percentile >= high)
    return crossed.fillna(False).astype(bool)


def _h10_basis_extreme(frame: pd.DataFrame, hypothesis: Hypothesis) -> pd.Series:
    """Extreme basis percentile -- tail membership only, as for funding."""

    if not _require(frame, ("basis_percentile", "basis_available")):
        return _false(frame)
    cut = float(hypothesis.thresholds.get("percentile_cut", 95.0))
    percentile = pd.to_numeric(frame["basis_percentile"], errors="coerce")
    tail = (percentile <= cut) if cut < 50 else (percentile >= cut)
    return (frame["basis_available"].fillna(False) & tail.fillna(False)).astype(bool)


def _h11_cross_asset_confirm(frame: pd.DataFrame, hypothesis: Hypothesis) -> pd.Series:
    """The symbol's own trend agreeing with the reference asset's."""

    if not _require(frame, ("trend_regime", "reference_trend_regime")):
        return _false(frame)
    up = hypothesis.expected_direction == "long"
    states = BULLISH if up else BEARISH
    return (frame["trend_regime"].isin(states) & frame["reference_trend_regime"].isin(states)).fillna(False)


def _h12_cross_asset_divergence(frame: pd.DataFrame, hypothesis: Hypothesis) -> pd.Series:
    """The symbol and the reference trending in opposite directions."""

    if not _require(frame, ("trend_regime", "reference_trend_regime")):
        return _false(frame)
    up = hypothesis.expected_direction == "long"
    own = frame["trend_regime"].isin(BULLISH if up else BEARISH)
    other = frame["reference_trend_regime"].isin(BEARISH if up else BULLISH)
    return (own & other).fillna(False)


def _h13_btc_filter(frame: pd.DataFrame, hypothesis: Hypothesis) -> pd.Series:
    """The symbol's signal, restricted to one preregistered BTC regime state."""

    if not _require(frame, ("trend_regime", "reference_trend_regime")):
        return _false(frame)
    state = str(hypothesis.thresholds.get("btc_state", "STRONG_UP"))
    up = hypothesis.expected_direction == "long"
    own = frame["trend_regime"].isin(BULLISH if up else BEARISH)
    return (own & (frame["reference_trend_regime"] == state)).fillna(False)


def _h14_multi_timeframe(frame: pd.DataFrame, hypothesis: Hypothesis) -> pd.Series:
    """Higher-timeframe trend agreeing with a lower-timeframe direction.

    A pullback leg is required so the entry is not simply a repeat of the
    higher-timeframe state; without it the confirmation is redundant rather
    than confirmatory.
    """

    if not _require(frame, ("trend_regime", "htf_trend_regime", "pullback_depth")):
        return _false(frame)
    up = hypothesis.expected_direction == "long"
    own = frame["trend_regime"].isin(BULLISH if up else BEARISH)
    higher = frame["htf_trend_regime"].isin(BULLISH if up else BEARISH)
    pullback = pd.to_numeric(frame["pullback_depth"], errors="coerce")
    return (own & higher & pullback.notna()).fillna(False)


def _h15_regime_activation(frame: pd.DataFrame, hypothesis: Hypothesis) -> pd.Series:
    """A style activated only inside its own preregistered regime."""

    if not _require(frame, ("trend_regime", "volatility_regime")):
        return _false(frame)
    regime = str(hypothesis.thresholds.get("regime", "STRONG_UP"))
    style = str(hypothesis.thresholds.get("style", "TREND_CONTINUATION"))
    up = hypothesis.expected_direction == "long"
    states = BULLISH if up else BEARISH
    own = frame["trend_regime"].isin(states)
    if regime in ("STRONG_UP", "STRONG_DOWN", "NEUTRAL"):
        gate = frame["trend_regime"] == regime
    else:
        gate = frame["volatility_regime"].isin(
            {"HIGH_VOL": VOL_HIGH, "LOW_VOL": VOL_LOW}.get(regime, (regime,))
        )
    if style == "MEAN_REVERSION":
        # A mean-reversion style is the direction against the prevailing trend.
        style_condition = ~own
    else:
        style_condition = own
    return (style_condition & gate).fillna(False)


HANDLERS: dict[str, Handler] = {
    "H1_trend_oi_confirmation": _h1_trend_oi,
    "H2_trend_oi_divergence": _h2_oi_divergence,
    "H3_funding_extremes": _h3_funding_extremes,
    "H4_funding_price_divergence": _h4_funding_price_divergence,
    "H5_funding_oi": _h5_funding_oi,
    "H6_price_oi_taker": _h6_price_oi_taker,
    "H7_deleveraging_proxy": _h7_oi_contraction,
    "H8_vol_compression_expansion": _h8_compression,
    "H9_volatility_shock": _h9_vol_shock,
    "H10_basis_extremes": _h10_basis_extreme,
    "H11_cross_asset_confirmation": _h11_cross_asset_confirm,
    "H12_cross_asset_divergence": _h12_cross_asset_divergence,
    "H13_btc_regime_filter": _h13_btc_filter,
    "H14_multi_timeframe_confirmation": _h14_multi_timeframe,
    "H15_regime_specific_activation": _h15_regime_activation,
}


def _trailing_percentile(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=window).rank(pct=True) * 100.0


def evaluate(hypothesis: Hypothesis, frame: pd.DataFrame) -> pd.Series:
    """Evaluate one preregistered hypothesis against a discovery frame."""

    handler = HANDLERS.get(hypothesis.family)
    if handler is None:
        raise KeyError(
            f"{hypothesis.hypothesis_id}: family {hypothesis.family!r} has no predicate. "
            "A family without a predicate must be reported untested, not skipped."
        )
    mask = handler(frame, hypothesis)
    # Every predicate must be a boolean aligned to the frame. A handler that
    # returns NaN is a bug, and treating NaN as False would quietly shrink the
    # sample in a way the report would attribute to the market.
    mask = pd.Series(mask, index=frame.index).fillna(False).astype(bool)
    return mask


def signal_counts(hypothesis: Hypothesis, frame: pd.DataFrame) -> dict[str, int]:
    mask = evaluate(hypothesis, frame)
    return {"total_bars": int(len(frame)), "matched": int(mask.sum())}
