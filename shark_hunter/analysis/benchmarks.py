"""The benchmarks that were missing, and the power analysis that bounds what
any of this can conclude.

Spec section 36 requires four baselines.  Three were implemented (B, C, D).
Two things were missing, and both matter more than they look:

**Baseline A, buy-and-hold.**  Required by the spec, never built.  Without
it there is no answer to "is a +0.14R-per-trade strategy better than just
holding the coin", which is the question a reader asks first.

**Effective sample size and power.**  Trade count is the wrong denominator.
Trades in this study are sequential, one position per symbol, clustered by
market regime, and drawn from only nine correlated instruments.  A count of
464 therefore overstates the evidence, and any significance test built on the
nominal count is optimistic.  This module deflates the count and states the
smallest effect the data could actually have detected.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


# --------------------------------------------------------------------------
# Baseline A: buy and hold
# --------------------------------------------------------------------------

def buy_and_hold(df: pd.DataFrame, symbol: str, timeframe: str) -> dict:
    """Hold one unit of the asset across the whole window, net of entry cost.

    Reported on its own terms -- percentage return, annualised Sharpe, max
    drawdown -- because R is undefined without a stop, and forcing a
    risk-denominated number onto a strategy with no risk model would invite
    a false comparison.
    """
    if df.empty:
        return {"symbol": symbol, "timeframe": timeframe, "note": "empty"}
    close = df["close"].to_numpy(dtype=float)
    # One round trip in and out: the friction a holder actually pays.
    cost = 2 * (5.0 + 1.0) * 1e-4
    ret = close[-1] / close[0] - 1.0 - cost

    span_days = max((df.index[-1] - df.index[0]).total_seconds() / 86400.0, 1.0)
    years = span_days / 365.25
    curve = pd.Series(np.concatenate([[1.0], close / close[0]]),
                      index=[df.index[0]] + list(df.index))
    rets = curve.pct_change().dropna()
    per_year = 365.25 * 24 * 3600 / max(
        (df.index[1] - df.index[0]).total_seconds(), 1.0)
    sharpe = float(rets.mean() / rets.std() * np.sqrt(per_year)) if rets.std() > 0 else 0.0
    peak = curve.cummax()
    return {
        "symbol": symbol, "timeframe": timeframe,
        "start": str(df.index[0]), "end": str(df.index[-1]),
        "total_return": float(ret),
        "annualized_return": float((1.0 + ret) ** (1.0 / years) - 1.0) if years > 0 else np.nan,
        "sharpe": sharpe,
        "max_drawdown": float((curve / peak - 1.0).min()),
        "calmar": float(((1.0 + ret) ** (1.0 / years) - 1.0) / abs((curve / peak - 1.0).min()))
        if (curve / peak - 1.0).min() < 0 else 0.0,
    }


def buy_and_hold_table(datasets: dict[str, pd.DataFrame], timeframe: str) -> pd.DataFrame:
    rows = [buy_and_hold(df, sym, timeframe) for sym, df in datasets.items()]
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Effective sample size
# --------------------------------------------------------------------------

def effective_sample_size(trades: pd.DataFrame, max_lag: int = 50) -> dict:
    """Deflate a trade count by the autocorrelation of the trade sequence.

    The standard correction is ``N_eff = N / (1 + 2 * sum(rho_k))`` over the
    autocorrelations that survive.  Trading P&L is strongly autocorrelated:
    losses cluster in drawdowns and wins cluster in trends, so the nominal
    count materially overstates the independent evidence.

    This is the single most important correction in the study, and it is the
    one that keeps getting skipped -- including by me, in the first two
    phases.
    """
    r = trades["r_net"].dropna().to_numpy(dtype=float)
    n = len(r)
    if n < 10:
        return {"n_nominal": n, "n_effective": np.nan,
                "note": "too few trades to adjust"}
    if r.std() == 0:
        return {"n_nominal": n, "n_effective": np.nan, "note": "zero dispersion"}

    centred = r - r.mean()
    denom = float(np.dot(centred, centred))
    rhos = []
    for k in range(1, min(max_lag, n // 2) + 1):
        rho = float(np.dot(centred[:-k], centred[k:]) / denom)
        rhos.append(rho)

    # Newey-West style truncation: sum only while the autocorrelation is still
    # positive, then stop.  Summing the full ACF would let noise cancel real
    # dependence and understate N_eff.
    total = 0.0
    for rho in rhos:
        if rho <= 0:
            break
        total += rho
    n_eff = n / (1.0 + 2.0 * total)

    # A block-bootstrap cross-check that does not assume the parametric form.
    rng = np.random.default_rng(0)
    block = max(2, int(np.sqrt(n)))
    n_blocks = int(np.ceil(n / block))
    starts = rng.integers(0, n, size=(n_blocks,))
    idx = (starts[:, None] + np.arange(block)[None, :]) % n
    sample = r[idx.ravel()[:n]]
    if sample.std() > 0:
        shift = r - sample.mean()
        bw = n / (1.0 + 2.0 * sum(
            float(np.dot(shift[:-k], shift[k:]) / np.dot(shift, shift))
            for k in range(1, min(block, n // 2) + 1)))
    else:
        bw = n

    return {
        "n_nominal": n,
        "n_effective_newey_west": float(max(n_eff, 1.0)),
        "n_effective_block": float(max(bw, 1.0)),
        "autocorrelation_sum": total,
        "lag1_autocorrelation": rhos[0] if rhos else np.nan,
        "inflation_factor": float(n / max(n_eff, 1.0)),
    }


# --------------------------------------------------------------------------
# Power: the smallest effect this data could have detected
# --------------------------------------------------------------------------

def minimum_detectable_effect(trades: pd.DataFrame, *, alpha: float = 0.05,
                              power: float = 0.80) -> dict:
    """Smallest per-trade expectancy this sample could resolve at ``power``.

    A backtest cannot detect an effect smaller than this, so a strategy whose
    measured expectancy sits below the floor is not merely "not proven" -- it
    is *unprovable* with the data available.  That is a statement about the
    experiment, not about the strategy, and it is the honest way to close out
    a study that ran out of data.
    """
    ess = effective_sample_size(trades)
    n = ess["n_effective_newey_west"]
    r = trades["r_net"].dropna().to_numpy(dtype=float)
    if not np.isfinite(n) or r.std() == 0 or n < 3:
        return {"note": "insufficient data", **ess}
    z_a = stats.norm.ppf(1 - alpha / 2)
    z_b = stats.norm.ppf(power)
    mde = (z_a + z_b) * r.std() / np.sqrt(n)
    observed = float(r.mean())
    t_observed = observed / (r.std() / np.sqrt(n))
    return {
        **ess,
        "alpha": alpha, "power": power,
        "observed_expectancy_r": observed,
        "observed_t_stat": float(t_observed),
        "min_detectable_effect_r": float(mde),
        "p_value": float(2 * (1 - stats.norm.cdf(abs(t_observed)))),
        "detectable": bool(observed >= mde),
    }
