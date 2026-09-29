"""Part 2: why does the IC say -0.0195 (t -3.79) but the decile portfolio say
nothing, and why does liquid-50 flip sign? Isolate stale/frozen names, extreme
returns, and check whether the liquid-50 momentum is real."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("display.width", 220)
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "user_data/universe/raw_daily"


def load():
    kept = {}
    for f in sorted(RAW.glob("*_1d.csv.gz")):
        sym = f.name.replace("_1d.csv.gz", "")
        d = pd.read_csv(f)
        d["date"] = pd.to_datetime(d["date"], format="%Y-%m-%d", errors="coerce")
        d = d.dropna(subset=["date", "close", "quote_volume"]).set_index("date").sort_index()
        d = d[~d.index.duplicated()]
        kept[sym] = d
    px = pd.concat({k: v["close"] for k, v in kept.items()}, axis=1).sort_index()
    qv = pd.concat({k: v["quote_volume"] for k, v in kept.items()}, axis=1).sort_index()
    return px, qv


def nw_t(v, lags=5):
    v = np.asarray(v, float)
    n = len(v); e = v - v.mean()
    g0 = float((e ** 2).sum()) / n; var = g0
    for L in range(1, lags + 1):
        var += 2 * (1 - L / (lags + 1)) * float((e[L:] * e[:-L]).sum()) / n
    return float(v.mean() / math.sqrt(max(var, 1e-18) / n))


def dec(px, k_frac=0.1, sign=-1):
    """sign=-1 : reversal (long the past losers). sign=+1 : momentum."""
    s = px.pct_change(fill_method=None)
    fwd = s.shift(-1)
    out, det = {}, []
    for d in px.index:
        a, b = s.loc[d], fwd.loc[d]
        m = a.notna() & b.notna()
        if m.sum() < 20:
            continue
        a, b = a[m], b[m]
        k = max(1, int(round(k_frac * len(a))))
        lo, hi = a.nsmallest(k).index, a.nlargest(k).index
        if sign < 0:
            pnl = float(b[lo].mean() - b[hi].mean())
        else:
            pnl = float(b[hi].mean() - b[lo].mean())
        out[d] = pnl
        src, tgt = (lo, hi) if sign < 0 else (hi, lo)
        for nm in tgt:
            det.append((d, nm, float(b[nm]) / k))
    return pd.Series(out).sort_index(), pd.DataFrame(det, columns=["date", "sym", "c"])


def main():
    px, qv = load()
    r = px.pct_change(fill_method=None)

    print("=" * 100)
    print("A. STALE-PRICE MASS")
    print("=" * 100)
    s = r.stack()
    nz = s[s != 0].abs()
    print(f"  cells total                 {s.notna().sum():,}")
    print(f"  cells exactly 0.00%         {int((s == 0).sum()):,}  "
          f"({(s == 0).sum()/s.notna().sum():.2%})")
    print(f"  |return| percentiles among NON-ZERO cells:")
    for q in (0.5, 0.9, 0.99, 0.999, 0.9999, 1.0):
        print(f"    p{q*100:>7.3f}   {np.percentile(nz.to_numpy(), q)*100:>8.2f}%")
    print(f"  |return| >  50%  {int((nz > .50).sum()):,}")
    print(f"  |return| > 100%  {int((nz > 1.0).sum()):,}")
    print(f"  |return| > 200%  {int((nz > 2.0).sum()):,}")
    big = s.abs().nlargest(12)
    print(f"  the 12 largest single-day moves in the panel:")
    for (d, c), v in big.items():
        print(f"    {d.date()}  {c:<12} {v*100:>10.1f}%")

    # frozen names
    zr = (r == 0).cumsum()
    runs = {}
    for c in px.columns:
        v = zr[c].dropna()
        runs[c] = int(v.iloc[-1]) if len(v) and v.iloc[-1] == v.max() else 0
    frozen = pd.Series(runs)
    frozen = frozen[frozen >= 30].sort_values(ascending=False)
    print(f"\n  symbols ending in a >=30-day frozen run (price never moved again): "
          f"{len(frozen)}")
    print(f"    {frozen.head(20).to_dict()}")
    # their last real move
    print(f"  share of the 200 panel that is frozen at the end: {len(frozen)/200:.1%}")

    print()
    print("=" * 100)
    print("B. REVERSAL PORTFOLIO: STALE NAMES IN vs OUT")
    print("=" * 100)
    ls_all, det_all = dec(px, sign=-1)
    print(f"  all 200 names            n {len(ls_all):5d}  mean {ls_all.mean()*100:+.4f}%/day  "
          f"t {nw_t(ls_all.to_numpy()):+.2f}")
    clean = [c for c in px.columns if c not in frozen.index]
    ls_cl, _ = dec(px[clean], sign=-1)
    print(f"  200 minus {len(frozen)} frozen  n {len(ls_cl):5d}  mean {ls_cl.mean()*100:+.4f}%/day  "
          f"t {nw_t(ls_cl.to_numpy()):+.2f}")

    print()
    print("=" * 100)
    print("C. THE IC vs THE PORTFOLIO, SIDE BY SIDE (200 names, reversal)")
    print("=" * 100)
    def icser(p, method="pearson"):
        s_ = p.pct_change(fill_method=None)
        f = s_.shift(-1)
        a, b = (s_, f) if method == "pearson" else (s_.rank(axis=1), f.rank(axis=1))
        pair = pd.concat([a.stack(), b.stack()], axis=1).dropna()
        return pair.groupby(level=0).corr().iloc[0::2, -1].dropna()
    for lbl, p in (("all 200", px), (f"ex-frozen ({len(clean)})", px[clean])):
        ip, isp = icser(p), icser(p, "spearman")
        lsp, _ = dec(p, sign=-1)
        sig = p.pct_change(fill_method=None).std(axis=1).mean()
        print(f"  {lbl}")
        print(f"    Pearson  IC {ip.mean():+.5f}  t {ip.mean()/ip.std()*math.sqrt(len(ip)):+6.2f}"
              f"   -> implied decile spread {3.51*abs(ip.mean())*sig*100:.4f}%/day")
        print(f"    Spearman IC {isp.mean():+.5f}  t {isp.mean()/isp.std()*math.sqrt(len(isp)):+6.2f}")
        print(f"    ACTUAL decile L/S     {lsp.mean()*100:+.4f}%/day  t {nw_t(lsp.to_numpy()):+.2f}"
              f"   ann {lsp.mean()*365*100:+.1f}%")
        print(f"    ratio implied/actual  {3.51*abs(ip.mean())*sig/abs(lsp.mean()):.1f}x")
        # winsorise
        w = r.clip(-0.30, 0.30)
        f = w.shift(-1); s_ = w
        pair = pd.concat([s_.stack(), f.stack()], axis=1).dropna()
        icw = pair.groupby(level=0).corr().iloc[0::2, -1].dropna()
        pw = p.copy()
        ls_w, _ = dec(pw, sign=-1)
        print(f"    [sanity] winsorised |r|<=30% Pearson IC {icw.mean():+.5f} "
              f"t {icw.mean()/icw.std()*math.sqrt(len(icw)):+.2f}")

    print()
    print("=" * 100)
    print("D. THE LIQUID-50: reversal AND momentum, plus the report's claimed -0.0060")
    print("=" * 100)
    med = qv.median()
    u50 = list(med.nlargest(50).index)
    p50 = px[u50]
    print(f"  is any of the top-50 frozen? {sorted(set(u50) & set(frozen.index))}")
    ip, isp = icser(p50), icser(p50, "spearman")
    print(f"    Pearson  IC {ip.mean():+.5f}  t {ip.mean()/ip.std()*math.sqrt(len(ip)):+.2f}  "
          f"n {len(ip)}   (REPORT CLAIMS -0.0060 / -0.99)")
    print(f"    Spearman IC {isp.mean():+.5f}  t {isp.mean()/isp.std()*math.sqrt(len(isp)):+.2f}")
    for lbl, sg in (("REVERSAL", -1), ("MOMENTUM", +1)):
        lsp, detp = dec(p50, sign=sg)
        print(f"    {lbl:<9} decile L/S {lsp.mean()*100:+.4f}%/day  t {nw_t(lsp.to_numpy()):+.2f}"
              f"   ann {lsp.mean()*365*100:+.1f}%")
    # concentration on the liquid 50
    lsp, detp = dec(p50, sign=-1)
    c = detp.groupby("sym")["c"].sum().sort_values(ascending=False)
    tot = c.sum()
    print(f"    reversal P&L by name: total {tot:+.4f}  top-1 share {c.iloc[0]/tot:.1%}  "
          f"top-5 {c.head(5).sum()/tot:.1%}  pos frac {(c>0).mean():.1%}")
    for k in (1, 3, 5, 10):
        keep = [x for x in p50.columns if x not in c.index[:k]]
        lsk, _ = dec(p50[keep], sign=-1)
        print(f"      drop top-{k:>2} -> {lsk.mean()*100:+.4f}%/day  t {nw_t(lsk.to_numpy()):+.2f}")

    print()
    print("=" * 100)
    print("E. WHAT DOES THE SHIPPED e5 CODE ACTUALLY DO? (e5_liquid.py line 80-85)")
    print("=" * 100)
    rets = p50.pct_change(fill_method=None)
    fwd = rets.shift(-1)
    s = rets.shift(1)
    pair = pd.concat([s.stack(), fwd.stack()], axis=1).dropna()
    ic5 = pair.groupby(level=0).corr().iloc[0::2, -1].dropna()
    print(f"  e5 signal = rets.shift(1) at t, target = rets.shift(-1) at t")
    print(f"  => corr(r_(t-1), r_(t+1))   [SKIPS r_t!]")
    print(f"  IC {ic5.mean():+.5f}  t {ic5.mean()/ic5.std()*math.sqrt(len(ic5)):+.2f}  n {len(ic5)}")
    print(f"  compare corr(r_t, r_(t+1))  IC {ip.mean():+.5f}  t {ip.mean()/ip.std()*math.sqrt(len(ip)):+.2f}")
    print(f"  compare corr(r_(t-1), r_(t+2)) (4-day) :")
    f4 = rets.shift(-2)
    pair4 = pd.concat([s.stack(), f4.stack()], axis=1).dropna()
    ic4 = pair4.groupby(level=0).corr().iloc[0::2, -1].dropna()
    print(f"    IC {ic4.mean():+.5f}  t {ic4.mean()/ic4.std()*math.sqrt(len(ic4)):+.2f}  n {len(ic4)}")
    print(f"  autcorr of daily market return: {rets.mean(axis=1).autocorr():+.4f}")

    print()
    print("=" * 100)
    print("F. e4_power.py: does IT have the same off-by-one? (form 1 / hold 1)")
    print("=" * 100)
    s_ = px.pct_change(periods=1, fill_method=None)
    fwd_ = px.pct_change(periods=1, fill_method=None).shift(-1)
    print(f"  signal at t = pct_change(1) at t = r_t        (NO shift)  -> correct")
    pair = pd.concat([s_.stack(), fwd_.stack()], axis=1).dropna()
    ice = pair.groupby(level=0).corr().iloc[0::2, -1].dropna()
    print(f"  e4_power IC {ice.mean():+.5f}  t {ice.mean()/ice.std()*math.sqrt(len(ice)):+.2f} "
          f"n {len(ice)}   (REPORT CLAIMS -0.0195 / -3.79 / 2433)")
    print(f"  e5      IC {ic5.mean():+.5f}  t {ic5.mean()/ic5.std()*math.sqrt(len(ic5)):+.2f} n {len(ic5)}")
    print(f"  --> e4_power and e5_liquid do NOT measure the same thing at form=hold=1.")


if __name__ == "__main__":
    main()
