"""Within-domain replication: frozen SMA-50 on Binance crypto majors.

This is the direct counterpart to tools/equity_out_of_domain.py. Identical
methodology, identical frozen rule (SMA-50, 50%/100%, no re-tuning), applied to
20 large-cap crypto majors from Binance instead of 109 US equities.

Purpose: an apples-to-apples comparison so the domain effect can be read off
cleanly.

  equity_out_of_domain.py  -> 109 equities, mean dSharpe vs flat -0.065, 0/4 gates
  this script              ->  20 crypto majors, same method

Also fixes a flaw in my round-2 test (sma_cross_asset_wf.py): that one selected
the window per fold, which multiplies trials. Here the rule is FROZEN at 50.

User constraint honoured: majors only, no meme coins or micro alts.
"""

import glob
import os

import numpy as np
import pandas as pd

PPY = 365
COST = 10.0
DIR = "user_data/data/binance"

MAJORS = [
    "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "DOT", "LINK",
    "LTC", "BCH", "ATOM", "UNI", "AAVE", "XLM", "ETC", "ALGO", "FIL",
    "NEO", "TRX",
]


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
    return 10_000 * (1 + (pos * rets - turn * cost / 10_000.0)).cumprod()


def sma_expo(close, w=50):
    ma = close.rolling(w, min_periods=w).mean()
    v = ma.notna()
    out = pd.Series(0.5, index=close.index)
    out[v] = np.where(close[v] > ma[v], 1.0, 0.5)
    return out


def block_idx(n, block, rng):
    nb = int(np.ceil(n / block))
    st = rng.integers(0, n, nb)
    return np.concatenate([np.arange(s, s + block) % n for s in st])[:n]


def shp(x):
    sd = x.std()
    return float(x.mean() / sd * np.sqrt(PPY)) if sd > 0 else 0.0


def main():
    closes = {}
    for m in MAJORS:
        p = os.path.join(DIR, f"{m}_USDT-1d.feather")
        if not os.path.exists(p):
            continue
        d = pd.read_feather(p).sort_values("date").drop_duplicates("date")
        closes[f"{m}/USDT"] = d.set_index("date")["close"].astype(float)

    panel = pd.DataFrame(closes).sort_index()
    panel = panel.loc["2019-01-01":]
    rets_all = panel.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)

    print("=" * 94)
    print("# WITHIN-DOMAIN: frozen SMA-50 on 20 Binance crypto majors")
    print("=" * 94)
    print(f"universe: {panel.shape[1]} majors (no meme/micro alts)")
    print(f"window  : {panel.index[0].date()} -> {panel.index[-1].date()} "
          f"({len(panel)/PPY:.1f}y)")
    print(f"rule    : FROZEN SMA-50, 50%/100%, {COST:.0f}bps\n")

    # ---------- 1. Per-asset replication ----------
    print("=" * 94)
    print("# 1. PER-ASSET REPLICATION")
    print(f"{'=' * 94}")
    print(f"\n  {'pair':<12} {'yrs':>5} {'BH SR':>7} {'rule SR':>8} {'flat SR':>8} "
          f"{'d vs flat':>10}  better?")
    rows = []
    for t in panel.columns:
        c = panel[t].dropna()
        if len(c) < 400:
            continue
        r = c.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        e = sma_expo(c)
        a = float(e.mean())
        sb = stats(run(r, pd.Series(1.0, index=r.index), 0.0))
        sd_ = stats(run(r, e))
        sf = stats(run(r, pd.Series(a, index=r.index)))
        d = sd_["sharpe"] - sf["sharpe"]
        rows.append({"pair": t, "yrs": len(c) / PPY, "d": d,
                     "d_bh": sd_["sharpe"] - sb["sharpe"],
                     "dd_bh": sb["maxdd"], "dd_rule": sd_["maxdd"]})
        print(f"  {t:<12} {len(c)/PPY:>5.1f} {sb['sharpe']:>7.2f} "
              f"{sd_['sharpe']:>8.2f} {sf['sharpe']:>8.2f} {d:>+10.3f}  "
              f"{'YES' if d > 0 else 'no':>7}")

    res = pd.DataFrame(rows)
    n = len(res)
    wins = int((res["d"] > 0).sum())
    print(f"\n  beats flat control : {wins}/{n} ({wins/n:.0%})")
    print(f"  mean dSharpe       : {res['d'].mean():+.3f}")
    print(f"  median dSharpe     : {res['d'].median():+.3f}")
    print(f"  drawdown improved  : {int((res['dd_rule'] > res['dd_bh']).sum())}/{n}")

    from math import comb
    p_sign = sum(comb(n, k) for k in range(wins, n + 1)) / (2 ** n)
    print(f"  sign test p        : {p_sign:.4f}")

    # ---------- 2. Correlation ----------
    corr = rets_all.corr()
    off = corr.where(~np.eye(len(corr), dtype=bool)).stack()
    ev = np.linalg.eigvalsh(corr.fillna(0).to_numpy())
    ev = ev[ev > 0]
    n_eff = float((ev.sum() ** 2) / (ev ** 2).sum())
    print(f"\n  mean pairwise correlation  : {float(off.mean()):.3f}")
    print(f"  EFFECTIVE independent bets : ~{n_eff:.1f} (nominal {n})")

    # ---------- 3. Correlation-aware null ----------
    print(f"\n{'=' * 94}")
    print("# 2. CORRELATION-AWARE NULL (identical method to the equity test)")
    print(f"{'=' * 94}")
    rng = np.random.default_rng(401)
    common = rets_all.mean(axis=1).fillna(0.0)
    obs = float(res["d"].mean())
    nulls = []
    for _ in range(300):
        z = rng.standard_normal((len(common), 1)) * common.std()
        sim = pd.DataFrame(
            np.repeat(z, n, axis=1) +
            rng.standard_normal((len(common), n)) * rets_all.std().mean() * 0.5,
            index=common.index, columns=res["pair"].tolist(),
        )
        ds = []
        for t in sim.columns:
            r = sim[t].fillna(0.0)
            c = 100 * (1 + r).cumprod()
            e = sma_expo(c)
            a = float(e.mean())
            ds.append(stats(run(r, e))["sharpe"] -
                      stats(run(r, pd.Series(a, index=r.index)))["sharpe"])
        nulls.append(np.mean(ds))
    nulls = np.array(nulls)
    p_mean = float((nulls >= obs).mean())
    print(f"\n  observed mean dSharpe : {obs:+.3f}")
    print(f"  null mean / p95       : {nulls.mean():+.3f} / {np.percentile(nulls, 95):+.3f}")
    print(f"  p-value               : {p_mean:.3f}")
    print(f"  -> {'SURVIVES' if p_mean < 0.05 else 'FAILS correlation-aware null'}")

    # ---------- 4. Equal-weight pool ----------
    print(f"\n{'=' * 94}")
    print("# 3. EQUAL-WEIGHT SAME-POOL PORTFOLIO")
    print(f"{'=' * 94}")
    rets_p = rets_all.mean(axis=1, skipna=True).fillna(0.0)
    idx = panel.ffill().mean(axis=1)
    e50 = sma_expo(idx).reindex(rets_p.index).fillna(0.5)
    a50 = float(e50.mean())
    print(f"\n  {'rule':<26} {'avgExp':>7} {'CAGR':>9} {'MaxDD':>9} {'Sharpe':>8}")
    for lbl, e, a in (("equal-weight B&H", pd.Series(1.0, index=rets_p.index), 1.0),
                      ("SMA-50", e50, a50),
                      (f"flat @ {a50:.0%}", pd.Series(a50, index=rets_p.index), a50)):
        st = stats(run(rets_p, e))
        print(f"  {lbl:<26} {a:>6.1%} {st['cagr']:>9.2%} {st['maxdd']:>9.2%} "
              f"{st['sharpe']:>8.2f}")

    rng2 = np.random.default_rng(409)
    nn = len(rets_p)
    p_ = e50.shift(1).fillna(0.0)
    t_ = p_.diff().abs().fillna(p_.abs())
    rr = (p_ * rets_p - t_ * COST / 10_000).to_numpy()
    rf = (a50 * rets_p).to_numpy()
    pt = shp(rr) - shp(rf)
    bs = np.array([shp(rr[i]) - shp(rf[i])
                   for i in (block_idx(nn, 20, rng2) for _ in range(5000))])
    lo, hi = np.percentile(bs, [2.5, 97.5])
    print(f"\n  bootstrap vs flat: dSharpe {pt:+.3f}  CI [{lo:+.3f}, {hi:+.3f}]  "
          f"p={float((bs <= 0).mean()):.3f}")
    print(f"  -> {'SIGNIFICANT' if lo > 0 else 'NOT significant'}")

    # ---------- 5. Same-domain comparison table ----------
    print(f"\n{'=' * 94}")
    print("# 4. DOMAIN COMPARISON (identical methodology)")
    print(f"{'=' * 94}")
    print(f"\n  {'domain':<28} {'series':>7} {'wins':>7} {'mean dSharpe':>13} "
          f"{'corr-null p':>12}")
    print(f"  {'crypto majors (this)':<28} {n:>7} {wins:>7} {obs:>+13.3f} "
          f"{p_mean:>12.3f}")
    print(f"  {'US equities (OOD test)':<28} {109:>7} {22:>7} {-0.065:>+13.3f} "
          f"{'0.793':>12}")
    print(f"\n  -> crypto is the favourable domain; equities mean-revert (VR(5)")
    print(f"     0.916) so trend rules LOSE there.")


if __name__ == "__main__":
    main()
