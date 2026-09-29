"""
The basis leg of the cash-and-carry trade.

`tools/carry/REPORT.md` measured the FUNDING component and explicitly left the
basis unmeasured. That matters: cash-and-carry return has two legs, and in
practice the basis leg is frequently the larger and the faster one.

    long spot + short perp  =>  P&L = funding collected + (basis_entry - basis_exit)

A perpetual that trades at a premium to its index converges, and a short-perp
leg profits from that convergence regardless of what funding does. If the basis
leg is large and mean-reverting, the trade can be viable even in a period when
funding alone does not cover the harvest cost -- which is the situation
reported for the last 12 months.

Data: `user_data/data/binance_v2/canonical/` -- mark_price and index_price at
1h for 5 perpetuals, plus their own traded price. 2020-02-01 -> 2026-08-31.

Run:  .venv\\Scripts\\python.exe tools\\carry\\basis_leg.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 30)

ROOT = Path(__file__).resolve().parents[2]
CANON = ROOT / "user_data/data/binance_v2/canonical"

SPOT_TAKER = 0.0010
PERP_TAKER = 0.0005
ROUND_TRIP = 2 * (SPOT_TAKER + PERP_TAKER)      # 0.30%
HOLD_DAYS = (7, 14, 30, 90)
ENTRY_PERCENTILES = (50, 70, 80, 90, 95)


def load_basis() -> pd.DataFrame:
    """basis = mark_price / index_price - 1, on the intersection of timestamps."""
    series = {}
    for f in sorted((CANON / "mark_price").glob("*_1h.feather")):
        sym = f.name.replace("_1h.feather", "")
        mark = pd.read_feather(f)[["timestamp", "mark_price"]]
        idx = pd.read_feather(CANON / "index_price" / f.name)[["timestamp", "index_price"]]
        m = mark.dropna().set_index("timestamp")["mark_price"].astype(float)
        i = idx.dropna().set_index("timestamp")["index_price"].astype(float)
        joined = pd.concat([m.rename("mark"), i.rename("index")], axis=1, join="inner")
        joined = joined[(joined["mark"] > 0) & (joined["index"] > 0)]
        series[sym] = joined["mark"] / joined["index"] - 1.0
    return pd.DataFrame(series).sort_index()


def main() -> None:
    basis = load_basis().dropna()
    print(f"symbols {basis.shape[1]}   hourly observations {len(basis):,}   "
          f"{basis.index[0].date()} -> {basis.index[-1].date()}")
    years = (basis.index[-1] - basis.index[0]).days / 365.25
    print(f"span {years:.2f} years\n")

    # ------------------------------------------------------ the raw premium
    print("=" * 78)
    print("A. IS THERE A PERSISTENT PERP PREMIUM?")
    print("=" * 78)
    rows = []
    for s in basis.columns:
        b = basis[s] * 100
        rows.append({
            "symbol": s,
            "mean_bps": round(b.mean() * 100, 1),
            "median_bps": round(b.median() * 100, 1),
            "p05_bps": round(b.quantile(0.05) * 100, 1),
            "p95_bps": round(b.quantile(0.95) * 100, 1),
            "pct_bars_premium": round((b > 0).mean() * 100, 1),
        })
    print(pd.DataFrame(rows).to_string(index=False))
    print(f"\n  mean basis across all symbols: {basis.mean().mean()*1e4:+.1f} bps")
    print("  A persistent positive mean is the raw material of the trade: the")
    print("  premium exists because perp longs pay for leverage, and shorts supply it.")

    # ------------------------------------------------- does it mean-revert
    print()
    print("=" * 78)
    print("B. DOES IT MEAN-REVERT? (lag-1 autocorrelation of the 24h change)")
    print("=" * 78)
    daily = basis.resample("D").last().dropna()
    acf = {}
    for s in daily.columns:
        d = daily[s].dropna()
        lag1 = float(d.autocorr(1))
        half = d.autocorr(24)
        acf[s] = (lag1, half)
        print(f"  {s:<9} lag-1 day {lag1:+.3f}   lag-24 day {half:+.3f}")
    mean_lag1 = np.mean([v[0] for v in acf.values()])
    print(f"\n  mean lag-1 {mean_lag1:+.3f}")
    if mean_lag1 < 0.3:
        print("  Low persistence means the premium does NOT drift away. It is a")
        print("  level around which it oscillates, which is what a harvestable")
        print("  mean-reversion looks like.")
    else:
        print("  High persistence means the premium is a slow-moving level, not an")
        print("  oscillation. Shorting it is a directional bet on the basis falling.")

    # ------------------------------------------- the trade, net of cost
    print()
    print("=" * 78)
    print("C. THE BASIS TRADE, NET OF THE HARVEST COST")
    print("=" * 78)
    print("""
Rule: short the perp premium when it is above an entry percentile of its own
trailing 1-year distribution, and close when it falls back to the median. The
spot leg is price-matched, so the pair is direction-neutral and earns the
convergence. Cost is one 0.30% round trip per completed cycle.

"Completed cycle" counts only: an open position at the end of the sample is
excluded, because closing it would realise a cost with no evidence yet that the
convergence happened.
""")

    results = []
    for sym in basis.columns:
        s = basis[sym]
        for lookback_days in (365,):
            roll = s.rolling(24 * lookback_days, min_periods=24 * 60)
            for pct in ENTRY_PERCENTILES:
                thr = roll.quantile(pct / 100.0)
                mid = roll.quantile(0.50)
                long_only = s > thr
                in_pos = False
                cycles, gross, held_bars = 0, 0.0, 0
                for value, high, level in zip(s.to_numpy(), thr.to_numpy(), mid.to_numpy()):
                    if not np.isfinite(high) or not np.isfinite(level):
                        continue
                    if not in_pos and value > high:
                        in_pos, entry = True, value
                    elif in_pos and value <= level:
                        in_pos = False
                        gross += entry - value
                        cycles += 1
                if cycles == 0:
                    continue
                net = gross - cycles * ROUND_TRIP
                results.append({
                    "symbol": sym,
                    "entry_pct": pct,
                    "cycles": cycles,
                    "cycles_per_year": round(cycles / years, 2),
                    "gross_total_%": round(gross * 100, 2),
                    "net_total_%": round(net * 100, 2),
                    "net_per_cycle_bps": round(net / cycles * 1e4, 1),
                    "net_annualised_%": round(net / years * 100, 2),
                })

    res = pd.DataFrame(results)
    if res.empty:
        print("  no completed cycles; the basis never reverted to its median after entry")
    else:
        agg = (res.groupby("entry_pct")
               .agg(symbols=("symbol", "nunique"),
                    cycles=("cycles", "sum"),
                    net_per_cycle_bps=("net_per_cycle_bps", "mean"),
                    net_annualised_pct=("net_annualised_%", "mean"))
               .round(2).reset_index())
        print("  pooled across symbols, by entry percentile:")
        print(agg.to_string(index=False))
        best = agg.loc[agg["net_per_cycle_bps"].idxmax()]
        print(f"\n  best entry percentile: {int(best['entry_pct'])}"
              f"  ->  {best['net_per_cycle_bps']} bps net per cycle"
              f"  ->  {best['net_annualised_pct']}%/yr")

    # ------------------------------------------------------ the recent leg
    print()
    print("=" * 78)
    print("D. IS THE BASIS TRADE LIVE RIGHT NOW?")
    print("=" * 78)
    eq = basis.mean(axis=1)
    for days in (30, 90, 365):
        w = eq.tail(24 * days)
        print(f"  last {days:>3}d  mean basis {w.mean()*1e4:+7.1f} bps   "
              f"p90 {w.quantile(0.9)*1e4:7.1f} bps   p10 {w.quantile(0.1)*1e4:7.1f} bps")
    full_p90 = eq.quantile(0.90)
    now = eq.tail(24 * 30).mean()
    print(f"\n  full-sample p90 basis : {full_p90*1e4:+.1f} bps")
    print(f"  last 30d mean basis   : {now*1e4:+.1f} bps")
    edge_bps = (full_p90 - now) * 1e4
    print(f"  entry edge available  : {edge_bps:.1f} bps")
    print(f"  round-trip cost       : {ROUND_TRIP*1e4:.0f} bps")
    print(f"  -> {'VIABLE' if edge_bps > ROUND_TRIP*1e4 else 'NOT VIABLE'} "
          f"on basis alone today"
          f" (needs the entry premium to exceed the {ROUND_TRIP*1e4:.0f} bps cost)")

    basis.to_csv(Path(__file__).resolve().parent / "basis_series.csv.gz",
                 compression="gzip")


if __name__ == "__main__":
    main()
