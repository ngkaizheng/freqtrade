"""The user's specific stock tickers — mechanism-first test.

The question worth answering is not "can we get the data" (yes: 16.7y locally,
plus Binance perps with 4-8 months). It is:

    Are these particular names TRENDY enough for a trend rule to work?

Round 4 established the mechanism: trend rules need positive return
persistence, measured by the variance ratio.

    crypto     VR(20) = 1.19  -> trending   -> SMA rule works
    US equities VR(20) = 0.84 -> mean-revert -> SMA rule fails 0/4

But that tested the broad equity universe. Semiconductors and megacap tech could
plausibly behave differently from the average stock. That is a real, falsifiable
question and it deserves a direct test rather than an assumption.

Pre-registered predictions (written before running):
  Q1. The user's tickers will show HIGHER mean VR(20) than the broad 109-ticker
      equity universe (they are higher-beta growth names).
  Q2. If so, the SMA-50 rule should show a LESS NEGATIVE (or positive) mean edge
      on them than on the broad universe.
  Q3. If Q2 holds, the per-name edge should still be far weaker than crypto's,
      because VR will still be below 1.

No tuning: SMA-50, exposure 50/100, 5bps equities, VR q=20, fixed now.
"""

import os
import glob
import numpy as np
import pandas as pd

CACHE = "quant-research-handoff/data/cache"
PPY_E = 252
COST_E = 5.0
VR_Q = 20
MA = 50

USER_TICKERS = ["MU", "NVDA", "SNDK", "SPCX", "TSLA", "AAPL", "META", "AMD",
                "GOOGL", "MSFT", "AMZN", "NFLX", "INTC", "AVGO", "QCOM"]
BENCH = ["SPY", "QQQ"]


def sharpe(r, ppy=PPY_E):
    sd = r.std()
    return float(r.mean() / sd * np.sqrt(ppy)) if sd and sd > 0 else np.nan


def sma_expo(close, w=MA):
    ma = close.rolling(w, min_periods=w).mean()
    v = ma.notna()
    out = pd.Series(0.5, index=close.index)
    out[v] = np.where(close[v] > ma[v], 1.0, 0.5)
    return out


def rule_net(rets, close, cost=COST_E):
    e = sma_expo(close)
    pos = e.shift(1).fillna(0.0)
    turn = pos.diff().abs().fillna(pos.abs())
    return pos * rets - turn * cost / 10_000.0


def flat_net(rets, close):
    a = float(sma_expo(close).mean())
    return pd.Series(a, index=rets.index) * rets


def max_dd(eq):
    return float((eq / eq.cummax() - 1).min())


def cagr(eq):
    y = len(eq) / PPY_E
    return float((eq.iloc[-1] / eq.iloc[0]) ** (1 / y) - 1) if y > 0 else np.nan


def vr(x, q=VR_Q):
    v = x.dropna().to_numpy()
    if len(v) < q * 5:
        return np.nan
    v1 = np.var(v, ddof=1)
    if v1 <= 0:
        return np.nan
    qr = np.convolve(v, np.ones(q), "valid")
    return float(np.var(qr, ddof=1) / (q * v1))


def load(t):
    p = os.path.join(CACHE, f"{t}.csv")
    if not os.path.exists(p):
        return None
    d = pd.read_csv(p, parse_dates=["Date"])
    d = d.dropna(subset=["Close"]).drop_duplicates("Date").sort_values("Date")
    return d.set_index("Date")["Close"].astype(float)


def analyse(tickers, label):
    rows = []
    for t in tickers:
        c = load(t)
        if c is None or len(c) < 600:
            continue
        r = c.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
        rr = r.fillna(0.0)
        e = float(sma_expo(c).mean())
        net = rule_net(rr, c)
        flat = flat_net(rr, c)
        bh = rr
        edge_flat = sharpe(net) - sharpe(flat)
        edge_bh = sharpe(net) - sharpe(bh)
        eq_rule = (1 + net).cumprod()
        eq_bh = (1 + rr).cumprod()
        rows.append({
            "ticker": t, "years": len(c) / PPY_E, "vr": vr(r, VR_Q),
            "edge_flat": edge_flat, "edge_bh": edge_bh,
            "avg_expo": e,
            "rule_sharpe": sharpe(net), "bh_sharpe": sharpe(bh),
            "rule_dd": max_dd(eq_rule), "bh_dd": max_dd(eq_bh),
            "rule_cagr": cagr(eq_rule), "bh_cagr": cagr(eq_bh),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        print(f"  {label}: no data")
        return df
    print(f"\n  {label}  ({len(df)} names, median {df['years'].median():.1f}y)")
    print(f"  {'ticker':<8} {'VR(20)':>8} {'edge vs flat':>13} {'edge vs B&H':>12} "
          f"{'rule SR':>8} {'BH SR':>7} {'rule DD':>9} {'BH DD':>9}")
    for _, r in df.sort_values("vr", ascending=False).iterrows():
        print(f"  {r['ticker']:<8} {r['vr']:>8.3f} {r['edge_flat']:>+13.3f} "
              f"{r['edge_bh']:>+12.3f} {r['rule_sharpe']:>8.2f} "
              f"{r['bh_sharpe']:>7.2f} {r['rule_dd']:>9.2%} {r['bh_dd']:>9.2%}")
    print(f"\n  mean VR(20)        : {df['vr'].mean():.3f}")
    print(f"  mean edge vs flat  : {df['edge_flat'].mean():+.3f}")
    print(f"  mean edge vs B&H   : {df['edge_bh'].mean():+.3f}")
    print(f"  beats flat         : {int((df['edge_flat'] > 0).sum())}/{len(df)}")
    print(f"  beats B&H Sharpe   : {int((df['edge_bh'] > 0).sum())}/{len(df)}")
    print(f"  drawdown improved  : {int((df['rule_dd'] > df['bh_dd']).sum())}/{len(df)}")
    return df


def main():
    print("=" * 96)
    print("# THE USER'S STOCK TICKERS — are they trendy enough for a trend rule?")
    print("=" * 96)
    print(f"\n  rule FROZEN: SMA-{MA}, exposure 50/100, {COST_E:.0f}bps, VR q={VR_Q}")

    df_user = analyse(USER_TICKERS, "USER TICKERS")
    # Broad universe for comparison
    allt = [os.path.basename(p)[:-4] for p in glob.glob(os.path.join(CACHE, "*.csv"))]
    broad = [t for t in allt if t not in USER_TICKERS and t not in BENCH]
    df_broad = analyse(broad, "BROAD EQUITY UNIVERSE (reference)")
    df_bench = analyse(BENCH, "BENCHMARK ETFs")

    # ---- Crypto reference from prior work ----
    print(f"\n{'=' * 96}")
    print("# REFERENCE — crypto majors (same rule, 10bps)")
    print(f"{'=' * 96}")
    closes = {}
    for m in ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "DOT", "LINK",
              "LTC", "BCH", "ATOM", "UNI", "AAVE", "XLM", "ETC", "ALGO", "FIL",
              "NEO", "TRX"]:
        p = f"user_data/data/binance/{m}_USDT-1d.feather"
        if not os.path.exists(p):
            continue
        d = pd.read_feather(p).sort_values("date").drop_duplicates("date")
        closes[f"{m}/USDT"] = d.set_index("date")["close"].astype(float)
    panel = pd.DataFrame(closes).sort_index().loc["2019-01-01":]
    cr_rows = []
    for t in panel.columns:
        c = panel[t].dropna()
        if len(c) < 600:
            continue
        r = c.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        net = rule_net(r, c, cost=10.0)
        flat = pd.Series(float(sma_expo(c).mean()), index=r.index) * r
        cr_rows.append({"ticker": t, "vr": vr(r, VR_Q),
                        "edge_flat": sharpe(net, 365) - sharpe(flat, 365)})
    cr = pd.DataFrame(cr_rows)
    print(f"\n  crypto majors: mean VR(20) {cr['vr'].mean():.3f}   "
          f"mean edge vs flat {cr['edge_flat'].mean():+.3f}   "
          f"beats flat {int((cr['edge_flat']>0).sum())}/{len(cr)}")

    # ---- PRE-REGISTERED VERDICT ----
    print(f"\n{'=' * 96}")
    print("# PRE-REGISTERED PREDICTIONS")
    print(f"{'=' * 96}")
    q1 = df_user["vr"].mean() > df_broad["vr"].mean()
    q2 = df_user["edge_flat"].mean() > df_broad["edge_flat"].mean()
    q3 = df_user["vr"].mean() < cr["vr"].mean()

    print(f"\n  Q1 user tickers more trendy than broad universe : "
          f"{'SUPPORTED' if q1 else 'FAILED'} "
          f"({df_user['vr'].mean():.3f} vs {df_broad['vr'].mean():.3f})")
    print(f"  Q2 user tickers edge less negative than broad   : "
          f"{'SUPPORTED' if q2 else 'FAILED'} "
          f"({df_user['edge_flat'].mean():+.3f} vs "
          f"{df_broad['edge_flat'].mean():+.3f})")
    print(f"  Q3 user tickers still below crypto              : "
          f"{'SUPPORTED' if q3 else 'FAILED'} "
          f"({df_user['vr'].mean():.3f} vs {cr['vr'].mean():.3f})")

    print(f"\n{'=' * 96}")
    print("# BOTTOM LINE")
    print(f"{'=' * 96}")
    print(f"""
  On the user's own tickers, with 16.7 years of data:
    mean edge vs matched flat control : {df_user['edge_flat'].mean():+.3f}
    names beating flat                : {int((df_user['edge_flat']>0).sum())}/{len(df_user)}
    names beating buy & hold Sharpe   : {int((df_user['edge_bh']>0).sum())}/{len(df_user)}
    drawdown improved                 : {int((df_user['rule_dd']>df_user['bh_dd']).sum())}/{len(df_user)}

  Compare crypto majors: mean edge vs flat {cr['edge_flat'].mean():+.3f}
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
