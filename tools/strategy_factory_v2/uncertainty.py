"""Uncertainty for serially dependent signal streams.

A pooled t-test assumes independent observations. Signals generated from
overlapping windows are emphatically not independent: two bars one hour apart
share most of their feature history, so their outcomes move together, and the
naive standard error is too small by roughly the square root of the effective
sample size.

Reporting that honestly means three things beyond a mean and a standard
deviation: how much the outcomes autocorrelate, how many *effectively
independent* observations there really are, and a confidence interval from a
block bootstrap that respects the dependence rather than assuming it away.

These are diagnostics. They are not gates, and nothing here is allowed to
change a selection threshold after the fact.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd


def autocorrelation(values: np.ndarray, max_lag: int = 20) -> dict[str, float]:
    """Sample autocorrelation at lags 1..``max_lag``."""

    series = np.asarray(values, dtype=float)
    series = series[np.isfinite(series)]
    n = len(series)
    if n < 10:
        return {"n": int(n), "acf": {}}
    centred = series - series.mean()
    denominator = float((centred**2).sum())
    if denominator <= 0:
        return {"n": int(n), "acf": {str(lag): 0.0 for lag in range(1, max_lag + 1)}}
    acf: dict[str, float] = {}
    for lag in range(1, max_lag + 1):
        if n - lag <= 1:
            break
        covariance = float((centred[:-lag] * centred[lag:]).sum())
        acf[str(lag)] = covariance / denominator
    return {"n": int(n), "acf": acf}


def effective_sample_size(values: np.ndarray, max_lag: int = 20) -> dict[str, float]:
    """Effective independent count from the integrated autocorrelation time.

    For a stationary series the integrated autocorrelation time is
    ``1 + 2 * sum(rho_lag)``, truncated at the first non-positive lag, and the
    effective sample size is ``n / tau``. Both are reported because a caller
    that disagrees with the truncation has a legitimate question and should be
    able to see what was assumed.
    """

    acf = autocorrelation(values, max_lag)
    n = acf.get("n", 0)
    if n == 0 or not acf.get("acf"):
        return {"n": n, "integrated_autocorrelation_time": 1.0, "effective_sample_size": float(n)}
    total = 0.0
    for lag in range(1, max_lag + 1):
        rho = acf["acf"].get(str(lag))
        if rho is None or rho <= 0:
            break
        total += rho
    tau = 1.0 + 2.0 * total
    return {
        "n": int(n),
        "integrated_autocorrelation_time": round(tau, 4),
        "effective_sample_size": round(max(1.0, n / tau), 2),
        "lag1_autocorrelation": round(acf["acf"].get("1", 0.0), 4),
    }


def circular_block_indices(n: int, block_length: int, rng: np.random.Generator) -> np.ndarray:
    """Circular block resample, matching the bootstrap the MVP used."""

    if n <= 0:
        return np.array([], dtype=int)
    block_length = max(1, min(int(block_length), n))
    starts = rng.integers(0, n, size=int(np.ceil(n / block_length)))
    indices = np.concatenate(
        [np.arange(start, start + block_length) % n for start in starts]
    )
    return indices[:n]


def block_bootstrap_ci(
    values: Sequence[float],
    statistic: str = "mean",
    draws: int = 2000,
    block_length: int = 24,
    seed: int = 20260926,
    confidence: float = 0.95,
) -> dict[str, Any]:
    """Confidence interval from a circular block bootstrap.

    The block length is the number of observations assumed to move together,
    which for hourly signals over a multi-day holding window is a matter of
    days rather than bars. It is reported alongside the interval so a reader
    can see the assumption rather than infer it.
    """

    series = np.asarray(values, dtype=float)
    series = series[np.isfinite(series)]
    n = len(series)
    if n < 10:
        return {
            "n": int(n),
            "status": "INSUFFICIENT_SAMPLE",
            "block_length": block_length,
            "draws": draws,
        }
    rng = np.random.default_rng(seed)
    fn = np.mean if statistic == "mean" else np.median
    samples = np.empty(draws, dtype=float)
    for draw in range(draws):
        samples[draw] = fn(series[circular_block_indices(n, block_length, rng)])
    alpha = (1.0 - confidence) / 2.0
    return {
        "n": int(n),
        "status": "OK",
        "statistic": statistic,
        "observed": float(fn(series)),
        "ci_low": float(np.percentile(samples, 100 * alpha)),
        "ci_high": float(np.percentile(samples, 100 * (1 - alpha))),
        "confidence": confidence,
        "block_length": block_length,
        "draws": draws,
        "seed": seed,
        "bootstrap_p_gt_zero": float((samples > 0).mean()),
        "note": (
            "The block length is the number of consecutive observations assumed "
            "to move together. It is reported rather than buried, because the "
            "interval is only as honest as that assumption."
        ),
    }


def uncertainty_report(
    returns: Sequence[float], block_length: int = 24, draws: int = 2000
) -> dict[str, Any]:
    """The full uncertainty picture for one return stream."""

    series = np.asarray(returns, dtype=float)
    series = series[np.isfinite(series)]
    if series.size == 0:
        return {"status": "NO_OBSERVATIONS", "n": 0}
    dependence = effective_sample_size(series)
    interval = block_bootstrap_ci(series, block_length=block_length, draws=draws)
    mean = float(series.mean())
    naive_se = float(series.std(ddof=1) / np.sqrt(len(series))) if len(series) > 1 else float("nan")
    ess = dependence.get("effective_sample_size", len(series))
    robust_se = float(series.std(ddof=1) / np.sqrt(max(1.0, ess))) if len(series) > 1 else float("nan")
    return {
        "status": "OK",
        "n": int(len(series)),
        "mean": mean,
        "lag1_autocorrelation": dependence.get("lag1_autocorrelation"),
        "integrated_autocorrelation_time": dependence.get(
            "integrated_autocorrelation_time"
        ),
        "effective_sample_size": ess,
        "naive_standard_error": naive_se,
        "dependence_adjusted_standard_error": robust_se,
        "naive_t_stat": (mean / naive_se) if naive_se and naive_se > 0 else None,
        "dependence_adjusted_t_stat": (mean / robust_se) if robust_se and robust_se > 0 else None,
        "bootstrap": interval,
        "interpretation": (
            "Where the effective sample size is well below n, the observations "
            "move together and the naive t-statistic overstates the evidence. "
            "The block-bootstrap interval is the honest one; it is a diagnostic, "
            "not a selection gate."
        ),
    }
