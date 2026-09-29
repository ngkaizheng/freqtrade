"""RECONCILIATION: why does freqtrade report Sharpe 0.92 while my study says 1.45?

This is exactly the kind of discrepancy that invalidates a result. Two different
execution models are in play:

  A. CONSTANT-MIX (what tools/sma_15year_test.py does)
     Exposure is reset to 0.5 or 1.0 of CURRENT wealth every single day.
     Mathematically this means: as price rises you SELL some to return to
     target, and as price falls you BUY more. That generates a rebalancing
     premium (volatility harvesting), which flatters the result in a volatile
     asset like BTC (75% annualised vol).

  B. FIXED UNITS (what freqtrade does)
     custom_stake_amount buys a stake, and adjust_trade_position only trades
     when the regime flips. Between flips you simply HOLD. Exposure as a
     fraction of wealth drifts with price.

If most of the edge is the constant-mix rebalancing premium, the strategy does
NOT work as implemented and the whole finding collapses.
"""

import numpy as np
import pandas as pd

PPY = 365
COST = 10.0


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


def stats_from_returns(r):
    eq = (1 + r).cumprod()
    return {"cagr": cagr(eq), "maxdd": max_dd(eq), "sharpe": sharpe(r)}


def sma_expo(close, w):
    ma = close.rolling(w, min_periods=w).mean()
    v = ma.notna()
    out = pd.Series(0.5, index=close.index)
    out[v] = np.where(close[v] > ma[v], 1.0, 0.5)
    return out


def simulate_constant_mix(rets, expo, cost=COST):
    """A: daily rebalance to target exposure."""
    pos = expo.shift(1).fillna(0.0)
    turn = pos.diff().abs().fillna(pos.abs())
    return pos * rets - turn * cost / 10_000.0


def simulate_units(rets, expo, cost=COST, init_frac=0.5):
    """Clean fixed-units simulation tracking wealth directly.

    At each bar: apply the market return to the held position, then move to the
    PREVIOUS close's target fraction if it differs by more than the dead-band.
    """
    e = expo.ffill().fillna(0.5).to_numpy()
    r = rets.to_numpy()
    n = len(r)

    wealth = 1.0
    pos_val = init_frac * wealth
    cash = wealth - pos_val
    series = np.empty(n)
    series[0] = wealth

    for i in range(1, n):
        # 1. market move on whatever we held
        pos_val *= (1.0 + r[i])
        wealth = cash + pos_val

        # 2. act on the PREVIOUS close's regime (single lag point)
        tgt = e[i - 1]
        cur = pos_val / wealth if wealth > 0 else 0.0
        if abs(tgt - cur) > 0.125:
            want = tgt * wealth
            delta = want - pos_val
            wealth -= abs(delta) * cost / 10_000.0
            pos_val = want
            cash = wealth - pos_val

        series[i] = wealth

    eq = pd.Series(series, index=rets.index)
    eq = eq / eq.iloc[0]
    return eq.pct_change().fillna(0.0)


def main():
    d = load()
    c = d.set_index("date")["close"].astype(float)
    r = c.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    c, r = c.iloc[200:], r.iloc[200:]
    ny = len(r) / PPY

    e = sma_expo(c, 50)
    e = e.ffill().fillna(0.5)

    print("=" * 94)
    print("# RECONCILIATION — constant-mix vs fixed-units execution")
    print("=" * 94)
    print(f"{c.index[0].date()} -> {c.index[-1].date()} ({ny:.1f}y), {COST:.0f}bps")
    print(f"BTC annualised vol: {r.std()*np.sqrt(PPY):.1%}\n")

    # Buy & hold
    bh = stats_from_returns(r)
    print(f"  {'buy & hold':<40} CAGR {bh['cagr']:>8.2%}  MaxDD {bh['maxdd']:>8.2%}  "
          f"Sharpe {bh['sharpe']:.2f}")

    # A. constant-mix (the study)
    ra = simulate_constant_mix(r, e)
    sa = stats_from_returns(ra)
    print(f"  {'A. SMA-50 constant-mix (my study)':<40} CAGR {sa['cagr']:>8.2%}  "
          f"MaxDD {sa['maxdd']:>8.2%}  Sharpe {sa['sharpe']:.2f}")

    # B. fixed units (freqtrade)
    rb = simulate_units(r, e)
    sb = stats_from_returns(rb)
    print(f"  {'B. SMA-50 fixed-units (freqtrade)':<40} CAGR {sb['cagr']:>8.2%}  "
          f"MaxDD {sb['maxdd']:>8.2%}  Sharpe {sb['sharpe']:.2f}")

    # Also: fixed units at a CONSTANT fractional exposure matching the rule's mean
    avg = float(e.mean())
    r_flat_cm = simulate_constant_mix(r, pd.Series(avg, index=r.index))
    s_flat_cm = stats_from_returns(r_flat_cm)
    r_flat_fu = simulate_units(r, pd.Series(avg, index=r.index))
    s_flat_fu = stats_from_returns(r_flat_fu)
    print(f"  {'flat ' + f'{avg:.1%}' + ' constant-mix':<40} CAGR {s_flat_cm['cagr']:>8.2%}  "
          f"MaxDD {s_flat_cm['maxdd']:>8.2%}  Sharpe {s_flat_cm['sharpe']:.2f}")
    print(f"  {'flat ' + f'{avg:.1%}' + ' fixed-units':<40} CAGR {s_flat_fu['cagr']:>8.2%}  "
          f"MaxDD {s_flat_fu['maxdd']:>8.2%}  Sharpe {s_flat_fu['sharpe']:.2f}")

    # ---- How much of the edge survives? ----
    print(f"\n{'=' * 94}")
    print("# HOW MUCH OF THE EDGE SURVIVES REALISTIC EXECUTION?")
    print(f"{'=' * 94}")
    print(f"\n  constant-mix  : rule {sa['sharpe']:.2f} - flat {s_flat_cm['sharpe']:.2f} "
          f"= {sa['sharpe'] - s_flat_cm['sharpe']:+.3f}")
    print(f"  fixed-units   : rule {sb['sharpe']:.2f} - flat {s_flat_fu['sharpe']:.2f} "
          f"= {sb['sharpe'] - s_flat_fu['sharpe']:+.3f}")
    print(f"\n  buy & hold Sharpe: {bh['sharpe']:.2f}")
    print(f"  fixed-units rule beats buy & hold by: {sb['sharpe'] - bh['sharpe']:+.3f}")

    # ---- Bootstrap the fixed-units edge ----
    print(f"\n{'=' * 94}")
    print("# BOOTSTRAP the REALISTIC (fixed-units) edge vs flat, 5000 draws")
    print(f"{'=' * 94}")
    n = len(r)
    rng = np.random.default_rng(113)

    def blk(nn, block, rr):
        nb = int(np.ceil(nn / block))
        st = rr.integers(0, nn, nb)
        return np.concatenate([(np.arange(s, s + block) % nn) for s in st])[:nn]

    def shp(x):
        sd = x.std()
        return float(x.mean() / sd * np.sqrt(PPY)) if sd > 0 else 0.0

    a_r = rb.to_numpy()
    a_f = r_flat_fu.to_numpy()
    pt = shp(a_r) - shp(a_f)
    bs = np.array([shp(a_r[i]) - shp(a_f[i])
                   for i in (blk(n, 20, rng) for _ in range(5000))])
    lo, hi = np.percentile(bs, [2.5, 97.5])
    print(f"\n  dSharpe {pt:+.3f}   95% CI [{lo:+.3f}, {hi:+.3f}]   "
          f"p(<=0) {float((bs <= 0).mean()):.3f}")
    print(f"  -> {'SIGNIFICANT after realistic execution' if lo > 0 else 'NOT significant once realistic execution is modelled'}")

    # vs buy & hold directly
    pt2 = shp(a_r) - shp(r.to_numpy())
    bs2 = np.array([shp(a_r[i]) - shp(r.to_numpy()[i])
                    for i in (blk(n, 20, rng) for _ in range(5000))])
    lo2, hi2 = np.percentile(bs2, [2.5, 97.5])
    print(f"\n  vs buy & hold: dSharpe {pt2:+.3f}  CI [{lo2:+.3f}, {hi2:+.3f}]  "
          f"p(<=0) {float((bs2 <= 0).mean()):.3f}")
    print(f"  -> {'SIGNIFICANT' if lo2 > 0 else 'NOT significant'}")


if __name__ == "__main__":
    main()
