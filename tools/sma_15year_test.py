"""SMA test on 15 years of BTC — the statistical-power fix.

Round 1 ended with SMA-50 rejected because:
  * anchored OOS failed
  * cross-asset replication collapsed to p=0.142 once the panel's ~2.6
    effective independent bets were accounted for
  * MinBTL demanded 12.8 years; we had 7.7

Two things change here:
  1. BTC/USD (Bitstamp) runs 2011-08-18 -> 2026-09-19 = 15.1 years, so
     SE(Sharpe) falls from 0.36 to 0.257. That is the only real cure for power
     (Lo 2002: SE ~ 1/sqrt(YEARS), independent of sampling frequency).
  2. 2011-2019 was NEVER searched in this project. It is a true holdout.

An honest caveat stated up front: the SMA-50 candidate itself was selected on
the 2019+ Binance data. The holdout can therefore confirm or refute the
*parameter choice*, but the search over windows still happened on other data.
"""

import numpy as np
import pandas as pd

PPY = 365
COST = 10.0
WINDOWS = [10, 20, 30, 50, 75, 100, 150, 200]


def load(name: str) -> pd.DataFrame:
    p = f"user_data/data/bitstamp/{name.replace('/', '_')}-1d.feather"
    d = pd.read_feather(p).sort_values("date").drop_duplicates("date")
    return d.reset_index(drop=True)


def max_dd(eq):
    return float((eq / eq.cummax() - 1.0).min())


def cagr(eq):
    y = len(eq) / PPY
    return float((eq.iloc[-1] / eq.iloc[0]) ** (1 / y) - 1) if y > 0 else np.nan


def sharpe(r):
    sd = r.std()
    return float(r.mean() / sd * np.sqrt(PPY)) if sd and sd > 0 else np.nan


def stats(eq):
    return {"cagr": cagr(eq), "maxdd": max_dd(eq),
            "sharpe": sharpe(eq.pct_change().dropna())}


def run(rets, expo, cost=COST, initial=10_000.0):
    pos = expo.shift(1).fillna(0.0)
    turn = pos.diff().abs().fillna(pos.abs())
    return initial * (1 + (pos * rets - turn * cost / 10_000.0)).cumprod()


def sma_expo(close: pd.Series, w: int) -> pd.Series:
    ma = close.rolling(w, min_periods=w).mean()
    v = ma.notna()
    out = pd.Series(0.5, index=close.index)
    out[v] = np.where(close[v] > ma[v], 1.0, 0.5)
    return out


def block_idx(n, block, rng):
    nb = int(np.ceil(n / block))
    st = rng.integers(0, n, nb)
    return np.concatenate([(np.arange(s, s + block) % n) for s in st])[:n]


def shp(x):
    sd = x.std()
    return float(x.mean() / sd * np.sqrt(PPY)) if sd > 0 else 0.0


def main():
    d = load("BTC/USD")
    close = d.set_index("date")["close"].astype(float)
    rets = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)

    # Drop warm-up (200-day MA needs history) so stats start clean.
    start = 200
    close = close.iloc[start:]
    rets = rets.iloc[start:]
    n_years = len(rets) / PPY
    se = 1 / np.sqrt(n_years)

    print("=" * 94)
    print("# SMA ON 15 YEARS OF BTC/USD (Bitstamp) — the power fix")
    print("=" * 94)
    print(f"window {close.index[0].date()} -> {close.index[-1].date()} "
          f"({n_years:.1f}y)")
    print(f"SE(annualised Sharpe) = 1/sqrt({n_years:.1f}) = {se:.3f}  "
          f"(was 0.36 on 7.7y)\n")

    bh = run(rets, pd.Series(1.0, index=rets.index), 0.0)
    bhs = stats(bh)
    print(f"buy & hold: CAGR {bhs['cagr']:.2%}  MaxDD {bhs['maxdd']:.2%}  "
          f"Sharpe {bhs['sharpe']:.2f}")

    print(f"\n{'=' * 94}")
    print("# WINDOW GRID on the FULL 15 years")
    print(f"{'=' * 94}")
    print(f"\n  {'window':<9} {'avgExp':>7} {'CAGR':>9} {'MaxDD':>10} {'Sharpe':>8} "
          f"{'vs flat':>9}")
    full = {}
    for w in WINDOWS:
        e = sma_expo(close, w)
        avg = float(e.mean())
        s = stats(run(rets, e))
        f = stats(run(rets, pd.Series(avg, index=rets.index)))
        full[w] = (e, s, f, avg)
        flag = "  <-- candidate" if w == 50 else ""
        print(f"  {w:<9} {avg:>6.1%} {s['cagr']:>9.2%} {s['maxdd']:>10.2%} "
              f"{s['sharpe']:>8.2f} {s['sharpe'] - f['sharpe']:>+9.3f}{flag}")

    # ---------------- HOLD OUT 2011-2019 ----------------
    print(f"\n{'=' * 94}")
    print("# TRUE HOLDOUT — 2011-2019 was NEVER searched in this project")
    print(f"{'=' * 94}")
    cut = pd.Timestamp("2019-01-01", tz="UTC")
    hold = close.index < cut
    later = ~hold

    print(f"\n  holdout period : {close.index[hold][0].date()} -> "
          f"{close.index[hold][-1].date()}  ({hold.sum()} days, "
          f"{hold.sum()/PPY:.1f}y)")
    print(f"  later period   : {close.index[later][0].date()} -> "
          f"{close.index[later][-1].date()}  ({later.sum()} days, "
          f"{later.sum()/PPY:.1f}y)")

    print(f"\n  {'rule':<22} {'holdout CAGR':>13} {'holdout MaxDD':>14} "
          f"{'holdout Sharpe':>15}")
    for w in (50, 100, 200):
        e = full[w][0]
        s = stats(run(rets[hold], e[hold]))
        b = stats(run(rets[hold], pd.Series(1.0, index=rets[hold].index), 0.0))
        avg_h = float(e[hold].mean())
        fl = stats(run(rets[hold], pd.Series(avg_h, index=rets[hold].index)))
        print(f"  {'SMA-' + str(w):<22} {s['cagr']:>13.2%} {s['maxdd']:>14.2%} "
              f"{s['sharpe']:>15.2f}")
        print(f"  {'  buy & hold':<22} {b['cagr']:>13.2%} {b['maxdd']:>14.2%} "
              f"{b['sharpe']:>15.2f}")
        print(f"  {'  flat same avg':<22} {fl['cagr']:>13.2%} {fl['maxdd']:>14.2%} "
              f"{fl['sharpe']:>15.2f}   "
              f"[{'BEATS both' if s['sharpe'] > max(b['sharpe'], fl['sharpe']) else 'fails'}]")
        print()

    # ---------------- The parameter was chosen on 2019+ ----------------
    print(f"{'=' * 94}")
    print("# CRITICAL: does the 2019+ chosen window (50) hold up OUT of that era?")
    print(f"{'=' * 94}")
    best_later = max(WINDOWS, key=lambda w: stats(run(rets[later], full[w][0][later]))["sharpe"])
    print(f"\n  best window on 2019+ (in-sample): SMA-{best_later}")
    e = full[50][0]
    s_h = stats(run(rets[hold], e[hold]))
    b_h = stats(run(rets[hold], pd.Series(1.0, index=rets[hold].index), 0.0))
    print(f"  SMA-50 on the 2011-2019 holdout: Sharpe {s_h['sharpe']:.2f} "
          f"vs buy & hold {b_h['sharpe']:.2f}")
    print(f"  -> {'HOLDS UP' if s_h['sharpe'] > b_h['sharpe'] else 'FAILS on holdout'}")

    # ---------------- Walk-forward on 15 years ----------------
    print(f"\n{'=' * 94}")
    print("# WALK-FORWARD on 15 years (pick window in-sample, trade OOS)")
    print(f"{'=' * 94}")
    n = len(rets)
    nf = 8
    fold = n // (nf + 1)
    oos_r, oos_b = [], []
    print(f"\n  {'fold':<5} {'train ends':<12} {'test':<24} {'chosen':>7} "
          f"{'IS SR':>7} {'OOS SR':>7}")
    for k in range(nf):
        tr_end = fold * (k + 1)
        te_end = min(tr_end + fold, n)
        if te_end - tr_end < 40:
            continue
        trm = np.zeros(n, bool); trm[:tr_end] = True
        best_w, best_sr = None, -np.inf
        for w in WINDOWS:
            sr = stats(run(rets[trm], full[w][0][trm]))["sharpe"]
            if sr > best_sr:
                best_w, best_sr = w, sr
        sl = slice(tr_end, te_end)
        e = full[best_w][0]
        seg = run(rets[sl], e[sl])
        oos_r.append(seg.pct_change().dropna())
        oos_b.append(rets[sl])
        print(f"  {k+1:<5} {str(close.index[tr_end-1].date()):<12} "
              f"{str(close.index[tr_end].date()) + '..' + str(close.index[te_end-1].date()):<24} "
              f"{best_w:>7} {best_sr:>7.2f} {stats(seg)['sharpe']:>7.2f}")

    rr = pd.concat(oos_r); rb = pd.concat(oos_b)
    sr_r = float(rr.mean() / rr.std() * np.sqrt(PPY))
    sr_b = float(rb.mean() / rb.std() * np.sqrt(PPY))
    print(f"\n  stitched OOS Sharpe: rule {sr_r:.2f}  vs  buy & hold {sr_b:.2f}")
    print(f"  -> {'OOS BEATS buy & hold' if sr_r > sr_b else 'OOS FAILS'}")

    # ---------------- Bootstrap vs flat on full sample ----------------
    print(f"\n{'=' * 94}")
    print("# PAIRED BOOTSTRAP vs FLAT CONTROL (full 15y), 5000 draws")
    print(f"{'=' * 94}")
    rng = np.random.default_rng(97)
    print(f"\n  {'window':<9} {'dSharpe':>9} {'95% CI':>20} {'p(<=0)':>8}  verdict")
    for w in (20, 50, 100, 200):
        e, s, f, avg = full[w]
        p_ = e.shift(1).fillna(0.0)
        t_ = p_.diff().abs().fillna(p_.abs())
        r_ = (p_ * rets - t_ * COST / 10_000).to_numpy()
        rf = (avg * rets).to_numpy()
        pt = shp(r_) - shp(rf)
        b = np.array([shp(r_[i]) - shp(rf[i])
                      for i in (block_idx(n, 20, rng) for _ in range(5000))])
        lo, hi = np.percentile(b, [2.5, 97.5])
        print(f"  {'SMA-' + str(w):<9} {pt:>+9.3f} {f'[{lo:+.2f}, {hi:+.2f}]':>20} "
              f"{float((b <= 0).mean()):>8.3f}  "
              f"{'SIGNIFICANT' if lo > 0 else 'not significant'}")

    # ---------------- Sub-period: the three big regimes ----------------
    print(f"\n{'=' * 94}")
    print("# SUB-PERIOD STABILITY across 15 years (SMA-50)")
    print(f"{'=' * 94}")
    e50 = full[50][0]
    eq_r = run(rets, e50)
    eq_b = run(rets, pd.Series(1.0, index=rets.index), 0.0)
    print(f"\n  {'year':<7} {'BH CAGR':>10} {'rule CAGR':>11} {'BH SR':>8} "
          f"{'rule SR':>9}  better?")
    wins = tot = 0
    for y in sorted(set(eq_r.index.year)):
        m = eq_r.index.year == y
        if m.sum() < 60:
            continue
        sb = stats(eq_b[m]); sr = stats(eq_r[m])
        tot += 1; wins += sr["sharpe"] > sb["sharpe"]
        print(f"  {y:<7} {sb['cagr']:>10.2%} {sr['cagr']:>11.2%} "
              f"{sb['sharpe']:>8.2f} {sr['sharpe']:>9.2f}  "
              f"{'YES' if sr['sharpe'] > sb['sharpe'] else 'no'}")
    print(f"\n  rule better in {wins}/{tot} years")


if __name__ == "__main__":
    main()
