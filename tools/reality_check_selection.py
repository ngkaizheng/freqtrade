"""REALITY CHECK — is the selected window's edge surprising GIVEN the selection?

The Deflated Sharpe Ratio is ambiguous here: DSR = 0.9887 counting only the
8-window grid, but 0.9435 counting the full ~176-trial project ledger. Which N is
honest is a judgement call, and per L5/L10 I will not resolve it by picking.

So resolve it computationally instead, with a test that needs no N:

    White's Reality Check / max-statistic null.

Procedure
---------
Destroy the TIMING relationship while preserving everything else, then re-run the
entire selection procedure and see how good the best window looks.

Null construction: circularly shift the RETURNS relative to the SIGNAL.
  * the signal keeps its exact structure (real price vs real SMA)
  * the returns keep their exact distribution AND autocorrelation (cyclic shift)
  * the alignment between them is destroyed
  * the selection over all 8 windows is re-run each time, so the max-statistic
    null incorporates the search itself

Statistic: max over windows of the excess Sharpe (rule - matched flat).
Compare the observed max (window 50, +0.818) to this null distribution.

This is the honest way to price the selection: if the shift-null produces maxima
as large as 0.818 often, the observed edge is explained by searching. If rarely,
the edge survives the search.

Assumption disclosed: circular shifting assumes returns are stationary enough
that a cyclic permutation is exchangeable. That is an approximation, not exact.
"""

import math

import numpy as np
import pandas as pd

PPY = 365
COST = 10.0
WINDOWS = [10, 20, 30, 50, 75, 100, 150, 200]
RISK_ON, RISK_OFF = 1.00, 0.50
N_SHIFTS = 500


def sharpe_daily(r):
    sd = r.std()
    return float(r.mean() / sd) if sd > 0 else 0.0


def sma_signal(pos_raw, w):
    """0/1 risk-on signal from price vs SMA (no lag applied)."""
    return (pos_raw > 0).astype(float)


def build(close):
    ma_cache, sig_cache = {}, {}
    for w in WINDOWS:
        ma = close.rolling(w, min_periods=w).mean()
        v = ma.notna()
        s = pd.Series(0.0, index=close.index)
        s[v] = np.where(close[v] > ma[v], RISK_ON, RISK_OFF)
        sig_cache[w] = s.to_numpy()
    return sig_cache


def excess_sharpe_for(sig, rets_shifted, cost=COST):
    """Excess Sharpe of the rule over a matched flat control, given the signal
    and a (possibly shifted) return series."""
    n = len(sig)
    pos = np.empty(n)
    pos[0] = 0.0
    pos[1:] = sig[:-1]                      # single lag point
    turn = np.abs(np.diff(pos, prepend=0.0))
    rule_net = pos * rets_shifted - turn * cost / 10_000.0
    flat_net = float(np.mean(sig)) * rets_shifted
    return sharpe_daily(rule_net) - sharpe_daily(flat_net)


def main():
    print("=" * 94)
    print("# REALITY CHECK — is the selected window's edge surprising GIVEN the search?")
    print("=" * 94)

    d = pd.read_feather("user_data/data/bitstamp/BTC_USD-1d.feather")
    d = d.sort_values("date").drop_duplicates("date")
    close = d.set_index("date")["close"].astype(float).iloc[200:]
    rets = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    r = rets.to_numpy()
    n = len(r)

    sig = build(close)

    # ---------- observed ----------
    obs = {w: excess_sharpe_for(sig[w], r) for w in WINDOWS}
    obs_max_w = max(obs, key=lambda w: obs[w])
    obs_max = obs[obs_max_w]
    print(f"\n  observed excess Sharpe (daily) by window:")
    for w in WINDOWS:
        flag = "  <-- best" if w == obs_max_w else ""
        print(f"    SMA-{w:<4} {obs[w]:>+.5f}{flag}")
    print(f"\n  observed MAX across the grid: {obs_max:+.5f} (SMA-{obs_max_w})")

    # ---------- the shift null ----------
    print(f"\n{'=' * 94}")
    print(f"# NULL DISTRIBUTION — {N_SHIFTS} circular shifts of returns vs signal")
    print(f"{'=' * 94}")
    rng = np.random.default_rng(2026)
    null_max = np.empty(N_SHIFTS)
    for i in range(N_SHIFTS):
        k = int(rng.integers(1, n))
        rs = np.roll(r, k)
        null_max[i] = max(excess_sharpe_for(sig[w], rs) for w in WINDOWS)

    p = float((null_max >= obs_max).mean())
    print(f"\n  null max: mean {null_max.mean():+.5f}  "
          f"sd {null_max.std():.5f}")
    print(f"  null percentiles:")
    for q in (50, 75, 90, 95, 99):
        print(f"    {q:>3}%  {np.percentile(null_max, q):>+.5f}")
    print(f"\n  observed max : {obs_max:+.5f}")
    print(f"  p-value      : {p:.4f}   ({int((null_max >= obs_max).sum())}/{N_SHIFTS} shifts)")

    # ---------- Also: the SMA-50 specifically, not just the max ----------
    print(f"\n{'=' * 94}")
    print("# SECONDARY — SMA-50 specifically (not the post-hoc max)")
    print(f"{'=' * 94}")
    null_50 = np.empty(N_SHIFTS)
    for i in range(N_SHIFTS):
        k = int(rng.integers(1, n))
        null_50[i] = excess_sharpe_for(sig[50], np.roll(r, k))
    p50 = float((null_50 >= obs[50]).mean())
    print(f"\n  observed SMA-50 excess Sharpe : {obs[50]:+.5f}")
    print(f"  null mean / p95              : {null_50.mean():+.5f} / "
          f"{np.percentile(null_50, 95):+.5f}")
    print(f"  p-value                      : {p50:.4f}")

    # ---------- Verdict ----------
    print(f"\n{'=' * 94}")
    print("# VERDICT")
    print(f"{'=' * 94}")
    print(f"""
  The max-statistic null already contains the selection: each of the {N_SHIFTS}
  null draws re-ran the full 8-window search and took the best. So a small
  p-value means the observed best is better than searching alone typically
  produces from data with no timing relationship at all.

  observed max {obs_max:+.5f}   vs   null p95 {np.percentile(null_max, 95):+.5f}
  p = {p:.4f}""")

    if p < 0.05:
        print(f"""
  => The selected window's edge is NOT explained by the search alone.
     This test does not confirm the edge, but it does not refute it either, and
     it prices the selection concern directly rather than by choosing an N.""")
    else:
        print(f"""
  => The selected window's edge IS consistent with what searching alone produces
     from data with no timing relationship. The search explains the result.""")

    print(f"""
  CAVEATS, stated rather than buried:
    * circular shifting assumes approximate exchangeability of returns; if the
      true return process is non-stationary this over- or under-states the null
    * the null keeps the SIGNAL fixed and shifts returns; an alternative null
      shifts the signal instead, which is not identical
    * this is one dataset (BTC/Bitstamp, 14.6y); it says nothing about the pool

  Next: repeat the identical procedure on the 20-major pool as a replication.""")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
