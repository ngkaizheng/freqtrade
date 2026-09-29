"""Deflated Sharpe Ratio (Bailey & Lopez de Prado) and White's Reality Check.

Both exist because of spec section 44: this study runs hundreds of strategy /
parameter combinations, so the best backtest result is expected to be
positive even if nothing works.  Neither statistic can manufacture an edge;
they can only say whether a reported one is distinguishable from the maximum
that pure luck would have produced across the same number of trials.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

EULER_MASCHERONI = 0.5772156649015329


# --------------------------------------------------------------------------
# Deflated Sharpe Ratio
# --------------------------------------------------------------------------

def deflated_sharpe(returns: np.ndarray, *, trials: int,
                    periods_per_year: float | None = None) -> dict:
    """DSR for a return series, deflated for the number of trials run.

    ``trials`` is the number of independent configurations tested.  It is the
    single most important input and the easiest to understate: the spec's
    parameter grid alone is hundreds of combinations before counting
    strategies, symbols, exits and timeframes.

    ``periods_per_year`` is only used to *display* an annualised Sharpe.  It
    must be supplied by the caller when the series is indexed by trade exit
    time, which is irregular: inferring a period from the median spacing of
    such an index produces an annualised figure that is an artefact of how
    trades happened to cluster, not a measure of anything.
    """
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    n = len(r)
    if n < 3:
        return {"dsr": np.nan, "note": "too few observations", "n": n, "trials": trials}

    mean = float(r.mean())
    std = float(r.std(ddof=1))
    if std <= 0:
        return {"dsr": 0.0, "note": "zero dispersion", "n": n, "trials": trials}

    sr = mean / std                                  # per-observation Sharpe
    z = sr * np.sqrt(n - 1)

    # Bailey & Lopez de Prado: the expected maximum Sharpe of `trials`
    # candidates is emax in RETURN-FREQUENCY units, so it must be added to
    # the observed Sharpe expressed the same way.  Comparing the per-observation
    # Sharpe against a bare emax is a units error that inflates the bar by
    # ~sqrt(T) and silently reports DSR = 0.
    sr0 = expected_max_sharpe(trials)               # return-frequency units

    skew = float(stats.skew(r))
    kurt = float(stats.kurtosis(r, fisher=False))    # non-excess kurtosis

    denom = np.sqrt(max(1e-12, 1.0 - skew * z + ((kurt - 1.0) / 4.0) * z ** 2))
    dsr = float(stats.norm.cdf((sr * np.sqrt(n - 1) - sr0) / denom))

    ppy = periods_per_year if periods_per_year else float("nan")
    return {
        "n": n,
        "trials": int(trials),
        "sharpe_per_obs": sr,
        "sharpe_return_freq": sr * np.sqrt(n),
        "periods_per_year": ppy,
        "sharpe_annualised": sr * np.sqrt(ppy) if np.isfinite(ppy) else np.nan,
        "emax_benchmark": float(sr0),
        "emax_per_obs": float(sr0 / np.sqrt(n)),
        "skew": skew,
        "kurtosis": kurt,
        "dsr": dsr,
        "significant_at_95": bool(dsr > 0.95),
    }


def expected_max_sharpe(trials: int) -> float:
    """E[max of ``trials`` iid standard normals], via the standard approximation.

    This is the Sharpe ratio that pure luck delivers when you run N tests and
    keep the best one.  Any strategy must beat *this*, not zero.
    """
    if trials <= 1:
        return 0.0
    from scipy.special import ndtri
    e = EULER_MASCHERONI
    a = ndtri(1.0 - 1.0 / trials)
    b = ndtri(1.0 - 1.0 / (trials * np.e))
    return float((1.0 - e) * a + e * b)


def _periods_per_year(returns) -> float:
    try:
        idx = pd.DatetimeIndex(returns.index)          # type: ignore[union-attr]
        if len(idx) > 2:
            step = pd.Series(idx).diff().median()
            seconds = step.total_seconds()
            if seconds and seconds > 0:
                return 365.25 * 24 * 3600 / seconds
    except Exception:                                   # noqa: BLE001
        pass
    return 252.0


# --------------------------------------------------------------------------
# White's Reality Check
# --------------------------------------------------------------------------

def reality_check(returns_by_strategy: dict[str, pd.Series], *,
                  block_size: int = 20, n_bootstrap: int = 5_000,
                  seed: int = 20260926) -> dict:
    """White's Reality Check on a panel of strategy return series.

    The null hypothesis is that *no* strategy has a positive mean.  The test
    statistic is the maximum mean across strategies; the bootstrap resamples
    time blocks to build its null distribution.  A small p-value means at
    least one strategy is genuinely positive; it does not say which, and it
    is deliberately conservative.

    A stationary bootstrap is used so that a strategy's own observations are
    shifted by a common random block draw, which is what makes the test valid
    for cross-correlated strategies (all of ours share the same market).
    """
    names = [k for k, v in returns_by_strategy.items() if v is not None and len(v)]
    if not names:
        return {"p_value": np.nan, "note": "no strategy series supplied"}

    common = returns_by_strategy[names[0]].index
    for n in names:
        common = common.intersection(returns_by_strategy[n].index)
    if len(common) < 10:
        return {"p_value": np.nan, "note": "no overlapping timestamps"}

    panel = np.column_stack([returns_by_strategy[n].reindex(common).to_numpy(dtype=float)
                             for n in names])
    t, k = panel.shape
    observed = float(np.nanmax(np.nanmean(panel, axis=0)))
    means = np.nanmean(panel, axis=0)
    best = int(np.nanargmax(means))

    rng = np.random.default_rng(seed)
    bs = min(block_size, max(2, t // 4))
    maxes = np.empty(n_bootstrap)
    for b in range(n_bootstrap):
        # Circular block bootstrap: choose a random start for each of ceil(T/bs)
        # blocks, then tile the resampled rows to length T.  Indices wrap
        # modulo T -- without that, a block starting near the end runs off the
        # end of the array.
        n_blocks = int(np.ceil(t / bs))
        starts = rng.integers(0, t, size=n_blocks)
        idx = ((starts[:, None] + np.arange(bs)[None, :]) % t).ravel()[:t]
        sample = panel[idx]
        maxes[b] = float(np.nanmax(np.nanmean(sample, axis=0)))

    p_value = float((maxes >= observed).mean())
    return {
        "n_strategies": k,
        "n_observations": t,
        "observed_max_mean": observed,
        "best_strategy": names[best],
        "bootstrap_mean_of_max": float(maxes.mean()),
        "p_value": p_value,
        "significant_at_95": bool(p_value < 0.05),
        "n_bootstrap": n_bootstrap,
        "block_size": bs,
    }


def spa_test(returns_by_strategy: dict[str, pd.Series], *,
             n_bootstrap: int = 5_000, seed: int = 20260926) -> dict:
    """Hansen SPA test: identifies *which* strategies survive.

    Strictly more powerful than White's test but answers a different question,
    so both are reported rather than one being silently substituted.
    """
    names = [k for k, v in returns_by_strategy.items() if v is not None and len(v)]
    if not names:
        return {"p_values": {}, "note": "no strategy series supplied"}
    common = returns_by_strategy[names[0]].index
    for n in names:
        common = common.intersection(returns_by_strategy[n].index)
    if len(common) < 10:
        return {"p_values": {}, "note": "no overlapping timestamps"}

    panel = np.column_stack([returns_by_strategy[n].reindex(common).to_numpy(dtype=float)
                             for n in names])
    t, k = panel.shape
    mu = np.nanmean(panel, axis=0)
    # Centre each strategy by its own mean, then ask whether the positive
    # deviations survive a bootstrap of the centred residuals.
    centred = panel - mu
    pos = np.clip(mu, 0, None)
    if pos.sum() <= 0:
        return {"p_values": {n: 1.0 for n in names}, "note": "no strategy has a positive mean"}

    weights = pos / pos.sum()
    t_obs = float(weights @ mu)
    rng = np.random.default_rng(seed)
    stats_null = np.empty(n_bootstrap)
    for b in range(n_bootstrap):
        idx = rng.integers(0, t, size=t)
        stats_null[b] = float(weights @ np.nanmean(centred[idx], axis=0))
    p = float((stats_null >= t_obs).mean())
    return {"best_p_value": p, "weights": dict(zip(names, weights.tolist())),
            "observed": t_obs, "n_bootstrap": n_bootstrap,
            "significant": {n: bool(p < 0.05) for n in names}}
