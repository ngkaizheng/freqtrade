"""Feasibility of a forward test: how long would it actually take?

Phase 3 established that the 4h edge (+0.043R per trade over the full sample)
sits *below* the minimum detectable effect of the historical data (+0.099R).
The natural next proposal is "run it forward for 12 months and see".

This module answers whether that is even possible, before anyone commits to
it.  It is the difference between proposing an experiment and proposing a
number of months.

Two levers determine the answer, and only one of them is free:

* **Trade frequency** -- fixed by the strategy as frozen.
* **Breadth** -- the number of independent instruments.  This is the only
  lever that buys power quickly, and it is the one that must be decided now,
  before the forward window opens, because a protocol that widens its
  universe mid-test has re-optimised.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy import stats


@dataclass
class Feasibility:
    observed_edge_r: float
    per_trade_std_r: float
    trades_per_year: int
    n_symbols_now: int
    n_symbols_candidate: int
    n_observed: int
    months: dict[int, int]
    verdict: str

    def to_dict(self) -> dict:
        return {
            "observed_edge_r": self.observed_edge_r,
            "per_trade_std_r": self.per_trade_std_r,
            "trades_per_year": self.trades_per_year,
            "n_symbols_now": self.n_symbols_now,
            "n_symbols_candidate": self.n_symbols_candidate,
            "n_observed": self.n_observed,
            "months_to_detect": self.months,
            "verdict": self.verdict,
        }


def required_trades(edge_r: float, std_r: float, *, alpha: float = 0.05,
                    power: float = 0.80) -> int:
    """Trades needed to detect ``edge_r`` at ``power``, two-sided ``alpha``."""
    if std_r <= 0 or edge_r == 0:
        return int("inf")
    z = stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)
    return int(math.ceil((z * std_r / edge_r) ** 2))


def inflate_for_multiple_testing(n_trades: int, trials: int) -> int:
    """Bailey & Lopez de Prado's expected-max Sharpe deflation.

    Running ``trials`` configurations and keeping the best means the observed
    edge has to clear the bar set by the *luckiest* of them, not by zero.
    Applied as an effect-size inflation so the feasibility estimate already
    accounts for the search that produced the candidate.
    """
    if trials <= 1:
        return n_trades
    e = 0.5772156649015329
    a = stats.norm.ppf(1 - 1.0 / trials)
    b = stats.norm.ppf(1 - 1.0 / (trials * math.e))
    emax = (1 - e) * a + e * b          # per-observation units
    # Convert the expected-max Sharpe back into an effect multiple, using the
    # observed dispersion.  Conservative: uses the ratio directly.
    return int(math.ceil(n_trades * max(emax, 1.0) ** 2))


def deflated_feasibility(observed_edge_r: float, per_trade_std_r: float, *,
                         trials: int, n_obs: int | None = None,
                         alpha: float = 0.05) -> dict:
    """Is the edge detectable *after* accounting for having searched for it?

    **Units matter here, and getting them wrong is easy.** The Sharpe of a
    mean-over-n-observations is ``sr = mean(r)/std(r)``, whose standard error
    is ``1/sqrt(T)``.  The expected maximum of ``trials`` iid standard normals
    is ``emax(trials)`` -- but that is a *return-frequency* quantity, not a
    per-observation one.  Expressed in the same per-observation units as the
    observed Sharpe, the benchmark is

        SR0 = emax(trials) / sqrt(T)

    An earlier version of this function compared the per-observation Sharpe
    against the raw ``emax``, which is a units error: it makes the bar ~41x
    too high and turns a finite requirement into a spurious "undefined".

    The test itself is stated in the common units, where it is unambiguous::

        sr * sqrt(T)  >=  z_a + z_b + emax(trials)

    and the required sample size follows directly.
    """
    sr = observed_edge_r / per_trade_std_r
    emax = expected_max_sharpe(trials)
    z = stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(0.80)

    # Return-frequency units: the right-hand side and the left-hand side match.
    sr_annualised = sr * math.sqrt(n_obs) if n_obs else float("nan")
    n_needed_undeflated = int(math.ceil((z / sr) ** 2)) if sr > 0 else None
    n_needed_deflated = (int(math.ceil(((z + emax) / sr) ** 2))
                         if sr > 0 else None)
    return {
        "observed_sharpe_per_trade": sr,
        "observed_sharpe_return_freq": sr_annualised,
        "emax": emax,
        "luck_benchmark_per_obs": (emax / math.sqrt(n_obs)) if n_obs else float("nan"),
        "n_obs": n_obs,
        "trials": trials,
        "trades_needed_undeflated": n_needed_undeflated,
        "trades_needed_deflated": n_needed_deflated,
        # Fails the deflated bar at this sample size?
        "clears_luck_bar_here": bool(sr_annualised > emax) if n_obs else None,
    }


def expected_max_sharpe(trials: int) -> float:
    """E[max of ``trials`` iid standard normals], per-observation Sharpe units."""
    if trials <= 1:
        return 0.0
    e = 0.5772156649015329
    a = stats.norm.ppf(1 - 1.0 / trials)
    b = stats.norm.ppf(1 - 1.0 / (trials * math.e))
    return float((1 - e) * a + e * b)


def assess(observed_edge_r: float, per_trade_std_r: float, trades_per_year: int,
           n_symbols_now: int, n_symbols_candidate: int,
           n_observed: int, *, trials: int = 41_472,
           alpha: float = 0.05, power: float = 0.80) -> Feasibility:
    need = required_trades(observed_edge_r, per_trade_std_r, alpha=alpha, power=power)
    need_adj = inflate_for_multiple_testing(need, trials)
    years_needed = need_adj / max(trades_per_year, 1)

    months = {}
    for ns in (n_symbols_now, n_symbols_candidate):
        tpy = trades_per_year * ns / n_symbols_now
        y = need_adj / max(tpy, 1)
        months[ns] = int(math.ceil(y * 12))

    if years_needed > 30:
        verdict = ("INFEASIBLE at the current edge size. Even a decade of "
                   "forward data at today's breadth would not resolve it.")
    elif years_needed > 5:
        verdict = ("Marginal. A multi-year forward test could resolve it, but "
                   "that is a research commitment, not a trading plan.")
    else:
        verdict = "Feasible within a practical horizon."

    return Feasibility(observed_edge_r, per_trade_std_r, trades_per_year,
                       n_symbols_now, n_symbols_candidate, n_observed,
                       months, verdict)
