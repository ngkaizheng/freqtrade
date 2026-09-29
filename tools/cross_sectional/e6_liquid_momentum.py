"""
E#6 -- momentum on the LIQUID universe. The one cell never run.

Pre-registration: PREREGISTRATION_E6.md, written before this produced a number.
The construction is byte-identical to E#3's; the only change is the universe,
and the universe is fixed by COST (top 50 by median daily quote volume is
where measure_cost.py returned the cheapest round trip), never by the signal.

Costs are MEASURED, not assumed, and the full frontier is published rather
than a single selected cell.

Run:  .venv\\Scripts\\python.exe tools\\cross_sectional\\e6_liquid_momentum.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("display.width", 230)
pd.set_option("display.max_columns", 40)

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "user_data/universe/raw_daily"
OUT = Path(__file__).resolve().parent

TOP_N = 50
FORMATION_WEEKS = (3, 6, 12, 24)
QUANTILE = 0.20
FEE_BPS_PER_SIDE = 5.0
REBASE = -0.90
BOOK_SIZES = (10_000, 50_000, 250_000, 1_000_000)
HEADLINE_PER_NAME = 10_000
COST_BPS = {10_000: 3.1, 50_000: 7.7, 250_000: 18.4, 1_000_000: 38.0}  # measured


def load_panel():
    """Returns (price panel, volume panel, symbols dropped by G7).

    G7 is evaluated, not asserted. An earlier version hardcoded it to True,
    which is a fabricated pass on a pre-registered gate -- the exact failure
    mode this project has now produced several times. On this panel the filter
    drops zero symbols, so the gate still passes, but it now passes because it
    was tested.
    """
    frames = {}
    dropped = []
    for f in sorted(RAW.glob("*_1d.csv.gz")):
        sym = f.name.replace("_1d.csv.gz", "")
        d = pd.read_csv(f)
        d["date"] = pd.to_datetime(d["date"], format="%Y-%m-%d", errors="coerce")
        d = d.dropna(subset=["date", "close", "quote_volume"]).set_index("date").sort_index()
        d = d[~d.index.duplicated()]
        d = d[d["quote_volume"] > 0]
        if (d["close"].pct_change() < REBASE).any():      # G7, applied to the DATA
            dropped.append(sym)
            continue
        frames[sym] = d
    px = pd.concat({k: v["close"] for k, v in frames.items()}, axis=1).sort_index()
    qv = pd.concat({k: v["quote_volume"] for k, v in frames.items()}, axis=1).sort_index()
    return px, qv, dropped


def build_signal(wk):
    total = pd.DataFrame(0.0, index=wk.index, columns=wk.columns)
    count = pd.DataFrame(0.0, index=wk.index, columns=wk.columns)
    for k in FORMATION_WEEKS:
        r = wk.pct_change(periods=k, fill_method=None).rank(axis=1, pct=True)
        total = total.add(r.fillna(0.0), fill_value=0.0)
        count = count.add(r.notna().astype(float), fill_value=0.0)
    sig = total / count.replace(0.0, np.nan)
    sig[count < len(FORMATION_WEEKS)] = np.nan
    return sig.astype(float)


def causality_check(wk, sig):
    """Truncation assertion, per AGENTS.md section 3. A feature that reads past
    its own timestamp changes when the panel is truncated; one that does not,
    does not."""
    cut = len(wk) // 2
    sig_a = build_signal(wk.iloc[:cut])
    shared = sig_a.iloc[: cut - 30]
    if not shared.equals(sig.reindex(shared.index).iloc[: cut - 30]):
        raise AssertionError("signal is not truncation-stable: lookahead")


def newey_west_t(x, lags=3):
    v = np.asarray(x, float)
    n = len(v)
    e = v - v.mean()
    g0 = float((e ** 2).sum()) / n
    var = g0
    for L in range(1, lags + 1):
        var += 2 * (1 - L / (lags + 1)) * float((e[L:] * e[:-L]).sum()) / n
    var = max(var, 1e-18)
    return float(v.mean() / math.sqrt(var / n)), float(math.sqrt(var / n))


def run_book(wk, sig, cost_round_trip):
    rets = wk.pct_change(fill_method=None)
    rows, detail, prev = [], [], None
    for i in range(1, len(wk) - 1):          # t+1 is the week actually earned
        t = wk.index[i]
        r = rets.iloc[i + 1]
        s = sig.loc[t]
        s = s if isinstance(s, pd.Series) else pd.Series(dtype=float)
        s = s.dropna()
        if len(s) < 20:
            continue
        s = s[s.index.isin(r.dropna().index)]
        if len(s) < 20:
            continue
        k = max(1, int(round(len(s) * QUANTILE)))
        longs, shorts = s.nlargest(k).index, s.nsmallest(k).index
        hold = longs.union(shorts)
        w = pd.Series(0.0, index=hold)
        w.loc[longs] = 0.5 / k
        w.loc[shorts] = -0.5 / k
        gross = float(w.reindex(r.index).fillna(0.0).mul(r).sum())
        turnover = (float(w.abs().sum()) if prev is None
                    else float((w - prev.reindex(w.index).fillna(0.0)).abs().sum()))
        prev = w
        c = turnover * cost_round_trip
        rows.append({"week": t, "gross": gross, "cost": c, "net": gross - c,
                     "turnover": turnover})
        for nm, wt in w.items():
            if wt != 0:
                detail.append({"week": t, "symbol": nm, "weight": wt,
                               "contrib": wt * float(r.get(nm, 0.0))})
    return pd.DataFrame(rows), pd.DataFrame(detail)


def stats(res):
    if res.empty:
        return None
    net = res["net"]
    t_nw, se = newey_west_t(net)
    v = net.to_numpy(float)
    x = v - v.mean()
    den = float((x ** 2).sum())
    tau = 1.0
    for lag in range(1, 13):
        rho = float((x[lag:] * x[:-lag]).sum() / den)
        if rho <= 0:
            break
        tau += 2 * rho
    n = len(v)
    t_adj = t_nw * math.sqrt(min(1.0, 1.0 / max(tau, 1.0)))
    eq = (1 + net).cumprod()
    dd = float((eq / eq.cummax() - 1).min())
    return {
        "rebalances": n,
        "mean_gross_pct": float(res["gross"].mean() * 100),
        "mean_cost_pct": float(res["cost"].mean() * 100),
        "mean_net_pct": float(net.mean() * 100),
        "turnover": float(res["turnover"].mean()),
        "nw_t": t_nw, "se": se, "iat": tau, "t_adjusted": t_adj,
        "annualised_sharpe": float(net.mean() / net.std(ddof=1) * math.sqrt(52)),
        "annualised_return_pct": float(net.mean() * 52 * 100),
        "cum_pct": float((eq.iloc[-1] - 1) * 100),
        "max_dd_pct": dd * 100,
    }


def main() -> int:
    px, qv, dropped_symbols = load_panel()
    med = qv.median()
    uni = list(med.nlargest(TOP_N).index)
    px = px[uni]
    print(f"universe: top {TOP_N} by median daily quote volume "
          f"(median {med[uni].median()/1e6:.0f}m USD/day)")
    print(f"  fixed by cost, not by signal.  survivor-only universe.\n")

    wk = px.resample("W-FRI").last()
    wk = wk.dropna(axis=1, how="all")
    wk = wk.dropna(thresh=int(0.8 * wk.shape[1]))
    print(f"weekly panel: {wk.shape[0]} weeks x {wk.shape[1]} symbols, "
          f"{wk.index[0].date()} -> {wk.index[-1].date()}")

    sig = build_signal(wk)
    causality_check(wk, sig)

    print()
    print("=" * 96)
    print("COST FRONTIUM  (the frontier, not a selected cell)")
    print("=" * 96)
    rows_all, detail_all = {}, {}
    for size in BOOK_SIZES:
        all_in = (COST_BPS[size] + 2 * FEE_BPS_PER_SIDE) / 1e4
        res, det = run_book(wk, sig, all_in)
        s = stats(res)
        rows_all[size] = s
        detail_all[size] = det
        if s is None:
            print(f"  ${size:>9,}/name   no rebalances")
            continue
        mark = "  <-- HEADLINE (pre-committed)" if size == HEADLINE_PER_NAME else ""
        print(f"  ${size:>9,}/name  all-in {COST_BPS[size]+2*FEE_BPS_PER_SIDE:>5.1f} bps   "
              f"net/summation {s['annualised_return_pct']:>+7.1f}%/yr   "
              f"SR {s['annualised_sharpe']:>+6.2f}   t_adj {s['t_adjusted']:>+6.2f}   "
              f"dd {s['max_dd_pct']:>+6.1f}%{mark}")

    head = rows_all[HEADLINE_PER_NAME]
    res2, _ = run_book(wk, sig, 2 * (COST_BPS[HEADLINE_PER_NAME] + 2 * FEE_BPS_PER_SIDE) / 1e4)
    s2 = stats(res2)

    print()
    print("=" * 96)
    print("HEADLINE DETAIL  ($10,000 per name, $500,000 book)")
    print("=" * 96)
    for k, v in head.items():
        if isinstance(v, float):
            print(f"  {k:<22} {v:+.5f}")
        else:
            print(f"  {k:<22} {v}")

    res_h, det_h = run_book(wk, sig,
                            (COST_BPS[HEADLINE_PER_NAME] + 2 * FEE_BPS_PER_SIDE) / 1e4)
    res_h["year"] = pd.to_datetime(res_h["week"]).dt.year
    yearly = res_h.groupby("year")["net"].agg(["mean", "count"])
    yearly["sum"] = res_h.groupby("year")["net"].sum()
    print()
    print("  by year:")
    print(yearly.round(6).to_string())

    if not det_h.empty:
        sym = det_h.groupby("symbol")["contrib"].sum().sort_values(ascending=False)
        total = sym.sum()
        share = sym / total if total else sym * 0
        pos_frac = float((sym > 0).mean())
        top_share = float(share.iloc[0])
        print()
        print("  by symbol (top 10):")
        print(pd.DataFrame({"contrib": sym.head(10).round(5),
                            "share": share.head(10).round(3)}).to_string())
        print(f"  positive-symbol fraction  {pos_frac:.3f}")
        print(f"  largest symbol share      {top_share:.3f}")
    else:
        pos_frac = top_share = None

    print()
    print("=" * 96)
    print("GATES (pre-registered)")
    print("=" * 96)
    gates = {
        "G1 net > 0 at measured cost": head["mean_net_pct"] > 0,
        "G2 net > 0 at 2x cost": (s2 or {}).get("mean_net_pct", -1) > 0,
        "G3 |t_adj| >= 2.0": abs(head["t_adjusted"]) >= 2.0,
        "G4 annualised net Sharpe >= 0.95": head["annualised_sharpe"] >= 0.95,
        "G5 positive in >= 60% of years": float((yearly["sum"] > 0).mean()) >= 0.60,
        "G6 positive in >= 60% of symbols": (pos_frac is not None and pos_frac >= 0.60),
        "G6b largest symbol share <= 0.35": (top_share is not None and top_share <= 0.35),
        "G7 no rebased names in the book": len(dropped_symbols) == 0,
    }
    for k, v in gates.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    print(f"\n  VERDICT: {'PASS' if all(gates.values()) else 'FAIL'} "
          f"({sum(gates.values())}/{len(gates)})")

    out = {
        "experiment": "E#6",
        "spec": "tools/cross_sectional/PREREGISTRATION_E6.md",
        "universe": "top 50 by median daily quote volume",
        "survivor_only": True,
        "headline_per_name_usd": HEADLINE_PER_NAME,
        "frontier": {str(k): (None if v is None else {kk: round(vv, 6) for kk, vv in v.items()})
                     for k, v in rows_all.items()},
        "double_cost": s2,
        "gates": {k: bool(v) for k, v in gates.items()},
        "verdict": "PASS" if all(gates.values()) else "FAIL",
    }
    (OUT / "e6_result.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    res_h.to_csv(OUT / "e6_rebalances.csv", index=False)
    print(f"\nwritten to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
