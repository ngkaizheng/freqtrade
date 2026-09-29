"""OUT-OF-DOMAIN TEST — the frozen SMA-50 rule on US equities.

Why this is the strongest remaining test
----------------------------------------
Everything so far rests on crypto. If SMA-50 works only on BTC/Bitstamp, it is a
curve-fit to one market. The handoff calls cross-market replication "最强的防过
拟合证据之一" (one of the strongest anti-overfit evidence types).

This is a genuine out-of-domain test:
  * different asset class (equities, not crypto)
  * different venue and data source (yfinance via the handoff, not Bitstamp)
  * different volatility regime (equities ~15-20% vol vs crypto ~75%)
  * the rule is FROZEN at SMA-50 / 50%-100% — no re-tuning allowed
  * 109 tickers, 2010-2026, so this also gives a large cross-section

Critically, I also report the handoff's own MA200 result for comparison, since
the handoff already established that MA200 exposure management reduces drawdown
on equities. The question here is whether the FASTER SMA-50 adds anything.

NOTE ON SURVIVORSHIP: the 109 tickers are today's large caps. The handoff
documented this as +1.78% CAGR / +0.141 Sharpe of upward bias. Because both legs
of every comparison use the identical universe, the bias largely cancels in the
relative comparison — same argument as the crypto pool.
"""

import glob
import os

import numpy as np
import pandas as pd

PPY = 252  # US equities trade ~252 days/year
COST = 5.0  # equities: much cheaper than crypto
CACHE = "quant-research-handoff/data/cache"
WINDOWS = [10, 20, 30, 50, 75, 100, 150, 200]


def max_dd(e):
    return float((e / e.cummax() - 1.0).min())


def cagr(e, ppy=PPY):
    y = len(e) / ppy
    return float((e.iloc[-1] / e.iloc[0]) ** (1 / y) - 1) if y > 0 else np.nan


def sharpe(r, ppy=PPY):
    sd = r.std()
    return float(r.mean() / sd * np.sqrt(ppy)) if sd and sd > 0 else np.nan


def stats(e, ppy=PPY):
    return {"cagr": cagr(e, ppy), "maxdd": max_dd(e),
            "sharpe": sharpe(e.pct_change().dropna(), ppy)}


def run(rets, expo, cost=COST):
    pos = expo.shift(1).fillna(0.0)
    turn = pos.diff().abs().fillna(pos.abs())
    return 10_000 * (1 + (pos * rets - turn * cost / 10_000.0)).cumprod()


def sma_expo(close, w):
    ma = close.rolling(w, min_periods=w).mean()
    v = ma.notna()
    out = pd.Series(0.5, index=close.index)
    out[v] = np.where(close[v] > ma[v], 1.0, 0.5)
    return out


def load_universe():
    """Load all equity CSVs into a close panel."""
    series = {}
    for path in sorted(glob.glob(os.path.join(CACHE, "*.csv"))):
        ticker = os.path.basename(path)[:-4]
        try:
            d = pd.read_csv(path, parse_dates=["Date"])
        except Exception:
            continue
        d = d.dropna(subset=["Close"]).drop_duplicates("Date").sort_values("Date")
        if len(d) < 500:
            continue
        series[ticker] = d.set_index("Date")["Close"].astype(float)
    return pd.DataFrame(series).sort_index()


def block_idx(n, block, rng):
    nb = int(np.ceil(n / block))
    st = rng.integers(0, n, nb)
    idx = []
    for s in st:
        idx.append(np.arange(s, s + block) % n)
    return np.concatenate(idx)[:n]


def shp(x):
    sd = x.std()
    return float(x.mean() / sd * np.sqrt(PPY)) if sd > 0 else 0.0


def main():
    close_all = load_universe()
    print("=" * 94)
    print("# OUT-OF-DOMAIN TEST — frozen SMA-50 on US equities")
    print("=" * 94)
    print(f"universe: {close_all.shape[1]} tickers   "
          f"{close_all.index.min().date()} -> {close_all.index.max().date()}")
    print(f"rule FROZEN: SMA-50, exposure 50%/100%, {COST:.0f}bps. No re-tuning.\n")

    # Evaluate from 2011 so every ticker has warm-up and the model does not
    # start mid-crisis.
    close_all = close_all.loc["2011-01-01":]

    # ---------------- 1. Per-ticker replication (frozen SMA-50) ----------------
    print("=" * 94)
    print("# 1. PER-TICKER REPLICATION — frozen SMA-50 vs buy & hold vs flat")
    print(f"{'=' * 94}")
    rows = []
    for t in close_all.columns:
        c = close_all[t].dropna()
        if len(c) < 400:
            continue
        r = c.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        e = sma_expo(c, 50)
        a = float(e.mean())
        sb = stats(run(r, pd.Series(1.0, index=r.index), 0.0))
        sd_ = stats(run(r, e))
        sf = stats(run(r, pd.Series(a, index=r.index)))
        rows.append({"ticker": t, "years": len(c) / PPY,
                     "bh_sharpe": sb["sharpe"], "rule_sharpe": sd_["sharpe"],
                     "flat_sharpe": sf["sharpe"],
                     "d_bh": sd_["sharpe"] - sb["sharpe"],
                     "d_flat": sd_["sharpe"] - sf["sharpe"],
                     "bh_dd": sb["maxdd"], "rule_dd": sd_["maxdd"]})

    res = pd.DataFrame(rows)
    print(f"\n  tickers tested: {len(res)}")
    print(f"  mean years: {res['years'].mean():.1f}")

    wins_bh = int((res["d_bh"] > 0).sum())
    wins_flat = int((res["d_flat"] > 0).sum())
    print(f"\n  beats buy & hold Sharpe : {wins_bh}/{len(res)} "
          f"({wins_bh/len(res):.0%})")
    print(f"  beats flat control      : {wins_flat}/{len(res)} "
          f"({wins_flat/len(res):.0%})")
    print(f"  mean dSharpe vs B&H     : {res['d_bh'].mean():+.3f}")
    print(f"  mean dSharpe vs flat    : {res['d_flat'].mean():+.3f}")
    print(f"  median dSharpe vs flat  : {res['d_flat'].median():+.3f}")
    dd_improved = int((res["rule_dd"] > res["bh_dd"]).sum())
    print(f"  drawdown improved       : {dd_improved}/{len(res)} "
          f"({dd_improved/len(res):.0%})")

    # Sign test, and the correlation-aware caveat
    from math import comb
    n = len(res)
    for label, w in (("vs buy & hold", wins_bh), ("vs flat", wins_flat)):
        p = sum(comb(n, k) for k in range(w, n + 1)) / (2 ** n)
        print(f"\n  sign test {label}: p = {p:.2e}")

    # Equity cross-correlation -> effective independent bets (the round-2 lesson)
    rets_all = close_all.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    corr = rets_all.corr()
    off = corr.where(~np.eye(len(corr), dtype=bool)).stack()
    ev = np.linalg.eigvalsh(corr.fillna(0).to_numpy())
    ev = ev[ev > 0]
    n_eff = float((ev.sum() ** 2) / (ev ** 2).sum())
    print(f"\n  mean pairwise correlation : {float(off.mean()):.3f}")
    print(f"  EFFECTIVE independent bets: ~{n_eff:.1f}  (nominal {len(res)})")

    # ---------------- 2. Correlation-aware null ----------------
    print(f"\n{'=' * 94}")
    print("# 2. CORRELATION-AWARE NULL (the round-2 lesson applied)")
    print(f"{'=' * 94}")
    rng = np.random.default_rng(307)
    common = rets_all.mean(axis=1).fillna(0.0)
    obs_mean = float(res["d_flat"].mean())
    nulls = []
    for _ in range(300):
        # One common factor + idiosyncratic noise, matched vol.
        z = rng.standard_normal((len(common), 1)) * common.std()
        sim = pd.DataFrame(
            np.repeat(z, len(res), axis=1) +
            rng.standard_normal((len(common), len(res))) * rets_all.std().mean() * 0.5,
            index=common.index, columns=res["ticker"].tolist(),
        )
        d = []
        for t in sim.columns:
            r = sim[t].fillna(0.0)
            c = 100 * (1 + r).cumprod()
            e = sma_expo(c, 50)
            a = float(e.mean())
            d.append(stats(run(r, e))["sharpe"] -
                     stats(run(r, pd.Series(a, index=r.index)))["sharpe"])
        nulls.append(np.mean(d))
    nulls = np.array(nulls)
    p_mean = float((nulls >= obs_mean).mean())
    print(f"\n  observed mean dSharpe vs flat : {obs_mean:+.3f}")
    print(f"  null mean / p95               : {nulls.mean():+.3f} / "
          f"{np.percentile(nulls, 95):+.3f}")
    print(f"  p-value                       : {p_mean:.3f}")
    print(f"  -> {'SURVIVES correlation-aware null' if p_mean < 0.05 else 'fails correlation-aware null'}")

    # ---------------- 3. Equal-weight same-pool portfolio ----------------
    print(f"\n{'=' * 94}")
    print("# 3. EQUAL-WEIGHT SAME-POOL PORTFOLIO (2011-2026)")
    print(f"{'=' * 94}")
    rets_p = rets_all.mean(axis=1, skipna=True).fillna(0.0)
    idx = close_all.ffill().mean(axis=1)
    e50 = sma_expo(idx, 50).reindex(rets_p.index).fillna(0.5)
    a50 = float(e50.mean())
    s_rule = stats(run(rets_p, e50))
    s_bh = stats(run(rets_p, pd.Series(1.0, index=rets_p.index)))
    s_flat = stats(run(rets_p, pd.Series(a50, index=rets_p.index)))
    print(f"\n  {'rule':<28} {'avgExp':>7} {'CAGR':>9} {'MaxDD':>9} {'Sharpe':>8}")
    for lbl, e, a in (("equal-weight B&H", pd.Series(1.0, index=rets_p.index), 1.0),
                      ("SMA-50", e50, a50),
                      (f"flat @ {a50:.0%}", pd.Series(a50, index=rets_p.index), a50)):
        st = stats(run(rets_p, e))
        print(f"  {lbl:<28} {a:>6.1%} {st['cagr']:>9.2%} {st['maxdd']:>9.2%} "
              f"{st['sharpe']:>8.2f}")

    # Window grid on the equity pool
    print(f"\n  window grid on the equity pool:")
    print(f"  {'window':<9} {'Sharpe':>8} {'vs flat':>9}")
    for w in WINDOWS:
        e = sma_expo(idx, w).reindex(rets_p.index).fillna(0.5)
        a = float(e.mean())
        st = stats(run(rets_p, e))
        fl = stats(run(rets_p, pd.Series(a, index=rets_p.index)))
        print(f"  {w:<9} {st['sharpe']:>8.2f} {st['sharpe'] - fl['sharpe']:>+9.3f}")

    # ---------------- 4. Bootstrap on the equity portfolio ----------------
    print(f"\n{'=' * 94}")
    print("# 4. BOOTSTRAP on the equity pool vs flat, 5000 draws")
    print(f"{'=' * 94}")
    rng2 = np.random.default_rng(311)
    nn = len(rets_p)
    p_ = e50.shift(1).fillna(0.0)
    t_ = p_.diff().abs().fillna(p_.abs())
    rr = (p_ * rets_p - t_ * COST / 10_000).to_numpy()
    rf = (a50 * rets_p).to_numpy()
    pt = shp(rr) - shp(rf)
    bs = np.array([shp(rr[i]) - shp(rf[i])
                   for i in (block_idx(nn, 20, rng2) for _ in range(5000))])
    lo, hi = np.percentile(bs, [2.5, 97.5])
    print(f"\n  dSharpe {pt:+.3f}   95% CI [{lo:+.3f}, {hi:+.3f}]   "
          f"p(<=0) {float((bs <= 0).mean()):.3f}")
    print(f"  -> {'SIGNIFICANT' if lo > 0 else 'NOT significant'}")

    # ---------------- 5. Verdict ----------------
    print(f"\n{'=' * 94}")
    print("# VERDICT — does the crypto finding generalize to equities?")
    print(f"{'=' * 94}")
    checks = [
        (f"per-ticker beats flat >50% ({wins_flat}/{n})", wins_flat / n > 0.5),
        ("mean dSharpe vs flat > 0", obs_mean > 0),
        ("survives correlation-aware null", p_mean < 0.05),
        ("portfolio bootstrap CI excludes 0", lo > 0),
    ]
    for lbl, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {lbl}")
    print(f"\n  {sum(ok for _, ok in checks)}/{len(checks)} passed")
    print(f"\n  CAVEAT: {len(res)} tickers are today's survivors (handoff measured")
    print(f"  +1.78% CAGR / +0.141 Sharpe of upward bias), but both legs of each")
    print(f"  comparison use the identical universe, so the bias largely cancels")
    print(f"  in the RELATIVE result reported here.")


if __name__ == "__main__":
    main()
