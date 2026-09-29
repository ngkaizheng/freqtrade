"""PRE-REGISTRATION — Hypothesis H-D

Written BEFORE looking at any results. The point of pre-registration is to make
it impossible to quietly change the hypothesis after seeing the data (lesson L5:
I selected SMA-50 on the full sample and voided my own out-of-sample claim).

--------------------------------------------------------------------------
BACKGROUND / MECHANISM (established, not assumed)
--------------------------------------------------------------------------
Round 4 established a real mechanism, not a pattern:

  variance ratio VR(q) = Var(q-period ret) / (q * Var(1-period ret))
    crypto  VR(20) = 1.19   -> POSITIVELY PERSISTENT (trending)
    equities VR(20) = 0.84  -> MEAN-REVERTING

The SMA exposure rule works on crypto and fails 0-for-4 on equities, and it
fails exactly where VR < 1. That is a causal story: a trend rule must lose on a
mean-reverting process.

If persistence is the mechanism, it should have a SECOND testable implication
that does not involve moving averages at all.

--------------------------------------------------------------------------
HYPOTHESIS H-D (falsifiable)
--------------------------------------------------------------------------
If positive return persistence is the true mechanism, then the degree of
trend-following profitability should be PREDICTABLE from the variance ratio
measured IN-SAMPLE, on data the rule has never traded.

Predictions, fixed now:

  P1. Ranking assets by VR(20) computed on 2019-2022 only, the top tercile
      will show a HIGHER mean SMA-50 edge (vs matched-exposure flat) in
      2023-2026 than the bottom tercile.
        -> required: top-tercile mean edge - bottom-tercile mean edge > 0

  P2. The cross-sectional Spearman correlation between in-sample VR(20) and
      out-of-sample SMA-50 edge will be POSITIVE.
        -> required: rho > 0

  P3. A single pooled regression of OOS edge on IS VR will have a positive
      slope with a bootstrap CI that excludes zero.
        -> required: CI lower bound > 0

  P4. CONTROL: the same procedure on US equities (where VR < 1) will NOT show
      P1's effect. If it does, the mechanism story is wrong and P1 was noise.

FALSIFICATION CRITERIA (decided now, not later):
  * Any of P1-P3 failing => H-D is NOT supported. Report it and stop.
  * P4 failing (equities ALSO show the effect) => the VR story is not
    mechanism-specific; report H-D as unsupported regardless of P1-P3.
  * No parameter changes after seeing results. VR window, tercile count, and
    the SMA rule are all fixed below.

FIXED PARAMETERS (not to be tuned):
  VR window q      = 20
  IS period        = 2019-01-01 .. 2022-12-31
  OOS period       = 2023-01-01 .. end
  SMA rule         = SMA-50, exposure 50%/100%, 10bps
  terciles         = 3 (top / bottom compared)
  bootstrap draws  = 5000

WHY THIS IS WORTH RUNNING
  It is the first test in this project that predicts OOS behaviour from an
  IS-measured mechanism property rather than selecting a parameter that happens
  to fit. If it works, it also gives a way to decide WHICH assets to trade
  without mining their returns. If it fails, that is informative: the VR story
  would be a post-hoc explanation rather than a usable mechanism.
"""

import os
import numpy as np
import pandas as pd

PPY_C, COST_C = 365, 10.0
PPY_E, COST_E = 252, 5.0
VR_Q = 20
IS_END = "2022-12-31"
OOS_START = "2023-01-01"
MA = 50

MAJORS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "DOT", "LINK",
          "LTC", "BCH", "ATOM", "UNI", "AAVE", "XLM", "ETC", "ALGO", "FIL",
          "NEO", "TRX"]


def sharpe(r, ppy):
    sd = r.std()
    return float(r.mean() / sd * np.sqrt(ppy)) if sd and sd > 0 else np.nan


def sma_expo(close, w=MA):
    ma = close.rolling(w, min_periods=w).mean()
    v = ma.notna()
    out = pd.Series(0.5, index=close.index)
    out[v] = np.where(close[v] > ma[v], 1.0, 0.5)
    return out


def rule_net(rets, close, cost):
    e = sma_expo(close)
    pos = e.shift(1).fillna(0.0)
    turn = pos.diff().abs().fillna(pos.abs())
    return pos * rets - turn * cost / 10_000.0


def flat_net(rets, close, cost):
    a = float(sma_expo(close).mean())
    return pd.Series(a, index=rets.index) * rets


def edge(rets, close, cost, ppy):
    return sharpe(rule_net(rets, close, cost), ppy) - \
           sharpe(flat_net(rets, close, cost), ppy)


def vr(x, q=VR_Q):
    v = x.dropna().to_numpy()
    if len(v) < q * 5:
        return np.nan
    v1 = np.var(v, ddof=1)
    if v1 <= 0:
        return np.nan
    qr = np.convolve(v, np.ones(q), "valid")
    return float(np.var(qr, ddof=1) / (q * v1))


def block_idx(n, block, rng):
    nb = int(np.ceil(n / block))
    st = rng.integers(0, n, nb)
    return np.concatenate([np.arange(s, s + block) % n for s in st])[:n]


def build_crypto():
    closes = {}
    for m in MAJORS:
        p = f"user_data/data/binance/{m}_USDT-1d.feather"
        if not os.path.exists(p):
            continue
        d = pd.read_feather(p).sort_values("date").drop_duplicates("date")
        closes[f"{m}/USDT"] = d.set_index("date")["close"].astype(float)
    return pd.DataFrame(closes).sort_index().loc["2019-01-01":]


def build_equities():
    import glob
    eq = pd.DataFrame({
        os.path.basename(p)[:-4]: pd.read_csv(p, parse_dates=["Date"])
        .dropna(subset=["Close"]).drop_duplicates("Date").sort_values("Date")
        .set_index("Date")["Close"].astype(float)
        for p in sorted(glob.glob("quant-research-handoff/data/cache/*.csv"))
    }).sort_index().loc["2011-01-01":]
    return eq


def run_panel(panel, ppy, cost, label, cut_is=IS_END, cut_oos=OOS_START):
    rets = panel.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    is_m = panel.index <= pd.Timestamp(cut_is, tz=panel.index.tz)
    oos_m = panel.index >= pd.Timestamp(cut_oos, tz=panel.index.tz)

    rows = []
    for t in panel.columns:
        c = panel[t].dropna()
        if len(c) < 500:
            continue
        r = rets[t].reindex(c.index)
        c_is, r_is = c[c.index.isin(panel.index[is_m])], r[r.index.isin(panel.index[is_m])]
        c_os, r_os = c[c.index.isin(panel.index[oos_m])], r[r.index.isin(panel.index[oos_m])]
        if len(c_is) < 250 or len(c_os) < 150:
            continue
        v = vr(r_is, VR_Q)
        if v != v:
            continue
        e = edge(r_os.fillna(0.0), c_os, cost, ppy)
        rows.append({"asset": t, "vr_is": v, "edge_oos": e,
                     "n_is": len(c_is), "n_oos": len(c_os)})
    df = pd.DataFrame(rows)
    if df.empty:
        return df, {}
    df = df.sort_values("vr_is").reset_index(drop=True)

    k = len(df) // 3
    bottom = df.iloc[:k]
    top = df.iloc[-k:]
    diff = float(top["edge_oos"].mean() - bottom["edge_oos"].mean())
    rho = float(df["vr_is"].corr(df["edge_oos"], method="spearman"))

    # P3: pooled OLS slope of edge on VR with block bootstrap CI
    x = df["vr_is"].to_numpy()
    y = df["edge_oos"].to_numpy()
    slope = float(np.polyfit(x, y, 1)[0])
    rng = np.random.default_rng(9001)
    n = len(df)
    bs = []
    for _ in range(5000):
        i = block_idx(n, 5, rng)
        xs, ys = x[i], y[i]
        if xs.std() > 0:
            bs.append(float(np.polyfit(xs, ys, 1)[0]))
    bs = np.array(bs)
    lo, hi = np.percentile(bs, [2.5, 97.5]) if len(bs) else (np.nan, np.nan)

    return df, {"label": label, "n": len(df), "k": k,
                "top_edge": float(top["edge_oos"].mean()),
                "bottom_edge": float(bottom["edge_oos"].mean()),
                "diff": diff, "rho": rho, "slope": slope,
                "slope_lo": float(lo), "slope_hi": float(hi),
                "vr_mean": float(df["vr_is"].mean())}


def main():
    print("=" * 92)
    print("# H-D PRE-REGISTERED TEST — is VR(20) PREDICTIVE of out-of-sample edge?")
    print("=" * 92)
    print(f"\n  IS  : <= {IS_END}")
    print(f"  OOS : >= {OOS_START}")
    print(f"  VR q={VR_Q}, SMA-{MA}, exposure 50/100, terciles, no tuning\n")

    cr = build_crypto()
    ec = build_equities()

    print("=" * 92)
    print("# TEST PANEL: CRYPTO MAJORS")
    print("=" * 92)
    dfc, rc = run_panel(cr, PPY_C, COST_C, "crypto")
    if not dfc.empty:
        print(f"\n  {'asset':<12} {'IS VR(20)':>10} {'OOS edge':>10}")
        for _, r in dfc.iterrows():
            print(f"  {r['asset']:<12} {r['vr_is']:>10.3f} {r['edge_oos']:>+10.3f}")
        print(f"\n  bottom tercile mean edge : {rc['bottom_edge']:+.3f} "
              f"({rc['k']} assets)")
        print(f"  top    tercile mean edge : {rc['top_edge']:+.3f} ({rc['k']} assets)")
        print(f"  difference (top-bottom)  : {rc['diff']:+.3f}")
        print(f"  Spearman rho(IS VR, OOS edge): {rc['rho']:+.3f}")
        print(f"  OLS slope                : {rc['slope']:+.3f} "
              f"CI [{rc['slope_lo']:+.3f}, {rc['slope_hi']:+.3f}]")

        print(f"\n  --- PRE-REGISTERED PREDICTIONS ---")
        print(f"  P1 (top tercile > bottom)   : "
              f"{'SUPPORTED' if rc['diff'] > 0 else 'FAILED'} ({rc['diff']:+.3f})")
        print(f"  P2 (rho > 0)                : "
              f"{'SUPPORTED' if rc['rho'] > 0 else 'FAILED'} ({rc['rho']:+.3f})")
        print(f"  P3 (slope CI excludes 0)    : "
              f"{'SUPPORTED' if rc['slope_lo'] > 0 else 'FAILED'} "
              f"([{rc['slope_lo']:+.3f}, {rc['slope_hi']:+.3f}])")

    print(f"\n{'=' * 92}")
    print("# P4 CONTROL: US EQUITIES (VR < 1 — effect must NOT appear)")
    print(f"{'=' * 92}")
    dfe, re_ = run_panel(ec, PPY_E, COST_E, "equities",
                         cut_is="2022-12-31", cut_oos="2023-01-01")
    if not dfe.empty:
        print(f"\n  assets: {re_['n']}   mean IS VR(20): {re_['vr_mean']:.3f}")
        print(f"  bottom tercile mean edge : {re_['bottom_edge']:+.3f}")
        print(f"  top    tercile mean edge : {re_['top_edge']:+.3f}")
        print(f"  difference (top-bottom)  : {re_['diff']:+.3f}")
        print(f"  Spearman rho             : {re_['rho']:+.3f}")
        print(f"  OLS slope                : {re_['slope']:+.3f} "
              f"CI [{re_['slope_lo']:+.3f}, {re_['slope_hi']:+.3f}]")
        ctrl_ok = not (re_["diff"] > 0 and re_["slope_lo"] > 0)
        print(f"\n  P4 (effect absent in equities): "
              f"{'SUPPORTED' if ctrl_ok else 'FAILED — mechanism story is wrong'}")

    print(f"\n{'=' * 92}")
    print("# H-D VERDICT")
    print("=" * 92)
    if dfc.empty or dfe.empty:
        print("\n  insufficient data to evaluate")
        return 1
    p1 = rc["diff"] > 0
    p2 = rc["rho"] > 0
    p3 = rc["slope_lo"] > 0
    p4 = not (re_["diff"] > 0 and re_["slope_lo"] > 0)
    passed = sum([p1, p2, p3, p4])
    print(f"\n  P1 {p1}   P2 {p2}   P3 {p3}   P4 {p4}   -> {passed}/4")
    if passed == 4:
        print("\n  H-D SUPPORTED: in-sample VR predicts out-of-sample trend edge,")
        print("  and the effect is absent where the mechanism is absent.")
    else:
        print("\n  H-D NOT SUPPORTED by the pre-registered criteria.")
        print("  Per the pre-registration, this is reported as a failure and the")
        print("  VR mechanism remains a post-hoc explanation, not a usable tool.")
        print("  No re-tuning. Recorded in the lessons ledger.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
