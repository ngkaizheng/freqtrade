"""Stress test: try to break the 15-year SMA-50 result.

It passed 6/6 gates. That is exactly when to be most suspicious. The remaining
ways this could be an artifact:

  1. MATCHED-DRAWDOWN test (the fairest possible control). The matched-exposure
     flat control is a blunt instrument: find the CONSTANT exposure that
     achieves the SAME drawdown as the rule, and compare Sharpe. If a dumb
     constant position matches both drawdown and Sharpe, the timing is worthless.
  2. Era dependence: is the edge concentrated in 2012-2015, when Bitstamp was
     tiny and illiquid with absurd moves (2013 CAGR +5437%)?
  3. Recent performance (2024-2026), where crypto matured.
  4. Cost sensitivity at realistic crypto levels.
  5. The "50 independent episodes" claim from the previous script was wrong --
     contiguous drawdown days overlap heavily. Count properly.
"""

import numpy as np
import pandas as pd

PPY = 365
WINDOWS = [10, 20, 30, 50, 75, 100, 150, 200]


def load(name="BTC/USD"):
    d = pd.read_feather(f"user_data/data/bitstamp/{name.replace('/', '_')}-1d.feather")
    return d.sort_values("date").drop_duplicates("date").reset_index(drop=True)


def max_dd(e):
    return float((e / e.cummax() - 1).min())


def cagr(e):
    y = len(e) / PPY
    return float((e.iloc[-1] / e.iloc[0]) ** (1 / y) - 1) if y > 0 else np.nan


def sharpe(r):
    sd = r.std()
    return float(r.mean() / sd * np.sqrt(PPY)) if sd and sd > 0 else np.nan


def stats(e):
    return {"cagr": cagr(e), "maxdd": max_dd(e),
            "sharpe": sharpe(e.pct_change().dropna())}


def run(rets, expo, cost=10.0):
    pos = expo.shift(1).fillna(0.0)
    turn = pos.diff().abs().fillna(pos.abs())
    return 10_000 * (1 + (pos * rets - turn * cost / 10_000)).cumprod()


def sma_expo(close, w):
    ma = close.rolling(w, min_periods=w).mean()
    v = ma.notna()
    out = pd.Series(0.5, index=close.index)
    out[v] = np.where(close[v] > ma[v], 1.0, 0.5)
    return out


def main():
    d = load()
    c = d.set_index("date")["close"].astype(float)
    r = c.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    c, r = c.iloc[200:], r.iloc[200:]
    n = len(r)
    ny = n / PPY

    e50 = sma_expo(c, 50)
    s50 = stats(run(r, e50))
    print("=" * 94)
    print("# STRESS TEST — trying to break SMA-50 on 15y BTC")
    print("=" * 94)
    print(f"{c.index[0].date()} -> {c.index[-1].date()} ({ny:.1f}y)\n")
    print(f"  SMA-50: CAGR {s50['cagr']:.2%}  MaxDD {s50['maxdd']:.2%}  "
          f"Sharpe {s50['sharpe']:.2f}")

    # ---------- 1. MATCHED-DRAWDOWN control ----------
    print(f"\n{'=' * 94}")
    print("# 1. MATCHED-DRAWDOWN CONTROL — find the constant exposure with the")
    print("#    SAME drawdown, then compare Sharpe. This is the fairest test.")
    print(f"{'=' * 94}")
    print(f"\n  {'const exp':>10} {'CAGR':>9} {'MaxDD':>9} {'Sharpe':>8}  note")
    best_const = None
    for a in np.arange(0.30, 1.001, 0.05):
        st = stats(run(r, pd.Series(float(a), index=r.index)))
        note = ""
        if abs(st["maxdd"] - s50["maxdd"]) < 0.03:
            note = "<-- similar drawdown"
            if best_const is None or abs(st["maxdd"] - s50["maxdd"]) < abs(best_const[2]["maxdd"] - s50["maxdd"]):
                best_const = (float(a), st, st)
        print(f"  {a:>10.2f} {st['cagr']:>9.2%} {st['maxdd']:>9.2%} "
              f"{st['sharpe']:>8.2f}  {note}")
    if best_const:
        a, st, _ = best_const
        print(f"\n  best drawdown-matched constant: {a:.0%} exposure")
        print(f"    constant {a:.0%} : MaxDD {st['maxdd']:.2%}  Sharpe {st['sharpe']:.2f}")
        print(f"    SMA-50      : MaxDD {s50['maxdd']:.2%}  Sharpe {s50['sharpe']:.2f}")
        d_ = s50["sharpe"] - st["sharpe"]
        print(f"    -> SMA-50 {'BEATS' if d_ > 0 else 'LOSES TO'} the matched constant "
              f"by {d_:+.3f} Sharpe")

    # ---------- 2. ERA DEPENDENCE ----------
    print(f"\n{'=' * 94}")
    print("# 2. ERA DEPENDENCE — is the edge just the illiquid 2012-2015 years?")
    print(f"{'=' * 94}")
    for label, start in (("full 2012-2026", None),
                         ("excl 2012-2014", "2015-01-01"),
                         ("excl 2012-2016", "2017-01-01"),
                         ("2019+ only", "2019-01-01"),
                         ("2021+ only", "2021-01-01")):
        m = pd.Series(True, index=c.index) if start is None else c.index >= pd.Timestamp(start, tz="UTC")
        if m.sum() < 300:
            continue
        e = e50[m]
        a = float(e.mean())
        sr = stats(run(r[m], e))
        sb = stats(run(r[m], pd.Series(1.0, index=r[m].index), 0.0))
        sf = stats(run(r[m], pd.Series(a, index=r[m].index)))
        yrs = m.sum() / PPY
        print(f"\n  {label}  ({yrs:.1f}y, avgExp {a:.1%})")
        print(f"    SMA-50    Sharpe {sr['sharpe']:>6.2f}  CAGR {sr['cagr']:>8.2%}  "
              f"MaxDD {sr['maxdd']:>7.2%}")
        print(f"    buy&hold  Sharpe {sb['sharpe']:>6.2f}  CAGR {sb['cagr']:>8.2%}  "
              f"MaxDD {sb['maxdd']:>7.2%}")
        print(f"    flat {a:.0%}   Sharpe {sf['sharpe']:>6.2f}  CAGR {sf['cagr']:>8.2%}  "
              f"MaxDD {sf['maxdd']:>7.2%}")
        print(f"    vs flat: {sr['sharpe'] - sf['sharpe']:+.3f}   "
              f"vs B&H: {sr['sharpe'] - sb['sharpe']:+.3f}")

    # ---------- 3. COST ----------
    print(f"\n{'=' * 94}")
    print("# 3. COST SENSITIVITY (crypto spot taker is realistically 10-50bps)")
    print(f"{'=' * 94}")
    turn = float((e50.shift(1).diff().abs().fillna(0).sum()) / ny)
    print(f"\n  turnover: {turn:.1f}x/year\n")
    for cost in (0, 10, 20, 30, 50, 100):
        st = stats(run(r, e50, cost))
        print(f"  {cost:>4.0f}bps  CAGR {st['cagr']:>8.2%}  MaxDD {st['maxdd']:>8.2%}  "
              f"Sharpe {st['sharpe']:.2f}")

    # ---------- 4. Proper episode count ----------
    print(f"\n{'=' * 94}")
    print("# 4. CORRECTED INDEPENDENCE COUNT")
    print(f"{'=' * 94}")
    eq = run(r, pd.Series(1.0, index=r.index), 0.0)
    dd = (eq / eq.cummax() - 1)
    # Count NON-OVERLAPPING drawdown cycles: a new episode starts only after
    # recovering to a new high.
    episodes = 0
    prev_peak = -np.inf
    for i in range(len(eq)):
        v = eq.iloc[i]
        if v > prev_peak:
            prev_peak = v
        elif v < prev_peak * 0.80:
            episodes += 1
            prev_peak = v  # reset so the same decline is not recounted
    print(f"\n  non-overlapping >20% drawdown episodes: {episodes}")
    print(f"  annualised volatility: {r.std()*np.sqrt(PPY):.1%}")
    print(f"  return autocorrelation (lag1): {r.autocorr(1):+.3f}")
    print(f"\n  Honest reading: a single asset's 15y history contains only a")
    print(f"  handful of truly independent market cycles, plus {episodes} drawdown")
    print(f"  episodes. The daily n={n} massively overstates independence.")

    # ---------- 5. Does the rule survive a LAGGED, noisier version? ----------
    print(f"\n{'=' * 94}")
    print("# 5. ROBUSTNESS — add execution delay and exposure noise")
    print(f"{'=' * 94}")
    print(f"\n  {'variant':<34} {'CAGR':>9} {'MaxDD':>9} {'Sharpe':>8}")
    for lag in (0, 1, 2, 3):
        e = e50.shift(lag).fillna(0.5) if lag else e50
        st = stats(run(r, e))
        print(f"  {'execution delay ' + str(lag) + ' extra bars':<34} "
              f"{st['cagr']:>9.2%} {st['maxdd']:>9.2%} {st['sharpe']:>8.2f}")
    rng = np.random.default_rng(7)
    for noise in (0.05, 0.10):
        en = (e50 + rng.normal(0, noise, len(e50))).clip(0, 1)
        st = stats(run(r, pd.Series(en, index=r.index)))
        print(f"  {'exposure noise sd=' + str(noise):<34} "
              f"{st['cagr']:>9.2%} {st['maxdd']:>9.2%} {st['sharpe']:>8.2f}")


if __name__ == "__main__":
    main()
