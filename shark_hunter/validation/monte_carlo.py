"""Monte Carlo trade reshuffling (spec section 43).

Answers the only question a trade sequence can answer honestly: if the trades
had arrived in a different order, or had been drawn from the same
distribution by chance, how would the equity path have looked?  It does not
test whether the signal works -- that is the out-of-sample test -- it tests
whether *this particular ordering* of losing trades is load-bearing.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _equity_from_r(rs: np.ndarray, risk_fraction: float = 0.005) -> np.ndarray:
    eq = 1.0
    out = np.empty(len(rs) + 1)
    out[0] = 1.0
    for i, r in enumerate(rs):
        eq *= max(0.0, 1.0 + r * risk_fraction)
        out[i + 1] = eq
    return out


def _equity_batch(rs_2d: np.ndarray, risk_fraction: float = 0.005) -> np.ndarray:
    """Vectorised compounded equity for a batch of resampled paths.

    ``np.cumprod`` replaces what was a per-trade Python loop; at 10,000 paths
    x 60,000 trades the loop version is ~600M iterations and does not finish.
    """
    growth = np.maximum(0.0, 1.0 + rs_2d * risk_fraction)
    out = np.empty((rs_2d.shape[0], rs_2d.shape[1] + 1))
    out[:, 0] = 1.0
    np.cumprod(growth, axis=1, out=out[:, 1:])
    return out


def _max_drawdown(equity: np.ndarray) -> float:
    peak = np.maximum.accumulate(equity)
    return float((equity / peak - 1.0).min())


def _drawdown_r(cum: np.ndarray) -> float:
    """Max peak-to-trough decline of a *cumulative R* path, in R units.

    The equity ratio ``cum/peak - 1`` is undefined here: a cumulative R series
    that runs negative crosses zero, and dividing by a near-zero running peak
    produces nonsense instead of a drawdown.  The decline
    ``cum - running_max(cum)`` is well defined for any sign and is what
    "drawdown" means in R space.
    """
    return float((cum - np.maximum.accumulate(cum)).min())


def _max_drawdown_batch(equity_2d: np.ndarray) -> np.ndarray:
    """Row-wise cumulative-R drawdown for a batch of paths."""
    return (equity_2d - np.maximum.accumulate(equity_2d, axis=1)).min(axis=1)


def monte_carlo(trades: pd.DataFrame, *, n_simulations: int = 10_000,
                risk_fraction: float = 0.005, seed: int = 20260926,
                block_size: int | None = None) -> dict:
    """Resample trades with replacement and summarise the outcome.

    ``block_size`` enables a circular block bootstrap, which preserves
    short-run autocorrelation (a run of losses stays a run of losses).  With
    ``block_size=None`` trades are shuffled independently.

    The primary output is the distribution of **expectancy** (mean R per
    trade), not the compounded terminal return.  With tens of thousands of
    trades at a fixed fractional risk, compounding saturates at -100% for
    every resampling, so the terminal return carries no information while the
    expectancy distribution answers the real question: is the observed edge
    distinguishable from a different ordering or a different draw of the same
    trades?  The compounded figures are still reported, with the saturation
    made explicit rather than hidden.
    """
    if trades.empty:
        return {"n_trades": 0, "n_simulations": n_simulations,
                "note": "no trades to resample"}

    rs = trades["r_net"].fillna(0.0).to_numpy()
    n = len(rs)
    rng = np.random.default_rng(seed)

    # Chunked: a full 10,000 x 62,955 index matrix is 4.7 GiB and blows up on
    # a pooled multi-symbol study.  Chunking caps the working set and changes
    # nothing about the result, since the draws are independent.
    terminal = np.empty(n_simulations)
    max_dd = np.empty(n_simulations)
    expectancy = np.empty(n_simulations)
    total_r = np.empty(n_simulations)
    chunk = max(1, min(500, int(4_000_000 // max(n, 1))))

    for start in range(0, n_simulations, chunk):
        size = min(chunk, n_simulations - start)
        if block_size and block_size > 1:
            starts = rng.integers(0, n, size=(size, n))
            offsets = np.arange(block_size) % n
            idx = (starts[:, :, None] + offsets[None, None, :]).reshape(size, -1)[:, :n]
            samples = rs[idx]
        else:
            samples = rs[rng.integers(0, n, size=(size, n))]
        expectancy[start:start + size] = samples.mean(axis=1)
        total_r[start:start + size] = samples.sum(axis=1)
        # Drawdown on the cumulative *R* path, which does not saturate the way
        # a compounded equity path does at 60k trades.
        cum = np.cumsum(samples, axis=1)
        max_dd[start:start + size] = _max_drawdown_batch(cum)
        eq = _equity_batch(samples, risk_fraction)
        terminal[start:start + size] = eq[:, -1] - 1.0

    observed_eq = _equity_from_r(rs, risk_fraction)
    observed_cum = np.cumsum(rs)
    return {
        "n_trades": n,
        "n_simulations": n_simulations,
        "block_size": block_size or 1,
        "seed": seed,
        "observed_expectancy_r": float(rs.mean()),
        "observed_total_r": float(rs.sum()),
        "observed_max_drawdown_r": _drawdown_r(observed_cum),
        # --- primary: does the edge survive reshuffling? ---
        "expectancy_p05": float(np.percentile(expectancy, 5)),
        "expectancy_p50": float(np.percentile(expectancy, 50)),
        "expectancy_p95": float(np.percentile(expectancy, 95)),
        "prob_expectancy_negative": float((expectancy < 0).mean()),
        "total_r_p05": float(np.percentile(total_r, 5)),
        "total_r_p50": float(np.percentile(total_r, 50)),
        "total_r_p95": float(np.percentile(total_r, 95)),
        # --- secondary: compounded path, saturating by construction ---
        "terminal_return_p05": float(np.percentile(terminal, 5)),
        "terminal_return_p50": float(np.percentile(terminal, 50)),
        "terminal_return_p95": float(np.percentile(terminal, 95)),
        "max_drawdown_p05": float(np.percentile(max_dd, 5)),
        "max_drawdown_p50": float(np.percentile(max_dd, 50)),
        "max_drawdown_p95": float(np.percentile(max_dd, 95)),
        "prob_loss": float((terminal < 0).mean()),
        "compounding_saturated": bool(np.all(terminal <= -0.999)),
        "note": ("max_drawdown_* is measured in cumulative R, not percent of "
                 "equity; terminal_return_* saturates at -100% for long runs and "
                 "is reported only for completeness"),
    }
