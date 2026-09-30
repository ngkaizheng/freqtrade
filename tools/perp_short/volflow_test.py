"""F-1: kline volume flow and volatility-as-signal, tested for INCREMENTAL information
beyond what the two existing trend books already carry.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\volflow_test.py

THE RULES ARE IN `docs-myself/PREREG_VOLFLOW_2026-09-30.md` AND ARE NOT RESTATED HERE
WITH DIFFERENT NUMBERS. This file is the instrument that applies them.

WHY "BIGGER |t|" IS THE WRONG TEST, AND WHAT REPLACES IT
---------------------------------------------------------
Both delivered books are price/volume trend books; the short book is essentially 4h
momentum. So a candidate that merely predicts returns is worthless. Gate B regresses the
forward return on `[mom_4, dVol_4, candidate]` and tests the CANDIDATE's incremental
coefficient. A feature can have a large univariate t and a zero incremental coefficient -
that is exactly what "the same information wearing a different feed" looks like, and it is
what closed the OI line.

CAUSALITY
----------
Every feature is computed from the bar and its own trailing history only. Nothing is
centred on the future, nothing is normalised by a statistic that includes later bars, and
the OI merge is reused as-is from the validated pipeline (backward `merge_asof`).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / "user_data" / "config_perp_forward_dry.json"
DATA4 = ROOT / "user_data" / "data" / "wide526" / "futures"
sys.path.insert(0, str(ROOT / "tools" / "perp_short"))
from oi_signal_test import ic_and_t, nw_lag, nw_t  # noqa: E402

HORIZONS = [4, 12, 24]
IC_PASS, T_PASS, PC_PASS = 0.02, 2.5, 0.01
CONTROLS = ["mom_4", "dVol_4"]
CONDX_MAX = 1e8      # above this the design is near-singular and the t is meaningless
MAX_SANE_T = 50.0   # a t above this is a numerical artefact, not a finding



def archive_symbol(pair: str) -> str:
    base, _, rest = pair.partition("/")
    return f"{base}{rest.split(':')[0]}"


def garman_klass(h, l, c, n=42):
    """Range-based volatility. Uses the high/low pair, which a close-to-close
    realised volatility does not - that is the point of including it."""
    r = np.log(c / c.shift(1))
    tr = np.log(h / l) ** 2
    return pd.Series(np.sqrt(((n - 2) / n) * tr.rolling(n, min_periods=n).mean()
                             - ((n - 1) / n) * (r ** 2).rolling(n, min_periods=n).mean()),
                     index=c.index).clip(lower=1e-9)


def features(x: pd.DataFrame) -> pd.DataFrame:
    o = pd.DataFrame(index=x.index)
    c, h, l, v = x["close"], x["high"], x["low"], x["volume"]
    r = np.log(c).diff()
    lr2 = r ** 2

    # ---- CONTROLS (unchanged from the OI round) --------------------------
    o["mom_4"] = c.pct_change(4)
    o["dVol_4"] = v.pct_change(4).replace([np.inf, -np.inf], np.nan)

    # ---- CANDIDATES: volume flow ----------------------------------------
    o["dVol_1"] = v.pct_change(1).replace([np.inf, -np.inf], np.nan)
    o["dVol_12"] = v.pct_change(12).replace([np.inf, -np.inf], np.nan)
    lv = np.log(v.where(v > 0))
    mu = lv.rolling(365 * 6, min_periods=200).mean()
    sd = lv.rolling(365 * 6, min_periods=200).std()
    o["vol_z"] = (lv - mu) / sd.replace(0.0, np.nan)
    sign = np.sign(c.diff())
    obv = (sign * v).cumsum()
    o["obv_slope"] = (obv - obv.shift(12)) / v.rolling(20, min_periods=20).mean()
    o["vol_x_sign"] = o["dVol_4"] * sign
    dollar_v = v * c
    o["amihud"] = r.abs() / dollar_v.replace(0.0, np.nan)
    o["vol_trend"] = v / v.rolling(20, min_periods=20).mean()

    # ---- CANDIDATES: volatility as a signal ------------------------------
    o["rv42"] = np.sqrt(lr2.rolling(42, min_periods=42).mean())
    o["rv_expand"] = o["rv42"] / o["rv42"].shift(42).replace(0.0, np.nan)
    o["vol_of_vol"] = o["rv42"].rolling(42, min_periods=42).std() / o["rv42"]
    o["gk_vol"] = garman_klass(h, l, c).where(lambda s: s > 0)
    o["rv_x_ret"] = o["rv42"] * r

    for hz in HORIZONS:
        o[f"fwd_{hz}"] = np.log(c.shift(-hz) / c)
    return o.replace([np.inf, -np.inf], np.nan)


def _resid_on(v: np.ndarray, X: np.ndarray) -> np.ndarray:
    """Residual of v after projecting out the columns of X (with an intercept)."""
    Xd = np.column_stack([np.ones(len(X)), X])
    b, *_ = np.linalg.lstsq(Xd, v, rcond=None)
    return v - Xd @ b


def incremental(y: pd.Series, xs: list[pd.Series]) -> tuple[float, float, int, float]:
    """Partial correlation of the LAST regressor with y given the earlier ones, and its
    Newey-West t, obtained by feeding the two residualised series into `ic_and_t` -
    the function `check_ic_t.py` already validated on a null, on autocorrelation and
    for power.

    THREE WRONG VERSIONS, EACH LOOKING LIKE A FINDING:

      v1  t = beta/se with an iid standard error. On `amihud` the design is
          near-singular, the SE collapses, and t came out at 1.04e17. The gate
          took the LARGEST |t|, so THE GATE PASSED ON THE ARTEFACT and named the
          worst feature in the table as the winner.
      v2  "fix": test mean(residual * regressor). The normal equations force that
          to be exactly zero, so every t printed 0.00 and a genuine signal
          (vol_z, partial r 0.048) was reported as failing.
      v3  Andrews-HAC covariance of the coefficient vector. Condition numbers were
          healthy (1-3) yet t came out in the hundreds, which I could not explain
          and therefore could not trust.

    This project's own rule: a number is not evidence until the step producing it
    is checked - and when three checks give three different answers the answer is to
    STOP building bespoke statistics, not to try a fourth variant. So v4 uses the
    textbook partial correlation (residualise BOTH sides on the controls) and takes
    its significance from the already-validated machinery. No new statistic.

    Guards kept, because v1's failure was not the formula but the absence of any
    check that the number was real: standardise, report the condition number and
    refuse above CONDX_MAX, and refuse any |t| above MAX_SANE_T.
    """
    j = pd.concat([y] + xs, axis=1).dropna()
    n = len(j)
    if n < 500:
        return float("nan"), float("nan"), n, float("nan")
    yv = j.iloc[:, 0].to_numpy(dtype=float)
    Xr = j.iloc[:, 1:].to_numpy(dtype=float)
    ysd = yv.std(ddof=1)
    xsd = Xr.std(axis=0, ddof=0)
    if ysd <= 0 or np.any(xsd <= 0):
        return float("nan"), float("nan"), n, float("inf")
    X = (Xr - Xr.mean(axis=0)) / xsd
    Xd = np.column_stack([np.ones(n), X])
    cond = float(np.linalg.cond(Xd))
    if not np.isfinite(cond) or cond > CONDX_MAX:
        return float("nan"), float("nan"), n, cond
    ry = _resid_on((yv - yv.mean()) / ysd, X[:, :-1])
    rx = _resid_on(X[:, -1], X[:, :-1])
    if rx.std(ddof=1) <= 0 or ry.std(ddof=1) <= 0:
        return float("nan"), float("nan"), n, cond
    _ic, t, _n2, _lag = ic_and_t(pd.Series(rx), pd.Series(ry))
    return float(t), float(np.corrcoef(rx, ry)[0, 1]), n, cond


def main() -> int:
    print("F-1  DO VOLUME FLOW / VOLATILITY ADD ANYTHING THE BOOKS DO NOT HAVE?\n")
    print("rules live in PREREG_VOLFLOW_2026-09-30.md; this file applies them\n")
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    names = [(archive_symbol(p), p.replace("/", "_").replace(":", "_"))
             for p in cfg["exchange"]["pair_whitelist"]]

    frames = []
    for arch, flat in names:
        f4 = DATA4 / f"{flat}-4h-futures.feather"
        if not f4.exists():
            continue
        p = pd.read_feather(f4)
        p["date"] = pd.to_datetime(p["date"], utc=True).dt.tz_localize(None)
        p = p.sort_values("date").drop_duplicates("date").set_index("date")
        if len(p) < 1000:
            continue
        frames.append(features(p))
    if len(frames) < 30:
        print(f"  INSUFFICIENT_DATA: only {len(frames)} symbols built features")
        return 2
    d = pd.concat(frames)
    cands = [c for c in d.columns
             if c not in CONTROLS and not c.startswith("fwd")]
    print(f"  symbols {len(frames)}/40   pooled 4h observations {len(d):,}")
    print(f"  candidates: {len(cands)}   controls: {CONTROLS}\n")

    print("GATE A  does anything clear |IC| >= 0.02 and |NW-t| >= 2.5?")
    print(f"  {'feature':<14}" + "".join(f"{'h='+str(h):>21}" for h in HORIZONS))
    bestA = None
    for f in cands:
        line = f"  {f:<14}"
        for hz in HORIZONS:
            ic, t, _n, _l = ic_and_t(d[f], d[f"fwd_{hz}"])
            line += f"{ic:>12.4f}/t{t:>6.2f}"
            if np.isfinite(t) and (bestA is None or abs(t) > bestA[1]):
                bestA = (f, t, ic, hz)
        print(line)
    if bestA is None:
        print("  no testable statistic")
        return 3
    gA = abs(bestA[2]) >= IC_PASS and abs(bestA[1]) >= T_PASS
    print(f"\n  best univariate: {bestA[0]} @ {bestA[3]}h  IC={bestA[2]:+.4f}  "
          f"NW-t={bestA[1]:+.2f}")
    print(f"  GATE A {'PASS' if gA else 'FAIL'}")

    print("\nGATE B  THE DECISIVE ONE - incremental over [mom_4, dVol_4]")
    print(f"  {'feature':<14}" + "".join(f"{'h='+str(h):>25}" for h in HORIZONS))
    print(f"  {'':<14}" + "".join(f"{'inc t / partial r / cond':>25}" for h in HORIZONS))
    bestB, degenerate = None, []
    for f in cands:
        line = f"  {f:<14}"
        for hz in HORIZONS:
            t, r, _n, cond = incremental(d[f"fwd_{hz}"], [d["mom_4"], d["dVol_4"], d[f]])
            if not np.isfinite(t):
                line += f"{'DEGENERATE':>25}"
                degenerate.append(f"{f}@{hz}h (cond={cond:.1e})")
            elif abs(t) > MAX_SANE_T:
                line += f"{'ARTEFACT':>25}"
                degenerate.append(f"{f}@{hz}h (t={t:.1e})")
            else:
                line += f"{t:>11.2f}/ {r:>8.4f}/ {cond:>6.1e}"
                if bestB is None or abs(t) > bestB[1]:
                    bestB = (f, t, r, hz, cond)
        print(line)
    if degenerate:
        print(f"\n  REFUSED as degenerate or artefactual ({len(degenerate)} cells): "
              f"{', '.join(degenerate[:6])}"
              f"{' ...' if len(degenerate) > 6 else ''}")
        print("  These are near-singular designs or numerically diverging t values. A gate")
        print("  that ACCEPTS the largest number regardless of whether it is real is not a gate.")
    if bestB is None:
        print("  no usable incremental statistic")
        return 3
    gB = abs(bestB[1]) >= T_PASS and abs(bestB[2]) >= PC_PASS
    print(f"\n  best incremental: {bestB[0]} @ {bestB[3]}h  inc NW-t={bestB[1]:+.2f}  "
          f"partial r={bestB[2]:+.4f}  cond={bestB[4]:.1e}")
    print(f"  GATE B {'PASS' if gB else 'FAIL'} (needs inc |t| >= {T_PASS} and "
          f"|partial r| >= {PC_PASS})")


    print("\nVERDICT")
    if gB:
        print(f"  {bestB[0]} carries information the two controls do not. That is the")
        print("  first candidate in this project to pass an INCREMENTAL test.")
        print("  NEXT: build a Freqtrade strategy and run the full chain - backtest ->")
        print("  realistic cost -> lookahead-analysis -> recursive-analysis -> OOS ->")
        print("  stress -> correlation (daily r < 0.30 vs BOTH books) -> holdout.")
        print("  Gate A/B is a feature-layer test and is NOT a backtest result.")
    elif bestA[2] is not None and abs(bestA[2]) < 0.08:
        print("  Gate B did not pass and the best UNIVARIATE effect is small")
        print(f"  (|IC| = {abs(bestA[2]):.4f}, well under the ~0.08 this test detects")
        print("  reliably). Per PREREG Gate C that is ** INCONCLUSIVE, not a negative:")
        print("  a 10-38 %-power test not firing says nothing about existence.")
        print("  INCONCLUSIVE.")
    else:
        print("  Gate A did not pass AND the univariate effect is large, so this IS a")
        print("  negative: kline volume and volatility carry nothing the two existing")
        print("  trend books do not already have. Tier 2 items D and F CLOSE on a")
        print("  measurement, and the whole 4h price/volume/volatility feature space is")
        print("  exhausted for this universe.")
    d.to_parquet(ROOT / "user_data" / "perp_short_out" / "volflow_features.parquet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
