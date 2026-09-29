"""Adversarial reproduction of the E#4/E#5 claims. Run by the reviewer, not by
the project. Every number here is recomputed from the raw panel; nothing is
taken from the reports.

Run: .venv\\Scripts\\python.exe tools\\cross_sectional\\_adversary_check.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("display.width", 220)
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "user_data/universe/raw_daily"
REBASE = -0.90


def load(qv_filter: bool):
    kept, dropped = {}, []
    for f in sorted(RAW.glob("*_1d.csv.gz")):
        sym = f.name.replace("_1d.csv.gz", "")
        d = pd.read_csv(f)
        d["date"] = pd.to_datetime(d["date"], format="%Y-%m-%d", errors="coerce")
        d = d.dropna(subset=["date", "close", "quote_volume"]).set_index("date").sort_index()
        d = d[~d.index.duplicated()]
        if qv_filter:
            d = d[d["quote_volume"] > 0]
        if (d["close"].pct_change() < REBASE).any():
            dropped.append(sym)
            continue
        kept[sym] = d
    px = pd.concat({k: v["close"] for k, v in kept.items()}, axis=1).sort_index()
    qv = pd.concat({k: v["quote_volume"] for k, v in kept.items()}, axis=1).sort_index()
    return px, qv, dropped


def ic_series(px: pd.DataFrame, form=1, hold=1, method="pearson") -> pd.Series:
    s = px.pct_change(periods=form, fill_method=None)
    fwd = px.pct_change(periods=hold, fill_method=None).shift(-hold)
    a, b = (s, fwd) if method == "pearson" else (s.rank(axis=1), fwd.rank(axis=1))
    pair = pd.concat([a.stack(), b.stack()], axis=1).dropna()
    return pair.groupby(level=0).corr().iloc[0::2, -1].dropna()


def acf_all(v: np.ndarray, max_lag: int = 30) -> np.ndarray:
    v = np.asarray(v, float)
    v = v - v.mean()
    den = float((v ** 2).sum())
    if den <= 0:
        return np.zeros(max_lag)
    return np.array([float((v[l:] * v[:-l]).sum() / den) for l in range(1, max_lag + 1)])


def iat_trunc(v, max_lag=30):
    a = acf_all(v, max_lag)
    tot = 0.0
    for rho in a:
        if rho <= 0:
            break
        tot += rho
    return 1.0 + 2 * tot


def iat_sum(v, max_lag=30):
    return float(1.0 + 2 * acf_all(v, max_lag).sum())


def tstat(ic):
    n = len(ic)
    return float(ic.mean() / ic.std(ddof=1) * math.sqrt(n)), n


def newey_west_t(v, lags=5):
    v = np.asarray(v, float)
    n = len(v)
    e = v - v.mean()
    g0 = float((e ** 2).sum()) / n
    var = g0
    for L in range(1, lags + 1):
        var += 2 * (1 - L / (lags + 1)) * float((e[L:] * e[:-L]).sum()) / n
    var = max(var, 1e-18)
    return float(v.mean() / math.sqrt(var / n))


def block_bootstrap_t(ic, block=10, reps=4000, seed=7):
    v = ic.to_numpy(float)
    n = len(v)
    nb = int(math.ceil(n / block))
    rng = np.random.default_rng(seed)
    means = np.empty(reps)
    for i in range(reps):
        starts = rng.integers(0, n - block + 1, nb)
        s = np.concatenate([v[s:s + block] for s in starts])[:n]
        means[i] = s.mean()
    return float(ic.mean() / means.std())


def decile_ls(px, form=1, hold=1):
    """Actual equal-weight long-short decile portfolio return, no IC shortcut."""
    s = px.pct_change(periods=form, fill_method=None)
    fwd = px.pct_change(periods=hold, fill_method=None).shift(-hold)
    out, detail = {}, []
    for d in px.index:
        a, b = s.loc[d], fwd.loc[d]
        m = a.notna() & b.notna()
        if m.sum() < 20:
            continue
        a, b = a[m], b[m]
        k = max(1, int(round(0.1 * len(a))))
        lo, hi = a.nsmallest(k).index, a.nlargest(k).index
        r = float(b[hi].mean() - b[lo].mean())     # buy losers, sell winners
        out[d] = r
        for nm in hi:
            detail.append((d, nm, float(b[nm]) / k))
        for nm in lo:
            detail.append((d, nm, -float(b[nm]) / k))
    return pd.Series(out).sort_index(), pd.DataFrame(detail, columns=["date", "sym", "c"])


def main():
    px, qv, dropped = load(qv_filter=False)
    px2, qv2, dropped2 = load(qv_filter=True)
    print("=" * 100)
    print("0. UNIVERSE CONSTRUCTION")
    print("=" * 100)
    print(f"  files on disk                 200")
    print(f"  kept by e4_power (no qv>0)    {px.shape[1]}")
    print(f"  kept with qv>0 filter         {px2.shape[1]}")
    print(f"  DROPPED by the -90% rule      {len(dropped)}  {dropped}")
    print(f"  panel span                    {px.index[0].date()} -> {px.index[-1].date()}")
    print(f"  calendar days in span         {len(px)}")

    # ---------------- 1. reproduce the headline
    print()
    print("=" * 100)
    print("1. REPRODUCE THE HEADLINE (200-name panel, form 1d / hold 1d)")
    print("=" * 100)
    ic_p = ic_series(px, 1, 1, "pearson")
    ic_s = ic_series(px, 1, 1, "spearman")
    t_p, n = tstat(ic_p)
    t_s, _ = tstat(ic_s)
    print(f"  CLAIM   IC -0.0195  t -3.79  n 2433  IAT 1.00")
    print(f"  CODE    IC {ic_p.mean():+.5f}  t {t_p:+.2f}  n {n}  "
          f"IAT(trunc) {iat_trunc(ic_p.to_numpy()):.2f}")
    print(f"  SPEARMAN IC {ic_s.mean():+.5f}  t {t_s:+.2f}   <-- the docs call it Spearman")
    print(f"  *** the shipped code computes PEARSON on raw returns; every report "
          f"calls it Spearman rank IC ***")

    # ---------------- 2. autocorrelation
    print()
    print("=" * 100)
    print("2. IS IAT = 1.00 REAL, OR AN ARTEFACT OF TRUNCATE-AT-FIRST-NEGATIVE?")
    print("=" * 100)
    a = acf_all(ic_p.to_numpy(), 30)
    print("  lag : " + " ".join(f"{i:>6d}" for i in range(1, 11)))
    print("  acf : " + " ".join(f"{v:>+6.3f}" for v in a[:10]))
    print("  lag : " + " ".join(f"{i:>6d}" for i in range(11, 21)))
    print("  acf : " + " ".join(f"{v:>+6.3f}" for v in a[10:20]))
    print(f"  IAT truncate-at-first-negative : {iat_trunc(ic_p.to_numpy()):.3f}   (what the report reports)")
    print(f"  IAT sum all 30 lags            : {iat_sum(ic_p.to_numpy()):.3f}")
    print(f"  IAT sum lags 1-5 (NW-ish)      : {1+2*a[:5].sum():.3f}")
    print(f"  Newey-West t (lags=5)          : {newey_west_t(ic_p.to_numpy()):+.2f}")
    print(f"  moving-block bootstrap t (b=10): {block_bootstrap_t(ic_p):+.2f}")

    # ---------------- 3. cross-section size
    print()
    print("=" * 100)
    print("3. HOW BIG IS THE CROSS-SECTION ACTUALLY?  (the docs say '200 perps')")
    print("=" * 100)
    cs = px.notna().sum(axis=1)
    byyear = cs.groupby(cs.index.year).agg(["min", "median", "max", "mean"])
    print(byyear.round(1).to_string())
    print(f"  mean cross-section over the whole panel : {cs.mean():.1f} names")
    print(f"  days with <  50 names alive             : {int((cs < 50).sum())}")
    print(f"  days with < 100 names alive             : {int((cs < 100).sum())}")

    # ---------------- 4. survivorship / stale
    print()
    print("=" * 100)
    print("4. SURVIVORSHIP AND STALE PRICES")
    print("=" * 100)
    last = px.apply(lambda s: s.last_valid_index())
    end = px.index[-1]
    dead = last[last < pd.Timestamp("2026-01-01")]
    print(f"  symbols whose data STOPS before 2026-01 (i.e. they are dead but still")
    print(f"  counted as 'currently listed'): {len(dead)}")
    print(f"  e.g. {list(dead.index[:12])}")
    print(f"  ...last data dates: {sorted(set(dead.dt.year))[:12]}")
    # trailing zero-return runs
    r = px.pct_change(fill_method=None)
    zero_run = (r == 0).cumsum()
    stale = {}
    for c in px.columns:
        s = zero_run[c]
        v = s[s.notna()]
        if len(v):
            stale[c] = int(v.iloc[-1]) if v.iloc[-1] == v.max() else 0
    st = pd.Series(stale).sort_values(ascending=False)
    print(f"  symbols ending in a >=30-day run of exactly 0.00% returns: "
          f"{int((st >= 30).sum())}  (median run {st.median():.0f}, max {st.max()})")
    print(f"  top: {st.head(6).to_dict()}")
    # how much of the panel is a frozen name
    print(f"  share of (name,day) cells that are a 0.00% return: "
          f"{(r == 0).sum().sum() / r.notna().sum().sum():.3%}")

    # ---------------- 5. outlier / concentration
    print()
    print("=" * 100)
    print("5. DOES A HANDFUL OF EXTreme NAMES DRIVE IT?")
    print("=" * 100)
    for name, icv in (("pearson", ic_p), ("spearman", ic_s)):
        print(f"  --- {name} ---")
        tt, nn = tstat(icv)
        print(f"    raw                        IC {icv.mean():+.5f}  t {tt:+.2f}")
    # winsorise returns at the 99.9/0.1 pct of the whole panel
    flat = r.stack().to_numpy(float)
    lo, hi = np.nanpercentile(flat, 0.1), np.nanpercentile(flat, 99.9)
    r_w = r.clip(lower=lo, upper=hi)
    fwd_w = r_w.shift(-1)
    pair = pd.concat([r_w.stack(), fwd_w.stack()], axis=1).dropna()
    ic_w = pair.groupby(level=0).corr().iloc[0::2, -1].dropna()
    tw, _ = tstat(ic_w)
    print(f"  returns winsorised at 0.1/99.9 pct (|r| max {lo:.2%}/{hi:.2%})")
    print(f"    pearson-after-winsor       IC {ic_w.mean():+.5f}  t {tw:+.2f}")
    # drop the single most extreme name-days entirely
    r2 = r.copy()
    s = r.stack()
    thr = s.abs().quantile(0.999)
    r2 = r.mask(r.abs() > thr)
    pair2 = pd.concat([r2.stack(), r2.shift(-1).stack()], axis=1).dropna()
    ic_x = pair2.groupby(level=0).corr().iloc[0::2, -1].dropna()
    tx, _ = tstat(ic_x)
    print(f"  drop the top 0.1% most extreme |return| name-days ({thr:.1%}):")
    print(f"    pearson                    IC {ic_x.mean():+.5f}  t {tx:+.2f}")
    # winsorised SPEARMAN
    pair3 = pd.concat([r_w.stack().rank(), fwd_w.stack().rank()], axis=1).dropna()
    ic_ws = pair3.groupby(level=0).corr().iloc[0::2, -1].dropna()
    tws, _ = tstat(ic_ws)
    print(f"    SPEARMAN after winsor      IC {ic_ws.mean():+.5f}  t {tws:+.2f}")

    # ---------------- 6. real portfolio
    print()
    print("=" * 100)
    print("6. THE ACTUAL DECILE LONG-SHORT PORTFOLIO, NOT IC x DEC x sigma")
    print("=" * 100)
    ls, det = decile_ls(px, 1, 1)
    print(f"  daily gross L/S   mean {ls.mean()*100:+.4f}%   t {newey_west_t(ls.to_numpy()):+.2f}"
          f"   n {len(ls)}   ann {ls.mean()*365*100:+.1f}%")
    contrib = det.groupby("sym")["c"].sum()
    contrib = contrib.sort_values(ascending=False)
    tot = contrib.sum()
    print(f"  total P&L contributed by all names: {tot:+.4f}")
    print(f"  top-5 names share of total P&L : {contrib.head(5).sum()/tot:.1%}")
    print(f"  top-20 names share            : {contrib.head(20).sum()/tot:.1%}")
    print(f"  positive-name fraction        : {(contrib > 0).mean():.1%}  of {len(contrib)} names")
    print(f"  top 5 contributors: {[f'{s} {v/tot:.1%}' for s, v in contrib.head(5).items()]}")
    # drop top-k names
    for k in (1, 3, 5, 10, 20):
        keep = [c for c in px.columns if c not in contrib.index[:k]]
        lsk, _ = decile_ls(px[keep], 1, 1)
        print(f"    drop top-{k:>2} names -> L/S mean {lsk.mean()*100:+.4f}%  "
              f"t {newey_west_t(lsk.to_numpy()):+.2f}")

    # ---------------- 7. liquid-50 and the dispersion question
    print()
    print("=" * 100)
    print("7. THE LIQUID-50 NULL, AND THE DISPERSION-SCALING ALTERNATIVE")
    print("=" * 100)
    med_qv = qv.median()
    uni50 = list(med_qv.nlargest(50).index)
    px50 = px[uni50]
    ic50_p = ic_series(px50, 1, 1, "pearson")
    ic50_s = ic_series(px50, 1, 1, "spearman")
    print(f"  CLAIM liquid-50: IC -0.0060  t -0.99")
    t50p, n50 = tstat(ic50_p)
    t50s, _ = tstat(ic50_s)
    print(f"  CODE  pearson : IC {ic50_p.mean():+.5f}  t {t50p:+.2f}  n {n50}")
    print(f"  CODE  spearman: IC {ic50_s.mean():+.5f}  t {t50s:+.2f}")
    ls50, _ = decile_ls(px50, 1, 1)
    print(f"  decile L/S liquid-50 : mean {ls50.mean()*100:+.4f}%  t {newey_west_t(ls50.to_numpy()):+.2f}")
    sig200 = px.pct_change(fill_method=None).std(axis=1).mean()
    sig50 = px50.pct_change(fill_method=None).std(axis=1).mean()
    print(f"  daily cross-sect sigma  200 {sig200*100:.2f}%   50 {sig50*100:.2f}%   "
          f"ratio {sig200/sig50:.3f}")
    print(f"  reported IC ratio 200/50 = {abs(ic_p.mean())/abs(ic50_p.mean()):.2f}")
    print(f"  reported gross ratio      = {abs(ic_p.mean())*sig200/(abs(ic50_p.mean())*sig50):.2f}")
    print(f"  actual portfolio ratio    = {abs(ls.mean())/abs(ls50.mean()):.2f}  "
          f"({ls.mean()*100:+.4f}% vs {ls50.mean()*100:+.4f}%)")
    print(f"  actual portfolio t 200 = {newey_west_t(ls.to_numpy()):+.2f}   "
          f"50 = {newey_west_t(ls50.to_numpy()):+.2f}")

    # ---------------- 8. market neutral?
    print()
    print("=" * 100)
    print("8. IS IT SURVIVING MARKET BETA, OR IS THE 'SIGNAL' THE MARKET?")
    print("=" * 100)
    mk = r.mean(axis=1)
    pair = pd.concat([r.stack(), r.shift(-1).stack()], axis=1).dropna()
    pair.columns = ["s", "f"]
    pair["m"] = mk.reindex(pair.index.get_level_values(0)).to_numpy()
    pair = pair.dropna()
    print(f"  corr(market return_t, market return_t+1) = "
          f"{np.corrcoef(pair['m'], pair['f'])[0,1]:+.4f}")
    res_s = []
    for d, g in pair.groupby(level=0):
        if len(g) < 20:
            continue
        x = g["s"].to_numpy() - g["m"].mean()
        y = g["f"].to_numpy() - g["m"].mean()
        if x.std() > 0 and y.std() > 0:
            res_s.append(np.corrcoef(x, y)[0, 1])
    ic_dm = pd.Series(res_s)
    tdm, _ = tstat(ic_dm)
    print(f"  DEMEANED (ex-market) cross-sectional IC: {ic_dm.mean():+.5f}  t {tdm:+.2f}")

    # ---------------- 9. subperiod
    print()
    print("=" * 100)
    print("9. STABILITY OVER TIME")
    print("=" * 100)
    for lbl, sl in (("2020-2021", ic_p.loc["2020":"2021"]),
                    ("2022-2023", ic_p.loc["2022":"2023"]),
                    ("2024", ic_p.loc["2024"]),
                    ("2025-2026", ic_p.loc["2025":"2026"])):
        if len(sl) < 30:
            print(f"  {lbl:10s} n={len(sl)}  (too few)")
            continue
        tt, nn = tstat(sl)
        print(f"  {lbl:10s} n {nn:5d}  IC {sl.mean():+.5f}  t {tt:+.2f}")

    # ---------------- 10. the Bonferroni arithmetic
    print()
    print("=" * 100)
    print("10. THE REPORTED p-VALUE 6.7e-4")
    print("=" * 100)
    from math import erfc, sqrt
    z = abs(t_p)
    p2 = erfc(z / sqrt(2))
    print(f"  |t| {z:.2f}  ->  two-sided normal p {p2:.3e}  x9 = {p2*9:.3e}")
    print(f"                     one-sided normal p {p2/2:.3e}  x9 = {p2/2*9:.3e}")
    print(f"  REPORTED: 6.7e-4  == one-sided p x 9 = {p2/2*9:.2e}")
    print(f"  -> the report used a ONE-SIDED p on a post-hoc-selected best-of-9.")
    print(f"  -> the two-sided Bonferroni number is {p2*9:.2e}, ~2x the reported value.")

    print()
    print("=" * 100)
    print("DONE")
    print("=" * 100)


if __name__ == "__main__":
    main()
