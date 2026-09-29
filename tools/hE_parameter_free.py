"""PRE-REGISTRATION — H-E and H-F: removing the un-selectable parameter

Written BEFORE looking at results.

--------------------------------------------------------------------------
WHERE THIS COMES FROM
--------------------------------------------------------------------------
Round 7 established, with 6 independent splits:

  * the SMA edge is TEMPORALLY STABLE for a fixed window
    (jackknife +0.154..+0.237 on BTC, CI excludes 0)
  * but the WINDOW CANNOT BE CHOSEN out-of-sample
    (BTC: the in-sample-best window produced a positive OOS edge in 0 of 6 splits;
     train-best test edge -0.172 vs oracle +0.152)

So the binding problem is the SELECTION STEP, not the signal. That suggests two
structurally different fixes, both testable.

--------------------------------------------------------------------------
H-E: ENSEMBLE (no selection at all)
--------------------------------------------------------------------------
Instead of choosing one window, average the exposure across ALL windows.

  exposure_t = mean over w in W of [ 1.0 if close_t > SMA_w(close_t) else 0.5 ]

There is no selection step, so nothing can be overfit by selection. The claim is
that averaging is not a parameter choice but a way of REMOVING one.

Predictions (fixed now):
  E1. The ensemble is temporally stable: leave-one-year-out edge stays > 0.
  E2. The ensemble shows a POSITIVE out-of-sample edge on a clean split
      (train <= 2024-12-31, test >= 2025-01-01), unlike the train-selected window.
  E3. The ensemble's OOS edge exceeds the *mean* OOS edge of the individual
      windows (variance reduction), i.e. it beats "pick one at random".
  E4. The ensemble beats a matched-exposure FLAT control out-of-sample.

--------------------------------------------------------------------------
H-F: TRULY PARAMETER-FREE (expanding mean)
--------------------------------------------------------------------------
  exposure_t = 1.0 if close_t > mean(close_0..close_{t-1}) else 0.5

No window, no threshold. The reference is all history so far.

I predict this DEGENERATES, and I am stating that prediction in advance:
  F1. Because crypto prices trend upward over the sample, price sits above its
      own expanding mean almost always, so mean exposure -> ~1.0.
  F2. With exposure ~constant, the rule is indistinguishable from buy & hold and
      its edge vs a matched flat control -> ~0.

If F1/F2 hold, that is a clean demonstration that "parameter-free" is not free:
removing the parameter can remove the signal with it.

--------------------------------------------------------------------------
FALSIFICATION CRITERIA (decided now)
--------------------------------------------------------------------------
  * H-E is unsupported if E1 or E2 fails. E3/E4 are supporting, not decisive.
  * H-F is CONFIRMED as degenerate if mean exposure > 0.95 and |edge| < 0.05.
    If instead F shows a real edge, my prediction was wrong and I say so.
  * No window sets, no thresholds, and no sub-periods are to be changed after
    seeing results. W = the same 8 windows used in every prior round.

FIXED PARAMETERS
  W (ensemble set)      = [10, 20, 30, 50, 75, 100, 150, 200]
  exposure band         = 1.00 / 0.50
  cost                  = 10bps crypto
  splits                = several, reported as a range (lesson L9)
"""

import os
import numpy as np
import pandas as pd

PPY = 365
COST = 10.0
W = [10, 20, 30, 50, 75, 100, 150, 200]
RISK_ON, RISK_OFF = 1.00, 0.50

MAJORS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "DOT", "LINK",
          "LTC", "BCH", "ATOM", "UNI", "AAVE", "XLM", "ETC", "ALGO", "FIL",
          "NEO", "TRX"]


def sharpe(r, ppy=PPY):
    sd = r.std()
    return float(r.mean() / sd * np.sqrt(ppy)) if sd and sd > 0 else np.nan


def expo_single(close, w):
    ma = close.rolling(w, min_periods=w).mean()
    v = ma.notna()
    out = pd.Series(RISK_OFF, index=close.index)
    out[v] = np.where(close[v] > ma[v], RISK_ON, RISK_OFF)
    return out


def expo_ensemble(close, windows=W):
    """Mean exposure across all windows. No selection."""
    acc = None
    for w in windows:
        e = expo_single(close, w)
        acc = e if acc is None else acc + e
    e = acc / len(windows)
    return e.ffill().fillna(RISK_OFF)


def expo_expanding(close):
    """Truly parameter-free: price vs the mean of ALL prior closes."""
    n = len(close)
    vals = close.to_numpy(dtype=float)
    csum = np.cumsum(vals)
    idx = np.arange(1, n + 1)
    exp_mean = np.empty(n)
    exp_mean[0] = np.nan
    exp_mean[1:] = csum[:-1] / idx[:-1]
    out = pd.Series(RISK_OFF, index=close.index)
    ok = ~np.isnan(exp_mean)
    out[ok] = np.where(vals[ok] > exp_mean[ok], RISK_ON, RISK_OFF)
    return out.ffill().fillna(RISK_OFF)


def nets(rets, expo, cost=COST):
    pos = expo.shift(1).fillna(0.0)
    turn = pos.diff().abs().fillna(pos.abs())
    return pos * rets - turn * cost / 10_000.0


def edge_vs_flat(rets, expo, cost=COST, ppy=PPY):
    r = nets(rets, expo, cost)
    f = pd.Series(float(expo.mean()), index=rets.index) * rets
    return sharpe(r, ppy) - sharpe(f, ppy)


def block_idx(n, block, rng):
    nb = int(np.ceil(n / block))
    st = rng.integers(0, n, nb)
    return np.concatenate([np.arange(s, s + block) % n for s in st])[:n]


def build_panels():
    d = pd.read_feather("user_data/data/bitstamp/BTC_USD-1d.feather")
    d = d.sort_values("date").drop_duplicates("date")
    btc = d.set_index("date")["close"].astype(float).iloc[200:]
    r_btc = btc.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)

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
    return {"BTC": (btc, r_btc), "pool": (idx, ew)}


def main():
    panels = build_panels()

    print("=" * 96)
    print("# H-E / H-F PRE-REGISTERED TEST")
    print("=" * 96)
    print(f"\n  ensemble windows : {W}")
    print(f"  band {RISK_ON}/{RISK_OFF}, {COST:.0f}bps, no selection in the ensemble")

    results = {}
    for name, (close, rets) in panels.items():
        print(f"\n{'=' * 96}")
        print(f"# {name}")
        print(f"{'=' * 96}")

        e_ens = expo_ensemble(close)
        e_exp = expo_expanding(close)
        e_50 = expo_single(close, 50)

        # ---------- exposure characteristics ----------
        print(f"\n  mean exposure: ensemble {e_ens.mean():.3f}   "
              f"SMA-50 {e_50.mean():.3f}   expanding {e_exp.mean():.3f}")

        # ---------- E1: temporal stability ----------
        base_ens = edge_vs_flat(rets, e_ens)
        print(f"\n  --- E1: leave-one-year-out on the ENSEMBLE ---")
        vals = []
        for y in sorted(set(close.index.year)):
            m = close.index.year != y
            if m.sum() < 200:
                continue
            vals.append((y, edge_vs_flat(rets[m], e_ens[m])))
        vals_arr = np.array([v for _, v in vals])
        print(f"    full-sample edge : {base_ens:+.3f}")
        print(f"    jackknife range  : {vals_arr.min():+.3f} .. {vals_arr.max():+.3f}")
        print(f"    E1 {'PASS' if vals_arr.min() > 0 else 'FAIL'} "
              f"(all leave-one-out edges > 0)")

        # ---------- E2/E3/E4: multiple splits ----------
        print(f"\n  --- E2/E3/E4: independent splits (train/test) ---")
        splits = (["2020-01-01", "2021-01-01", "2022-01-01", "2023-01-01",
                   "2024-01-01", "2025-01-01"] if name == "BTC"
                  else ["2021-06-01", "2022-01-01", "2022-07-01", "2023-01-01",
                        "2023-07-01", "2024-01-01"])
        tlen = 550 if name == "BTC" else 400

        print(f"    {'split':<12} {'ens edge':>9} {'SMA50 edge':>11} "
              f"{'flat-ish?':>10} {'mean-w edge':>12}")
        e_ens_oos, e_50_oos, e_meanw_oos = [], [], []
        for s in splits:
            c = pd.Timestamp(s, tz=close.index.tz)
            te = (close.index >= c) & (close.index < c + pd.Timedelta(days=tlen))
            if te.sum() < 100:
                continue
            a_ens = edge_vs_flat(rets[te], e_ens[te])
            a_50 = edge_vs_flat(rets[te], e_50[te])
            # mean OOS edge across individual windows (random-pick baseline)
            indiv = [edge_vs_flat(rets[te], expo_single(close, w)[te]) for w in W]
            a_meanw = float(np.mean(indiv))
            e_ens_oos.append(a_ens)
            e_50_oos.append(a_50)
            e_meanw_oos.append(a_meanw)
            print(f"    {s:<12} {a_ens:>+9.3f} {a_50:>+11.3f} "
                  f"{'':>10} {a_meanw:>+12.3f}")

        e_ens_oos = np.array(e_ens_oos)
        e_50_oos = np.array(e_50_oos)
        e_meanw_oos = np.array(e_meanw_oos)
        print(f"\n    ensemble OOS mean      : {e_ens_oos.mean():+.3f}  "
              f"(range {e_ens_oos.min():+.3f}..{e_ens_oos.max():+.3f}, "
              f"positive {int((e_ens_oos>0).sum())}/{len(e_ens_oos)})")
        print(f"    SMA-50 OOS mean        : {e_50_oos.mean():+.3f}  "
              f"(positive {int((e_50_oos>0).sum())}/{len(e_50_oos)})")
        print(f"    mean-single-window OOS : {e_meanw_oos.mean():+.3f}")
        print(f"    E2 {'PASS' if e_ens_oos.mean() > 0 else 'FAIL'} "
              f"(ensemble OOS edge > 0)")
        print(f"    E3 {'PASS' if e_ens_oos.mean() > e_meanw_oos.mean() else 'FAIL'} "
              f"(ensemble > mean single window)")

        # E4: bootstrap on ensemble OOS vs flat, pooled over splits
        rng = np.random.default_rng(4444)
        c = pd.Timestamp(splits[0], tz=close.index.tz)
        te_all = close.index >= c
        rr = nets(rets[te_all], e_ens[te_all]).to_numpy()
        rf = (float(e_ens[te_all].mean()) * rets[te_all]).to_numpy()
        n = len(rr)
        def shp(x):
            sd = x.std()
            return float(x.mean() / sd * np.sqrt(PPY)) if sd > 0 else 0.0
        bs = np.array([shp(rr[i]) - shp(rf[i])
                       for i in (block_idx(n, 20, rng) for _ in range(5000))])
        lo, hi = np.percentile(bs, [2.5, 97.5])
        print(f"    E4 bootstrap (vs flat, pooled OOS): edge "
              f"{shp(rr)-shp(rf):+.3f} CI [{lo:+.3f}, {hi:+.3f}] "
              f"-> {'PASS' if lo > 0 else 'FAIL'}")

        # ---------- H-F ----------
        print(f"\n  --- H-F: expanding-mean (parameter-free) ---")
        e_exp_mean = float(e_exp.mean())
        e_exp_edge = edge_vs_flat(rets, e_exp)
        print(f"    mean exposure : {e_exp_mean:.3f}")
        print(f"    edge vs flat  : {e_exp_edge:+.3f}")
        f1 = e_exp_mean > 0.95
        f2 = abs(e_exp_edge) < 0.05
        print(f"    F1 {'CONFIRMED' if f1 else 'REFUTED'} (mean exposure > 0.95)")
        print(f"    F2 {'CONFIRMED' if f2 else 'REFUTED'} (|edge| < 0.05)")
        print(f"    -> expanding-mean is "
              f"{'DEGENERATE (removing the parameter removed the signal)' if (f1 and f2) else 'not degenerate -- my prediction was wrong'}")

        results[name] = {
            "ens_full": base_ens, "ens_jack_min": float(vals_arr.min()),
            "ens_oos_mean": float(e_ens_oos.mean()),
            "ens_oos_pos": int((e_ens_oos > 0).sum()), "n_splits": len(e_ens_oos),
            "sma50_oos_mean": float(e_50_oos.mean()),
            "meanw_oos": float(e_meanw_oos.mean()),
            "e4_lo": float(lo), "e4_hi": float(hi),
            "exp_mean": e_exp_mean, "exp_edge": e_exp_edge,
        }

    # ---------- VERDICT ----------
    print(f"\n{'=' * 96}")
    print("# VERDICT")
    print(f"{'=' * 96}")
    for name, r in results.items():
        e1 = r["ens_jack_min"] > 0
        e2 = r["ens_oos_mean"] > 0
        e3 = r["ens_oos_mean"] > r["meanw_oos"]
        e4 = r["e4_lo"] > 0
        print(f"\n  {name}:")
        print(f"    E1 temporal stability  : {'PASS' if e1 else 'FAIL'} "
              f"(jackknife min {r['ens_jack_min']:+.3f})")
        print(f"    E2 OOS edge > 0        : {'PASS' if e2 else 'FAIL'} "
              f"({r['ens_oos_mean']:+.3f} over {r['n_splits']} splits, "
              f"{r['ens_oos_pos']} positive)")
        print(f"    E3 beats mean window   : {'PASS' if e3 else 'FAIL'} "
              f"({r['ens_oos_mean']:+.3f} vs {r['meanw_oos']:+.3f})")
        print(f"    E4 OOS CI excludes 0   : {'PASS' if e4 else 'FAIL'} "
              f"[{r['e4_lo']:+.3f}, {r['e4_hi']:+.3f}]")
        print(f"    H-E {sum([e1,e2,e3,e4])}/4")
        print(f"    H-F expanding-mean edge: {r['exp_edge']:+.3f} "
              f"at exposure {r['exp_mean']:.3f}")

    print(f"""
  Per the pre-registration:
    * H-E is supported only if E1 AND E2 pass. E3/E4 are supporting.
    * H-F is confirmed degenerate if mean exposure > 0.95 and |edge| < 0.05.
  No re-tuning is permitted. If H-E fails, it is recorded as a failure.""")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
