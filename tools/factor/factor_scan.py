"""Stage 0 cost-aware factor discovery scan. Implements PREREG_FACTOR_SCAN_2026-09-27
INCLUDING AMENDMENT 1 (both trade directions) and AMENDMENT 2 (risk-unit robustness).

Frozen before any result was produced. Do not add factors, change the gate, or
change the decision rule here - that is the exact failure the prereg exists to
prevent. If the rule is wrong, retire the prereg and write a new one.

Four outputs, nothing else:
  1. net forward R per factor bucket, cost subtracted PER BAR (dynamic cost_R)
  2. the full percentile curve (20 buckets), never a threshold
  3. liquidity buckets (Top3/Mid3/Tail3 - the requested Top20/Mid50/Tail30 is
     impossible on 9 symbols) and time windows 2023-24 / 2025 / 2026
  4. IAT-corrected t everywhere (12-bar forward returns overlap, IAT >= 12)
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
OUT = ROOT / "shark_results" / "factor_scan"

# ---- frozen constants (PREREG §2, §3, §0b, §0c) ---------------------------
HORIZON = 12          # bars; 12 x 5m = 1 hour
STOP_MULT = 1.0
SAFETY = 1.3
NBUCKET = 20
COST_REGIMES = {"calm": 12.0, "cascade": 15.6, "volatile": 22.8, "covid": 34.9}
COST_MAIN = "calm"
FACTORS = ["rvol", "cvd_press", "vwap_dev"]
DIRECTIONS = {"long": 1.0, "short": -1.0}          # AMENDMENT 1
PRIMARY_TESTS = len(FACTORS) * len(DIRECTIONS) * NBUCKET
WINSOR = 5.0                                        # AMENDMENT 2

WINDOWS = [("2023-24", "2023-01-01", "2025-01-01"),
           ("2025", "2025-01-01", "2026-01-01"),
           ("2026", "2026-01-01", "2027-01-01")]


def load(sym: str) -> pd.DataFrame:
    d = pd.read_csv(KLINES / f"{sym}_5m.csv.gz")
    d["ts"] = pd.to_datetime(d["timestamp"], unit="ms", utc=True)
    return d.sort_values("ts").reset_index(drop=True)


def features(d: pd.DataFrame) -> pd.DataFrame:
    """All three factors, all causal (bar t and history only)."""
    f = pd.DataFrame(index=d.index)
    close, high, low = d["close"], d["high"], d["low"]
    vol, qv, tbq = d["volume"], d["quote_volume"], d["taker_buy_quote_volume"]

    prev = close.shift(1)
    tr = pd.concat([high - low, (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    f["atr"] = atr
    f["atr_pct"] = atr / close
    # AMENDMENT 2 robustness risk unit: trailing 1-day median ATR
    f["atr_pct_slow"] = atr.rolling(288, min_periods=288).median() / close

    f["rvol"] = vol / vol.rolling(20, min_periods=20).mean().replace(0.0, np.nan)
    delta_q = 2.0 * tbq - qv
    f["cvd_press"] = (delta_q.rolling(HORIZON, min_periods=HORIZON).sum()
                      / qv.rolling(HORIZON, min_periods=HORIZON).sum().replace(0.0, np.nan))
    vwap20 = (qv.rolling(20, min_periods=20).sum()
              / vol.rolling(20, min_periods=20).sum().replace(0.0, np.nan))
    f["vwap_dev"] = (close - vwap20) / atr.replace(0.0, np.nan)

    f["fwd_ret"] = close.shift(-HORIZON) / close - 1.0
    f["ts"] = d["ts"]
    return f


def stats(x: np.ndarray) -> dict:
    """IAT-corrected statistics. Never returns a naive t as the headline."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 50:
        return {"n": n, "mean_R": np.nan, "sd": np.nan, "t_adj": np.nan, "iat": np.nan}
    d = dependence_t(x)
    # NB: the key is NOT "iat" - `Series.iat` is pandas' integer accessor, and
    # `r.iat` on a row returns that object, not this column.
    return {"n": n, "mean_R": float(d["mean_r"]), "sd": float(d["sd_r"]),
            "t_adj": float(d["t_adjusted"]), "iat_est": float(d["iat"])}


def pf(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    g, l = x[x > 0].sum(), -x[x < 0].sum()
    return float(g / l) if l > 0 else np.inf


def net_series(df: pd.DataFrame, col: str, direction: float, variant: str) -> pd.ndarray:
    """net_R for one (risk-unit variant, cost regime, direction) combination."""
    if variant == "winsor":
        return np.clip(direction * df[col], -WINSOR, WINSOR)
    return direction * df[col]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    syms = sorted(p.name.replace("_5m.csv.gz", "") for p in KLINES.glob("*_5m.csv.gz"))
    print(f"symbols: {len(syms)} -> {syms}\n")

    frames = []
    for s in syms:
        f = features(load(s))
        f["symbol"] = s
        f = f.iloc[:-HORIZON]        # no forward return on the last HORIZON bars
        frames.append(f)
    df = pd.concat(frames, ignore_index=True)
    print(f"bars: {len(df):,}  {df['ts'].min().date()} -> {df['ts'].max().date()}\n")

    liq = {s: float(load(s)["quote_volume"].median()) for s in syms}
    rank = sorted(syms, key=lambda s: -liq[s])
    bucket = {s: ("top" if i < 3 else "mid" if i < 6 else "tail") for i, s in enumerate(rank)}
    df["liq"] = df["symbol"].map(bucket)
    print("liquidity ranking by median quote_volume:")
    for i, s in enumerate(rank):
        print(f"  {i+1}. {s:<9s} {liq[s]:>14,.0f}  -> {bucket[s]}")
    print("  (Top3/Mid3/Tail3 - the requested Top20/Mid50/Tail30 is IMPOSSIBLE on 9 symbols)\n")

    cbps = COST_REGIMES[COST_MAIN]
    for k, v in COST_REGIMES.items():
        df[f"costR_{k}"] = v / (STOP_MULT * df["atr_pct"] * 10000.0)
        df[f"netR_{k}"] = df["fwd_ret"] / df["atr_pct"] - df[f"costR_{k}"]
        df[f"netRslow_{k}"] = (df["fwd_ret"] / df["atr_pct_slow"]
                               - v / (STOP_MULT * df["atr_pct_slow"] * 10000.0))
    NET = f"netR_{COST_MAIN}"
    NETSLOW = f"netRslow_{COST_MAIN}"

    cp = df[f"costR_{COST_MAIN}"].describe(percentiles=[.05, .5, .95])
    print(f"=== cost model (calm {cbps} bps, stop {STOP_MULT} ATR, safety {SAFETY}) ===")
    print(f"cost_R: min {cp['min']:.3f}  p5 {cp['5%']:.3f}  median {cp['50%']:.3f}  "
          f"p95 {cp['95%']:.3f}  max {cp['max']:.3f}  -> required_edge = cost_R x {SAFETY}")
    print("         a FIXED gate is meaningless here: cost_R spans "
          f"{cp['min']:.2f}-{cp['max']:.2f}R on one sample\n")

    # ---- full percentile curves, both directions, three robustness variants --
    print("=" * 120)
    print(f"1. FULL PERCENTILE CURVES, pooled, net of {cbps} bps "
          f"(bucket 19 = top 5%; short = negated)")
    print("=" * 120)
    rows = []
    for fac in FACTORS:
        b = pd.cut(df[fac].rank(pct=True) * 100,
                   np.linspace(0, 100, NBUCKET + 1), labels=False, include_lowest=True)
        for k in range(NBUCKET):
            m = b == k
            for dname, sgn in DIRECTIONS.items():
                raw = sgn * df.loc[m, NET].to_numpy()
                w = np.clip(raw, -WINSOR, WINSOR)
                sl = sgn * df.loc[m, NETSLOW].to_numpy()
                s = stats(raw)
                rows.append({
                    "factor": fac, "bucket": k, "dir": dname,
                    "pct_lo": 100 * k / NBUCKET, "pct_hi": 100 * (k + 1) / NBUCKET,
                    "n": s["n"], "mean_R": s["mean_R"], "t_adj": s["t_adj"],
                    "iat_est": s["iat_est"], "pf": pf(raw),
                    "mean_winsor": float(np.nanmean(w)),
                    "mean_slowATR": float(np.nanmean(sl)),
                    "mean_costR": float(df.loc[m, f"costR_{COST_MAIN}"].mean()),
                    "mean_grossR": float(df.loc[m, "fwd_ret"].div(df.loc[m, "atr_pct"]).mean()),
                })
    curve = pd.DataFrame(rows)
    curve.to_csv(OUT / "curve_pooled.csv", index=False)

    for fac in FACTORS:
        for dname in DIRECTIONS:
            c = curve[(curve.factor == fac) & (curve["dir"] == dname)]
            tail = c.tail(NBUCKET // 5)
            mono = (tail.mean_R > 0).all() or (tail.mean_R < 0).all()
            print(f"\n--- {fac} / {dname} ---  {'MONOTONE-SIGNED' if mono else 'SIGN FLIP -> FAILS prereg c1'}")
            print(f"{'bkt':>3s} {'pct':>9s} {'n':>8s} {'grossR':>9s} {'costR':>7s} "
                  f"{'netR':>9s} {'wins5R':>8s} {'slowATR':>8s} {'PF':>6s} {'t_adj':>7s} {'IAT':>5s}")
            for _, r in c.iterrows():
                mk = " *" if r.bucket >= NBUCKET - NBUCKET // 5 else ""
                print(f"{int(r.bucket):3d} {r['pct_lo']:3.0f}-{r['pct_hi']:<4.0f} {int(r.n):8,d} "
                      f"{r.mean_grossR:+9.4f} {r.mean_costR:7.4f} {r.mean_R:+9.4f} "
                      f"{r.mean_winsor:+8.4f} {r.mean_slowATR:+8.4f} {r.pf:6.2f} "
                      f"{r.t_adj:7.2f} {r.iat_est:5.1f}{mk}")

    # ---- windows / liquidity / symbols for the tail of each (fac, dir) -----
    print()
    print("=" * 120)
    print("2+3+4. TAIL BUCKET (top 5% / bottom 5% of the factor) by TIME WINDOW, "
          "LIQUIDITY, and SYMBOL")
    print("=" * 120)
    combos = [(f, d) for f in FACTORS for d in DIRECTIONS]
    detail = {}
    for fac, dname in combos:
        sgn = DIRECTIONS[dname]
        c = curve[(curve.factor == fac) & (curve["dir"] == dname)]
        if dname == "long":
            thr = df[fac].quantile(0.95); msk = df[fac] >= thr
        else:
            thr = df[fac].quantile(0.05); msk = df[fac] <= thr
        vals = sgn * df[NET]
        detail[(fac, dname)] = {
            "mask": msk,
            "wins": {w: float(vals[msk & (df.ts >= w0) & (df.ts < w1)].mean())
                     for w, w0, w1 in WINDOWS},
            "liq": {b_: float(vals[msk & (df.liq == b_)].mean()) for b_ in ("top", "mid", "tail")},
            "sym": {s: float(vals[msk & (df.symbol == s)].mean()) for s in syms},
        }

    print(f"\n{'factor/dir':<18s} " + "".join(f"{w[0]:>10s}" for w in WINDOWS)
          + "   | " + "".join(f"{b_:>10s}" for b_ in ("top", "mid", "tail")))
    for k, v in detail.items():
        print(f"{k[0]+'/'+k[1]:<18s} " + "".join(f"{v['wins'][w[0]]:>+10.3f}" for w in WINDOWS)
              + "   | " + "".join(f"{v['liq'][b_]:>+10.3f}" for b_ in ("top", "mid", "tail")))

    print(f"\n{'factor/dir':<18s} " + " ".join(f"{s[:5]:>8s}" for s in syms) + "   positives")
    for k, v in detail.items():
        sv = v["sym"]
        print(f"{k[0]+'/'+k[1]:<18s} " + " ".join(f"{sv[s]:>+8.3f}" for s in syms)
              + f"   {sum(1 for s in syms if sv[s] > 0)}/{len(syms)}")

    # ---- prereg decision rule --------------------------------------------
    print()
    print("=" * 120)
    print("5. PREREG DECISION RULE (frozen) - primary grid = "
          f"{PRIMARY_TESTS} tests (3 factors x 2 directions x {NBUCKET} buckets)")
    print("   NOTE c1: the NET curve is near-trivially monotone because net = gross - cost")
    print("   and cost_R is itself a function of atr_pct, which correlates with the factor.")
    print("   The decision that matters is c2: GROSS edge in the tail vs 1.3 x cost_R.")
    print("=" * 120)
    print(f"{'factor/dir':<18s} {'c1 curve':<10s} {'c2 size':<9s} {'c3 consist':<11s} "
          f"{'c4 signif':<10s} {'robust':<9s} {'gross/cost':>11s} {'VERDICT'}")
    verdicts = {}
    for fac, dname in combos:
        c = curve[(curve.factor == fac) & (curve["dir"] == dname)]
        tail = c.tail(NBUCKET // 5)
        s = tail.mean_R
        c1 = bool((s > 0).all() or (s < 0).all())
        # PREREG §3 form: the GROSS edge must clear 1.3 x cost_R. (The §5 wording
        # "net R >= 1.3 x cost" would have required gross >= 2.3 x cost; §3 is the
        # stated intent and the prereg's two statements were inconsistent. Recorded.)
        gross_tail = float(np.mean(np.abs(tail.mean_grossR.to_numpy())))
        cost_tail = float(tail.mean_costR.mean())
        ratio = gross_tail / cost_tail if cost_tail else np.inf
        c2 = bool(ratio >= SAFETY)
        v = detail[(fac, dname)]
        c3 = (sum(1 for x in v["wins"].values() if x > 0) >= 2
              and sum(1 for x in v["liq"].values() if x > 0) >= 2)
        c4 = bool(tail.t_adj.max() >= 2.0)
        sgn = 1.0 if tail.mean_R.mean() > 0 else -1.0
        robust = bool(float(tail.mean_winsor.mean()) * sgn > 0
                      and float(tail.mean_slowATR.mean()) * sgn > 0)
        ok = c1 and c2 and c3 and c4 and robust
        verdict = "ADVANCE" if ok else ("FRAGILE" if (c1 and c2 and c3 and c4) else "NULL")
        verdicts[(fac, dname)] = (verdict, c1, c2, c3, c4, robust, ratio)
        print(f"{fac+'/'+dname:<18s} {str(c1):<10s} {str(c2):<9s} {str(c3):<11s} "
              f"{str(c4):<10s} {str(robust):<9s} {ratio:11.4f} {verdict}")

    print()
    print("   GROSS edge is what the factor actually predicts; cost_R is what one round")
    print("   trip costs. The gate is gross/cost >= 1.3.")
    best = max(verdicts.items(), key=lambda kv: kv[1][6])
    print(f"   best factor/direction: {best[0][0]}/{best[0][1]} at "
          f"gross/cost = {best[1][6]:.4f} (needs 1.3, short by "
          f"{SAFETY / best[1][6]:.1f}x)")

    print()
    print("=" * 120)
    print("6. COST SENSITIVITY of each tail bucket (does the sign survive the "
          "measured regimes?)")
    print("=" * 120)
    print(f"{'factor/dir':<18s} " + "".join(f"{k:>11s}" for k in COST_REGIMES))
    for fac, dname in combos:
        sgn = DIRECTIONS[dname]
        thr = df[fac].quantile(0.95 if dname == "long" else 0.05)
        m = (df[fac] >= thr) if dname == "long" else (df[fac] <= thr)
        cells = [f"{sgn * df.loc[m, f'netR_{k}'].mean():>+11.4f}" for k in COST_REGIMES]
        print(f"{fac+'/'+dname:<18s} " + "".join(cells))

    n_adv = sum(1 for v in verdicts.values() if v[0] == "ADVANCE")
    print()
    print(f"PREREG §6 FALSIFIER: " + (
        "no factor met the size test -> 5m microstructure direction is CLOSED"
        if n_adv == 0 else f"{n_adv} factor/direction(s) ADVANCE to Stage 1"))
    print("\nwrote", OUT)


if __name__ == "__main__":
    main()
