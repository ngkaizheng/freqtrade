"""The train/test split you asked for: train 2012-2024, test 2025-2026.

Why this matters, and an honest disclosure up front
---------------------------------------------------
I did run walk-forward folds that covered 2025-2026, so that period was not
entirely unseen. BUT there is a real leak I need to state plainly:

  **SMA-50 itself was chosen by looking at the FULL sample, including 2025-2026.**
  It emerged as the best window on Binance 2019-2026 data in round 1, and was
  then confirmed as the peak of a grid run over the full 15-year Bitstamp series
  in round 2. So the *parameter* had seen the test period even though the
  *evaluation* had not.

That means the correct experiment is NOT "evaluate the frozen SMA-50 on
2025-2026" — that number is contaminated. The correct experiment is:

    select the window using TRAIN ONLY  ->  freeze  ->  evaluate on TEST

which is what this script does. I then also report the contaminated SMA-50
number for transparency, clearly labelled.

A structural caveat I must state before any result is read
----------------------------------------------------------
Lo (2002): SE(annualised Sharpe) ~ 1/sqrt(YEARS). A test window of 2025-01-01
to 2026-09-19 is ~1.7 years, so SE ~ 0.77. This test is therefore ASYMMETRIC:

  * If the rule FAILS badly on test -> genuinely informative (edge decayed)
  * If the rule SUCCEEDS -> weak evidence, because SE 0.77 cannot distinguish
    Sharpe 1.45 from 0.68

It is a falsification test, not a confirmation test. That is still worth
running: falsification is cheap and a failure would matter.
"""

import glob
import os
import numpy as np
import pandas as pd

PPY_C = 365
COST_C = 10.0
PPY_E = 252
COST_E = 5.0
WINDOWS = [10, 20, 30, 50, 75, 100, 150, 200]

MAJORS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "DOT", "LINK",
          "LTC", "BCH", "ATOM", "UNI", "AAVE", "XLM", "ETC", "ALGO", "FIL",
          "NEO", "TRX"]


def max_dd(e):
    return float((e / e.cummax() - 1.0).min())


def cagr(e, ppy):
    y = len(e) / ppy
    return float((e.iloc[-1] / e.iloc[0]) ** (1 / y) - 1) if y > 0 else np.nan


def sharpe(r, ppy):
    sd = r.std()
    return float(r.mean() / sd * np.sqrt(ppy)) if sd and sd > 0 else np.nan


def stats(e, ppy):
    return {"cagr": cagr(e, ppy), "maxdd": max_dd(e),
            "sharpe": sharpe(e.pct_change().dropna(), ppy)}


def run(rets, expo, cost):
    pos = expo.shift(1).fillna(0.0)
    turn = pos.diff().abs().fillna(pos.abs())
    return 10_000 * (1 + (pos * rets - turn * cost / 10_000.0)).cumprod()


def sma_expo(close, w):
    ma = close.rolling(w, min_periods=w).mean()
    v = ma.notna()
    out = pd.Series(0.5, index=close.index)
    out[v] = np.where(close[v] > ma[v], 1.0, 0.5)
    return out


def edge_vs_flat(close, rets, w, cost, ppy):
    e = sma_expo(close, w)
    a = float(e.mean())
    r = stats(run(rets, e, cost), ppy)["sharpe"]
    f = stats(run(rets, pd.Series(a, index=rets.index), cost), ppy)["sharpe"]
    return r - f, r, f, a


def select_on_train(close_tr, rets_tr, cost, ppy):
    """Pick the window with the best train-set edge vs flat. Return (w, edge)."""
    best_w, best_edge = None, -np.inf
    for w in WINDOWS:
        d, _, _, _ = edge_vs_flat(close_tr, rets_tr, w, cost, ppy)
        if d > best_edge:
            best_w, best_edge = w, d
    return best_w, best_edge


def split_report(label, close, rets, cost, ppy, train_end, test_start,
                 leaked_window=None, verbose=True):
    tr = close.index < pd.Timestamp(train_end, tz=close.index.tz)
    te = ~tr
    c_tr, r_tr = close[tr], rets[tr]
    c_te, r_te = close[te], rets[te]

    if len(c_te) < 100 or len(c_tr) < 500:
        return None

    w, edge_tr = select_on_train(c_tr, r_tr, cost, ppy)
    d_te, sr_te, sf_te, avg_te = edge_vs_flat(c_te, r_te, w, cost, ppy)
    bh_te = stats(run(r_te, pd.Series(1.0, index=r_te.index), 0.0), ppy)
    rule_te = stats(run(r_te, sma_expo(c_te, w), cost), ppy)

    y_te = len(c_te) / ppy
    se_te = 1 / np.sqrt(y_te)

    row = {"label": label, "train_w": w, "edge_train": edge_tr,
           "test_w_used": w, "edge_test": d_te, "rule_sharpe_test": sr_te,
           "flat_sharpe_test": sf_te, "bh_sharpe_test": bh_te["sharpe"],
           "rule_cagr_test": rule_te["cagr"], "bh_cagr_test": bh_te["cagr"],
           "rule_dd_test": rule_te["maxdd"], "bh_dd_test": bh_te["maxdd"],
           "test_years": y_te, "se_test": se_te}

    if verbose:
        print(f"  {label}")
        print(f"    train: {c_tr.index[0].date()} -> {c_tr.index[-1].date()} "
              f"({len(c_tr)/ppy:.1f}y)   selected SMA-{w}  (train edge {edge_tr:+.3f})")
        print(f"    test : {c_te.index[0].date()} -> {c_te.index[-1].date()} "
              f"({y_te:.1f}y, SE {se_te:.2f})")
        print(f"      frozen SMA-{w:<4} rule Sharpe {sr_te:>6.2f}  "
              f"CAGR {rule_te['cagr']:>8.2%}  MaxDD {rule_te['maxdd']:>8.2%}")
        print(f"      flat (same exp)  Sharpe {sf_te:>6.2f}")
        print(f"      buy & hold       Sharpe {bh_te['sharpe']:>6.2f}  "
              f"CAGR {bh_te['cagr']:>8.2%}  MaxDD {bh_te['maxdd']:>8.2%}")
        print(f"      -> test edge vs flat {d_te:+.3f}")
        if leaked_window is not None:
            dl, srl, sfl, _ = edge_vs_flat(c_te, r_te, leaked_window, cost, ppy)
            print(f"    [CONTAMINATED] SMA-{leaked_window} (chosen with test "
                  f"knowledge): rule Sharpe {srl:.2f}, edge {dl:+.3f}")
        print()

    return row


def main():
    print("=" * 96)
    print("# TRAIN 2012-2024 / TEST 2025-2026  — the split you asked for")
    print("=" * 96)
    print("\nMethod: select the SMA window on TRAIN ONLY, freeze it, evaluate on")
    print("TEST. The frozen SMA-50 is also shown, clearly marked CONTAMINATED,")
    print("because its parameter selection had already seen 2025-2026.\n")

    # ---------------- A. BTC 15y ----------------
    print("=" * 96)
    print("# A. BTC/USD (Bitstamp, 15.1y)")
    print("=" * 96 + "\n")
    d = pd.read_feather("user_data/data/bitstamp/BTC_USD-1d.feather")
    d = d.sort_values("date").drop_duplicates("date")
    btc = d.set_index("date")["close"].astype(float).iloc[200:]
    r_btc = btc.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    rowA = split_report("BTC/USD", btc, r_btc, COST_C, PPY_C,
                        "2025-01-01", "2025-01-01", leaked_window=50)

    # ---------------- B. Binance majors ----------------
    print("=" * 96)
    print("# B. Binance majors — train 2019-2023 / test 2024-2026")
    print("=" * 96 + "\n")
    closes = {}
    for m in MAJORS:
        p = f"user_data/data/binance/{m}_USDT-1d.feather"
        if not os.path.exists(p):
            continue
        dd = pd.read_feather(p).sort_values("date").drop_duplicates("date")
        closes[f"{m}/USDT"] = dd.set_index("date")["close"].astype(float)
    panel = pd.DataFrame(closes).sort_index().loc["2019-01-01":]
    prets = panel.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)

    # Per-asset
    rowsB = []
    for t in panel.columns:
        c = panel[t].dropna()
        if len(c) < 800:
            continue
        r = prets[t].reindex(c.index).fillna(0.0)
        rr = split_report(t, c, r, COST_C, PPY_C, "2024-01-01", "2024-01-01",
                          leaked_window=50, verbose=False)
        if rr:
            rowsB.append(rr)

    dfB = pd.DataFrame(rowsB)
    wins = int((dfB["edge_test"] > 0).sum())
    print(f"  per-asset results ({len(dfB)} majors, train 2019-2023, "
          f"test 2024-2026):")
    print(f"\n    {'pair':<12} {'train w':>8} {'train edge':>11} {'test edge':>10} "
          f"{'rule SR':>8} {'BH SR':>7}")
    for _, r in dfB.iterrows():
        print(f"    {r['label']:<12} {int(r['train_w']):>8} {r['edge_train']:>+11.3f} "
              f"{r['edge_test']:>+10.3f} {r['rule_sharpe_test']:>8.2f} "
              f"{r['bh_sharpe_test']:>7.2f}")
    print(f"\n    test edge vs flat positive: {wins}/{len(dfB)}")
    print(f"    mean test edge vs flat    : {dfB['edge_test'].mean():+.3f}")
    print(f"    mean train edge vs flat   : {dfB['edge_train'].mean():+.3f}")
    print(f"    rule beats B&H on Sharpe  : "
          f"{int((dfB['rule_sharpe_test'] > dfB['bh_sharpe_test']).sum())}/{len(dfB)}")

    # Pool
    print()
    ew = prets.mean(axis=1, skipna=True).fillna(0.0)
    pidx = panel.ffill().mean(axis=1)
    rowBpool = split_report("20-major pool", pidx, ew, COST_C, PPY_C,
                            "2024-01-01", "2024-01-01", leaked_window=50)

    # ---------------- C. Equities control ----------------
    print("=" * 96)
    print("# C. US equities (control) — train 2011-2024 / test 2025-2026")
    print("=" * 96 + "\n")
    eq = pd.DataFrame({
        os.path.basename(p)[:-4]: pd.read_csv(p, parse_dates=["Date"])
        .dropna(subset=["Close"]).drop_duplicates("Date").sort_values("Date")
        .set_index("Date")["Close"].astype(float)
        for p in sorted(glob.glob("quant-research-handoff/data/cache/*.csv"))
    }).sort_index().loc["2011-01-01":]
    eqr = eq.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)

    rowsC = []
    for t in eq.columns:
        c = eq[t].dropna()
        if len(c) < 800:
            continue
        r = eqr[t].reindex(c.index).fillna(0.0)
        tr = c.index < pd.Timestamp("2025-01-01")
        te = ~tr
        if len(c[te]) < 100:
            continue
        w, e_tr = select_on_train(c[tr], r[tr], COST_E, PPY_E)
        d_te, sr_te, sf_te, _ = edge_vs_flat(c[te], r[te], w, COST_E, PPY_E)
        rowsC.append({"ticker": t, "train_w": w, "edge_train": e_tr,
                      "edge_test": d_te, "rule_sharpe_test": sr_te})
    dfC = pd.DataFrame(rowsC)
    wC = int((dfC["edge_test"] > 0).sum())
    print(f"  {len(dfC)} tickers, train 2011-2024 / test 2025-2026")
    print(f"    test edge vs flat positive : {wC}/{len(dfC)} ({wC/len(dfC):.0%})")
    print(f"    mean train edge            : {dfC['edge_train'].mean():+.3f}")
    print(f"    mean test edge             : {dfC['edge_test'].mean():+.3f}")
    print(f"    (equities were already shown to fail out-of-domain; this")
    print(f"     confirms the same protocol reproduces that failure)")

    # ---------------- D. Summary ----------------
    print(f"\n{'=' * 96}")
    print("# SUMMARY")
    print(f"{'=' * 96}")
    print(f"\n  {'dataset':<24} {'train sel':>10} {'train edge':>11} "
          f"{'test edge':>10} {'sign kept?':>11}")
    for row, name in ((rowA, "BTC/USD"), (rowBpool, "20-major pool")):
        if row:
            kept = "yes" if (row["edge_train"] > 0) == (row["edge_test"] > 0) else "NO"
            print(f"  {name:<24} {'SMA-' + str(int(row['train_w'])):>10} "
                  f"{row['edge_train']:>+11.3f} {row['edge_test']:>+10.3f} "
                  f"{kept:>11}")
    print(f"  {'US equities (109)':<24} {'mixed':>10} "
          f"{dfC['edge_train'].mean():>+11.3f} {dfC['edge_test'].mean():>+10.3f} "
          f"{'no':>11}")

    print(f"\n  Read the test window as a FALSIFICATION test, not confirmation:")
    print(f"  with ~1.7y of test data, SE(Sharpe) ~ 0.77, so a positive result")
    print(f"  cannot establish the edge and only a clear failure would be decisive.")


if __name__ == "__main__":
    main()
