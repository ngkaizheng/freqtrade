"""Walk-forward selection and dependence-aware statistical checks."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import NormalDist
from typing import Any

import numpy as np
import pandas as pd

from tools.strategy_factory.data import as_utc
from tools.strategy_factory.engine import daily_portfolio_returns, performance_metrics
from tools.strategy_factory.preregistration import STATISTICS, WALK_FORWARD


@dataclass(frozen=True)
class Fold:
    fold_id: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    validation_start: pd.Timestamp
    validation_end: pd.Timestamp

    def as_dict(self) -> dict[str, Any]:
        return {
            "fold_id": self.fold_id,
            "train_start": self.train_start,
            "train_end": self.train_end,
            "validation_start": self.validation_start,
            "validation_end": self.validation_end,
        }


def make_folds(
    data_start: str | pd.Timestamp,
    data_end: str | pd.Timestamp,
    config=WALK_FORWARD,
) -> list[Fold]:
    """Create rolling train/validation windows with a fixed embargo."""

    start = as_utc(data_start)
    end = as_utc(data_end)
    first_validation = as_utc(config.first_validation)
    validation_start = first_validation
    folds: list[Fold] = []
    fold_id = 0
    while validation_start < end:
        train_start = validation_start - pd.Timedelta(days=config.train_days)
        train_end = validation_start - pd.Timedelta(hours=config.embargo_hours)
        validation_end = validation_start + pd.Timedelta(days=config.validation_days)
        if train_start >= start and validation_end <= end:
            folds.append(
                Fold(
                    fold_id=fold_id,
                    train_start=train_start,
                    train_end=train_end,
                    validation_start=validation_start,
                    validation_end=validation_end,
                )
            )
            fold_id += 1
        validation_start += pd.Timedelta(days=config.step_days)
    return folds


def filter_trades(
    trades: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    """Keep only trades wholly contained in a fold (purge boundary crosses)."""

    if trades.empty:
        return trades.copy()
    return trades[
        (trades["entry_time"] >= start) & (trades["exit_time"] < end)
    ].copy()


def metrics_for_fold(
    trade_frames: dict[str, pd.DataFrame],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    filtered = {
        pair: filter_trades(frame, start, end)
        for pair, frame in trade_frames.items()
    }
    daily = daily_portfolio_returns(filtered, start, end)
    all_trades = pd.concat(list(filtered.values()), ignore_index=True) if filtered else pd.DataFrame()
    metrics = performance_metrics(daily, all_trades)
    metrics["start"] = start
    metrics["end"] = end
    return metrics


def choose_training_winner(
    candidate_rows: list[dict[str, Any]],
    min_trades: int = WALK_FORWARD.min_train_trades,
) -> dict[str, Any] | None:
    eligible = [row for row in candidate_rows if int(row.get("trades", 0)) >= min_trades]
    if not eligible:
        eligible = candidate_rows
    if not eligible:
        return None
    return sorted(
        eligible,
        key=lambda row: (
            -float(row.get("net_sharpe", -np.inf))
            if np.isfinite(float(row.get("net_sharpe", -np.inf)))
            else np.inf,
            -float(row.get("expectancy", -np.inf))
            if np.isfinite(float(row.get("expectancy", -np.inf)))
            else np.inf,
            str(row.get("trial_id", "")),
        ),
    )[0]


def _daily_sharpe(values: np.ndarray, annualization: int = STATISTICS.annualization) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    mean = np.nanmean(values, axis=1)
    standard_deviation = np.nanstd(values, axis=1, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        result = mean / standard_deviation * np.sqrt(annualization)
    result[~np.isfinite(result)] = 0.0
    return result


def effective_trial_count(candidate_returns: pd.DataFrame) -> float:
    """Participation-ratio estimate of correlated candidate trials."""

    if candidate_returns.empty or candidate_returns.shape[1] < 2:
        return float(max(1, candidate_returns.shape[0]))
    values = candidate_returns.fillna(0.0).to_numpy(dtype=float)
    std = values.std(axis=1, ddof=1)
    values = values[std > 0]
    if len(values) < 2:
        return float(max(1, candidate_returns.shape[0]))
    correlation = np.corrcoef(values)
    correlation = np.nan_to_num(correlation, nan=0.0)
    np.fill_diagonal(correlation, 1.0)
    eigenvalues = np.linalg.eigvalsh(correlation)
    eigenvalues = eigenvalues[eigenvalues > 0]
    if not len(eigenvalues):
        return float(max(1, candidate_returns.shape[0]))
    return float(np.clip(eigenvalues.sum() ** 2 / np.square(eigenvalues).sum(), 1, len(values)))


def _normal_ppf(value: float) -> float:
    value = min(max(value, 1e-12), 1 - 1e-12)
    return NormalDist().inv_cdf(value)


def expected_max_daily_sharpe(variance: float, trials: float) -> float:
    if trials < 2 or variance <= 0:
        return 0.0
    euler = 0.5772156649015329
    z1 = _normal_ppf(1 - 1 / trials)
    z2 = _normal_ppf(1 - 1 / (trials * np.e))
    return float(np.sqrt(variance) * ((1 - euler) * z1 + euler * z2))


def probabilistic_sharpe(
    returns: pd.Series,
    benchmark_daily: float = 0.0,
    annualization: int = STATISTICS.annualization,
) -> tuple[float, float, float, float, float]:
    """Return PSR, daily SR, annualized SR, skew and kurtosis."""

    values = pd.Series(returns, dtype=float).replace([np.inf, -np.inf], np.nan).dropna().to_numpy()
    if len(values) < 30:
        return np.nan, np.nan, np.nan, np.nan, np.nan
    standard_deviation = float(values.std(ddof=1))
    if standard_deviation == 0:
        return np.nan, 0.0, 0.0, np.nan, np.nan
    daily_sr = float(values.mean() / standard_deviation)
    skew = float(pd.Series(values).skew())
    kurtosis = float(pd.Series(values).kurtosis()) + 3.0
    denominator = 1 - skew * daily_sr + (kurtosis - 1) * daily_sr**2 / 4
    if denominator <= 0:
        return np.nan, daily_sr, daily_sr * np.sqrt(annualization), skew, kurtosis
    z = (daily_sr - benchmark_daily) * np.sqrt(len(values) - 1) / np.sqrt(denominator)
    psr = NormalDist().cdf(z)
    return psr, daily_sr, daily_sr * np.sqrt(annualization), skew, kurtosis


def deflated_sharpe(
    selected_returns: pd.Series,
    candidate_returns: pd.DataFrame,
    trials: int | None = None,
) -> dict[str, float | int]:
    """Calculate a DSR using common-period daily net returns.

    The input is a candidate-return matrix, not raw trade P&Ls. Serial
    dependence remains a limitation; the effective trial count adjusts only
    cross-candidate correlation.
    """

    if candidate_returns.empty:
        return {
            "dsr": np.nan,
            "psr": np.nan,
            "daily_sharpe": np.nan,
            "annualized_sharpe": np.nan,
            "effective_trials": 0,
            "trial_variance": np.nan,
        }
    common = candidate_returns.reindex(columns=candidate_returns.columns).fillna(0.0)
    values = common.to_numpy(dtype=float)
    means = np.nanmean(values, axis=1)
    standard_deviations = np.nanstd(values, axis=1, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        daily_sharpes = means / standard_deviations
    daily_sharpes = np.nan_to_num(daily_sharpes, nan=0.0, posinf=0.0, neginf=0.0)
    variance = float(np.var(daily_sharpes, ddof=1)) if len(daily_sharpes) > 1 else 0.0
    effective_trials = effective_trial_count(common)
    n_trials = max(1, int(round(trials or effective_trials)))
    expected_max = expected_max_daily_sharpe(variance, n_trials)
    psr, daily_sr, annualized_sr, _, _ = probabilistic_sharpe(
        selected_returns.reindex(common.columns).fillna(0.0),
        benchmark_daily=expected_max,
    )
    return {
        "dsr": psr,
        "psr": psr,
        "daily_sharpe": daily_sr,
        "annualized_sharpe": annualized_sr,
        "effective_trials": int(round(effective_trials)),
        "trial_variance": variance,
    }


def _circular_block_indices(
    n: int,
    block_length: int,
    rng: np.random.Generator,
) -> np.ndarray:
    if n <= 0:
        return np.array([], dtype=int)
    block_length = max(1, min(int(block_length), n))
    starts = rng.integers(0, n, size=int(np.ceil(n / block_length)))
    indices = np.concatenate([np.arange(start, start + block_length) % n for start in starts])
    return indices[:n]


def white_reality_check(
    selected_returns: pd.Series,
    candidate_returns: pd.DataFrame,
    block_length: int = STATISTICS.monte_carlo_block_days,
    draws: int = STATISTICS.monte_carlo_draws,
    seed: int = STATISTICS.random_seed,
) -> dict[str, float | int]:
    """Block-bootstrap max-statistic check against a centered null.

    This is a Reality-Check-style sensitivity test, not a claim that a
    non-significant result proves the absence of an edge. The complete candidate
    matrix used in the run must be supplied, including rejected configurations.
    """

    if candidate_returns.empty or selected_returns.empty:
        return {"observed_sharpe": np.nan, "null_p95": np.nan, "p_value": np.nan, "draws": 0}
    common = candidate_returns.copy()
    selected = selected_returns.reindex(common.columns).fillna(0.0)
    observed = float(_daily_sharpe(selected.to_numpy(dtype=float)[None, :])[0])
    centered = common.fillna(0.0).to_numpy(dtype=float)
    centered = centered - centered.mean(axis=1, keepdims=True)
    rng = np.random.default_rng(seed)
    n = centered.shape[1]
    null_max = np.empty(draws, dtype=float)
    for draw in range(draws):
        indices = _circular_block_indices(n, block_length, rng)
        null_max[draw] = float(np.max(_daily_sharpe(centered[:, indices])))
    exceedances = int(np.count_nonzero(null_max >= observed))
    return {
        "observed_sharpe": observed,
        "null_p95": float(np.percentile(null_max, 95)),
        "p_value": float((exceedances + 1) / (draws + 1)),
        "draws": int(draws),
    }


def monte_carlo_equity(
    daily_returns: pd.Series,
    block_length: int = STATISTICS.monte_carlo_block_days,
    draws: int = STATISTICS.monte_carlo_draws,
    seed: int = STATISTICS.random_seed,
) -> dict[str, float | int]:
    """Joint calendar-time block bootstrap for terminal return and max DD."""

    values = pd.Series(daily_returns, dtype=float).fillna(0.0).to_numpy()
    n = len(values)
    if n == 0:
        return {"terminal_return_p05": np.nan, "terminal_return_p95": np.nan, "max_dd_p95": np.nan, "draws": 0}
    rng = np.random.default_rng(seed)
    terminals = np.empty(draws, dtype=float)
    drawdowns = np.empty(draws, dtype=float)
    for draw in range(draws):
        indices = _circular_block_indices(n, block_length, rng)
        path = np.cumprod(1 + values[indices])
        terminals[draw] = path[-1] - 1
        drawdowns[draw] = float(np.min(path / np.maximum.accumulate(path) - 1))
    return {
        "terminal_return_p05": float(np.percentile(terminals, 5)),
        "terminal_return_p95": float(np.percentile(terminals, 95)),
        "max_dd_p95": float(np.percentile(drawdowns, 95)),
        "draws": int(draws),
    }
