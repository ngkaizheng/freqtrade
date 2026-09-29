"""Exposure scaling: can the validated edge be made survivable?

The candidate's weakest point for "makes money sustainably" is the -74% maximum
drawdown. It beats buy & hold (-85%) but a 74% loss is not survivable for most
real capital.

Round 1 established that reducing exposure lowers drawdown MECHANICALLY. That
was a criticism when it was the only source of benefit. Here it is useful: the
validated part of SMA-50 is its RELATIVE edge (timing), and scaling exposure
uniformly should preserve the relative edge while proportionally shrinking the
drawdown.

Being explicit about what this does and does not show:
  * It does NOT create new alpha. Sharpe of a scaled version should be roughly
    unchanged, because scaling both the rule and its benchmark by the same
    constant is a near-linear transformation.
  * It DOES answer the practical question: at what exposure does the drawdown
    become survivable, and what does that cost in return?

Scales tested: the rule's 50/100 band compressed to 25/50, 37.5/75, and 50/100.
"""

import numpy as np
import pandas as pd

PPY = 365
COST = 10.0


def load_btc():
    d = pd.read_feather("user_data/data/bitstamp/BTC_USD-1d.feather")
    d = d.sort_values("date").drop_duplicates("date")
    c = d.set_index("date")["close"].astype(float)
    r = c.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return c.iloc[200:], r.iloc[200:]


def load_pool():
    s = {}
    for m in ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "DOT",
              "LINK", "LTC", "BCH", "ATOM", "UNI", "AAVE", "XLM", "ETC",
              "ALGO", "FIL", "NEO", "TRX"]:
        p = f"user_data/data/binance/{m}_USDT-1d.feather"
        try:
            d = pd.read_feather(p).sort_values("date").drop_duplicates("date")
        except FileNotFoundError:
            continue
        s[f"{m}/USDT"] = d.set_index("date")["close"].astype(float)
    panel = pd.DataFrame(s).sort_index().loc["2019-01-01":]
    r = panel.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    return panel, r


def max_dd(e):
    return float((e / e.cummax() - 1.0).min())


def cagr(e):
    y = len(e) / PPY
    return float((e.iloc[-1] / e.iloc[0]) ** (1 / y) - 1) if y > 0 else np.nan


def sharpe(r):
    sd = r.std()
    return float(r.mean() / sd * np.sqrt(PPY)) if sd and sd > 0 else np.nan


def stats(e):
    return {"cagr": cagr(e), "maxdd": max_dd(e),
            "sharpe": sharpe(e.pct_change().dropna())}


def run(rets, expo, cost=COST):
    pos = expo.shift(1).fillna(0.0)
    turn = pos.diff().abs().fillna(pos.abs())
    return 10_000 * (1 + (pos * rets - turn * cost / 10_000)).cumprod()


def sma_raw(close, w=50):
    """Raw 0/1 signal: 1 when close > SMA."""
    ma = close.rolling(w, min_periods=w).mean()
    v = ma.notna()
    out = pd.Series(np.nan, index=close.index)
    out[v] = (close[v] > ma[v]).astype(float)
    return out


def scaled_expo(close, risk_on, risk_off, w=50):
    raw = sma_raw(close, w)
    expo = raw * (risk_on - risk_off) + risk_off
    return expo.ffill().fillna(risk_off)


def block_idx(n, block, rng):
    nb = int(np.ceil(n / block))
    st = rng.integers(0, n, nb)
    return np.concatenate([np.arange(s, s + block) % n for s in st])[:n]


def shp(x):
    sd = x.std()
    return float(x.mean() / sd * np.sqrt(PPY)) if sd > 0 else 0.0


def report(label, close, rets, scales):
    print(f"\n{'=' * 94}")
    print(f"# {label}")
    print(f"{'=' * 94}")
    print(f"  window {close.index[0].date()} -> {close.index[-1].date()} "
          f"({len(rets)/PPY:.1f}y), {COST:.0f}bps")
    n = len(rets)
    rng = np.random.default_rng(503)

    print(f"\n  {'exposure band':<16} {'avgExp':>7} {'CAGR':>9} {'MaxDD':>9} "
          f"{'Sharpe':>8} {'d vs flat':>10}  {'boot p':>7}")
    out = []
    for on, off in scales:
        e = scaled_expo(close, on, off)
        avg = float(e.mean())
        st = stats(run(rets, e))
        fl = stats(run(rets, pd.Series(avg, index=rets.index)))
        p_ = e.shift(1).fillna(0.0)
        t_ = p_.diff().abs().fillna(p_.abs())
        rr = (p_ * rets - t_ * COST / 10_000).to_numpy()
        rf = (avg * rets).to_numpy()
        bs = np.array([shp(rr[i]) - shp(rf[i])
                       for i in (block_idx(n, 20, rng) for _ in range(2000))])
        bplo = np.percentile(bs, 2.5)
        out.append((on, off, avg, st, st["sharpe"] - fl["sharpe"], bplo))
        print(f"  {f'{on:.0%}/{off:.0%}':<16} {avg:>6.1%} {st['cagr']:>9.2%} "
              f"{st['maxdd']:>9.2%} {st['sharpe']:>8.2f} "
              f"{st['sharpe'] - fl['sharpe']:>+10.3f}  "
              f"{'sig' if bplo > 0 else 'ns':>7}")

    # Buy & hold for reference
    bh = stats(run(rets, pd.Series(1.0, index=rets.index), 0.0))
    print(f"\n  buy & hold      : CAGR {bh['cagr']:>8.2%}  MaxDD {bh['maxdd']:>8.2%}  "
          f"Sharpe {bh['sharpe']:.2f}")
    return out


def main():
    print("=" * 94)
    print("# EXPOSURE SCALING — making the validated edge survivable")
    print("=" * 94)
    print("\n  The validated component is the RELATIVE (timing) edge. Scaling")
    print("  exposure down should preserve it while shrinking drawdown.")
    print("  This is NOT new alpha — it is risk budgeting.")

    scales = [(1.00, 0.50), (0.75, 0.375), (0.50, 0.25), (0.40, 0.20), (0.25, 0.125)]

    c_btc, r_btc = load_btc()
    out_btc = report("BTC/USD 15y (Bitstamp)", c_btc, r_btc, scales)

    panel, rets_all = load_pool()
    idx = panel.ffill().mean(axis=1)
    pool_rets = rets_all.mean(axis=1, skipna=True).fillna(0.0)
    out_pool = report("20-major equal-weight pool (Binance)", idx, pool_rets, scales)

    # ---- Interpretation ----
    print(f"\n{'=' * 94}")
    print("# INTERPRETATION")
    print(f"{'=' * 94}")
    print(f"\n  {'band':<12} {'BTC MaxDD':>11} {'pool MaxDD':>12} {'BTC edge':>10} "
          f"{'pool edge':>10}")
    for b, p in zip(out_btc, out_pool):
        on_b, off_b, avg_b, st_b, edge_b, lo_b = b
        on_p, off_p, avg_p, st_p, edge_p, lo_p = p
        print(f"  {f'{on_b:.0%}/{off_b:.0%}':<12} {st_b['maxdd']:>11.2%} "
              f"{st_p['maxdd']:>12.2%} {edge_b:>+10.3f} {edge_p:>+10.3f}")

    print(f"""
  Reading it correctly:
    * The RELATIVE edge (d vs flat) is roughly stable across bands, confirming
      it is the timing that carries information, not the position size.
    * Drawdown scales down roughly proportionally with exposure. That is the
      mechanical effect round 1 identified -- useful here, not a discovery.
    * A ~25/12.5% band brings the drawdown into a range a real account can
      survive, at the cost of most of the absolute return.

  It does NOT make the strategy "safe". It is still a directional crypto
  position; the drawdown is inherent to the asset.""")


if __name__ == "__main__":
    main()
