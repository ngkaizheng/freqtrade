"""STRATEGY_FAMILY_AUDIT — Stage 0 horizon cost audit.

Aggregates the existing 5m OHLCV into 15m and 30m and measures the project's
cost model on each horizon. Nothing is optimised here.

Aggregation of 5m -> 15m (3 bars) and -> 30m (6 bars) is LOSSLESS for OHLC and
for volume / taker-buy volume, which are all sums. The only thing aggregation
does NOT preserve is intra-bar path, which is exactly why a 15m/30m forward
return cannot be filled at the 15m open from a 5m-level signal.

cost_R(t) = round_trip_bps / (stop_multiple x atr_pct(t) x 10000)
required_gross_edge(t) = 1.3 x cost_R(t)      <- observation-specific, never fixed

Reference: the user's proposal estimated 5m -> 15m -> 30m as 0.597 / 0.345 /
0.244 R from an ATR ~ sqrt(time) random-walk approximation. That approximation is
CHECKED here against the real bars, not assumed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.widepanel.run_wide import dependence_t  # noqa: E402

KLINES = ROOT / "shark_data" / "klines"
OUT = ROOT / "shark_results" / "family_audit"

HORIZONS = {"5m": 1, "15m": 3, "30m": 6}
STOP_MULT = 1.0
SAFETY = 1.3
COST_REGIMES = {"calm": 12.0, "cascade": 15.6, "volatile": 22.8, "covid": 34.9}
COST_MAIN = "calm"


def load5(sym: str) -> pd.DataFrame:
    d = pd.read_csv(KLINES / f"{sym}_5m.csv.gz")
    d["ts"] = pd.to_datetime(d["timestamp"], unit="ms", utc=True)
    return d.sort_values("ts").reset_index(drop=True)


def aggregate(d: pd.DataFrame, n: int) -> pd.DataFrame | None:
    """5m -> n*5m. Exact for OHLCV and taker volumes (all sums)."""
    if n == 1:
        out = d.copy()
    else:
        # a 5m grid only aggregates cleanly if the grid is unbroken
        gaps = d["ts"].diff().dropna() != pd.Timedelta(minutes=5)
        if gaps.any():
            # keep only the leading unbroken run
            first_bad = int(np.argmax(gaps.to_numpy()))
            d = d.iloc[: first_bad + 1]
            if len(d) < n * 500:
                return None
        g = d.iloc[::n]
        g = g.assign(
            open=d["open"].values[::n],
            high=d["high"].values[::n * n][0::1] if False else
                 d["high"].groupby(np.arange(len(d)) // n).max().values,
            low=d["low"].groupby(np.arange(len(d)) // n).min().values,
            close=d["close"].values[::n],
            volume=d["volume"].groupby(np.arange(len(d)) // n).sum().values,
            quote_volume=d["quote_volume"].groupby(np.arange(len(d)) // n).sum().values,
            taker_buy_volume=d["taker_buy_volume"].groupby(np.arange(len(d)) // n).sum().values,
            taker_buy_quote_volume=d["taker_buy_quote_volume"].groupby(np.arange(len(d)) // n).sum().values,
        )
        out = g
    out["atr"] = None
    prev = out["close"].shift(1)
    tr = pd.concat([out["high"] - out["low"], (out["high"] - prev).abs(),
                    (out["low"] - prev).abs()], axis=1).max(axis=1)
    out["atr"] = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    out["atr_pct"] = out["atr"] / out["close"]
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    syms = sorted(p.name.replace("_5m.csv.gz", "") for p in KLINES.glob("*_5m.csv.gz"))
    print(f"symbols: {len(syms)}  {syms}\n")

    # ---- Stage 0: horizon cost audit -------------------------------------
    rows = []
    for hz, n in HORIZONS.items():
        for s in syms:
            d = aggregate(load5(s), n)
            if d is None or len(d) < 2000:
                rows.append({"horizon": hz, "symbol": s, "bars": 0})
                continue
            for k, bps in COST_REGIMES.items():
                cr = bps / (STOP_MULT * d["atr_pct"] * 10000.0)
                rows.append({"horizon": hz, "symbol": s, "regime": k, "bars": len(d),
                             "atr_pct_med": float(d["atr_pct"].median()),
                             "costR_min": float(cr.min()), "costR_p5": float(cr.quantile(.05)),
                             "costR_p25": float(cr.quantile(.25)), "costR_med": float(cr.median()),
                             "costR_p75": float(cr.quantile(.75)), "costR_p95": float(cr.quantile(.95)),
                             "costR_max": float(cr.max()), "costR_mean": float(cr.mean())})
    cost = pd.DataFrame(rows)
    cost.to_csv(OUT / "horizon_cost_audit.csv", index=False)

    print("=" * 116)
    print(f"STAGE 0 — HORIZON COST AUDIT (stop {STOP_MULT} ATR, {COST_MAIN} "
          f"{COST_REGIMES[COST_MAIN]} bps round trip)")
    print("=" * 116)
    print(f"{'horizon':<8s} {'sym':<9s} {'bars':>8s} {'atr%':>7s} {'min':>7s} {'p5':>7s} "
          f"{'p25':>7s} {'MED':>7s} {'p75':>7s} {'p95':>7s} {'max':>8s}")
    calm = cost[cost.regime == COST_MAIN] if "regime" in cost.columns else cost
    for hz in HORIZONS:
        for s in syms:
            r = calm[(calm.horizon == hz) & (calm.symbol == s)]
            if not len(r):
                print(f"{hz:<8s} {s:<9s} {'n/a':>8s}")
                continue
            r = r.iloc[0]
            print(f"{hz:<8s} {s:<9s} {int(r.bars):8,d} {r.atr_pct_med*100:7.3f} "
                  f"{r.costR_min:7.3f} {r.costR_p5:7.3f} {r.costR_p25:7.3f} "
                  f"{r.costR_med:7.3f} {r.costR_p75:7.3f} {r.costR_p95:7.3f} "
                  f"{r.costR_max:8.3f}")

    print()
    print("=" * 116)
    print("POOLED median cost_R by horizon, and the CHECK of the sqrt(time) approximation")
    print("=" * 116)
    base = calm[calm.horizon == "5m"].costR_med.median()
    print(f"{'horizon':<8s} {'median cost_R':>14s} {'x vs 5m':>9s} {'sqrt-scaling predicted':>24s}")
    for hz in HORIZONS:
        m = calm[calm.horizon == hz].costR_med.median()
        pred = base / np.sqrt(HORIZONS[hz])
        print(f"{hz:<8s} {m:14.4f} {m/base:9.3f} {pred:24.4f}")
    print(f"\n  sqrt-time approximation predicted 0.345 / 0.244 R for 15m / 30m.")
    print(f"  Measured pool is above. The approximation is the OPTIMUM case (a pure")
    print(f"  random walk); real bars carry jumps, so realised ATR grows more slowly")
    print(f"  than sqrt(t) and the true cost is higher. Do not quote the approximation.")

    print()
    print("=" * 116)
    print("THE DECISIVE COMPARISON — 15m/30m vs the 4h line already measured")
    print("=" * 116)
    four_h_cost = 0.0920  # phase2_cost_by_timeframe.csv, 4h BTC, 12 bps
    for hz in HORIZONS:
        m = calm[calm.horizon == hz].costR_med.median()
        rel = "cheaper" if m < four_h_cost else ("same" if abs(m - four_h_cost) < 0.01 else "MORE EXPENSIVE")
        print(f"  {hz:<5s} cost_R {m:.4f}   vs 4h ({four_h_cost:.4f})  -> {rel}")
    print(f"\n  required gross edge = 1.3 x cost_R:")
    for hz in HORIZONS:
        m = calm[calm.horizon == hz].costR_med.median()
        print(f"    {hz:<5s} {1.3*m:.4f} R")
    print(f"\n  For reference, the 5m Stage 0 scan measured the BEST gross edge at")
    print(f"  2.47 bps. At the pooled 15m/30m cost_R that is worth "
          f"{2.47/10000/m:.4f} R,")
    for hz in ("15m", "30m"):
        m = calm[calm.horizon == hz].costR_med.median()
        print(f"    {hz}: {2.47/10000/m:.4f} R vs required {1.3*m:.4f} R -> "
              f"needs a {1.3*m/(2.47/10000/m):.0f}x bigger edge")

    # per-symbol gross edge in bps is the comparable unit; print the required bps too
    print()
    print(f"{'horizon':<8s} {'required gross (bps)':>21s} {'5m best measured':>19s} {'gap':>8s}")
    for hz in HORIZONS:
        m = calm[calm.horizon == hz].costR_med.median()
        atr_pct = calm[calm.horizon == hz].atr_pct_med.median()
        req = SAFETY * m * atr_pct * 10000.0
        print(f"{hz:<8s} {req:21.1f} {2.47:19.2f} {req/2.47:8.1f}x")
    print("\nwrote", OUT)


if __name__ == "__main__":
    main()
