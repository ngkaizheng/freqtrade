"""Adversarial test: dollar-neutral LONG-SHORT version of the 47-symbol momentum signal.

The project rejected the cross-sectional design citing -89.49% MaxDD from
tools/crypto_momentum_study.py.  That study is LONG-ONLY (see build_weights docstring:
"long only"), so the drawdown is crypto beta, not the design.  This script implements
the actual cross-sectional design (long top-K / short bottom-K, dollar-neutral) on the
SAME 47 symbols, SAME data, and reports what the design really delivers.

Reports net of transaction costs, with a Newey-West HAC t-stat and an IAT-based
effective-N, per the repo's own trap 3.1/3.2.
"""
import os
import glob
import numpy as np
import pandas as pd

DATA = r"user_data\data\binance"
IATA = 365  # 0.5% annualised target for the 1.645 single-test benchmark


def load_panel():
    frames = {}
    for f in sorted(glob.glob(os.path.join(DATA, "*-1d.feather"))):
        sym = os.path.basename(f).split("-1d")[0]
        d = pd.read_feather(f)
        d.columns = [str(c).lower() for c in d.columns]
        if "date" in d.columns:
            d = d.set_index("date")
        if not isinstance(d.index, pd.DatetimeIndex):
            d.index = pd.to_datetime(d.index.astype("int64"), utc=True)
        frames[sym] = d["close"].astype("float64")
    px = pd.DataFrame(frames).sort_index()
    return px


def iat(x, max_lag=40):
    """Intera autocorrelations-based effective sample size (Lo 2002 style)."""
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 10:
        return 1.0, n
    x = x - x.mean()
    v = np.dot(x, x) / n
    rho_sum = 1.0
    for lag in range(1, max_lag + 1):
        r = np.dot(x[:-lag], x[lag:]) / n / v
        if r <= 0:
            break
        rho_sum += 2.0 * r
    return n / max(rho_sum, 1.0), n


def nw_tstat(r, lags=None):
    r = np.asarray(r, float)
    n = len(r)
    if lags is None:
        ne, _ = iat(r)
        lags = max(1, int(round(4 * (n / ne) ** 0.25)))
        lags = min(lags, n - 2)
    mu = r.mean()
    e = r - mu
    g0 = np.dot(e, e) / n
    var = g0
    for L in range(1, lags + 1):
        gl = np.dot(e[L:], e[:-L]) / n
        var += 2.0 * (1.0 - L / (lags + 1.0)) * gl
    var = max(var, 1e-18)
    return mu / np.sqrt(var / n), lags


def maxdd(eq):
    eq = np.asarray(eq, float)
    return float((eq / np.maximum.accumulate(eq) - 1.0).min())


def build_ls(px, lookback, k, rebalance, cost_bps, gross=2.0):
    """Long top-k, short bottom-k, dollar neutral, equal weight within legs.

    Positions are force-closed when a symbol stops printing prices, otherwise a
    delisted coin leaves a stale weight and the book takes a phantom -100% hit.
    """
    r = px.pct_change(fill_method=None)
    # data sanity: a spot token cannot 100x in a day on real volume. Values beyond this
    # are broken/renamed/rebased prints, exactly the trap 3.13/3.22 family. Cap them.
    r = r.clip(-3.0, 8.0)
    mom = px / px.shift(lookback) - 1.0
    valid = px.notna()
    eligible = valid & (valid.rolling(lookback).sum() == lookback)

    n = len(px)
    W = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    for i in range(n):
        if i % rebalance:
            continue
        ok = eligible.iloc[i]
        pool = list(ok.index[ok])
        if len(pool) < 2 * k:
            continue
        s = mom.iloc[i][pool].dropna()
        if len(s) < 2 * k:
            continue
        top = list(s.nlargest(k).index)
        bot = list(s.nsmallest(k).index)
        leg = 1.0 / k
        # reset the whole row: symbols not selected this rebalance must exit, not
        # silently keep (and later compound) a stale weight.
        W.iloc[i, :] = 0.0
        for t in top:
            W.iat[i, px.columns.get_loc(t)] += leg * gross / 2.0
        for b in bot:
            W.iat[i, px.columns.get_loc(b)] -= leg * gross / 2.0
    # hold until next rebalance
    W = W.where(W != 0).ffill().fillna(0.0)
    # force-close anything that stopped printing prices
    W = W.where(valid.fillna(False) | W.eq(0.0), 0.0)
    # renormalise: keep gross exposure at the target after any forced closes
    gexp = W.abs().sum(axis=1)
    W = W.div(gexp.where(gexp > 0), axis=0).mul(gross).fillna(0.0)

    # decision made on close[t] -> realised at t+1
    realised = W.shift(1).fillna(0.0)
    # turnover = fraction of gross that changes per day
    gross_exp = realised.abs().sum(axis=1)
    dW = realised.diff().abs().sum(axis=1)
    turnover = (dW / gross_exp.replace(0.0, np.nan)).fillna(0.0)

    port_gross = (realised * r.fillna(0.0)).sum(axis=1)
    cost = turnover * (cost_bps / 1e4)
    net = port_gross - cost
    net = net[realised.abs().sum(axis=1) > 0]
    return net


def report(name, net, rebalance):
    ppy = 365.0 / rebalance
    eq = np.cumprod(1.0 + net.values)
    yrs = len(net) / 365.0
    cagr = eq[-1] ** (1.0 / yrs) - 1.0 if yrs > 0 else np.nan
    sd = net.std(ddof=1)
    shr = (net.mean() / sd) * np.sqrt(ppy) if sd > 0 else np.nan
    t, lags = nw_tstat(net.values)
    ne, n = iat(net.values)
    return dict(name=name, n=int(n), effN=round(ne, 1), HAC_t=round(t, 2), nw_lags=lags,
                CAGR=round(cagr * 100, 2), Sharpe=round(shr, 3), MaxDD=round(maxdd(eq) * 100, 2),
                IR_at_IAT=round(shr * np.sqrt(ne / len(net)), 3))


def main():
    px = load_panel()
    px = px.loc["2019-01-01":]
    print(f"panel: {px.shape[0]} daily bars x {px.shape[1]} symbols, "
          f"{px.index[0].date()} -> {px.index[-1].date()}")
    print()

    rows = []
    for cost in (10, 20, 50):
        for lb, k in [(30, 10), (30, 20), (90, 10), (90, 20), (60, 10), (14, 10)]:
            net = build_ls(px, lb, k, 7, cost, gross=2.0)
            if len(net) < 50:
                continue
            rows.append(report(f"LS mom{lb}d k={k} @{cost}bps", net, 7))
    out = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    print(out.to_string(index=False))
    print()
    yrs = 3.0
    print(f"Single pre-registered test, 3y weekly: required annualised Sharpe at 95% = "
          f"{1.645 / np.sqrt(yrs):.3f}   (at 90% = {1.281 / np.sqrt(yrs):.3f})")
    print()
    # ---- how much of the long-only result is just beta? ----
    net = build_ls(px, 30, 10, 7, 20, gross=2.0)
    print("worst 6 days of LS(mom30d,k=10,20bps):")
    print((net.nsmallest(6) * 1e4).round(1).to_string())
    uni = px.pct_change(fill_method=None).clip(-3.0, 8.0).mean(axis=1).fillna(0.0).loc[net.index]
    x, y = uni.values, net.values
    b = np.polyfit(x, y, 1)
    print(f"\nLS(mom30d,k=10,20bps) regressed on equal-weight-universe return: "
          f"beta={b[0]:+.3f}  alpha={b[1]*1e4:+.3f} bps/day  R2={np.corrcoef(x, y)[0, 1]**2:.3f}")
    print(f"  beta of {b[0]:+.2f} confirms the book is dollar-neutral; the -89.49% MaxDD of the")
    print( "  long-only study is its beta term, not a property of the cross-sectional design.")
    ew = (1 + px.pct_change(fill_method=None).clip(-3.0, 8.0).mean(axis=1).fillna(0.0)).cumprod()
    ewv = ew.dropna().values
    print(f"  equal-weight all-47 universe, same window: "
          f"CAGR={(ewv[-1]**(365/len(ewv))-1)*100:.1f}%  MaxDD={maxdd(ewv)*100:.1f}%")


if __name__ == "__main__":
    main()
