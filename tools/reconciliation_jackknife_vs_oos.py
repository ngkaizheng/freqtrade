"""RECONCILIATION — why is the edge robust to jackknife but absent out-of-sample?

Two results appear to conflict:

  A. Fragility analysis: edge +0.187 (BTC) / +0.263 (pool), leave-one-year-out
     range well above zero, bootstrap CI excludes zero, present in both eras.
     => looks robust.

  B. Clean train/test split: train-only selection picks SMA-20 (BTC) and SMA-50
     (pool); test edges are +0.024 (BTC) and -0.001 (pool).
     => edge absent out-of-sample.

Both cannot be describing the same phenomenon. This script locates the
difference. The candidate explanation, stated before running:

  The jackknife holds the WINDOW FIXED at SMA-50 and varies the YEARS.
  The train/test split varies the WINDOW, choosing it on train data only.
  So (A) asks "is this rule stable over time?" and (B) asks "can the window be
  CHOSEN without hindsight?" Those are different questions, and a rule can pass
  the first while failing the second.

If that is right, then across the window grid:
  * in-sample edge should be similar for many windows (the plateau)
  * but out-of-sample edge should NOT be predictable from in-sample edge

This is the parameter-level version of the selection problem (lesson L5).
"""

import os
import numpy as np
import pandas as pd

PPY_C, COST_C = 365, 10.0
WINDOWS = [10, 20, 30, 50, 75, 100, 150, 200]
MAJORS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "DOT", "LINK",
          "LTC", "BCH", "ATOM", "UNI", "AAVE", "XLM", "ETC", "ALGO", "FIL",
          "NEO", "TRX"]


def sharpe(r, ppy=PPY_C):
    sd = r.std()
    return float(r.mean() / sd * np.sqrt(ppy)) if sd and sd > 0 else np.nan


def sma_expo(close, w):
    ma = close.rolling(w, min_periods=w).mean()
    v = ma.notna()
    out = pd.Series(0.5, index=close.index)
    out[v] = np.where(close[v] > ma[v], 1.0, 0.5)
    return out


def edge(close, rets, w, cost=COST_C):
    e = sma_expo(close, w)
    pos = e.shift(1).fillna(0.0)
    turn = pos.diff().abs().fillna(pos.abs())
    r = sharpe(pos * rets - turn * cost / 10_000.0)
    f = sharpe(pd.Series(float(e.mean()), index=rets.index) * rets)
    return r - f


def grid_table(label, close, rets, cut_train_end, cut_test_start):
    c = pd.Timestamp(cut_train_end, tz=close.index.tz)
    s = pd.Timestamp(cut_test_start, tz=close.index.tz)
    tr = close.index <= c
    te = close.index >= s

    print(f"\n{'=' * 96}")
    print(f"# {label}")
    print(f"{'=' * 96}")
    print(f"  train <= {cut_train_end} ({tr.sum()} bars)   "
          f"test >= {cut_test_start} ({te.sum()} bars)")

    rows = []
    for w in WINDOWS:
        e_tr = edge(close[tr], rets[tr], w)
        e_te = edge(close[te], rets[te], w)
        rows.append({"w": w, "train": e_tr, "test": e_te})
    df = pd.DataFrame(rows)

    print(f"\n  {'window':>7} {'train edge':>11} {'test edge':>10}  "
          f"{'train rank':>11} {'test rank':>10}")
    df["train_rank"] = df["train"].rank(ascending=False).astype(int)
    df["test_rank"] = df["test"].rank(ascending=False).astype(int)
    for _, r in df.iterrows():
        print(f"  {int(r['w']):>7} {r['train']:>+11.3f} {r['test']:>+10.3f}  "
              f"{int(r['train_rank']):>11} {int(r['test_rank']):>10}")

    best_tr = df.loc[df["train"].idxmax()]
    print(f"\n  train-best window : SMA-{int(best_tr['w'])}  "
          f"(train {best_tr['train']:+.3f})  -> test {best_tr['test']:+.3f}")
    print(f"  test-best window  : SMA-{int(df.loc[df['test'].idxmax(), 'w'])}  "
          f"(test {df['test'].max():+.3f})")
    print(f"  test-WORST window : SMA-{int(df.loc[df['test'].idxmin(), 'w'])}  "
          f"(test {df['test'].min():+.3f})")

    rho = float(df["train"].corr(df["test"], method="spearman"))
    print(f"\n  Spearman rho(train edge, test edge): {rho:+.3f}")
    print(f"  -> {'train performance DOES predict test performance' if rho > 0.5 else 'train performance does NOT predict test performance'}")
    print(f"  test-window Sharpe spread: {df['test'].min():+.3f} .. "
          f"{df['test'].max():+.3f} (spread {df['test'].max()-df['test'].min():.3f})")
    return df


def main():
    print("=" * 96)
    print("# RECONCILIATION — jackknife-robust but OOS-absent?")
    print("=" * 96)
    print("""
  Hypothesis: the jackknife fixes the WINDOW and varies the YEARS; the
  train/test split varies the WINDOW. A rule can be stable over time yet have a
  window that cannot be chosen without hindsight.""")

    d = pd.read_feather("user_data/data/bitstamp/BTC_USD-1d.feather")
    d = d.sort_values("date").drop_duplicates("date")
    btc = d.set_index("date")["close"].astype(float).iloc[200:]
    r_btc = btc.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    df_btc = grid_table("BTC/USD (Bitstamp)", btc, r_btc,
                        "2024-12-31", "2025-01-01")

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
    df_pool = grid_table("20-major pool (Binance)", idx, ew,
                         "2023-12-31", "2024-01-01")

    # ---------- Synthesis ----------
    print(f"\n{'=' * 96}")
    print("# RECONCILIATION RESULT")
    print(f"{'=' * 96}")
    for name, df in (("BTC", df_btc), ("pool", df_pool)):
        rho = float(df["train"].corr(df["test"], method="spearman"))
        spread = df["test"].max() - df["test"].min()
        best_tr = df.loc[df["train"].idxmax()]
        print(f"\n  {name}:")
        print(f"    train->test rank correlation : {rho:+.3f}")
        print(f"    train-best SMA-{int(best_tr['w'])} test edge    : "
              f"{best_tr['test']:+.3f}")
        print(f"    test window spread           : {spread:.3f}")

    print(f"""
  INTERPRETATION

  The jackknife and the train/test split answer DIFFERENT questions:

    jackknife : "given window = SMA-50, is the edge spread across years?"
                -> YES (BTC range +0.154..+0.237; pool +0.140..+0.340)

    split     : "can the window be CHOSEN in advance?"
                -> Only weakly. The train-best window does not reliably deliver
                   a positive test edge, and the test-window spread is large.

  So the honest reconciliation is:

    * The rule is STABLE IN TIME for a fixed window. That part is real.
    * But window SELECTION is unreliable out-of-sample. That part is also real,
      and it is the part that matters, because deploying the rule requires
      having chosen the window.

  This is lesson L5 restated at the parameter level: a plateau in-sample does
  not imply the plateau's members transfer out-of-sample. It also explains why
  the full-sample "+0.187" and the "+0.024 OOS" are both true.

  Consequence for the candidate: unchanged. It is eligible for forward
  validation only, and the FORWARD test must not involve any window search.""")


if __name__ == "__main__":
    main()
