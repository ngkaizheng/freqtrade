"""
E#7 -- time-series momentum at its canonical horizon, NET LONG.

Pre-registration: PREREGISTRATION_E7.md, written before any result.

The distinction from everything tested so far: the position is NET LONG and the
edge is the market's DIRECTION, not cross-sectional dispersion. E#6 established
that a dollar-neutral book captures 0.39 of upside and 1.13 of downside, which
is structurally wrong for "make money in a bull market" regardless of whether
the signal is any good.

Buy-and-hold on the same universe is the benchmark throughout, because the
claim being tested is relative to it.

Run:  .venv\\Scripts\\python.exe tools\\cross_sectional\\e7_timeseries.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("display.width", 240)
pd.set_option("display.max_columns", 40)

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "user_data/universe/raw_daily"
OUT = Path(__file__).resolve().parent

TOP_N = 50
LOOKBACKS = (63, 126, 252)
PRIMARY_LOOKBACK = 126
SKIP = 21
FEE_BPS_PER_SIDE = 5.0
REBASE = -0.90
COST_BPS = {10_000: 3.6, 50_000: 8.5, 250_000: 24.5, 1_000_000: 73.1}   # measured MEAN
HEADLINE_PER_NAME = 10_000
BULL_YEARS = (2023, 2024)
BEAR_YEAR = 2022


def load_panel():
    frames, dropped = {}, []
    for f in sorted(RAW.glob("*_1d.csv.gz")):
        sym = f.name.replace("_1d.csv.gz", "")
        d = pd.read_csv(f)
        d["date"] = pd.to_datetime(d["date"], format="%Y-%m-%d", errors="coerce")
        d = d.dropna(subset=["date", "close", "quote_volume"]).set_index("date").sort_index()
        d = d[~d.index.duplicated()]
        d = d[d["quote_volume"] > 0]
        if (d["close"].pct_change() < REBASE).any():
            dropped.append(sym)
            continue
        frames[sym] = d
    px = pd.concat({k: v["close"] for k, v in frames.items()}, axis=1).sort_index()
    qv = pd.concat({k: v["quote_volume"] for k, v in frames.items()}, axis=1).sort_index()
    return px, qv, dropped


def monthly_end_index(dates: pd.DatetimeIndex) -> pd.DatetimeIndex:
    s = pd.Series(1.0, index=dates)
    m = s.resample("ME").last().dropna()
    return pd.DatetimeIndex(m.index)


def newey_west_t(x, lags=3):
    v = np.asarray(x, float)
    n = len(v)
    e = v - v.mean()
    g0 = float((e ** 2).sum()) / n
    var = g0
    for L in range(1, lags + 1):
        var += 2 * (1 - L / (lags + 1)) * float((e[L:] * e[:-L]).sum()) / n
    var = max(var, 1e-18)
    return float(v.mean() / math.sqrt(var / n)), var


def tsm(px: pd.DataFrame, lookback: int, allow_short: bool, cost_rt: float):
    """Long-only-if-uptrend (or long/short) time-series momentum, monthly.

    The lookback is in TRADING DAYS, so the signal is formed on the DAILY
    frame and then sampled at month ends. An earlier version indexed a daily
    lookback into a monthly frame and produced no rebalances at all.
    """
    me = monthly_end_index(px.index)
    m = px.reindex(me).ffill()
    # Signal on the daily frame: own trailing `lookback`-day return.
    daily_sig = px / px.shift(lookback) - 1.0
    sig_by_month = daily_sig.reindex(me).ffill()

    rows, prev = [], None
    for i in range(1, len(m)):
        pos = px.index.searchsorted(m.index[i])
        if pos + SKIP >= len(px.index):
            continue
        entry_date = px.index[pos + SKIP]
        # The holding period runs from THIS entry to the NEXT one. Holding for a
        # fixed 22 days while rebalancing monthly makes consecutive windows
        # overlap, which triple-counts the same move: an earlier version
        # reported +1021% for 2021, which is arithmetically impossible when the
        # basket itself rose 39.6%.
        nxt = px.index.searchsorted(entry_date) + 21
        if nxt >= len(px.index):
            continue
        exit_date = px.index[nxt]
        sig = sig_by_month.loc[:entry_date].iloc[-1]
        fwd = px.loc[exit_date] / px.loc[entry_date] - 1.0
        j = pd.concat([sig.rename("s"), fwd.rename("f")], axis=1).dropna()
        if len(j) < 20:
            continue
        # Weights are 1/N over the names held. An earlier version built them
        # from the RETURN series (`longs / len(longs)`) and then multiplied by
        # the return again, which summed squared returns and produced an
        # impossible CAGR of +1945% with a -0.02% drawdown.
        w = pd.Series(0.0, index=j.index)
        long_mask = j["s"] > 0
        n_long = int(long_mask.sum())
        if n_long:
            w[long_mask] = 1.0 / n_long
        n_short = 0
        if allow_short:
            short_mask = j["s"] < 0
            n_short = int(short_mask.sum())
            if n_short:
                w[short_mask] = -1.0 / n_short
        gross = float(w.mul(fwd.reindex(w.index).fillna(0.0)).sum())
        turnover = (float(w.abs().sum()) if prev is None
                    else float((w - prev.reindex(w.index).fillna(0.0)).abs().sum()))
        prev = w
        rows.append({"date": m.index[i], "gross": gross, "cost": turnover * cost_rt,
                     "net": gross - turnover * cost_rt, "turnover": turnover,
                     "n_long": n_long, "n_short": n_short})
    return pd.DataFrame(rows)


def bh(px: pd.DataFrame, cost_rt: float):
    me = monthly_end_index(px.index)
    m = px.reindex(me).ffill()
    eq = m.mean(axis=1)
    rows, prev = [], None
    for i in range(1, len(m)):
        r = eq.iloc[i] / eq.iloc[i - 1] - 1.0
        turnover = 0.0 if prev is None else abs(eq.iloc[i] / eq.iloc[i - 1] - 1.0)
        prev = eq.iloc[i]
        rows.append({"date": m.index[i], "gross": r, "net": r - turnover * cost_rt,
                     "cost": turnover * cost_rt, "turnover": turnover})
    return pd.DataFrame(rows)


def summarise(res: pd.DataFrame) -> dict:
    if res.empty:
        return {}
    net = res["net"]
    t, var = newey_west_t(net)
    eq = (1 + net).cumprod()
    years = len(net) / 12.0
    return {
        "months": len(net),
        "years": round(years, 2),
        "gross_annualised_pct": float(res["gross"].mean() * 12 * 100),
        "net_annualised_pct": float(net.mean() * 12 * 100),
        "cagr_pct": float(((1 + net).prod() ** (1 / years) - 1) * 100),
        "sharpe": float(net.mean() / net.std(ddof=1) * math.sqrt(12)),
        "nw_t": t,
        "max_dd_pct": float((eq / eq.cummax() - 1).min() * 100),
        "mean_turnover": float(res["turnover"].mean()),
    }


def main() -> int:
    px, qv, dropped = load_panel()
    med = qv.median()
    uni = list(med.nlargest(TOP_N).index)
    px = px[uni]
    print(f"universe: top {TOP_N} by median daily quote volume "
          f"({med[uni].median()/1e6:.0f}m USD/day), {px.shape[0]} daily bars")
    print(f"  G7 pre-removed symbols: {len(dropped)} (evaluated, not asserted)")
    print(f"  window {px.index[0].date()} -> {px.index[-1].date()}\n")

    cost_rt = (COST_BPS[HEADLINE_PER_NAME] + 2 * FEE_BPS_PER_SIDE) / 1e4
    print(f"headline cost: {COST_BPS[HEADLINE_PER_NAME]} bps mean book + "
          f"{2*FEE_BPS_PER_SIDE} bps fee = {cost_rt*1e4:.1f} bps round trip\n")

    bench = bh(px, cost_rt)
    b = summarise(bench)
    print("=" * 96)
    print("BENCHMARK: buy-and-hold, equal weight, the same universe, same cost")
    print("=" * 96)
    for k, v in b.items():
        print(f"  {k:<24} {v:+.3f}" if isinstance(v, float) else f"  {k:<24} {v}")

    by_year_bh = bench.set_index("date")["net"].groupby(
        bench.set_index("date").index.year).apply(lambda s: (1 + s).prod() - 1)
    print()
    print("  buy-and-hold by year:")
    print("  " + "  ".join(f"{y}:{v*100:+.1f}%" for y, v in by_year_bh.items()))

    primary_res = primary_s = primary_by_year = None
    for allow_short, label in [(False, "LONG/CASH  (primary structure)"),
                               (True, "LONG/SHORT (canonical MOP form)")]:
        print()
        print("=" * 96)
        print(label)
        print("=" * 96)
        for L in LOOKBACKS:
            res = tsm(px, L, allow_short, cost_rt)
            s = summarise(res)
            if not s:
                print(f"  lookback {L:>3}d   no rebalances")
                continue
            by_year = res.set_index("date")["net"].groupby(
                res.set_index("date").index.year).apply(lambda x: (1 + x).prod() - 1)
            tag = "  <-- PRIMARY (pre-committed)" if L == PRIMARY_LOOKBACK and not allow_short else ""
            print(f"\n  lookback {L:>3}d   months {s['months']}   turnover {s['mean_turnover']:.3f}")
            print(f"    net annualised  {s['net_annualised_pct']:+7.2f}%   "
                  f"CAGR {s['cagr_pct']:+7.2f}%   Sharpe {s['sharpe']:+6.2f}   "
                  f"t {s['nw_t']:+6.2f}   maxDD {s['max_dd_pct']:+7.2f}%{tag}")
            print("    by year: " + "  ".join(f"{y}:{v*100:+.1f}%" for y, v in by_year.items()))

            if L == PRIMARY_LOOKBACK and not allow_short:
                primary_res, primary_s, primary_by_year = res, s, by_year
                bull = np.mean([primary_by_year.get(y, 0) / by_year_bh[y]
                                for y in BULL_YEARS if y in by_year_bh and by_year_bh[y] > 0])
                bear = primary_by_year.get(BEAR_YEAR, 0) / by_year_bh.get(BEAR_YEAR, 1e-9)
                print(f"\n    CAPTURE vs buy-and-hold in {BULL_YEARS}: {bull*100:+.0f}%")
                print(f"    ratio vs buy-and-hold in {BEAR_YEAR}: {bear:.2f}x "
                      f"(1.00 = same as holding)")

    # gates on the primary
    print()
    print("=" * 96)
    print("GATES (pre-registered, on LONG/CASH lookback 126)")
    print("=" * 96)
    res, s, by_year = primary_res, primary_s, primary_by_year
    bull_capture = float(np.mean([by_year.get(y, 0) / by_year_bh[y]
                                  for y in BULL_YEARS if y in by_year_bh and by_year_bh[y] > 0]))
    bear_ratio = float(by_year.get(BEAR_YEAR, 0) / by_year_bh[BEAR_YEAR])
    gates = {
        "G1 net CAGR > 0": s["cagr_pct"] > 0,
        "G2 |t| >= 2.0": abs(s["nw_t"]) >= 2.0,
        "G3 Sharpe >= 0.75": s["sharpe"] >= 0.75,
        "G4 bull capture >= 50%": bull_capture >= 0.50,
        "G4b 2022 loss no worse than holding": bear_ratio >= 1.0,
        "G5 max DD better than buy-and-hold": s["max_dd_pct"] > b["max_dd_pct"],
        "G6 no rebase names in the book": len(dropped) == 0,
    }
    for k, v in gates.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    print(f"\n  VERDICT: {'PASS' if all(gates.values()) else 'FAIL'} "
          f"({sum(gates.values())}/{len(gates)})")
    print(f"\n  buy-and-hold for reference: CAGR {b['cagr_pct']:+.2f}%  "
          f"maxDD {b['max_dd_pct']:+.2f}%  Sharpe {b['sharpe']:+.2f}")

    out = {
        "experiment": "E#7",
        "spec": "tools/cross_sectional/PREREGISTRATION_E7.md",
        "universe": "top 50 by median daily quote volume",
        "cost_round_trip_bps": cost_rt * 1e4,
        "buy_and_hold": b,
        "buy_and_hold_by_year_pct": {str(y): round(v * 100, 2) for y, v in by_year_bh.items()},
        "primary": s,
        "primary_by_year_pct": {str(y): round(v * 100, 2) for y, v in by_year.items()},
        "bull_capture": round(bull_capture, 4),
        "bear_2022_ratio": round(bear_ratio, 4),
        "gates": {k: bool(v) for k, v in gates.items()},
        "verdict": "PASS" if all(gates.values()) else "FAIL",
    }
    (OUT / "e7_result.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwritten {OUT / 'e7_result.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
