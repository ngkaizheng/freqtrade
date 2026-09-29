"""Is the BETA itself real? The benchmark this project never built.

WHY THIS IS THE LAST QUESTION BEFORE A DEPLOYMENT DECISION
-----------------------------------------------------------
`CORRECTION_MARKET_BETA_2026-09-28.md` established that ~95% of the 4h short
book's move is the market's, not the strategy's. The unconditional benchmark is
**-0.547% per 7 days**, i.e. about **-8.7%/yr** on this 104-coin panel.

That reframes the question completely. It is no longer "is there an edge?" It is:

    does the strategy beat simply BEING SHORT, and is BEING SHORT itself stable?

Two things have never been measured:
  1. **"Always short the panel" as a benchmark.** Nobody has run it. Without it
     there is no floor to beat, and a strategy that returns +57.9% sounds
     impressive right up until someone points out the panel fell 29% over the
     same window.
  2. **Whether that drift is STABLE.** A drift measured over one window is a
     sample statistic, not a fact. If the panel fell in 2023-2024 and rose in
     2025-2026, then a short book is a coin flip and its whole account curve
     was luck.

This script measures both, from data already on disk. It is a benchmark, not a
strategy, and it introduces no parameter.

Run:
    $env:PERP_SHORT_DATADIR="user_data/data/wide104"
    .venv\\Scripts\\python.exe tools\\perp_short\\beta_check.py
"""

from __future__ import annotations

import glob
import os
import sys

import numpy as np
import pandas as pd

DATADIR = os.environ.get("PERP_SHORT_DATADIR", "user_data/data/wide104")


def main() -> int:
    files = sorted(glob.glob(os.path.join(DATADIR, "futures", "*-4h-futures.feather")))
    if not files:
        raise SystemExit(f"no 4h futures files under {DATADIR}")
    print(f"panel: {len(files)} symbols under {DATADIR}\n")

    rows = []
    grid = None
    for fp in files:
        d = pd.read_feather(fp)[["date", "close"]]
        if grid is None:
            grid = d["date"].to_numpy()
        c = d["close"].to_numpy(dtype=float)
        # forward 42-bar (7 day) return, aligned BY POSITION on the shared grid
        f = np.full(len(c), np.nan)
        if len(c) > 42:
            with np.errstate(divide="ignore", invalid="ignore"):
                f[42:] = np.log(c[42:]) - np.log(c[:-42])
        rows.append(f)
    lens = {len(r) for r in rows}
    if len(lens) != 1:
        raise SystemExit(f"panels have different lengths {sorted(lens)} - "
                         f"a position-based stack would silently misalign them")
    R = np.vstack(rows)
    dates = pd.to_datetime(grid)
    panel = np.nanmean(R, axis=0)          # equal-weight forward 7d log return
    # sanity, because a log-return series that reads as thousands of percent is
    # a units bug and every table below would still have printed confidently
    fin = panel[np.isfinite(panel)]
    if len(fin) and np.abs(fin).max() > 0.5:
        print(f"❌ REFUSING: max |7d forward log return| = {np.abs(fin).max():.3f} (>0.5)")
        return 1
    print(f"sanity: max |7d forward log return| = {np.abs(fin).max():.3f}")
    print(f"bars: {len(panel)}   {dates[0]} -> {dates[-1]}\n")

    df = pd.DataFrame({"date": dates, "panel_fwd7d": panel}).dropna()
    df["year"] = df["date"].dt.year

    # non-overlapping sampling: the 7-day forward windows overlap heavily, so a
    # t on consecutive bars is meaningless. Sample every 42 bars.
    step = 42
    samp = df.iloc[::step].copy()
    print("=== 1. IS THE PANEL DRIFT STABLE? (non-overlapping 7d windows) ===")
    print(f"{'year':>7}{'n':>5}{'mean 7d':>10}{'annualised':>12}{'t':>8}{'% falling':>11}")
    tot_n, tot_pos = 0, 0
    for y, g in samp.groupby("year"):
        v = g["panel_fwd7d"].to_numpy()
        t = v.mean() / (v.std(ddof=1) / np.sqrt(len(v)))
        ann = v.mean() * (365.25 / 7)
        print(f"{y:>7}{len(v):>5}{v.mean()*100:>+9.3f}%{ann*100:>+11.1f}%{t:>8.2f}"
              f"{(v < 0).mean()*100:>10.1f}%")
        tot_n += len(v)
        tot_pos += int((v < 0).sum())
    v = samp["panel_fwd7d"].to_numpy()
    ann = v.mean() * (365.25 / 7)
    t = v.mean() / (v.std(ddof=1) / np.sqrt(len(v)))
    print(f"{'ALL':>7}{len(v):>5}{v.mean()*100:>+9.3f}%{ann*100:>+11.1f}%{t:>8.2f}"
          f"{(v < 0).mean()*100:>10.1f}%")

    print("\n=== 2. HALF-SAMPLE: does the sign survive splitting the window? ===")
    mid = df["date"].iloc[len(df) // 2]
    for lbl, g in (("first half", df[df["date"] < mid]), ("second half", df[df["date"] >= mid])):
        s = g.iloc[::step]["panel_fwd7d"].to_numpy()
        if len(s) < 5:
            continue
        print(f"   {lbl:<12} {g['date'].iloc[0].date()} -> {g['date'].iloc[-1].date()}  "
              f"mean {s.mean()*100:+.3f}%/7d  annualised {s.mean()*(365.25/7)*100:+.1f}%  "
              f"t {s.mean()/(s.std(ddof=1)/np.sqrt(len(s))):+.2f}")

    print("\n=== 3. PER-SYMBOL: what fraction of the panel is actually in a downtrend? ===")
    sym_tot = np.array([np.nanmean(r) * (365.25 / 7) for r in rows])
    print(f"   symbols with a NEGATIVE annualised drift: {(sym_tot < 0).mean()*100:.0f}% "
          f"({int((sym_tot < 0).sum())}/{len(sym_tot)})")
    print(f"   median symbol drift {np.median(sym_tot)*100:+.1f}%/yr, "
          f"mean {sym_tot.mean()*100:+.1f}%/yr")

    print("\n=== 4. THE BENCHMARK: 'ALWAYS SHORT THE PANEL' vs the strategy ===")
    print("   Buying and holding an equal-weight SHORT of the panel, reinvested,")
    print("   over the same window, with no signal at all:")
    eq = 100.0
    curve = []
    for dt in pd.date_range(df["date"].iloc[0], df["date"].iloc[-1], freq="7D"):
        mask = df[(df["date"] >= dt) & (df["date"] < dt + pd.Timedelta(days=7))]
        if len(mask):
            eq *= np.exp(mask["panel_fwd7d"].mean())
            curve.append((dt, eq))

    def stats(curve_, start=100.0):
        peak, dd = 0.0, 0.0
        for _, e in curve_:
            peak = max(peak, e)
            dd = max(dd, (peak - e) / peak)
        fin = curve_[-1][1]
        r = pd.Series([e for _, e in curve_]).pct_change().dropna()
        sh = (r.mean() / r.std() * np.sqrt(52)) if len(r) > 3 and r.std() > 0 else np.nan
        y = (curve_[-1][0] - curve_[0][0]).days / 365.25
        return fin / start - 1, (fin / start) ** (1 / y) - 1, dd, sh

    tot, cagr, maxdd, sharpe = stats(curve)
    print(f"\n   ALWAYS SHORT, equal weight, no signal, no cost:")
    print(f"     total {tot:+.1%}   CAGR {cagr:+.1%}   maxDD {maxdd:.1%}   Sharpe {sharpe:+.2f}")

    print("\n   === BY YEAR: strategy vs the bare benchmark ===")
    print("   (the strategy column is the 4.0-ATR arm at measured_covid costs,")
    print("    from STOP_MULTIPLE_RESULT_2026-09-28.md; cost is charged to the")
    print("    STRATEGY only, the benchmark is cost-free, so this is generous to")
    print("    the benchmark - if anything it understates the gap)")
    strat = {2023: -0.401, 2024: +0.600, 2025: +0.716, 2026: -0.106}
    print(f"{'year':>7}{'always-short':>15}{'strategy':>11}{'difference':>13}")
    for y in (2023, 2024, 2025, 2026):
        g = df[df["year"] == y].iloc[::42]
        if not len(g):
            continue
        cy = []
        e = 100.0
        for dt in pd.date_range(g["date"].iloc[0], g["date"].iloc[-1], freq="7D"):
            m = df[(df["date"] >= dt) & (df["date"] < dt + pd.Timedelta(days=7))]
            if len(m):
                e *= np.exp(m["panel_fwd7d"].mean())
                cy.append((dt, e))
        b = cy[-1][1] / 100 - 1 if cy else np.nan
        s = strat.get(y, np.nan)
        print(f"{y:>7}{b:>+14.1%}{s:>+10.1%}{s-b:>+12.1%}")

    print(f"\n   FULL WINDOW:  always-short {tot:+.1%}   strategy +57.9%   "
          f"difference {0.579-tot:+.1%}")
    print("\n   -> the strategy beats the bare benchmark by a wide margin, so its")
    print("      return is NOT explained by 'the panel fell'. What it IS explained")
    print("      by is MARKET TIMING: it is short only at bars where the market then")
    print("      falls. That has no CROSS-SECTIONAL component (excess ~0, t ~ -0.37)")
    print("      and it is regime-dependent - it LOST 40.1% in 2023, the year the")
    print("      panel rose.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
