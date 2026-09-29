"""Phase F -- the runner. Stitch, dissect, label, stop.

    python -m tools.strategy_factory_v2.phase_f_main --out <run-dir>

The order is the discipline, and it is the same discipline the earlier phases
used: prove the candidates have not moved, build the timeline through the
frozen pipeline, measure, and only then write anything. Nothing here creates a
hypothesis, changes a threshold, or promotes a result -- there is no code path
in this module that can, which is a stronger guarantee than a promise in a
docstring.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from tools.strategy_factory_v2 import phase_f as F
from tools.strategy_factory_v2.freeze import source_hash
from tools.strategy_factory_v2.hypotheses import get
from tools.strategy_factory_v2.spec import BASE_COST, SPEC_VERSION, STRESS_COST, DOUBLE_COST


def _say(message: str) -> None:
    print(message, flush=True)


def _quiet_pandas_fragmentation_warnings() -> None:
    """Silence a warning that is noise here and would bury a real one.

    ``with_reference`` inserts a few columns one at a time into a frame that
    already carries a hundred, so pandas complains ten times per symbol. The
    advice is real but the fix belongs in that function, not in this phase; the
    alternative is a log in which the one line that matters is invisible.
    """

    import warnings

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", category=pd.errors.PerformanceWarning, module="tools.strategy_factory_v2"
        )
    warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)


def run_phase_f(
    output_dir: Path,
    candidates: Sequence[str] = F.CANDIDATE_IDS,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    _quiet_pandas_fragmentation_warnings()

    # ---- 1. the boundary, and the fact that it is already open -------------
    partition, access = F.load_unblinded_partition()
    _say(
        f"holdout already unblinded at {access['unsealed_utc']} by "
        f"{access['unsealed_by_phase']}; Phase F writes no new unseal event"
    )

    # ---- 2. the candidates must be the ones that failed -------------------
    logic_hashes = F.assert_candidate_untouched(candidates)
    _say(f"candidate logic verified against the Phase D freeze: {sorted(logic_hashes)}")

    # ---- 3. the continuous timeline ---------------------------------------
    timeline = F.build_timeline(partition, F.SYMBOLS, F.TIMEFRAME, progress=_say)
    _say(
        f"timeline: {timeline.development_rows:,} development rows + "
        f"{timeline.holdout_rows:,} holdout rows across {len(timeline.frames)} symbols; "
        f"{timeline.warmup_rows_excluded:,} warm-up rows excluded; "
        f"{timeline.incomplete_outcome_rows:,} rows without a complete forward outcome"
    )

    # ---- 4. signals --------------------------------------------------------
    trades: dict[str, pd.DataFrame] = {
        candidate_id: F.signal_trades(candidate_id, timeline.frames)
        for candidate_id in candidates
    }
    for candidate_id, frame in trades.items():
        _say(f"  {candidate_id}: {len(frame):,} signals across the full timeline")

    primary = F.PRIMARY_CANDIDATE
    control = F.control_trades(primary, timeline.frames)
    _say(f"  diagnostic unfiltered control ({primary}): {len(control):,} signals")

    # ---- 5. the thirteen diagnostics --------------------------------------
    _say("section 3  fixed chronological timeline...")
    period = F.period_metrics(trades, timeline)
    rolling = F.rolling_metrics(trades[primary], timeline)

    _say("section 4  input distribution drift...")
    drift = F.feature_distribution_drift(timeline)

    _say("section 5  BTC regime frequency...")
    regimes = F.regime_frequency(timeline)

    _say("section 6  signal frequency and clustering...")
    signal_rate = F.signal_frequency(primary, timeline)

    _say("section 7  symbol x period...")
    symbols = F.symbol_period_matrix(trades[primary], timeline)

    _say("section 8  gross versus cost...")
    side = 1 if get(primary).expected_direction == "long" else -1
    costs = F.cost_decomposition(trades[primary], side, partition, BASE_COST)
    F.assert_decomposition_reconciles(costs)

    _say("section 9  holding horizons...")
    horizons = F.holding_horizon_diagnostics(primary, timeline)

    _say("section 10 dependence structure...")
    dependence = F.dependence_diagnostics(trades, timeline)

    _say("section 11 regime-conditioned attribution...")
    attribution = F.regime_attribution(primary, trades[primary], control, timeline)

    _say("section 12 descriptive drift labels...")
    conclusion = F.conclusion_rows(trades, timeline)
    drift_table = build_drift_diagnostics(
        timeline, trades, control, period, rolling, drift, regimes,
        signal_rate, costs, horizons, dependence, attribution,
    )

    _say("direction-convention defect audit...")
    direction_audit = F.direction_convention_audit(trades, timeline)

    return {
        "run_id": output_dir.name,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "spec_version": SPEC_VERSION,
        "partition": partition,
        "access": access,
        "logic_hashes": logic_hashes,
        "executed_source_hash": source_hash(
            [
                Path("tools/strategy_factory_v2") / name
                for name in (
                    "hypothesis_eval.py", "features.py", "regime.py", "discovery.py",
                    "discovery_engine.py", "joins.py", "spec.py",
                )
            ]
        ),
        "timeline": timeline,
        "timeline_summary": {
            "symbols": list(F.SYMBOLS),
            "timeframe": F.TIMEFRAME,
            "horizon_bars": F.HORIZON,
            "development_rows": timeline.development_rows,
            "holdout_rows": timeline.holdout_rows,
            "warmup_rows_excluded": timeline.warmup_rows_excluded,
            "rows_dropped_at_the_boundary": timeline.boundary_gap_rows,
            "rows_without_complete_outcome": timeline.incomplete_outcome_rows,
            "start": str(timeline.start),
            "end": str(timeline.end),
            "periods": {
                name: [str(low), str(high)] for name, (low, high) in timeline.periods.items()
            },
            "rolling_window_days": F.ROLLING_WINDOW_DAYS,
            "rolling_step_days": F.ROLLING_STEP_DAYS,
            "warmup_days": F.HOLDOUT_WARMUP_DAYS,
        },
        "trades": trades,
        "control": control,
        "conclusion": conclusion,
        "period_metrics": period,
        "rolling_metrics": rolling,
        "feature_distribution_drift": drift,
        "regime_frequency": regimes,
        "signal_frequency": signal_rate,
        "symbol_period_matrix": symbols,
        "cost_decomposition": costs,
        "holding_horizon_diagnostics": horizons,
        "dependence_diagnostics": dependence,
        "regime_attribution_posthoc": attribution,
        "hypothesis_drift_assessment": drift_table,
        "direction_convention_audit": direction_audit,
    }


# ---------------------------------------------------------------------------
# Section 12 -- the descriptive labels
# ---------------------------------------------------------------------------


def _value(frame: pd.DataFrame, column: str) -> float | None:
    """One numeric cell, or None. Never guesses a column and never averages."""

    if frame is None or len(frame) == 0 or column not in frame.columns:
        return None
    return _number(frame.iloc[0][column])


def _region_series(
    frame: pd.DataFrame, column: str, period_column: str = "period"
) -> list[float | None]:
    """One value per region, in region order, from a table that has a region column."""

    return [
        _value(frame[frame[period_column] == region], column) for region in F.REGION_ORDER
    ]


def _effective_sample_fraction(frame: pd.DataFrame) -> list[float | None]:
    """Effective sample size divided by the raw observation count, per region.

    The raw count is not comparable across regions -- the holdout is a quarter
    the length of development -- so comparing the two sizes directly would read
    a shorter window as a weaker one.
    """

    out: list[float | None] = []
    for region in F.REGION_ORDER:
        row = frame[frame["period"] == region] if "period" in frame.columns else frame
        effective = _value(row, "effective_sample_size")
        raw = _value(row, "observations")
        if effective is None or not raw:
            out.append(None)
            continue
        out.append(effective / raw)
    return out


def build_drift_diagnostics(
    timeline,
    trades: dict[str, pd.DataFrame],
    control: pd.DataFrame,
    period: pd.DataFrame,
    rolling: pd.DataFrame,
    drift: pd.DataFrame,
    regimes: pd.DataFrame,
    signal_rate: pd.DataFrame,
    costs: pd.DataFrame,
    horizons: pd.DataFrame,
    dependence: pd.DataFrame,
    attribution: pd.DataFrame,
) -> pd.DataFrame:
    """Every diagnostic the plan lists, reduced to three comparable numbers.

    A diagnostic belongs in this table only if it has one value per region and
    those three values mean the same thing in each. Anything that cannot be put
    in that shape stays in its own section rather than being forced into a
    comparison it does not support. Every lookup names its column explicitly:
    a diagnostic layer that hunts for a column by trying several names is a
    diagnostic layer that can quietly report the wrong number.
    """

    primary = F.PRIMARY_CANDIDATE
    rows: list[
        tuple[str, str, float | None, float | None, float | None, int, int, float]
    ] = []

    region_period = period[
        (period["candidate"] == primary) & (period["bucket_type"] == "region")
    ]
    region_period = region_period.assign(period=region_period["bucket"])
    development_n = int(
        region_period.loc[
            region_period["period"] == "development", "trade_count"
        ].sum()
    )
    holdout_n = int(
        region_period.loc[
            region_period["period"] == "final_holdout", "trade_count"
        ].sum()
    )
    counts = (development_n, holdout_n)

    def add(
        name: str,
        interpretation: str,
        values: Sequence[float | None],
        sample: tuple[int, int] = counts,
        neutral: float = 0.0,
    ) -> None:
        padded = list(values) + [None] * (3 - len(values))
        rows.append(
            (
                name,
                interpretation,
                padded[0],
                padded[1],
                padded[2],
                sample[0],
                sample[1],
                neutral,
            )
        )

    # --- the candidate's own behaviour ------------------------------------
    add(
        "return_expectancy",
        "the primary measurement: mean net return per signal at base cost",
        _region_series(region_period, "expectancy"),
    )
    add(
        "stress_expectancy",
        "the same measurement at the frozen stress cost model",
        _region_series(region_period, "stress_expectancy"),
    )
    add(
        "profit_factor",
        "gross gain divided by gross loss; the neutral level is 1.0, not 0, "
        "because 1.2 and 0.8 are the same sign and opposite outcomes",
        _region_series(region_period, "profit_factor"),
        neutral=1.0,
    )

    # --- frequency and clustering -----------------------------------------
    pooled_signals = signal_rate[signal_rate["symbol"] == "POOLED"]
    add(
        "signal_rate_per_month",
        "how often the candidate fired across all trading symbols; a fall in rate and a fall in return are different failures",
        _region_series(pooled_signals, "signals_per_month"),
    )
    month_rows = period[
        (period["candidate"] == primary) & (period["bucket_type"] == "calendar_month")
    ]
    add(
        "active_month_fraction",
        "share of the region's calendar months that produced at least one signal; "
        "a month with none is evidence, not a gap",
        _active_month_fraction(month_rows, timeline),
    )

    # --- the reference regime ---------------------------------------------
    strong_down = regimes[regimes["regime"] == "STRONG_DOWN"]
    add(
        "btc_strong_down_share",
        "share of reference-asset bars in the STRONG_DOWN state; a rarer state means fewer eligible signals",
        _region_series(strong_down, "bar_share"),
    )
    add(
        "btc_strong_down_mean_run_bars",
        "mean length of an uninterrupted STRONG_DOWN spell on the reference asset",
        _region_series(strong_down, "mean_run_bars"),
    )

    # --- the derivatives inputs -------------------------------------------
    for feature, name, sentence in (
        ("basis", "basis_mean", "mean mark/index basis; a distribution shift, not a cause"),
        ("funding_rate_last", "funding_rate_mean", "mean last settled funding rate"),
        ("open_interest_pct_change_288", "oi_pct_change_288_mean", "mean 288-bar change in open interest"),
        ("realized_vol_30", "realized_vol_30_mean", "mean 30-bar realised volatility"),
        ("price_return_24", "price_return_24_mean", "mean 24-bar price return"),
    ):
        subset = drift[
            (drift["feature"] == feature)
            & (drift["symbol"] == "POOLED_ALTS")
            & (~drift["period"].astype(str).str.startswith("development_vs"))
        ]
        add(name, sentence, _region_series(subset, "mean"))

    # --- cost structure ---------------------------------------------------
    add(
        "gross_expectancy",
        "mean return after slippage and before fees and funding; its sign is the alpha question",
        _region_series(costs, "gross_expectancy"),
    )
    add(
        "funding_impact",
        "mean adverse funding charge per signal; the part of the cost the market sets",
        _region_series(costs, "funding_impact"),
    )

    # --- dependence --------------------------------------------------------
    add(
        "lag1_autocorrelation",
        "serial dependence of the signal stream; high values make the naive t-statistic optimistic",
        _region_series(dependence[dependence["candidate"] == primary], "lag1_autocorrelation"),
    )
    add(
        "effective_sample_fraction",
        "effective sample size as a share of the raw count; the scale-free version, "
        "so a shorter region is not mistaken for weaker dependence",
        _effective_sample_fraction(dependence[dependence["candidate"] == primary]),
    )

    # --- attribution and consistency --------------------------------------
    add(
        "regime_filter_lift_vs_control",
        "candidate expectancy minus the unfiltered control; an association, never a causal effect",
        _region_series(attribution, "difference"),
    )
    add(
        "symbol_positive_fraction",
        "share of trading symbols whose expectancy was positive in the region",
        _symbol_positive_fraction(trades[primary], timeline),
    )

    horizon_pivot = horizons.pivot_table(
        index="horizon_bars", columns="period", values="expectancy", aggfunc="first"
    )
    if {"development", "final_holdout"}.issubset(horizon_pivot.columns):
        signs = horizon_pivot.dropna(subset=["development", "final_holdout"])
        # A development-versus-holdout comparison with no validation value. It
        # goes in the prose rather than into the table: a row structurally
        # missing a third of its numbers is a row the reader pauses over.
        HORIZON_SIGN_AGREEMENT["value"] = float(
            (np.sign(signs["development"]) == np.sign(signs["final_holdout"])).mean()
        )
    add(
        "horizon_positive_share",
        "share of the registered horizons with positive expectancy in the region; "
        "a horizon-specific result and a universal one look different here",
        [
            float((horizon_pivot[region] > 0).mean()) if region in horizon_pivot.columns else None
            for region in F.REGION_ORDER
        ],
    )

    return F.hypothesis_drift_table(rows)


def _active_month_fraction(month_rows: pd.DataFrame, timeline) -> list[float | None]:
    """Share of each region's calendar months that produced at least one signal.

    A fraction, not a count: the regions are wildly different lengths -- 64
    months of development against 6 of validation -- so a raw count would make a
    candidate look like it stopped firing purely because the window closed.

    Decided by the region each calendar month actually falls in, taken from the
    partition boundaries rather than inferred from a signal.
    """

    if month_rows.empty:
        return [None, None, None]
    buckets = list(month_rows["bucket"].astype(str))
    counts = list(month_rows["trade_count"].fillna(0).astype(int))
    out: list[float | None] = []
    for region in F.REGION_ORDER:
        start, end = timeline.periods[region]
        eligible = 0
        active = 0
        for bucket, count in zip(buckets, counts):
            first = pd.Timestamp(f"{bucket}-01", tz="UTC")
            following = first + pd.DateOffset(months=1)
            if first < end and following > start:
                eligible += 1
                active += 1 if count > 0 else 0
        out.append(active / eligible if eligible else None)
    return out


#: Filled in by the drift builder, read by the report's prose. Module state
#: rather than a return value because it is one number the report needs and the
#: three-column table cannot hold.
HORIZON_SIGN_AGREEMENT: dict[str, float | None] = {"value": None}


def _symbol_positive_fraction(
    trades: pd.DataFrame, timeline
) -> list[float | None]:
    """Share of symbols with positive mean net return, per region."""

    out: list[float | None] = []
    for region in F.REGION_ORDER:
        start, end = timeline.periods[region]
        subset = F._in_period(trades, start, end)
        if subset.empty:
            out.append(None)
            continue
        means = subset.groupby("symbol")["net_base"].mean()
        out.append(float((means > 0).mean()))
    return out


def _counts(period: pd.DataFrame, candidate: str) -> tuple[int, int]:
    """Development and holdout sample sizes for the primary candidate."""

    rows = period[
        (period["candidate"] == candidate) & (period["bucket_type"] == "region")
    ]
    development = rows[rows["bucket"] == "development"]
    holdout = rows[rows["bucket"] == "final_holdout"]
    return (
        int(development["trade_count"].iloc[0]) if len(development) else 0,
        int(holdout["trade_count"].iloc[0]) if len(holdout) else 0,
    )


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(number) else number


if __name__ == "__main__":
    # Imported here rather than at module scope: the report module imports the
    # runner, and a top-level import in the other direction would close the
    # cycle. A runner that can be executed but not *invoked* is a runner whose
    # silence looks exactly like a successful no-op.
    from tools.strategy_factory_v2.phase_f_report import main

    raise SystemExit(main())
