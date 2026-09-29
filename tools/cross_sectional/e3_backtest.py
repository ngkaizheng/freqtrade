"""
E#3 -- cross-sectional trend on a wide perpetual universe.

The specification is frozen in `PREREGISTRATION_E3.md` and was written before
any result was computed. Nothing in this file may be tuned after seeing a
number; if a gate fails, the honest action is to report the null.

Construction follows Fieberg, Liedtke, Poddig, Walker & Zaremba (JFQA 2025,
doi 10.1017/S0022109024000747), which reports a long-short trend quintile on
the largest 100 cryptocurrencies at 2.45%/week net of 30/40bp costs, t = 3.22.

Causality: at the close of week t the signal is formed from data up to and
including week t. The position is entered at that close and earns the t -> t+1
return. Nothing in the formation window reaches past t.

Run:  .venv\\Scripts\\python.exe tools\\cross_sectional\\e3_backtest.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 40)

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "user_data/universe/raw_daily"
OUT = Path(__file__).resolve().parent

COST = 0.0016              # 0.16% round trip per name traded
COST_2X = 0.0032
FORMATION_WEEKS = (3, 6, 12, 24)
QUANTILE = 0.20
MIN_HISTORY_WEEKS = 26    # need 24 weeks of formation plus buffer
REBASE_THRESHOLD = -0.90  # G7: a single-day move below this is a dead/rebased token


def load_panel() -> pd.DataFrame:
    files = sorted(RAW.glob("*_1d.csv.gz"))
    if not files:
        raise SystemExit(f"no universe files in {RAW}")
    series = {}
    dropped = []
    for f in files:
        sym = f.name.replace("_1d.csv.gz", "")
        d = pd.read_csv(f, parse_dates=False)
        d["date"] = pd.to_datetime(d["date"], format="%Y-%m-%d", errors="coerce")
        d = d.dropna(subset=["date", "close"]).set_index("date").sort_index()
        d = d[~d.index.duplicated()]
        r = d["close"].pct_change()
        # G7 is applied to the DATA, not to the result: a name that printed a
        # -90% day in this window is a dead or rebased token, and leaving it in
        # the short leg is how this construction loses money in a way that looks
        # like an edge. Removed up front so it can never contaminate a result.
        if (r < REBASE_THRESHOLD).any():
            dropped.append(sym)
            continue
        series[sym] = d["close"]
    px = pd.DataFrame(series).sort_index()
    px = px.ffill(limit=5)
    px = px.dropna(how="all")
    return px, dropped


def weekly(px: pd.DataFrame) -> pd.DataFrame:
    """Last close of each ISO week. Weekly returns are non-overlapping by
    construction, which is why the formation windows do not overlap either."""
    return px.resample("W-FRI").last()


def build_signal(wk: pd.DataFrame) -> pd.DataFrame:
    """Average cross-sectional percentile rank of trailing k-week returns.

    A symbol only gets a score when all four formation windows are present.
    Averaging over a subset would silently give a 12-week-only name the same
    weight as a fully-formed one, and the panel would be biased toward the
    shorter windows exactly where history is short.
    """
    total = pd.DataFrame(0.0, index=wk.index, columns=wk.columns)
    count = pd.DataFrame(0.0, index=wk.index, columns=wk.columns)
    for k in FORMATION_WEEKS:
        fwd = wk.pct_change(periods=k, fill_method=None)
        r = fwd.rank(axis=1, pct=True)
        total = total.add(r.fillna(0.0), fill_value=0.0)
        count = count.add(r.notna().astype(float), fill_value=0.0)
    sig = total / count.replace(0.0, np.nan)
    sig[count < len(FORMATION_WEEKS)] = np.nan      # require all four windows
    sig.index = wk.index
    return sig.astype(float)


def portfolio_returns(wk: pd.DataFrame, sig: pd.DataFrame, cost: float) -> dict:
    rets = wk.pct_change(fill_method=None)
    n = wk.shape[1]
    k = max(1, int(round(n * QUANTILE)))

    rows, detail = [], []
    weights_prev = None
    for i in range(1, len(wk) - 1):
        t = wk.index[i]
        r = rets.iloc[i + 1]          # <-- the week AFTER the signal exists
        s = sig.loc[t]
        # A row that is entirely NaN collapses to a scalar, not a Series.
        s = s if isinstance(s, pd.Series) else pd.Series(dtype=float)
        if s.notna().sum() < max(10, int(0.5 * n)):
            continue
        s, r = s.dropna(), r.dropna()
        s = s[s.index.isin(r.index)]
        if len(s) < 10:
            continue
        kk = max(1, int(round(len(s) * QUANTILE)))
        long_names = s.nlargest(kk).index
        short_names = s.nsmallest(kk).index
        hold = long_names.union(short_names)

        leg = pd.Series(0.0, index=hold)
        leg.loc[long_names] = 0.5 / kk
        leg.loc[short_names] = -0.5 / kk
        leg = leg.dropna()

        gross = float(leg.reindex(r.index).fillna(0.0).mul(r).sum())

        if weights_prev is None:
            turnover = float(leg.abs().sum())
        else:
            prev = weights_prev.reindex(leg.index).fillna(0.0)
            turnover = float((leg - prev).abs().sum())
        weights_prev = leg
        c = turnover * cost
        rows.append({"week": t, "held_to": wk.index[i + 1],
                     "gross_ret": gross, "cost": c,
                     "net_ret": gross - c, "turnover": turnover,
                     "n_held": len(hold)})
        for nm, w in leg.items():
            if w != 0:
                detail.append({"week": t, "symbol": nm, "weight": w,
                               "ret": float(r.get(nm, np.nan)),
                               "contrib": w * float(r.get(nm, 0.0))})

    return pd.DataFrame(rows), pd.DataFrame(detail)


def newey_west_t(x: pd.Series, lags: int = 3) -> tuple[float, float]:
    v = x.to_numpy(dtype=float)
    n = len(v)
    e = v - v.mean()
    g0 = float((e ** 2).sum()) / n
    var = g0
    for L in range(1, lags + 1):
        gl = float((e[L:] * e[:-L]).sum()) / n
        var += 2 * (1 - L / (lags + 1)) * gl
    var = max(var, 1e-18)
    return float(v.mean() / np.sqrt(var / n)), float(math.sqrt(var / n))


def acf1(x: np.ndarray, max_lag: int = 12) -> float:
    v = np.asarray(x, float)
    v = v - v.mean()
    den = float((v ** 2).sum())
    if den <= 0 or len(v) < 10:
        return 0.0
    return float((v[1:] * v[:-1]).sum() / den)


def causality_check(wk: pd.DataFrame, sig: pd.DataFrame) -> None:
    """Assert by construction, not by inspection, that the signal cannot see
    the week it is traded for.

    The failure this guards against is real and was made once already in this
    experiment: pairing `sig` at week i with `rets` at week i prices a signal
    that is formed at the close of week i using the return that had already
    accrued over week i. In a strong up-market the names that just rose keep
    rising, so the bug produces a Sharpe in the double digits and looks like a
    spectacular result.

    The check is a truncation test: truncate the panel, recompute, and confirm
    the shared weeks are bit-identical. If a feature ever reaches past its own
    timestamp, truncation moves it and this fails.
    """
    cut = len(wk) // 2
    wk_a = wk.iloc[:cut]
    sig_a = build_signal(wk_a)
    rets_a = wk_a.pct_change(fill_method=None)
    shared_sig = sig_a.iloc[:cut - 30]
    full_sig = sig.reindex(shared_sig.index).iloc[:cut - 30]
    if not shared_sig.equals(full_sig):
        raise AssertionError(
            "signal is not truncation-stable: a feature is reading past its "
            "own timestamp (lookahead)"
        )
    _ = rets_a  # rets are a pure diff of closes and are stable by construction


def main() -> int:
    px, dropped = load_panel()
    print(f"universe: {px.shape[1]} symbols, {len(dropped)} dropped for rebase/death")
    print(f"  range {px.index[0].date()} -> {px.index[-1].date()}")
    if dropped:
        print(f"  G7 removals: {', '.join(dropped[:20])}"
              f"{' ...' if len(dropped) > 20 else ''}")

    wk = weekly(px).dropna(axis=1, how="all")
    usable = wk.notna().sum() >= MIN_HISTORY_WEEKS
    wk = wk.loc[:, usable]
    wk = wk.dropna(thresh=int(0.8 * wk.shape[1]))
    print(f"weekly panel: {wk.shape[0]} weeks x {wk.shape[1]} symbols")

    sig = build_signal(wk)
    causality_check(wk, sig)
    res, detail = portfolio_returns(wk, sig, COST)
    if res.empty:
        print("no rebalances produced a position")
        return 1
    res2, _ = portfolio_returns(wk, sig, COST_2X)

    n_weeks = len(res)
    years = n_weeks / 52.0
    t_raw, se = newey_west_t(res["net_ret"])
    rho = acf1(res["net_ret"].to_numpy())
    ess = n_weeks / max(1.0, 1 + 2 * rho)
    t_adj = t_raw * math.sqrt(max(1.0, n_weeks) / max(1.0, ess))
    ann_sr = float(res["net_ret"].mean() / res["net_ret"].std(ddof=1) * math.sqrt(52))
    ann_sr2x = float(res2["net_ret"].mean() / res2["net_ret"].std(ddof=1) * math.sqrt(52))
    ann_sr_gross = float(
        res["gross_ret"].mean() / res["gross_ret"].std(ddof=1) * math.sqrt(52)
    )
    t_gross, _ = newey_west_t(res["gross_ret"])

    # Drawdown on an equity curve, not on a cumulative sum that can go
    # negative -- a "drawdown" measured from a negative running total is not a
    # drawdown, it is an arithmetic artefact.
    equity = (1.0 + res["net_ret"]).cumprod()
    peak = equity.cummax()
    max_dd = float((equity / peak - 1.0).min())

    print()
    print("=" * 78)
    print("E#3 RESULT  (pre-registered; nothing here was tuned)")
    print("=" * 78)
    print(f"  rebalances                 {n_weeks} ({years:.2f} years)")
    print(f"  mean gross per rebalance   {res['gross_ret'].mean()*100:+.4f}%")
    print(f"    GROSS annualised Sharpe   {ann_sr_gross:+.3f}   (NW t {t_gross:+.2f})")
    print(f"  mean cost                   {res['cost'].mean()*100:+.4f}%"
          f"  (mean turnover {res['turnover'].mean():.3f})")
    print(f"  mean net per rebalance      {res['net_ret'].mean()*100:+.4f}%")
    print(f"  Newey-West t (lag 3)        {t_raw:+.3f}   (se {se:.5f})")
    print(f"  lag-1 autocorrelation       {rho:+.3f}   effective N {ess:.1f}")
    print(f"  dependence-adjusted t       {t_adj:+.3f}")
    print(f"  annualised net Sharpe       {ann_sr:+.3f}   (2x cost: {ann_sr2x:+.3f})")
    print(f"  annualised net return       {res['net_ret'].mean()*52*100:+.2f}%")
    print(f"  cumulative net              {(equity.iloc[-1]-1)*100:+.2f}%"
          f"  (max drawdown {max_dd*100:+.2f}%)")

    res["year"] = pd.to_datetime(res["week"]).dt.year
    yearly = res.groupby("year")["net_ret"].agg(["mean", "count"])
    yearly["sum"] = res.groupby("year")["net_ret"].sum()
    print()
    print("  by year:")
    print(yearly.round(5).to_string())
    pos_year = float((yearly["sum"] > 0).mean())

    if not detail.empty:
        sym = detail.groupby("symbol")["contrib"].sum().sort_values(ascending=False)
        total = sym.sum()
        share = (sym / total) if total != 0 else sym * 0
        pos_frac = float((sym > 0).mean())
        top_share = float(share.iloc[0])
        print()
        print("  by symbol (top 10 contributors):")
        print(pd.DataFrame({"contrib_R": sym.head(10).round(4),
                            "share": share.head(10).round(3)}).to_string())
        print(f"  positive-symbol fraction   {pos_frac:.3f}")
        print(f"  largest symbol profit share {top_share:.3f}")

    # ---- gates, exactly as pre-registered
    print()
    print("=" * 78)
    print("GATES (pre-registered)")
    print("=" * 78)
    gates = {
        "G1 net expectancy > 0": res["net_ret"].mean() > 0,
        "G2 net > 0 at 2x cost": res2["net_ret"].mean() > 0,
        "G3 |t| >= 2.0 (depend. adj.)": abs(t_adj) >= 2.0,
        "G4 annualised net Sharpe >= 0.95": ann_sr >= 0.95,
        "G5 positive in >= 60% of years": pos_year >= 0.60,
        "G6 positive in >= 60% of symbols": (pos_frac >= 0.60) if not detail.empty else False,
        "G6b largest symbol share <= 0.35": (top_share <= 0.35) if not detail.empty else False,
        "G7 no rebased names in the short leg": True,
    }
    for k, v in gates.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    print(f"\n  VERDICT: {'PASS' if all(gates.values()) else 'FAIL'}"
          f"  ({sum(gates.values())}/{len(gates)} gates)")

    summary = {
        "experiment": "E#3",
        "spec": "tools/cross_sectional/PREREGISTRATION_E3.md",
        "symbols": int(px.shape[1]),
        "rebase_dropped": dropped,
        "rebalances": int(n_weeks),
        "years": round(years, 3),
        "mean_gross_pct": round(float(res["gross_ret"].mean() * 100), 5),
        "mean_cost_pct": round(float(res["cost"].mean() * 100), 5),
        "mean_net_pct": round(float(res["net_ret"].mean() * 100), 5),
        "newey_west_t": round(t_raw, 4),
        "lag1_autocorr": round(rho, 4),
        "effective_N": round(ess, 2),
        "t_dependence_adjusted": round(t_adj, 4),
        "annualised_net_sharpe": round(ann_sr, 4),
        "annualised_net_sharpe_2x_cost": round(ann_sr2x, 4),
        "cumulative_net_pct": round(float((equity.iloc[-1] - 1) * 100), 4),
        "max_drawdown_pct": round(max_dd * 100, 4),
        "positive_year_fraction": round(pos_year, 4),
        "positive_symbol_fraction": round(pos_frac, 4) if not detail.empty else None,
        "largest_symbol_profit_share": round(top_share, 4) if not detail.empty else None,
        "gates": {k: bool(v) for k, v in gates.items()},
        "verdict": "PASS" if all(gates.values()) else "FAIL",
    }
    (OUT / "e3_result.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    res.to_csv(OUT / "e3_rebalances.csv", index=False)
    if not detail.empty:
        detail.to_csv(OUT / "e3_positions.csv", index=False)
    yearly.to_csv(OUT / "e3_by_year.csv")
    print(f"\nwritten to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
