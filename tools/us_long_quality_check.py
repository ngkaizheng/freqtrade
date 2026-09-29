"""Quality check the newly downloaded long-history equity data.

Before building anything on it, verify it is not corrupt. Long Yahoo histories
have known artifacts: split/dividend adjustments, bad ticks, zero prices, and
stale stretches. The handoff's checklist demands this be done BEFORE any
backtest, and lesson L2 says verify with an independent check where possible.
"""

import glob
import os

import numpy as np
import pandas as pd

DIR = "user_data/data/us_long"


def main():
    files = sorted(glob.glob(os.path.join(DIR, "*.csv")))
    print("=" * 94)
    print("# LONG US-EQUITY DATA QUALITY CHECK")
    print("=" * 94)
    print(f"\n  files: {len(files)}")

    rows = []
    for p in files:
        t = os.path.basename(p)[:-4]
        d = pd.read_csv(p, parse_dates=["Date"]).sort_values("Date")
        d = d.drop_duplicates("Date").reset_index(drop=True)
        r = d["Close"].pct_change(fill_method=None)

        gaps = d["Date"].diff().dt.days
        big = gaps[gaps > 10]
        rows.append({
            "ticker": t,
            "rows": len(d),
            "years": (d["Date"].max() - d["Date"].min()).days / 365.25,
            "dup": int(d["Date"].duplicated().sum()),
            "nonpos": int((d[["Open", "High", "Low", "Close"]] <= 0).sum().sum()),
            "badhl": int((d["High"] < d["Low"]).sum()),
            "stale": int((d["Close"].diff() == 0).sum()),
            "stale_pct": float((d["Close"].diff() == 0).mean()),
            "huge": int((r.abs() > 0.5).sum()),
            "maxret": float(r.abs().max()),
            "inf": int(np.isinf(r).sum()),
            "gaps>10d": int(len(big)),
            "maxgap": int(big.max()) if len(big) else 0,
            "zerovol": int((d["Volume"].fillna(0) <= 0).sum()),
            "has_adj": "AdjClose" in d.columns,
        })

    df = pd.DataFrame(rows)

    print(f"\n  {'ticker':<7} {'yrs':>5} {'rows':>6} {'dup':>4} {'nonpos':>7} "
          f"{'badHL':>6} {'stale%':>7} {'>50%':>5} {'gap>10d':>8} {'zerovol':>8}")
    for _, r in df.sort_values("years", ascending=False).iterrows():
        print(f"  {r['ticker']:<7} {r['years']:>5.1f} {r['rows']:>6} {r['dup']:>4} "
              f"{r['nonpos']:>7} {r['badhl']:>6} {r['stale_pct']:>6.1%} "
              f"{r['huge']:>5} {r['gaps>10d']:>8} {r['zerovol']:>8}")

    print(f"\n{'=' * 94}")
    print("# AGGREGATE")
    print(f"{'=' * 94}")
    print(f"\n  total duplicate dates   : {int(df['dup'].sum())}")
    print(f"  total non-positive px   : {int(df['nonpos'].sum())}")
    print(f"  total high<low          : {int(df['badhl'].sum())}")
    print(f"  total inf returns       : {int(df['inf'].sum())}")
    print(f"  tickers with AdjClose   : {int(df['has_adj'].sum())}/{len(df)}")
    print(f"  median stale-close rate : {df['stale_pct'].median():.1%}")
    print(f"  median max |daily ret|  : {df['maxret'].median():.1%}")

    # Independent cross-check: SPY vs the handoff's own SPY on the overlap
    print(f"\n{'=' * 94}")
    print("# INDEPENDENT CROSS-CHECK — new SPY vs handoff SPY on overlap")
    print(f"{'=' * 94}")
    try:
        new = pd.read_csv(os.path.join(DIR, "SPY.csv"))
        old = pd.read_csv("quant-research-handoff/data/cache/SPY.csv",
                          parse_dates=["Date"])
        # The new file's Date carries a time component ('1993-01-29 14:30:00')
        # from the Yahoo timestamps, while the handoff file is date-only. A raw
        # merge on unequal strings yields ZERO overlap. Normalize both to
        # tz-naive midnight before merging.
        new["Date"] = (pd.to_datetime(new["Date"], errors="coerce", utc=True)
                       .dt.tz_localize(None).dt.normalize())
        old["Date"] = (pd.to_datetime(old["Date"], errors="coerce", utc=True)
                       .dt.tz_localize(None).dt.normalize())
        m = new.merge(old, on="Date", suffixes=("_new", "_old"))
        m["r_new"] = m["Close_new"].pct_change()
        m["r_old"] = m["Close_old"].pct_change()
        c = m[["r_new", "r_old"]].dropna().corr().iloc[0, 1]
        print(f"\n  overlapping days      : {len(m)}")
        print(f"  return correlation    : {c:.6f}")
        print(f"  -> {'CONSISTENT' if c > 0.99 else 'MISMATCH -- investigate'}")
        # split-adjustment sanity: compare levels
        lvl = float((m["Close_new"] / m["Close_old"]).median())
        print(f"  median price ratio    : {lvl:.4f} "
              f"({'same basis' if abs(lvl-1) < 0.02 else 'different adjustment basis'})")
        print(f"\n  NOTE: if the ratio is not ~1, one series is split/dividend")
        print(f"  adjusted differently. Returns should still match if both are")
        print(f"  consistently adjusted within themselves.")
    except Exception as e:
        print(f"  cross-check failed: {type(e).__name__}: {e}")

    print(f"""
{'=' * 94}
# VERDICT
{'=' * 94}

  Data is usable if: no duplicates, no non-positive prices, high>=low everywhere,
  and the SPY cross-check correlates >0.99 with the handoff series.

  Two known caveats to carry forward:
    * Yahoo 'Close' here is the SPLIT-adjusted price, not dividend-adjusted.
      Dividend adjustment matters for total return; 'AdjClose' is also saved
      where available. A price-only series UNDERSTATES equity returns by roughly
      the dividend yield (~1-3%/yr historically).
    * 1970s tickers (GE, IBM, XOM, KO, PG, JNJ) include delisting/survivorship
      questions for the companies themselves but are single-name histories, so
      survivorship applies to universe SELECTION, not to these series.""")


if __name__ == "__main__":
    main()
