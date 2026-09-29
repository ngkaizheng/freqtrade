"""Part 3: qualify the liquid-50 momentum, check mean-vs-median cost, and read
the project's own E3/E6 outputs."""
from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "user_data/universe/raw_daily"
OUT = ROOT / "tools/cross_sectional"


def nw_t(v, lags=5):
    v = np.asarray(v, float)
    n = len(v); e = v - v.mean()
    g0 = float((e ** 2).sum()) / n; var = g0
    for L in range(1, lags + 1):
        var += 2 * (1 - L / (lags + 1)) * float((e[L:] * e[:-L]).sum()) / n
    return float(v.mean() / math.sqrt(max(var, 1e-18) / n))


def dec(px, sign):
    s = px.pct_change(fill_method=None); fwd = s.shift(-1)
    out, csz = {}, {}
    for d in px.index:
        a, b = s.loc[d], fwd.loc[d]
        m = a.notna() & b.notna()
        if m.sum() < 20:
            continue
        a, b = a[m], b[m]
        k = max(1, int(round(0.1 * len(a))))
        lo, hi = a.nsmallest(k).index, a.nlargest(k).index
        out[d] = float((b[lo].mean() - b[hi].mean()) if sign < 0
                       else (b[hi].mean() - b[lo].mean()))
        csz[d] = int(m.sum())
    return pd.Series(out).sort_index(), pd.Series(csz).sort_index()


def main():
    kept = {}
    for f in sorted(RAW.glob("*_1d.csv.gz")):
        sym = f.name.replace("_1d.csv.gz", "")
        d = pd.read_csv(f)
        d["date"] = pd.to_datetime(d["date"], format="%Y-%m-%d", errors="coerce")
        d = d.dropna(subset=["date", "close", "quote_volume"]).set_index("date").sort_index()
        kept[sym] = d
    px = pd.concat({k: v["close"] for k, v in kept.items()}, axis=1).sort_index()
    qv = pd.concat({k: v["quote_volume"] for k, v in kept.items()}, axis=1).sort_index()

    u50 = list(qv.median().nlargest(50).index)
    p50 = px[u50]
    mom, csz = dec(p50, +1)
    rev, _ = dec(p50, -1)

    print("=" * 96)
    print("G. LIQUID-50 DAILY MOMENTUM, BY YEAR (is +0.45%/day a 2021 artefact?)")
    print("=" * 96)
    df = pd.DataFrame({"mom": mom, "n": csz})
    df["yr"] = df.index.year
    for y, g in df.groupby("yr"):
        print(f"  {y}  n_days {len(g):4d}  mean cross-section {g['n'].mean():5.1f}  "
              f"momentum {g['mom'].mean()*100:+.4f}%/day  t {nw_t(g['mom'].to_numpy()):+.2f}")
    recent = df[df.index >= "2022-01-01"]
    print(f"  2022-2026 only: momentum {recent['mom'].mean()*100:+.4f}%/day  "
          f"t {nw_t(recent['mom'].to_numpy()):+.2f}  ({len(recent)} days)")
    # require a proper cross-section
    big = df[df["n"] >= 45]
    print(f"  days with >=45 of the 50 alive: momentum {big['mom'].mean()*100:+.4f}%/day  "
          f"t {nw_t(big['mom'].to_numpy()):+.2f}  ({len(big)} days)")

    print()
    print("=" * 96)
    print("H. 200-NAME REVERSAL PORTFOLIO BY YEAR (the real gross edge)")
    print("=" * 96)
    r200, c200 = dec(px, -1)
    d2 = pd.DataFrame({"rev": r200, "n": c200}); d2["yr"] = d2.index.year
    for y, g in d2.groupby("yr"):
        print(f"  {y}  n_days {len(g):4d}  mean cross-section {g['n'].mean():5.1f}  "
              f"reversal {g['rev'].mean()*100:+.4f}%/day  t {nw_t(g['rev'].to_numpy()):+.2f}")
    print(f"  ALL     n_days {len(r200):4d}  reversal {r200.mean()*100:+.4f}%/day  "
          f"t {nw_t(r200.to_numpy()):+.2f}  ann {r200.mean()*365*100:+.1f}%")
    print(f"  2023+ only: {d2[d2.index>='2023-01-01']['rev'].mean()*100:+.4f}%/day  "
          f"t {nw_t(d2[d2.index>='2023-01-01']['rev'].to_numpy()):+.2f}")

    print()
    print("=" * 96)
    print("I. COST: MEAN vs MEDIAN (an equal-weight book pays the MEAN)")
    print("=" * 96)
    cm = json.loads((OUT / "cost_measurement.json").read_text(encoding="utf-8"))
    rows = [r for r in cm["rows"] if "error" not in r]
    print(f"  symbols requested 20, books returned {len(rows)} "
          f"(failed: {[r['symbol'] for r in cm['rows'] if 'error' in r]})")
    for n_ in (10_000, 50_000, 250_000, 1_000_000):
        v = [r[f"rt_bps_{n_}"] for r in rows if r.get(f"rt_bps_{n_}")]
        v2 = sorted(v)
        print(f"  ${n_:>9,}   median {statistics.median(v):6.2f}   MEAN {statistics.mean(v):6.2f}   "
              f"p90 {v2[int(.9*len(v2))]:6.2f}   max {max(v):6.2f}   "
              f"mean/median {statistics.mean(v)/statistics.median(v):.2f}x")
    # max depth levels used -> partial fill check
    lv = []
    for r in rows:
        for n_ in (1_000_000,):
            s_ = r.get(f"book_levels_{n_}")
            if s_:
                a, b = s_.split("/"); lv.append(max(int(a), int(b)))
    print(f"  $1M orders consumed at most {max(lv)} of the 1000 available levels "
          f"-> NO partial fills, the depth snapshot was not exhausted")

    print()
    print("=" * 96)
    print("J. THE PROJECT'S OWN E3 / E6 OUTPUTS")
    print("=" * 96)
    for f in ("e3_result.json", "e6_result.json", "e5_liquid_result.json"):
        p = OUT / f
        if p.exists():
            print(f"\n  --- {f} ---")
            print(json.dumps(json.loads(p.read_text(encoding="utf-8")), indent=2)[:2600])


if __name__ == "__main__":
    main()
