"""Orchestrate a complete, versioned strategy-factory research run."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
from typing import Any

import numpy as np
import pandas as pd

from tools.strategy_factory.data import as_utc, load_pair_bundle
from tools.strategy_factory.engine import (
    apply_cost_scenario,
    daily_portfolio_returns,
    performance_metrics,
    raw_trades_to_frame,
    simulate_trades,
)
from tools.strategy_factory.features import FeatureBundle, build_features
from tools.strategy_factory.models import StrategySpec
from tools.strategy_factory.preregistration import (
    ACCEPTANCE,
    BASE_COST,
    COST_SCENARIOS,
    HYPOTHESIS_IDS,
    PAIRS,
    SPEC_VERSION,
    STATISTICS,
    WALK_FORWARD,
    generate_specs,
    preregistration_manifest,
)
from tools.strategy_factory.strategies import signals_for_spec
from tools.strategy_factory.report import write_heatmaps, write_report
from tools.strategy_factory.validation import (
    choose_training_winner,
    deflated_sharpe,
    filter_trades,
    make_folds,
    monte_carlo_equity,
    white_reality_check,
)


@dataclass
class FactoryRun:
    output_dir: Path
    manifest: dict[str, Any]
    trial_results: pd.DataFrame
    fold_winners: pd.DataFrame
    hypothesis_summary: pd.DataFrame
    leaderboard: pd.DataFrame
    survivors: list[dict[str, Any]]


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _source_hash() -> str:
    digest = sha256()
    package_dir = Path(__file__).parent
    for path in sorted(package_dir.glob("*.py")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _fingerprint(audits: list[dict[str, Any]]) -> str:
    relevant = []
    for audit in sorted(audits, key=lambda item: item["pair"]):
        relevant.append(
            {
                "pair": audit["pair"],
                "one": audit["one_minute"],
                "five": audit["five_minute"],
                "funding": audit["funding"],
                "files": audit["files"],
            }
        )
    return sha256(_json(relevant).encode()).hexdigest()


def _flatten_params(params: dict[str, int | float]) -> dict[str, int | float | str]:
    return {f"param_{key}": value for key, value in sorted(params.items())}


def _metrics_for_frames(
    trade_frames: dict[str, pd.DataFrame],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[dict[str, Any], pd.Series]:
    filtered = {
        pair: filter_trades(frame, start, end)
        for pair, frame in trade_frames.items()
    }
    daily = daily_portfolio_returns(filtered, start, end)
    combined = (
        pd.concat(list(filtered.values()), ignore_index=True)
        if filtered
        else pd.DataFrame()
    )
    return performance_metrics(daily, combined), daily


def _scenario_frames(
    raw_by_pair: dict[str, pd.DataFrame],
    scenario,
) -> dict[str, pd.DataFrame]:
    return {pair: apply_cost_scenario(frame, scenario) for pair, frame in raw_by_pair.items()}


def _safe_float(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return np.nan
    return result if np.isfinite(result) else np.nan


def _boundary_indices(frame: pd.DataFrame, folds: list[Any]) -> set[int]:
    """Map fold boundaries to 1m positions for flat-state resets."""

    dates = pd.to_datetime(frame["date"], utc=True).to_numpy(dtype="datetime64[ns]")
    reset: set[int] = set()
    for fold in folds:
        for boundary in (
            fold.train_start,
            fold.train_end,
            fold.validation_start,
            fold.validation_end,
        ):
            value = as_utc(boundary).to_datetime64()
            position = int(np.searchsorted(dates, value, side="left"))
            if position < len(dates) and dates[position] == value:
                reset.add(position)
    return reset


def run_factory(
    data_dir: str | Path,
    output_dir: str | Path,
    pairs: tuple[str, ...] = PAIRS,
    start: str | None = None,
    end: str | None = None,
    max_specs: int | None = None,
    monte_carlo_draws: int | None = None,
    overwrite: bool = False,
    quick: bool = False,
) -> FactoryRun:
    """Run the frozen MVP search and write an auditable result directory.

    ``max_specs`` is a diagnostic smoke-test escape hatch, not part of the
    pre-registered experiment. If used, the manifest records the truncated
    search and the output must not be interpreted as a full trial result.
    """

    output = Path(output_dir)
    if output.exists() and any(output.iterdir()) and not overwrite:
        raise FileExistsError(
            f"Output directory is not empty: {output}. Use a new run-id path or overwrite=True."
        )
    all_specs = generate_specs()
    specs = all_specs
    if quick:
        specs = [
            candidate
            for hypothesis in HYPOTHESIS_IDS
            for candidate in (
                next(item for item in all_specs if item.hypothesis_id == hypothesis),
                all_specs[len(all_specs) // 2]
                if all_specs[len(all_specs) // 2].hypothesis_id == hypothesis
                else next(
                    item
                    for item in reversed(all_specs)
                    if item.hypothesis_id == hypothesis
                ),
            )
        ]
    truncated = len(specs) < len(all_specs)
    if max_specs is not None:
        specs = specs[: max(0, max_specs)]
        truncated = truncated or len(specs) < len(all_specs)
    if not specs:
        raise ValueError("No strategy specifications selected")
    # Preserve order while removing duplicate objects in the quick profile.
    unique_specs: list[StrategySpec] = []
    for spec in specs:
        if spec not in unique_specs:
            unique_specs.append(spec)
    specs = unique_specs

    audits: list[dict[str, Any]] = []
    data_starts: list[pd.Timestamp] = []
    data_ends: list[pd.Timestamp] = []
    for pair in pairs:
        # Read only long enough to obtain the audit/range, then release raw
        # frames. The feature pass below reloads one pair at a time.
        bundle = load_pair_bundle(data_dir, pair)
        audits.append(bundle.audit)
        data_starts.append(as_utc(bundle.audit["one_minute"]["start"]))
        data_ends.append(as_utc(bundle.audit["one_minute"]["end"]))
        del bundle

    data_start = min(data_starts)
    data_end = max(data_ends)
    blocking_issues = [
        {
            "pair": audit["pair"],
            "one_minute": {
                key: audit["one_minute"][key]
                for key in ("gaps", "duplicates", "invalid_ohlcv")
                if audit["one_minute"][key]
            },
            "five_minute": {
                key: audit["five_minute"][key]
                for key in ("gaps", "duplicates", "invalid_ohlcv")
                if audit["five_minute"][key]
            },
        }
        for audit in audits
        if any(audit["one_minute"][key] for key in ("gaps", "duplicates", "invalid_ohlcv"))
        or any(audit["five_minute"][key] for key in ("gaps", "duplicates", "invalid_ohlcv"))
    ]
    if blocking_issues:
        raise ValueError(f"Blocking data-quality issues: {blocking_issues}")
    requested_start = as_utc(start) if start else data_start
    requested_end = as_utc(end) if end else data_end
    evaluation_start = max(data_start, requested_start)
    evaluation_end = min(data_end, requested_end)
    if evaluation_end <= evaluation_start:
        raise ValueError("Requested research range is empty")

    data_fingerprint = _fingerprint(audits)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    write_dir = output.with_name(f"{output.name}.tmp-{run_id}")
    if write_dir.exists():
        raise FileExistsError(f"Temporary output already exists: {write_dir}")
    write_dir.mkdir(parents=True, exist_ok=False)
    trial_ids = {spec: spec.trial_id(data_fingerprint) for spec in specs}
    walk_forward = WALK_FORWARD
    fold_override = None
    if start and evaluation_start > data_start:
        # A bounded diagnostic run gets a new, explicitly recorded fold origin;
        # it is not silently mixed with the frozen full-history episode.
        fold_override = str(evaluation_start.date())
        walk_forward = replace(WALK_FORWARD, first_validation=fold_override)
    all_folds = make_folds(data_start, data_end, walk_forward)
    folds = [
        fold
        for fold in all_folds
        if fold.validation_start >= evaluation_start
        and fold.validation_end <= evaluation_end
    ]
    if not folds:
        raise ValueError("No complete walk-forward folds fit inside the requested range")

    raw_by_trial: dict[str, dict[str, pd.DataFrame]] = {
        trial_id: {} for trial_id in trial_ids.values()
    }
    reset_indices: dict[str, set[int]] = {}
    for pair in pairs:
        feature_bundle = build_features(load_pair_bundle(data_dir, pair))
        frame = feature_bundle.frame
        reset_indices[pair] = _boundary_indices(frame, folds)
        if end:
            frame = frame[frame["date"] < evaluation_end].copy()
            feature_bundle.frame = frame.copy()
        for spec in specs:
            long_signal, short_signal = signals_for_spec(feature_bundle, spec)
            trades = simulate_trades(
                frame,
                long_signal,
                short_signal,
                spec,
                feature_bundle.funding,
                reset_indices=reset_indices[pair],
            )
            raw_by_trial[trial_ids[spec]][pair] = raw_trades_to_frame(trades)
        # Release the large feature frame before building the next pair.
        del feature_bundle, frame
        print(f"simulated pair {pair}: {len(specs)} specs", flush=True)

    base_by_trial: dict[str, dict[str, pd.DataFrame]] = {
        tid: _scenario_frames(frames, BASE_COST) for tid, frames in raw_by_trial.items()
    }
    stats_draws = monte_carlo_draws or STATISTICS.monte_carlo_draws
    trial_rows: list[dict[str, Any]] = []
    winner_rows: list[dict[str, Any]] = []
    validation_daily: dict[str, list[pd.Series]] = {tid: [] for tid in trial_ids.values()}
    selected_raw: dict[str, list[dict[str, pd.DataFrame]]] = {
        hypothesis: [] for hypothesis in HYPOTHESIS_IDS
    }
    selected_fold_metrics: dict[str, list[dict[str, Any]]] = {
        hypothesis: [] for hypothesis in HYPOTHESIS_IDS
    }

    for fold in folds:
        for hypothesis in HYPOTHESIS_IDS:
            family_specs = [spec for spec in specs if spec.hypothesis_id == hypothesis]
            candidate_rows: list[dict[str, Any]] = []
            for spec in family_specs:
                tid = trial_ids[spec]
                base_frames = base_by_trial[tid]
                train_metrics, _ = _metrics_for_frames(
                    base_frames, fold.train_start, fold.train_end
                )
                validation_metrics, validation_daily_series = _metrics_for_frames(
                    base_frames, fold.validation_start, fold.validation_end
                )
                candidate = {
                    "fold_id": fold.fold_id,
                    "hypothesis_id": hypothesis,
                    "trial_id": tid,
                    "spec_version": spec.spec_version,
                    "params": _json(spec.params),
                    "train_start": fold.train_start,
                    "train_end": fold.train_end,
                    "validation_start": fold.validation_start,
                    "validation_end": fold.validation_end,
                    "train_trades": train_metrics.get("trades", 0),
                    "train_expectancy": train_metrics.get("expectancy", np.nan),
                    "train_profit_factor": train_metrics.get("profit_factor", np.nan),
                    "train_sharpe": train_metrics.get("sharpe", np.nan),
                    "validation_trades": validation_metrics.get("trades", 0),
                    "validation_expectancy": validation_metrics.get("expectancy", np.nan),
                    "validation_profit_factor": validation_metrics.get("profit_factor", np.nan),
                    "validation_sharpe": validation_metrics.get("sharpe", np.nan),
                    "validation_total_return": validation_metrics.get("total_return", np.nan),
                    "validation_max_drawdown": validation_metrics.get("max_drawdown", np.nan),
                }
                candidate["net_sharpe"] = candidate["validation_sharpe"]
                candidate_rows.append(candidate)
                validation_daily[tid].append(validation_daily_series)
                trial_rows.append(candidate)
            winner = choose_training_winner(
                [
                    {
                        **row,
                        "net_sharpe": row["train_sharpe"],
                        "expectancy": row["train_expectancy"],
                        "trades": row["train_trades"],
                    }
                    for row in candidate_rows
                ],
                min_trades=WALK_FORWARD.min_train_trades,
            )
            if winner is None:
                continue
            winning_tid = str(winner["trial_id"])
            winning_spec = next(spec for spec in family_specs if trial_ids[spec] == winning_tid)
            selected_raw[hypothesis].append(
                {
                    pair: filter_trades(
                        raw_by_trial[winning_tid][pair], fold.validation_start, fold.validation_end
                    )
                    for pair in pairs
                }
            )
            selected_fold_metrics[hypothesis].append(
                {
                    "fold_id": fold.fold_id,
                    "expectancy": _safe_float(winner.get("validation_expectancy")),
                    "profit_factor": _safe_float(winner.get("validation_profit_factor")),
                    "trades": int(winner.get("validation_trades", 0)),
                    "trial_id": winning_tid,
                    "params": _json(winning_spec.params),
                }
            )
            winner_rows.append(
                {
                    "fold_id": fold.fold_id,
                    "hypothesis_id": hypothesis,
                    "trial_id": winning_tid,
                    "params": _json(winning_spec.params),
                    "train_trades": winner.get("train_trades", 0),
                    "train_expectancy": winner.get("train_expectancy", np.nan),
                    "validation_trades": winner.get("validation_trades", 0),
                    "validation_expectancy": winner.get("validation_expectancy", np.nan),
                    "validation_profit_factor": winner.get("validation_profit_factor", np.nan),
                    "validation_sharpe": winner.get("validation_sharpe", np.nan),
                }
            )

    trial_results = pd.DataFrame(trial_rows)
    fold_winners = pd.DataFrame(winner_rows)
    summaries: list[dict[str, Any]] = []
    survivors: list[dict[str, Any]] = []
    all_selected_trade_rows: list[pd.DataFrame] = []

    for hypothesis in HYPOTHESIS_IDS:
        family_specs = [spec for spec in specs if spec.hypothesis_id == hypothesis]
        selected_parts = selected_raw[hypothesis]
        if not selected_parts:
            continue
        selected_base: dict[str, pd.DataFrame] = {}
        for pair in pairs:
            frames = [part[pair] for part in selected_parts if pair in part]
            selected_base[pair] = (
                pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
            )
        selected_stress = _scenario_frames(selected_base, COST_SCENARIOS[1])
        selected_start = min(fold.validation_start for fold in folds)
        selected_end = max(fold.validation_end for fold in folds)
        base_metrics, selected_daily = _metrics_for_frames(
            _scenario_frames(selected_base, BASE_COST), selected_start, selected_end
        )
        stress_metrics, stress_daily = _metrics_for_frames(
            selected_stress, selected_start, selected_end
        )
        # Per-pair checks are intentionally reported separately; BTC/ETH are not
        # treated as independent confirmations.
        pair_metrics: dict[str, dict[str, Any]] = {}
        for pair in pairs:
            pair_metrics[pair] = performance_metrics(
                daily_portfolio_returns(
                    {pair: _scenario_frames(selected_base, BASE_COST)[pair]},
                    selected_start,
                    selected_end,
                ),
                _scenario_frames(selected_base, BASE_COST)[pair],
            )
        candidate_matrix_rows: list[pd.Series] = []
        candidate_trial_ids: list[str] = []
        for spec in family_specs:
            tid = trial_ids[spec]
            series = validation_daily[tid]
            if series:
                candidate_matrix_rows.append(pd.concat(series).sort_index())
                candidate_trial_ids.append(tid)
        if candidate_matrix_rows:
            candidate_matrix = pd.DataFrame(candidate_matrix_rows)
            candidate_matrix.index = candidate_trial_ids
            candidate_matrix = candidate_matrix.loc[:, ~candidate_matrix.columns.duplicated()]
        else:
            candidate_matrix = pd.DataFrame()
        selected_series = selected_daily.reindex(candidate_matrix.columns).fillna(0.0)
        dsr = deflated_sharpe(selected_series, candidate_matrix)
        rc = white_reality_check(
            selected_series,
            candidate_matrix,
            draws=stats_draws,
        )
        mc = monte_carlo_equity(selected_series, draws=stats_draws)
        positive_fold_fraction = (
            float(np.mean([row["expectancy"] > 0 for row in selected_fold_metrics[hypothesis]]))
            if selected_fold_metrics[hypothesis]
            else 0.0
        )
        family_rows = trial_results[trial_results["hypothesis_id"] == hypothesis]
        positive_parameter_fraction = (
            float((family_rows["validation_expectancy"] > 0).mean())
            if not family_rows.empty
            else 0.0
        )
        btc_pair = next((pair for pair in pairs if pair.startswith("BTC/")), None)
        eth_pair = next((pair for pair in pairs if pair.startswith("ETH/")), None)
        both_pairs = (
            btc_pair is not None
            and eth_pair is not None
            and _safe_float(pair_metrics[btc_pair].get("expectancy")) > 0
            and _safe_float(pair_metrics[eth_pair].get("expectancy")) > 0
        )
        gates = {
            "min_oos_trades": int(base_metrics.get("trades", 0)) >= ACCEPTANCE.min_oos_trades,
            "positive_fold_fraction": positive_fold_fraction >= ACCEPTANCE.min_positive_fold_fraction,
            "base_profit_factor": _safe_float(base_metrics.get("profit_factor"))
            >= ACCEPTANCE.min_base_profit_factor,
            "stress_profit_factor": _safe_float(stress_metrics.get("profit_factor"))
            >= ACCEPTANCE.min_stress_profit_factor,
            "dsr": _safe_float(dsr.get("dsr")) >= ACCEPTANCE.min_dsr,
            "reality_check": _safe_float(rc.get("p_value")) <= ACCEPTANCE.max_reality_check_p,
            "positive_parameter_fraction": positive_parameter_fraction
            >= ACCEPTANCE.min_positive_parameter_fraction,
            "both_pairs": both_pairs,
        }
        summary = {
            "hypothesis_id": hypothesis,
            "selected_trial_ids": ";".join(
                str(row["trial_id"]) for row in selected_fold_metrics[hypothesis]
            ),
            "oos_trades": base_metrics.get("trades", 0),
            "oos_expectancy": base_metrics.get("expectancy", np.nan),
            "oos_profit_factor": base_metrics.get("profit_factor", np.nan),
            "oos_total_return": base_metrics.get("total_return", np.nan),
            "oos_max_drawdown": base_metrics.get("max_drawdown", np.nan),
            "oos_sharpe": base_metrics.get("sharpe", np.nan),
            "stress_expectancy": stress_metrics.get("expectancy", np.nan),
            "stress_profit_factor": stress_metrics.get("profit_factor", np.nan),
            "positive_fold_fraction": positive_fold_fraction,
            "positive_parameter_fraction": positive_parameter_fraction,
            "dsr": dsr.get("dsr", np.nan),
            "dsr_effective_trials": dsr.get("effective_trials", 0),
            "reality_check_p": rc.get("p_value", np.nan),
            "reality_check_null_p95": rc.get("null_p95", np.nan),
            "monte_carlo_terminal_p05": mc.get("terminal_return_p05", np.nan),
            "monte_carlo_terminal_p95": mc.get("terminal_return_p95", np.nan),
            "monte_carlo_max_dd_p95": mc.get("max_dd_p95", np.nan),
            "btc_expectancy": pair_metrics.get(btc_pair or "", {}).get("expectancy", np.nan),
            "eth_expectancy": pair_metrics.get(eth_pair or "", {}).get("expectancy", np.nan),
            **{f"gate_{name}": passed for name, passed in gates.items()},
            "survivor": all(gates.values()),
        }
        summaries.append(summary)
        if summary["survivor"]:
            survivors.append(summary)
        for pair in pairs:
            frame = _scenario_frames(selected_base, BASE_COST)[pair]
            if not frame.empty:
                frame = frame.copy()
                frame["hypothesis_id"] = hypothesis
                all_selected_trade_rows.append(frame)

    summary_frame = pd.DataFrame(summaries)
    leaderboard = (
        summary_frame.sort_values(["survivor", "oos_sharpe"], ascending=[False, False])
        if not summary_frame.empty
        else pd.DataFrame()
    )
    selected_trades = (
        pd.concat(all_selected_trade_rows, ignore_index=True)
        if all_selected_trade_rows
        else pd.DataFrame()
    )
    manifest = {
        "run_id": run_id,
        "spec_version": SPEC_VERSION,
        "source_hash": _source_hash(),
        "data_fingerprint": data_fingerprint,
        "data_start": str(evaluation_start),
        "data_end": str(evaluation_end),
        "pairs": list(pairs),
        "full_trial_count": len(generate_specs()),
        "executed_trial_count": len(specs),
        "truncated_search": truncated,
        "monte_carlo_draws": stats_draws,
        "folds": [fold.as_dict() for fold in folds],
        "walk_forward_override": fold_override,
        "preregistration": preregistration_manifest(),
        "data_audits": audits,
        "funding_limitation": (
            "The local futures directory uses legacy 8h funding/mark files, while "
            "current Freqtrade 2026.8 parity expects canonical 1h funding/mark. "
            "This research run uses observed funding events and the adverse-payer "
            "convention; mark-notional settlement and missing-event recovery are not "
            "claimed."
        ),
        "portfolio_limitation": (
            "BTC and ETH are equal-weight standalone sleeves for hypothesis testing. "
            "Families are not simultaneously capital-competing and this is not a "
            "live portfolio backtest."
        ),
    }

    trial_catalog = [
        {"trial_id": trial_ids[spec], **spec.as_dict()} for spec in specs
    ]
    selected_specs = [
        {
            "fold_id": int(row["fold_id"]),
            "hypothesis_id": row["hypothesis_id"],
            "trial_id": row["trial_id"],
            "params": json.loads(row["params"]),
        }
        for _, row in fold_winners.iterrows()
    ] if not fold_winners.empty else []
    (write_dir / "trial_catalog.json").write_text(
        json.dumps(trial_catalog, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    (write_dir / "selected_specs.json").write_text(
        json.dumps(selected_specs, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    trial_results.to_csv(write_dir / "trial_results.csv", index=False)
    fold_winners.to_csv(write_dir / "fold_winners.csv", index=False)
    summary_frame.to_csv(write_dir / "hypothesis_summary.csv", index=False)
    leaderboard.to_csv(write_dir / "leaderboard.csv", index=False)
    selected_trades.to_csv(write_dir / "selected_trades.csv", index=False)
    (write_dir / "survivors.json").write_text(
        json.dumps(survivors, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    write_heatmaps(trial_results, write_dir)
    write_report(write_dir, manifest, summary_frame, fold_winners)
    # The manifest is written last inside the temporary directory, then the
    # completed directory is promoted atomically. A failed run never looks like
    # a valid result set.
    (write_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    if output.exists():
        if not overwrite:
            raise FileExistsError(f"Output directory appeared during run: {output}")
        shutil.rmtree(output)
    write_dir.replace(output)
    return FactoryRun(
        output_dir=output,
        manifest=manifest,
        trial_results=trial_results,
        fold_winners=fold_winners,
        hypothesis_summary=summary_frame,
        leaderboard=leaderboard,
        survivors=survivors,
    )
