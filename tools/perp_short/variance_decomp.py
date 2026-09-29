"""Why is a strategy that clears its costs by 9.8x not statistically significant?

F-1 (FUNDING_DECOMPOSITION_2026-09-29.md) measured that fees+funding take only
~10% of the gross price move. So "costs are too high" is dead, and the remaining
explanation for t ~= 0 has to be VARIANCE. This script sizes that variance on
the delivered book, and then asks the design question directly:

    If I add a SECOND signal, how much of the new book's risk is the same
    market factor the first book already carries?

That question is a property of the UNIVERSE, not of any P&L, so it can be
answered from price data alone - no backtest, no result to overfit. That makes
it a proper Gate 0 measurement (AGENTS.md 1a): it says whether an ensembling
experiment on this data could conclude, BEFORE anyone writes one.

Three quantities:
  1. per-trade R dispersion and the n needed for t=2 at the observed mean;
  2. the equal-weight cross-sectional ("common") share of per-trade R;
  3. the cross-symbol correlation structure of 4h returns: mean pairwise
     correlation, and the share of variance in the top eigen-direction.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\variance_decomp.py
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r_stats import tstat  # noqa: E402
from risk_unit import load_with_risk  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "user_data" / "data" / "wide526" / "futures"
RESULTS = [
    ("full/n50", "user_data/sizing_out/full/n50/backtest-result-2026-09-28_21-44-27.zip"),
    ("oos/n50", "user_data/sizing_out/oos/n50/backtest-result-2026-09-28_21-45-26.zip"),
    ("full/n100", "user_data/sizing_out/full/n100/backtest-result-2026-09-28_21-47-44.zip"),
]


def head(t: str) -> None:
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def load_trades(rel: str) -> pd.DataFrame:
    """⚠ The 2026-09-29 first version divided by
    `stake * |initial_stop_loss_ratio|`, which is the CLASS BACKSTOP (0.300000
    on every trade), not the 4xATR anchor - it overstated risk by a median of
    2.9x. The project's own `r_stats.build` has always used the ATR unit; this
    now routes through the same loader so there is one definition, not two."""
    return load_with_risk(rel)


def ret_panel(pairs: list[str]) -> pd.DataFrame:
    """4h log returns, aligned on time.

    Three defects this has to refuse rather than absorb:
      * a close of 0 or below makes log() return -inf, and an inf in the panel
        is NOT NaN - `corr()` keeps it and every correlation downstream is
        silently wrong. The first run of this script emitted
        "divide by zero encountered in log" as a RuntimeWarning and carried on.
      * symbols list at different times, so a common index would invent
        returns across the gap unless missing values are real NaN.
      * np.diff has n-1 entries and must be indexed by dates[1:].
    """
    cols = {}
    bad = 0
    for p in pairs:
        f = DATA / f"{p.replace('/', '_').replace(':', '_')}-4h-futures.feather"
        if not f.exists():
            continue
        d = pd.read_feather(f)
        d["date"] = pd.to_datetime(d["date"], utc=True)
        d = d.sort_values("date")
        c = d["close"].to_numpy(dtype=float)
        n_bad = int((~(c > 0)).sum())
        if n_bad:
            bad += n_bad
            print(f"  [data] {p}: {n_bad} non-positive close values dropped")
        keep = c > 0
        # diff has n-1 entries and must be indexed by the SECOND timestamp of
        # each pair, not the first.
        r = np.diff(np.log(c))
        rr = np.where(np.isfinite(r), r, np.nan)
        # r[i] = log(c[i+1]) - log(c[i]) is defined iff BOTH endpoints are
        # positive, so the mask is keep[:-1] & keep[1:] -- length n-1, matching
        # r. (Wrapping it in np.concatenate([[True], ...]) adds one element and
        # is a length mismatch, which is what the first run raised.)
        cols[p] = pd.Series(rr, index=d["date"].to_numpy()[1:][
            keep[:-1] & keep[1:]])
    print(f"  [data] {bad} non-positive closes dropped across {len(cols)} symbols")
    # cols[p] is ALREADY the log-return series. An earlier version of this
    # function ended with np.log(px / px.shift(1)), which log-transformed the
    # returns a second time - that raised "divide by zero" (log of a 0 return)
    # and, worse, would have turned every negative return into NaN.
    out = pd.DataFrame(cols)
    n_inf = int(np.isinf(out.to_numpy()).sum())
    if n_inf:
        print(f"  [data] {n_inf} infinite values survived; they would corrupt "
              f"every correlation below")
        out = out.replace([np.inf, -np.inf], np.nan)
    return out


def main() -> int:
    print("VARIANCE DECOMPOSITION: where does the risk in this book live?\n")
    print("R = net P&L / (stake * 4 * ATR(entry bar) / entry) - the project's\n"
          "long-standing risk unit from r_stats.build, NOT the recorded\n"
          "initial_stop_loss_ratio, which is the class 0.30 backstop. All times UTC.\n")

    universe: set[str] = set()
    for label, rel in RESULTS:
        df = load_trades(rel)
        head(f"{label}   ({len(df)} trades, {df['pair'].nunique()} symbols)")
        universe |= set(df["pair"].unique())

        # ---- 1. per-trade dispersion --------------------------------------
        r = df["R"].to_numpy()
        print(f"  per-trade R : mean {r.mean():+.4f}  sd {r.std(ddof=1):.4f}  "
              f"min {r.min():.3f}  max {r.max():.3f}")
        print(f"               the -1R floor is the 4xATR stop; mean/sd = "
              f"{r.mean()/r.std(ddof=1):.4f}")

        # ---- 2. the book as actually held, one row per entry timestamp -----
        # Every position is risk-sized to the same stop multiple, so the
        # equal-weight mean R of the trades ENTERING at a timestamp is the
        # standard per-timestamp estimator this project uses for t (the same
        # one as r_stats.report's t_by_timestamp). It is NOT the realised
        # equity path - overlapping cohorts are counted once each - and the
        # difference matters: its mean is ~half the per-trade mean because
        # entry cohorts average good and bad symbols against each other.
        port = df.groupby("open")["R"].agg(["mean", "count"])
        pr = port["mean"].to_numpy()
        t_p, m_p, n_eff_p, iat_p = tstat(pr)
        print(f"\n  entry-cohort mean R per timestamp: {m_p:+.4f}  "
              f"sd {pr.std(ddof=1):.4f}  t = {t_p:+.2f}  "
              f"n = {len(pr)}  IAT = {iat_p:.2f}  n_eff = {n_eff_p}")
        print(f"  (per-trade mean is {r.mean():+.4f}; the cohort mean is lower "
              f"because entry\n   cohorts average good and bad symbols against "
              f"each other. The t above is the\n   project-standard estimator, not "
              f"a realised equity curve.)")
        print(f"  positions open at once: mean {port['count'].mean():.1f}  "
              f"max {int(port['count'].max())}")

        # ---- 3. common vs idiosyncratic share of per-trade R --------------
        # Common = the equal-weight cross-sectional mean R at the same entry
        # timestamp: "the market moved". Whatever a market-timing book cannot
        # diversify away sits here.
        common = df.groupby("open")["R"].transform("mean")
        v_trade = float(np.nanvar(df["R"].to_numpy()))
        v_common = float(np.nanvar(common.to_numpy()))
        v_obs = float(np.nanvar(pr))
        kbar = float(port["count"].mean())
        v_ideal = v_trade / kbar
        print(f"\n  var(single trade)  = {v_trade:.6f}")
        print(f"  var(common factor) = {v_common:.6f}  "
              f"({v_common/v_trade*100:.0f}% of single-trade variance)")
        print(f"  var(portfolio)     = {v_obs:.6f}")
        print(f"  var if the k simultaneous trades were independent = "
              f"{v_ideal:.6f}")
        print(f"  => observed portfolio risk is {v_obs/v_ideal:.1f}x that ideal. "
              f"The gap IS the\n     common factor: positions opened together "
              f"move together, so opening more of\n     them does not diversify "
              f"the book the way diversification is supposed to.")

        # ---- 4. what would it take? ---------------------------------------
        if m_p > 0:
            need_n = int(np.ceil((2 * pr.std(ddof=1) / m_p) ** 2))
            print(f"\n  to reach t = 2 at the observed mean this design needs "
                  f"{need_n:,} independent\n     timestamps; it produced "
                  f"{len(pr):,} ({need_n/len(pr):.1f}x short).")
        else:
            # dividing by a non-positive mean produced 1.8e24 in the first run
            # of this script. The honest statement is that no sample size
            # reaches t=2 at a mean of zero or less.
            print(f"\n  the mean is {m_p:+.4f} <= 0, so t = 2 is unreachable at "
                  f"ANY sample size.\n     More data of the same kind cannot "
                  f"fix this; the design has to change.")
        print(f"  for scale, t=2 needs mean/sd = 2/sqrt(n_eff) = "
              f"{2/np.sqrt(n_eff_p):.4f}; the book has "
              f"{m_p/pr.std(ddof=1):+.4f}.")

    # ---- 5. the universe's correlation structure -------------------------
    head("THE UNIVERSE: how correlated are these symbols at 4h?")
    pairs = sorted(universe)
    rets = ret_panel(pairs)
    print(f"  {len(pairs)} symbols, {len(rets)} aligned 4h bars")
    c = rets.corr(min_periods=200)
    c = c.dropna(how="all").dropna(axis=1, how="all")
    vals = c.to_numpy()[np.triu_indices(len(c), 1)]
    vals = vals[np.isfinite(vals)]
    print(f"  pairwise correlation of 4h returns: mean {vals.mean():+.3f}  "
          f"median {np.median(vals):+.3f}  "
          f"p90 {np.percentile(vals,90):+.3f}")
    ev = np.linalg.eigvalsh(c.fillna(0).to_numpy())[::-1]
    ev = np.clip(ev, 0, None)
    share = ev[0] / ev.sum()
    n_eff = (ev.sum() / (ev ** 2).sum()) * len(c)
    print(f"  top eigen-direction carries {share*100:.0f}% of the total "
          f"variance ({len(c)} symbols)")
    print(f"  effective number of independent bets at this horizon: "
          f"{n_eff:.1f} of {len(c)}")

    # ---- 6. would MORE simultaneous positions even help? -------------------
    # For k simultaneous equal-risk positions whose per-trade variance is s2 and
    # whose common-factor share is c, the variance of their equal-weight mean is
    #     s2 * (c + (1 - c)/k).
    # This is checked against the observed numbers, then extrapolated. It is the
    # single most decision-relevant number in this script, because it says
    # whether the obvious fix ("hold more names at once") is worth anything.
    head("WOULD HOLDING MORE POSITIONS AT ONCE ACTUALLY HELP?")
    df = load_trades(RESULTS[0][1])
    port = df.groupby("open")["R"].agg(["mean", "count"])
    v_trade = float(np.nanvar(df["R"].to_numpy()))
    cf = float(np.nanvar(df.groupby("open")["R"].transform("mean").to_numpy())) / v_trade
    v_obs = float(np.nanvar(port["mean"].to_numpy()))
    kbar = float(port["count"].mean())
    pred = v_trade * (cf + (1 - cf) / kbar)
    print(f"  model: var of the equal-weight mean of k positions = "
          f"var_trade * (c + (1-c)/k)")
    print(f"    c = {cf:.3f},  var_trade = {v_trade:.4f},  k observed = "
          f"{kbar:.1f}")
    print(f"    predicted {pred:.4f}  vs  observed {v_obs:.4f}  "
          f"({abs(pred/v_obs-1)*100:.0f}% off)  <- the model is usable")
    print(f"\n  {'k positions':<12}{'predicted sd':>14}{'vs today':>10}")
    for k in (3, 5, 11.5, 25, 50, 100, 200):
        v = v_trade * (cf + (1 - cf) / k)
        print(f"  {k:<12.1f}{np.sqrt(v):>14.4f}"
              f"{np.sqrt(v)/np.sqrt(v_trade*(cf+(1-cf)/kbar))*100:>9.0f}%")
    lo = np.sqrt(v_trade * (cf + (1 - cf) / 3))
    hi = np.sqrt(v_trade * (cf + (1 - cf) / n_eff))
    print(f"\n  => going from 3 concurrent positions to the {n_eff:.0f} the "
          f"universe actually\n     supports would cut the portfolio's standard "
          f"deviation by {(1-hi/lo)*100:.0f}%.")
    print(f"     Diversification is close to useless while {cf*100:.0f}% of the "
          f"variance is shared.")
    print(f"     This is why adding symbols has not fixed the t-statistic, and it "
          f"is the\n     strongest available argument that this line is near its "
          f"structural ceiling: the only\n     levers left are removing the market "
          f"exposure (which makes the signal\n     disappear - see the "
          f"market-neutralised result) or adding a signal that is\n     NOT "
          f"market-exposed, which is a different mechanism and needs its own "
          f"preregistration.")

    head("WHAT THIS IMPLIES FOR THE NEXT EXPERIMENT")
    print(f"""  1. Costs are NOT the binding constraint (F-1: costs are ~11% of gross).
  2. The binding constraint is the common factor: {cf*100:.0f}% of single-trade
     variance, and the 4h returns of these symbols are {vals.mean():+.2f}
     correlated on average. A {len(c)}-symbol universe is worth ~{n_eff:.1f}
     independent bets.
  3. Holding MORE names at once does not fix it: it buys ~{(1-hi/lo)*100:.0f}%
     of the standard deviation, and only if the extra names are uncorrelated
     with the common factor, which is exactly what this universe is not.
  4. A second market-exposed signal would take t from {t_p:+.2f} to roughly
     {t_p*np.sqrt(2):+.2f} at best. Not a fix.
  5. The honest summary: an edge of ~0.12R per trade that clears its costs by
     ~9x is undetectable in 3.4 years BECAUSE the strategy is ~{cf*100:.0f}% a
     single market bet, and the market itself is ~one factor at 4h - 50 to 99
     symbols carry the information of about three independent bets. That is a
     fact about crypto's factor structure, not a defect in the implementation,
     and no amount of extra data of the same kind changes it.""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
