"""The pre-registered V2 hypothesis registry.

This module is the *contract* for what V2 is allowed to test. It is written
before any conditional-return result exists and it is frozen: changing any entry
requires a new spec version and a new run directory, never an edit in place.

The central discipline of V2 is that **every hypothesis declares the data fields
it needs**. A hypothesis whose fields are not on disk is reported ``BLOCKED``.
It is never approximated with a proxy, never silently dropped, and never
silently re-scoped to a weaker question. An honest ``BLOCKED`` is a research
result; a quietly weakened hypothesis is not.

Registry contents are declarative only. Evaluation of the conditions is Phase C
work; what exists now is the frozen specification those evaluators must match.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from tools.strategy_factory_v2.spec import (
    FORWARD_HORIZONS_BARS,
    PERCENTILE_WINDOW,
    DISCOVERY_TIMEFRAMES,
    SPEC_VERSION,
    TAKER_FLOW_WINDOWS,
    TAKER_IMBALANCE_CUTS,
    VOL_PERCENTILE_CUTS,
)

#: Canonical data-field vocabulary. A hypothesis may only require these names.
PRICE = "price"
VOLUME = "volume"
FUNDING = "funding_rate"
OPEN_INTEREST = "open_interest"
MARK = "mark_price"
INDEX = "index_price"
TAKER = "taker_flow"
CROSS_ASSET = "cross_asset"

CANONICAL_FIELDS = (
    PRICE,
    VOLUME,
    FUNDING,
    OPEN_INTEREST,
    MARK,
    INDEX,
    TAKER,
    CROSS_ASSET,
)

#: Verdicts a hypothesis can receive in Phase C.
TESTABLE = "TESTABLE"
BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class Hypothesis:
    """One preregistered conditional-return question.

    ``condition`` is deliberately a *description* rather than executable code.
    Writing the reasoning down before seeing results is the point; a predicate
    that could be edited after the fact would defeat the whole exercise. Phase C
    compiles these descriptions into boolean masks and asserts that the compiled
    condition still matches this text.
    """

    hypothesis_id: str
    family: str
    economic_reason: str
    features: tuple[str, ...]
    required_fields: tuple[str, ...]
    timeframe: str
    entry_definition: str
    exit_definition: str
    thresholds: dict[str, Any]
    expected_direction: str
    condition: str
    direction_mirrored: bool = False
    preregistered: bool = True
    invalidation: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["spec_version"] = SPEC_VERSION
        return payload

    def requires(self, field_name: str) -> bool:
        return field_name in self.required_fields


def _both_directions(
    hypothesis_id: str,
    family: str,
    economic_reason: str,
    features: tuple[str, ...],
    required_fields: tuple[str, ...],
    timeframe: str,
    condition: str,
    thresholds: dict[str, Any],
    invalidation: str,
) -> list[Hypothesis]:
    """A condition is registered for its long reading and its short mirror.

    Direction is never assumed. Plan section 22 requires both directions to be
    researched, and section 23 warns that the intuitive interpretation
    (continuation vs exhaustion) may be wrong. Measuring both is how the data
    gets to decide.
    """

    return [
        Hypothesis(
            hypothesis_id=f"{hypothesis_id}_LONG",
            family=family,
            economic_reason=economic_reason,
            features=features,
            required_fields=required_fields,
            timeframe=timeframe,
            entry_definition="evaluate the conditional return at the next bar open after the signal",
            exit_definition="not applicable in the research layer; exits are a Phase C conversion",
            thresholds=dict(thresholds),
            expected_direction="long",
            condition=condition,
            direction_mirrored=False,
            invalidation=invalidation,
        ),
        Hypothesis(
            hypothesis_id=f"{hypothesis_id}_SHORT",
            family=family,
            economic_reason=(
                f"{economic_reason} Registered as the short mirror so the data, "
                "not the narrative, decides between continuation and exhaustion."
            ),
            features=features,
            required_fields=required_fields,
            timeframe=timeframe,
            entry_definition="evaluate the conditional return at the next bar open after the signal",
            exit_definition="not applicable in the research layer; exits are a Phase C conversion",
            thresholds=dict(thresholds),
            expected_direction="short",
            condition=condition,
            direction_mirrored=True,
            invalidation=invalidation,
        ),
    ]


_NO_EXIT = "not applicable in the research layer; exits are a Phase C conversion"
_ENTRY = "evaluate the conditional return at the next bar open after the signal"


def _build_registry() -> tuple[Hypothesis, ...]:
    out: list[Hypothesis] = []

    def add(hypothesis_id: str, family: str, reason: str, features, required, tf, cond, thr, inval) -> None:
        for side in ("LONG", "SHORT"):
            out.append(
                Hypothesis(
                    hypothesis_id=f"{hypothesis_id}_{side}",
                    family=family,
                    economic_reason=reason,
                    features=tuple(features),
                    required_fields=tuple(required),
                    timeframe=tf,
                    entry_definition=_ENTRY,
                    exit_definition=_NO_EXIT,
                    thresholds=dict(thr),
                    expected_direction="long" if side == "LONG" else "short",
                    condition=cond,
                    direction_mirrored=(side == "SHORT"),
                    invalidation=inval,
                )
            )

    # ---- H1: trend confirmed by rising open interest -----------------------
    for tf in DISCOVERY_TIMEFRAMES:
        for window in (288,):
            add(
                f"H1_OI_CONFIRM_{tf.upper()}_{window}",
                "H1_trend_oi_confirmation",
                "Rising open interest with directional price means new positions are "
                "opening in the move, which is the classic definition of a trend driven "
                "by fresh capital rather than by short covering.",
                ("trend_regime", f"oi_change_{window}", f"oi_percentile_{PERCENTILE_WINDOW}"),
                (PRICE, OPEN_INTEREST),
                tf,
                f"trend_regime is directional AND oi_change_{window} > 0",
                {"oi_window_bars": window, "percentile_window": PERCENTILE_WINDOW},
                "If OI stops moving while price keeps trending, the move is a squeeze, "
                "not a trend, and the condition no longer describes its own hypothesis.",
            )

    # ---- H2: price/OI divergence ------------------------------------------
    for tf in DISCOVERY_TIMEFRAMES:
        for window in (288,):
            add(
                f"H2_OI_DIVERGENCE_{tf.upper()}_{window}",
                "H2_trend_oi_divergence",
                "Price rising while open interest falls means longs are closing, not "
                "new longs arriving. Whether that is short covering (continuation) or "
                "long liquidation (exhaustion) is exactly what the data must decide; the "
                "plan forbids assuming the interpretation.",
                ("trend_regime", f"oi_change_{window}"),
                (PRICE, OPEN_INTEREST),
                tf,
                f"price direction is directional AND oi_change_{window} < 0",
                {"oi_window_bars": window},
                "If the divergence disappears because OI data was smoothed or "
                "interpolated, the hypothesis is untestable rather than falsified.",
            )

    # ---- H3: funding extremes ---------------------------------------------
    for tf in DISCOVERY_TIMEFRAMES:
        for cut in (5, 95):
            add(
                f"H3_FUNDING_EXTREME_{tf.upper()}_P{cut}",
                "H3_funding_extremes",
                "Extreme funding is the exchange's own price of imbalance in perpetual "
                "positioning. Positive funding means longs are crowded and paying. That "
                "is a description of a crowded trade, not a prediction, so mean "
                "reversion must be measured rather than assumed.",
                ("funding_regime", f"funding_percentile_expanding"),
                (PRICE, FUNDING),
                tf,
                f"funding expanding percentile is at or beyond the {cut}th percentile",
                {"percentile_cut": float(cut), "min_history_events": 30},
                "If funding becomes clamped at the exchange cap for most of the sample, "
                "the series stops discriminating and the family is retired.",
            )

    # ---- H4: funding vs price divergence ----------------------------------
    for tf in DISCOVERY_TIMEFRAMES:
        for window in TAKER_FLOW_WINDOWS[1:2]:
            add(
                f"H4_FUNDING_PRICE_DIVERGENCE_{tf.upper()}_{window}",
                "H4_funding_price_divergence",
                "Price and funding are set by different participants: price by the "
                "taker side, funding by the accumulated leverage imbalance. Persistent "
                "disagreement between them is an observable stress in positioning that "
                "price alone cannot show.",
                ("trend_regime", "funding_change", "funding_regime"),
                (PRICE, FUNDING),
                tf,
                f"price is directional while the {window}-event funding change moves "
                "against the price direction",
                {"funding_window_events": window},
                "If funding and price are found to be a deterministic function of each "
                "other at this horizon, the divergence carries no independent information.",
            )

    # ---- H5: funding combined with open interest ---------------------------
    for tf in DISCOVERY_TIMEFRAMES:
        for window in (288,):
            add(
                f"H5_FUNDING_OI_{tf.upper()}_{window}",
                "H5_funding_oi",
                "Funding sign and the direction of open interest together separate four "
                "distinct positioning states: new longs entering, longs closing, new "
                "shorts entering, shorts closing. Each implies a different next move.",
                ("funding_regime", f"oi_change_{window}"),
                (PRICE, FUNDING, OPEN_INTEREST),
                tf,
                f"funding sign is non-neutral AND oi_change_{window} is non-zero",
                {"oi_window_bars": window},
                "If the four quadrants are statistically indistinguishable, positioning "
                "state carries no information and the family is reported as such.",
            )

    # ---- H6: price + open interest + taker flow ---------------------------
    for tf in DISCOVERY_TIMEFRAMES:
        for cut in TAKER_IMBALANCE_CUTS:
            add(
                f"H6_OI_TAKER_{tf.upper()}_T{cut:g}",
                "H6_price_oi_taker",
                "Price, open interest and taker imbalance are three independent readings "
                "of the same trade. Agreement across all three is a much stronger claim "
                "than any one of them alone, which is why the thresholds are the only "
                "two preregistered magnitudes rather than a searched grid.",
                ("trend_regime", "taker_imbalance", f"taker_imbalance_roll_{TAKER_FLOW_WINDOWS[2]}"),
                (PRICE, OPEN_INTEREST, TAKER),
                tf,
                f"taker imbalance is beyond the {cut:.0f}th percentile of its own trailing "
                f"distribution AND oi is rising AND price is directional",
                {
                    "taker_percentile_cut": float(cut),
                    "taker_roll_window": TAKER_FLOW_WINDOWS[2],
                    "percentile_window": PERCENTILE_WINDOW,
                },
                "Taker flow is a reported exchange aggregate, not an independently "
                "verified tape. If it is derived from the same feed as volume it adds "
                "no independent information.",
            )

    # ---- H7: OI contraction after a large price move -----------------------
    for tf in DISCOVERY_TIMEFRAMES:
        for window in (288,):
            add(
                f"H7_OI_CONTRACTION_{tf.upper()}_{window}",
                "H7_deleveraging_proxy",
                "A large price move accompanied by a sharp fall in open interest is the "
                "observable signature of forced position closure. It is called an OI "
                "contraction, not a liquidation, because no liquidation feed is on disk "
                "and the plan forbids claiming a label the data cannot support.",
                ("abs_return", f"oi_change_{window}"),
                (PRICE, OPEN_INTEREST),
                tf,
                f"absolute return over the window is in the top decile AND "
                f"oi_change_{window} is in the bottom decile",
                {"oi_window_bars": window, "percentile_cut": 10.0},
                "Without actual liquidation data this remains a proxy. If a real "
                "liquidation feed later disagrees with the proxy, the family is revised "
                "under a new hypothesis id, never edited.",
            )

    # ---- H8: volatility compression then expansion -------------------------
    for tf in DISCOVERY_TIMEFRAMES:
        for cut in VOL_PERCENTILE_CUTS[:1]:
            add(
                f"H8_COMPRESSION_{tf.upper()}_P{cut:g}",
                "H8_vol_compression_expansion",
                "Low volatility followed by range and volume expansion is a stored-energy "
                "release. Whether the release continues as a breakout or reverts into the "
                "range is a genuine empirical question, so the breakout direction is not "
                "imposed at signal time.",
                ("vol_percentile", "range_ratio", "volume_percentile"),
                (PRICE, VOLUME),
                tf,
                f"vol_percentile is at or below {cut:g} and the current bar expands both "
                "range and volume versus the trailing distribution",
                {
                    "vol_percentile_cut": float(cut),
                    "range_window": 48,
                    "percentile_window": PERCENTILE_WINDOW,
                },
                "If the compression measure is dominated by microstructure noise at this "
                "timeframe, the family is not testable here.",
            )

    # ---- H9: volatility shock transitions ----------------------------------
    for tf in DISCOVERY_TIMEFRAMES:
        for low, high in ((20.0, 80.0), (20.0, 95.0)):
            add(
                f"H9_VOL_SHOCK_{tf.upper()}_{low:g}_{high:g}",
                "H9_volatility_shock",
                "A volatility regime jump marks a change in the market's risk state, not "
                "merely a larger move. Information about volatility clustering means the "
                "post-shock distribution is worth measuring on its own.",
                ("vol_regime", "vol_percentile"),
                (PRICE, VOLUME),
                tf,
                f"vol_percentile crosses from at or below {low:g} to at or above {high:g}",
                {"from_percentile": low, "to_percentile": high},
                "If the transition is an artifact of the percentile window rather than a "
                "state change, the family reports no effect.",
            )

    # ---- H10: basis extremes ----------------------------------------------
    for tf in DISCOVERY_TIMEFRAMES:
        for cut in (5, 95):
            add(
                f"H10_BASIS_EXTREME_{tf.upper()}_P{cut}",
                "H10_basis_extremes",
                "Basis is the exchange's own statement about the cost of carry between "
                "perpetual and index. An extreme basis is a market-wide, non-chartable "
                "statement about where leverage is priced.",
                ("basis", "basis_percentile"),
                (MARK, INDEX),
                tf,
                f"basis expanding percentile is at or beyond the {cut}th percentile",
                {"percentile_cut": float(cut)},
                "Requires a genuine index price. A mark-versus-perpetual spread is a "
                "different quantity and is not accepted as a substitute.",
            )

    # ---- H11: cross-asset confirmation -------------------------------------
    for tf in DISCOVERY_TIMEFRAMES:
        add(
            f"H11_CROSS_ASSET_CONFIRM_{tf.upper()}",
            "H11_cross_asset_confirmation",
            "BTC is the market's risk factor for crypto perps. When an alt confirms BTC's "
            "direction, the move is systemic rather than idiosyncratic, and the question "
            "is whether systemic moves carry more predictable follow-through.",
            ("btc_trend_regime", "trend_regime"),
            (PRICE, CROSS_ASSET),
            tf,
            "BTC trend regime agrees with the symbol's own trend regime",
            {"reference_asset": "BTC"},
            "If BTC stops leading alt perps, the family is retired rather than "
            "re-weighted to whatever asset currently leads.",
        )

    # ---- H12: cross-asset divergence ---------------------------------------
    for tf in DISCOVERY_TIMEFRAMES:
        add(
            f"H12_CROSS_ASSET_DIVERGENCE_{tf.upper()}",
            "H12_cross_asset_divergence",
            "When majors disagree, relative-value flows between them can pull the pair "
            "back together. Mean reversion here is a hypothesis to be measured, not an "
            "assumption the plan permits us to skip.",
            ("btc_trend_regime", "trend_regime", "relative_strength"),
            (PRICE, CROSS_ASSET),
            tf,
            "BTC and the symbol's trend regimes are opposite",
            {"reference_asset": "BTC"},
            "If the pair never converges within any tested horizon, the reversion story "
            "is simply wrong and is reported as such.",
        )

    # ---- H13: BTC regime filter -------------------------------------------
    for tf in DISCOVERY_TIMEFRAMES:
        for state in ("STRONG_UP", "STRONG_DOWN", "NEUTRAL"):
            add(
                f"H13_BTC_FILTER_{tf.upper()}_{state}",
                "H13_btc_regime_filter",
                "Restricting alt trades to a BTC regime is the cheapest possible test of "
                "whether market-wide state carries information beyond the asset's own "
                "chart.",
                ("btc_trend_regime", "trend_regime"),
                (PRICE, CROSS_ASSET),
                tf,
                f"the symbol's own signal fires AND btc_trend_regime == {state}",
                {"btc_state": state},
                "A filter that only helps in one BTC state is reported as state-specific, "
                "never as a universal improvement.",
            )

    # ---- H14: multi-timeframe confirmation ---------------------------------
    for tf in DISCOVERY_TIMEFRAMES:
        add(
            f"H14_MTF_{tf.upper()}",
            "H14_multi_timeframe_confirmation",
            "A higher-timeframe trend with a lower-timeframe pullback and a lower-timeframe "
            "momentum recovery is a single economic event observed at three resolutions. "
            "The EMA periods are the preregistered ones; no combination is searched.",
            ("htf_trend_regime", "trend_regime", "pullback_depth"),
            (PRICE,),
            tf,
            f"the {tf} signal fires while the next higher timeframe is in the same "
            "directional trend regime and the lower timeframe is in a pullback",
            {"ema_periods": (20, 50, 100, 200), "timeframe_ladder": ["1h", "15m", "5m"]},
            "If the confirmation is a restatement of the lower timeframe alone, it adds "
            "no degrees of freedom and is reported as redundant.",
        )

    # ---- H15: regime-specific activation -----------------------------------
    for tf in DISCOVERY_TIMEFRAMES:
        for regime, style in (
            ("STRONG_UP", "TREND_CONTINUATION"),
            ("NEUTRAL", "MEAN_REVERSION"),
            ("HIGH_VOL", "BREAKOUT"),
        ):
            add(
                f"H15_REGIME_ACTIVATION_{tf.upper()}_{style}",
                "H15_regime_specific_activation",
                "Different strategies are supposed to work in different market states. "
                "Rather than search for a universal strategy, this asks whether activating "
                "a fixed style only inside its own regime improves its conditional return.",
                ("trend_regime", "vol_regime"),
                (PRICE, VOLUME),
                tf,
                f"the {style} condition holds AND the {regime} regime condition holds",
                {"regime": regime, "style": style},
                "If activation never changes the conditional return, regime conditioning "
                "is reported as inert for that style.",
            )

    return tuple(out)


#: The frozen registry: 15 families x the 2 preregistered discovery timeframes
#: x the mandated long/short mirror, with preregistered condition variants only.
HYPOTHESES: tuple[Hypothesis, ...] = _build_registry()

#: Expected count, asserted by the test suite so the registry cannot drift.
#: 92 sits inside the plan's 50-100 band on purpose.
EXPECTED_HYPOTHESIS_COUNT = 92

FAMILY_COUNTS: dict[str, int] = {}
for _h in HYPOTHESES:
    FAMILY_COUNTS[_h.family] = FAMILY_COUNTS.get(_h.family, 0) + 1


def available_fields(
    field_status: dict[str, str],
    price_available: bool = True,
    cross_asset_available_: bool = False,
) -> set[str]:
    """Translate a data audit into the set of canonical fields V2 may use.

    ``price`` and ``volume`` ride on the same OHLCV frame, so they are gated by
    ``price_available`` (any usable timeframe) rather than by a separate column.
    ``cross_asset`` needs at least two price symbols, never a derivatives feed.
    """

    from tools.strategy_factory_v2.data import AVAILABLE, DEGRADED  # local: avoid cycle

    ok = (AVAILABLE, DEGRADED)
    usable: set[str] = set()
    if price_available:
        usable.update({PRICE, VOLUME})
    if field_status.get("funding_rate") in ok:
        usable.add(FUNDING)
    if field_status.get("open_interest") in ok:
        usable.add(OPEN_INTEREST)
    if field_status.get("mark_price") in ok:
        usable.add(MARK)
    if field_status.get("index_price") in ok:
        usable.add(INDEX)
    if field_status.get("taker_buy_volume") in ok and field_status.get("taker_sell_volume") in ok:
        usable.add(TAKER)
    if cross_asset_available_:
        usable.add(CROSS_ASSET)
    return usable


def cross_asset_available(symbols: Iterable[str]) -> bool:
    return len({s for s in symbols}) >= 2


def status_for(
    hypothesis: Hypothesis,
    field_status: dict[str, str],
    symbols: Iterable[str] = (),
    price_available: bool = True,
) -> str:
    """Return ``TESTABLE`` or ``BLOCKED`` for one hypothesis.

    A hypothesis is blocked when any field it declares is absent from the data.
    Blocking is reported, never worked around with a proxy.
    """

    usable = available_fields(
        field_status,
        price_available=price_available,
        cross_asset_available_=cross_asset_available(symbols),
    )
    # Every V2 hypothesis is a statement about a *forward return*, so price is
    # required unconditionally -- even for a family whose distinguishing
    # inputs are mark and index. A basis extreme with no price series has no
    # return to condition on, and must not be reported as testable.
    required = set(hypothesis.required_fields) | {PRICE}
    missing = sorted(required - usable)
    return BLOCKED if missing else TESTABLE


def registry_manifest(
    field_status: dict[str, str] | None = None,
    symbols: Iterable[str] = (),
    price_available: bool = True,
) -> dict[str, Any]:
    """Summarise the registry and, if a data audit is supplied, its readiness."""

    families: dict[str, dict[str, Any]] = {}
    for hypothesis in HYPOTHESES:
        entry = families.setdefault(
            hypothesis.family,
            {"count": 0, "required_fields": set(), "hypothesis_ids": []},
        )
        entry["count"] += 1
        entry["required_fields"].update(hypothesis.required_fields)
        entry["hypothesis_ids"].append(hypothesis.hypothesis_id)

    families_out: dict[str, Any] = {}
    for name, entry in sorted(families.items()):
        required = sorted(entry["required_fields"])
        blocked: list[str] = []
        if field_status is not None:
            blocked = sorted(
                h.hypothesis_id
                for h in HYPOTHESES
                if h.family == name
                and status_for(h, field_status, symbols, price_available) == BLOCKED
            )
        families_out[name] = {
            "count": entry["count"],
            "required_fields": required,
            "testable": None if field_status is None else entry["count"] - len(blocked),
            "blocked": None if field_status is None else len(blocked),
            "blocked_hypothesis_ids": blocked,
            "hypothesis_ids": sorted(entry["hypothesis_ids"]),
        }

    summary: dict[str, Any] = {
        "spec_version": SPEC_VERSION,
        "hypothesis_count": len(HYPOTHESES),
        "family_count": len(families_out),
        "families": families_out,
        "forward_horizons_bars": list(FORWARD_HORIZONS_BARS),
    }
    if field_status is not None:
        blocked_all = sorted(
            h.hypothesis_id
            for h in HYPOTHESES
            if status_for(h, field_status, symbols, price_available) == BLOCKED
        )
        summary["testable_hypotheses"] = len(HYPOTHESES) - len(blocked_all)
        summary["blocked_hypotheses"] = len(blocked_all)
        summary["blocked_hypothesis_ids"] = blocked_all
    return summary


def hypotheses_as_records() -> list[dict[str, Any]]:
    return [hypothesis.as_dict() for hypothesis in HYPOTHESES]


def get(hypothesis_id: str) -> Hypothesis:
    for hypothesis in HYPOTHESES:
        if hypothesis.hypothesis_id == hypothesis_id:
            return hypothesis
    raise KeyError(hypothesis_id)
