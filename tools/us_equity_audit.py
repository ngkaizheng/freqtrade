"""US equity research environment audit — Gate 0 preparation.

Two things to establish before ANY new strategy work:

1. DATA LENGTH. The handoff's README claims "SPY 1993-2026 (33.6 years)", but the
   local cache file looked like 2010-2026 (16.7y). That discrepancy matters,
   because the entire recommendation to switch to equities rests on having MORE
   history than crypto's 14.6y. Verify what is actually on disk.

2. UNIVERSE + POWER. Compute, per asset: history length, SE(Sharpe), and
   effective independent bets — i.e. the inputs Gate 0 needs.

Also reports where longer history could come from if the local data is short.
"""

import glob
import os

import numpy as np
import pandas as pd

CACHE = "quant-research-handoff/data/cache"


def main():
    files = sorted(glob.glob(os.path.join(CACHE, "*.csv")))
    print("=" * 94)
    print("# US EQUITY DATA AUDIT")
    print("=" * 94)
    print(f"\n  CSVs in handoff cache: {len(files)}")

    rows = []
    for p in files:
        t = os.path.basename(p)[:-4]
        try:
            d = pd.read_csv(p, parse_dates=["Date"])
        except Exception:
            continue
        d = d.dropna(subset=["Close"]).drop_duplicates("Date").sort_values("Date")
        if len(d) < 100:
            continue
        yrs = (d["Date"].max() - d["Date"].min()).days / 365.25
        rows.append({"ticker": t, "start": d["Date"].min().date(),
                     "end": d["Date"].max().date(), "rows": len(d), "years": yrs})
    df = pd.DataFrame(rows).sort_values("years", ascending=False)

    print(f"\n  {'ticker':<8} {'start':<12} {'end':<12} {'rows':>6} {'years':>7}")
    for _, r in df.head(15).iterrows():
        print(f"  {r['ticker']:<8} {str(r['start']):<12} {str(r['end']):<12} "
              f"{r['rows']:>6} {r['years']:>7.1f}")
    print(f"  ... ({len(df)} total)")
    print(f"\n  longest history : {df['years'].max():.1f}y ({df.iloc[0]['ticker']})")
    print(f"  median history  : {df['years'].median():.1f}y")
    print(f"  shortest        : {df['years'].min():.1f}y")

    # ---------- 1. the SPY discrepancy ----------
    print(f"\n{'=' * 94}")
    print("# 1. SPY DISCREPANCY CHECK")
    print(f"{'=' * 94}")
    spy = df[df["ticker"] == "SPY"]
    if not spy.empty:
        s = spy.iloc[0]
        print(f"\n  local SPY.csv : {s['start']} -> {s['end']}  "
              f"({s['rows']} rows, {s['years']:.1f} years)")
    readme = os.path.join("quant-research-handoff", "README.md")
    claimed = None
    if os.path.exists(readme):
        txt = open(readme, encoding="utf-8").read()
        import re
        for m in re.finditer(r"SPY\s*(\d{4})-(\d{4})[^\n]*?(\d+\.\d+)\s*年", txt):
            claimed = (m.group(1), m.group(2), m.group(3))
        if claimed:
            print(f"  README claims : {claimed[0]}-{claimed[1]} "
                  f"({claimed[2]} years)")
    if claimed:
        gap = float(claimed[2]) - float(s["years"])
        print(f"\n  GAP: {gap:.1f} years of claimed history is NOT in the local cache.")
        print(f"  -> the handoff's headline SPY result was computed on data it did")
        print(f"     not ship. The local cache starts {s['start']}, not {claimed[0]}.")
        print(f"  -> I CANNOT reproduce the 33.6-year SPY result from local files.")

    # ---------- 2. power inputs ----------
    print(f"\n{'=' * 94}")
    print("# 2. POWER INPUTS (Gate 0 ingredients)")
    print(f"{'=' * 94}")
    print(f"\n  For each asset: SE(Sharpe) = 1/sqrt(years) is the resolution limit.")
    print(f"\n  {'asset':<8} {'years':>7} {'SE(Sharpe)':>11} {'ann vol':>9}")
    for tk in ("SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "GLD"):
        sub = df[df["ticker"] == tk]
        if sub.empty:
            continue
        s = sub.iloc[0]
        d = pd.read_csv(os.path.join(CACHE, f"{tk}.csv"), parse_dates=["Date"])
        d = d.dropna(subset=["Close"]).sort_values("Date")
        r = d["Close"].pct_change().dropna()
        vol = float(r.std() * np.sqrt(252))
        print(f"  {tk:<8} {s['years']:>7.1f} {1/np.sqrt(s['years']):>11.3f} "
              f"{vol:>9.1%}")

    # ---------- 3. cross-asset correlation (effective bets) ----------
    print(f"\n{'=' * 94}")
    print("# 3. EFFECTIVE INDEPENDENT BETS ACROSS THE UNIVERSE")
    print(f"{'=' * 94}")
    panels = {}
    for p in files:
        t = os.path.basename(p)[:-4]
        try:
            d = pd.read_csv(p, parse_dates=["Date"])
        except Exception:
            continue
        d = d.dropna(subset=["Close"]).drop_duplicates("Date").sort_values("Date")
        panels[t] = d.set_index("Date")["Close"].astype(float)
    panel = pd.DataFrame(panels).sort_index()
    rets = panel.pct_change(fill_method=None)
    # use the common overlap window
    rets = rets.loc["2011-01-01":]
    rets = rets.loc[:, rets.notna().sum() > 2000]
    C = rets.corr()
    off = C.where(~np.eye(len(C), dtype=bool)).stack()
    ev = np.linalg.eigvalsh(C.fillna(0).to_numpy())
    ev = ev[ev > 0]
    n_eff = float((ev.sum() ** 2) / (ev ** 2).sum())
    print(f"\n  assets in panel         : {rets.shape[1]}")
    print(f"  overlapping window      : {rets.index[0].date()} -> "
          f"{rets.index[-1].date()}")
    print(f"  mean pairwise corr      : {float(off.mean()):.3f}")
    print(f"  EFFECTIVE independent bets: ~{n_eff:.1f}")

    # ---------- 4. where longer history could come from ----------
    print(f"\n{'=' * 94}")
    print("# 4. SOURCES FOR LONGER HISTORY")
    print(f"{'=' * 94}")
    print("""
  Not tested here (network calls), listed for the next step:
    * yfinance      - SPY daily from 1993; free; not currently installed
    * Stooq        - SPY from 1993; free CSV download, no key
    * FRED         - SP500 index from 1950s (index, not ETF; no dividends)
    * Norgate/Sharadar - paid, survivorship-bias-free, point-in-time

  For a US-equity risk question, ~1993+ is the practical free ceiling (SPY
  inception). That is ~33 years, vs 14.6y of crypto daily -- roughly 2.3x the
  history and therefore ~1.5x better Sharpe resolution (SE 0.17 vs 0.26).
""")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
