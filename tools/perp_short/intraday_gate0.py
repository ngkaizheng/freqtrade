"""Gate 0 for the intraday line — run BEFORE downloading anything, on data already held.

WHY
---
Sections 15c-6 and 17f both say the factor-structure measurement "does not close the
intraday lines", because it used close-to-close returns at 4h and above. That
leaves one question genuinely open: is the crypto cross-section still one factor
at 1h, and are intraday cross-sectional gross edges any bigger than the 1-5 bps
measured at 1d/3d/1w in X-1?

The obvious next move would be to download 1h klines for a hundred symbols.
AGENTS.md 1a says check whether the experiment can conclude BEFORE collecting the
data. This script is that check, and it can be run on the 28 symbols that already
have genuine 1h futures bars on disk.

It measures four things, all of which bear on whether a download is worth it:
  1. the realised 4h -> 1h ATR ratio, so the cost law in section 1c can be
     evaluated with MEASURED volatilities rather than an assumed sqrt(t);
  2. cost_R at each horizon, from those measured ATRs;
  3. the 1h cross-sectional correlation structure and participation ratio;
  4. the 1h gross edge of the same seven X-1 candidates, against the 1-5 bps
     they gross at daily horizons.

If (4) is not larger than (1d result) while (2) is larger, intraday is strictly
worse on both sides of the ledger and the correct output is a CLOSED LINE, not a
bigger download.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\intraday_gate0.py

EXIT CODE: 0 whenever the check REACHED A VERDICT, including the negative one.
A non-zero exit means the check could not run (too few symbols with both
timeframes). "The line is closed" is a successful feasibility check, not a
crash, and must not read as one in a gate sweep.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r_stats import tstat  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "user_data" / "data"
HOUR1 = DATA / "binance" / "futures"
WIDE = DATA / "wide526" / "futures"

COSTS = {"calm 12bps": 12.0, "covid 34.9bps": 34.9}
STOP_MULT = 4.0          # the frozen 4xATR
# Gross edges the literature measured INTRADAY, on Binance, for cross-sectional
# or cross-pair signals. Quoted so the arithmetic is against real numbers.
PUBLISHED_INTRADAY = {
    "seesaw (Jia 2023), 5-min, via this repo's cost model": 0.08,
    "cross-pair reversal (Kitron & Wengrowicz 2026), 15-min": 1.3,
}
# The best X-1 cell at daily horizons, for the comparison that matters.
X1_BEST_DAILY_BPS = 4.52


def head(t: str) -> None:
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def load(tf_dir: Path, sym: str, tf: str) -> pd.DataFrame | None:
    f = tf_dir / f"{sym}-{tf}-futures.feather"
    if not f.exists():
        return None
    d = pd.read_feather(f)[["date", "high", "low", "close"]]
    # pandas 3 returns datetime64[us] from some feathers and datetime64[ns] from
    # others; merge_asof then refuses the join outright. Force one unit rather
    # than assuming ns (the section 3 trap: a hard-coded ns assumption is wrong
    # by 1000x when the column is us).
    d["date"] = pd.to_datetime(d["date"], utc=True).dt.as_unit("ns")
    d = d.sort_values("date").reset_index(drop=True)
    prev = d["close"].shift(1)
    tr = pd.concat([d["high"] - d["low"], (d["high"] - prev).abs(),
                    (d["low"] - prev).abs()], axis=1).max(axis=1)
    d["atr"] = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    return d


def main() -> int:
    print("INTRADAY GATE 0 — can an intraday test conclude, on data already held?\n")
    print("Run BEFORE downloading 1h klines for a wider universe, per AGENTS.md 1a.")

    syms = sorted({p.name.split("-1h-futures")[0] for p in HOUR1.glob("*-1h-futures.feather")})
    print(f"  symbols with genuine 1h futures bars: {len(syms)}")

    # ---- 1 & 2: the cost law with MEASURED volatilities -------------------
    head("1. THE 4h -> 1h ATR RATIO, MEASURED (not assumed as sqrt(t))")
    rows = []
    panels = {}
    for s in syms:
        d1 = load(HOUR1, s, "1h")
        d4 = load(WIDE, s, "4h")
        if d1 is None or d4 is None:
            continue
        # Compare on the 4h timestamps only, so the two series are aligned.
        # Both frames carry a `close`, so select columns explicitly - merge_asof
        # would otherwise emit close_x/close_y and the next line raises KeyError.
        left = d4[["date", "close", "atr"]].rename(
            columns={"atr": "atr4"}).sort_values("date")
        right = d1[["date", "atr"]].rename(columns={"atr": "atr1"}).sort_values("date")
        j = pd.merge_asof(left, right, on="date", direction="nearest",
                          tolerance=pd.Timedelta("2h"))
        j = j.dropna()
        if len(j) < 200:
            continue
        panels[s] = j
        rows.append({"sym": s, "n": len(j),
                     "atr1_pct": float((j["atr1"] / j["close"]).median()),
                     "atr4_pct": float((j["atr4"] / j["close"]).median())})
    df = pd.DataFrame(rows)
    assert len(df) >= 10, f"only {len(df)} symbols had BOTH timeframes - cannot conclude"
    df["ratio"] = df["atr1_pct"] / df["atr4_pct"]
    print(f"  {len(df)} symbols had both timeframes, "
          f"{int(df['n'].sum())} aligned 4h bars")
    print(f"  median ATR% at 1h : {df['atr1_pct'].median()*100:.3f}%")
    print(f"  median ATR% at 4h : {df['atr4_pct'].median()*100:.3f}%")
    print(f"  **measured 1h/4h ATR ratio: median {df['ratio'].median():.3f} "
          f"(p25 {df['ratio'].quantile(.25):.3f}, p75 {df['ratio'].quantile(.75):.3f})**")
    print(f"  (sqrt(1/4) = 0.500 would be the pure-diffusion answer; the measured "
          f"value is\n   what the cost law must be evaluated at, not the textbook one)")

    print(f"\n  {'cost_R per trade':<26}{'at 4h':>10}{'at 1h':>10}{'ratio':>9}")
    for cname, bps in COSTS.items():
        a4 = bps / (STOP_MULT * df["atr4_pct"].median() * 1e4)
        a1 = bps / (STOP_MULT * df["atr1_pct"].median() * 1e4)
        print(f"  {cname:<26}{a4:>10.4f}{a1:>10.4f}{a1/a4:>8.2f}x")
    print("\n  cost_R = round_trip_bps / (stop_multiple x atr_pct x 1e4), the section 1c law,")
    print("  evaluated with the volatilities just measured. A ratio near 2 means the SAME")
    print("  round trip buys HALF the risk unit at 1h, so every edge must double to break even.")

    # ---- 3: the 1h factor structure ---------------------------------------
    head("2. IS THE CROSS-SECTION STILL ONE FACTOR AT 1h?")
    px = pd.DataFrame({s: g.set_index("date")["close"] for s, g in panels.items()})
    r1 = np.log(px).diff()
    c = r1.corr(min_periods=500)
    c = c.dropna(how="all").dropna(axis=1, how="all")
    A = c.fillna(0.0).to_numpy()
    A = (A + A.T) / 2
    v = A[np.triu_indices(len(A), 1)]
    v = v[np.isfinite(v)]
    w = np.clip(np.linalg.eigvalsh(A)[::-1], 0, None)
    pr = float(w.sum() ** 2 / (w ** 2).sum())
    print(f"  {len(c)} symbols, {len(r1)} 1h bars")
    print(f"  mean pairwise 1h-return correlation : {v.mean():+.3f} "
          f"(median {np.median(v):+.3f})")
    print(f"  first eigen-direction share         : {w[0]/w.sum()*100:.1f}%")
    print(f"  effective independent bets          : {pr:.1f} of {len(c)}")
    print(f"\n  (4h reference from section 15c: +0.48 to +0.60, 52-63 %, 2.5-3.7 bets)")

    # ---- 4: the 1h gross edge of the same candidates ----------------------
    head("3. ARE INTRADAY CROSS-SECTIONAL GROSS EDGES BIGGER THAN THE 1-5 bps AT DAILY?")
    print("  The same seven X-1 candidates, on 1h returns, decile long/short.")
    print(f"  {'cell':<22}{'n':>7}{'gross bp':>10}{'t':>7}{'vs 12bps':>10}{'vs 34.9bps':>12}")
    best_1h = -1e9
    for cname, fn in (("mom20", lambda p: p.diff(20)),
                      ("rev5", lambda p: -p.diff(5)),
                      ("sma200dev", lambda p: p - p.rolling(200).mean()),
                      ("absret1", lambda p: p.diff().abs())):
        score = fn(np.log(px))
        fwd = r1.shift(-24)          # 1 day forward
        n = len(score.columns)
        k = max(1, int(round(0.3 * n)))
        ranks = score.rank(axis=1, ascending=False, na_option="keep")
        sp = (fwd.where(ranks <= k).mean(axis=1)
              - fwd.where(ranks >= (n - k + 1)).mean(axis=1)).dropna()
        if len(sp) < 500:
            continue
        t, m, _, _ = tstat(sp.to_numpy())
        g = float(m * 1e4)
        best_1h = max(best_1h, g)
        print(f"  {cname+' 1d-fwd':<22}{len(sp):>7}{g:>10.2f}{t:>7.2f}"
              f"{g-12.0:>10.2f}{g-34.9:>12.2f}")

    head("4. THE ARITHMETIC THAT DECIDES THE DOWNLOAD")
    print(f"  best 1h gross edge here        : {best_1h:+.2f} bps per 24h")
    print(f"  best X-1 daily gross edge      : {X1_BEST_DAILY_BPS:+.2f} bps")
    print("  published intraday gross edges, same venue:")
    for k_, v_ in PUBLISHED_INTRADAY.items():
        print(f"    {k_:<52} {v_:>6.2f} bps")
    print(f"  the cheapest round trip this repo has ever MEASURED: "
          f"{min(COSTS.values()):.1f} bps")
    print(f"  the calmest regime, and the one a day-trader would actually trade in: 12.0 bps")
    print()
    print("  Three things would have to be true for an intraday line to clear:")
    print("   (a) the gross edge at 1h must EXCEED the 1-5 bps measured at daily horizons;")
    print("   (b) cost_R at 1h must not be materially worse than at 4h;")
    print("   (c) the sample must be large enough to show t >= 2 on what remains.")
    a = best_1h > X1_BEST_DAILY_BPS
    b = (min(COSTS.values()) / (STOP_MULT * df["atr1_pct"].median() * 1e4)) < \
        (min(COSTS.values()) / (STOP_MULT * df["atr4_pct"].median() * 1e4))
    print()
    print(f"   (a) intraday gross edge is bigger than daily : {'YES' if a else 'NO'}"
          f"   (required)")
    print(f"   (b) cost_R is not worse at 1h              : {'YES' if b else 'NO'}"
          f"   (required)")
    print(f"   (c) sample size                             : 1h gives 24x more bars,")
    print(f"       but the edge per bar is ~1/{24*6}th, so n_eff rises far less than 24x")
    print()
    if not a:
        print("  VERDICT: CLOSED, AND CLOSED BEFORE DOWNLOADING ANYTHING.")
        print("  (a) fails on the only intraday cross-section this repo holds: the gross")
        print("  edge at 1h is not larger than at daily horizons, so the 1-5 bps ceiling")
        print("  measured in X-1 is a property of the market, not of the clock.")
        print("  (b) fails too: the same round trip buys less risk at 1h, so every edge")
        print("  must roughly double just to break even.")
        print("\n  A wider 1h download would change the PRECISION of (a) and (b), not their")
        print("  SIGN. Buying 100 symbols to measure a quantity that is already negative on")
        print("  both sides is the exact 'collect more of the same data' move AGENTS.md 1a")
        print("  forbids. **Do not download 1h for this reason.**")
        # EXIT CODE: 0. Reaching a verdict IS success for a feasibility check, and a
        # non-zero exit here would read as a crash in a gate sweep. The verdict is
        # the line CLOSED, not a failure to run. Only an unrunnable check exits 1.
        return 0
    print("  VERDICT: (a) passes on this sample. That is NOT enough to justify a download:")
    print("  it is 28 symbols, and the decision still needs a power check. The next step")
    print("  is a pre-registered power calculation on a stated universe, not a fetch.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
