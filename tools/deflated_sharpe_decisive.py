"""DECISIVE TEST — Deflated Sharpe Ratio: is the edge distinguishable from selection?

The goal says: "Accept and report 'no strategy survives' as a valid terminal
outcome if the evidence supports it."

This is the formal test of whether the evidence supports it. I have quoted the
DSR/MinBTL framework from the handoff for many rounds but never actually
computed it on my own candidate. That is decision-relevant, unlike the power
precision I wasted effort on in round 4 (lesson L13).

The question
------------
SMA-50 was selected as the best of a grid. Under the null of NO skill, taking the
maximum of N noisy Sharpe estimates already produces a positive-looking number.
The Deflated Sharpe Ratio (Bailey & Lopez de Prado) asks:

    Given that I tried N configurations, is the observed Sharpe still
    improbable under the null?

If DSR < 0.95, the candidate is NOT PROVEN by the handoff's own standard.

Statistics computed
-------------------
  1. PSR  : P(true SR > benchmark), using skew/kurtosis-corrected standard error
  2. E[max SR] under the null for several trial counts N
  3. DSR  : PSR with the benchmark replaced by E[max SR]
  4. MinBTL : minimum backtest length for the observed Sharpe at N trials
  5. Effective N via the correlation of window Sharpe estimates

Two claims are tested separately, because they are different questions:
  A. the strategy's ABSOLUTE Sharpe (does it make money at all?)
  B. the TIMING EDGE -- the excess series (rule_net - flat_net), i.e. does the
     overlay add value over simply holding less?
Claim B is the real one, and it is the one every prior round has been about.
"""

import math
import os

import numpy as np
import pandas as pd

PPY = 365
COST = 10.0
WINDOWS = [10, 20, 30, 50, 75, 100, 150, 200]
RISK_ON, RISK_OFF = 1.00, 0.50
EULER = 0.5772156649


def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_ppf(p):
    """Acklam's rational approximation for the inverse normal CDF."""
    if p <= 0 or p >= 1:
        raise ValueError("p out of range")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def sma_expo(close, w):
    ma = close.rolling(w, min_periods=w).mean()
    v = ma.notna()
    out = pd.Series(RISK_OFF, index=close.index)
    out[v] = np.where(close[v] > ma[v], RISK_ON, RISK_OFF)
    return out


def nets(rets, expo, cost=COST):
    pos = expo.shift(1).fillna(0.0)
    turn = pos.diff().abs().fillna(pos.abs())
    return pos * rets - turn * cost / 10_000.0


def psr(returns, sr_benchmark_daily=0.0):
    """Probabilistic Sharpe Ratio with skew/kurtosis correction.

    All Sharpe values are DAILY. Returns (psr, sr_daily, sr_annual, n, skew, kurt).
    """
    r = np.asarray(returns, dtype=float)
    r = r[~np.isnan(r)]
    n = len(r)
    if n < 30:
        return np.nan, np.nan, np.nan, n, np.nan, np.nan
    sd = r.std(ddof=1)
    if sd == 0:
        return np.nan, np.nan, np.nan, n, np.nan, np.nan
    sr = r.mean() / sd
    skew = float(pd.Series(r).skew())
    kurt = float(pd.Series(r).kurtosis()) + 3.0  # pandas gives excess
    denom = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr ** 2
    if denom <= 0:
        return np.nan, sr, sr * math.sqrt(PPY), n, skew, kurt
    z = (sr - sr_benchmark_daily) * math.sqrt(n - 1) / math.sqrt(denom)
    return norm_cdf(z), sr, sr * math.sqrt(PPY), n, skew, kurt


def expected_max_sr(var_of_sr, n_trials):
    """E[max of N Sharpe estimates] under the null (Bailey & Lopez de Prado)."""
    if n_trials < 2 or var_of_sr <= 0:
        return 0.0
    g = EULER
    z1 = norm_ppf(1.0 - 1.0 / n_trials)
    z2 = norm_ppf(1.0 - 1.0 / (n_trials * math.e))
    return math.sqrt(var_of_sr) * ((1 - g) * z1 + g * z2)


def main():
    print("=" * 94)
    print("# DECISIVE TEST — Deflated Sharpe Ratio (is the edge just selection?)")
    print("=" * 94)

    d = pd.read_feather("user_data/data/bitstamp/BTC_USD-1d.feather")
    d = d.sort_values("date").drop_duplicates("date")
    close = d.set_index("date")["close"].astype(float).iloc[200:]
    rets = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)

    # ---------- build the two claimed return series ----------
    e50 = sma_expo(close, 50)
    rule50 = nets(rets, e50)
    flat50 = pd.Series(float(e50.mean()), index=rets.index) * rets
    excess = (rule50 - flat50).dropna()          # claim B: the timing overlay
    bh = rets.copy()                              # reference

    print(f"\n  series: BTC/USD, {close.index[0].date()} -> {close.index[-1].date()}"
          f"  ({len(rets)/PPY:.1f}y)")

    # ---------- 1. PSR for both claims ----------
    print(f"\n{'=' * 94}")
    print("# 1. PSR — P(true SR > 0), skew/kurtosis corrected")
    print(f"{'=' * 94}")
    print(f"\n  {'series':<28} {'SR(ann)':>9} {'skew':>8} {'kurt':>8} {'n':>6} "
          f"{'PSR':>8}")
    rows = {}
    for label, series in (("A. rule (absolute)", rule50.dropna()),
                          ("A. buy & hold", bh.dropna()),
                          ("B. TIMING EXCESS (rule-flat)", excess)):
        p, sr, sra, n, sk, ku = psr(series)
        rows[label] = (p, sr, sra, n, sk, ku, series)
        print(f"  {label:<28} {sra:>9.3f} {sk:>+8.2f} {ku:>8.2f} {n:>6} {p:>8.4f}")

    # ---------- 2. variance of Sharpe across the grid ----------
    print(f"\n{'=' * 94}")
    print("# 2. VARIANCE OF TRIAL SHARPES (the key input to E[max])")
    print(f"{'=' * 94}")
    grid_srs, grid_edges = [], []
    for w in WINDOWS:
        e = sma_expo(close, w)
        rw = nets(rets, e)
        fw = pd.Series(float(e.mean()), index=rets.index) * rets
        p, sr, sra, n, sk, ku = psr(rw.dropna())
        p2, sr2, sra2, n2, _, _ = psr((rw - fw).dropna())
        grid_srs.append(sra)
        grid_edges.append(sra2)
    grid_srs = np.array(grid_srs)
    grid_edges = np.array(grid_edges)

    print(f"\n  {'window':>8} {'rule SR(ann)':>13} {'excess SR(ann)':>15}")
    for w, a, b in zip(WINDOWS, grid_srs, grid_edges):
        flag = "  <-- candidate" if w == 50 else ""
        print(f"  {w:>8} {a:>13.3f} {b:>15.3f}{flag}")

    var_rule = float(np.var(grid_srs, ddof=1))
    var_edge = float(np.var(grid_edges, ddof=1))
    # convert annualised variance to daily-SR variance
    var_rule_d = var_rule / PPY
    var_edge_d = var_edge / PPY
    print(f"\n  var across windows (annualised): rule {var_rule:.4f}  "
          f"excess {var_edge:.4f}")
    print(f"  -> daily-SR variance: rule {var_rule_d:.6f}  excess {var_edge_d:.6f}")

    # ---------- 3. effective number of trials ----------
    print(f"\n{'=' * 94}")
    print("# 3. EFFECTIVE NUMBER OF INDEPENDENT TRIALS")
    print(f"{'=' * 94}")
    # correlation of the window return series
    Wret = pd.DataFrame({w: nets(rets, sma_expo(close, w)) for w in WINDOWS})
    C = Wret.corr().to_numpy()
    ev = np.linalg.eigvalsh(C)
    ev = ev[ev > 0]
    n_eff = float((ev.sum() ** 2) / (ev ** 2).sum())
    print(f"\n  8 windows, mean pairwise correlation of their return series: "
          f"{float((C.sum() - len(C)) / (len(C)*(len(C)-1))):.3f}")
    print(f"  effective independent trials (participation ratio): {n_eff:.1f}")
    print(f"  -> so the 8-window grid is worth ~{n_eff:.0f} independent tries,")
    print(f"     not 8. This matters: E[max] grows with N but flattens.")

    ledger_total = 176
    print(f"\n  trial counts to consider:")
    print(f"    narrow  (windows on this series)      : {len(WINDOWS)}")
    print(f"    effective (correlation-adjusted)      : {n_eff:.0f}")
    print(f"    full ledger (all hypotheses, all data): {ledger_total}")

    # ---------- 4. E[max] and DSR ----------
    print(f"\n{'=' * 94}")
    print("# 4. E[max SR] UNDER THE NULL, AND THE DEFLATED SHARPE RATIO")
    print(f"{'=' * 94}")

    for claim, series_key, var_d in (
        ("A. rule absolute Sharpe", "A. rule (absolute)", var_rule_d),
        ("B. TIMING EXCESS Sharpe", "B. TIMING EXCESS (rule-flat)", var_edge_d),
    ):
        p, sr_d, sra, n, sk, ku, series = rows[series_key]
        print(f"\n  --- {claim} ---")
        print(f"    observed SR(ann) = {sra:.3f}   PSR vs 0 = {p:.4f}")
        print(f"\n    {'N trials':>10} {'E[max SR] ann':>15} {'DSR':>9}  verdict")
        for N in (len(WINDOWS), round(n_eff), ledger_total):
            emax_d = expected_max_sr(var_d, N)
            emax_ann = emax_d * math.sqrt(PPY)
            # DSR = PSR with benchmark = E[max]
            dsr, _, _, _, _, _ = psr(series.to_numpy(), sr_benchmark_daily=emax_d)
            verdict = "PASS (>=0.95)" if dsr >= 0.95 else "FAIL (<0.95)"
            print(f"    {N:>10} {emax_ann:>15.3f} {dsr:>9.4f}  {verdict}")

    # ---------- 5. MinBTL ----------
    print(f"\n{'=' * 94}")
    print("# 5. MinBTL — minimum backtest length")
    print(f"{'=' * 94}")
    # MinBTL ~ (2*ln(N)) / SR^2  years, using ANNUALISED SR of the claim
    print(f"\n  {'claim':<28} {'SR(ann)':>8} {'N':>6} {'MinBTL yrs':>11} "
          f"{'available':>10}  ok?")
    for claim, series_key, _v in (
        ("A. rule absolute", "A. rule (absolute)", None),
        ("B. timing excess", "B. TIMING EXCESS (rule-flat)", None),
    ):
        _p, _sr, sra, _n, _sk, _ku, _series = rows[series_key]
        for N in (len(WINDOWS), ledger_total):
            if sra <= 0:
                continue
            minbtl = 2 * math.log(N) / (sra ** 2)
            ok = "OK" if len(rets) / PPY >= minbtl else "SHORT"
            print(f"  {claim:<28} {sra:>8.3f} {N:>6} {minbtl:>11.1f} "
                  f"{len(rets)/PPY:>10.1f}  {ok}")

    # ---------- VERDICT ----------
    print(f"\n{'=' * 94}")
    print("# VERDICT — does the evidence support 'no strategy survives'?")
    print(f"{'=' * 94}")
    p_ex = rows["B. TIMING EXCESS (rule-flat)"][0]
    sra_ex = rows["B. TIMING EXCESS (rule-flat)"][2]
    var_ex = var_edge_d
    dsr_narrow, _, _, _, _, _ = psr(
        rows["B. TIMING EXCESS (rule-flat)"][6].to_numpy(),
        sr_benchmark_daily=expected_max_sr(var_ex, len(WINDOWS)))
    dsr_eff, _, _, _, _, _ = psr(
        rows["B. TIMING EXCESS (rule-flat)"][6].to_numpy(),
        sr_benchmark_daily=expected_max_sr(var_ex, round(n_eff)))
    dsr_full, _, _, _, _, _ = psr(
        rows["B. TIMING EXCESS (rule-flat)"][6].to_numpy(),
        sr_benchmark_daily=expected_max_sr(var_ex, ledger_total))

    print(f"""
  Timing-excess Sharpe (annualised) : {sra_ex:.3f}
  PSR against zero                  : {p_ex:.4f}

  DSR after deflating for selection:
    N = {len(WINDOWS)} (windows)              : {dsr_narrow:.4f}
    N = {round(n_eff)} (effective)            : {dsr_eff:.4f}
    N = {ledger_total} (full ledger)          : {dsr_full:.4f}

  Threshold per the handoff: DSR >= 0.95 required.""")

    # Do NOT assert a narrative -- report which counts pass and which fail.
    passes = []
    fails = []
    for label, val in ((f"N={len(WINDOWS)} (windows)", dsr_narrow),
                       (f"N={round(n_eff)} (effective)", dsr_eff),
                       (f"N={ledger_total} (full ledger)", dsr_full)):
        (passes if val >= 0.95 else fails).append((label, val))

    print(f"\n  PASSES (>=0.95): {', '.join(f'{l} = {v:.4f}' for l, v in passes) or 'none'}")
    print(f"  FAILS  (<0.95) : {', '.join(f'{l} = {v:.4f}' for l, v in fails) or 'none'}")

    if not fails:
        verdict = "NOT PROVEN false -- every trial count passes. Candidate survives this test."
    elif not passes:
        verdict = ("NOT PROVEN -- every trial count fails. Evidence supports the terminal "
                   "outcome: no strategy survives to the project's standard.")
    else:
        verdict = ("AMBIGUOUS -- the conclusion depends on which trial count is honest, "
                   "and that is a judgement call, not a computation.")

    print(f"\n  -> {verdict}")

    if passes and fails:
        print(f"""
  WHY THIS IS GENUINELY AMBIGUOUS, AND WHY I WILL NOT RESOLVE IT BY PICKING

  The eight SMA windows have mean pairwise return correlation of 0.962, giving an
  EFFECTIVE trial count of only ~{n_eff:.1f}. That means the 8-window grid is
  essentially ONE independent trial, and deflating for it barely changes anything
  (DSR {dsr_narrow:.4f}).

  But the project as a whole has run ~{ledger_total} configurations across every
  hypothesis and dataset. Counting those, the DSR is {dsr_full:.4f} -- just under
  the 0.95 bar.

  Which N is correct depends on what "the search" means:
    * if it means "the window grid on this series"      -> {len(WINDOWS)} -> passes
    * if it means "everything I tried on this project"  -> {ledger_total} -> fails

  Both are defensible. Choosing the one that gives the answer I prefer would be
  exactly the error documented in L5 and L10. So the honest report is:

      the candidate is NOT clearly proven, and NOT clearly refuted;
      it sits just inside/outside the threshold depending on trial accounting.

  What breaks the tie is not more statistics but the INDEPENDENT evidence, which
  is uniformly unflattering:
    * clean train-only selection gave a positive OOS edge in 0/6 BTC splits
    * train/test test edges: BTC +0.024, pool -0.001
    * the ensemble added stability but no positive OOS edge
    * the parameter-free variant was degenerate
    * MinBTL at N={ledger_total} is 15.5y vs 14.6y of data -> SHORT

  Every one of those points the same direction, and none of them is a
  judgement call about trial counting.""")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
