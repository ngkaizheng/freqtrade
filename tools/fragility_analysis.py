"""FRAGILITY ANALYSIS of the BTC SMA-50 edge.

The 15-year full-sample result was edge +0.187 Sharpe vs a matched flat control.
But the clean train/test split showed out-of-sample edges at or below zero. Those
two facts must be reconciled, and the reconciliation is a fragility test:

    If a modest edge is concentrated in a few years or a few days, then the
    full-sample number is an artifact of those observations, not a property of
    the rule.

This is DIAGNOSTIC, not a new hypothesis. Nothing is re-tuned or re-selected:
the rule stays frozen at SMA-50 / 50%-100%, the metric stays (Sharpe_rule -
Sharpe_flat) on matched exposure. I am asking only "how stable is this number?"
-- which is what a robustness check is for.

Tests:
  1. Leave-one-year-out jackknife
  2. Era split (pre-2019 vs 2019+)
  3. Profit concentration (share of P&L from the best k days)
  4. Bootstrap CI on the edge
  5. The same on the 20-major Binance pool
"""

import os
import numpy as np
import pandas as pd

PPY_C = 365
COST_C = 10.0
MA = 50
RISK_ON, RISK_OFF = 1.00, 0.50

MAJORS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "DOT", "LINK",
          "LTC", "BCH", "ATOM", "UNI", "AAVE", "XLM", "ETC", "ALGO", "FIL",
          "NEO", "TRX"]


def sharpe(r, ppy=PPY_C):
    sd = r.std()
    return float(r.mean() / sd * np.sqrt(ppy)) if sd and sd > 0 else np.nan


def sma_expo(close, w=MA):
    ma = close.rolling(w, min_periods=w).mean()
    v = ma.notna()
    out = pd.Series(0.5, index=close.index)
    out[v] = np.where(close[v] > ma[v], RISK_ON, RISK_OFF)
    return out


def nets(rets, close, cost=COST_C):
    """Return (rule_net, flat_net) daily net return series on matched exposure."""
    e = sma_expo(close)
    pos = e.shift(1).fillna(0.0)
    turn = pos.diff().abs().fillna(pos.abs())
    rule = pos * rets - turn * cost / 10_000.0
    flat = pd.Series(float(e.mean()), index=rets.index) * rets
    return rule, flat


def edge(rets, close, cost=COST_C):
    r, f = nets(rets, close, cost)
    return sharpe(r) - sharpe(f)


def block_idx(n, block, rng):
    nb = int(np.ceil(n / block))
    st = rng.integers(0, n, nb)
    return np.concatenate([np.arange(s, s + block) % n for s in st])[:n]


def fragility(label, close, rets):
    print(f"\n{'=' * 96}")
    print(f"# {label}")
    print(f"{'=' * 96}")
    print(f"  span {close.index[0].date()} -> {close.index[-1].date()} "
          f"({len(rets)/PPY_C:.1f}y)")

    base = edge(rets, close)
    print(f"\n  full-sample edge (Sharpe_rule - Sharpe_flat): {base:+.3f}")

    # ---------- 1. Leave-one-year-out jackknife ----------
    print(f"\n  --- 1. LEAVE-ONE-YEAR-OUT JACKKNIFE ---")
    years = sorted(set(close.index.year))
    vals = []
    print(f"    {'dropped':<9} {'edge':>8} {'delta':>8}  effect")
    for y in years:
        m = close.index.year != y
        if m.sum() < 200:
            continue
        e = edge(rets[m], close[m])
        vals.append(e)
        d = e - base
        flag = "  <-- edge depends on this year" if d < -0.05 else ""
        print(f"    {y:<9} {e:>+8.3f} {d:>+8.3f}{flag}")
    vals = np.array(vals)
    print(f"\n    jackknife edge range : {vals.min():+.3f} .. {vals.max():+.3f}")
    print(f"    baseline             : {base:+.3f}")
    print(f"    -> {'FRAGILE: some year carries the edge' if vals.min() < 0 else 'edge survives dropping any single year'}")

    # ---------- 2. Era split ----------
    print(f"\n  --- 2. ERA SPLIT ---")
    for cut in ("2019-01-01",):
        c = pd.Timestamp(cut, tz=close.index.tz)
        pre = close.index < c
        post = ~pre
        e_pre = edge(rets[pre], close[pre])
        e_post = edge(rets[post], close[post])
        print(f"    pre-{cut[:4]}  ({pre.sum()/PPY_C:.1f}y): edge {e_pre:+.3f}")
        print(f"    {cut[:4]}+     ({post.sum()/PPY_C:.1f}y): edge {e_post:+.3f}")
        share = e_pre / base if base else np.nan
        print(f"    -> {'edge is concentrated in the early era' if e_post < e_pre * 0.5 else 'edge is present in both eras'}")

    # ---------- 3. Profit concentration ----------
    print(f"\n  --- 3. PROFIT CONCENTRATION (rule net returns) ---")
    r, f = nets(rets, close)
    excess = (r - f).dropna()
    tot = float(excess.sum())
    for k in (1, 5, 10, 25, 50):
        topk = float(excess.nlargest(k).sum())
        print(f"    top {k:>3} days contribute {topk/tot:>7.1%} of total excess "
              f"({k/len(excess):.2%} of days)")
    print(f"    -> {'HIGHLY concentrated (few days drive it)' if float(excess.nlargest(10).sum())/tot > 0.5 else 'reasonably distributed'}")

    # ---------- 4. Bootstrap CI ----------
    print(f"\n  --- 4. BOOTSTRAP CI on the edge (5000 draws, block 20) ---")
    rng = np.random.default_rng(1234)
    rn, fn = r.to_numpy(), f.to_numpy()
    n = len(rn)
    def shp(x):
        sd = x.std()
        return float(x.mean() / sd * np.sqrt(PPY_C)) if sd > 0 else 0.0
    bs = np.array([shp(rn[i]) - shp(fn[i])
                   for i in (block_idx(n, 20, rng) for _ in range(5000))])
    lo, hi = np.percentile(bs, [2.5, 97.5])
    print(f"    edge {base:+.3f}   CI [{lo:+.3f}, {hi:+.3f}]   p(<=0) {float((bs<=0).mean()):.3f}")
    print(f"    -> {'CI excludes 0' if lo > 0 else 'CI includes 0'}")

    return {"label": label, "base": base, "jack_min": float(vals.min()),
            "jack_max": float(vals.max()), "ci_lo": float(lo), "ci_hi": float(hi)}


def main():
    print("=" * 96)
    print("# FRAGILITY ANALYSIS — is the SMA-50 edge robust or concentrated?")
    print("=" * 96)
    print("\n  Diagnostic only. Rule frozen at SMA-50 / 50%-100%. Nothing re-tuned.")

    d = pd.read_feather("user_data/data/bitstamp/BTC_USD-1d.feather")
    d = d.sort_values("date").drop_duplicates("date")
    btc = d.set_index("date")["close"].astype(float).iloc[200:]
    r_btc = btc.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    res_btc = fragility("BTC/USD (Bitstamp, 15y)", btc, r_btc)

    closes = {}
    for m in MAJORS:
        p = f"user_data/data/binance/{m}_USDT-1d.feather"
        if not os.path.exists(p):
            continue
        dd = pd.read_feather(p).sort_values("date").drop_duplicates("date")
        closes[f"{m}/USDT"] = dd.set_index("date")["close"].astype(float)
    panel = pd.DataFrame(closes).sort_index().loc["2019-01-01":]
    prets = panel.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    ew = prets.mean(axis=1, skipna=True).fillna(0.0)
    idx = panel.ffill().mean(axis=1)
    res_pool = fragility("20-major equal-weight pool (Binance, 7.7y)", idx, ew)

    # ---------- Synthesis ----------
    print(f"\n{'=' * 96}")
    print("# SYNTHESIS — does this reconcile the full-sample pass with the OOS fail?")
    print(f"{'=' * 96}")
    rows = [("BTC/USD 15y", res_btc), ("20-major pool 7.7y", res_pool)]
    print(f"\n  {'dataset':<24} {'full edge':>10} {'jackknife min':>14} "
          f"{'CI low':>9} {'CI high':>9} {'CI excl 0?':>11}")
    for name, r in rows:
        excl = "yes" if r["ci_lo"] > 0 else "NO"
        print(f"  {name:<24} {r['base']:>+10.3f} {r['jack_min']:>+14.3f} "
              f"{r['ci_lo']:>+9.3f} {r['ci_hi']:>+9.3f} {excl:>11}")

    print(f"""
  How to read this:

  * A leave-one-year-out minimum FAR BELOW the baseline means one year carries
    the result -- the edge is not a property of the rule.
  * A bootstrap CI that includes zero means the full-sample edge is not
    distinguishable from no edge.
  * If either holds, the full-sample '+0.187' is a point estimate inside a wide
    interval, NOT evidence of a durable edge -- which is exactly consistent with
    the clean train/test split showing OOS edges at or below zero.

  Both statements can be true simultaneously:
      the rule passed the predefined historical gates
      AND the edge is too fragile to rely on
  Reconciling them is the point of this analysis.""")


if __name__ == "__main__":
    main()
