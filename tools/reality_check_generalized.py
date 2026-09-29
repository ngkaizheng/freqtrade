"""REALITY CHECK, generalized: two datasets AND two edge definitions.

Two issues to settle honestly:

1. REPLICATION. reality_check_selection.py ran on BTC only. The natural check is
   the 20-major pool — different data, same procedure.

2. METRIC CONSISTENCY. I noticed my own scripts use two different definitions of
   "edge", and the two do NOT have to agree:

     metric D (difference of levels)  : Sharpe(rule) - Sharpe(flat)
     metric S (Sharpe of the overlay) : Sharpe(rule_net - flat_net)

   Earlier rounds used D (the DSR script used S for its "claim B"). If the
   verdict flips between D and S, then the finding is metric-dependent and must
   be reported as such rather than picking whichever is convenient (L5/L10/L9).

The max-statistic circular-shift null is N-free: each null draw re-runs the full
8-window search, so the null already prices the selection.
"""

import numpy as np
import pandas as pd

PPY = 365
COST = 10.0
WINDOWS = [10, 20, 30, 50, 75, 100, 150, 200]
RISK_ON, RISK_OFF = 1.00, 0.50
N_SHIFTS = 500

MAJORS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "DOT", "LINK",
          "LTC", "BCH", "ATOM", "UNI", "AAVE", "XLM", "ETC", "ALGO", "FIL",
          "NEO", "TRX"]


def sh(r):
    sd = r.std()
    return float(r.mean() / sd) if sd > 0 else 0.0


def build_signals(close):
    out = {}
    for w in WINDOWS:
        ma = close.rolling(w, min_periods=w).mean()
        v = ma.notna()
        s = pd.Series(RISK_OFF, index=close.index)
        s[v] = np.where(close[v] > ma[v], RISK_ON, RISK_OFF)
        out[w] = s.to_numpy()
    return out


def nets(sig, rets, cost=COST):
    n = len(sig)
    pos = np.empty(n)
    pos[0] = 0.0
    pos[1:] = sig[:-1]
    turn = np.abs(np.diff(pos, prepend=0.0))
    return pos * rets - turn * cost / 10_000.0


def edge_D(sig, rets):
    """metric D: Sharpe(rule) - Sharpe(flat at matched exposure)."""
    rule = nets(sig, rets)
    flat = float(np.mean(sig)) * rets
    return sh(rule) - sh(flat)


def edge_S(sig, rets):
    """metric S: Sharpe of the overlay (rule_net - flat_net)."""
    rule = nets(sig, rets)
    flat = float(np.mean(sig)) * rets
    return sh(rule - flat)


def run_dataset(label, close, rets, metric_fn, metric_name):
    r = rets.to_numpy()
    n = len(r)
    sig = build_signals(close)

    obs = {w: metric_fn(sig[w], r) for w in WINDOWS}
    best_w = max(obs, key=lambda w: obs[w])
    obs_max = obs[best_w]

    rng = np.random.default_rng(2026)
    null_max = np.empty(N_SHIFTS)
    for i in range(N_SHIFTS):
        rs = np.roll(r, int(rng.integers(1, n)))
        null_max[i] = max(metric_fn(sig[w], rs) for w in WINDOWS)

    p_max = float((null_max >= obs_max).mean())

    # SMA-50 alone (selection NOT priced in)
    null50 = np.empty(N_SHIFTS)
    for i in range(N_SHIFTS):
        rs = np.roll(r, int(rng.integers(1, n)))
        null50[i] = metric_fn(sig[50], rs)
    p50 = float((null50 >= obs[50]).mean())

    return {
        "label": label, "metric": metric_name, "best_w": best_w,
        "obs_max": obs_max, "obs_50": obs[50],
        "null_max_p95": float(np.percentile(null_max, 95)),
        "p_max": p_max, "p_50": p50,
        "null50_p95": float(np.percentile(null50, 95)),
        "years": n / PPY,
    }


def main():
    print("=" * 96)
    print("# REALITY CHECK — replication across datasets AND edge definitions")
    print("=" * 96)

    d = pd.read_feather("user_data/data/bitstamp/BTC_USD-1d.feather")
    d = d.sort_values("date").drop_duplicates("date")
    btc = d.set_index("date")["close"].astype(float).iloc[200:]
    r_btc = btc.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)

    closes = {}
    for m in MAJORS:
        p = f"user_data/data/binance/{m}_USDT-1d.feather"
        try:
            dd = pd.read_feather(p).sort_values("date").drop_duplicates("date")
        except FileNotFoundError:
            continue
        closes[f"{m}/USDT"] = dd.set_index("date")["close"].astype(float)
    panel = pd.DataFrame(closes).sort_index().loc["2019-01-01":]
    prets = panel.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    idx = panel.ffill().mean(axis=1)
    ew = prets.mean(axis=1, skipna=True).fillna(0.0)

    results = []
    for ds_label, c, r in (("BTC/USD 14.6y", btc, r_btc),
                           ("20-major pool 7.7y", idx, ew)):
        for mname, mfn in (("D: SR(rule)-SR(flat)", edge_D),
                           ("S: SR(rule-flat overlay)", edge_S)):
            res = run_dataset(ds_label, c, r, mfn, mname)
            results.append(res)
            print(f"\n{'=' * 96}")
            print(f"# {ds_label}   |   metric {mname}")
            print(f"{'=' * 96}")
            print(f"  best window by this metric : SMA-{res['best_w']} "
                  f"(value {res['obs_max']:+.5f})")
            print(f"  SMA-50 value               : {res['obs_50']:+.5f}")
            print(f"  null(max over 8) p95       : {res['null_max_p95']:+.5f}")
            print(f"  -> p (SELECTION PRICED IN) : {res['p_max']:.4f}")
            print(f"  null(SMA-50 alone) p95     : {res['null50_p95']:+.5f}")
            print(f"  -> p (selection ignored)   : {res['p_50']:.4f}")

    # ---------- summary ----------
    print(f"\n{'=' * 96}")
    print("# SUMMARY")
    print(f"{'=' * 96}")
    print(f"\n  {'dataset':<22} {'metric':<26} {'p(max)':>9} {'p(SMA50)':>10}  "
          f"verdict at 0.05")
    for res in results:
        v = "search explains" if res["p_max"] > 0.05 else "survives search"
        print(f"  {res['label']:<22} {res['metric']:<26} {res['p_max']:>9.4f} "
              f"{res['p_50']:>10.4f}  {v}")

    print(f"""
  How to read:
    * p(max) is the honest test when the window was CHOSEN -- the null re-runs
      the search.
    * p(SMA50) ignores selection and is therefore optimistic; it is shown only
      to expose how much the selection penalty matters.

  Consistency across the four combinations is the evidence. If all four agree
  that the search explains the result, the finding is robust to both the dataset
  and the metric definition.""")

    agree = sum(1 for res in results if res["p_max"] > 0.05)
    print(f"\n  {agree}/{len(results)} combinations: search explains the result (p>0.05)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
