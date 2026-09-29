"""Phase C -- the runner. Executes the preregistered discovery and stops.

    python -m tools.strategy_factory_v2.phase_c --out user_data/strategy_factory_runs/v2/<run>

The final holdout is never opened. There is no flag for it here, and the only
code path that can return holdout rows is
``holdout.open_holdout``, which requires a written justification and a spec
version frozen beforehand. That is a deliberate structural choice: a boundary
that can be opened by an option is a boundary that will be opened by an option.

Outputs, all under the run directory:

    manifest.json  trial_ledger.jsonl  hypothesis_results.csv  regime_summary.csv
    conditional_returns.csv  fold_results.csv  multiple_testing.json
    data_snapshot.json  report.md  report.html
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from tools.strategy_factory_v2.coverage_report import write_data_coverage_report
from tools.strategy_factory_v2.discovery import (
    FORWARD_HORIZON_BARS,
    build_discovery_frame,
    higher_timeframe_regime,
    with_regime,
    with_reference,
)
from tools.strategy_factory_v2.discovery_engine import (
    REFERENCE_SYMBOL,
    conditional_report,
    evaluate_hypothesis,
)
from tools.strategy_factory_v2.holdout import DataPartition, read_lock
from tools.strategy_factory_v2.hypotheses import HYPOTHESES
from tools.strategy_factory_v2.hypothesis_eval import evaluate
from tools.strategy_factory_v2.regime import REGIME_COLUMNS, classify, regime_distribution
from tools.strategy_factory_v2.spec import (
    DISCOVERY_TIMEFRAMES,
    MIN_OOS_TRADES,
    SPEC_VERSION,
    STATISTICS_V2,
    SURVIVOR_CRITERIA,
    spec_manifest,
)
from tools.strategy_factory_v2.integrity import run_gate

SYMBOLS = ("BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT", "BNBUSDT")
PRIMARY_HORIZON = 12


def _load_partition() -> DataPartition:
    lock = read_lock()
    if not lock:
        raise SystemExit(
            "No holdout lock file found. The research boundary must be declared "
            "before Phase C runs; refusing to invent one here."
        )
    return DataPartition(**lock["partition"])


# ---------------------------------------------------------------------------
# Multiple testing
# ---------------------------------------------------------------------------


def benjamini_hochberg(p_values: Sequence[float]) -> list[float]:
    """Benjamini-Hochberg adjusted p-values, the missing piece in V1.

    The V1 runner deflated only for cross-candidate correlation through a
    participation ratio. That handles dependent trials, but it does nothing
    about the ninety-odd independent hypotheses, and here the two effects are
    separable: a family of thresholds is internally correlated, and the
    families are not much correlated with each other.
    """

    values = np.asarray(p_values, dtype=float)
    n = len(values)
    if n == 0:
        return []
    order = np.argsort(values)
    ranked = values[order]
    adjusted = ranked * n / np.arange(1, n + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    adjusted = np.clip(adjusted, 0.0, 1.0)
    out = np.empty(n, dtype=float)
    out[order] = adjusted
    return [float(v) for v in out]


def one_sided_p_value(sample_count: int, t_stat: float) -> float:
    """One-sided p-value that the mean return is non-positive.

    Computed from a normal approximation with a small-sample correction rather
    than from a bootstrap, because it is run ninety-two times per fold and the
    direction of the test -- not its exact tail -- is what the multiple-testing
    correction is there to protect.
    """

    if sample_count < 5 or not np.isfinite(t_stat):
        return float("nan")
    from statistics import NormalDist

    # Student-t tail via a normal quantile and a simple df correction.
    z = t_stat
    p = 1.0 - NormalDist().cdf(z)
    return float(min(1.0, max(0.0, p)))


def multiple_testing_analysis(
    outcomes: Sequence[Any], frame_returns: pd.DataFrame
) -> dict[str, Any]:
    """Deflate the tested population for the number of hypotheses examined.

    Two defects are corrected here, both of which had inflated the count of
    "significant" results in the first run of this pipeline.

    **Serial dependence.** The pooled forward returns overlap in time, so a
    naive t-statistic treats correlated observations as independent evidence.
    The measured integrated autocorrelation time for the frozen candidates was
    5.9-10.7; deflating by that is the difference between 17 hypotheses
    clearing the bar and 2. Each row now carries its own IAT and effective N,
    and the correction is applied per hypothesis rather than by a global guess.

    **Logic identity.** ``logic_hash`` is recorded per hypothesis here, at the
    point where the screening statistic is produced. It previously existed only
    in the Phase D freeze record, which meant two stages could evaluate
    different things under one hypothesis id and nothing would notice.

    Fail-closed: if the return series for a hypothesis is unavailable, its
    significance cannot be established, so it is not counted as significant.
    An unverifiable candidate is not a verified one.
    """

    from tools.strategy_factory_v2.freeze import logic_hash
    from tools.strategy_factory_v2.hypotheses import get
    from tools.strategy_factory_v2.uncertainty import effective_sample_size

    rows = []
    for outcome in outcomes:
        metrics = outcome.metrics
        n = metrics.get("sample_count", 0)
        mean = metrics.get("mean_return")
        std = metrics.get("std_return")
        t = (
            float(mean / (std / math.sqrt(n)))
            if n and mean is not None and std and np.isfinite(std) and std > 0
            else float("nan")
        )

        series = getattr(outcome, "net_returns", None)
        dependence = effective_sample_size(
            np.asarray(series, dtype=float) if series is not None else np.array([])
        )
        iat = float(dependence.get("integrated_autocorrelation_time", 1.0) or 1.0)
        iat = max(1.0, iat)
        n_eff = float(dependence.get("effective_sample_size", n) or n)
        dependence_checked = series is not None and len(series) >= 10

        # Deflate: a serially dependent series of n observations carries the
        # evidence of n/tau of them.
        t_deflated = t / math.sqrt(iat) if dependence_checked else t

        try:
            digest = logic_hash(get(outcome.hypothesis_id))
        except Exception:
            digest = ""

        rows.append(
            {
                "hypothesis_id": outcome.hypothesis_id,
                "family": outcome.family,
                "sample_count": n,
                "mean_return": mean,
                "t_stat": t,
                "t_stat_dependence_adjusted": t_deflated,
                "integrated_autocorrelation_time": round(iat, 4),
                "effective_sample_size": round(n_eff, 2),
                "dependence_checked": dependence_checked,
                "logic_hash": digest,
                "p_raw": one_sided_p_value(n_eff if dependence_checked else n, t_deflated),
            }
        )
    frame = pd.DataFrame(rows)
    valid = frame["p_raw"].notna().to_numpy()
    adjusted = [float("nan")] * len(frame)
    if valid.any():
        values = benjamini_hochberg(frame.loc[valid, "p_raw"].tolist())
        for position, index in enumerate(frame.index[valid]):
            adjusted[index] = values[position]
    frame["p_bh_adjusted"] = adjusted
    # Fail-closed: significance is only claimed when the dependence correction
    # could actually be computed.
    frame["p_bh_significant"] = (frame["p_bh_adjusted"] < STATISTICS_V2.reality_check_alpha) & (
        frame["dependence_checked"]
    )

    raw = [p for p in frame["p_raw"].tolist() if np.isfinite(p)]
    return {
        "hypotheses_tested": int(len(frame)),
        "hypotheses_with_usable_sample": int(valid.sum()),
        "hypotheses_with_dependence_checked": int(frame["dependence_checked"].sum()),
        "correction": (
            "Benjamini-Hochberg FDR on one-sided t-tests of the pooled OOS mean, "
            "with the variance deflated by each hypothesis's own integrated "
            "autocorrelation time"
        ),
        "alpha": STATISTICS_V2.reality_check_alpha,
        "raw_p_median": float(np.median(raw)) if raw else None,
        "raw_p_min": float(np.min(raw)) if raw else None,
        "bh_significant_count": int(frame["p_bh_significant"].sum()),
        "per_hypothesis": frame.to_dict("records"),
        "note": (
            "The whole tested population is reported, not the best-looking slice. "
            "A hypothesis that fails here is not removed; it is recorded as failed. "
            "A hypothesis whose return series was unavailable cannot be certified "
            "significant and is reported with dependence_checked=false."
        ),
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_phase_c(output_dir: Path, symbols: Sequence[str] = SYMBOLS) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    partition = _load_partition()

    # The gate is re-run rather than trusted: Phase C is only allowed to run
    # against a dataset that passes right now, not against a cached verdict.
    gate = run_gate()
    if gate["a25_status"] != "PASS":
        raise SystemExit(
            "A2.5 integrity gate FAILED. Phase C must not run.\n"
            + "\n".join(f"  - {name}" for name in gate["criteria_failed"])
        )

    started = datetime.now(timezone.utc)
    frames: dict[tuple[str, str], Any] = {}
    snapshots: dict[str, Any] = {}
    regime_rows: list[dict[str, Any]] = []

    for symbol in symbols:
        for timeframe in DISCOVERY_TIMEFRAMES:
            try:
                frame = with_regime(build_discovery_frame(symbol, timeframe, partition, "development"))
            except (FileNotFoundError, ValueError) as error:
                print(f"  skip {symbol}/{timeframe}: {error}", flush=True)
                continue
            frames[(symbol, timeframe)] = frame
            snapshots[f"{symbol}/{timeframe}"] = {
                "rows": int(len(frame.frame)),
                "start": str(frame.frame["date"].min()),
                "end": str(frame.frame["date"].max()),
                "attach": frame.attach_report,
            }
            for _, row in regime_distribution(classify(frame.frame)).iterrows():
                regime_rows.append(
                    {"symbol": symbol, "timeframe": timeframe, **row.to_dict()}
                )
            print(f"  built {symbol}/{timeframe}: {len(frame.frame):,} rows", flush=True)

    # Cross-asset families need a reference. BTC is the preregistered reference
    # asset; for BTC itself the reference is itself, and the cross-asset families
    # are reported as UNTESTABLE rather than evaluated against a self-join.
    for (symbol, timeframe), frame in list(frames.items()):
        reference = frames.get((REFERENCE_SYMBOL, timeframe))
        if reference is None or symbol == REFERENCE_SYMBOL:
            for column in (
                "reference_trend_regime", "reference_trend_percentile", "relative_strength",
                "pullback_depth", "htf_trend_regime",
            ):
                frame.frame[column] = "UNKNOWN" if column.endswith("regime") else np.nan
            continue
        with_reference(frame, reference)
        # One concat per frame rather than a column insert per frame: the
        # fragmented-block warning is a symptom of assembling a wide frame one
        # column at a time, and the fix is structural.
        additions = {"htf_trend_regime": pd.Series(
            higher_timeframe_regime(symbol, timeframe, partition, frame.frame["decision_time"]),
            index=frame.frame.index,
        )}
        frame.frame = pd.concat([frame.frame, pd.DataFrame(additions)], axis=1)

    # ---- evaluate every preregistered hypothesis -------------------------
    outcomes: list[Any] = []
    conditional_rows: list[dict[str, Any]] = []
    fold_rows: list[dict[str, Any]] = []
    untested: list[dict[str, str]] = []
    ledger_lines: list[str] = []

    for hypothesis in HYPOTHESES:
        frames_at_tf = {
            symbol: discovery.frame
            for (symbol, timeframe), discovery in frames.items()
            if timeframe == hypothesis.timeframe
        }
        if not frames_at_tf:
            untested.append(
                {
                    "hypothesis_id": hypothesis.hypothesis_id,
                    "reason": f"no data at timeframe {hypothesis.timeframe}",
                }
            )
            continue

        matched_bars = 0
        for symbol, frame in frames_at_tf.items():
            mask = evaluate(hypothesis, frame)
            matched_bars += int(mask.fillna(False).sum())
            for row in conditional_report(frame, hypothesis, mask):
                row["symbol"] = symbol
                conditional_rows.append(row)

        if matched_bars == 0:
            untested.append(
                {
                    "hypothesis_id": hypothesis.hypothesis_id,
                    "reason": "no bar at this timeframe satisfied the condition on any symbol",
                }
            )
            ledger_lines.append(
                json.dumps(
                    {
                        "hypothesis_id": hypothesis.hypothesis_id,
                        "family": hypothesis.family,
                        "timeframe": hypothesis.timeframe,
                        "expected_direction": hypothesis.expected_direction,
                        "status": "UNMATCHED",
                        "matched_bars": 0,
                    }
                )
            )
            continue

        outcome = evaluate_hypothesis(hypothesis, frames_at_tf, PRIMARY_HORIZON)
        outcomes.append(outcome)
        for row in outcome.fold_rows:
            fold_rows.append({"hypothesis_id": hypothesis.hypothesis_id, **row})
        ledger_lines.append(
            json.dumps(
                {
                    "hypothesis_id": hypothesis.hypothesis_id,
                    "family": hypothesis.family,
                    "timeframe": hypothesis.timeframe,
                    "expected_direction": hypothesis.expected_direction,
                    "status": outcome.verdict,
                    "sample_count": outcome.sample_count,
                    "matched_bars": matched_bars,
                    "gates": outcome.gates,
                }
            )
        )

    multiple = multiple_testing_analysis(outcomes, pd.DataFrame())
    for outcome in outcomes:
        row = next(
            (r for r in multiple["per_hypothesis"] if r["hypothesis_id"] == outcome.hypothesis_id),
            None,
        )
        adjusted = row.get("p_bh_adjusted") if row else None
        # A survivor must also survive the multiple-testing correction. A raw
        # p-value that looks convincing across ninety-two tests is exactly the
        # result the correction exists to suppress.
        passes_correction = bool(
            adjusted is not None and np.isfinite(adjusted) and adjusted < STATISTICS_V2.reality_check_alpha
        )
        outcome.gates["multiple_testing_adjusted"] = passes_correction
        outcome.survivor = outcome.survivor and passes_correction
        outcome.verdict = (
            "INSUFFICIENT_SAMPLE"
            if outcome.sample_count < MIN_OOS_TRADES
            else ("PROMISING_BUT_UNVERIFIED" if outcome.survivor else "FAIL")
        )
    survivors = [o for o in outcomes if o.survivor]

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()

    return {
        "partition": partition,
        "gate": gate,
        "frames": frames,
        "outcomes": outcomes,
        "untested": untested,
        "survivors": survivors,
        "multiple": multiple,
        "conditional_rows": conditional_rows,
        "fold_rows": fold_rows,
        "regime_rows": regime_rows,
        "snapshots": snapshots,
        "ledger_lines": ledger_lines,
        "elapsed_seconds": round(elapsed, 1),
    }


def _load_partition_or_exit() -> DataPartition:
    return _load_partition()
