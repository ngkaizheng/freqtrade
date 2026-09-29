"""
E#4 feasibility: can a cross-sectional REVERSAL construction on a liquid
perpetual universe clear costs and reach significance?

Run before any test, per AGENTS.md section 1a. A test that cannot conclude
consumes months and returns "don't know" carrying false confidence.

The only cross-sectional signal with significant evidence in this project is
NOT momentum. It is short-horizon reversal: the adversarial review measured a
1-day forward rank IC of -0.0158 to -0.0246 (HAC t -3.27 to -5.40) on this
repository's own 47-symbol spot panel, and E#3's own trend construction came
out with a negative gross edge. Both point the same way, from different panels
and by different routes.

Reversal is a high-turnover signal, so the question is arithmetic, not
sentiment: does the edge clear the cost of harvesting it?

Run:  .venv\\Scripts\\python.exe tools\\cross_sectional\\e4_feasibility.py
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("display.width", 220)

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "user_data/universe/raw_daily"

COST = 0.0016                 # round trip per name traded
DEC = 3.51                    # E[top decile] - E[bottom decile] of a standardised normal
Z = 1.6449
DAYS = 365


def load_panel():
    frames = {}
    for f in sorted(RAW.glob("*_1d.csv.gz")):
        sym = f.name.replace("_1d.csv.gz", "")
        d = pd.read_csv(f)
        d["date"] = pd.to_datetime(d["date"], format="%Y-%m-%d", errors="coerce")
        d = d.dropna(subset=["date", "close"]).set_index("date").sort_index()
        d = d[~d.index.duplicated()]
        d = d[d["quote_volume"] > 0]
        if (d["close"].pct_change() < -0.90).any():
            continue
        frames[sym] = d
    px = pd.concat({k: v["close"] for k, v in frames.items()}, axis=1).sort_index()
    qv = pd.concat({k: v["quote_volume"] for k, v in frames.items()}, axis=1).sort_index()
    return px, qv


def main() -> None:
    px, qv = load_panel()
    med_qv = qv.median()
    print(f"panel {px.shape[1]} symbols, {px.index[0].date()} -> {px.index[-1].date()}")

    print()
    print("=" * 78)
    print("A. THE UNIVERSE QUESTION: liquidity vs history")
    print("=" * 78)
    rows = []
    for n in (50, 100, 150, 200):
        top = med_qv.nlargest(n).index
        hist = px[top].notna().sum().idxmax()
        # common history = first week where at least 80% of the top-N have data
        ok = px[top].notna().mean(axis=1) >= 0.80
        start = ok[ok].index[0] if ok.any() else None
        days = (px.index[-1] - start).days if start is not None else 0
        rows.append({
            "universe": n,
            "median_quote_vol_usd_1y": float(med_qv[top].median() / 1e6),
            "usable_from": str(start.date()) if start is not None else "n/a",
            "history_years": round(days / 365, 2),
        })
    print(pd.DataFrame(rows).to_string(index=False))
    print("""
  A liquid universe is shorter-lived than an old one. That is the real trade
  between breadth and history, and it is a genuine constraint rather than a
  modelling inconvenience.""")

    # -------------------------------------------------- B. the IC, measured
    print()
    print("=" * 78)
    print("B. THE REVERSAL IC ON THIS PANEL, several horizons (measurement, not a test)")
    print("=" * 78)
    px = px.dropna(axis=1, how="all")
    sig_cs = px.pct_change().std(axis=1)      # cross-sectional dispersion per day
    print(f"  mean daily cross-sectional sigma {sig_cs.mean()*100:.2f}%")

    rows = []
    for hold_days in (1, 7, 30):
        fwd = px.pct_change(periods=hold_days, fill_method=None).shift(-hold_days)
        for form_days in (1, 7, 30):
            s = px.pct_change(periods=form_days, fill_method=None)
            pair = pd.concat([s.stack(), fwd.stack()], axis=1)
            pair = pair.dropna()
            ic = pair.groupby(level=0).corr().iloc[0::2, -1].dropna()
            if len(ic) < 30:
                continue
            rows.append({
                "form_days": form_days, "hold_days": hold_days,
                "mean_IC": round(float(ic.mean()), 5),
                "t": round(float(ic.mean() / ic.std() * math.sqrt(len(ic))), 2),
                "n_days": len(ic),
            })
    res = pd.DataFrame(rows).sort_values("t", key=abs, ascending=False)
    print(res.to_string(index=False))
    print("""
  Read this as a description of the panel, not as a test. Every combination
  tried is a trial; a family claim needs the correction applied across the
  whole table, which is what the pre-registration has to fix in advance.""")

    # -------------------------------------------------- C. the economics
    print()
    print("=" * 78)
    print("C. CAN THE EDGE CLEAR THE COST?  (the binding question)")
    print("=" * 78)
    print(f"  {'form':>5} {'hold':>5} {'|IC|':>8} {'turnover':>9} "
          f"{'gross/per':>10} {'cost/per':>9} {'net/per':>9} {'periods/yr':>11} {'net/yr':>9}")
    print("  " + "-" * 84)
    survivors = []
    for _, r in res.iterrows():
        form, hold, ic = r["form_days"], r["hold_days"], abs(r["mean_IC"])
        # edge for a decile long-short held over `hold` days
        sig_h = sig_cs.mean() * math.sqrt(hold)
        gross_h = DEC * ic * sig_h
        # A formation window of `form` days that fully resets the ranking turns
        # the book over once per holding period. Turnover is set to 1.0, which
        # is the WORST case: a smooth cross-sectional score would turn over less.
        turnover_per_period = 1.0 if form <= hold else hold / form
        cost_p = turnover_per_period * COST
        net = gross_h - cost_p
        periods_per_year = DAYS / hold
        # Non-overlapping periods: annualise by the number of periods, NOT by
        # pretending a monthly trade earns a weekly rate 52 times. The first
        # version of this table did exactly that and overstated the monthly row
        # by 4x.
        net_yr = net * periods_per_year
        print(f"  {form:>5} {hold:>5} {ic:>8.4f} {turnover_per_period:>9.2f} "
              f"{gross_h*100:>9.3f}% {cost_p*100:>8.3f}% {net*100:>8.3f}% "
              f"{periods_per_year:>11.1f} {net_yr*100:>8.1f}%")
        if net > 0:
            survivors.append((form, hold, r["t"], net, net_yr))

    print()
    print("  Ranked by |t| among the net-positive rows, with a family correction")
    print("  applied across ALL combinations measured above:")
    n_trials = len(res)
    for form, hold, t_raw, net, net_yr in sorted(survivors, key=lambda x: -abs(x[2])):
        t_corr = abs(t_raw) / math.sqrt(n_trials)
        print(f"    form {form:>3}d hold {hold:>3}d   |t| {abs(t_raw):5.2f} "
              f"-> family-corrected {t_corr:5.2f}   net {net*100:+.3f}%/period  "
              f"{net_yr*100:+.1f}%/yr")

    print("=" * 78)
    print("D. VERDICT")
    print("=" * 78)
    viable = [s for s in survivors if abs(s[2]) / math.sqrt(n_trials) >= 2.0]
    if viable:
        print(f"  {len(viable)} of {n_trials} measured combinations are both")
        print("  family-corrected-significant and net-positive. That is enough to")
        print("  justify ONE pre-registered confirmation, with the strongest member")
        print("  named as the primary in advance and the correction carried over.")
    else:
        print("  NONE of the measured combinations is both significant and net-positive")
        print("  after a family correction. Stop this line rather than search it.")


if __name__ == "__main__":
    main()
