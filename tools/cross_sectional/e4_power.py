"""
The dependence correction the IC table is missing.

`e4_feasibility.py` reports t = mean(IC)/std(IC) * sqrt(n) with n = 2375
daily observations. But those 2375 ICs are computed from a 30-day forward
return sampled every day, so consecutive ICs share 29 of 30 days of overlap.
The naive t is inflated by roughly sqrt(IAT) -- the same defect this project
found in Strategy Factory V2 Phase C, where 17 "significant" hypotheses
became 2 once the variance was deflated.

This computes the integrated autocorrelation time of the IC series and the
deflated t. If the deflated t does not clear 2, there is nothing to
pre-register and the line stops here.

Run:  .venv\\Scripts\\python.exe tools\\cross_sectional\\e4_power.py
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "user_data/universe/raw_daily"
MAX_LAG = 30


def acf(series: np.ndarray, max_lag: int) -> np.ndarray:
    v = np.asarray(series, float)
    v = v - v.mean()
    den = float((v ** 2).sum())
    if den <= 0:
        return np.zeros(max_lag)
    return np.array([float((v[l:] * v[:-l]).sum() / den) for l in range(1, max_lag + 1)])


def iat(series: np.ndarray, max_lag: int = MAX_LAG) -> tuple[float, int, float]:
    """Integrated autocorrelation time, truncated at the first non-positive
    lag, exactly as tools/strategy_factory_v2/uncertainty.py does it."""
    a = acf(series, max_lag)
    total = 0.0
    for rho in a:
        if rho <= 0:
            break
        total += rho
    tau = 1.0 + 2.0 * total
    n = len(series)
    return tau, n, n / max(tau, 1.0)


def load():
    series = {}
    for f in sorted(RAW.glob("*_1d.csv.gz")):
        sym = f.name.replace("_1d.csv.gz", "")
        d = pd.read_csv(f)
        d["date"] = pd.to_datetime(d["date"], format="%Y-%m-%d", errors="coerce")
        d = d.dropna(subset=["date", "close"]).set_index("date").sort_index()
        d = d[~d.index.duplicated()]
        if (d["close"].pct_change() < -0.90).any():
            continue
        series[sym] = d["close"]
    return pd.concat(series, axis=1).sort_index()


def main() -> None:
    px = load()
    print(f"panel {px.shape[1]} symbols\n")
    print("=" * 84)
    print("IC t-STATISTICS, naive versus dependence-adjusted")
    print("=" * 84)
    print(f"{'form':>5} {'hold':>5} {'n':>6} {'IAT':>6} {'ess':>8} "
          f"{'IC':>9} {'t_naive':>9} {'t_adj':>8}")
    print("-" * 84)

    rows = []
    for hold in (1, 7, 30):
        fwd = px.pct_change(periods=hold, fill_method=None).shift(-hold)
        for form in (1, 7, 30):
            s = px.pct_change(periods=form, fill_method=None)
            pair = pd.concat([s.stack(), fwd.stack()], axis=1).dropna()
            ic = pair.groupby(level=0).corr().iloc[0::2, -1].dropna()
            if len(ic) < 60:
                continue
            tau, n, ess = iat(ic.to_numpy())
            t_naive = ic.mean() / ic.std(ddof=1) * math.sqrt(n)
            t_adj = t_naive * math.sqrt(min(1.0, ess / n))
            rows.append((form, hold, n, tau, ess, ic.mean(), t_naive, t_adj))
            print(f"{form:>5} {hold:>5} {n:>6} {tau:>6.2f} {ess:>8.1f} "
                  f"{ic.mean():>+9.4f} {t_naive:>+9.2f} {t_adj:>+8.2f}")

    best = max(rows, key=lambda r: abs(r[7]))
    n_trials = len(rows)
    print()
    print("=" * 84)
    print("VERDICT")
    print("=" * 84)
    print(f"  strongest member : form {best[0]}d / hold {best[1]}d")
    print(f"  naive t           : {best[6]:+.2f}")
    print(f"  dependence-adj t  : {best[7]:+.2f}   (IAT {best[3]:.2f}, "
          f"effective N {best[4]:.0f} of {best[2]})")
    print(f"  family correction : /sqrt({n_trials}) = "
          f"{abs(best[7])/math.sqrt(n_trials):.2f}")
    corrected = abs(best[7]) / math.sqrt(n_trials)
    print()
    if corrected >= 2.0:
        print("  CLEARED. The strongest member survives the dependence adjustment")
        print("  AND the family correction. There is something here worth one")
        print("  pre-registered confirmation.")
    else:
        print("  NOT CLEARED. The naive t is inflated by the overlapping forward")
        print("  window exactly the way Phase C's 17 'significant' hypotheses were.")
        print("  This is the same defect a third time, caught this time before the")
        print("  experiment rather than after it.")


if __name__ == "__main__":
    main()
