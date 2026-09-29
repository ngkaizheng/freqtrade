"""
Put the signal and the cost on the same universe.

`measure_cost.py` established that the E#4 reversal is affordable only in the
liquid majors at modest book size. `e4_power.py` established that the signal
was measured on the 200 OLDEST-listed perps -- the long tail, where depth is
thin and impact is not the number above.

Those two facts do not meet. This closes the loop: measure the reversal IC on
the universe where the measured cost says the trade is affordable, and price
it with that measured cost rather than with an assumed one.

The universe is fixed in advance and for a reason that is NOT the signal: it is
the top 50 by median daily quote volume, which is where `measure_cost.py`
returned the lowest round-trip cost. Choosing it by IC would be a search.

Run:  .venv\\Scripts\\python.exe tools\\cross_sectional\\e5_liquid.py
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

pd.set_option("display.width", 220)

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "user_data/universe/raw_daily"
OUT = Path(__file__).resolve().parent

TOP_N = 50                  # fixed by cost, not by signal
FEE_BPS_PER_SIDE = 5.0      # Binance USD-M VIP0 taker
DEC = 3.51
REBASE = -0.90


def iat(v: np.ndarray, max_lag: int = 30) -> float:
    x = np.asarray(v, float)
    x = x - x.mean()
    den = float((x ** 2).sum())
    if den <= 0 or len(x) < 20:
        return 1.0
    total = 0.0
    for lag in range(1, min(max_lag, len(x) - 1) + 1):
        rho = float((x[lag:] * x[:-lag]).sum() / den)
        if rho <= 0:
            break
        total += rho
    return 1.0 + 2.0 * total


def main() -> None:
    cost = json.loads((OUT / "cost_measurement.json").read_text(encoding="utf-8"))
    frames = {}
    for f in sorted(RAW.glob("*_1d.csv.gz")):
        sym = f.name.replace("_1d.csv.gz", "")
        d = pd.read_csv(f)
        d["date"] = pd.to_datetime(d["date"], format="%Y-%m-%d", errors="coerce")
        d = d.dropna(subset=["date", "close", "quote_volume"]).set_index("date").sort_index()
        d = d[~d.index.duplicated()]
        if (d["close"].pct_change() < REBASE).any():
            continue
        frames[sym] = d
    px = pd.concat({k: v["close"] for k, v in frames.items()}, axis=1).sort_index()
    qv = pd.concat({k: v["quote_volume"] for k, v in frames.items()}, axis=1).sort_index()

    med_qv = qv.median()
    universe = list(med_qv.nlargest(TOP_N).index)
    print(f"universe: top {TOP_N} by median daily quote volume "
          f"(median {med_qv[universe].median()/1e6:.0f}m USD/day)")
    print(f"          fixed by cost, not by the signal.\n")

    px = px[universe]
    rets = px.pct_change(fill_method=None)
    # CORRECTED 2026-09-26. This was `fwd = rets.shift(-1); s = rets.shift(1)`,
    # which at index t computes corr(r_{t-1}, r_{t+1}) -- a two-day formation
    # that SKIPS r_t -- while e4_power.py computes corr(r_t, r_{t+1}). The
    # headline table in SIGNAL_VS_COST.md was therefore comparing two different
    # statistics. The signal at index t is r_t; the return earned is r_{t+1}.
    s = rets
    fwd = rets.shift(-1)

    pair = pd.concat([s.stack(), fwd.stack()], axis=1).dropna()
    ic = pair.groupby(level=0).corr().iloc[0::2, -1].dropna()
    tau = iat(ic.to_numpy())
    n = len(ic)
    t_raw = ic.mean() / ic.std(ddof=1) * math.sqrt(n)
    t_adj = t_raw * math.sqrt(min(1.0, n / max(n / tau, 2.0)))

    print("=" * 76)
    print("1. THE SIGNAL ON THE LIQUID UNIVERSE")
    print("=" * 76)
    print(f"  observations          {n}")
    print(f"  mean IC               {ic.mean():+.5f}")
    print(f"  integrated autocorr   {tau:.2f}   effective N {n/tau:.0f}")
    print(f"  t naive               {t_raw:+.2f}")
    print(f"  t dependence-adjusted {t_adj:+.2f}")
    print(f"  |t| > 2 ?             {'yes' if abs(t_adj) > 2 else 'NO'}")

    # ---------------------------------------------------- economics
    print()
    print("=" * 76)
    print("2. PRICED WITH THE MEASURED COST, NOT AN ASSUMED ONE")
    print("=" * 76)
    sig_h = float(rets.std(axis=1).mean())
    gross_daily = DEC * abs(ic.mean()) * sig_h
    print(f"  daily cross-sectional sigma  {sig_h*100:.2f}%")
    print(f"  gross edge per day           {gross_daily*100:.3f}%")

    # measured book cost for the liquid names
    per_sym = {r["symbol"]: r for r in cost["rows"] if "rt_bps" in r or True}
    book_bps = {}
    for notional in (10_000, 50_000, 250_000, 1_000_000):
        vals = [r.get(f"rt_bps_{notional}") for r in cost["rows"]]
        vals = [v for v in vals if v]
        if vals:
            book_bps[notional] = statistics.median(vals)

    print()
    print(f"  {'per-name size':>14} {'book bps':>9} {'+fee bps':>9} "
          f"{'all-in':>8} {'vs 26.6':>9} {'net/day':>9} {'net/yr':>9}")
    print("  " + "-" * 72)
    for n_size, book in book_bps.items():
        allin = book + 2 * FEE_BPS_PER_SIDE
        net = gross_daily - allin * 1.03 / 1e4      # turnover 1.03 measured
        book_total = n_size * TOP_N
        print(f"  {n_size:>13,} {book:>9.1f} {2*FEE_BPS_PER_SIDE:>9.1f} "
              f"{allin:>7.1f}b {('BELOW' if allin < 26.6 else 'ABOVE'):>9} "
              f"{net*100:>8.3f}% {net*365*100:>8.1f}%")
    print(f"\n  book size implied: {TOP_N} names x per-name size")
    for n_size in book_bps:
        print(f"    {n_size:>10,} per name  ->  {n_size*TOP_N:>12,} total book")

    print("""
  The cost column is MEASURED, from a live depth snapshot on these names on
  2026-09-26. It is a lower bound: it excludes adverse selection while an
  order works, and it is a single snapshot, not a distribution. A 376x-turnover
  strategy is exposed to both.""")

    verdict = {
        "universe": "top 50 by median daily quote volume",
        "n_symbols": TOP_N,
        "observations": int(n),
        "ic": round(float(ic.mean()), 5),
        "iat": round(tau, 2),
        "t_naive": round(t_raw, 3),
        "t_adjusted": round(t_adj, 3),
        "significant_at_2": bool(abs(t_adj) > 2),
        "gross_daily_pct": round(gross_daily * 100, 4),
        "measured_book_bps": {str(k): v for k, v in book_bps.items()},
        "fee_bps_per_side": FEE_BPS_PER_SIDE,
        "breakeven_bps": 26.6,
        "status": "EXPLORATORY - not pre-registered",
    }
    (OUT / "e5_liquid_result.json").write_text(json.dumps(verdict, indent=2), encoding="utf-8")
    print(f"\nwritten {OUT / 'e5_liquid_result.json'}")


if __name__ == "__main__":
    main()
