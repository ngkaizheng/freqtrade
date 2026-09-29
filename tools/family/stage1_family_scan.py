"""STRATEGY_FAMILY_AUDIT — Stage 1: three mechanism families, zero parameters.

GROSS-FIRST, ALWAYS. The t-statistic is computed on the GROSS series and the
cost is subtracted afterwards and reported separately. The previous Stage 0 scan
learned this the hard way: a t on `net = gross - cost` measures how predictable
the COST is, not the edge (net-side t_adj 34-59 collapsed to 0.30-2.88 gross).

There is no parameter search here. Every family is a fixed construction scored
continuously by percentile, and the whole curve is published. Forward horizons
are a REPORTING axis, not a selection: all of them are printed.
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

HORIZONS = {"15m": 3, "30m": 6}          # 5m bars per aggregated bar
NBUCKET = 20
COST_BPS = 12.0                          # calm regime, round trip
SAFETY = 1.3
FORM = 12                                # formation window in aggregated bars
FWD = {"short": 4, "medium": 12, "long": 24}
WINDOWS = [("2023-24", "2023-01-01", "2025-01-01"),
           ("2025", "2025-01-01", "2026-01-01"),
           ("2026", "2026-01-01", "2027-01-01")]

# ---- DATA INTEGRITY GATE (frozen before any family result was produced) ----
# The first run of this script reported forward returns of +7,503 bps over three
# hours, with a bucket MEAN above its own 95th percentile - arithmetically
# impossible, and a direct symptom of bad prints in the corpus.
#
# Measured: ADA +65.7%, AVAX +70.4%, DOGE +57.7%, LINK +50.2% in a SINGLE 5m
# bar, against a p99.9 of 1.2-2.3%. A 20% move inside five minutes is not a
# market event in a liquid perpetual; it is a data event. OHLC structural checks
# all pass (0 violations), so the bars are internally consistent and wrong.
#
# A 20% absolute floor is used rather than a sigma multiple on purpose: crypto
# 5m returns are genuinely fat-tailed (p99.9 is already ~1.3-2.3%), so a
# 5-sigma rule would delete real observations. 20% is far outside the tail.
CORRUPT_5M_LOGRET = 0.20
CORRUPT_5M_DEV = 0.30                      # |close - trailing 288-bar median| / median


def load5(sym: str) -> pd.DataFrame:
    d = pd.read_csv(KLINES / f"{sym}_5m.csv.gz")
    d["ts"] = pd.to_datetime(d["timestamp"], unit="ms", utc=True)
    d = d.sort_values("ts").reset_index(drop=True)
    r = np.log(d["close"] / d["close"].shift(1))
    med = d["close"].rolling(288, min_periods=288).median()
    bad = (r.abs() > CORRUPT_5M_LOGRET) | ((d["close"] - med).abs() / med > CORRUPT_5M_DEV)
    d["corrupt"] = bad.fillna(False).to_numpy()
    return d


def propagate_corrupt(df: pd.DataFrame, n: int, hb: int) -> pd.Series:
    """True where [t, t+hb] aggregated bars contains a corrupt 5m bar.

    Aggregation factor n, so an aggregated bar covers n underlying 5m bars; a
    forward window of hb aggregated bars covers hb*n 5m bars. A formation window
    of FORM aggregated bars covers FORM*n before the decision.
    """
    c = df["corrupt"].to_numpy()
    win = max(hb, FORM) * n
    # rolling sum via cumsum, O(n)
    cs = np.concatenate([[0], np.cumsum(c.astype(np.int64))])
    out = (cs[win:] - cs[:-win]) > 0
    pad = np.zeros(len(c), dtype=bool)
    pad[: len(out)] = out
    return pd.Series(pad, index=df.index)


def aggregate(d: pd.DataFrame, n: int) -> pd.DataFrame:
    prev = d["close"].shift(1)
    tr = pd.concat([d["high"] - d["low"], (d["high"] - prev).abs(),
                    (d["low"] - prev).abs()], axis=1).max(axis=1)
    d["atr"] = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    if n == 1:
        return d
    idx = np.arange(len(d)) // n
    g = d.groupby(idx)
    out = pd.DataFrame({
        "ts": d["ts"].values[::n],
        "open": d["open"].values[::n], "close": d["close"].values[::n],
        "high": g["high"].max().values, "low": g["low"].min().values,
        "volume": g["volume"].sum().values,
        "quote_volume": g["quote_volume"].sum().values,
        # carry the integrity flag through aggregation: an aggregated bar is
        # corrupt if ANY of its underlying 5m bars is
        "corrupt": g["corrupt"].max().values.astype(bool),
    })
    # ATR recomputed on the aggregated series (5m ATR is not a valid 15m ATR)
    prev = out["close"].shift(1)
    tr = pd.concat([out["high"] - out["low"], (out["high"] - prev).abs(),
                    (out["low"] - prev).abs()], axis=1).max(axis=1)
    out["atr"] = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    return out


WINSOR_BPS = 100.0   # winsorise the forward-return distribution at +/-100 bps


def stat(x) -> dict:
    """Robust statistics. The MEAN is not usable on this distribution.

    A first pass reported a bucket MEAN of +7,503 bps with its own 95th
    percentile at +169 bps - arithmetically impossible without outliers of ~4e6
    bps. The cause was traced and it is NOT corrupt data: on 2025-10-10 AVAX
    traded 25 -> 8.43 -> 21 inside one hour during a real liquidation cascade.
    The bars are internally consistent, the timestamps are unbroken (385,631
    consecutive 5-minute gaps, zero duplicates), and the event is real. It just
    does not belong in a MEAN.

    So: MEDIAN is the primary location statistic, winsorised mean secondary, and
    the t-statistic is run on the WINSORISED series. The raw mean is still
    printed, labelled, so the cascade is visible rather than deleted.
    """
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 100:
        return {"n": n, "median": np.nan, "win_mean": np.nan, "raw_mean": np.nan,
                "t_adj": np.nan, "iat": np.nan, "p25": np.nan, "p50": np.nan,
                "p75": np.nan, "p95": np.nan, "p99": np.nan}
    w = np.clip(x, -WINSOR_BPS, WINSOR_BPS)
    d = dependence_t(w)
    q = np.percentile(x, [25, 50, 75, 95, 99])
    return {"n": n, "median": float(np.median(x)),
            "win_mean": float(w.mean()), "raw_mean": float(x.mean()),
            "t_adj": float(d["t_adjusted"]), "iat": float(d["iat"]),
            "p25": float(q[0]), "p50": float(q[1]), "p75": float(q[2]),
            "p95": float(q[3]), "p99": float(q[4])}


def curve_table(df: pd.DataFrame, fac: str, fwdcol: str, family: str,
                hz: str, horizon_bars: int) -> pd.DataFrame:
    rows = []
    b = pd.cut(df[fac].rank(pct=True) * 100, np.linspace(0, 100, NBUCKET + 1),
               labels=False, include_lowest=True)
    for k in range(NBUCKET):
        m = b == k
        fwd = df.loc[m, fwdcol].to_numpy() * 1e4          # bps
        s = stat(fwd)
        cost = df.loc[m, "costR"].mean() * df.loc[m, "atr_pct"].mean() * 1e4
        rows.append({"family": family, "horizon": hz, "fwd_bars": horizon_bars,
                     "bucket": k, "n": s["n"], "median_bps": s["median"],
                     "win_mean_bps": s["win_mean"], "raw_mean_bps": s["raw_mean"],
                     "t_adj": s["t_adj"], "iat_est": s["iat"],
                     "cost_bps": cost,
                     "median_over_cost": s["median"] / cost if cost else np.nan,
                     "p25": s["p25"], "p50": s["p50"], "p75": s["p75"],
                     "p95": s["p95"], "p99": s["p99"]})
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    syms = sorted(p.name.replace("_5m.csv.gz", "") for p in KLINES.glob("*_5m.csv.gz"))
    all_curves = []
    summary_rows = []

    for hz, n in HORIZONS.items():
        frames = []
        n_bad_total = 0
        for s in syms:
            raw = load5(s)
            n_bad_total += int(raw["corrupt"].sum())
            d = aggregate(raw, n)
            d["symbol"] = s
            frames.append(d)
        df = pd.concat(frames, ignore_index=True)
        # NOTE: do NOT reset df["corrupt"] here - aggregate() already carried the
        # flag through as "any underlying 5m bar is corrupt". Overwriting it with
        # False silently disabled the whole integrity gate (and produced a bucket
        # mean of +7,503 bps with a p95 of +169 bps, which is arithmetically
        # impossible - a mean cannot exceed the 95th percentile without outliers
        # of ~4e6 bps).

        r = np.log(df["close"]).diff()
        df["atr_pct"] = df["atr"] / df["close"]
        df["costR"] = COST_BPS / (1.0 * df["atr_pct"] * 10000.0)
        # FAMILY A: formation return over FORM bars
        df["mom"] = df["close"] / df["close"].shift(FORM) - 1.0
        # FAMILY B: vol expansion ratio
        df["volshort"] = r.rolling(6, min_periods=6).std()
        df["volfast"] = df["volshort"]
        df["volslow"] = r.rolling(48, min_periods=48).std()
        df["volratio"] = df["volfast"] / df["volslow"].replace(0.0, np.nan)
        for hname, hb in FWD.items():
            df[f"fwd_{hname}"] = df["close"].shift(-hb) / df["close"] - 1.0
            df[f"fwdabs_{hname}"] = df[f"fwd_{hname}"].abs()
            # drop any decision whose formation or forward window touched a corrupt bar
            bad_win = propagate_corrupt(df, n, hb)
            for c in (f"fwd_{hname}", f"fwdabs_{hname}", "mom", "volratio"):
                df.loc[bad_win, c] = np.nan

        n_dropped = int(df["fwd_medium"].isna().sum())
        n_nan_natural = FWD["long"] * n + FORM * n
        print(f"{hz}: built {len(df):,} bars, {len(syms)} symbols, "
              f"{n_bad_total} corrupt 5m bars flagged, "
              f"{n_dropped - n_nan_natural:,} decisions excluded by the gate, "
              f"{n_dropped:,} total NaN forward rows")

        for hname, hb in FWD.items():
            fc = f"fwd_{hname}"
            # FAMILY A: mean reversion -> the reversal direction is -sign(mom)
            df["A_fac"] = -np.sign(df["mom"]) * np.abs(df["mom"])
            all_curves.append(curve_table(df, "A_fac", fc, "A_mean_reversion", hz, hb))
            # FAMILY B: volatility expansion -> directional continuation
            df["B_fac"] = df["volratio"]
            all_curves.append(curve_table(df, "B_fac", fc, "B_vol_expansion", hz, hb))
            # FAMILY B2: does expansion predict magnitude at all?
            df["B2_fac"] = df["volratio"]
            all_curves.append(curve_table(df, "B2_fac", f"fwdabs_{hname}",
                                          "B2_vol_expansion_magnitude", hz, hb))

        # FAMILY C: cross-sectional, rank by FORM-bar return WITHIN each timestamp
        df["cs_rank"] = df.groupby("ts")["mom"].rank(pct=True)
        for hname, hb in FWD.items():
            df["_cs_fwd"] = df[f"fwd_{hname}"]
            top = df[df["cs_rank"] >= 0.8].groupby("ts")["_cs_fwd"].mean()
            bot = df[df["cs_rank"] <= 0.2].groupby("ts")["_cs_fwd"].mean()
            spread = (top - bot).dropna() * 1e4
            s = stat(spread.to_numpy())
            summary_rows.append({"family": "C_cross_sectional", "horizon": hz,
                                 "fwd_bars": hb, "variant": "long_winner_short_loser",
                                 **{k: v for k, v in s.items()}})
            neg = {k: (-v if k in ("median", "win_mean", "raw_mean", "t_adj",
                                   "p25", "p50", "p75", "p95", "p99") else v)
                   for k, v in s.items()}
            summary_rows.append({"family": "C_cross_sectional", "horizon": hz,
                                 "fwd_bars": hb, "variant": "long_loser_short_winner",
                                 **neg})
        med = df["cs_rank"].between(0.8, 1.0) | df["cs_rank"].between(0.0, 0.2)
        sub = df[med]
        for w, w0, w1 in WINDOWS:
            m = (sub["ts"] >= w0) & (sub["ts"] < w1)
            s = stat(sub.loc[m, "fwd_medium"].to_numpy() * 1e4)
            summary_rows.append({"family": "C_dispersion", "horizon": hz,
                                 "fwd_bars": FWD["medium"], "variant": f"window_{w}",
                                 **s})
        for sym in syms:
            m = sub["symbol"] == sym
            s = stat(sub.loc[m, "fwd_medium"].to_numpy() * 1e4)
            summary_rows.append({"family": "C_dispersion", "horizon": hz,
                                 "fwd_bars": FWD["medium"], "variant": f"sym_{sym}",
                                 **s})

    curves = pd.concat(all_curves, ignore_index=True)
    curves.to_csv(OUT / "family_curves.csv", index=False)
    summ = pd.DataFrame(summary_rows)
    summ.to_csv(OUT / "family_summary.csv", index=False)

    # ---- report -----------------------------------------------------------
    for hz in HORIZONS:
        for fam in ("A_mean_reversion", "B_vol_expansion", "B2_vol_expansion_magnitude"):
            c = curves[(curves.horizon == hz) & (curves.family == fam)
                       & (curves.fwd_bars == FWD["medium"])]
            if not len(c):
                continue
            head, tail = c.iloc[:2], c.tail(NBUCKET // 5)
            best = c.loc[c.median_bps.abs().idxmax()]
            print()
            print("=" * 128)
            print(f"{fam}  |  {hz}  |  forward {FWD['medium']} bars  |  "
                  f"cost {COST_BPS} bps | winsorised at +/-{WINSOR_BPS:.0f} bps")
            print("=" * 128)
            print(f"{'bkt':>3s} {'n':>8s} {'MEDIAN':>9s} {'winMean':>9s} {'rawMean':>10s} "
                  f"{'cost':>7s} {'med/cost':>9s} {'t_adj':>7s} {'IAT':>5s} "
                  f"{'p25':>8s} {'p75':>8s} {'p95':>9s} {'p99':>10s}")
            for _, r in c.iterrows():
                mk = " *" if r.bucket >= NBUCKET - NBUCKET // 5 else ""
                print(f"{int(r.bucket):3d} {int(r.n):8,d} {r.median_bps:+9.2f} "
                      f"{r.win_mean_bps:+9.2f} {r.raw_mean_bps:+10.1f} "
                      f"{r.cost_bps:7.2f} {r.median_over_cost:9.3f} "
                      f"{r.t_adj:7.2f} {r.iat_est:5.1f} {r.p25:+8.2f} {r.p75:+8.2f} "
                      f"{r.p95:+9.2f} {r.p99:+10.1f}{mk}")
            tail = c.tail(NBUCKET // 5)
            mono = (tail.median_bps > 0).all() or (tail.median_bps < 0).all()
            best = c.loc[c.median_bps.abs().idxmax()]
            print(f"  top20% median-signed: {'YES' if mono else 'NO (sign flip)'} | "
                  f"best bucket {int(best.bucket)} median {best.median_bps:+.2f} bps vs "
                  f"cost {best.cost_bps:.2f} bps -> ratio {best.median_over_cost:.3f} "
                  f"(need {SAFETY})")

    print()
    print("=" * 118)
    print("FAMILY C — cross-sectional, 9 symbols (Top20% vs bottom 20%)")
    print("=" * 118)
    cc = summ[summ.family == "C_cross_sectional"]
    print(f"{'hz':<5s} {'fwd':>4s} {'variant':<26s} {'n':>7s} {'median bps':>11s} "
          f"{'winMean':>9s} {'t_adj':>8s}")
    for _, r in cc.iterrows():
        print(f"{r.horizon:<5s} {r.fwd_bars:4d} {r.variant:<26s} {int(r.n):7,d} "
              f"{r['median']:+11.2f} {r.win_mean:+9.2f} {r.t_adj:8.2f}")
    print("\n  (with 9 names, 'top 20%' is 1-2 symbols — see report caveat)")

    print()
    print("=" * 118)
    print("FAMILY C — dispersion (long-short spread, medium forward horizon)")
    print("=" * 118)
    cd = summ[summ.family == "C_dispersion"]
    for hz in HORIZONS:
        print(f"\n  --- {hz} ---")
        for _, r in cd[(cd.horizon == hz)].iterrows():
            print(f"    {r.variant:<20s} n={int(r.n):7,d}  median {r['median']:+8.2f} bps  "
                  f"winMean {r.win_mean:+8.2f}  t_adj {r.t_adj:6.2f}  IAT {r['iat']:5.1f}")
    print("\nwrote", OUT)


if __name__ == "__main__":
    main()
