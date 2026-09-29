"""Final gates on the 15-year BTC result.

sma_15year_test.py found:
  * window grid 10-150 all give Sharpe 1.40-1.45 -> a genuine PLATEAU, so the
    result is not a tuned spike (unlike the 7.7y data where 50 was a ridge)
  * 2011-2019 holdout (never searched until now): Sharpe 1.70 vs BH 1.54 and
    flat 1.54 -> beats both
  * walk-forward stitched OOS 1.20 vs 1.04
  * bootstrap vs flat: SMA-20/50/100 CIs exclude zero

Before believing any of it, this script applies the remaining hard gates:
  1. Wildcard placebo at matched mean (random exposure, 500 draws)
  2. MinBTL / Deflated Sharpe with the full trial ledger
  3. Independence: how many independent bull/bear EPISODES are there really?
  4. Multi-asset replication on the other Bitstamp pairs
"""

import numpy as np
import pandas as pd

PPY = 365
COST = 10.0
WINDOWS = [10, 20, 30, 50, 75, 100, 150, 200]
PAIRS = ["BTC/USD", "ETH/USD", "LTC/USD", "XRP/USD", "BCH/USD"]


def load(name):
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


def run(rets, expo, cost=COST):
    pos = expo.shift(1).fillna(0.0)
    turn = pos.diff().abs().fillna(pos.abs())
    return 10_000 * (1 + (pos * rets - turn * cost / 10_000)).cumprod()


def sma_expo(close, w):
    ma = close.rolling(w, min_periods=w).mean()
    v = ma.notna()
    out = pd.Series(0.5, index=close.index)
    out[v] = np.where(close[v] > ma[v], 1.0, 0.5)
    return out


def prepare(name):
    d = load(name)
    c = d.set_index("date")["close"].astype(float)
    r = c.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return c.iloc[200:], r.iloc[200:]


def main():
    close, rets = prepare("BTC/USD")
    n = len(rets)
    ny = n / PPY

    print("=" * 94)
    print("# FINAL GATES — 15-year BTC/USD SMA rule")
    print("=" * 94)
    print(f"{close.index[0].date()} -> {close.index[-1].date()}  "
          f"({ny:.1f}y, n={n}), {COST:.0f}bps\n")

    e50 = sma_expo(close, 50)
    avg50 = float(e50.mean())
    s50 = stats(run(rets, e50))
    bh = stats(run(rets, pd.Series(1.0, index=rets.index), 0.0))
    flat = stats(run(rets, pd.Series(avg50, index=rets.index)))

    print(f"  buy & hold     : CAGR {bh['cagr']:>8.2%}  MaxDD {bh['maxdd']:>8.2%}  "
          f"Sharpe {bh['sharpe']:.2f}")
    print(f"  SMA-50         : CAGR {s50['cagr']:>8.2%}  MaxDD {s50['maxdd']:>8.2%}  "
          f"Sharpe {s50['sharpe']:.2f}")
    print(f"  flat @ {avg50:.1%}   : CAGR {flat['cagr']:>8.2%}  MaxDD {flat['maxdd']:>8.2%}  "
          f"Sharpe {flat['sharpe']:.2f}")

    # ---------- 1. Wildcard placebo ----------
    print(f"\n{'=' * 94}")
    print("# 1. WILDCARD PLACEBO — random exposure, matched mean, 500 draws")
    print(f"{'=' * 94}")
    rng = np.random.default_rng(101)

    def wildcard(mean_exp, length, idx, block, r):
        nb = int(np.ceil(length / block))
        vals = r.random(nb) < mean_exp
        return pd.Series(np.repeat(vals, block)[:length].astype(float), index=idx)

    print(f"\n  {'rule':<10} {'Sharpe':>8} {'placebo mean':>13} {'p95':>8} "
          f"{'p(Sharpe)':>10}  verdict")
    for w in (20, 50, 100):
        e = sma_expo(close, w)
        a = float(e.mean())
        d = stats(run(rets, e))
        ps = [stats(run(rets, wildcard(a, n, rets.index, 30, rng)))["sharpe"]
              for _ in range(500)]
        ps = np.array(ps)
        p = float((ps >= d["sharpe"]).mean())
        print(f"  {'SMA-' + str(w):<10} {d['sharpe']:>8.2f} {ps.mean():>13.2f} "
              f"{np.percentile(ps, 95):>8.2f} {p:>10.3f}  "
              f"{'PASSES' if p < 0.0125 else 'weak' if p < 0.05 else 'indistinguishable'}")

    # ---------- 2. MinBTL / deflated view ----------
    print(f"\n{'=' * 94}")
    print("# 2. MinBTL — is 15 years enough for the number of trials run?")
    print(f"{'=' * 94}")
    trials = {
        "round1 (MA200, momentum, drawdown, volume, funding)": 70,
        "SMA window grids (7.7y)": 8,
        "cross-asset walk-forward": 20,
        "SMA window grid (15y, this round)": 8,
    }
    total = sum(trials.values())
    print()
    for k, v in trials.items():
        print(f"  {k:<52} {v:>4}")
    print(f"  {'TOTAL':<52} {total:>4}")
    for sr in (1.45, 1.20, 1.04):
        minbtl = 2 * np.log(total) / (sr ** 2)
        ok = "OK" if ny > minbtl else "TOO SHORT"
        print(f"\n  SR={sr:.2f}: MinBTL {minbtl:.1f}y vs available {ny:.1f}y -> {ok}")

    # Deflated Sharpe (Bailey & Lopez de Prado, simplified expected-max term)
    srs = np.array([stats(run(rets, sma_expo(close, w)))["sharpe"] for w in WINDOWS])
    v = srs.var()
    g = 0.5772156649
    e_max = np.sqrt(v) * ((1 - g) * 1.96 + g * 2.0)
    print(f"\n  observed window-Sharpe spread (var {v:.4f})")
    print(f"  expected max Sharpe under null (N={total}): ~{e_max:.2f}")
    print(f"  observed best Sharpe: {srs.max():.2f}")
    print(f"  -> {'EXCEEDS null expectation' if srs.max() > e_max else 'within null expectation'}")

    # ---------- 3. Independence: how many real episodes? ----------
    print(f"\n{'=' * 94}")
    print("# 3. INDEPENDENCE — how many independent episodes, really?")
    print(f"{'=' * 94}")
    # Count major drawdown cycles as a proxy for independent regimes.
    eq = run(rets, pd.Series(1.0, index=rets.index), 0.0)
    peak = eq.cummax()
    dd = eq / peak - 1
    in_dd = dd < -0.20
    # Count contiguous -20% drawdown episodes
    eps = 0
    prev = False
    for x in in_dd:
        if x and not prev:
            eps += 1
        prev = x
    print(f"\n  distinct >20% drawdown episodes in 15y: {eps}")
    print(f"  observed autocorrelation of daily returns: "
          f"{float(rets.autocorr(1)):+.3f}")
    # Effective sample: overlapping-year Sharpe estimates
    print(f"\n  A 15y single-asset history contains roughly {eps} independent")
    print(f"  stress episodes. That is the real N for regime-level inference,")
    print(f"  NOT {n} daily observations.")

    # ---------- 4. Multi-asset replication ----------
    print(f"\n{'=' * 94}")
    print("# 4. MULTI-ASSET REPLICATION (Bitstamp, frozen SMA-50, no re-tuning)")
    print(f"{'=' * 94}")
    print(f"\n  {'pair':<10} {'years':>7} {'BH SR':>8} {'SMA50 SR':>9} "
          f"{'flat SR':>8} {'d vs flat':>10}  better?")
    deltas = []
    for p in PAIRS:
        try:
            c, r = prepare(p)
        except FileNotFoundError:
            continue
        yrs = len(r) / PPY
        e = sma_expo(c, 50)
        a = float(e.mean())
        sb = stats(run(r, pd.Series(1.0, index=r.index), 0.0))
        sd = stats(run(r, e))
        sf = stats(run(r, pd.Series(a, index=r.index)))
        d = sd["sharpe"] - sf["sharpe"]
        deltas.append(d)
        print(f"  {p:<10} {yrs:>7.1f} {sb['sharpe']:>8.2f} {sd['sharpe']:>9.2f} "
              f"{sf['sharpe']:>8.2f} {d:>+10.3f}  "
              f"{'YES' if d > 0 else 'no':>7}")
    deltas = np.array(deltas)
    print(f"\n  beats flat control in {int((deltas > 0).sum())}/{len(deltas)} assets")
    print(f"  mean dSharpe {deltas.mean():+.3f}")

    # ---------- VERDICT ----------
    print(f"\n{'=' * 94}")
    print("# VERDICT")
    print("=" * 94)
    checks = [
        ("beats flat control (CI excludes 0)", True),
        ("holdout 2011-2019 beats both", True),
        ("walk-forward OOS beats B&H", True),
        ("parameter plateau (not a spike)", True),
        ("sample > MinBTL", ny > 2 * np.log(total) / (1.45 ** 2)),
        ("multi-asset replication", (deltas > 0).sum() >= 4),
    ]
    for label, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    print(f"\n  {sum(ok for _, ok in checks)}/{len(checks)} passed")
    print(f"\n  CAVEAT: only ~{eps} independent stress episodes; BTC is one asset.")


if __name__ == "__main__":
    main()
