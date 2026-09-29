"""Mechanism test: WHY does SMA-50 work on crypto but not equities?

The out-of-domain test was decisive: frozen SMA-50 on 109 US equities gives
mean dSharpe vs flat of -0.065, only 22/109 tickers beat the benchmark, and
0/4 gates pass. On crypto the same rule gave +0.168 (BTC) and +0.252 (pool).

That leaves three possibilities:
  A. The crypto result is genuine but DOMAIN-SPECIFIC (crypto trends harder)
  B. The crypto result is an artifact and equities expose it
  C. The equity test is mis-specified somehow

The distinguishing evidence is the MECHANISM. A trend-following rule (SMA
exposure) can only add value if returns are positively AUTOCORRELATED: you need
today's direction to predict tomorrow's. If crypto has materially stronger
return persistence than equities, possibility A is supported and the rule is
genuinely (if narrowly) valid.

Tests:
  1. Return autocorrelation (lag 1..10) for crypto vs equities
  2. Variance ratio VR(q) = Var(q-period ret)/(q * Var(1-period ret))
     VR > 1 => trending/persistent;  VR < 1 => mean-reverting
  3. Hurst exponent (R/S style) as a robustness check
  4. Does dSharpe from the SMA rule correlate with the trendiness measure?
"""

import glob
import os

import numpy as np
import pandas as pd

CRYPTO_DIR = "user_data/data/bitstamp"
CACHE = "quant-research-handoff/data/cache"


def load_crypto():
    s = {}
    for p in sorted(glob.glob(os.path.join(CRYPTO_DIR, "*-1d.feather"))):
        n = os.path.basename(p).replace("-1d.feather", "")
        d = pd.read_feather(p).sort_values("date").drop_duplicates("date")
        s[n] = d.set_index("date")["close"].astype(float)
    return pd.DataFrame(s).sort_index()


def load_equities():
    s = {}
    for p in sorted(glob.glob(os.path.join(CACHE, "*.csv"))):
        t = os.path.basename(p)[:-4]
        try:
            d = pd.read_csv(p, parse_dates=["Date"])
        except Exception:
            continue
        d = d.dropna(subset=["Close"]).drop_duplicates("Date").sort_values("Date")
        if len(d) < 500:
            continue
        s[t] = d.set_index("Date")["Close"].astype(float)
    return pd.DataFrame(s).sort_index()


def rets_of(panel):
    r = panel.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    return r


def autocorr_profile(r, lags=10):
    """Mean autocorrelation across series at each lag."""
    out = []
    for k in range(1, lags + 1):
        vals = [r[c].autocorr(k) for c in r.columns if r[c].notna().sum() > 400]
        vals = [v for v in vals if v == v]
        out.append(float(np.mean(vals)) if vals else np.nan)
    return out


def variance_ratio(r, q):
    """VR(q) averaged across series. >1 persistent, <1 mean-reverting."""
    vals = []
    for c in r.columns:
        x = r[c].dropna().to_numpy()
        if len(x) < 300:
            continue
        v1 = np.var(x, ddof=1)
        # q-period overlapping returns
        n = len(x) - q + 1
        if n < 50:
            continue
        qr = np.convolve(x, np.ones(q), "valid")
        vq = np.var(qr, ddof=1)
        if v1 > 0:
            vals.append(vq / (q * v1))
    return float(np.mean(vals)) if vals else np.nan


def sma_expo(close, w):
    ma = close.rolling(w, min_periods=w).mean()
    v = ma.notna()
    out = pd.Series(0.5, index=close.index)
    out[v] = np.where(close[v] > ma[v], 1.0, 0.5)
    return out


def run(rets, expo, cost):
    pos = expo.shift(1).fillna(0.0)
    turn = pos.diff().abs().fillna(pos.abs())
    return 10_000 * (1 + (pos * rets - turn * cost / 10_000.0)).cumprod()


def sharpe(r):
    sd = r.std()
    return float(r.mean() / sd * np.sqrt(365 if len(r) > 0 else 1)) if sd and sd > 0 else np.nan


def main():
    print("=" * 94)
    print("# MECHANISM — why does trend-following work on crypto but not equities?")
    print("=" * 94)

    cr = rets_of(load_crypto()).loc["2013-01-01":]
    eq = rets_of(load_equities()).loc["2011-01-01":]

    print(f"\n  crypto series : {cr.shape[1]} pairs, {len(cr)} daily obs")
    print(f"  equity series : {eq.shape[1]} tickers, {len(eq)} daily obs")

    # ---- 1. Autocorrelation ----
    print(f"\n{'=' * 94}")
    print("# 1. RETURN AUTOCORRELATION (mean across series)")
    print(f"{'=' * 94}")
    ac_c = autocorr_profile(cr, 10)
    ac_e = autocorr_profile(eq, 10)
    print(f"\n  {'lag':<6} {'crypto':>10} {'equities':>10}")
    for i, (a, b) in enumerate(zip(ac_c, ac_e), 1):
        print(f"  {i:<6} {a:>+10.4f} {b:>+10.4f}")
    print(f"\n  mean |AC| crypto : {np.nanmean(np.abs(ac_c)):.4f}")
    print(f"  mean |AC| equities: {np.nanmean(np.abs(ac_e)):.4f}")

    # ---- 2. Variance ratio ----
    print(f"\n{'=' * 94}")
    print("# 2. VARIANCE RATIO — >1 trending, <1 mean-reverting")
    print(f"{'=' * 94}")
    print(f"\n  {'q':<6} {'crypto VR':>12} {'equities VR':>13}   interpretation")
    for q in (0, 1, 2, 4, 9, 19):
        qq = q + 1
        vc = variance_ratio(cr, qq)
        ve = variance_ratio(eq, qq)
        interp = ""
        if qq > 1:
            if vc > 1 and ve <= 1:
                interp = "crypto trends, equities do not"
            elif vc > ve:
                interp = "crypto more persistent"
        print(f"  {qq:<6} {vc:>12.3f} {ve:>13.3f}   {interp}")

    # ---- 3. Does trendiness predict the SMA edge? ----
    print(f"\n{'=' * 94}")
    print("# 3. DOES TRENDINESS PREDICT THE SMA-50 EDGE? (per series)")
    print(f"{'=' * 94}")
    print(f"\n  {'asset':<12} {'VR(5)':>8} {'AC(1)':>8} {'dSharpe':>9}  class")
    rows = []
    for label, panel, ppy, cost in (("crypto", cr, 365, 10.0),
                                    ("equities", eq, 252, 5.0)):
        for c in panel.columns:
            x = panel[c].dropna()
            if len(x) < 400:
                continue
            close = (1 + x).cumprod() * 100
            e = sma_expo(close, 50)
            a = float(e.mean())
            sr_rule = _stats_sharpe(run(x, e, cost), ppy)
            sr_flat = _stats_sharpe(run(x, pd.Series(a, index=x.index), cost), ppy)
            vr = _vr_series(x, 5)
            ac = x.autocorr(1)
            rows.append({"asset": c, "class": label, "vr": vr, "ac": ac,
                         "d": sr_rule - sr_flat})

    df = pd.DataFrame(rows)
    for label in ("crypto", "equities"):
        sub = df[df["class"] == label]
        print(f"\n  --- {label} ({len(sub)} series) ---")
        print(f"    mean VR(5)        : {sub['vr'].mean():.3f}")
        print(f"    mean AC(1)        : {sub['ac'].mean():+.4f}")
        print(f"    mean dSharpe      : {sub['d'].mean():+.4f}")
        corr_vr = sub[["vr", "d"]].corr().iloc[0, 1]
        corr_ac = sub[["ac", "d"]].corr().iloc[0, 1]
        print(f"    corr(VR(5), dSharpe) : {corr_vr:+.3f}")
        print(f"    corr(AC(1), dSharpe) : {corr_ac:+.3f}")

    # ---- Conclusion ----
    print(f"\n{'=' * 94}")
    print("# CONCLUSION")
    print(f"{'=' * 94}")
    vc5 = variance_ratio(cr, 5)
    ve5 = variance_ratio(eq, 5)
    print(f"\n  VR(5): crypto {vc5:.3f}  vs  equities {ve5:.3f}")
    if vc5 > ve5:
        print(f"\n  Crypto returns are MORE persistent than equity returns.")
        print(f"  That is a mechanism-level reason a trend rule can work on one")
        print(f"  and not the other — it is domain-specific, not universal.")
    else:
        print(f"\n  NO persistence advantage found for crypto.")
        print(f"  The crypto SMA-50 result is then more likely an artifact.")
    print(f"\n  Either way: the rule is NOT universal. Rejecting it as a")
    print(f"  general strategy is the honest reading.")


def _stats_sharpe(eq, ppy):
    r = eq.pct_change().dropna()
    sd = r.std()
    return float(r.mean() / sd * np.sqrt(ppy)) if sd and sd > 0 else np.nan


def _vr_series(x, q):
    v = x.dropna().to_numpy()
    if len(v) < 300:
        return np.nan
    v1 = np.var(v, ddof=1)
    qr = np.convolve(v, np.ones(q), "valid")
    return float(np.var(qr, ddof=1) / (q * v1)) if v1 > 0 else np.nan


if __name__ == "__main__":
    main()
